"""
REFINET Cloud — BitNet Provider
Calls the local bitnet.cpp llama-server over HTTP.
Extracted from api/services/inference.py into the BaseProvider interface.
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

logger = logging.getLogger("refinet.providers.bitnet")


class BitNetProvider(BaseProvider):
    provider_type = ProviderType.BITNET
    display_name = "BitNet b1.58-2B (Sovereign)"

    def __init__(self, host: str = "http://127.0.0.1:8080"):
        self._host = host.rstrip("/")

    def list_models(self) -> list[str]:
        return ["bitnet-b1.58-2b"]

    async def complete(
        self,
        messages: list[dict],
        model: str = "bitnet-b1.58-2b",
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
    ) -> InferenceResult:
        prompt = _messages_to_prompt(messages)
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": ["</s>", "<|end|>", "<|user|>"],
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._host}/completion",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                return InferenceResult(
                    content=data.get("content", ""),
                    prompt_tokens=data.get("tokens_evaluated", 0),
                    completion_tokens=data.get("tokens_predicted", 0),
                    model=model,
                    provider=self.provider_type.value,
                )
        except httpx.TimeoutException:
            return InferenceResult(
                content="Inference timed out. Please try again.",
                model=model,
                provider=self.provider_type.value,
                finish_reason="error",
            )
        except Exception as e:
            return InferenceResult(
                content=f"Inference error: {str(e)}",
                model=model,
                provider=self.provider_type.value,
                finish_reason="error",
            )

    async def stream(
        self,
        messages: list[dict],
        model: str = "bitnet-b1.58-2b",
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
        result: Optional[StreamResult] = None,
    ) -> AsyncGenerator[str, None]:
        prompt = _messages_to_prompt(messages)
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": ["</s>", "<|end|>", "<|user|>"],
            "stream": True,
        }

        completion_token_count = 0

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self._host}/completion",
                    json=payload,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            content = data.get("content", "")

                            if data.get("stop", False):
                                timings = data.get("timings", {})
                                if result is not None:
                                    result.prompt_tokens = (
                                        data.get("tokens_evaluated", 0)
                                        or timings.get("prompt_n", 0)
                                    )
                                    result.completion_tokens = (
                                        data.get("tokens_predicted", 0)
                                        or timings.get("predicted_n", 0)
                                        or completion_token_count
                                    )
                                    result.model = model
                                    result.provider = self.provider_type.value
                                if content:
                                    completion_token_count += 1
                                    yield content
                                break

                            if content:
                                completion_token_count += 1
                                if result is not None:
                                    result.content += content
                                yield content
                        except json.JSONDecodeError:
                            continue

            if result is not None and result.completion_tokens == 0:
                result.completion_tokens = completion_token_count

        except Exception as e:
            yield f"\n[Error: {str(e)}]"

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._host}/health")
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    return ProviderHealth(
                        is_healthy=True,
                        latency_ms=latency,
                        available_models=self.list_models(),
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


def _messages_to_prompt(messages: list[dict]) -> str:
    """
    Convert OpenAI-style messages to a prompt format for BitNet/llama-server.
    Uses a simple chat template compatible with most small models.
    """
    parts = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            parts.append(f"<|system|>\n{content}</s>")
        elif role == "user":
            parts.append(f"<|user|>\n{content}</s>")
        elif role == "assistant":
            parts.append(f"<|assistant|>\n{content}</s>")
    parts.append("<|assistant|>\n")
    return "\n".join(parts)
