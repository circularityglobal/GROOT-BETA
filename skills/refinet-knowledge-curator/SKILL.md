---
name: refinet-knowledge-curator
description: >
  REFINET Cloud knowledge base curator skill for autonomous RAG/CAG intelligence
  maintenance. Use this skill whenever the user wants to: manage the REFINET knowledge
  base, ingest documents into RAG, sync smart contract ABIs into CAG, detect orphaned
  embeddings, prune stale vector chunks, re-embed documents, monitor embedding quality,
  run knowledge base integrity checks, automate document ingestion pipelines, or build
  autonomous knowledge management workflows on REFINET Cloud. Triggers on phrases like
  "knowledge base", "RAG maintenance", "CAG sync", "embedding quality", "document ingestion",
  "re-embed", "orphaned documents", "stale chunks", "vector index", "knowledge curator",
  "semantic search quality", "knowledge pipeline", "auto-ingest", "embedding drift",
  "knowledge digest", "GROOT knowledge", "REFINET documents", "contract ABI ingestion",
  "CAG index", "knowledge health", "chunking", "sentence-transformer", "FTS5 index",
  "knowledge integrity", or any request to curate, maintain, audit, or automate the
  GROOT-BETA / REFINET Cloud knowledge base, RAG pipeline, or CAG contract index.
  Also triggers when discussing document upload quality, search relevance tuning,
  or knowledge base capacity planning.
---

# REFINET Knowledge Curator — Autonomous RAG/CAG Intelligence Skill

This skill gives Claude everything needed to:
1. Autonomously maintain the RAG knowledge base (document ingestion, chunking, embedding, pruning)
2. Synchronize the CAG contract index when new ABIs enter the smart contract registry
3. Detect and repair orphaned embeddings, stale chunks, and ingestion failures
4. Monitor semantic search quality over time and trigger re-embedding when drift is detected
5. Send structured admin email digests about knowledge base health and activity

---

## Part 1 — Knowledge Base Architecture

### 1.1 The Dual Intelligence System

REFINET Cloud augments every LLM response with two retrieval systems. Both inject context into the 7-layer stack before inference.

```
User query
    │
    ├──→ RAG (Retrieval-Augmented Generation)
    │      │
    │      ├── Semantic search: sentence-transformer embeddings (384-dim)
    │      ├── Keyword scoring: BM25-style term matching
    │      └── Full-text indexing: SQLite FTS5
    │      │
    │      └──→ Top-K document chunks injected into context
    │
    ├──→ CAG (Contract-Augmented Generation)
    │      │
    │      ├── ABI search: parsed function/event signatures
    │      └── SDK search: generated SDK method definitions
    │      │
    │      └──→ Matching contract context injected
    │
    └──→ LLM inference (BitNet / Ollama / Claude Code / Gemini)
```

### 1.2 Storage Architecture

| Component | Storage | Location |
|---|---|---|
| Document metadata | SQLite `public.db` | `knowledge_documents` table |
| Document chunks | SQLite `public.db` | `knowledge_chunks` table (embedding JSON column, 384-dim) |
| Full-text index | SQLite FTS5 | `document_chunks_fts` virtual table |
| Contract definitions | SQLite `public.db` | `contract_definitions` table |
| Registry ABIs | SQLite `public.db` | `registry_abis` table |
| Parsed SDK defs | SQLite `public.db` | `registry_sdks` table |
| Security flags | SQLite `public.db` | `contract_security_flags` table |

### 1.3 Supported Input Formats

| Format | Chunking Strategy | Embedding |
|---|---|---|
| PDF | Page-aware sentence splitting | sentence-transformers |
| DOCX | Paragraph-aware splitting | sentence-transformers |
| XLSX/CSV | Row-group chunking (headers preserved) | sentence-transformers |
| TXT/Markdown | Sentence splitting with overlap | sentence-transformers |
| JSON | Key-path aware chunking | sentence-transformers |
| Solidity (.sol) | Function-level splitting (ABI extracted separately) | sentence-transformers |
| YouTube URL | Transcript extraction → sentence splitting | sentence-transformers |
| URL | HTML content extraction → sentence splitting | sentence-transformers |

