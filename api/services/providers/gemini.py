"""
REFINET Cloud — Google AI Studio / Gemini Provider
Custom API format (not OpenAI-compatible) — requires message conversion.
Supports streaming, safety settings, grounding with Google Search.
"""

from __future__ import annotations

import asyncio
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

logger = logging.getLogger("refinet.providers.gemini")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# ── Safety ────────────────────────────────────────────────────────

SAFETY_CATEGORIES = [
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
]

_FINISH_REASON_MAP = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "OTHER": "stop",
    "FINISH_REASON_UNSPECIFIED": "stop",
}


# ── Message Conversion ────────────────────────────────────────────

def _openai_messages_to_gemini(
    messages: list[dict],
) -> tuple[Optional[dict], list[dict]]:
    """
    Convert OpenAI-style messages to Gemini contents + systemInstruction.
    - system → systemInstruction (merged if multiple)
    - assistant → role: "model"
    - user → role: "user"
    - Consecutive same-role messages are merged (Gemini requires alternation).
    """
    system_instruction = None
    contents: list[dict] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            if system_instruction is None:
                system_instruction = {"parts": [{"text": content}]}
            else:
                system_instruction["parts"][0]["text"] += "\n\n" + content
            continue

        gemini_role = "model" if role == "assistant" else "user"

        # Merge consecutive same-role (Gemini requires alternation)
        if contents and contents[-1]["role"] == gemini_role:
            contents[-1]["parts"][0]["text"] += "\n\n" + content
        else:
            contents.append({
                "role": gemini_role,
                "parts": [{"text": content}],
            })

    # Gemini requires first message to be "user"
    if contents and contents[0]["role"] == "model":
        contents.insert(0, {"role": "user", "parts": [{"text": "."}]})

    # Gemini requires at least one content entry
    if not contents:
        contents.append({"role": "user", "parts": [{"text": "."}]})

    return system_instruction, contents


# ── Provider ──────────────────────────────────────────────────────

