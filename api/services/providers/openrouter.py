"""
REFINET Cloud — OpenRouter Provider
Multi-model proxy with OpenAI-compatible API.
Routes to hundreds of models from various providers.
Supports free-tier models (e.g. google/gemini-2.0-flash-exp:free).
"""

from __future__ import annotations

from api.services.providers.base import ProviderType
from api.services.providers.openai_compat import OpenAICompatProvider


# Popular free models on OpenRouter
_DEFAULT_OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
]


class OpenRouterProvider(OpenAICompatProvider):
    provider_type = ProviderType.OPENROUTER
    display_name = "OpenRouter"

    def __init__(self, api_key: str, default_models: list[str] | None = None):
        super().__init__(
            base_url="https://openrouter.ai/api",
            api_key=api_key,
            default_models=default_models or _DEFAULT_OPENROUTER_MODELS,
            extra_headers={
                "HTTP-Referer": "https://refinet.io",
                "X-Title": "REFINET Cloud",
            },
        )

    def supports_model(self, model: str) -> bool:
        """OpenRouter is a catch-all — it supports virtually any model ID."""
        return True