### 1.4 Chunking Parameters

```python
CHUNK_SIZE = 512          # tokens per chunk (target)
CHUNK_OVERLAP = 64        # overlap between consecutive chunks
EMBEDDING_DIM = 384       # sentence-transformer output dimensions
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # default model
MIN_CHUNK_LENGTH = 50     # minimum chars to embed (skip tiny fragments)
MAX_CHUNKS_PER_DOC = 500  # safety limit per document
```

---

## Part 2 — Autonomous Pipelines

### 2.1 Auto-Ingestion Pipeline

When a new document is uploaded via `POST /knowledge/upload` or `POST /knowledge/youtube`, the knowledge-curator agent should:

```
1. PERCEIVE — New document detected (webhook trigger or periodic scan)
2. PLAN    — Determine format, estimate chunk count, check for duplicates
3. ACT     — Chunk document → embed chunks → insert into vector index → update FTS5
4. OBSERVE — Verify: chunk_count > 0, all embeddings are 384-dim, FTS5 entries exist
5. REFLECT — Log: ingestion time, chunk count, any errors, duplicate detection result
6. STORE   — Write to episodic memory, email admin digest if configured
```

**Verification checklist (run after every ingestion):**

```python
def verify_ingestion(document_id: str) -> dict:
    """Verify a document was fully ingested. Returns health report."""
    checks = {}

    # 1. Document exists in metadata table
    doc = db.execute(
        "SELECT id, title, doc_type, visibility, created_at FROM knowledge_documents WHERE id = ?",
        (document_id,)
    ).fetchone()
    checks["metadata_exists"] = doc is not None

    # 2. Chunks were created
    chunk_count = db.execute(
        "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?",
        (document_id,)
    ).fetchone()[0]
    checks["chunks_created"] = chunk_count
    checks["chunks_ok"] = chunk_count > 0

    # 3. All chunks have embeddings (embedding column on knowledge_chunks)
    embedded_count = db.execute(
        "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ? AND embedding IS NOT NULL",
        (document_id,)
    ).fetchone()[0]
    checks["embeddings_created"] = embedded_count
    checks["embeddings_complete"] = embedded_count == chunk_count

    # 4. FTS5 entries exist
    fts_count = db.execute(
        "SELECT COUNT(*) FROM document_chunks_fts WHERE rowid IN "
        "(SELECT rowid FROM knowledge_chunks WHERE document_id = ?)",
        (document_id,)
    ).fetchone()[0]
    checks["fts_entries"] = fts_count
    checks["fts_complete"] = fts_count == chunk_count

    # 5. Embedding dimensions are correct
    if embedded_count > 0:
        sample = db.execute(
            "SELECT embedding FROM knowledge_chunks WHERE document_id = ? AND embedding IS NOT NULL LIMIT 1",
            (document_id,)
        ).fetchone()
        if sample:
            import json
            vec = json.loads(sample[0])
            checks["embedding_dim"] = len(vec)
            checks["embedding_dim_ok"] = len(vec) == 384

    checks["fully_ingested"] = all([
        checks.get("chunks_ok"),
        checks.get("embeddings_complete"),
        checks.get("fts_complete"),
        checks.get("embedding_dim_ok", True)
    ])

    return checks
```

### 2.2 Orphan Detection and Re-Embedding

Run every 6 hours. Finds documents that exist in metadata but have missing or incomplete embeddings.

```python
def find_orphaned_documents() -> list[dict]:
    """Find documents with missing or incomplete embeddings."""
    orphans = db.execute("""
        SELECT d.id, d.title, d.doc_type,
               COUNT(dc.id) as num_chunks,
               SUM(CASE WHEN dc.embedding IS NOT NULL THEN 1 ELSE 0 END) as num_embeddings
        FROM knowledge_documents d
        LEFT JOIN knowledge_chunks dc ON dc.document_id = d.id
        GROUP BY d.id
        HAVING num_chunks = 0 OR num_embeddings < num_chunks
    """).fetchall()

    return [
        {
            "document_id": row[0],
            "title": row[1],
            "format": row[2],
            "chunks": row[3],
            "embeddings": row[4],
            "missing_embeddings": row[3] - row[4],
            "status": "no_chunks" if row[3] == 0 else "partial_embeddings"
        }
        for row in orphans
    ]


def reembed_document(document_id: str):
    """Re-chunk and re-embed a document from its stored content."""
    # 1. Delete existing chunks for this document (embeddings are inline)
    db.execute("DELETE FROM knowledge_chunks WHERE document_id = ?",
               (document_id,))
    db.commit()

    # 2. Re-chunk from stored source content
    # (Implementation depends on the platform's chunking pipeline)
    # Call: POST /knowledge/reindex/{document_id}

    # 3. Verify
    return verify_ingestion(document_id)
```

