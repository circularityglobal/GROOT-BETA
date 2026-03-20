"""
REFINET Cloud — Vector Memory Service
Hybrid memory: structured SQLite tables + sqlite-vec KNN search.
Provides store, retrieve, dedup, decay, and context building for agents.
Falls back to brute-force cosine similarity if sqlite-vec is unavailable.
"""

import json
import logging
import math
import struct
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func, update

from api.models.vector_memory import (
    VectorMemory,
    VectorInteraction,
    VectorMemoryLink,
)

logger = logging.getLogger("refinet.vector_memory")

# ── Constants ──────────────────────────────────────────────────────

EMBEDDING_DIM = 384


# ── sqlite-vec availability ────────────────────────────────────────

def _check_vec_available(db: Session) -> bool:
    """
    Check if sqlite-vec extension is loaded on this connection.

    Uses the DB layer's cached load status first (no SQL probe needed in
    most cases).  Result is NOT cached in a module-level global so that
    every worker/process gets an accurate answer from its own connections.
    """
    # Fast path: the DB layer already recorded the outcome at connect time
    from api.database import get_vec_load_status
    status = get_vec_load_status()
    if status["loaded"]:
        return True
    if status["reason"] is not None:
        return False

    # Probe: status was never set (shouldn't normally happen)
    try:
        result = db.execute(text("SELECT vec_version()"))
        result.fetchone()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def is_vec_available(db: Session) -> bool:
    """Public check for sqlite-vec availability."""
    return _check_vec_available(db)


def get_vec_diagnostics(db: Session) -> dict:
    """Return detailed diagnostics about vector search capability."""
    from api.database import get_vec_load_status

    vec_status = get_vec_load_status()
    emb_available = False
    try:
        from api.services.embedding import is_available
        emb_available = is_available()
    except Exception:
        pass

    if vec_status["loaded"]:
        search_mode = "sqlite-vec KNN (native)"
    elif emb_available:
        search_mode = "brute-force cosine similarity (Python)"
    else:
        search_mode = "importance + recency ranking (no embeddings)"

    return {
        "sqlite_vec_loaded": vec_status["loaded"],
        "sqlite_vec_reason": vec_status["reason"],
        "embedding_model": emb_available,
        "search_mode": search_mode,
    }


# ── Vector serialization ──────────────────────────────────────────

def _vec_serialize(vec: list[float]) -> bytes:
    """Serialize float list to binary format for sqlite-vec.
    Validates dimension to prevent silent index corruption."""
    if len(vec) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(vec)}"
        )
    return struct.pack(f"{EMBEDDING_DIM}f", *vec)


def _vec_deserialize(data: bytes) -> list[float]:
    """Deserialize binary format back to float list."""
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


# ── Virtual table management ──────────────────────────────────────

_VEC_TABLE_SQL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories "
    f"USING vec0(memory_id TEXT PRIMARY KEY, embedding float[{EMBEDDING_DIM}])"
)


def ensure_vec_index(db: Session) -> bool:
    """Create the vec0 virtual table if sqlite-vec is available. Idempotent.

    Uses flush (not commit) — caller's context manager owns the transaction.
    """
    if not _check_vec_available(db):
        return False
    try:
        db.execute(text(_VEC_TABLE_SQL))
        db.flush()
        logger.info("vec_memories virtual table ready")
        return True
    except Exception as e:
        logger.error(f"Failed to create vec_memories: {e}")
        return False


def _sync_to_vec_index(db: Session, memory_id: str, embedding: list[float]) -> bool:
    """Insert or replace an embedding in the vec0 virtual table."""
    if not _check_vec_available(db):
        return False
    try:
        db.execute(
            text("INSERT OR REPLACE INTO vec_memories(memory_id, embedding) VALUES (:mid, :emb)"),
            {"mid": memory_id, "emb": _vec_serialize(embedding)},
        )
        return True
    except Exception as e:
        logger.warning(f"vec index sync failed for {memory_id}: {e}")
        return False


