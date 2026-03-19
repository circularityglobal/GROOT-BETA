"""
REFINET Cloud — Inference Routes
OpenAI-compatible API for multi-provider inference.
Supports BitNet, Gemini, Ollama, LM Studio, OpenRouter.
Supports both streaming (SSE) and non-streaming responses.
Supports anonymous (unauthenticated) access with IP-based rate limiting.
"""

import json
import time
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_INFERENCE_READ
from api.auth.api_keys import validate_api_key
from api.models.public import User, UsageRecord
from api.schemas.inference import (
    ChatCompletionRequest, ChatCompletionResponse,
    ChatCompletionChoice, ChatMessage, UsageInfo,
    ModelListResponse, ModelInfo, SourceReference,
)
from api.services.gateway import ModelGateway
from api.services.providers import ProviderRegistry, StreamResult
from api.services.inference import estimate_prompt_tokens
from api.services.rag import build_groot_system_prompt
from api.config import get_settings

router = APIRouter(tags=["inference"])


# ── Anonymous rate limiting (in-memory, per-IP) ──────────────────

_anon_lock = threading.Lock()
_anon_counters: dict[str, dict[str, int]] = {}  # {ip: {"date": "YYYY-MM-DD", "count": N}}


def _check_anonymous_rate(ip: str) -> bool:
    """
    Check and increment anonymous IP counter.
    Returns True if within limits, False if quota exhausted.
    """
    settings = get_settings()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with _anon_lock:
        entry = _anon_counters.get(ip)
        if entry is None or entry["date"] != today:
            _anon_counters[ip] = {"date": today, "count": 1}
            return True
        if entry["count"] >= settings.anonymous_daily_requests:
            return False
        entry["count"] += 1
        return True


# ── RAG context injection ──────────────────────────────────────────

def _inject_rag_context(
    messages: list[dict],
    db: Session,
    notebook_doc_ids: Optional[list[str]] = None,
    user_id: Optional[str] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Inject Groot's system prompt with RAG context before sending to any provider.
    Returns (enriched_messages, sources_list).
    """
    user_query = ""
    for msg in reversed(messages):
        if msg["role"] == "user":
            user_query = msg["content"]
            break

    if not user_query:
        return messages, []

    # For multi-turn: blend last 2 user messages for richer RAG query
    if len([m for m in messages if m["role"] == "user"]) > 1:
        user_msgs = [m["content"] for m in messages if m["role"] == "user"]
        recent = user_msgs[-2:]
        blended = recent[-1]
        if len(recent) > 1:
            prev_snippet = recent[-2][:200]
            blended = f"{blended} {prev_snippet}"
        user_query = blended

    system_prompt, sources = build_groot_system_prompt(
        db, user_query, doc_ids=notebook_doc_ids, user_id=user_id,
    )

    if messages and messages[0]["role"] == "system":
        messages[0]["content"] = system_prompt + "\n\n" + messages[0]["content"]
    else:
        messages = [{"role": "system", "content": system_prompt}] + messages

    return messages, sources


# ── Auth helper — supports JWT, API key, and anonymous ────────────

def _authenticate_inference(
    request: Request, db: Session
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Authenticate via JWT, API key, or allow anonymous access.
    Returns (user_id, api_key_id, is_anonymous).
    """
    auth_header = request.headers.get("Authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

        if token.startswith("rf_"):
            api_key = validate_api_key(db, token)
            if not api_key:
                raise HTTPException(status_code=401, detail="Invalid or rate-limited API key")
            return api_key.user_id, api_key.id, False

        try:
            payload = decode_access_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        if not verify_scope(payload, SCOPE_INFERENCE_READ):
            raise HTTPException(status_code=403, detail="Token lacks inference:read scope")

        return payload["sub"], None, False

    client_ip = request.client.host if request.client else "unknown"
    if not _check_anonymous_rate(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Anonymous daily limit reached. Create a free account for higher limits.",
        )
    return None, None, True


# ── BYOK: Resolve user-owned provider keys ────────────────────────

def _resolve_user_provider(db: Session, user_id: Optional[str], model: str):
    """
    Check if the user has their own API key for the provider that handles this model.
    Returns an ephemeral BaseProvider instance or None.

    SECURITY: Only returns a provider if the user has completed all 3 auth layers.
    This prevents users with SIWE-only auth from using BYOK keys.
    """
    if not user_id:
        return None

    # Map model prefix to provider type
    provider_type = None
    if model.startswith("gpt-") or model.startswith("dall-e") or model.startswith("whisper") or model.startswith("tts-"):
        provider_type = "openai"
    elif model.startswith("claude-"):
        provider_type = "anthropic"
    elif model.startswith("gemini-"):
        provider_type = "gemini"
    elif "/" in model:  # e.g., "meta-llama/llama-3.1-8b" → openrouter
        provider_type = "openrouter"
    elif model.startswith("mistral-") or model.startswith("codestral"):
        provider_type = "mistral"
    elif model.startswith("sonar"):
        provider_type = "perplexity"
    elif model.startswith("llama-") or model.startswith("mixtral"):
        provider_type = "groq"

    if not provider_type:
        return None

    try:
        # SECURITY: Verify user has completed all 3 auth layers before decrypting keys
        from api.models.public import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        if not (user.auth_layer_1_complete and user.auth_layer_2_complete and user.auth_layer_3_complete):
            return None

        from api.services.provider_keys import get_decrypted_key
        result = get_decrypted_key(db, user_id, provider_type)
        if result:
            api_key, base_url = result
            return ModelGateway.create_user_provider(provider_type, api_key, base_url)
    except Exception:
        pass

    return None


# ── Models endpoint (no auth required) ─────────────────────────────

@router.get("/v1/models", response_model=ModelListResponse)
def list_models():
    """Return all models from all registered providers."""
    registry = ProviderRegistry.get()
    entries = registry.list_all_models()

    now = int(time.time())
    models = [
        ModelInfo(
            id=entry.model_id,
            created=now,
            owned_by=entry.owned_by,
            provider=entry.provider_type.value,
            context_window=entry.context_window,
            is_free=entry.is_free,
        )
        for entry in entries
    ]

    # Always include at least the default model
    if not models:
        models = [ModelInfo(id="bitnet-b1.58-2b", created=now)]

    return ModelListResponse(data=models)


# ── Chat completions ───────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, api_key_id, is_anonymous = _authenticate_inference(request, db)
    start_time = time.time()

    # Cap max_tokens for anonymous users to conserve compute
    if is_anonymous:
        settings = get_settings()
        if req.max_tokens is None or req.max_tokens > settings.anonymous_max_tokens:
            req.max_tokens = settings.anonymous_max_tokens

    # Inject RAG/CAG context from knowledge base (scoped to user's visible docs)
    enriched_messages, rag_sources = _inject_rag_context(
        [{"role": m.role, "content": m.content} for m in req.messages],
        db,
        notebook_doc_ids=req.notebook_doc_ids,
        user_id=user_id,
    )

    # ── BYOK: Check if user has their own key for this model's provider ──
    user_provider = _resolve_user_provider(db, user_id, req.model)

    if req.stream:
        return StreamingResponse(
            _stream_response(req, enriched_messages, user_id, api_key_id, db, start_time, rag_sources, user_provider),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming response — use user provider if available, else gateway
    if user_provider:
        kwargs: dict = dict(
            messages=enriched_messages, model=req.model,
            temperature=req.temperature, max_tokens=req.max_tokens, top_p=req.top_p,
        )
        if req.grounding:
            kwargs["grounding"] = True
        result = await user_provider.complete(**kwargs)
    else:
        gateway = ModelGateway.get()
        result = await gateway.complete(
            messages=enriched_messages,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            top_p=req.top_p,
            grounding=req.grounding,
        )

    latency_ms = int((time.time() - start_time) * 1000)

    # Record usage (skip for anonymous — no user_id for FK)
    if user_id:
        usage_record = UsageRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            api_key_id=api_key_id,
            model=req.model,
            provider=result.provider,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            latency_ms=latency_ms,
            endpoint="/v1/chat/completions",
        )
        db.add(usage_record)
        db.flush()

    # Build source references
    source_refs = [
        SourceReference(
            document_id=s["document_id"],
            document_title=s["document_title"],
            category=s["category"],
            doc_type=s.get("doc_type"),
            tags=s.get("tags", []),
            score=round(s.get("score", 0.0), 4),
            preview=s.get("preview", ""),
        )
        for s in rag_sources
    ] if rag_sources else None

    response = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=req.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(
                    role="assistant",
                    content=result.content,
                ),
                finish_reason=result.finish_reason,
            )
        ],
        usage=UsageInfo(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
        ),
        sources=source_refs,
        provider=result.provider,
    )
    return response


