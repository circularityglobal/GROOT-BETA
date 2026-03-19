"""
REFINET Cloud — User Provider Key Routes
Allows users to manage their own external AI provider API keys.
Keys are encrypted at rest with AES-256-GCM.

SECURITY: All mutating endpoints require full 3-layer auth:
  Layer 3: SIWE (wallet)
  Layer 1: Email + Password
  Layer 2: TOTP (2FA)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.enforce import require_full_auth, require_authenticated

router = APIRouter(prefix="/provider-keys", tags=["provider-keys"])


@router.get("/catalog")
def get_provider_catalog():
    """List all available AI service providers. Public — no auth required."""
    from api.services.provider_keys import get_catalog
    return get_catalog()


@router.get("/security-status")
def get_security_status(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Check if the user has completed all 3 security layers for BYOK access."""
    user_id, user = require_authenticated(request, db)
    return {
        "user_id": user_id,
        "layer_1_complete": user.auth_layer_1_complete,  # Email + Password
        "layer_2_complete": user.auth_layer_2_complete,  # TOTP / 2FA
        "layer_3_complete": user.auth_layer_3_complete,  # SIWE
        "all_layers_complete": (
            user.auth_layer_1_complete
            and user.auth_layer_2_complete
            and user.auth_layer_3_complete
        ),
        "can_manage_keys": (
            user.auth_layer_1_complete
            and user.auth_layer_2_complete
            and user.auth_layer_3_complete
        ),
    }


@router.get("")
def list_keys(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List all provider keys for the authenticated user. Requires full 3-layer auth."""
    user_id, _ = require_full_auth(request, db)
    from api.services.provider_keys import list_provider_keys
    return list_provider_keys(db, user_id)


@router.post("")
def save_key(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Save or update an external provider API key.
    Requires full 3-layer auth (SIWE + Email/Password + TOTP).
    Body: { provider_type, display_name, api_key, base_url? }
    """
    user_id, _ = require_full_auth(request, db)

    provider_type = body.get("provider_type")
    display_name = body.get("display_name")
    api_key = body.get("api_key", "")
    base_url = body.get("base_url")

    if not provider_type:
        raise HTTPException(status_code=400, detail="provider_type is required")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")

    from api.services.provider_keys import PROVIDER_CATALOG
    catalog_entry = next((p for p in PROVIDER_CATALOG if p["type"] == provider_type), None)
    if not catalog_entry:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_type}")

    if catalog_entry["auth_type"] != "url_only" and not api_key:
        raise HTTPException(status_code=400, detail="api_key is required for this provider")

    if catalog_entry["auth_type"] == "url_only":
        if not base_url:
            raise HTTPException(status_code=400, detail="base_url is required for local providers")
        api_key = api_key or "local"

    from api.services.provider_keys import save_provider_key
    result = save_provider_key(
        db, user_id,
        provider_type=provider_type,
        display_name=display_name,
        api_key=api_key,
        base_url=base_url,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/{key_id}")
def delete_key(
    key_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Delete a provider key. Requires full 3-layer auth."""
    user_id, _ = require_full_auth(request, db)
    from api.services.provider_keys import delete_provider_key
    result = delete_provider_key(db, user_id, key_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{key_id}/test")
async def test_key(
    key_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Test a provider key by making a lightweight API call. Requires full 3-layer auth."""
    user_id, _ = require_full_auth(request, db)

    from api.models.public import UserProviderKey
    from api.services.provider_keys import _decrypt, PROVIDER_CATALOG

    key = db.query(UserProviderKey).filter(
        UserProviderKey.id == key_id,
        UserProviderKey.user_id == user_id,
        UserProviderKey.is_active == True,  # noqa: E712
    ).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")

    try:
        decrypted = _decrypt(key.encrypted_key)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt key")

    catalog_entry = next((p for p in PROVIDER_CATALOG if p["type"] == key.provider_type), None)
    base_url = key.base_url or (catalog_entry["base_url"] if catalog_entry else "")

    import httpx
    import time

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {"Authorization": f"Bearer {decrypted}"}
            if key.provider_type == "anthropic":
                headers = {"x-api-key": decrypted, "anthropic-version": "2023-06-01"}
                resp = await client.get(f"{base_url}/v1/models", headers=headers)
            elif key.provider_type == "gemini":
                resp = await client.get(f"{base_url}/models", params={"key": decrypted})
            elif key.provider_type in ("ollama", "lmstudio"):
                resp = await client.get(f"{base_url}/v1/models")
            else:
                resp = await client.get(f"{base_url}/v1/models", headers=headers)

            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                return {"status": "ok", "latency_ms": latency_ms, "provider": key.provider_type, "message": "Connection successful"}
            elif resp.status_code == 401:
                return {"status": "error", "latency_ms": latency_ms, "provider": key.provider_type, "message": "Authentication failed — check your API key"}
            elif resp.status_code == 403:
                return {"status": "error", "latency_ms": latency_ms, "provider": key.provider_type, "message": "Access denied — key may lack required permissions"}
            elif resp.status_code == 429:
                return {"status": "error", "latency_ms": latency_ms, "provider": key.provider_type, "message": "Rate limit exceeded on provider"}
            else:
                return {"status": "error", "latency_ms": latency_ms, "provider": key.provider_type, "message": f"Provider returned HTTP {resp.status_code}"}
    except httpx.ConnectError:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "error", "latency_ms": latency_ms, "provider": key.provider_type, "message": "Connection refused — check the host URL"}
    except httpx.TimeoutException:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "error", "latency_ms": latency_ms, "provider": key.provider_type, "message": "Connection timed out"}
    except Exception:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "error", "latency_ms": latency_ms, "provider": key.provider_type, "message": "Connection failed — check provider URL and key"}
