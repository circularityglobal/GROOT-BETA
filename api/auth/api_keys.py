"""
REFINET Cloud — API Key Management
rf_ prefixed keys with SHA256 hashing, daily rate counters, and scoping.
"""

import os
import hashlib
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from api.models.public import ApiKey
import uuid


def generate_api_key(prefix: str = "rf_") -> str:
    """Generate a new API key: prefix + 48 random bytes hex."""
    return f"{prefix}{os.urandom(48).hex()}"


def hash_api_key(key: str) -> str:
    """SHA256 hash of the full API key for storage."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_key_prefix(key: str) -> str:
    """First 12 characters for display."""
    return key[:12]


def create_api_key(
    db: Session,
    user_id: str,
    name: str,
    scopes: str = "inference:read",
    daily_limit: int = 250,
    expires_at: Optional[datetime] = None,
    prefix: str = "rf_",
) -> tuple[str, ApiKey]:
    """
    Create a new API key. Returns (raw_key, db_record).
    The raw_key is returned ONCE — it cannot be recovered after creation.
    """
    raw_key = generate_api_key(prefix)

    record = ApiKey(
        id=str(uuid.uuid4()),
        user_id=user_id,
        key_hash=hash_api_key(raw_key),
        key_prefix=get_key_prefix(raw_key),
        name=name,
        scopes=scopes,
        daily_limit=daily_limit,
        expires_at=expires_at,
        last_reset_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    db.add(record)
    db.flush()

    return raw_key, record


def validate_api_key(db: Session, raw_key: str) -> Optional[ApiKey]:
    """
    Look up an API key by its hash, verify it's active and within limits.
    Returns the ApiKey record if valid, None if invalid.
    Increments the daily counter on valid use.
    """
    key_hash = hash_api_key(raw_key)
    record = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True,  # noqa: E712
    ).first()

    if not record:
        return None

    now = datetime.now(timezone.utc)

    # Check expiry
    if record.expires_at and record.expires_at.replace(tzinfo=timezone.utc) < now:
        return None

    # Reset daily counter if new day
    today = now.strftime("%Y-%m-%d")
    if record.last_reset_date != today:
        record.requests_today = 0
        record.last_reset_date = today

    # Check daily limit
    if record.requests_today >= record.daily_limit:
        return None  # caller should return 429

    # Increment counter
    record.requests_today += 1
    record.last_used_at = now
    db.flush()

    return record


def check_api_key_rate_limit(db: Session, raw_key: str) -> tuple[bool, Optional[ApiKey]]:
    """
    Check if an API key is within its daily rate limit WITHOUT incrementing.
    Returns (is_within_limit, api_key_record).
    """
    key_hash = hash_api_key(raw_key)
    record = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True,  # noqa: E712
    ).first()

    if not record:
        return False, None

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    if record.last_reset_date != today:
        return True, record  # new day, counter will reset

    return record.requests_today < record.daily_limit, record


def revoke_api_key(db: Session, key_id: str, user_id: str) -> bool:
    """Revoke (soft-delete) an API key. Returns True if found and revoked."""
    record = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == user_id,
    ).first()
    if not record:
        return False
    record.is_active = False
    db.flush()
    return True
