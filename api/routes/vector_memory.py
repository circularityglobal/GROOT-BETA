"""
REFINET Cloud — Vector Memory API Routes
Endpoints for the hybrid vector memory system.
Auth follows the same pattern as api/routes/agents.py.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database import public_db_dependency

logger = logging.getLogger("refinet.routes.vector_memory")
router = APIRouter(prefix="/memory/vector", tags=["vector-memory"])


# ── Auth helper (same pattern as agents.py) ───────────────────────

def _get_user_id(request: Request, db: Session) -> str:
    """Extract and validate user from Bearer token or API key."""
    from api.auth.jwt import decode_access_token
    from api.auth.api_keys import validate_api_key

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    if token.startswith("rf_"):
        api_key = validate_api_key(db, token)
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key.user_id
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


def _require_agent_access(db: Session, agent_id: str, user_id: str):
    """Verify the user owns the specified agent."""
    from api.models.public import AgentRegistration
    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── Request/Response models ───────────────────────────────────────

class StoreRequest(BaseModel):
    agent_id: str
    content: str
    memory_type: str = "user"
    metadata: Optional[dict] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchRequest(BaseModel):
    agent_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    filters: Optional[dict] = None


class ContextRequest(BaseModel):
    agent_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class InteractionRequest(BaseModel):
    agent_id: str
    input_text: str
    output_text: Optional[str] = None


class DecayRequest(BaseModel):
    agent_id: Optional[str] = None
    decay_rate: float = Field(default=0.01, ge=0.0, le=1.0)


class BatchStoreRequest(BaseModel):
    agent_id: str
    items: list[dict]


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/health")
def health_check(db: Session = Depends(public_db_dependency)):
    """Check sqlite-vec availability, search mode, and actionable diagnostics."""
    from api.services.vector_memory import get_vec_diagnostics
    diag = get_vec_diagnostics(db)
    return {
        "status": "ok",
        "search_mode": diag["search_mode"],
        "sqlite_vec_loaded": diag["sqlite_vec_loaded"],
        "sqlite_vec_reason": diag["sqlite_vec_reason"],
        "embedding_model": diag["embedding_model"],
    }


@router.post("/store")
def store(
    req: StoreRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Store a memory with automatic embedding and dedup."""
    user_id = _get_user_id(request, db)
    _require_agent_access(db, req.agent_id, user_id)

    from api.services.vector_memory import store_memory
    try:
        mem = store_memory(
            db=db,
            agent_id=req.agent_id,
            content=req.content,
            memory_type=req.memory_type,
            metadata=req.metadata,
            importance=req.importance,
        )
    except Exception as e:
        logger.error(f"store_memory failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store memory")
    return {
        "id": mem.id,
        "agent_id": mem.agent_id,
        "content": mem.content,
        "memory_type": mem.memory_type,
        "importance": mem.importance,
        "has_embedding": mem.embedding_json is not None,
    }


@router.post("/store/batch")
def store_batch(
    req: BatchStoreRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Batch store memories with single embedding call."""
    user_id = _get_user_id(request, db)
    _require_agent_access(db, req.agent_id, user_id)

    if not req.items:
        raise HTTPException(status_code=400, detail="items list is empty")

    from api.services.vector_memory import store_memory_batch
    try:
        memories = store_memory_batch(db=db, agent_id=req.agent_id, items=req.items)
    except Exception as e:
        logger.error(f"store_memory_batch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store batch")
    return {
        "stored": len(memories),
        "ids": [m.id for m in memories],
    }


@router.post("/search")
def search(
    req: SearchRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Semantic search with importance weighting and recency boost."""
    user_id = _get_user_id(request, db)
    _require_agent_access(db, req.agent_id, user_id)

    from api.services.vector_memory import retrieve_memory
    try:
        results = retrieve_memory(
            db=db,
            agent_id=req.agent_id,
            query=req.query,
            top_k=req.top_k,
            filters=req.filters,
        )
    except Exception as e:
        logger.error(f"retrieve_memory failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")
    return {"query": req.query, "count": len(results), "results": results}


@router.post("/context")
def context(
    req: ContextRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Build a prompt-ready context block from vector memory."""
    user_id = _get_user_id(request, db)
    _require_agent_access(db, req.agent_id, user_id)

    from api.services.vector_memory import build_context
    try:
        return build_context(db=db, agent_id=req.agent_id, query=req.query, top_k=req.top_k)
    except Exception as e:
        logger.error(f"build_context failed: {e}")
        raise HTTPException(status_code=500, detail="Context build failed")


@router.post("/interaction")
def record_interaction(
    req: InteractionRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Store an agent interaction (input/output pair)."""
    user_id = _get_user_id(request, db)
    _require_agent_access(db, req.agent_id, user_id)

    from api.services.vector_memory import store_interaction
    try:
        interaction = store_interaction(
            db=db,
            agent_id=req.agent_id,
            input_text=req.input_text,
            output_text=req.output_text,
        )
    except Exception as e:
        logger.error(f"store_interaction failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store interaction")
    return {"id": interaction.id, "agent_id": interaction.agent_id}


@router.post("/decay")
def trigger_decay(
    req: DecayRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Trigger importance decay on memories. Requires auth."""
    _get_user_id(request, db)  # Auth required, no agent ownership check needed

    from api.services.vector_memory import decay_memories
    try:
        count = decay_memories(db=db, agent_id=req.agent_id, decay_rate=req.decay_rate)
    except Exception as e:
        logger.error(f"decay_memories failed: {e}")
        raise HTTPException(status_code=500, detail="Decay failed")
    return {"decayed": count}


@router.get("/stats/{agent_id}")
def stats(
    agent_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get memory statistics for an agent."""
    user_id = _get_user_id(request, db)
    _require_agent_access(db, agent_id, user_id)

    from api.services.vector_memory import get_stats
    return get_stats(db, agent_id)


@router.delete("/{memory_id}")
def delete(
    memory_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Delete a specific memory."""
    user_id = _get_user_id(request, db)

    # Verify ownership via the memory's agent
    from api.models.vector_memory import VectorMemory
    mem = db.query(VectorMemory).filter(VectorMemory.id == memory_id).first()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    _require_agent_access(db, mem.agent_id, user_id)

    from api.services.vector_memory import delete_memory
    delete_memory(db, memory_id)
    return {"deleted": True, "memory_id": memory_id}
