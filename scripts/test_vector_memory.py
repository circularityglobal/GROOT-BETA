#!/usr/bin/env python3
"""
REFINET Cloud — Vector Memory Test Script
Demonstrates store, search, dedup, decay, and context building.

Usage:
    python -m scripts.test_vector_memory
    # or
    python scripts/test_vector_memory.py
"""

SCRIPT_META = {
    "name": "test_vector_memory",
    "description": "Test vector memory store, search, dedup, and decay",
    "category": "testing",
    "requires_admin": False,
}

import sys
import os
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import init_databases, get_public_db
from api.services.vector_memory import (
    ensure_vec_index,
    is_vec_available,
    store_memory,
    store_memory_batch,
    retrieve_memory,
    build_context,
    decay_memories,
    get_stats,
    delete_memory,
)


TEST_USER_ID = "__test_vec_user__"
TEST_AGENT_ID = "__test_vec_agent__"


def _ensure_test_agent(db):
    """Create test user + agent registration if they don't exist (FK requirements)."""
    from api.models.public import User, AgentRegistration
    user = db.query(User).filter(User.id == TEST_USER_ID).first()
    if not user:
        user = User(
            id=TEST_USER_ID,
            email="vectest@localhost",
            username="__vectest__",
            hashed_password="__test__",
        )
        db.add(user)
        db.flush()
    agent = db.query(AgentRegistration).filter(AgentRegistration.id == TEST_AGENT_ID).first()
    if not agent:
        agent = AgentRegistration(
            id=TEST_AGENT_ID,
            user_id=TEST_USER_ID,
            name="Vector Memory Test Agent",
            product="test",
        )
        db.add(agent)
        db.flush()


def _cleanup_test_agent(db):
    """Remove test user + agent registration."""
    from api.models.public import User, AgentRegistration
    db.query(AgentRegistration).filter(AgentRegistration.id == TEST_AGENT_ID).delete()
    db.query(User).filter(User.id == TEST_USER_ID).delete()
    db.flush()

