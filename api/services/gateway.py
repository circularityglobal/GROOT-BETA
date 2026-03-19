"""
REFINET Cloud — Model Gateway Service
Universal entry point for inference across all configured providers.
Handles routing, fallback, and SSE normalization.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from api.services.providers.base import (
    BaseProvider,
    ProviderType,
    InferenceResult,
    StreamResult,
)
from api.services.providers.registry import ProviderRegistry

logger = logging.getLogger("refinet.gateway")


class ModelGateway:
    """
    Singleton gateway — sole entry point for all inference.
    Routes to the correct provider, handles fallback on error.
    """

    _instance: Optional["ModelGateway"] = None

    def __init__(self):
        self._registry = ProviderRegistry.get()
        self._initialized = False

    @classmethod
    def get(cls) -> "ModelGateway":
        if cls._instance is None:
            cls._instance = ModelGateway()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None
        ProviderRegistry.reset()

    async def initialize(self):
        """
        Called at startup (from lifespan).
        Reads settings, instantiates providers for all non-empty config entries,
        registers them in ProviderRegistry.
        """
        from api.config import get_settings
        settings = get_settings()
        registry = self._registry

        # BitNet is always registered (may be unhealthy but always present)
        from api.services.providers.bitnet import BitNetProvider
        registry.register(BitNetProvider(settings.bitnet_host))

        # Gemini — enabled when API key is set
        gemini_key = getattr(settings, "gemini_api_key", "")
        if gemini_key:
            try:
                from api.services.providers.gemini import GeminiProvider
                models_str = getattr(settings, "gemini_models", "gemini-2.0-flash,gemini-2.5-flash,gemini-2.5-pro")
                models = [m.strip() for m in models_str.split(",") if m.strip()]
                safety = getattr(settings, "gemini_safety_threshold", "BLOCK_MEDIUM_AND_ABOVE")
                registry.register(GeminiProvider(
                    api_key=gemini_key,
                    default_models=models,
                    safety_threshold=safety,
                ))
            except ImportError:
                logger.warning("Gemini provider module not found, skipping")

        # Ollama — enabled when host is set
        ollama_host = getattr(settings, "ollama_host", "")
        if ollama_host:
            try:
                from api.services.providers.ollama import OllamaProvider
                registry.register(OllamaProvider(host=ollama_host))
            except ImportError:
                logger.warning("Ollama provider module not found, skipping")

        # LM Studio — enabled when host is set
        lmstudio_host = getattr(settings, "lmstudio_host", "")
        if lmstudio_host:
            try:
                from api.services.providers.lmstudio import LMStudioProvider
                registry.register(LMStudioProvider(host=lmstudio_host))
            except ImportError:
                logger.warning("LM Studio provider module not found, skipping")

        # OpenRouter — enabled when API key is set
        openrouter_key = getattr(settings, "openrouter_api_key", "")
        if openrouter_key:
            try:
                from api.services.providers.openrouter import OpenRouterProvider
                registry.register(OpenRouterProvider(api_key=openrouter_key))
            except ImportError:
                logger.warning("OpenRouter provider module not found, skipping")

        # Set fallback chain from config
        chain_str = getattr(settings, "provider_fallback_chain", "bitnet,gemini,ollama,lmstudio,openrouter")
        chain = []
        for p in chain_str.split(","):
            p = p.strip()
            if p:
                try:
                    chain.append(ProviderType(p))
                except ValueError:
                    logger.warning("Unknown provider in fallback chain: %s", p)
        if chain:
            registry.set_fallback_chain(chain)

        self._initialized = True
        providers = registry.registered_providers()
        logger.info(
            "Model gateway initialized with %d providers: %s",
            len(providers),
            [p.value for p in providers],
        )

    async def complete(
        self,
        messages: list[dict],
        model: str = "bitnet-b1.58-2b",
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
        grounding: bool = False,
    ) -> InferenceResult:
        """
        Non-streaming completion through the gateway.
        Resolves provider, attempts inference, falls back on error.
        """
        provider = self._registry.resolve_with_fallback(model)
        if provider is None:
            return InferenceResult(
                content="No inference providers are configured.",
                model=model,
                provider="none",
                finish_reason="error",
            )

        try:
            kwargs: dict = dict(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens, top_p=top_p,
            )
            if grounding:
                kwargs["grounding"] = True
            result = await provider.complete(**kwargs)
            return result
        except Exception as e:
            logger.error(
                "Provider %s failed for model %s: %s",
                provider.provider_type.value, model, e,
            )
            # Try fallback
            fallback = self._get_fallback(provider.provider_type)
            if fallback and fallback.provider_type != provider.provider_type:
                logger.info(
                    "Failover: %s → %s",
                    provider.provider_type.value,
                    fallback.provider_type.value,
                )
                try:
                    # Use fallback's default model
                    fallback_model = fallback.list_models()[0] if fallback.list_models() else model
                    return await fallback.complete(
                        messages=messages,
                        model=fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                    )
                except Exception as e2:
                    logger.error("Fallback provider also failed: %s", e2)

            return InferenceResult(
                content=f"Inference error: {str(e)}",
                model=model,
                provider=provider.provider_type.value,
                finish_reason="error",
            )

    async def stream(
        self,
        messages: list[dict],
        model: str = "bitnet-b1.58-2b",
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
        grounding: bool = False,
        result: Optional[StreamResult] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion through the gateway.
        Yields normalized content chunks (provider-agnostic).
        """
        provider = self._registry.resolve_with_fallback(model)
        if provider is None:
            yield "No inference providers are configured."
            return

        try:
            kwargs: dict = dict(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens,
                top_p=top_p, result=result,
            )
            if grounding:
                kwargs["grounding"] = True
            async for chunk in provider.stream(**kwargs):
                yield chunk
        except Exception as e:
            logger.error(
                "Streaming failed for %s: %s",
                provider.provider_type.value, e,
            )
            yield f"\n[Error: {str(e)}]"

    def _get_fallback(self, exclude: ProviderType) -> Optional[BaseProvider]:
        """Get next healthy provider in chain, excluding the given one."""
        for pt in self._registry._fallback_chain:
            if pt != exclude and pt in self._registry._providers:
                if self._registry._is_healthy(pt):
                    return self._registry._providers[pt]
        return None

    @staticmethod
    def create_user_provider(
        provider_type: str,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> Optional[BaseProvider]:
        """
        Create an ephemeral provider instance from a user's own API key.
        Used for BYOK (Bring Your Own Key) inference.
        """
        from api.services.providers.base import ProviderType as PT

        if provider_type in ("openai", "together", "groq", "mistral", "perplexity"):
            from api.services.providers.openai_compat import OpenAICompatProvider
            url_map = {
                "openai": "https://api.openai.com",
                "together": "https://api.together.xyz",
                "groq": "https://api.groq.com/openai",
                "mistral": "https://api.mistral.ai",
                "perplexity": "https://api.perplexity.ai",
            }
            url = base_url or url_map.get(provider_type, "")
            if not url:
                return None
            p = OpenAICompatProvider(base_url=url, api_key=api_key)
            p.provider_type = PT.OPENROUTER  # Use openrouter type for tracking
            p.display_name = f"User: {provider_type}"
            return p

        if provider_type == "anthropic":
            # Anthropic uses a different auth header but same-ish format
            from api.services.providers.openai_compat import OpenAICompatProvider
            url = base_url or "https://api.anthropic.com"
            p = OpenAICompatProvider(
                base_url=url,
                api_key=api_key,
                extra_headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            p.provider_type = PT.OPENROUTER
            p.display_name = "User: anthropic"
            return p

        if provider_type == "gemini":
            from api.services.providers.gemini import GeminiProvider
            return GeminiProvider(api_key=api_key)

        if provider_type == "openrouter":
            from api.services.providers.openrouter import OpenRouterProvider
            return OpenRouterProvider(api_key=api_key)

        if provider_type == "ollama":
            from api.services.providers.ollama import OllamaProvider
            return OllamaProvider(host=base_url or "http://127.0.0.1:11434")

        if provider_type == "lmstudio":
            from api.services.providers.lmstudio import LMStudioProvider
            return LMStudioProvider(host=base_url or "http://127.0.0.1:1234")

        if provider_type == "custom":
            from api.services.providers.openai_compat import OpenAICompatProvider
            if not base_url:
                return None
            p = OpenAICompatProvider(base_url=base_url, api_key=api_key)
            p.display_name = "User: custom"
            return p

        return None


async def provider_health_check_handler(**kwargs):
    """Scheduled task: check health of all registered providers."""
    registry = ProviderRegistry.get()
    for pt in registry.registered_providers():
        provider = registry.get_provider(pt)
        if provider:
            try:
                health = await provider.health_check()
                registry.update_health(pt, health)
                if not health.is_healthy:
                    logger.warning(
                        "Provider %s unhealthy: %s",
                        pt.value, health.error,
                    )
            except Exception as e:
                from api.services.providers.base import ProviderHealth
                registry.update_health(pt, ProviderHealth(
                    is_healthy=False, error=str(e),
                ))


async def provider_model_sync_handler(**kwargs):
    """Scheduled task: refresh dynamic model lists from Ollama/LM Studio."""
    registry = ProviderRegistry.get()
    for pt in (ProviderType.OLLAMA, ProviderType.LMSTUDIO):
        provider = registry.get_provider(pt)
        if provider:
            try:
                health = await provider.health_check()
                if health.is_healthy and health.available_models:
                    # Re-register to update model map
                    registry.register(provider)
            except Exception as e:
                logger.debug("Model sync failed for %s: %s", pt.value, e)
