"""
REFINET Cloud — Unified Protocol Authentication
Shared auth for REST, GraphQL, gRPC, SOAP, and WebSocket protocols.
"""

from dataclasses import dataclass
from typing import Optional, List
from sqlalchemy.orm import Session

from api.auth.jwt import decode_access_token, verify_scope
from api.auth.api_keys import validate_api_key


class AuthError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class AuthResult:
    user_id: str
    scopes: List[str]
    api_key_id: Optional[str] = None


def authenticate_token(
    token: str,
    db: Session,
    required_scope: Optional[str] = None,
) -> AuthResult:
    """
    Authenticate from any protocol. Token can be JWT or API key (rf_ prefix).
    Returns AuthResult on success, raises AuthError on failure.
    """
    if not token:
        raise AuthError("Missing authentication token")

    # Strip "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    # API key authentication
    if token.startswith("rf_"):
        api_key = validate_api_key(db, token)
        if not api_key:
            raise AuthError("Invalid or rate-limited API key")
        scopes = api_key.scopes.split() if api_key.scopes else []
        if required_scope and required_scope not in scopes:
            raise AuthError(f"API key lacks required scope: {required_scope}", 403)
        return AuthResult(
            user_id=api_key.user_id,
            scopes=scopes,
            api_key_id=api_key.id,
        )

    # JWT authentication
    try:
        payload = decode_access_token(token)
    except Exception:
        raise AuthError("Invalid or expired token")

    scopes = payload.get("scopes", [])
    if required_scope and not verify_scope(payload, required_scope):
        raise AuthError(f"Token lacks required scope: {required_scope}", 403)

    return AuthResult(
        user_id=payload["sub"],
        scopes=scopes,
    )


def authenticate_request_header(
    authorization: str,
    db: Session,
    required_scope: Optional[str] = None,
) -> AuthResult:
    """
    Authenticate from an Authorization header value.
    Convenience wrapper that handles 'Bearer ' prefix.
    """
    if not authorization:
        raise AuthError("Missing Authorization header")
    return authenticate_token(authorization, db, required_scope)