### 2.3 Stale Chunk Pruning

Finds embeddings that reference deleted documents (ghost context).

```python
def find_stale_chunks() -> list[dict]:
    """Find chunks whose parent document no longer exists."""
    stale = db.execute("""
        SELECT dc.id, dc.document_id, dc.chunk_index,
               LENGTH(dc.content) as content_length
        FROM knowledge_chunks dc
        LEFT JOIN knowledge_documents d ON d.id = dc.document_id
        WHERE d.id IS NULL
    """).fetchall()

    return [
        {
            "chunk_id": row[0],
            "orphaned_document_id": row[1],
            "chunk_index": row[2],
            "content_bytes": row[3]
        }
        for row in stale
    ]


def prune_stale_chunks() -> dict:
    """Remove all chunks and embeddings for deleted documents."""
    stale = find_stale_chunks()
    if not stale:
        return {"pruned": 0, "status": "clean"}

    chunk_ids = [s["chunk_id"] for s in stale]
    placeholders = ",".join("?" * len(chunk_ids))

    # Delete chunks (embeddings are inline, no separate table)
    db.execute(f"DELETE FROM knowledge_chunks WHERE id IN ({placeholders})", chunk_ids)
    db.commit()

    return {"pruned": len(stale), "freed_chunks": len(chunk_ids), "status": "pruned"}
```

### 2.4 CAG Index Synchronization

When new ABIs enter the smart contract registry, the CAG index must be updated.

```python
def sync_cag_index() -> dict:
    """Sync CAG search index with latest registry ABIs."""
    # Find ABIs not yet in CAG index
    unindexed = db.execute("""
        SELECT ra.id, ra.project_id, ra.chain, ra.contract_address
        FROM registry_abis ra
        LEFT JOIN contract_definitions cd ON cd.address = ra.contract_address AND cd.chain = ra.chain
        WHERE cd.id IS NULL
    """).fetchall()

    if not unindexed:
        return {"synced": 0, "status": "up_to_date"}

    indexed = 0
    for abi in unindexed:
        # 1. Parse ABI → extract function signatures + event signatures
        # 2. Generate SDK method descriptions
        # 3. Embed function descriptions with sentence-transformers
        # 4. Insert into contract_definitions table
        # Call: POST /registry/projects/{project_id}/abis/{abi_id}/reindex
        indexed += 1

    return {"synced": indexed, "total_unindexed_found": len(unindexed), "status": "synced"}
```

### 2.5 Embedding Drift Detection

Weekly benchmark to ensure semantic search quality hasn't degraded.

