"""
REFINET Cloud — Base Provider Interface
Strategy pattern ABC that every inference provider implements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Optional


class ProviderType(str, Enum):
    BITNET = "bitnet"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    OPENROUTER = "openrouter"


@dataclass
class InferenceResult:
    """Unified result from any provider."""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    provider: str = ""
    finish_reason: str = "stop"


@dataclass
class StreamResult:
    """Accumulates token counts during streaming for accurate usage records."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    content: str = ""
    model: str = ""
    provider: str = ""


@dataclass
class ProviderHealth:
    """Health check result for a provider."""
    is_healthy: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    available_models: list[str] = field(default_factory=list)


class BaseProvider(ABC):
    """
    Strategy interface for inference providers.
    Every provider implements this contract.
    """

    provider_type: ProviderType
    display_name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
    ) -> InferenceResult:
        """Non-streaming completion. Returns unified InferenceResult."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
        result: Optional[StreamResult] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming completion. Yields content chunks. Populates StreamResult if provided."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check if this provider is reachable and functioning."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return model IDs this provider supports."""
        ...

    def supports_model(self, model: str) -> bool:
        """Check if this provider handles the given model ID."""
        return model in self.list_models()
