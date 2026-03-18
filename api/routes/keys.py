"""REFINET Cloud — API Key Routes"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_KEYS_WRITE
from api.auth.api_keys import create_api_key, revoke_api_key
from api.models.public import ApiKey, UsageRecord

router = APIRouter(prefix="/keys", tags=["keys"])


def _get_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(auth_header[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not verify_scope(payload, SCOPE_KEYS_WRITE):
        raise HTTPException(status_code=403, detail="Requires keys:write scope")
    return payload["sub"]


@router.post("")
def create_key(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request)
    raw_key, record = create_api_key(
        db, user_id,
        name=body.get("name", "default"),
        scopes=body.get("scopes", "inference:read"),
        daily_limit=body.get("daily_limit", 100),
    )
    return {
        "id": record.id,
        "key": raw_key,  # shown ONCE
        "prefix": record.key_prefix,
        "name": record.name,
        "scopes": record.scopes,
        "daily_limit": record.daily_limit,
        "message": "Save this key — it won't be shown again.",
    }


@router.get("")
def list_keys(request: Request, db: Session = Depends(public_db_dependency)):
    user_id = _get_user_id(request)
    keys = db.query(ApiKey).filter(
        ApiKey.user_id == user_id,
        ApiKey.is_active == True,  # noqa: E712
    ).all()
    return [
        {
            "id": k.id,
            "prefix": k.key_prefix,
            "name": k.name,
            "scopes": k.scopes,
            "daily_limit": k.daily_limit,
            "requests_today": k.requests_today,
            "last_used_at": k.last_used_at,
            "created_at": k.created_at,
        }
        for k in keys
    ]


@router.delete("/{key_id}")
def delete_key(
    key_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request)
    if not revoke_api_key(db, key_id, user_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "Key revoked"}


@router.get("/activity")
def recent_activity(request: Request, db: Session = Depends(public_db_dependency)):
    """Get the last 5 usage records for the current user."""
    user_id = _get_user_id(request)
    records = db.query(UsageRecord).filter(
        UsageRecord.user_id == user_id,
    ).order_by(UsageRecord.created_at.desc()).limit(5).all()
    return [
        {
            "id": r.id,
            "endpoint": r.endpoint,
            "tokens_used": r.tokens_used,
            "latency_ms": r.latency_ms,
            "created_at": str(r.created_at),
        }
        for r in records
    ]


@router.get("/{key_id}/usage")
def key_usage(
    key_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request)
    key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == user_id,
    ).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    return {
        "id": key.id,
        "requests_today": key.requests_today,
        "daily_limit": key.daily_limit,
        "last_used_at": key.last_used_at,
    }