def _remove_from_vec_index(db: Session, memory_id: str) -> bool:
    """Remove an embedding from the vec0 virtual table."""
    if not _check_vec_available(db):
        return False
    try:
        db.execute(
            text("DELETE FROM vec_memories WHERE memory_id = :mid"),
            {"mid": memory_id},
        )
        return True
    except Exception as e:
        logger.warning(f"vec index removal failed for {memory_id}: {e}")
        return False


# ── Embedding helpers ─────────────────────────────────────────────

def _get_embedding(content: str) -> Optional[list[float]]:
    """Generate embedding using the existing embedding service.
    The service returns normalized vectors (normalize_embeddings=True)."""
    try:
        from api.services.embedding import embed_text
        return embed_text(content)
    except Exception:
        return None


def _get_embedding_batch(texts: list[str]) -> Optional[list[list[float]]]:
    """Batch embed using the existing embedding service."""
    try:
        from api.services.embedding import embed_batch
        return embed_batch(texts)
    except Exception:
        return None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity — reuses embedding service or inline fallback."""
    try:
        from api.services.embedding import cosine_similarity
        return cosine_similarity(a, b)
    except Exception:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0


def _serialize_json(vec: list[float]) -> str:
    """JSON-serialize embedding for caching in TEXT column."""
    return json.dumps([round(v, 6) for v in vec])


def _deserialize_json(data: str) -> Optional[list[float]]:
    """Deserialize embedding from JSON TEXT column."""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


# ── Scoring ───────────────────────────────────────────────────────
# Distance-to-similarity note:
# The embedding service (all-MiniLM-L6-v2) produces L2-normalized vectors
# (normalize_embeddings=True in embed_text).  sqlite-vec uses L2 distance.
# For unit vectors: cosine_sim = 1 − (d² / 2).

def _l2_distance_to_cosine_sim(distance: float) -> float:
    """Convert sqlite-vec L2 distance to cosine similarity.
    Valid only for L2-normalized (unit) vectors."""
    return max(0.0, 1.0 - (distance * distance / 2.0))


def _recency_boost(created_at: datetime, window_days: int = 90) -> float:
    """Linear recency boost: 1.0 for now, 0.0 at window_days ago."""
    if created_at is None:
        return 0.0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - created_at).total_seconds() / 86400.0
    return max(0.0, 1.0 - age / window_days)


def _composite_score(
    similarity: float,
    importance: float,
    created_at: datetime,
    sim_weight: float = 0.7,
    imp_weight: float = 0.2,
    rec_weight: float = 0.1,
    recency_window: int = 90,
) -> float:
    """Weighted composite: similarity + importance + recency."""
    recency = _recency_boost(created_at, recency_window)
    return similarity * sim_weight + importance * imp_weight + recency * rec_weight


# ── Deduplication ─────────────────────────────────────────────────

def _find_duplicate(
    db: Session,
    agent_id: str,
    embedding: list[float],
    threshold: float = 0.95,
) -> Optional[VectorMemory]:
    """Find an existing memory above the similarity threshold.
    Scoped to agent_id — KNN candidates are pre-filtered via subquery."""
    if _check_vec_available(db) and embedding:
        try:
            # Pre-filter: only search within this agent's memories
            agent_ids = db.query(VectorMemory.id).filter(
                VectorMemory.agent_id == agent_id,
                VectorMemory.embedding_json.isnot(None),
            ).all()
            if not agent_ids:
                return None

            id_set = {r[0] for r in agent_ids}

            rows = db.execute(
                text(
                    "SELECT vm.memory_id, vm.distance "
                    "FROM vec_memories vm "
                    "WHERE vm.embedding MATCH :qvec AND k = :lim"
                ),
                {"qvec": _vec_serialize(embedding), "lim": min(len(id_set), 10)},
            ).fetchall()

            for mid, distance in rows:
                if mid not in id_set:
                    continue
                sim = _l2_distance_to_cosine_sim(distance)
                if sim >= threshold:
                    mem = db.query(VectorMemory).filter(
                        VectorMemory.id == mid,
                    ).first()
                    if mem:
                        return mem
        except Exception as e:
            logger.debug(f"Vec dedup search failed, trying brute-force: {e}")

    # Brute-force fallback (always agent-scoped)
    if embedding:
        candidates = db.query(VectorMemory).filter(
            VectorMemory.agent_id == agent_id,
            VectorMemory.embedding_json.isnot(None),
        ).order_by(desc(VectorMemory.created_at)).limit(100).all()

        for c in candidates:
            c_vec = _deserialize_json(c.embedding_json)
            if c_vec and _cosine_sim(embedding, c_vec) >= threshold:
                return c

    return None


# ── Store ─────────────────────────────────────────────────────────

def store_memory(
    db: Session,
    agent_id: str,
    content: str,
    memory_type: str = "user",
    metadata: Optional[dict] = None,
    importance: float = 0.5,
    dedup_threshold: float = 0.95,
) -> VectorMemory:
    """Store a memory with embedding. Deduplicates if a near-duplicate exists.

    Vec index sync is best-effort — if it fails, the memory is still stored
    with its embedding_json cache and will be found via brute-force fallback.
    """
    importance = max(0.0, min(1.0, importance))

    # 1. Generate embedding
    embedding = _get_embedding(content)

    # 2. Dedup check
    if embedding and dedup_threshold < 1.0:
        existing = _find_duplicate(db, agent_id, embedding, dedup_threshold)
        if existing:
            existing.importance = (existing.importance + importance) / 2.0
            existing.access_count += 1
            existing.updated_at = datetime.now(timezone.utc)
            db.flush()
            logger.debug(f"Deduplicated memory {existing.id}")
            return existing

    # 3. Create new memory
    mem = VectorMemory(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        content=content,
        memory_type=memory_type,
        metadata_json=json.dumps(metadata) if metadata else None,
        importance=importance,
        embedding_json=_serialize_json(embedding) if embedding else None,
        access_count=0,
    )
    db.add(mem)
    db.flush()

    # 4. Sync to vec index (best-effort — logged on failure, does not raise)
    if embedding:
        _sync_to_vec_index(db, mem.id, embedding)

    logger.debug(f"Stored memory {mem.id} type={memory_type}")
    return mem


def store_memory_batch(
    db: Session,
    agent_id: str,
    items: list[dict],
) -> list[VectorMemory]:
    """Batch store memories. Each item: {content, memory_type, metadata, importance}.

    Generates embeddings in one batch call for efficiency.
    Does not deduplicate across items within the batch.
    """
    texts = [item["content"] for item in items]
    embeddings = _get_embedding_batch(texts)

    results = []
    for i, item in enumerate(items):
        emb = embeddings[i] if embeddings else None
        mem = VectorMemory(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            content=item["content"],
            memory_type=item.get("memory_type", "user"),
            metadata_json=json.dumps(item.get("metadata")) if item.get("metadata") else None,
            importance=max(0.0, min(1.0, item.get("importance", 0.5))),
            embedding_json=_serialize_json(emb) if emb else None,
            access_count=0,
        )
        db.add(mem)
        db.flush()
        if emb:
            _sync_to_vec_index(db, mem.id, emb)
        results.append(mem)

    return results


# ── Retrieve ──────────────────────────────────────────────────────

def retrieve_memory(
    db: Session,
    agent_id: str,
    query: str,
    top_k: int = 5,
    filters: Optional[dict] = None,
) -> list[dict]:
    """Retrieve memories by semantic similarity with importance weighting and recency boost.

    filters: {memory_type: str, min_importance: float, after: datetime, before: datetime}
    Returns list of dicts sorted by composite score.
    """
    embedding = _get_embedding(query)
    filters = filters or {}

    candidates = _retrieve_vec(db, agent_id, embedding, top_k * 3, filters) \
        if embedding and _check_vec_available(db) \
        else _retrieve_brute(db, agent_id, embedding, top_k * 3, filters)

    # Score and sort
    scored = []
    for mem, similarity in candidates:
        score = _composite_score(similarity, mem.importance, mem.created_at)
        scored.append((score, similarity, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:top_k]

    # Update access counts
    now = datetime.now(timezone.utc)
    for _, _, mem in results:
        mem.access_count += 1
        mem.last_accessed_at = now
    db.flush()

    return [
        {
            "id": mem.id,
            "content": mem.content,
            "memory_type": mem.memory_type,
            "metadata": json.loads(mem.metadata_json) if mem.metadata_json else None,
            "importance": round(mem.importance, 3),
            "similarity": round(sim, 4),
            "score": round(score, 4),
            "access_count": mem.access_count,
            "created_at": mem.created_at.isoformat() if mem.created_at else None,
        }
        for score, sim, mem in results
    ]


def _retrieve_vec(
    db: Session,
    agent_id: str,
    embedding: list[float],
    limit: int,
    filters: dict,
) -> list[tuple]:
    """KNN retrieval via sqlite-vec, scoped to agent_id.

    Strategy: fetch a larger KNN set globally, then post-filter to this agent.
    We over-fetch (limit * 3) to compensate for cross-agent entries being
    filtered out. This is the standard approach for vec0 which does not
    support WHERE clauses on non-virtual columns.
    """
    fetch_limit = limit * 3  # Over-fetch to compensate for agent filtering
    try:
        rows = db.execute(
            text(
                "SELECT vm.memory_id, vm.distance "
                "FROM vec_memories vm "
                "WHERE vm.embedding MATCH :qvec AND k = :lim"
            ),
            {"qvec": _vec_serialize(embedding), "lim": fetch_limit},
        ).fetchall()
    except Exception as e:
        logger.error(f"Vec search failed: {e}")
        return _retrieve_brute(db, agent_id, embedding, limit, filters)

    if not rows:
        return []

    ids = [r[0] for r in rows]
    dist_map = {r[0]: r[1] for r in rows}

    # Post-filter by agent_id and user-supplied filters
    q = db.query(VectorMemory).filter(
        VectorMemory.id.in_(ids),
        VectorMemory.agent_id == agent_id,
    )
    q = _apply_filters(q, filters)
    memories = q.all()

    results = []
    for mem in memories:
        d = dist_map.get(mem.id, 1.0)
        sim = _l2_distance_to_cosine_sim(d)
        results.append((mem, sim))

    return results


def _retrieve_brute(
    db: Session,
    agent_id: str,
    embedding: Optional[list[float]],
    limit: int,
    filters: dict,
) -> list[tuple]:
    """Brute-force cosine similarity fallback."""
    q = db.query(VectorMemory).filter(VectorMemory.agent_id == agent_id)
    q = _apply_filters(q, filters)

    if embedding:
        q = q.filter(VectorMemory.embedding_json.isnot(None))

    candidates = q.order_by(desc(VectorMemory.created_at)).limit(limit * 2).all()

    if not embedding:
        # No embedding available — rank by importance + recency only
        return [(m, 0.5) for m in candidates[:limit]]

    results = []
    for mem in candidates:
        vec = _deserialize_json(mem.embedding_json)
        if vec:
            sim = _cosine_sim(embedding, vec)
            results.append((mem, sim))
        else:
            results.append((mem, 0.0))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def _apply_filters(q, filters: dict):
    """Apply optional filters to a SQLAlchemy query."""
    if filters.get("memory_type"):
        q = q.filter(VectorMemory.memory_type == filters["memory_type"])
    if filters.get("min_importance") is not None:
        q = q.filter(VectorMemory.importance >= filters["min_importance"])
    if filters.get("after"):
        q = q.filter(VectorMemory.created_at >= filters["after"])
    if filters.get("before"):
        q = q.filter(VectorMemory.created_at <= filters["before"])
    return q


# ── Context Building ─────────────────────────────────────────────

def build_context(
    db: Session,
    agent_id: str,
    query: str,
    top_k: int = 5,
) -> dict:
    """Build a prompt-friendly context block from vector memory.

    Returns:
        {"relevant_memories": [...], "context_block": "formatted string"}
    """
    memories = retrieve_memory(db, agent_id, query, top_k=top_k)

    if not memories:
        return {"relevant_memories": [], "context_block": ""}

    lines = []
    for m in memories:
        lines.append(
            f"  - [{m['memory_type']}, importance={m['importance']:.2f}] "
            f"{m['content'][:200]} (relevance: {m['score']:.2f})"
        )

    context_block = "## Vector Memory Recall\n" + "\n".join(lines)

    return {
        "relevant_memories": memories,
        "context_block": context_block,
    }


# ── Interactions ──────────────────────────────────────────────────

def store_interaction(
    db: Session,
    agent_id: str,
    input_text: str,
    output_text: Optional[str] = None,
) -> VectorInteraction:
    """Store an agent interaction (input/output pair)."""
    interaction = VectorInteraction(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        input_text=input_text,
        output_text=output_text,
    )
    db.add(interaction)
    db.flush()
    return interaction


def link_memory_to_interaction(
    db: Session,
    memory_id: str,
    interaction_id: str,
    relevance_score: float = 1.0,
) -> VectorMemoryLink:
    """Link a memory to the interaction that produced or used it."""
    link = VectorMemoryLink(
        id=str(uuid.uuid4()),
        memory_id=memory_id,
        interaction_id=interaction_id,
        relevance_score=relevance_score,
    )
    db.add(link)
    db.flush()
    return link


# ── Memory Decay ──────────────────────────────────────────────────

def decay_memories(
    db: Session,
    agent_id: Optional[str] = None,
    decay_rate: float = 0.01,
) -> int:
    """Decay memory importance over time using bulk SQL updates.

    Two-pass approach:
      1. Memories with last_accessed_at: decay slower (rate scales with days since access).
      2. Memories never accessed: decay at 2× rate.
    Returns total number of rows updated.
    """
    now = datetime.now(timezone.utc)

    # Pass 1: Never-accessed memories — flat 2× decay
    q1 = (
        update(VectorMemory)
        .where(VectorMemory.importance > 0.01)
        .where(VectorMemory.last_accessed_at.is_(None))
    )
    if agent_id:
        q1 = q1.where(VectorMemory.agent_id == agent_id)
    new_imp = func.max(0.0, VectorMemory.importance - decay_rate * 2.0)
    result1 = db.execute(q1.values(importance=new_imp, updated_at=now))

    # Pass 2: Recently-accessed memories — standard decay rate
    q2 = (
        update(VectorMemory)
        .where(VectorMemory.importance > 0.01)
        .where(VectorMemory.last_accessed_at.isnot(None))
    )
    if agent_id:
        q2 = q2.where(VectorMemory.agent_id == agent_id)
    result2 = db.execute(q2.values(
        importance=func.max(0.0, VectorMemory.importance - decay_rate),
        updated_at=now,
    ))

    db.flush()
    count = (result1.rowcount or 0) + (result2.rowcount or 0)
    logger.info(f"Decayed {count} memories (agent={agent_id or 'all'})")
    return count


def run_decay_all() -> int:
    """Standalone decay runner for scheduler (opens its own session)."""
    from api.database import get_public_db
    with get_public_db() as db:
        return decay_memories(db)


# ── Stats ─────────────────────────────────────────────────────────

def get_stats(db: Session, agent_id: str) -> dict:
    """Return memory stats for an agent."""
    total = db.query(func.count(VectorMemory.id)).filter(
        VectorMemory.agent_id == agent_id
    ).scalar() or 0

    type_counts = db.query(
        VectorMemory.memory_type,
        func.count(VectorMemory.id),
    ).filter(
        VectorMemory.agent_id == agent_id,
    ).group_by(VectorMemory.memory_type).all()

    avg_importance = db.query(func.avg(VectorMemory.importance)).filter(
        VectorMemory.agent_id == agent_id
    ).scalar() or 0.0

    return {
        "total_memories": total,
        "by_type": {t: c for t, c in type_counts},
        "avg_importance": round(float(avg_importance), 3),
        "vec_available": _check_vec_available(db),
    }


# ── Cleanup ───────────────────────────────────────────────────────

def delete_memory(db: Session, memory_id: str) -> bool:
    """Delete a memory and its vec index entry."""
    mem = db.query(VectorMemory).filter(VectorMemory.id == memory_id).first()
    if not mem:
        return False
    _remove_from_vec_index(db, memory_id)
    db.delete(mem)
    db.flush()
    return True
