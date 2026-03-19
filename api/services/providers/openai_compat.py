"""
REFINET Cloud — OpenAI-Compatible Provider Base
Shared implementation for Ollama, LM Studio, OpenRouter, and any future
provider that exposes the standard /v1/chat/completions endpoint.
"""

from __future__ import annotations

import json
import httpx
import logging
import time
from typing import AsyncGenerator, Optional

from api.services.providers.base import (
    BaseProvider,
    ProviderType,
    InferenceResult,
    StreamResult,
    ProviderHealth,
)

logger = logging.getLogger("refinet.providers.openai_compat")


class OpenAICompatProvider(BaseProvider):
    """
    Base for any provider that exposes the OpenAI /v1/chat/completions API.
    Messages pass through directly (already OpenAI format).
    """

    provider_type: ProviderType = ProviderType.OLLAMA  # overridden by subclasses
    display_name: str = "OpenAI-Compatible"

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        default_models: Optional[list[str]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: float = 120.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._default_models = default_models or []
        self._extra_headers = extra_headers or {}
        self._timeout = timeout
        self._cached_models: Optional[list[str]] = None
        self._cache_time: float = 0

    def list_models(self) -> list[str]:
        if self._cached_models and (time.monotonic() - self._cache_time) < 60:
            return self._cached_models
        return self._default_models

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        headers.update(self._extra_headers)
        return headers

    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
    ) -> InferenceResult:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    headers=self._build_headers(),
                )
                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                usage = data.get("usage", {})

                return InferenceResult(
                    content=message.get("content", ""),
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    model=data.get("model", model),
                    provider=self.provider_type.value,
                    finish_reason=choice.get("finish_reason", "stop"),
                )
        except httpx.TimeoutException:
            return InferenceResult(
                content=f"{self.display_name} inference timed out.",
                model=model,
                provider=self.provider_type.value,
                finish_reason="error",
            )
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                error_detail = str(e)
            return InferenceResult(
                content=f"{self.display_name} error: {error_detail}",
                model=model,
                provider=self.provider_type.value,
                finish_reason="error",
            )
        except Exception as e:
            return InferenceResult(
                content=f"{self.display_name} error: {str(e)}",
                model=model,
                provider=self.provider_type.value,
                finish_reason="error",
            )

    async def stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
        result: Optional[StreamResult] = None,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        completion_token_count = 0

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    headers=self._build_headers(),
                ) as resp:
                    if resp.status_code != 200:
                        error_body = ""
                        async for chunk in resp.aiter_text():
                            error_body += chunk
                        yield f"{self.display_name} error: {error_body[:300]}"
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Extract usage from final chunk (OpenAI stream_options)
                        usage = data.get("usage")
                        if usage and result is not None:
                            result.prompt_tokens = usage.get("prompt_tokens", result.prompt_tokens)
                            result.completion_tokens = usage.get("completion_tokens", result.completion_tokens)
                            result.model = data.get("model", model)
                            result.provider = self.provider_type.value

                        choices = data.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            completion_token_count += 1
                            if result is not None:
                                result.content += content
                            yield content

            # Fallback token count
            if result is not None:
                if result.completion_tokens == 0:
                    result.completion_tokens = completion_token_count
                if not result.provider:
                    result.provider = self.provider_type.value

        except Exception as e:
            yield f"\n[{self.display_name} error: {str(e)}]"

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url}/v1/models",
                    headers=self._build_headers(),
                )
                latency = int((time.monotonic() - start) * 1000)

                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    # Update cache
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
