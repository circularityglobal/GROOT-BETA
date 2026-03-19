"""
REFINET Cloud — User Provider Key Service
Manages encrypted storage of user-owned external AI provider API keys.
Uses AES-256-GCM encryption with the platform's INTERNAL_DB_ENCRYPTION_KEY.
"""

from __future__ import annotations

import os
import base64
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.config import get_settings
from api.models.public import UserProviderKey

logger = logging.getLogger("refinet.provider_keys")


# ── Provider Catalog ──────────────────────────────────────────────
# Each entry defines a provider that users can connect to.

PROVIDER_CATALOG = [
    {
        "type": "openai",
        "name": "OpenAI",
        "description": "GPT-4o, GPT-4o-mini, DALL-E 3, Whisper, TTS",
        "category": "llm",
        "capabilities": ["chat", "image", "audio", "embedding"],
        "auth_type": "api_key",
        "key_url": "https://platform.openai.com/api-keys",
        "base_url": "https://api.openai.com",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "dall-e-3", "whisper-1", "tts-1"],
        "free_tier": False,
    },
    {
        "type": "anthropic",
        "name": "Anthropic",
        "description": "Claude Opus, Sonnet, Haiku — advanced reasoning and coding",
        "category": "llm",
        "capabilities": ["chat"],
        "auth_type": "api_key",
        "key_url": "https://console.anthropic.com/settings/keys",
        "base_url": "https://api.anthropic.com",
        "models": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
        "free_tier": False,
    },
    {
        "type": "gemini",
        "name": "Google Gemini",
        "description": "Gemini Flash, Pro — free tier with 15 RPM",
        "category": "llm",
        "capabilities": ["chat", "grounding"],
        "auth_type": "api_key",
        "key_url": "https://aistudio.google.com/apikey",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
        "free_tier": True,
    },
    {
        "type": "openrouter",
        "name": "OpenRouter",
        "description": "100+ models from all providers — free and paid tiers",
        "category": "llm",
        "capabilities": ["chat"],
        "auth_type": "api_key",
        "key_url": "https://openrouter.ai/keys",
        "base_url": "https://openrouter.ai/api",
        "models": ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.1-8b-instruct:free"],
        "free_tier": True,
    },
    {
        "type": "replicate",
        "name": "Replicate",
        "description": "Run open-source models — Flux, Stable Diffusion, LLaMA, Whisper",
        "category": "multi",
        "capabilities": ["chat", "image", "audio", "video"],
        "auth_type": "api_key",
        "key_url": "https://replicate.com/account/api-tokens",
        "base_url": "https://api.replicate.com/v1",
        "models": ["meta/llama-3.1-405b", "black-forest-labs/flux-1.1-pro"],
        "free_tier": False,
    },
    {
        "type": "stability",
        "name": "Stability AI",
        "description": "Stable Diffusion 3, Stable Video — image and video generation",
        "category": "image",
        "capabilities": ["image", "video"],
        "auth_type": "api_key",
        "key_url": "https://platform.stability.ai/account/keys",
        "base_url": "https://api.stability.ai",
        "models": ["stable-diffusion-3", "stable-video-diffusion"],
        "free_tier": False,
    },
    {
        "type": "together",
        "name": "Together AI",
        "description": "Fast open-source model inference — Llama, Mixtral, Code Llama",
        "category": "llm",
        "capabilities": ["chat", "embedding"],
        "auth_type": "api_key",
        "key_url": "https://api.together.xyz/settings/api-keys",
        "base_url": "https://api.together.xyz",
        "models": ["meta-llama/Llama-3.1-70B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "free_tier": True,
    },
    {
        "type": "groq",
        "name": "Groq",
        "description": "Ultra-fast LPU inference — Llama, Mixtral at lightning speed",
        "category": "llm",
        "capabilities": ["chat"],
        "auth_type": "api_key",
        "key_url": "https://console.groq.com/keys",
        "base_url": "https://api.groq.com/openai",
        "models": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
        "free_tier": True,
    },
    {
        "type": "mistral",
        "name": "Mistral AI",
        "description": "Mistral Large, Codestral — European AI powerhouse",
        "category": "llm",
        "capabilities": ["chat", "embedding"],
        "auth_type": "api_key",
        "key_url": "https://console.mistral.ai/api-keys",
        "base_url": "https://api.mistral.ai",
        "models": ["mistral-large-latest", "codestral-latest", "mistral-small-latest"],
        "free_tier": False,
    },
    {
        "type": "perplexity",
        "name": "Perplexity",
        "description": "Online LLM with real-time web search built in",
        "category": "llm",
        "capabilities": ["chat", "grounding"],
        "auth_type": "api_key",
        "key_url": "https://www.perplexity.ai/settings/api",
        "base_url": "https://api.perplexity.ai",
        "models": ["sonar-pro", "sonar"],
        "free_tier": False,
    },
    {
        "type": "ollama",
        "name": "Ollama (Local)",
        "description": "Run models locally — no API key needed, just a host URL",
        "category": "local",
        "capabilities": ["chat"],
        "auth_type": "url_only",
        "key_url": "https://ollama.com/download",
        "base_url": "http://127.0.0.1:11434",
        "models": [],
        "free_tier": True,
    },
    {
        "type": "lmstudio",
        "name": "LM Studio (Local)",
        "description": "Desktop app for local models — no API key needed",
        "category": "local",
        "capabilities": ["chat"],
        "auth_type": "url_only",
        "key_url": "https://lmstudio.ai/",
        "base_url": "http://127.0.0.1:1234",
        "models": [],
        "free_tier": True,
    },
    {
        "type": "custom",
        "name": "Custom OpenAI-Compatible",
        "description": "Any service with an OpenAI-compatible /v1/chat/completions endpoint",
        "category": "custom",
        "capabilities": ["chat"],
        "auth_type": "api_key_and_url",
        "key_url": "",
        "base_url": "",
        "models": [],
        "free_tier": False,
    },
]


