"""
REFINET Cloud — Agent Routes
Agent registration, heartbeat, and remote config delivery.
"""

import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_DEVICES_WRITE
from api.auth.api_keys import validate_api_key
from api.models.public import AgentRegistration

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
