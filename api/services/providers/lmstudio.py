"""
REFINET Cloud — LM Studio Provider
Local model server with OpenAI-compatible API.
Default port: 1234.
"""

from __future__ import annotations

from api.services.providers.base import ProviderType
from api.services.providers.openai_compat import OpenAICompatProvider


class LMStudioProvider(OpenAICompatProvider):
    provider_type = ProviderType.LMSTUDIO
    display_name = "LM Studio (Local)"

    def __init__(self, host: str = "http://127.0.0.1:1234"):
        super().__init__(
            base_url=host,
            api_key=None,
            default_models=[],
        )
