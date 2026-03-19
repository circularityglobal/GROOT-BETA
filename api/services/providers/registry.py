"""
REFINET Cloud — Provider Registry
Singleton registry of all configured providers.
Handles model-to-provider routing and fallback chain resolution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from api.services.providers.base import (
    BaseProvider,
    ProviderType,
    ProviderHealth,
)

logger = logging.getLogger("refinet.providers.registry")


@dataclass
class ModelEntry:
    """A model available in the platform."""
    model_id: str
    provider_type: ProviderType
    display_name: str
    context_window: int = 4096
    is_free: bool = True
    owned_by: str = "refinet"


# Known context windows for common models
_CONTEXT_WINDOWS = {
    "bitnet-b1.58-2b": 2048,
    "gemini-2.0-flash": 1048576,
    "gemini-2.5-flash": 1048576,
    "gemini-2.5-pro": 1048576,
}

# Provider display names for model entries
_OWNED_BY = {
    ProviderType.BITNET: "refinet",
    ProviderType.GEMINI: "google",
    ProviderType.OLLAMA: "ollama",
    ProviderType.LMSTUDIO: "lmstudio",
    ProviderType.OPENROUTER: "openrouter",
}


class ProviderRegistry:
    """
    Singleton registry of all configured providers and their models.
    """

    _instance: Optional["ProviderRegistry"] = None

    def __init__(self):
        self._providers: dict[ProviderType, BaseProvider] = {}
        self._model_map: dict[str, ProviderType] = {}
        self._health_cache: dict[ProviderType, ProviderHealth] = {}
        self._fallback_chain: list[ProviderType] = [
            ProviderType.BITNET,
            ProviderType.GEMINI,
            ProviderType.OLLAMA,
            ProviderType.LMSTUDIO,
            ProviderType.OPENROUTER,
        ]

    @classmethod
    def get(cls) -> "ProviderRegistry":
        if cls._instance is None:
            cls._instance = ProviderRegistry()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None

    def register(self, provider: BaseProvider):
        """Register a provider and map its models."""
        self._providers[provider.provider_type] = provider
        for model_id in provider.list_models():
            self._model_map[model_id] = provider.provider_type
        logger.info(
            "Registered provider %s with models: %s",
            provider.provider_type.value,
            provider.list_models(),
        )

    def set_fallback_chain(self, chain: list[ProviderType]):
        self._fallback_chain = chain

    def resolve(self, model: str) -> Optional[BaseProvider]:
        """
        Look up the provider for a model ID.
        1. Exact match in model_map.
        2. Prefix heuristic: gemini-* → Gemini, ollama/* → Ollama.
        3. 'auto' or empty → first healthy provider in fallback chain.
        4. Unknown model → OpenRouter as catch-all (if registered).
        """
        # Exact match
        if model in self._model_map:
            pt = self._model_map[model]
            if pt in self._providers:
                return self._providers[pt]

        # Prefix heuristics
        if model.startswith("gemini-"):
            if ProviderType.GEMINI in self._providers:
                return self._providers[ProviderType.GEMINI]
        if model.startswith("ollama/"):
            if ProviderType.OLLAMA in self._providers:
                return self._providers[ProviderType.OLLAMA]
        if model.startswith("lmstudio/"):
            if ProviderType.LMSTUDIO in self._providers:
                return self._providers[ProviderType.LMSTUDIO]
        if model.startswith("openrouter/"):
            if ProviderType.OPENROUTER in self._providers:
                return self._providers[ProviderType.OPENROUTER]

        # Auto: first provider in fallback chain
        if model in ("auto", ""):
            return self._first_healthy_provider()

        # Unknown model: try OpenRouter as catch-all
        if ProviderType.OPENROUTER in self._providers:
            return self._providers[ProviderType.OPENROUTER]

        # Last resort: first registered provider
        if self._providers:
            return next(iter(self._providers.values()))

        return None

    def resolve_with_fallback(self, model: str) -> Optional[BaseProvider]:
        """
        Resolve provider for model. If that provider is unhealthy,
        walk the fallback chain until a healthy provider is found.
        """
        primary = self.resolve(model)
        if primary is None:
            return None

        if self._is_healthy(primary.provider_type):
            return primary

        # Walk fallback chain
        for pt in self._fallback_chain:
            if pt in self._providers and self._is_healthy(pt):
                logger.info(
                    "Failover: %s unhealthy, routing to %s",
                    primary.provider_type.value, pt.value,
                )
                return self._providers[pt]

        # No healthy provider found — return primary anyway (let error propagate)
        return primary

    def list_all_models(self) -> list[ModelEntry]:
        """Return all available models across all registered providers."""
        entries = []
        for pt, provider in self._providers.items():
            for model_id in provider.list_models():
                entries.append(ModelEntry(
                    model_id=model_id,
                    provider_type=pt,
                    display_name=provider.display_name,
                    context_window=_CONTEXT_WINDOWS.get(model_id, 4096),
                    is_free=True,
                    owned_by=_OWNED_BY.get(pt, "community"),
                ))
        return entries

    def get_provider(self, provider_type: ProviderType) -> Optional[BaseProvider]:
        return self._providers.get(provider_type)

    def update_health(self, provider_type: ProviderType, health: ProviderHealth):
        self._health_cache[provider_type] = health

    def get_health(self, provider_type: ProviderType) -> Optional[ProviderHealth]:
        return self._health_cache.get(provider_type)

    def registered_providers(self) -> list[ProviderType]:
        return list(self._providers.keys())

    def _is_healthy(self, provider_type: ProviderType) -> bool:
        cached = self._health_cache.get(provider_type)
        if cached is None:
            # No health data yet — assume healthy (first request will reveal)
            return True
        return cached.is_healthy

    def _first_healthy_provider(self) -> Optional[BaseProvider]:
        for pt in self._fallback_chain:
            if pt in self._providers and self._is_healthy(pt):
                return self._providers[pt]
        # Fallback: return first registered
        if self._providers:
            return next(iter(self._providers.values()))
        return None
