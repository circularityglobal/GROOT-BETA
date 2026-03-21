"""
CIFI Federated Identity — REST client for api.cifi.finance.

Validates wallets, fetches profiles, checks KYC status, and registers
new identities through CIFI's partner API.

Security:
  - Partner API key is stored AES-256-GCM encrypted in internal.db (ServerSecret)
  - Fallback to .env CIFI_PARTNER_API_KEY for bootstrap/migration
  - All CIFI response data is validated and sanitized before storage
  - API key is never logged; error messages are generic
"""

import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds

# Strict allowlists for CIFI data sanitization
# Note: _USERNAME_RE is intentionally wider (3-30) than CIFIRegisterRequest (5-15)
# because existing CIFI accounts may have usernames outside the 5-15 registration range.
_USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,30}$")
_DISPLAY_NAME_RE = re.compile(r"^[a-zA-Z0-9 _.'\-]{1,100}$")
_SAFE_TEXT_RE = re.compile(r"[<>&\"';\\/]")  # Characters to strip


def _get_settings():
    """Lazy import to avoid circular dependencies."""
    from api.config import get_settings
    return get_settings()


def _get_cifi_api_key() -> str:
    """
    Retrieve CIFI partner API key from encrypted ServerSecret table,
    with fallback to .env for bootstrap/migration.

    Priority: internal.db ServerSecret → .env CIFI_PARTNER_API_KEY
    """
    try:
        from api.database import get_internal_db
        from api.models.internal import ServerSecret

        with get_internal_db() as int_db:
            secret = int_db.query(ServerSecret).filter(
                ServerSecret.name == "cifi_partner_api_key"
            ).first()
            if secret and secret.encrypted_value:
                return _decrypt_secret(secret.encrypted_value)
    except Exception as e:
        logger.debug("ServerSecret lookup failed, falling back to .env: %s", type(e).__name__)

    # Fallback to .env
    settings = _get_settings()
    key = settings.cifi_partner_api_key
    if key:
        return key
    return ""


def _decrypt_secret(encrypted: str) -> str:
    """Decrypt a ServerSecret value using the platform encryption key."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64

    settings = _get_settings()
    key = bytes.fromhex(settings.internal_db_encryption_key)
    packed = base64.b64decode(encrypted)
    nonce, ct = packed[:12], packed[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()


def _build_headers() -> dict:
    """Build request headers with the CIFI API key. Raises if key is missing."""
    api_key = _get_cifi_api_key()
    if not api_key:
        raise ValueError(
            "CIFI partner API key not configured. "
            "Set it via POST /admin/secrets with name='cifi_partner_api_key'."
        )
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }


def _sanitize_username(raw: str) -> str:
    """
    Validate and sanitize a CIFI username.
    Only lowercase alphanumeric, underscore, and hyphen allowed.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("Invalid username from CIFI")

    cleaned = raw.strip().lower()
    if not _USERNAME_RE.match(cleaned):
        raise ValueError(
            f"CIFI username '{cleaned[:20]}' contains invalid characters or length"
        )
    return cleaned