async def _stream_response(req, enriched_messages, user_id, api_key_id, db, start_time, rag_sources=None, user_provider=None):
    """Generate SSE stream from any provider via ModelGateway or user's own provider."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    stream_result = StreamResult()

    if user_provider:
        kwargs: dict = dict(
            messages=enriched_messages, model=req.model,
            temperature=req.temperature, max_tokens=req.max_tokens,
            top_p=req.top_p, result=stream_result,
        )
        if req.grounding:
            kwargs["grounding"] = True
        stream_gen = user_provider.stream(**kwargs)
    else:
        gateway = ModelGateway.get()
        stream_gen = gateway.stream(
            messages=enriched_messages,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            top_p=req.top_p,
            grounding=req.grounding,
            result=stream_result,
        )

    async for chunk in stream_gen:
        data = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": req.model,
            "choices": [{
                "index": 0,
                "delta": {"content": chunk},
                "finish_reason": None,
            }],
        }
        yield f"data: {json.dumps(data)}\n\n"

    # If server didn't report prompt_tokens, estimate from the enriched messages
    if stream_result.prompt_tokens == 0:
        stream_result.prompt_tokens = estimate_prompt_tokens(enriched_messages)

    # Final chunk with finish_reason and usage (OpenAI-compatible)
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": stream_result.prompt_tokens,
            "completion_tokens": stream_result.completion_tokens,
            "total_tokens": stream_result.prompt_tokens + stream_result.completion_tokens,
        },
    }
    yield f"data: {json.dumps(final)}\n\n"

    # Emit sources metadata before [DONE] so frontend can attach to last message
    if rag_sources:
        sources_data = {
            "sources": [
                {
                    "document_id": s["document_id"],
                    "document_title": s["document_title"],
                    "category": s["category"],
                    "doc_type": s.get("doc_type"),
                    "tags": s.get("tags", []),
                    "score": round(s.get("score", 0.0), 4),
                    "preview": s.get("preview", ""),
                }
                for s in rag_sources
            ]
        }
        yield f"data: {json.dumps(sources_data)}\n\n"

    yield "data: [DONE]\n\n"

    # Record accurate usage after stream completes (skip for anonymous)
    if user_id:
        latency_ms = int((time.time() - start_time) * 1000)
        usage_record = UsageRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            api_key_id=api_key_id,
            model=req.model,
            provider=stream_result.provider or "unknown",
            prompt_tokens=stream_result.prompt_tokens,
            completion_tokens=stream_result.completion_tokens,
            latency_ms=latency_ms,
            endpoint="/v1/chat/completions",
        )
        db.add(usage_record)
        db.commit()
