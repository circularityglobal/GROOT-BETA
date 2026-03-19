"""
REFINET Cloud — Admin Routes
Internal DB operations. Role-gated: requires admin role in internal.db.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from api.database import public_db_dependency, internal_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_ADMIN_READ, SCOPE_ADMIN_WRITE
from api.auth.roles import is_admin, grant_role, revoke_role, get_user_roles
from api.models.public import User, ApiKey, DeviceRegistration, AgentRegistration, WebhookSubscription, UsageRecord
from api.models.internal import (
    ServerSecret, AdminAuditLog, ProductRegistry,
    MCPServerRegistry, SystemConfig, RoleAssignment,
    ScheduledTask,
)
from api.schemas.admin import (
    AdminUserSummary, RoleUpdateRequest, SecretCreateRequest,
    SecretListItem, AuditLogEntry, ProductRegistryItem,
    MCPServerItem, SystemConfigItem, PlatformStats,
)
from api.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Encryption for internal secrets ────────────────────────────────

def _encrypt_internal(plaintext: str) -> str:
    """AES-256-GCM encrypt using INTERNAL_DB_ENCRYPTION_KEY."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    settings = get_settings()
    key = bytes.fromhex(settings.internal_db_encryption_key)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _decrypt_internal(encrypted: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    settings = get_settings()
    key = bytes.fromhex(settings.internal_db_encryption_key)
    packed = base64.b64decode(encrypted)
    nonce, ct = packed[:12], packed[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()


# ── Auth helper ────────────────────────────────────────────────────

def _require_admin(request: Request, internal_db: Session) -> tuple[str, str]:
    """Returns (user_id, admin_username). Raises 403 if not admin."""
    auth_header = request.headers.get("Authorization", "")
    admin_secret = request.headers.get("X-Admin-Secret", "")
    settings = get_settings()

    if admin_secret and admin_secret == settings.admin_api_secret:
        return "system", "system"

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = decode_access_token(auth_header[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload["sub"]
    if not is_admin(internal_db, user_id):
        raise HTTPException(status_code=403, detail="Admin role required")

    return user_id, user_id


# ── Users ──────────────────────────────────────────────────────────

@router.get("/users")
def list_users(
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    _require_admin(request, int_db)
    users = pub_db.query(User).all()
    result = []
    for u in users:
        roles = get_user_roles(int_db, u.id)
        result.append(AdminUserSummary(
            id=u.id, email=u.email, username=u.username,
            tier=u.tier,
            auth_layer_1_complete=u.auth_layer_1_complete,
            auth_layer_2_complete=u.auth_layer_2_complete,
            auth_layer_3_complete=u.auth_layer_3_complete,
            is_active=u.is_active, roles=roles,
            created_at=u.created_at,
        ))
    return result


@router.get("/users/{user_id}")
def get_user_detail(
    user_id: str,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    _require_admin(request, int_db)
    user = pub_db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    roles = get_user_roles(int_db, user_id)
    devices = pub_db.query(DeviceRegistration).filter(DeviceRegistration.user_id == user_id).count()
    agents = pub_db.query(AgentRegistration).filter(AgentRegistration.user_id == user_id).count()
    return {
        "user": AdminUserSummary(
            id=user.id, email=user.email, username=user.username,
            tier=user.tier,
            auth_layer_1_complete=user.auth_layer_1_complete,
            auth_layer_2_complete=user.auth_layer_2_complete,
            auth_layer_3_complete=user.auth_layer_3_complete,
            is_active=user.is_active, roles=roles, created_at=user.created_at,
        ),
        "device_count": devices,
        "agent_count": agents,
    }


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    req: RoleUpdateRequest,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    admin_id, admin_name = _require_admin(request, int_db)
    ip = request.client.host if request.client else None

    if req.action == "grant":
        grant_role(int_db, user_id, req.role, admin_name, ip_address=ip)
        return {"message": f"Role '{req.role}' granted to {user_id}"}
    elif req.action == "revoke":
        revoke_role(int_db, user_id, req.role, admin_name, ip_address=ip)
        return {"message": f"Role '{req.role}' revoked from {user_id}"}


# ── Secrets ────────────────────────────────────────────────────────

@router.get("/secrets", response_model=list[SecretListItem])
def list_secrets(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    _require_admin(request, int_db)
    secrets = int_db.query(ServerSecret).all()
    return [
        SecretListItem(
            id=s.id, name=s.name, description=s.description,
            created_by=s.created_by, created_at=s.created_at,
            rotated_at=s.rotated_at,
        )
        for s in secrets
    ]


@router.post("/secrets")
def create_secret(
    req: SecretCreateRequest,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    admin_id, admin_name = _require_admin(request, int_db)

    encrypted = _encrypt_internal(req.value)
    existing = int_db.query(ServerSecret).filter(ServerSecret.name == req.name).first()
    if existing:
        existing.encrypted_value = encrypted
        existing.rotated_at = datetime.now(timezone.utc)
    else:
        secret = ServerSecret(
            id=str(uuid.uuid4()),
            name=req.name,
            encrypted_value=encrypted,
            description=req.description,
            created_by=admin_name,
        )
        int_db.add(secret)

    # Audit
    audit = AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="WRITE_SECRET",
        target_type="secret",
        target_id=req.name,
        ip_address=request.client.host if request.client else None,
    )
    int_db.add(audit)

    return {"message": f"Secret '{req.name}' stored"}


# ── Audit Log ──────────────────────────────────────────────────────

@router.get("/audit", response_model=list[AuditLogEntry])
def get_audit_log(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
    limit: int = 50,
    offset: int = 0,
):
    _require_admin(request, int_db)
    logs = int_db.query(AdminAuditLog).order_by(
        AdminAuditLog.timestamp.desc()
    ).offset(offset).limit(limit).all()
    return [
        AuditLogEntry(
            id=l.id, admin_username=l.admin_username,
            action=l.action, target_type=l.target_type,
            target_id=l.target_id, details=l.details,
            ip_address=l.ip_address, timestamp=l.timestamp,
        )
        for l in logs
    ]


# ── Products ───────────────────────────────────────────────────────

@router.get("/products", response_model=list[ProductRegistryItem])
def list_products(request: Request, int_db: Session = Depends(internal_db_dependency)):
    _require_admin(request, int_db)
    return [
        ProductRegistryItem(
            id=p.id, name=p.name, current_version=p.current_version,
            connection_count=p.connection_count, last_connected_at=p.last_connected_at,
        )
        for p in int_db.query(ProductRegistry).all()
    ]


@router.post("/products")
def register_product(
    body: dict,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    import hashlib
    admin_id, admin_name = _require_admin(request, int_db)
    build_key = f"rf_{body['name'][:2]}_{os.urandom(48).hex()}"
    product = ProductRegistry(
        id=str(uuid.uuid4()),
        name=body["name"],
        build_key_hash=hashlib.sha256(build_key.encode()).hexdigest(),
        notes=body.get("notes"),
    )
    int_db.add(product)
    return {"id": product.id, "name": product.name, "build_key": build_key}


# ── MCP ────────────────────────────────────────────────────────────

@router.get("/mcp", response_model=list[MCPServerItem])
def list_mcp(request: Request, int_db: Session = Depends(internal_db_dependency)):
    _require_admin(request, int_db)
    return [
        MCPServerItem(
            id=s.id, name=s.name, url=s.url,
            transport=s.transport, auth_type=s.auth_type,
            capabilities=json.loads(s.capabilities) if s.capabilities else [],
            status=s.status, is_healthy=s.is_healthy,
        )
        for s in int_db.query(MCPServerRegistry).all()
    ]


@router.post("/mcp")
def register_mcp(body: dict, request: Request, int_db: Session = Depends(internal_db_dependency)):
    _require_admin(request, int_db)
    server = MCPServerRegistry(
        id=str(uuid.uuid4()),
        name=body["name"],
        url=body["url"],
        transport=body.get("transport", "http"),
        auth_type=body.get("auth_type", "none"),
        auth_value=_encrypt_internal(body["auth_value"]) if body.get("auth_value") else None,
        capabilities=json.dumps(body.get("capabilities", [])),
    )
    int_db.add(server)
    return {"id": server.id, "name": server.name}


@router.put("/mcp/{mcp_id}")
def update_mcp(mcp_id: str, body: dict, request: Request, int_db: Session = Depends(internal_db_dependency)):
    _require_admin(request, int_db)
    server = int_db.query(MCPServerRegistry).filter(MCPServerRegistry.id == mcp_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    for field in ["url", "transport", "auth_type", "status"]:
        if field in body:
            setattr(server, field, body[field])
    if "auth_value" in body:
        server.auth_value = _encrypt_internal(body["auth_value"])
    if "capabilities" in body:
        server.capabilities = json.dumps(body["capabilities"])
    return {"message": "Updated"}


# ── System Config ──────────────────────────────────────────────────

@router.get("/system/config")
def get_system_config(request: Request, int_db: Session = Depends(internal_db_dependency)):
    _require_admin(request, int_db)
    return [
        SystemConfigItem(key=c.key, value=c.value, data_type=c.data_type, description=c.description)
        for c in int_db.query(SystemConfig).all()
    ]


@router.put("/system/config")
def update_system_config(body: dict, request: Request, int_db: Session = Depends(internal_db_dependency)):
    admin_id, admin_name = _require_admin(request, int_db)
    existing = int_db.query(SystemConfig).filter(SystemConfig.key == body["key"]).first()
    if existing:
        existing.value = body["value"]
        existing.updated_at = datetime.now(timezone.utc)
        existing.updated_by = admin_name
    else:
        int_db.add(SystemConfig(
            key=body["key"], value=body["value"],
            data_type=body.get("data_type", "string"),
            description=body.get("description"),
            updated_by=admin_name,
        ))
    return {"message": f"Config '{body['key']}' updated"}


# ── Stats ──────────────────────────────────────────────────────────

@router.get("/uptime")
def uptime_stats(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Get uptime statistics from health check logs."""
    _require_admin(request, int_db)
    from api.services.monitor import compute_uptime, get_uptime_seconds
    return {
        "server_uptime_seconds": int(get_uptime_seconds()),
        "last_24h": compute_uptime(int_db, hours=24),
        "last_7d": compute_uptime(int_db, hours=168),
        "last_30d": compute_uptime(int_db, hours=720),
    }


# ── Scheduled Tasks ───────────────────────────────────────────────

@router.get("/scheduled-tasks")
def list_scheduled_tasks_route(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """List all scheduled tasks with status and next run time."""
    _require_admin(request, int_db)
    from api.services.scheduler import list_scheduled_tasks
    return list_scheduled_tasks(int_db)


@router.post("/scheduled-tasks")
def create_scheduled_task_route(
    body: dict,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Create a new scheduled task."""
    admin_id, admin_name = _require_admin(request, int_db)

    required = ["name", "task_type", "schedule", "handler_path"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    if body["task_type"] not in ("interval", "cron", "once"):
        raise HTTPException(status_code=400, detail="task_type must be: interval, cron, or once")

    from api.services.scheduler import create_scheduled_task
    task = create_scheduled_task(
        int_db,
        name=body["name"],
        task_type=body["task_type"],
        schedule=body["schedule"],
        handler_path=body["handler_path"],
        handler_args=json.dumps(body["handler_args"]) if body.get("handler_args") else None,
        created_by=admin_name,
    )

    # Audit
    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="CREATE_SCHEDULED_TASK",
        target_type="scheduled_task",
        target_id=task.id,
        details=json.dumps({"name": body["name"], "task_type": body["task_type"], "schedule": body["schedule"]}),
        ip_address=request.client.host if request.client else None,
    ))

    return {"id": task.id, "name": task.name, "message": "Scheduled task created"}


@router.put("/scheduled-tasks/{task_id}")
def update_scheduled_task_route(
    task_id: str,
    body: dict,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Enable/disable a scheduled task or update its schedule."""
    admin_id, admin_name = _require_admin(request, int_db)

    task = int_db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    if "is_enabled" in body:
        task.is_enabled = bool(body["is_enabled"])
    if "schedule" in body:
        task.schedule = body["schedule"]
    if "handler_args" in body:
        task.handler_args = json.dumps(body["handler_args"]) if body["handler_args"] else None

    task.updated_at = datetime.now(timezone.utc)
    int_db.flush()

    return {"message": f"Task '{task.name}' updated", "is_enabled": task.is_enabled}


@router.delete("/scheduled-tasks/{task_id}")
def delete_scheduled_task_route(
    task_id: str,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Delete a scheduled task."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.services.scheduler import delete_scheduled_task
    if not delete_scheduled_task(int_db, task_id):
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="DELETE_SCHEDULED_TASK",
        target_type="scheduled_task",
        target_id=task_id,
        ip_address=request.client.host if request.client else None,
    ))

    return {"message": "Scheduled task deleted"}


@router.post("/scheduled-tasks/{task_id}/run")
async def run_scheduled_task_now(
    task_id: str,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Force immediate execution of a scheduled task."""
    admin_id, admin_name = _require_admin(request, int_db)

    task = int_db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    from api.services.scheduler import TaskScheduler
    await TaskScheduler.get()._execute(task.name, task.handler_path, task.handler_args)

    # Update run tracking on our session
    task.last_run_at = datetime.now(timezone.utc)
    task.run_count += 1
    int_db.flush()

    # Reload to pick up last_result written by _execute → _update_result (separate session)
    int_db.refresh(task)

    return {"message": f"Task '{task.name}' executed", "last_result": task.last_result}


# ── Script Management ─────────────────────────────────────────────

@router.get("/scripts")
def list_scripts_route(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """List all discovered platform scripts."""
    _require_admin(request, int_db)
    from api.services.script_runner import discover_scripts
    scripts = discover_scripts()
    return [
        {
            "name": s["name"],
            "description": s.get("description", ""),
            "category": s.get("category", ""),
            "requires_admin": s.get("requires_admin", False),
            "file_name": s.get("file_name", ""),
        }
        for s in scripts
    ]


@router.post("/scripts/{script_name}/run")
async def run_script_route(
    script_name: str,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Execute a platform script by name."""
    admin_id, admin_name = _require_admin(request, int_db)

    from api.services.script_runner import execute_script
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    result = await execute_script(
        int_db,
        script_name=script_name,
        args=body.get("args"),
        started_by=admin_name,
    )

    if "error" in result and "execution_id" not in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/scripts/executions")
def list_script_executions_route(
    request: Request,
    script_name: str = None,
    limit: int = 20,
    offset: int = 0,
    int_db: Session = Depends(internal_db_dependency),
):
    """List past script execution history."""
    _require_admin(request, int_db)
    from api.services.script_runner import list_executions
    return list_executions(int_db, script_name=script_name, limit=limit, offset=offset)


# ── Stats ──────────────────────────────────────────────────────────

@router.get("/usage/summary")
def usage_summary(
    request: Request,
    period: str = "week",
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """
    Aggregated usage summary: total calls, tokens consumed, top users, agent task stats.
    Periods: day, week, month.
    """
    _require_admin(request, int_db)
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    if period == "day":
        cutoff = now - timedelta(days=1)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now - timedelta(days=7)

    # Inference usage
    inference_total = pub_db.query(UsageRecord).filter(UsageRecord.created_at >= cutoff).count()
    prompt_tokens = pub_db.query(sqlfunc.sum(UsageRecord.prompt_tokens)).filter(
        UsageRecord.created_at >= cutoff
    ).scalar() or 0
    completion_tokens = pub_db.query(sqlfunc.sum(UsageRecord.completion_tokens)).filter(
        UsageRecord.created_at >= cutoff
    ).scalar() or 0
    avg_latency = pub_db.query(sqlfunc.avg(UsageRecord.latency_ms)).filter(
        UsageRecord.created_at >= cutoff
    ).scalar() or 0

    # Agent task stats
    agent_stats = {}
    try:
        from api.models.agent_engine import AgentTask
        agent_tasks_total = pub_db.query(AgentTask).filter(AgentTask.created_at >= cutoff).count()
        agent_tasks_completed = pub_db.query(AgentTask).filter(
            AgentTask.created_at >= cutoff, AgentTask.status == "completed"
        ).count()
        agent_tasks_failed = pub_db.query(AgentTask).filter(
            AgentTask.created_at >= cutoff, AgentTask.status == "failed"
        ).count()
        agent_tokens = pub_db.query(sqlfunc.sum(AgentTask.tokens_used)).filter(
            AgentTask.created_at >= cutoff
        ).scalar() or 0
        agent_stats = {
            "tasks_total": agent_tasks_total,
            "tasks_completed": agent_tasks_completed,
            "tasks_failed": agent_tasks_failed,
            "tokens_used": agent_tokens,
        }
    except Exception:
        pass

    # Top 5 users by inference calls
    top_users = pub_db.query(
        UsageRecord.user_id,
        sqlfunc.count().label("calls"),
        sqlfunc.sum(UsageRecord.prompt_tokens + UsageRecord.completion_tokens).label("tokens"),
    ).filter(
        UsageRecord.created_at >= cutoff,
        UsageRecord.user_id != None,  # noqa: E711
    ).group_by(UsageRecord.user_id).order_by(sqlfunc.count().desc()).limit(5).all()

    top_user_list = []
    for row in top_users:
        user = pub_db.query(User).filter(User.id == row.user_id).first()
        top_user_list.append({
            "user_id": row.user_id,
            "username": user.username if user else None,
            "calls": row.calls,
            "tokens": row.tokens or 0,
        })

    return {
        "period": period,
        "from": cutoff.isoformat(),
        "to": now.isoformat(),
        "inference": {
            "total_calls": inference_total,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "avg_latency_ms": round(avg_latency, 1),
        },
        "agent_tasks": agent_stats,
        "top_users": top_user_list,
    }


# ── App Store Management ──────────────────────────────────────────

@router.get("/apps")
def admin_list_apps_route(
    request: Request,
    category: str = None,
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 50,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """List all app store listings (including unpublished)."""
    _require_admin(request, int_db)
    from api.services.app_store import admin_list_apps
    return admin_list_apps(pub_db, include_inactive=include_inactive, category=category, page=page, page_size=page_size)


@router.get("/apps/stats")
def admin_app_store_stats_route(
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Get app store statistics."""
    _require_admin(request, int_db)
    from api.services.app_store import admin_store_stats
    return admin_store_stats(pub_db)


@router.post("/apps/publish")
def admin_publish_product_route(
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Admin: publish a product directly to the App Store."""
    admin_id, admin_name = _require_admin(request, int_db)

    name = body.get("name")
    category = body.get("category")
    if not name or not category:
        raise HTTPException(status_code=400, detail="'name' and 'category' are required")

    from api.services.app_store import admin_publish_product
    result = admin_publish_product(
        pub_db,
        admin_user_id=admin_id,
        name=name,
        description=body.get("description", ""),
        category=category,
        readme=body.get("readme"),
        chain=body.get("chain"),
        version=body.get("version", "1.0.0"),
        icon_url=body.get("icon_url"),
        screenshots=body.get("screenshots"),
        tags=body.get("tags"),
        price_type=body.get("price_type", "free"),
        price_amount=float(body.get("price_amount", 0)),
        price_token=body.get("price_token"),
        price_token_amount=float(body["price_token_amount"]) if body.get("price_token_amount") else None,
        license_type=body.get("license_type", "open"),
        download_url=body.get("download_url"),
        external_url=body.get("external_url"),
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Audit
    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="PUBLISH_STORE_PRODUCT",
        target_type="app_listing",
        target_id=result.get("id"),
        details=json.dumps({"name": name, "category": category, "price_type": body.get("price_type", "free")}),
        ip_address=request.client.host if request.client else None,
    ))

    return result


@router.put("/apps/{app_id}/verify")
def admin_verify_app_route(
    app_id: str,
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Admin: verify or unverify an app listing."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.services.app_store import admin_verify_app
    verified = body.get("verified", True)
    result = admin_verify_app(pub_db, app_id, verified=verified)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="VERIFY_APP" if verified else "UNVERIFY_APP",
        target_type="app_listing",
        target_id=app_id,
        ip_address=request.client.host if request.client else None,
    ))

    return result


@router.put("/apps/{app_id}/feature")
def admin_feature_app_route(
    app_id: str,
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Admin: feature or unfeature an app listing."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.services.app_store import admin_feature_app
    featured = body.get("featured", True)
    result = admin_feature_app(pub_db, app_id, featured=featured)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="FEATURE_APP" if featured else "UNFEATURE_APP",
        target_type="app_listing",
        target_id=app_id,
        ip_address=request.client.host if request.client else None,
    ))

    return result


@router.put("/apps/{app_id}/status")
def admin_set_app_status_route(
    app_id: str,
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Admin: activate or deactivate an app listing."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.services.app_store import admin_deactivate_app
    active = body.get("active", True)
    result = admin_deactivate_app(pub_db, app_id, active=active)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="ACTIVATE_APP" if active else "DEACTIVATE_APP",
        target_type="app_listing",
        target_id=app_id,
        ip_address=request.client.host if request.client else None,
    ))

    return result


# ── Submission Review Pipeline ─────────────────────────────────────

@router.get("/submissions")
def admin_list_submissions_route(
    request: Request,
    status: str = None,
    category: str = None,
    page: int = 1,
    page_size: int = 50,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """List all app submissions for review."""
    _require_admin(request, int_db)
    from api.services.submission import admin_list_submissions
    return admin_list_submissions(pub_db, status=status, category=category, page=page, page_size=page_size)


@router.get("/submissions/stats")
def admin_submission_stats_route(
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Get submission pipeline statistics."""
    _require_admin(request, int_db)
    from api.services.submission import submission_stats
    return submission_stats(pub_db)


@router.get("/submissions/{submission_id}")
def admin_get_submission_route(
    submission_id: str,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Get full submission detail with notes."""
    _require_admin(request, int_db)
    from api.services.submission import get_submission_detail
    result = get_submission_detail(pub_db, submission_id)
    if not result:
        raise HTTPException(status_code=404, detail="Submission not found")
    return result


@router.put("/submissions/{submission_id}/claim")
def admin_claim_submission_route(
    submission_id: str,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Claim a submission for review."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.services.submission import claim_submission
    result = claim_submission(pub_db, submission_id, admin_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="CLAIM_SUBMISSION",
        target_type="app_submission",
        target_id=submission_id,
        ip_address=request.client.host if request.client else None,
    ))
    return result


@router.post("/submissions/{submission_id}/notes")
def admin_add_note_route(
    submission_id: str,
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Add a review note to a submission."""
    admin_id, _ = _require_admin(request, int_db)
    content = body.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="'content' is required")
    from api.services.submission import add_review_note
    result = add_review_note(pub_db, submission_id, admin_id, content, body.get("note_type", "comment"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/submissions/{submission_id}/request-changes")
def admin_request_changes_route(
    submission_id: str,
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Request changes from the developer."""
    admin_id, admin_name = _require_admin(request, int_db)
    reason = body.get("reason")
    if not reason:
        raise HTTPException(status_code=400, detail="'reason' is required")
    from api.services.submission import request_changes
    result = request_changes(pub_db, submission_id, admin_id, reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="REQUEST_CHANGES",
        target_type="app_submission",
        target_id=submission_id,
        details=json.dumps({"reason": reason[:200]}),
        ip_address=request.client.host if request.client else None,
    ))
    return result


@router.put("/submissions/{submission_id}/approve")
def admin_approve_submission_route(
    submission_id: str,
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Approve a submission and publish it to the App Store."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.services.submission import approve_submission
    result = approve_submission(pub_db, submission_id, admin_id, note=body.get("note", ""))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="APPROVE_SUBMISSION",
        target_type="app_submission",
        target_id=submission_id,
        ip_address=request.client.host if request.client else None,
    ))
    return result


@router.put("/submissions/{submission_id}/reject")
def admin_reject_submission_route(
    submission_id: str,
    body: dict,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Reject a submission with reason."""
    admin_id, admin_name = _require_admin(request, int_db)
    reason = body.get("reason")
    if not reason:
        raise HTTPException(status_code=400, detail="'reason' is required")
    from api.services.submission import reject_submission
    result = reject_submission(pub_db, submission_id, admin_id, reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="REJECT_SUBMISSION",
        target_type="app_submission",
        target_id=submission_id,
        details=json.dumps({"reason": reason[:200]}),
        ip_address=request.client.host if request.client else None,
    ))
    return result


# ── Sandbox Management ────────────────────────────────────────────

@router.post("/submissions/{submission_id}/sandbox")
def admin_provision_sandbox_route(
    submission_id: str,
    request: Request,
    body: dict = None,
    int_db: Session = Depends(internal_db_dependency),
):
    """Spin up an isolated Docker sandbox for reviewing a submission."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.services.sandbox import provision_sandbox
    result = provision_sandbox(
        int_db,
        submission_id=submission_id,
        created_by=admin_id,
        resource_limits=(body or {}).get("resource_limits"),
    )
    if "error" in result:
        status = 409 if "already exists" in result["error"] else 400
        raise HTTPException(status_code=status, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="PROVISION_SANDBOX",
        target_type="sandbox",
        target_id=result.get("sandbox_id"),
        details=json.dumps({"submission_id": submission_id}),
        ip_address=request.client.host if request.client else None,
    ))
    return result


@router.get("/submissions/{submission_id}/sandbox")
def admin_get_sandbox_route(
    submission_id: str,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Get sandbox status for a submission."""
    _require_admin(request, int_db)
    from api.models.internal import SandboxEnvironment
    sandbox = int_db.query(SandboxEnvironment).filter(
        SandboxEnvironment.submission_id == submission_id,
        SandboxEnvironment.status.in_(["provisioning", "ready", "running", "stopped"]),
    ).first()
    if not sandbox:
        raise HTTPException(status_code=404, detail="No active sandbox for this submission")
    from api.services.sandbox import get_sandbox_status
    return get_sandbox_status(int_db, sandbox.id)


@router.get("/submissions/{submission_id}/sandbox/logs")
def admin_get_sandbox_logs_route(
    submission_id: str,
    request: Request,
    tail: int = 100,
    int_db: Session = Depends(internal_db_dependency),
):
    """Get runtime logs from the sandbox."""
    _require_admin(request, int_db)
    from api.models.internal import SandboxEnvironment
    sandbox = int_db.query(SandboxEnvironment).filter(
        SandboxEnvironment.submission_id == submission_id,
    ).order_by(SandboxEnvironment.created_at.desc()).first()
    if not sandbox:
        raise HTTPException(status_code=404, detail="No sandbox found for this submission")
    from api.services.sandbox import get_sandbox_logs
    return get_sandbox_logs(int_db, sandbox.id, tail=tail)


@router.delete("/submissions/{submission_id}/sandbox")
def admin_destroy_sandbox_route(
    submission_id: str,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Tear down the sandbox for a submission."""
    admin_id, admin_name = _require_admin(request, int_db)
    from api.models.internal import SandboxEnvironment
    sandbox = int_db.query(SandboxEnvironment).filter(
        SandboxEnvironment.submission_id == submission_id,
        SandboxEnvironment.status.in_(["provisioning", "ready", "running", "stopped"]),
    ).first()
    if not sandbox:
        raise HTTPException(status_code=404, detail="No active sandbox for this submission")
    from api.services.sandbox import destroy_sandbox
    result = destroy_sandbox(int_db, sandbox.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="DESTROY_SANDBOX",
        target_type="sandbox",
        target_id=sandbox.id,
        ip_address=request.client.host if request.client else None,
    ))
    return result


@router.get("/sandboxes")
def admin_list_sandboxes_route(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """List all active sandboxes."""
    _require_admin(request, int_db)
    from api.services.sandbox import list_active_sandboxes
    return list_active_sandboxes(int_db)


# ── Model Providers ───────────────────────────────────────────────

@router.get("/providers")
def list_providers(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """List all configured model providers with health status."""
    _require_admin(request, int_db)
    from api.services.providers.registry import ProviderRegistry
    from api.services.providers.base import ProviderType

    registry = ProviderRegistry.get()
    settings = get_settings()
    result = []

    # All possible providers and their config keys
    provider_defs = [
        {
            "type": "bitnet",
            "name": "BitNet b1.58-2B (Sovereign)",
            "description": "1-bit quantized LLM running on Oracle Cloud. Sovereign infrastructure, zero API cost.",
            "config_key": "BITNET_HOST",
            "config_value": settings.bitnet_host,
            "enabled": True,  # Always registered
        },
        {
            "type": "gemini",
            "name": "Google Gemini",
            "description": "Google AI Studio free tier. Flash: 15 RPM / 1500 daily. Pro: 2 RPM / 50 daily.",
            "config_key": "GEMINI_API_KEY",
            "config_value": "***" if getattr(settings, "gemini_api_key", "") else "",
            "enabled": bool(getattr(settings, "gemini_api_key", "")),
        },
        {
            "type": "ollama",
            "name": "Ollama (Local)",
            "description": "Run open-source models locally. Supports Llama, Mistral, CodeLlama, Phi, and more.",
            "config_key": "OLLAMA_HOST",
            "config_value": getattr(settings, "ollama_host", ""),
            "enabled": bool(getattr(settings, "ollama_host", "")),
        },
        {
            "type": "lmstudio",
            "name": "LM Studio (Local)",
            "description": "Desktop app for running local LLMs with OpenAI-compatible API.",
            "config_key": "LMSTUDIO_HOST",
            "config_value": getattr(settings, "lmstudio_host", ""),
            "enabled": bool(getattr(settings, "lmstudio_host", "")),
        },
        {
            "type": "openrouter",
            "name": "OpenRouter",
            "description": "Multi-model cloud proxy. Access 100+ models including free-tier options.",
            "config_key": "OPENROUTER_API_KEY",
            "config_value": "***" if getattr(settings, "openrouter_api_key", "") else "",
            "enabled": bool(getattr(settings, "openrouter_api_key", "")),
        },
    ]

    for pdef in provider_defs:
        try:
            pt = ProviderType(pdef["type"])
        except ValueError:
            pt = None

        health = registry.get_health(pt) if pt else None
        provider = registry.get_provider(pt) if pt else None
        models = provider.list_models() if provider else []

        result.append({
            **pdef,
            "registered": pt in registry._providers if pt else False,
            "healthy": health.is_healthy if health else None,
            "latency_ms": health.latency_ms if health else None,
            "error": health.error if health and not health.is_healthy else None,
            "models": models,
        })

    # Get fallback chain
    chain = [p.value for p in registry._fallback_chain]

    # Get default model
    default_model = getattr(settings, "default_model", "bitnet-b1.58-2b")

    return {
        "admin_wallet": settings.admin_wallet,
        "default_model": default_model,
        "fallback_chain": chain,
        "providers": result,
    }


@router.get("/providers/health")
async def check_all_provider_health(
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """Force health check on all registered providers."""
    _require_admin(request, int_db)
    from api.services.gateway import provider_health_check_handler
    await provider_health_check_handler()

    from api.services.providers.registry import ProviderRegistry
    registry = ProviderRegistry.get()

    results = {}
    for pt in registry.registered_providers():
        health = registry.get_health(pt)
        results[pt.value] = {
            "healthy": health.is_healthy if health else None,
            "latency_ms": health.latency_ms if health else None,
            "error": health.error if health and not health.is_healthy else None,
            "models": health.available_models if health else [],
        }

    return results


@router.put("/providers/config")
def update_provider_config(
    body: dict,
    request: Request,
    int_db: Session = Depends(internal_db_dependency),
):
    """
    Update provider configuration via SystemConfig.
    Keys: provider.{type}.{setting}
    Example: provider.gemini.daily_limit = "1500"
    """
    admin_id, admin_name = _require_admin(request, int_db)

    key = body.get("key")
    value = body.get("value")
    if not key or value is None:
        raise HTTPException(status_code=400, detail="'key' and 'value' required")

    # Only allow provider.* keys
    if not key.startswith("provider."):
        raise HTTPException(status_code=400, detail="Key must start with 'provider.'")

    existing = int_db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if existing:
        existing.value = str(value)
        existing.updated_at = datetime.now(timezone.utc)
        existing.updated_by = admin_name
    else:
        int_db.add(SystemConfig(
            key=key, value=str(value),
            data_type="string",
            description=f"Provider config: {key}",
            updated_by=admin_name,
        ))

    int_db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=admin_name,
        action="UPDATE_PROVIDER_CONFIG",
        target_type="provider_config",
        target_id=key,
        details=json.dumps({"key": key, "value": str(value)}),
        ip_address=request.client.host if request.client else None,
    ))

    return {"message": f"Provider config '{key}' updated"}


@router.get("/providers/usage")
def provider_usage_stats(
    request: Request,
    period: str = "day",
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Usage breakdown by provider."""
    _require_admin(request, int_db)
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now - timedelta(days=1)

    rows = pub_db.query(
        UsageRecord.provider,
        sqlfunc.count().label("calls"),
        sqlfunc.sum(UsageRecord.prompt_tokens).label("prompt_tokens"),
        sqlfunc.sum(UsageRecord.completion_tokens).label("completion_tokens"),
        sqlfunc.avg(UsageRecord.latency_ms).label("avg_latency"),
    ).filter(
        UsageRecord.created_at >= cutoff,
    ).group_by(UsageRecord.provider).all()

    breakdown = []
    for row in rows:
        breakdown.append({
            "provider": row.provider or "bitnet",
            "calls": row.calls,
            "prompt_tokens": row.prompt_tokens or 0,
            "completion_tokens": row.completion_tokens or 0,
            "avg_latency_ms": round(row.avg_latency or 0, 1),
        })

    return {
        "period": period,
        "from": cutoff.isoformat(),
        "to": now.isoformat(),
        "by_provider": breakdown,
    }


# ── Platform Stats ────────────────────────────────────────────────

@router.get("/stats", response_model=PlatformStats)
def platform_stats(
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    _require_admin(request, int_db)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return PlatformStats(
        total_users=pub_db.query(User).count(),
        active_users_today=pub_db.query(User).filter(
            sqlfunc.date(User.last_login_at) == today
        ).count(),
        total_devices=pub_db.query(DeviceRegistration).filter(
            DeviceRegistration.status == "active"
        ).count(),
        total_agents=pub_db.query(AgentRegistration).count(),
        total_api_keys=pub_db.query(ApiKey).filter(ApiKey.is_active == True).count(),  # noqa
        inference_calls_today=pub_db.query(UsageRecord).filter(
            sqlfunc.date(UsageRecord.created_at) == today
        ).count(),
        total_webhooks=pub_db.query(WebhookSubscription).filter(
            WebhookSubscription.is_active == True  # noqa
        ).count(),
    )
