"""
REFINET Cloud — Provider Registry
Singleton registry of all configured providers.
Handles model-to-provider routing and fallback chain resolution.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from api.services.providers.base import (
    BaseProvider,
    ProviderType,
    ProviderHealth,
)

logger = logging.getLogger("refinet.providers.registry")


class CircuitBreaker:
    """
    Thread-safe in-memory circuit breaker for provider health.
    States: closed (normal) → open (skip) → half_open (probe one request).
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        open_duration: float = 60.0,
        max_open_duration: float = 300.0,
    ):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.last_failure_time = 0.0
        self.open_duration = open_duration
        self.max_open_duration = max_open_duration
        self.state = "closed"
        self._lock = threading.Lock()

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    "Circuit breaker OPEN after %d failures (cooldown %.0fs)",
                    self.failure_count, self.open_duration,
                )

    def record_success(self):
        with self._lock:
            if self.state == "half_open":
                logger.info("Circuit breaker CLOSED — provider recovered")
            self.failure_count = 0
            self.open_duration = 60.0
            self.state = "closed"

    def is_available(self) -> bool:
        with self._lock:
            if self.state == "closed":
                return True
            if self.state == "open":
                elapsed = time.monotonic() - self.last_failure_time
                if elapsed >= self.open_duration:
                    self.state = "half_open"
                    logger.info("Circuit breaker HALF_OPEN — allowing probe")
                    return True
                return False
            # half_open: allow one probe
            return True

    def on_probe_failure(self):
        """Called when a half-open probe fails — reopen with exponential backoff."""
        with self._lock:
            self.state = "open"
            self.open_duration = min(self.open_duration * 2, self.max_open_duration)
            self.last_failure_time = time.monotonic()
            logger.warning(
                "Circuit breaker RE-OPENED (backoff %.0fs)", self.open_duration
            )


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
        self._circuit_breakers: dict[ProviderType, CircuitBreaker] = {}
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
        cb = self._circuit_breakers.setdefault(provider_type, CircuitBreaker())
        if health.is_healthy:
            cb.record_success()
        else:
            if cb.state == "half_open":
                cb.on_probe_failure()
            else:
                cb.record_failure()

    def get_health(self, provider_type: ProviderType) -> Optional[ProviderHealth]:
        return self._health_cache.get(provider_type)

    def registered_providers(self) -> list[ProviderType]:
        return list(self._providers.keys())

    def _is_healthy(self, provider_type: ProviderType) -> bool:
        # Circuit breaker check — skip network call if breaker is open
        cb = self._circuit_breakers.get(provider_type)
        if cb and not cb.is_available():
            return False

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
