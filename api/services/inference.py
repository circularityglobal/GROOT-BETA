"""
REFINET Cloud — Inference Service (Backward-Compatibility Shim)
Delegates to ModelGateway → BitNetProvider.
Existing code that imports call_bitnet/stream_bitnet continues to work.
"""

from __future__ import annotations

from typing import AsyncGenerator, Optional

# Re-export StreamResult from the providers layer for backward compatibility
from api.services.providers.base import StreamResult


async def call_bitnet(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
    top_p: float = 1.0,
) -> dict:
    """
    Non-streaming inference — delegates to ModelGateway.
    Returns {"content": str, "prompt_tokens": int, "completion_tokens": int}.
    """
    from api.services.gateway import ModelGateway
    result = await ModelGateway.get().complete(
        messages=messages,
        model="bitnet-b1.58-2b",
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )
    return {
        "content": result.content,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }


async def stream_bitnet(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
    top_p: float = 1.0,
    result: Optional[StreamResult] = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming inference — delegates to ModelGateway.
    Yields tokens one at a time. Populates StreamResult if provided.
    """
    from api.services.gateway import ModelGateway
    async for chunk in ModelGateway.get().stream(
        messages=messages,
        model="bitnet-b1.58-2b",
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        result=result,
    ):
        yield chunk


def estimate_prompt_tokens(messages: list[dict]) -> int:
    """
    Estimate prompt token count using the 4-chars-per-token heuristic.
    Fallback when the server doesn't report tokens_evaluated.
    """
    from api.services.providers.bitnet import _messages_to_prompt
    prompt = _messages_to_prompt(messages)
    return max(1, len(prompt) // 4)
