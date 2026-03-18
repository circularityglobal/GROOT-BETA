"""
REFINET Cloud — JWT Authentication
Scoped access tokens + refresh token rotation.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from sqlalchemy.orm import Session

from api.config import get_settings
from api.models.public import RefreshToken
import uuid
import os


# ── Scopes ──────────────────────────────────────────────────────────

SCOPE_INFERENCE_READ = "inference:read"
SCOPE_KEYS_WRITE = "keys:write"
SCOPE_WEBHOOKS_WRITE = "webhooks:write"
SCOPE_DEVICES_WRITE = "devices:write"
SCOPE_ADMIN_READ = "admin:read"
SCOPE_ADMIN_WRITE = "admin:write"
SCOPE_REGISTRY_READ = "registry:read"
SCOPE_REGISTRY_WRITE = "registry:write"
SCOPE_REGISTRY_ADMIN = "registry:admin"

FULL_USER_SCOPES = [
    SCOPE_INFERENCE_READ,
    SCOPE_KEYS_WRITE,
    SCOPE_WEBHOOKS_WRITE,
    SCOPE_DEVICES_WRITE,
    SCOPE_REGISTRY_READ,
    SCOPE_REGISTRY_WRITE,
]

ADMIN_SCOPES = FULL_USER_SCOPES + [
    SCOPE_ADMIN_READ, SCOPE_ADMIN_WRITE, SCOPE_REGISTRY_ADMIN,
]


# ── Access Tokens ───────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    scopes: list[str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token with scopes."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))

    payload = {
        "sub": user_id,
        "scopes": scopes,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.
    Returns the payload dict.
    Raises jwt.InvalidTokenError on failure.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def verify_scope(token_payload: dict, required_scope: str) -> bool:
    """Check if the token has the required scope."""
    scopes = token_payload.get("scopes", [])
    return required_scope in scopes


# ── Refresh Tokens ──────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, user_id: str) -> tuple[str, datetime]:
    """
    Create a refresh token, store its hash in DB.
    Returns (raw_token, expires_at).
    """
    settings = get_settings()
    raw_token = f"rfrt_{os.urandom(48).hex()}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()

    return raw_token, expires_at


def rotate_refresh_token(
    db: Session,
    old_token: str,
    user_id: str = "",
) -> tuple[str, str, datetime]:
    """
    Rotate a refresh token: revoke old, issue new.
    Returns (new_access_token, new_refresh_token, refresh_expires_at).
    Raises ValueError if old token is invalid/revoked.
    If user_id is empty, it is looked up from the token record.
    """
    old_hash = _hash_token(old_token)

    # Look up by token hash only — user_id is resolved from the record
    record = db.query(RefreshToken).filter(
        RefreshToken.token_hash == old_hash,
        RefreshToken.is_revoked == False,  # noqa: E712
    ).first()

    if not record:
        raise ValueError("Invalid or revoked refresh token")

    # Resolve user_id from the token record
    user_id = record.user_id

    now = datetime.now(timezone.utc)
    if record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise ValueError("Refresh token expired")

    # Issue new refresh token
    new_raw, new_expires = create_refresh_token(db, user_id)

    # Revoke old token and link to new
    record.is_revoked = True
    record.replaced_by = _hash_token(new_raw)
    db.flush()

    # Issue new access token with full scopes
    new_access = create_access_token(user_id, FULL_USER_SCOPES)

    return new_access, new_raw, new_expires


def revoke_all_refresh_tokens(db: Session, user_id: str) -> int:
    """Revoke all refresh tokens for a user (logout)."""
    count = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False,  # noqa: E712
    ).update({"is_revoked": True})
    return count


def cleanup_expired_refresh_tokens(db: Session) -> int:
    """Delete revoked or expired refresh tokens. Called by background cleanup task."""
    now = datetime.now(timezone.utc)
    deleted = db.query(RefreshToken).filter(
        (RefreshToken.is_revoked == True) | (RefreshToken.expires_at < now)  # noqa: E712
    ).delete(synchronize_session=False)
    return deleted
