"""
REFINET Cloud — Agent Memory Service
4-tier memory system: working, episodic, semantic, procedural.
Provides CRUD and recall for each tier with semantic search support.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from api.models.agent_engine import (
    AgentMemoryWorking,
    AgentMemoryEpisodic,
    AgentMemorySemantic,
    AgentMemoryProcedural,
)

logger = logging.getLogger("refinet.agent.memory")


# ── Working Memory (Tier 1) — short-lived, per-task ──────────────

def store_working(
    db: Session,
    agent_id: str,
    task_id: str,
    key: str,
    value: str,
    ttl_seconds: int = 3600,
) -> AgentMemoryWorking:
    """Store a working memory entry with TTL."""
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    # Upsert: update if same agent+task+key exists
    existing = db.query(AgentMemoryWorking).filter(
        AgentMemoryWorking.agent_id == agent_id,
        AgentMemoryWorking.task_id == task_id,
        AgentMemoryWorking.key == key,
    ).first()

    if existing:
        existing.value = value
        existing.expires_at = expires
        db.flush()
        return existing

    entry = AgentMemoryWorking(
        agent_id=agent_id,
        task_id=task_id,
        key=key,
        value=value,
        expires_at=expires,
    )
    db.add(entry)
    db.flush()
    return entry


def recall_working(db: Session, agent_id: str, task_id: str) -> dict[str, str]:
    """Recall all working memory for a specific task. Returns {key: value}."""
    now = datetime.now(timezone.utc)
    entries = db.query(AgentMemoryWorking).filter(
        AgentMemoryWorking.agent_id == agent_id,
        AgentMemoryWorking.task_id == task_id,
        (AgentMemoryWorking.expires_at == None) | (AgentMemoryWorking.expires_at > now),  # noqa: E711
    ).all()
    return {e.key: e.value for e in entries}


def clear_working(db: Session, agent_id: str, task_id: str) -> int:
    """Clear all working memory for a completed task."""
    count = db.query(AgentMemoryWorking).filter(
        AgentMemoryWorking.agent_id == agent_id,
        AgentMemoryWorking.task_id == task_id,
    ).delete()
    db.flush()
    return count


def cleanup_expired_working(db: Session) -> int:
    """Remove all expired working memory entries. Called by background task."""
    now = datetime.now(timezone.utc)
    count = db.query(AgentMemoryWorking).filter(
        AgentMemoryWorking.expires_at != None,  # noqa: E711
        AgentMemoryWorking.expires_at < now,
    ).delete()
    db.flush()
    return count


# ── Episodic Memory (Tier 2) — timestamped events ────────────────

def store_episode(
    db: Session,
    agent_id: str,
    event_type: str,
    summary: str,
    context: Optional[dict] = None,
    outcome: str = "success",
    tokens_used: int = 0,
) -> AgentMemoryEpisodic:
    """Store an episodic memory entry (DB + JSONL)."""
    entry = AgentMemoryEpisodic(
        agent_id=agent_id,
        event_type=event_type,
        summary=summary,
        context_json=json.dumps(context) if context else None,
        outcome=outcome,
        tokens_used=tokens_used,
    )
    db.add(entry)
    db.flush()

    # Also append to JSONL file for audit trail
    try:
        from api.services.jsonl_logger import append_episode
        task_id = context.get("task_id") if context else None
        append_episode(
            agent_id=agent_id,
            event_type=event_type,
            summary=summary,
            context=context,
            outcome=outcome,
            tokens_used=tokens_used,
            task_id=task_id,
        )
    except Exception:
        pass  # JSONL logging is non-fatal

    return entry


def recall_episodes(
    db: Session,
    agent_id: str,
    event_type: Optional[str] = None,
    outcome: Optional[str] = None,
    max_results: int = 10,
) -> list[dict]:
    """Recall recent episodic memories, optionally filtered by type/outcome."""
    q = db.query(AgentMemoryEpisodic).filter(
        AgentMemoryEpisodic.agent_id == agent_id,
    )
    if event_type:
        q = q.filter(AgentMemoryEpisodic.event_type == event_type)
    if outcome:
        q = q.filter(AgentMemoryEpisodic.outcome == outcome)

    entries = q.order_by(desc(AgentMemoryEpisodic.timestamp)).limit(max_results).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "summary": e.summary,
            "context": json.loads(e.context_json) if e.context_json else None,
            "outcome": e.outcome,
            "tokens_used": e.tokens_used,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in entries
    ]


def recall_relevant_episodes(
    db: Session,
    agent_id: str,
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """Recall episodic memories relevant to a query (keyword search)."""
    import re
    keywords = re.findall(r'\w+', query.lower())
    if not keywords:
        return recall_episodes(db, agent_id, max_results=max_results)

    from sqlalchemy import or_
    conditions = []
    for kw in keywords[:5]:
        conditions.append(AgentMemoryEpisodic.summary.ilike(f"%{kw}%"))

    entries = db.query(AgentMemoryEpisodic).filter(
        AgentMemoryEpisodic.agent_id == agent_id,
        or_(*conditions),
    ).order_by(desc(AgentMemoryEpisodic.timestamp)).limit(max_results).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "summary": e.summary,
            "outcome": e.outcome,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in entries
    ]


# ── Semantic Memory (Tier 3) — learned facts ─────────────────────

def learn_fact(
    db: Session,
    agent_id: str,
    fact: str,
    source: Optional[str] = None,
    confidence: float = 0.5,
) -> AgentMemorySemantic:
    """Store a learned fact. Deduplicates by checking existing facts."""
    # Simple dedup: check for very similar existing facts
    existing = db.query(AgentMemorySemantic).filter(
        AgentMemorySemantic.agent_id == agent_id,
        AgentMemorySemantic.fact == fact,
    ).first()

    if existing:
        # Update confidence (weighted average)
        existing.confidence = (existing.confidence + confidence) / 2
        existing.usage_count += 1
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    # Generate embedding if available
    embedding_json = None
    try:
        from api.services.embedding import embed_text, serialize_embedding
        vec = embed_text(fact)
        if vec is not None:
            embedding_json = serialize_embedding(vec)
    except Exception:
        pass

    entry = AgentMemorySemantic(
        agent_id=agent_id,
        fact=fact,
        confidence=confidence,
        source=source,
        embedding=embedding_json,
    )
    db.add(entry)
    db.flush()
    return entry


def recall_facts(
    db: Session,
    agent_id: str,
    query: Optional[str] = None,
    max_results: int = 10,
    min_confidence: float = 0.0,
) -> list[dict]:
    """Recall semantic facts, optionally filtered by query relevance."""
    q = db.query(AgentMemorySemantic).filter(
        AgentMemorySemantic.agent_id == agent_id,
        AgentMemorySemantic.confidence >= min_confidence,
    )

    entries = q.order_by(desc(AgentMemorySemantic.confidence)).limit(max_results * 3).all()

    # If query provided, re-rank by semantic similarity
    if query and entries:
        try:
            from api.services.embedding import embed_text, deserialize_embedding, cosine_similarity
            query_vec = embed_text(query)
            if query_vec:
                scored = []
                for e in entries:
                    if e.embedding:
                        fact_vec = deserialize_embedding(e.embedding)
                        if fact_vec:
                            sim = cosine_similarity(query_vec, fact_vec)
                            scored.append((sim, e))
                            continue
                    scored.append((0.0, e))

                scored.sort(key=lambda x: x[0], reverse=True)
                entries = [e for _, e in scored[:max_results]]
        except Exception:
            entries = entries[:max_results]
    else:
        entries = entries[:max_results]

    return [
        {
            "id": e.id,
            "fact": e.fact,
            "confidence": e.confidence,
            "source": e.source,
            "usage_count": e.usage_count,
        }
        for e in entries
    ]


# ── Procedural Memory (Tier 4) — strategy patterns ──────────────

def store_procedure(
    db: Session,
    agent_id: str,
    pattern_name: str,
    trigger_condition: str,
    action_sequence: list[dict],
    success_rate: float = 0.0,
) -> AgentMemoryProcedural:
    """Store or update a procedural memory pattern."""
    existing = db.query(AgentMemoryProcedural).filter(
        AgentMemoryProcedural.agent_id == agent_id,
        AgentMemoryProcedural.pattern_name == pattern_name,
    ).first()

    if existing:
        existing.trigger_condition = trigger_condition
        existing.action_sequence = json.dumps(action_sequence)
        # Weighted update of success rate
        existing.success_rate = (
            existing.success_rate * existing.usage_count + success_rate
        ) / (existing.usage_count + 1)
        existing.usage_count += 1
        existing.last_used_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    entry = AgentMemoryProcedural(
        agent_id=agent_id,
        pattern_name=pattern_name,
        trigger_condition=trigger_condition,
        action_sequence=json.dumps(action_sequence),
        success_rate=success_rate,
    )
    db.add(entry)
    db.flush()
    return entry


def match_procedure(
    db: Session,
    agent_id: str,
    situation: str,
    max_results: int = 3,
) -> list[dict]:
    """Find procedures relevant to a situation (keyword matching on trigger conditions)."""
    import re
    keywords = re.findall(r'\w+', situation.lower())
    if not keywords:
        return []

    from sqlalchemy import or_
    conditions = []
    for kw in keywords[:5]:
        conditions.append(AgentMemoryProcedural.trigger_condition.ilike(f"%{kw}%"))

    entries = db.query(AgentMemoryProcedural).filter(
        AgentMemoryProcedural.agent_id == agent_id,
        or_(*conditions),
    ).order_by(desc(AgentMemoryProcedural.success_rate)).limit(max_results).all()

    return [
        {
            "id": e.id,
            "pattern_name": e.pattern_name,
            "trigger_condition": e.trigger_condition,
            "action_sequence": json.loads(e.action_sequence) if e.action_sequence else [],
            "success_rate": e.success_rate,
            "usage_count": e.usage_count,
        }
        for e in entries
    ]


# ── Memory Summary (for system prompt injection) ─────────────────

def build_memory_context(
    db: Session,
    agent_id: str,
    task_description: str,
    task_id: Optional[str] = None,
) -> str:
    """
    Build a memory context string for injection into the agent's system prompt.
    Combines relevant entries from all 4 memory tiers.
    """
    parts = []

    # Working memory (current task context)
    if task_id:
        working = recall_working(db, agent_id, task_id)
        if working:
            items = [f"  {k}: {v}" for k, v in working.items()]
            parts.append("## Current Task Context\n" + "\n".join(items))

    # Relevant episodic memories
    episodes = recall_relevant_episodes(db, agent_id, task_description, max_results=3)
    if episodes:
        ep_lines = []
        for ep in episodes:
            ep_lines.append(f"  [{ep['outcome']}] {ep['summary']}")
        parts.append("## Relevant Past Experiences\n" + "\n".join(ep_lines))

    # Relevant facts
    facts = recall_facts(db, agent_id, query=task_description, max_results=5)
    if facts:
        fact_lines = [f"  - {f['fact']} (confidence: {f['confidence']:.1f})" for f in facts]
        parts.append("## Known Facts\n" + "\n".join(fact_lines))

    # Matching procedures
    procedures = match_procedure(db, agent_id, task_description, max_results=2)
    if procedures:
        proc_lines = []
        for p in procedures:
            proc_lines.append(f"  Pattern: {p['pattern_name']} (success: {p['success_rate']:.0%})")
            proc_lines.append(f"  Trigger: {p['trigger_condition']}")
        parts.append("## Known Strategies\n" + "\n".join(proc_lines))

    # Vector memory (Tier 5) — sqlite-vec hybrid search
    try:
        from api.services.vector_memory import build_context as vec_build_context
        result = vec_build_context(db, agent_id, task_description, top_k=3)
        if result and result.get("context_block"):
            parts.append(result["context_block"])
    except Exception:
        pass  # Vector memory is complementary

    return "\n\n".join(parts) if parts else ""