# ── Encryption ────────────────────────────────────────────────────

def _encrypt(plaintext: str) -> str:
    """AES-256-GCM encrypt a provider API key."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    settings = get_settings()
    key = bytes.fromhex(settings.internal_db_encryption_key)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _decrypt(encrypted: str) -> str:
    """AES-256-GCM decrypt a provider API key."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    settings = get_settings()
    key = bytes.fromhex(settings.internal_db_encryption_key)
    packed = base64.b64decode(encrypted)
    nonce, ct = packed[:12], packed[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()


# ── CRUD Operations ───────────────────────────────────────────────

def save_provider_key(
    db: Session,
    user_id: str,
    provider_type: str,
    display_name: str,
    api_key: str,
    base_url: Optional[str] = None,
) -> dict:
    """Save or update a user's external provider API key."""
    # Validate provider type
    valid_types = {p["type"] for p in PROVIDER_CATALOG}
    if provider_type not in valid_types:
        return {"error": f"Unknown provider type: {provider_type}. Valid: {sorted(valid_types)}"}

    # Check for existing key with same provider + name
    existing = db.query(UserProviderKey).filter(
        UserProviderKey.user_id == user_id,
        UserProviderKey.provider_type == provider_type,
        UserProviderKey.display_name == display_name,
    ).first()

    encrypted = _encrypt(api_key)
    preview = _compute_preview(api_key)

    if existing:
        existing.encrypted_key = encrypted
        existing.key_preview = preview
        existing.base_url = base_url
        existing.is_active = True
        db.flush()
        return {"id": existing.id, "message": "Provider key updated", "updated": True}

    record = UserProviderKey(
        id=str(uuid.uuid4()),
        user_id=user_id,
        provider_type=provider_type,
        display_name=display_name,
        encrypted_key=encrypted,
        key_preview=preview,
        base_url=base_url,
    )
    db.add(record)
    db.flush()
    return {"id": record.id, "message": "Provider key saved", "updated": False}


def list_provider_keys(db: Session, user_id: str) -> list[dict]:
    """List all provider keys for a user (keys masked)."""
    keys = db.query(UserProviderKey).filter(
        UserProviderKey.user_id == user_id,
        UserProviderKey.is_active == True,  # noqa: E712
    ).order_by(UserProviderKey.created_at.desc()).all()

    return [
        {
            "id": k.id,
            "provider_type": k.provider_type,
            "display_name": k.display_name,
            "base_url": k.base_url,
            "has_key": bool(k.encrypted_key),
            "key_preview": k.key_preview or "***",
            "usage_count": k.usage_count,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat() if k.created_at else None,
        }
        for k in keys
    ]


def delete_provider_key(db: Session, user_id: str, key_id: str) -> dict:
    """Delete a user's provider key."""
    key = db.query(UserProviderKey).filter(
        UserProviderKey.id == key_id,
        UserProviderKey.user_id == user_id,
    ).first()
    if not key:
        return {"error": "Provider key not found"}
    db.delete(key)
    db.flush()
    return {"message": "Provider key deleted"}


def get_decrypted_key(db: Session, user_id: str, provider_type: str) -> Optional[tuple[str, Optional[str]]]:
    """
    Get the decrypted API key and base_url for a user's provider.
    Returns (api_key, base_url) or None if not found.
    """
    key = db.query(UserProviderKey).filter(
        UserProviderKey.user_id == user_id,
        UserProviderKey.provider_type == provider_type,
        UserProviderKey.is_active == True,  # noqa: E712
    ).first()
    if not key:
        return None

    try:
        decrypted = _decrypt(key.encrypted_key)
        # Update usage stats
        key.usage_count += 1
        key.last_used_at = datetime.now(timezone.utc)
        db.flush()
        return (decrypted, key.base_url)
    except Exception as e:
        logger.error("Failed to decrypt provider key %s: %s", key.id, e)
        return None


def get_catalog() -> list[dict]:
    """Return the full provider catalog for frontend display."""
    return PROVIDER_CATALOG


def _compute_preview(api_key: str) -> str:
    """Compute a safe preview from the plaintext key at save time. Never decrypt to preview."""
    if not api_key or api_key == "local":
        return "***"
    if len(api_key) > 12:
        return api_key[:4] + "..." + api_key[-4:]
    return api_key[:2] + "..."
