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
