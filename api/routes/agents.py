"""
REFINET Cloud — Agent Routes
Agent registration, heartbeat, remote config delivery,
SOUL identity, task execution, and delegation.
"""

import json
import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session

from api.database import public_db_dependency, get_public_db
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_DEVICES_WRITE
from api.auth.api_keys import validate_api_key
from api.models.public import AgentRegistration
from api.schemas.agent_engine import (
    SoulCreateRequest, TaskSubmitRequest, DelegationRequest,
)

from api.services.agent_standard import validate_agent_manifest, manifest_to_soul_md

router = APIRouter(prefix="/agents", tags=["agents"])


def _get_user_id(request: Request, db: Session) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    if token.startswith("rf_"):
        api_key = validate_api_key(db, token)
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key.user_id
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


@router.post("/register")
def register_agent(
    request: Request,
    body: dict,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request, db)

    agent = AgentRegistration(
        id=f"ag_{uuid.uuid4().hex[:16]}",
        user_id=user_id,
        name=body.get("name", "unknown"),
        product=body.get("product", "custom"),
        eth_address=body.get("eth_address"),
        version=body.get("version"),
        config=json.dumps({
            "model": "bitnet-b1.58-2b",
            "max_tokens": 512,
            "daily_limit": 100,
            "features_enabled": ["inference", "webhooks"],
        }),
        last_connected_at=datetime.now(timezone.utc),
    )
    db.add(agent)
    db.flush()

    return {
        "agent_id": agent.id,
        "config": json.loads(agent.config),
    }


@router.post("/validate-manifest")
def validate_manifest(
    request: Request,
    body: dict,
    db: Session = Depends(public_db_dependency),
):
    """
    Validate a refinet-agent.yaml manifest against the REFINET Agent Standard.
    Accepts {"manifest": "<yaml string>"} and returns validation results.
    Used by CI pipelines and developers before submission.
    """
    _get_user_id(request, db)  # Must be authenticated

    manifest_content = body.get("manifest", "")
    if not manifest_content:
        raise HTTPException(status_code=400, detail="Missing 'manifest' field with YAML content")

    result = validate_agent_manifest(manifest_content)
    return result


@router.post("/register-with-manifest")
def register_agent_with_manifest(
    request: Request,
    body: dict,
    db: Session = Depends(public_db_dependency),
):
    """
    Register an agent using a refinet-agent.yaml manifest.
    Validates the manifest, creates the agent registration, and auto-creates
    the SOUL identity from the manifest's soul section.
    """
    user_id = _get_user_id(request, db)

    manifest_content = body.get("manifest", "")
    if not manifest_content:
        raise HTTPException(status_code=400, detail="Missing 'manifest' field with YAML content")

    validation = validate_agent_manifest(manifest_content)
    if not validation["valid"]:
        raise HTTPException(status_code=422, detail={
            "message": "Manifest validation failed",
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        })

    manifest = validation["parsed"]
    runtime = manifest.get("runtime", {})

    # Create agent registration
    agent = AgentRegistration(
        id=f"ag_{uuid.uuid4().hex[:16]}",
        user_id=user_id,
        name=manifest["name"],
        product=manifest.get("category", "agent"),
        eth_address=body.get("eth_address"),
        version=manifest.get("version", "1.0.0"),
        config=json.dumps({
            "model": runtime.get("model", "bitnet-b1.58-2b"),
            "max_tokens": runtime.get("max_tokens", 512),
            "daily_limit": runtime.get("daily_limit", 100),
            "features_enabled": runtime.get("features", ["inference"]),
            "entrypoint": runtime.get("entrypoint", "main.py"),
            "language": runtime.get("language", "python"),
            "resources": runtime.get("resources", {}),
            "standard_version": manifest.get("compliance", {}).get("standard_version", "1.0.0"),
        }),
        last_connected_at=datetime.now(timezone.utc),
    )
    db.add(agent)
    db.flush()

    # Auto-create SOUL from manifest
    soul_md = manifest_to_soul_md(manifest)
    from api.services.agent_soul import create_soul
    soul = create_soul(db, agent.id, soul_md)

    return {
        "agent_id": agent.id,
        "name": agent.name,
        "soul_id": soul.id,
        "config": json.loads(agent.config),
        "warnings": validation["warnings"],
        "message": "Agent registered with REFINET Agent Standard manifest",
    }


@router.get("")
def list_agents(request: Request, db: Session = Depends(public_db_dependency)):
    user_id = _get_user_id(request, db)
    agents = db.query(AgentRegistration).filter(
        AgentRegistration.user_id == user_id,
    ).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "product": a.product,
            "version": a.version,
            "last_connected_at": a.last_connected_at,
            "total_inference_calls": a.total_inference_calls,
        }
        for a in agents
    ]


