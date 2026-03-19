"""
REFINET Cloud — API Key Routes

SECURITY: Creating and managing API keys requires full 3-layer auth:
  Layer 3: SIWE (wallet)
  Layer 1: Email + Password
  Layer 2: TOTP (2FA)

Read-only operations (list, usage) require basic auth only.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import SCOPE_KEYS_WRITE
from api.auth.api_keys import create_api_key, revoke_api_key
from api.auth.enforce import require_full_auth, require_authenticated
from api.models.public import ApiKey, UsageRecord

router = APIRouter(prefix="/keys", tags=["keys"])


@router.post("")
def create_key(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create a new API key. Requires SIWE + Email/Password + TOTP."""
    user_id, _ = require_full_auth(request, db, scope=SCOPE_KEYS_WRITE)
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
    """List active API keys. Requires full 3-layer auth."""
    user_id, _ = require_full_auth(request, db, scope=SCOPE_KEYS_WRITE)
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
    """Revoke an API key. Requires full 3-layer auth."""
    user_id, _ = require_full_auth(request, db, scope=SCOPE_KEYS_WRITE)
    if not revoke_api_key(db, key_id, user_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "Key revoked"}


@router.get("/activity")
def recent_activity(request: Request, db: Session = Depends(public_db_dependency)):
    """Get last 5 usage records. Basic auth only (read-only)."""
    user_id, _ = require_authenticated(request, db)
    records = db.query(UsageRecord).filter(
        UsageRecord.user_id == user_id,
    ).order_by(UsageRecord.created_at.desc()).limit(5).all()
    return [
        {
            "id": r.id,
            "endpoint": r.endpoint,
            "model": r.model,
            "provider": r.provider,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
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
    """Check key usage. Basic auth only (read-only)."""
    user_id, _ = require_authenticated(request, db)
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
