"""
REFINET Cloud — Broker Routes
Create and manage brokered sessions between service providers and consumers.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.broker import (
    create_session, get_session, list_sessions,
    complete_session, cancel_session, get_broker_fee,
)

router = APIRouter(prefix="/broker", tags=["broker"])


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


@router.post("/sessions")
def create_broker_session(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Request a new brokered session.
    Body: { service_type: "deploy"|"audit"|"consult"|"custom", config?: {}, provider_id?: str }
    """
    user_id = _get_user_id(request, db)
    service_type = body.get("service_type")
    if not service_type:
        raise HTTPException(status_code=400, detail="service_type is required")

    result = create_session(
        db, client_id=user_id,
        service_type=service_type,
        config=body.get("config"),
        provider_id=body.get("provider_id"),
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.commit()
    return result


@router.get("/sessions")
def get_broker_sessions(
    request: Request,
    role: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(public_db_dependency),
):
    """List broker sessions. Optional role filter: 'client' or 'provider'."""
    user_id = _get_user_id(request, db)
    return list_sessions(db, user_id, role=role, status=status, limit=limit, offset=offset)


@router.get("/sessions/{session_id}")
def get_broker_session_detail(
    session_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get broker session details."""
    user_id = _get_user_id(request, db)
    result = get_session(db, session_id, user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.post("/sessions/{session_id}/complete")
async def complete_broker_session(
    session_id: str,
    request: Request,
    body: dict = None,
    db: Session = Depends(public_db_dependency),
):
    """Mark a broker session as completed."""
    user_id = _get_user_id(request, db)
    result = await complete_session(db, session_id, result=body, user_id=user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.commit()
    return result


@router.post("/sessions/{session_id}/cancel")
def cancel_broker_session(
    session_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Cancel a broker session."""
    user_id = _get_user_id(request, db)
    result = cancel_session(db, session_id, user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.commit()
    return result


@router.get("/fees/{service_type}")
def broker_fee(
    service_type: str,
    db: Session = Depends(public_db_dependency),
):
    """Get the fee structure for a broker service type."""
    return get_broker_fee(db, service_type)