@router.post("/{agent_id}/heartbeat")
def agent_heartbeat(
    agent_id: str,
    request: Request,
    body: dict,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.last_connected_at = datetime.now(timezone.utc)
    if body.get("version"):
        agent.version = body["version"]
    db.flush()

    return {"status": "ok", "agent_id": agent_id}


@router.get("/{agent_id}/config")
def get_agent_config(
    agent_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return json.loads(agent.config) if agent.config else {}


@router.put("/{agent_id}/config")
def update_agent_config(
    agent_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.config = json.dumps(body)
    db.flush()

    return {"message": "Config updated", "agent_id": agent_id}


# ── SOUL Identity ────────────────────────────────────────────────

@router.post("/{agent_id}/soul")
def create_or_update_soul(
    agent_id: str,
    body: SoulCreateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create or update an agent's SOUL identity from markdown."""
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from api.services.agent_soul import create_soul
    soul = create_soul(db, agent_id, body.soul_md)

    return {
        "id": soul.id,
        "agent_id": soul.agent_id,
        "persona": soul.persona,
        "delegation_policy": soul.delegation_policy,
        "message": "Soul created/updated",
    }


@router.get("/{agent_id}/soul")
def get_agent_soul(
    agent_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get an agent's SOUL identity."""
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from api.services.agent_soul import get_soul
    soul = get_soul(db, agent_id)
    if not soul:
        raise HTTPException(status_code=404, detail="Soul not configured")

    return soul


# ── Task Execution ───────────────────────────────────────────────

@router.post("/{agent_id}/run")
async def run_agent_task(
    agent_id: str,
    body: TaskSubmitRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(public_db_dependency),
):
    """Submit a task for an agent to execute through the cognitive loop."""
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from api.services.agent_engine import create_task, AgentCognitiveLoop
    task = create_task(db, agent_id, user_id, body.description)
    task_id = task.id
    db.flush()

    # Run cognitive loop in background
    async def _run_loop():
        with get_public_db() as bg_db:
            from api.services.agent_engine import get_task
            bg_task = get_task(bg_db, task_id, agent_id)
            if bg_task:
                loop = AgentCognitiveLoop(bg_db, agent_id, user_id)
                await loop.run(bg_task)

    background_tasks.add_task(lambda: asyncio.run(_run_loop()))

    return {
        "task_id": task_id,
        "agent_id": agent_id,
        "status": "pending",
        "message": "Task submitted — poll GET /agents/{agent_id}/tasks/{task_id} for status",
    }


@router.get("/{agent_id}/tasks")
def list_agent_tasks(
    agent_id: str,
    request: Request,
    status: str = None,
    db: Session = Depends(public_db_dependency),
):
    """List tasks for an agent."""
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from api.services.agent_engine import list_tasks
    return list_tasks(db, agent_id, status=status)


@router.get("/{agent_id}/tasks/{task_id}")
def get_agent_task(
    agent_id: str,
    task_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get detailed task status including execution trace."""
    user_id = _get_user_id(request, db)
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from api.services.agent_engine import get_task
    task = get_task(db, task_id, agent_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "agent_id": task.agent_id,
        "description": task.description,
        "status": task.status,
        "current_phase": task.current_phase,
        "plan": json.loads(task.plan_json) if task.plan_json else None,
        "steps": json.loads(task.steps_json) if task.steps_json else None,
        "result": json.loads(task.result_json) if task.result_json else None,
        "error_message": task.error_message,
        "tokens_used": task.tokens_used,
        "inference_calls": task.inference_calls,
        "tool_calls": task.tool_calls,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.get("/{agent_id}/tasks/{task_id}/steps")
def get_task_steps(
    agent_id: str,
    task_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get the execution trace for a task."""
    user_id = _get_user_id(request, db)
    from api.services.agent_engine import get_task
    task = get_task(db, task_id, agent_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task.id,
        "status": task.status,
        "steps": json.loads(task.steps_json) if task.steps_json else [],
    }


@router.post("/{agent_id}/tasks/{task_id}/cancel")
def cancel_agent_task(
    agent_id: str,
    task_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Cancel a running or pending task."""
    user_id = _get_user_id(request, db)
    from api.services.agent_engine import cancel_task
    if not cancel_task(db, task_id, agent_id):
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")

    return {"message": "Task cancelled", "task_id": task_id}


# ── Agent-to-Agent Delegation ────────────────────────────────────

@router.post("/{agent_id}/delegate")
async def delegate_to_agent(
    agent_id: str,
    body: DelegationRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Delegate a subtask from this agent to another agent."""
    user_id = _get_user_id(request, db)

    # Verify the source agent exists and belongs to user
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Source agent not found")

    # Need an active task to delegate from — use the most recent running task
    from api.models.agent_engine import AgentTask
    source_task = db.query(AgentTask).filter(
        AgentTask.agent_id == agent_id,
        AgentTask.status == "running",
    ).order_by(AgentTask.created_at.desc()).first()

    if not source_task:
        raise HTTPException(status_code=400, detail="No running task to delegate from")

    from api.services.agent_engine import delegate_task
    delegation = await delegate_task(
        db, agent_id, body.target_agent_id,
        source_task.id, body.subtask_description, user_id,
    )

    if not delegation:
        raise HTTPException(
            status_code=400,
            detail="Delegation rejected — target agent may not accept delegations",
        )

    return {
        "delegation_id": delegation.id,
        "status": delegation.status,
        "source_agent_id": agent_id,
        "target_agent_id": body.target_agent_id,
    }