```python
# Benchmark queries — these should return predictable top results
BENCHMARK_QUERIES = [
    {
        "query": "How does SIWE authentication work on REFINET?",
        "expected_keywords": ["SIWE", "EIP-4361", "wallet", "authentication", "sign"],
        "min_score": 0.6
    },
    {
        "query": "What is the agent cognitive loop?",
        "expected_keywords": ["PERCEIVE", "PLAN", "ACT", "OBSERVE", "REFLECT", "STORE"],
        "min_score": 0.5
    },
    {
        "query": "How are smart contract ABIs parsed?",
        "expected_keywords": ["ABI", "function", "event", "parsing", "SDK"],
        "min_score": 0.5
    },
    {
        "query": "What are the memory tiers for agents?",
        "expected_keywords": ["working", "episodic", "semantic", "procedural"],
        "min_score": 0.5
    },
    {
        "query": "How does the chain listener monitor on-chain events?",
        "expected_keywords": ["chain", "listener", "event", "webhook", "block"],
        "min_score": 0.5
    }
]


def run_embedding_benchmark() -> dict:
    """Run benchmark queries and check semantic search quality."""
    results = []
    total_score = 0

    for bench in BENCHMARK_QUERIES:
        # Call: POST /knowledge/search with bench["query"]
        # Check if top-3 results contain expected keywords
        search_results = knowledge_search(bench["query"], top_k=3)

        matched_keywords = 0
        for keyword in bench["expected_keywords"]:
            for result in search_results:
                if keyword.lower() in result["content"].lower():
                    matched_keywords += 1
                    break

        recall = matched_keywords / len(bench["expected_keywords"])
        passed = recall >= bench["min_score"]
        total_score += recall

        results.append({
            "query": bench["query"],
            "recall": round(recall, 2),
            "passed": passed,
            "matched": matched_keywords,
            "expected": len(bench["expected_keywords"])
        })

    avg_recall = total_score / len(BENCHMARK_QUERIES)
    drift_detected = avg_recall < 0.5

    return {
        "average_recall": round(avg_recall, 2),
        "drift_detected": drift_detected,
        "benchmarks": results,
        "recommendation": "FULL RE-EMBED RECOMMENDED" if drift_detected else "Quality acceptable"
    }
```

---

## Part 3 — Admin Email Notifications

### 3.1 Alert Categories

| Category | Subject Prefix | When |
|---|---|---|
| INGESTION | `[REFINET KNOWLEDGE]` | New document ingested successfully |
| INGESTION_FAIL | `[REFINET KNOWLEDGE]` | Document ingestion failed verification |
| ORPHAN | `[REFINET KNOWLEDGE]` | Orphaned documents detected and re-embedded |
| PRUNE | `[REFINET KNOWLEDGE]` | Stale chunks pruned from vector index |
| CAG_SYNC | `[REFINET KNOWLEDGE]` | New ABIs synced to CAG index |
| DRIFT | `[REFINET KNOWLEDGE]` | Embedding drift detected — quality below threshold |
| DIGEST | `[REFINET KNOWLEDGE]` | Daily knowledge base activity digest |

### 3.2 Email Sending Pattern

Use the same `send_admin_alert()` function from the platform-ops skill. Category is always `KNOWLEDGE`.

### 3.3 Daily Digest Template

```python
def knowledge_digest_body(stats: dict) -> str:
    return f"""
    <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('total_documents', 0)}</div>
        <div style="font-size: 12px; color: #888;">Documents</div>
      </div>
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('total_chunks', 0)}</div>
        <div style="font-size: 12px; color: #888;">Chunks</div>
      </div>
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('cag_contracts', 0)}</div>
        <div style="font-size: 12px; color: #888;">CAG contracts</div>
      </div>
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: {'#ff6b6b' if stats.get('orphans_found', 0) > 0 else '#00d4aa'}; font-weight: bold;">{stats.get('orphans_found', 0)}</div>
        <div style="font-size: 12px; color: #888;">Orphans fixed</div>
      </div>
    </div>
    <table style="width: 100%; color: #e0e0e0; font-size: 13px;">
      <tr><td style="padding: 4px 0; color: #888;">New docs (24h)</td><td style="text-align: right;">{stats.get('new_documents_24h', 0)}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">New chunks (24h)</td><td style="text-align: right;">{stats.get('new_chunks_24h', 0)}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">Stale pruned (24h)</td><td style="text-align: right;">{stats.get('stale_pruned_24h', 0)}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">CAG ABIs synced (24h)</td><td style="text-align: right;">{stats.get('cag_synced_24h', 0)}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">Search quality score</td><td style="text-align: right; color: {'#ff6b6b' if stats.get('search_quality', 1) < 0.5 else '#00d4aa'};">{stats.get('search_quality', '—')}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">DB size</td><td style="text-align: right;">{stats.get('db_size_mb', '—')} MB</td></tr>
    </table>
    """
```

---

## Part 4 — Cron Schedule