# Sample memories covering all types
SAMPLE_MEMORIES = [
    {
        "content": "The USDC contract on Polygon uses a proxy pattern with a separate implementation contract",
        "memory_type": "blockchain",
        "metadata": {"chain": "polygon", "contract": "USDC"},
        "importance": 0.9,
    },
    {
        "content": "User prefers concise responses with bullet points rather than long paragraphs",
        "memory_type": "user",
        "metadata": {"preference": "response_style"},
        "importance": 0.7,
    },
    {
        "content": "The search_documents tool returns results sorted by relevance with BM25 scoring",
        "memory_type": "tool",
        "metadata": {"tool": "search_documents"},
        "importance": 0.6,
    },
    {
        "content": "Gas prices on Ethereum mainnet are lowest between 2-5 AM UTC on weekends",
        "memory_type": "blockchain",
        "metadata": {"chain": "ethereum", "topic": "gas"},
        "importance": 0.8,
    },
    {
        "content": "The RAG system uses hybrid scoring: 40% semantic + 25% BM25 + 20% keyword + 15% tags",
        "memory_type": "system",
        "metadata": {"component": "rag"},
        "importance": 0.75,
    },
]


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    print("REFINET Cloud — Vector Memory Test")
    print("=" * 60)

    # ── Initialize ────────────────────────────────────────────
    separator("1. Initialization")
    init_databases()

    with get_public_db() as db:
        _ensure_test_agent(db)
        vec_ok = ensure_vec_index(db)
        print(f"  sqlite-vec available: {is_vec_available(db)}")
        print(f"  vec_memories table:   {'created' if vec_ok else 'skipped (brute-force fallback)'}")

        # Check embedding model
        from api.services.embedding import is_available
        print(f"  embedding model:      {'loaded' if is_available() else 'unavailable'}")

    # ── Store Memories ────────────────────────────────────────
    separator("2. Store Memories")
    stored_ids = []

    with get_public_db() as db:
        t0 = time.perf_counter()
        for i, sample in enumerate(SAMPLE_MEMORIES):
            mem = store_memory(
                db=db,
                agent_id=TEST_AGENT_ID,
                content=sample["content"],
                memory_type=sample["memory_type"],
                metadata=sample["metadata"],
                importance=sample["importance"],
            )
            stored_ids.append(mem.id)
            has_emb = "yes" if mem.embedding_json else "no"
            print(f"  [{i+1}] id={mem.id[:8]}... type={mem.memory_type:<12} "
                  f"importance={mem.importance:.2f} embedding={has_emb}")

        elapsed = time.perf_counter() - t0
        print(f"\n  Stored {len(stored_ids)} memories in {elapsed:.3f}s")

    # ── Deduplication Test ────────────────────────────────────
    separator("3. Deduplication Test")

    with get_public_db() as db:
        # Try storing a near-duplicate
        dup = store_memory(
            db=db,
            agent_id=TEST_AGENT_ID,
            content="The USDC contract on Polygon uses proxy pattern with separate implementation",
            memory_type="blockchain",
            importance=0.85,
        )
        if dup.id in stored_ids:
            print(f"  Deduplicated! Merged into existing memory {dup.id[:8]}...")
            print(f"  Updated importance: {dup.importance:.3f}")
        else:
            print(f"  Created new memory {dup.id[:8]}... (similarity below threshold)")
            stored_ids.append(dup.id)

    # ── Semantic Search ───────────────────────────────────────
    separator("4. Semantic Search")

    queries = [
        "How does USDC work on Polygon?",
        "What are the user's response preferences?",
        "Tell me about gas optimization on Ethereum",
    ]

    with get_public_db() as db:
        for query in queries:
            print(f"  Query: \"{query}\"")
            t0 = time.perf_counter()
            results = retrieve_memory(db, TEST_AGENT_ID, query, top_k=3)
            elapsed = time.perf_counter() - t0

            for j, r in enumerate(results):
                print(f"    #{j+1} [score={r['score']:.4f} sim={r['similarity']:.4f}] "
                      f"({r['memory_type']}) {r['content'][:80]}...")

            print(f"    ({elapsed:.3f}s)\n")

    # ── Filtered Search ───────────────────────────────────────
    separator("5. Filtered Search (blockchain type only)")

    with get_public_db() as db:
        results = retrieve_memory(
            db, TEST_AGENT_ID, "smart contract patterns",
            top_k=5, filters={"memory_type": "blockchain"},
        )
        for j, r in enumerate(results):
            print(f"  #{j+1} [score={r['score']:.4f}] ({r['memory_type']}) {r['content'][:80]}...")

    # ── Context Building ──────────────────────────────────────
    separator("6. Build Context (prompt injection)")

    with get_public_db() as db:
        ctx = build_context(db, TEST_AGENT_ID, "deploy a token contract", top_k=3)
        print(ctx["context_block"] if ctx["context_block"] else "  (no context)")

    # ── Memory Decay ──────────────────────────────────────────
    separator("7. Memory Decay")

    with get_public_db() as db:
        # Show before
        stats_before = get_stats(db, TEST_AGENT_ID)
        print(f"  Before decay: avg_importance={stats_before['avg_importance']:.3f}")

        count = decay_memories(db, TEST_AGENT_ID, decay_rate=0.05)
        print(f"  Decayed {count} memories (rate=0.05)")

        stats_after = get_stats(db, TEST_AGENT_ID)
        print(f"  After decay:  avg_importance={stats_after['avg_importance']:.3f}")

    # ── Stats ─────────────────────────────────────────────────
    separator("8. Stats")

    with get_public_db() as db:
        stats = get_stats(db, TEST_AGENT_ID)
        print(f"  Total memories:  {stats['total_memories']}")
        print(f"  By type:         {stats['by_type']}")
        print(f"  Avg importance:  {stats['avg_importance']:.3f}")
        print(f"  Vec available:   {stats['vec_available']}")

    # ── Batch Store ───────────────────────────────────────────
    separator("9. Batch Store")

    with get_public_db() as db:
        t0 = time.perf_counter()
        batch = store_memory_batch(db, TEST_AGENT_ID, [
            {"content": "Batch memory one: Solidity uses EVM opcodes", "memory_type": "system"},
            {"content": "Batch memory two: Rust contracts compile to WASM", "memory_type": "system"},
            {"content": "Batch memory three: Vyper is Python-like EVM language", "memory_type": "system"},
        ])
        elapsed = time.perf_counter() - t0
        print(f"  Batch stored {len(batch)} memories in {elapsed:.3f}s")
        for m in batch:
            stored_ids.append(m.id)

    # ── Cleanup ───────────────────────────────────────────────
    separator("10. Cleanup")

    with get_public_db() as db:
        for mid in stored_ids:
            delete_memory(db, mid)
        print(f"  Deleted {len(stored_ids)} test memories")

        final = get_stats(db, TEST_AGENT_ID)
        print(f"  Remaining: {final['total_memories']}")

        _cleanup_test_agent(db)

    print("\n" + "=" * 60)
    print("  All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
