"""
REFINET Cloud — Authentication Layer Enforcement
Reusable middleware to require specific auth layers before accessing sensitive resources.

Auth Layers:
  Layer 3: SIWE (wallet signature) — set on signup
  Layer 1: Email + Password — user enables via settings
  Layer 2: TOTP (2FA) — user enables via settings

For sensitive operations (API keys, provider keys, secrets), ALL THREE layers must be complete.
"""

from typing import Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from api.auth.jwt import decode_access_token, verify_scope
from api.models.public import User


def require_full_auth(
    request: Request,
    db: Session,
    scope: Optional[str] = None,
) -> Tuple[str, User]:
    """
    Enforce that the user has completed ALL three auth layers:
      1. Email + Password (auth_layer_1_complete)
      2. TOTP / 2FA (auth_layer_2_complete)
      3. SIWE wallet auth (auth_layer_3_complete)

    Returns (user_id, user) on success.
    Raises HTTPException on failure with a specific error code
    so the frontend can guide users to complete missing layers.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_access_token(auth_header[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Check scope if required
    if scope and not verify_scope(payload, scope):
        raise HTTPException(status_code=403, detail=f"Requires {scope} scope")

    user_id = payload["sub"]

    # Load user from DB to check auth layers
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Check each auth layer and return specific guidance
    missing_layers = []

    if not user.auth_layer_3_complete:
        missing_layers.append("siwe")

    if not user.auth_layer_1_complete:
        missing_layers.append("password")

    if not user.auth_layer_2_complete:
        missing_layers.append("totp")

    if missing_layers:
        detail = {
            "error": "security_layers_required",
            "message": "Complete all security layers to access this feature",
            "missing_layers": missing_layers,
            "instructions": {},
        }
        if "siwe" in missing_layers:
            detail["instructions"]["siwe"] = "Sign in with your Ethereum wallet"
        if "password" in missing_layers:
            detail["instructions"]["password"] = "Set an email and password in Settings → Security"
        if "totp" in missing_layers:
            detail["instructions"]["totp"] = "Enable 2FA (TOTP) in Settings → Security"

        raise HTTPException(status_code=403, detail=detail)

    return user_id, user


def require_authenticated(
    request: Request,
    db: Session,
    scope: Optional[str] = None,
) -> Tuple[str, User]:
    """
    Basic auth check — requires valid JWT and active user.
    Does NOT enforce auth layers. Use for non-sensitive operations.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_access_token(auth_header[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if scope and not verify_scope(payload, scope):
        raise HTTPException(status_code=403, detail=f"Requires {scope} scope")

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    return user_id, user