```yaml
# configs/knowledge-curator-cron.yaml
schedules:
  # Every 30 minutes — check for new unprocessed uploads
  - name: ingestion-check
    interval: 30m
    agent: knowledge-curator
    task: >
      Check for documents in the knowledge_documents table with zero chunks
      or missing embeddings. For each, run the ingestion pipeline and verify.
      Email admin summary if any new documents were processed.

  # Every 6 hours — orphan detection and repair
  - name: orphan-repair
    interval: 6h
    agent: knowledge-curator
    task: >
      Scan for orphaned documents (metadata exists, chunks/embeddings missing).
      Re-embed all orphans. Scan for stale chunks (chunks exist, parent document
      deleted). Prune all stale chunks. Email admin report with counts.

  # Every 6 hours — CAG index sync
  - name: cag-sync
    interval: 6h
    agent: knowledge-curator
    task: >
      Check smart contract registry for ABIs not yet in the CAG index.
      Parse each, generate SDK descriptions, embed, and insert into contract_definitions.
      Email admin if new contracts were indexed.

  # Daily at 05:30 UTC — embedding quality benchmark
  - name: quality-benchmark
    cron: "30 5 * * *"
    agent: knowledge-curator
    task: >
      Run embedding benchmark against 5 standard queries. Compute average
      recall score. If recall < 0.5, flag embedding drift and alert admin.
      Log results to episodic memory for trend tracking.

  # Daily at 06:00 UTC — knowledge digest email
  - name: daily-digest
    cron: "0 6 * * *"
    agent: knowledge-curator
    task: >
      Compile 24-hour knowledge base digest: new documents ingested, total
      chunks created, orphans repaired, stale chunks pruned, CAG contracts
      synced, search quality score, database size. Format as HTML dashboard
      email and send to admin.
```

---

## Part 5 — Operating Procedures

### 5.1 When User Asks to Check Knowledge Base Health

1. Count total documents, chunks, embeddings in DB
2. Run `find_orphaned_documents()` — report any orphans
3. Run `find_stale_chunks()` — report any ghost context
4. Run `run_embedding_benchmark()` — report search quality
5. Check CAG sync status — report unindexed ABIs
6. Compile and email health report to admin

### 5.2 When User Asks to Ingest a Document

1. Accept document path or URL
2. Determine format and chunking strategy from Part 1.3
3. Chunk with parameters from Part 1.4
4. Embed all chunks with sentence-transformers (384-dim)
5. Insert into `knowledge_chunks` (with embedding column) and `document_chunks_fts`
6. Run `verify_ingestion()` to confirm completeness
7. Email admin confirmation with chunk count and any warnings

### 5.3 When User Asks to Fix Orphaned Documents

1. Run `find_orphaned_documents()`
2. For each orphan, call `reembed_document()`
3. Verify each re-embedding with `verify_ingestion()`
4. Run `find_stale_chunks()` and `prune_stale_chunks()`
5. Email admin summary of repairs

### 5.4 When User Asks About Search Quality

1. Run `run_embedding_benchmark()`
2. If `drift_detected` is True, recommend full re-embedding
3. Show per-query recall scores
4. Compare against historical scores in episodic memory
5. If trending downward over 3+ runs, escalate to admin

---

## Part 6 — Safety Constraints

Inherited from SAFETY.md — always enforced:

- Never expose private document content from other users' namespaces
- Only access documents with `visibility: public` or owned by the authenticated user
- Contract source code is never included in agent context — SDKs and parsed ABIs only
- Agents write to memory ONLY during REFLECT/STORE phases, never mid-action
- Working memory is scoped to a single task and auto-cleaned after completion
- Log all tool calls to episodic memory with full parameters and results
- Token budget per knowledge-curator task: 4096 tokens max context injection

---

## Part 7 — Reference Files

Read these for implementation specifics:

- `references/knowledge-api.md` — Knowledge base API endpoints and schemas
- `references/embedding-pipeline.md` — Chunking, embedding, and indexing implementation details

For platform infrastructure context, consult the `refinet-platform-ops` skill.
For agent architecture patterns, consult the `agent-os` skill.
For self-hosted SMTP implementation, consult the `smtp-self-hosted` skill.