class GeminiProvider(BaseProvider):
    provider_type = ProviderType.GEMINI
    display_name = "Google Gemini"

    def __init__(
        self,
        api_key: str,
        default_models: Optional[list[str]] = None,
        safety_threshold: str = "BLOCK_MEDIUM_AND_ABOVE",
    ):
        self._api_key = api_key
        self._default_models = default_models or [
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]
        self._safety_threshold = safety_threshold

    def list_models(self) -> list[str]:
        return list(self._default_models)

    def _build_safety_settings(self) -> list[dict]:
        return [
            {"category": cat, "threshold": self._safety_threshold}
            for cat in SAFETY_CATEGORIES
        ]

    async def complete(
        self,
        messages: list[dict],
        model: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
        grounding: bool = False,
    ) -> InferenceResult:
        # Check rate limit with graceful backoff
        from api.services.providers.gemini_rate_limiter import GeminiRateLimiter
        allowed, retry_after = GeminiRateLimiter.get().acquire(model)
        if not allowed:
            if retry_after and retry_after <= 10.0:
                # RPM exhausted but daily budget remains — wait and retry once
                logger.info("Gemini RPM limit hit, backing off %.1fs", retry_after)
                await asyncio.sleep(retry_after)
                allowed, retry_after = GeminiRateLimiter.get().acquire(model)
            if not allowed:
                msg = "Gemini rate limit exceeded."
                if retry_after:
                    msg += f" Try again in {retry_after:.1f}s."
                else:
                    msg += " Daily quota exhausted."
                return InferenceResult(
                    content=msg, model=model,
                    provider=self.provider_type.value,
                    finish_reason="rate_limit",
                )

        system_instruction, contents = _openai_messages_to_gemini(messages)

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": top_p,
                "candidateCount": 1,
            },
            "safetySettings": self._build_safety_settings(),
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if grounding:
            payload["tools"] = [{"googleSearch": {}}]

        url = f"{GEMINI_API_BASE}/models/{model}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    url, json=payload,
                    params={"key": self._api_key},
                )

                if resp.status_code == 429:
                    return InferenceResult(
                        content="Gemini rate limit exceeded. Please try again.",
                        model=model, provider=self.provider_type.value,
                        finish_reason="rate_limit",
                    )

                if resp.status_code == 400:
                    try:
                        err_msg = resp.json().get("error", {}).get("message", "Bad request")
                    except Exception:
                        err_msg = resp.text[:300]
                    return InferenceResult(
                        content=f"Gemini error: {err_msg}",
                        model=model, provider=self.provider_type.value,
                        finish_reason="error",
                    )

                resp.raise_for_status()
                data = resp.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    block_reason = data.get("promptFeedback", {}).get("blockReason", "UNKNOWN")
                    return InferenceResult(
                        content=f"Response blocked by safety filter: {block_reason}",
                        model=model, provider=self.provider_type.value,
                        finish_reason="content_filter",
                    )

                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                usage = data.get("usageMetadata", {})

                return InferenceResult(
                    content=text,
                    prompt_tokens=usage.get("promptTokenCount", 0),
                    completion_tokens=usage.get("candidatesTokenCount", 0),
                    model=model,
                    provider=self.provider_type.value,
                    finish_reason=_FINISH_REASON_MAP.get(
                        candidate.get("finishReason", "STOP"), "stop",
                    ),
                )

        except httpx.TimeoutException:
            return InferenceResult(
                content="Gemini inference timed out. Please try again.",
                model=model, provider=self.provider_type.value,
                finish_reason="error",
            )
        except Exception as e:
            logger.error("Gemini inference error: %s", e)
            return InferenceResult(
                content=f"Gemini error: {str(e)}",
                model=model, provider=self.provider_type.value,
                finish_reason="error",
            )

    async def stream(
        self,
        messages: list[dict],
        model: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 1.0,
        grounding: bool = False,
        result: Optional[StreamResult] = None,
    ) -> AsyncGenerator[str, None]:
        # Check rate limit with graceful backoff
        from api.services.providers.gemini_rate_limiter import GeminiRateLimiter
        allowed, retry_after = GeminiRateLimiter.get().acquire(model)
        if not allowed:
            if retry_after and retry_after <= 10.0:
                logger.info("Gemini RPM limit hit (stream), backing off %.1fs", retry_after)
                await asyncio.sleep(retry_after)
                allowed, retry_after = GeminiRateLimiter.get().acquire(model)
            if not allowed:
                msg = "Gemini rate limit exceeded."
                if retry_after:
                    msg += f" Try again in {retry_after:.1f}s."
                yield msg
                return

        system_instruction, contents = _openai_messages_to_gemini(messages)

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": top_p,
                "candidateCount": 1,
            },
            "safetySettings": self._build_safety_settings(),
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if grounding:
            payload["tools"] = [{"googleSearch": {}}]

        url = f"{GEMINI_API_BASE}/models/{model}:streamGenerateContent"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", url,
                    json=payload,
                    params={"key": self._api_key, "alt": "sse"},
                ) as resp:
                    if resp.status_code == 429:
                        yield "Gemini rate limit exceeded. Please try again."
                        return

                    if resp.status_code != 200:
                        error_body = ""
                        async for chunk in resp.aiter_text():
                            error_body += chunk
                        try:
                            msg = json.loads(error_body).get("error", {}).get("message", error_body[:200])
                        except (json.JSONDecodeError, AttributeError):
                            msg = error_body[:200]
                        yield f"Gemini error: {msg}"
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

                        candidates = data.get("candidates", [])
                        if not candidates:
                            continue

                        candidate = candidates[0]
                        parts = candidate.get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)

                        if text:
                            if result is not None:
                                result.content += text
                            yield text

                        # Token counts from usageMetadata (present in final chunk)
                        usage = data.get("usageMetadata", {})
                        if usage and result is not None:
                            result.prompt_tokens = usage.get(
                                "promptTokenCount", result.prompt_tokens,
                            )
                            result.completion_tokens = usage.get(
                                "candidatesTokenCount", result.completion_tokens,
                            )
                            result.model = model
                            result.provider = self.provider_type.value

        except Exception as e:
            logger.error("Gemini streaming error: %s", e)
            yield f"\n[Gemini error: {str(e)}]"

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{GEMINI_API_BASE}/models",
                    params={"key": self._api_key},
                )
                latency = int((time.monotonic() - start) * 1000)

                if resp.status_code == 200:
                    data = resp.json()
                    models = [
                        m.get("name", "").replace("models/", "")
                        for m in data.get("models", [])
                        if "generateContent" in str(m.get("supportedGenerationMethods", []))
                    ]
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