def _sanitize_display_name(raw: Optional[str]) -> Optional[str]:
    """
    Sanitize a display name from CIFI. Strips HTML/script injection characters.
    Returns None if the input is empty or invalid.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip()[:100]  # Hard limit to 100 chars
    # Strip dangerous characters (HTML, script injection)
    cleaned = _SAFE_TEXT_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def _sanitize_kyc_level(raw: Optional[str]) -> Optional[str]:
    """Validate KYC level against known values."""
    if not raw or not isinstance(raw, str):
        return None
    allowed = {"basic", "intermediate", "advanced", "verified", "none"}
    cleaned = raw.strip().lower()
    return cleaned if cleaned in allowed else None


# ── CIFI API calls ────────────────────────────────────────────────


def validate_wallet(wallet_address: str) -> dict:
    """
    Check if a wallet has a registered CIFI identity.

    Returns:
        {"success": True, "registered": True/False, "data": {...}} on success
    Raises:
        ValueError on API error or network failure
    """
    settings = _get_settings()
    url = f"{settings.cifi_api_url}/federated-identity-validate"
    headers = _build_headers()
    payload = {"wallet_address": wallet_address}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code == 429:
            raise ValueError("CIFI rate limit exceeded. Please try again later.")
        if resp.status_code == 401:
            raise ValueError("CIFI partner API key is invalid or expired.")
        if resp.status_code != 200:
            raise ValueError(f"CIFI identity service returned an error (status {resp.status_code})")

        data = resp.json()
        if not data.get("success"):
            raise ValueError(data.get("error", "CIFI validation failed"))
        return data

    except httpx.TimeoutException:
        raise ValueError("CIFI API is temporarily unavailable. Please try again.")
    except httpx.HTTPError:
        # Never log the full exception which may contain headers/API key
        logger.error("CIFI validate_wallet: network error for wallet %s...%s",
                      wallet_address[:6], wallet_address[-4:])
        raise ValueError("Unable to reach CIFI identity service.")


def get_profile(wallet_address: str) -> dict:
    """
    Fetch full CIFI profile (bio, avatar, social links) by wallet address.

    Returns:
        {"success": True, "data": {"username": ..., "display_name": ..., ...}}
    Raises:
        ValueError on API error
    """
    settings = _get_settings()
    url = f"{settings.cifi_api_url}/federated-identity-profile"
    headers = _build_headers()
    payload = {"wallet_address": wallet_address}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code == 404:
            raise ValueError("User not found on CIFI")
        if resp.status_code != 200:
            raise ValueError(f"CIFI profile service returned an error (status {resp.status_code})")

        data = resp.json()
        if not data.get("success"):
            raise ValueError(data.get("error", "CIFI profile lookup failed"))
        return data

    except httpx.TimeoutException:
        raise ValueError("CIFI API is temporarily unavailable. Please try again.")
    except httpx.HTTPError:
        logger.error("CIFI get_profile: network error for wallet %s...%s",
                      wallet_address[:6], wallet_address[-4:])
        raise ValueError("Unable to reach CIFI identity service.")


def get_verification_status(wallet_address: str) -> dict:
    """
    Query KYC/verification status for a wallet (public endpoint, no auth).

    Returns:
        {"wallet_address": ..., "has_verifications": bool, "verification_summary": {...}}
    """
    settings = _get_settings()
    url = f"{settings.cifi_api_url}/federated-verification-status"

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url, params={"wallet_address": wallet_address})

        if resp.status_code != 200:
            return {"has_verifications": False, "verification_summary": None}

        return resp.json()

    except (httpx.TimeoutException, httpx.HTTPError):
        logger.warning("CIFI verification status unavailable for %s...%s",
                        wallet_address[:6], wallet_address[-4:])
        return {"has_verifications": False, "verification_summary": None}


def register_identity(wallet_address: str, username: str) -> dict:
    """
    Register a new wallet identity on CIFI through our partner API.

    Returns:
        {"success": True, "data": {"user_id": ..., "wallet_address": ..., "username": ...}}
    Raises:
        ValueError on validation error, conflict, or API error
    """
    # Pre-validate username locally before sending to CIFI
    username = _sanitize_username(username)

    settings = _get_settings()
    url = f"{settings.cifi_api_url}/federated-identity-register"
    headers = _build_headers()
    payload = {"wallet_address": wallet_address, "username": username}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code == 409:
            raise ValueError("Wallet or username already registered on CIFI.")
        if resp.status_code == 400:
            data = resp.json()
            raise ValueError(data.get("error", "Invalid registration data"))
        if resp.status_code != 200:
            raise ValueError(f"CIFI registration service returned an error (status {resp.status_code})")

        data = resp.json()
        if not data.get("success"):
            raise ValueError(data.get("error", "CIFI registration failed"))
        return data

    except httpx.TimeoutException:
        raise ValueError("CIFI API is temporarily unavailable. Please try again.")
    except httpx.HTTPError:
        logger.error("CIFI register_identity: network error for wallet %s...%s",
                      wallet_address[:6], wallet_address[-4:])
        raise ValueError("Unable to reach CIFI identity service.")


def check_username(username: str) -> dict:
    """
    Check if a username is available on CIFI.

    Returns:
        {"success": True, "available": bool, "taken": bool, "reserved": bool, "pattern_blocked": bool}
    """
    settings = _get_settings()
    url = f"{settings.cifi_api_url}/federated-identity-check-username"
    headers = _build_headers()
    payload = {"username": username}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            raise ValueError(f"CIFI username check returned an error (status {resp.status_code})")

        return resp.json()

    except httpx.TimeoutException:
        raise ValueError("CIFI API is temporarily unavailable. Please try again.")
    except httpx.HTTPError:
        logger.error("CIFI check_username: network error")
        raise ValueError("Unable to reach CIFI identity service.")


# ── Local DB operations ──────────────────────────────────────────


def store_cifi_verification(
    db,
    user_id: str,
    cifi_data: dict,
    kyc_data: Optional[dict] = None,
) -> "User":
    """
    Store CIFI verification result on the local user record.
    All CIFI response data is validated and sanitized before storage.

    Args:
        db: SQLAlchemy session
        user_id: local user ID
        cifi_data: response['data'] from validate_wallet or get_profile
        kyc_data: response from get_verification_status (optional)
    """
    from api.models.public import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    # Validate and sanitize all CIFI response data
    cifi_username = _sanitize_username(cifi_data.get("username", ""))
    cifi_display_name = _sanitize_display_name(cifi_data.get("display_name"))

    # Pre-check for collisions BEFORE modifying the user object.
    # This prevents leaving the in-memory object in a dirty state on failure.
    cifi_collision = db.query(User).filter(
        User.cifi_username == cifi_username,
        User.id != user_id,
    ).first()
    if cifi_collision:
        raise ValueError(
            f"CIFI username @{cifi_username} is already linked to another account on this platform"
        )

    username_collision = db.query(User).filter(
        User.username == cifi_username,
        User.id != user_id,
    ).first()
    if username_collision:
        raise ValueError(
            f"Username '{cifi_username}' is already taken by another account"
        )

    # All checks passed — now modify the user
    user.cifi_verified = True
    user.cifi_username = cifi_username
    user.cifi_display_name = cifi_display_name
    user.cifi_verified_at = datetime.utcnow()
    user.username = cifi_username  # URL routing: /u/alice_web3

    # KYC level (sanitized against allowlist)
    if kyc_data and kyc_data.get("has_verifications"):
        summary = kyc_data.get("verification_summary") or {}
        user.cifi_kyc_level = _sanitize_kyc_level(summary.get("highest_level"))
    else:
        user.cifi_kyc_level = None

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"CIFI username @{cifi_username} could not be saved due to a conflict"
        )

    db.refresh(user)
    return user


def revoke_cifi_verification(db, user_id: str) -> "User":
    """
    Remove CIFI verification and revert to pseudonymous wallet identity.
    """
    from api.models.public import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    # Revert username to truncated wallet format
    if user.eth_address:
        user.username = f"{user.eth_address[:6]}...{user.eth_address[-4:]}"

    user.cifi_verified = False
    user.cifi_username = None
    user.cifi_display_name = None
    user.cifi_verified_at = None
    user.cifi_kyc_level = None

    db.commit()
    db.refresh(user)
    return user


def reverify_cifi_identity(db, user_id: str) -> dict:
    """
    Re-check a user's CIFI identity. Revokes if no longer valid.

    Returns:
        {"verified": bool, "username": str or None}
    """
    from api.models.public import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.eth_address:
        raise ValueError("User not found")

    try:
        result = validate_wallet(user.eth_address)
    except ValueError:
        revoke_cifi_verification(db, user_id)
        return {"verified": False, "username": None}

    if not result.get("registered"):
        revoke_cifi_verification(db, user_id)
        return {"verified": False, "username": None}

    # Re-fetch KYC
    kyc_data = get_verification_status(user.eth_address)

    cifi_data = result.get("data", {})
    updated_user = store_cifi_verification(db, user_id, cifi_data, kyc_data)
    return {"verified": True, "username": updated_user.cifi_username}
