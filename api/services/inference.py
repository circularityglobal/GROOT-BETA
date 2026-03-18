"""
REFINET Cloud — Inference Service
Calls the local bitnet.cpp llama-server over HTTP.
Supports both blocking and streaming (SSE) responses.
"""

import json
import httpx
from typing import AsyncGenerator

from api.config import get_settings


async def call_bitnet(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
    top_p: float = 1.0,
) -> dict:
    """
    Non-streaming inference call to bitnet.cpp llama-server.
    Returns {"content": str, "prompt_tokens": int, "completion_tokens": int}.
    """
    settings = get_settings()

    # Build prompt from messages (llama-server uses /completion endpoint)
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
                f"{settings.bitnet_host}/completion",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "content": data.get("content", ""),
                "prompt_tokens": data.get("tokens_evaluated", 0),
                "completion_tokens": data.get("tokens_predicted", 0),
            }
    except httpx.TimeoutException:
        return {"content": "Inference timed out. Please try again.", "prompt_tokens": 0, "completion_tokens": 0}
    except Exception as e:
        return {"content": f"Inference error: {str(e)}", "prompt_tokens": 0, "completion_tokens": 0}


async def stream_bitnet(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
    top_p: float = 1.0,
) -> AsyncGenerator[str, None]:
    """
    Streaming inference — yields tokens one at a time from bitnet.cpp.
    """
    settings = get_settings()
    prompt = _messages_to_prompt(messages)

    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stop": ["</s>", "<|end|>", "<|user|>"],
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{settings.bitnet_host}/completion",
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
                        if content:
                            yield content
                        if data.get("stop", False):
                            break
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"\n[Error: {str(e)}]"


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
