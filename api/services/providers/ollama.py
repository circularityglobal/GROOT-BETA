"""
REFINET Cloud — Ollama Provider
Local model server with OpenAI-compatible API.
Supports dynamic model discovery via /api/tags.
"""

from __future__ import annotations

import httpx
import logging
import time
from typing import Optional

from api.services.providers.base import ProviderType, ProviderHealth
from api.services.providers.openai_compat import OpenAICompatProvider

logger = logging.getLogger("refinet.providers.ollama")


class OllamaProvider(OpenAICompatProvider):
    provider_type = ProviderType.OLLAMA
    display_name = "Ollama (Local)"

    def __init__(self, host: str = "http://127.0.0.1:11434"):
        super().__init__(
            base_url=host,
            api_key=None,
            default_models=[],
        )

    async def health_check(self) -> ProviderHealth:
        """
        Ollama health check — tries /v1/models first (newer versions),
        falls back to /api/tags (older versions).
        """
        start = time.monotonic()

        # Try OpenAI-compat /v1/models first
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url}/v1/models")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    latency = int((time.monotonic() - start) * 1000)
                    if models:
                        self._cached_models = models
                        self._cache_time = time.monotonic()
                    return ProviderHealth(
                        is_healthy=True,
                        latency_ms=latency,
                        available_models=models,
                    )
        except Exception:
            pass

        # Fallback to Ollama-native /api/tags
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    if models:
                        self._cached_models = models
                        self._cache_time = time.monotonic()
                    return ProviderHealth(
                        is_healthy=True,
                        latency_ms=latency,
                        available_models=models,
                    )
                return ProviderHealth(
                    is_healthy=False,
                    latency_ms=latency,
                    error=f"HTTP {resp.status_code}",
                )
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return ProviderHealth(
                is_healthy=False,
                latency_ms=latency,
                error=str(e),
            )

    def list_models(self) -> list[str]:
        """Return cached models from last health check, or empty list."""
        if self._cached_models and (time.monotonic() - self._cache_time) < 60:
            return self._cached_models
        return self._default_models
