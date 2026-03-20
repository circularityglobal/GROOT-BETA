# REFINET Knowledge Curator — Claude Code Installation Prompt

> **Copy everything below the line into Claude Code as a single prompt.**
> Run from inside your cloned `GROOT-BETA/` repo directory.
> Drop the 4 skill files from the `refinet-knowledge-curator/` folder into the conversation so Claude Code can read them.

---

## The Prompt

```
You are operating inside the GROOT-BETA repository (https://github.com/circularityglobal/GROOT-BETA), which is the REFINET Cloud sovereign AI platform. Your job is to install the `refinet-knowledge-curator` skill into the project and wire up fully autonomous, zero-cost RAG/CAG intelligence maintenance. Follow every step below precisely. Do not skip steps. Do not ask for confirmation between steps — execute them all sequentially.

## CONTEXT

REFINET Cloud is a sovereign AI platform running on Oracle Cloud Always Free tier (ARM A1 Flex, 4 OCPUs, 24GB RAM, 200GB storage). The knowledge base is the intelligence backbone — it powers both RAG (Retrieval-Augmented Generation) and CAG (Contract-Augmented Generation) for every user interaction with Groot.

Key knowledge base facts:
- Backend: FastAPI + SQLAlchemy 2.0 + SQLite WAL mode (public.db)
- Embeddings: sentence-transformers all-MiniLM-L6-v2 (384-dim, runs on CPU)
- Search: 3-signal hybrid — semantic (cosine similarity) + keyword (BM25) + FTS5 (SQLite full-text)
- Supported formats: PDF, DOCX, XLSX, CSV, TXT, Markdown, JSON, Solidity, YouTube, URL
- Chunking: 512 tokens target, 64 token overlap, sentence-aware splitting
- CAG: Parses smart contract ABIs from the registry, generates SDK descriptions, embeds for search
- Zero recurring cost is a HARD CONSTRAINT — all embedding/search runs locally on ARM CPU

The `refinet-platform-ops` skill is already installed at `skills/refinet-platform-ops/`. This new skill follows the same pattern: SKILL.md + scripts/ + references/, same cron structure, same email alerting, same LLM fallback chain.

Existing repo structure includes: api/, bitnet/, configs/, docs/, frontend/, migrations/, nginx/, products/, scripts/, skills/, memory/, plus root files GROOT.md, SOUL.md, SAFETY.md, AGENTS.md, MEMORY.md, HEARTBEAT.md.

## STEP 1 — Install the skill into the project

Create the following files from the provided skill package:

### 1a. Create `skills/refinet-knowledge-curator/SKILL.md`

This is the main skill file (546 lines). It covers:
- Part 1: Knowledge base architecture (dual RAG/CAG system, storage schema, formats, chunking params)
- Part 2: Autonomous pipelines (auto-ingestion, orphan detection, stale chunk pruning, CAG sync, embedding drift detection)
- Part 3: Admin email notifications (7 alert categories, daily digest template)
- Part 4: Cron schedule (5 scheduled tasks)
- Part 5: Operating procedures (health check, ingestion, orphan repair, search quality)
- Part 6: Safety constraints (inherited from SAFETY.md)
- Part 7: Reference file pointers

Read the provided SKILL.md file and copy it exactly to `skills/refinet-knowledge-curator/SKILL.md`.

### 1b. Create `skills/refinet-knowledge-curator/scripts/knowledge_health.py`

This is the knowledge base health checker (284 lines). It:
- Counts documents, chunks, embeddings in the database
- Detects orphaned documents (metadata exists, embeddings missing)
- Finds stale chunks (chunks exist, parent document deleted)
- Checks CAG sync status (ABIs not yet indexed)
- Optionally repairs orphans and prunes stale chunks (--repair flag)
- Formats and emails admin report (--email flag)
- Returns exit code 0 (healthy) or 1 (issues detected)

Read the provided knowledge_health.py and copy it exactly.

### 1c. Create `skills/refinet-knowledge-curator/references/knowledge-api.md`

Knowledge base API reference: all endpoints (upload, search, reindex, CAG sync), request/response schemas, and the complete SQLite database schema for documents, chunks, embeddings, FTS5, and CAG index tables.

### 1d. Create `skills/refinet-knowledge-curator/references/embedding-pipeline.md`

Embedding pipeline reference: full pipeline flow from upload to indexing, hybrid search algorithm with 3-signal fusion weights, re-embedding strategy (zero-downtime staging swap), capacity planning for ARM A1, and sentence-transformer setup.

## STEP 2 — Create the cron configuration

Create `configs/knowledge-curator-cron.yaml`:

```yaml
# REFINET Knowledge Curator — Autonomous RAG/CAG Maintenance Schedule
# All tasks execute through the zero-cost LLM fallback chain
# Total recurring cost: $0

schedules:
  # Every 30 minutes — check for unprocessed uploads
  - name: ingestion-check
    interval: 30m
    agent: knowledge-curator
    task: >
      Check for documents in the documents table with status 'pending' or
      with zero chunks. For each, run the ingestion pipeline and verify.
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
      Parse each, generate SDK descriptions, embed, and insert into cag_index.
      Email admin if new contracts were indexed.

  # Daily at 05:30 UTC — embedding quality benchmark
  - name: quality-benchmark
    cron: "30 5 * * *"
    agent: knowledge-curator
    task: >
      Run embedding benchmark against 5 standard queries. Compute average
      recall score. If recall below 0.5, flag embedding drift and alert admin.
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

## STEP 3 — Add GitHub Actions workflow

Create `.github/workflows/knowledge-curator.yml`:

```yaml
name: REFINET Knowledge Curator — Autonomous RAG/CAG Maintenance

on:
  schedule:
    # Daily health + digest at 06:00 UTC
    - cron: '0 6 * * *'
    # 6-hourly orphan repair + CAG sync
    - cron: '0 */6 * * *'
  workflow_dispatch:
    inputs:
      task:
        description: 'Knowledge curator task'
        required: false
        default: 'Full knowledge base health check with repair and email report'

jobs:
  health-check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Run knowledge health check
        run: python skills/refinet-knowledge-curator/scripts/knowledge_health.py --repair --email
        env:
          DATABASE_PATH: ${{ secrets.DATABASE_PATH }}
          REFINET_API_BASE: ${{ secrets.REFINET_API_BASE }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          MAIL_FROM: ${{ secrets.MAIL_FROM }}

  curator-task:
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      - name: Install jq
        run: sudo apt-get install -y jq

      - name: Run curator agent via fallback chain
        run: |
          chmod +x skills/refinet-platform-ops/scripts/run_agent.sh
          ./skills/refinet-platform-ops/scripts/run_agent.sh \
            knowledge-curator \
            "${{ github.event.inputs.task }}"
        env:
          REFINET_ROOT: ${{ github.workspace }}
          BITNET_HOST: ${{ secrets.BITNET_HOST }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
```

## STEP 4 — Add cron entries to the server installer

Read `scripts/install_platform_ops_cron.sh` and append these entries to the crontab section (before the closing CRON heredoc). If the file does not exist yet, create a new `scripts/install_knowledge_curator_cron.sh` with the same pattern:

```bash
# ── REFINET-KNOWLEDGE: Autonomous Knowledge Curator ─────────────
# Every 6 hours — orphan repair + CAG sync
0 */6 * * * cd ${REPO_ROOT} && python3 skills/refinet-knowledge-curator/scripts/knowledge_health.py --repair --email >> /var/log/refinet-knowledge.log 2>&1 # REFINET-KNOWLEDGE

# Daily quality benchmark at 05:30 UTC
30 5 * * * cd ${REPO_ROOT} && ${AGENT_SCRIPT} knowledge-curator "Run embedding benchmark and check for quality drift" >> /var/log/refinet-knowledge.log 2>&1 # REFINET-KNOWLEDGE

# Daily knowledge digest at 06:00 UTC
0 6 * * * cd ${REPO_ROOT} && ${AGENT_SCRIPT} knowledge-curator "Compile 24h knowledge digest and email admin" >> /var/log/refinet-knowledge.log 2>&1 # REFINET-KNOWLEDGE
```

## STEP 5 — Update AGENTS.md

Read the existing `AGENTS.md` and enhance the `knowledge-curator` row with full detail. If a basic entry already exists, replace it with:

```markdown

## knowledge-curator

**Role**: Autonomous RAG/CAG intelligence maintenance — document ingestion, embedding integrity, search quality monitoring, and contract index synchronization.

**Trigger sources**: Webhook (new upload), cron (30m ingestion check, 6h orphan repair, 6h CAG sync, daily benchmark, daily digest), heartbeat.

**LLM runtime**: Zero-cost fallback chain — Claude Code CLI → Ollama → BitNet → Gemini Flash.

**Tools** (MCP gateway access):
- `knowledge.search` — Hybrid search (semantic + keyword + FTS5)
- `knowledge.upload` — Document ingestion
- `knowledge.documents` — List/get/delete documents
- `knowledge.reindex` — Re-chunk and re-embed a document
- `knowledge.cag.sync` — Sync CAG index with registry ABIs
- `db.read.embeddings` — Read embedding tables for integrity checks
- `smtp.send` — Email admin alerts and digests

**Delegation policy**: `auto` — accepts delegated tasks from platform-ops and orchestrator. Can delegate to maintenance agent for cleanup tasks. Max depth: 3.

**Email alert categories**: INGESTION, INGESTION_FAIL, ORPHAN, PRUNE, CAG_SYNC, DRIFT, DIGEST.

**Key files**:
- `skills/refinet-knowledge-curator/SKILL.md` — Full operational manual
- `skills/refinet-knowledge-curator/scripts/knowledge_health.py` — KB health checker
- `skills/refinet-knowledge-curator/references/knowledge-api.md` — API reference
- `skills/refinet-knowledge-curator/references/embedding-pipeline.md` — Pipeline reference
- `configs/knowledge-curator-cron.yaml` — Cron schedule
- `.github/workflows/knowledge-curator.yml` — GitHub Actions runner
```

## STEP 6 — Update MEMORY.md

Read `MEMORY.md` and append this section:

```markdown

## Knowledge Curator Memory Usage

The knowledge-curator agent uses the 4-tier memory system as follows:

| Tier | What the Curator Stores |
|---|---|
| Working | Current ingestion batch state, documents being processed |
| Episodic | Ingestion events, orphan repairs, benchmark scores over time |
| Semantic | Embedding quality baselines, document format patterns |
| Procedural | Learned chunking strategies per format, optimal re-embed timing |

The curator's episodic memory is critical for embedding drift detection — it compares current benchmark scores against historical entries to identify downward trends. If 3+ consecutive benchmarks show declining recall, the agent escalates to admin with a full re-embed recommendation.
```

## STEP 7 — Wire into HEARTBEAT.md

Read `HEARTBEAT.md` and append to the "Platform Ops Agent Integration" section (or create a new section if it doesn't exist):

```markdown

### Knowledge Curator Integration

The heartbeat system also routes knowledge-related events to the curator agent:

| Interval | Agent | Task |
|---|---|---|
| 30m | knowledge-curator | Check for pending document uploads |
| 6h | knowledge-curator | Orphan detection + stale chunk pruning |
| 6h | knowledge-curator | CAG index sync with registry |
| Daily 05:30 | knowledge-curator | Embedding quality benchmark |
| Daily 06:00 | knowledge-curator | Knowledge base digest email |
```

## STEP 8 — Add setup documentation

Create `docs/KNOWLEDGE_CURATOR_SETUP.md`:

```markdown
# Knowledge Curator Setup Guide

## What It Does

The knowledge-curator agent autonomously maintains the RAG and CAG intelligence systems:
- Detects and re-embeds orphaned documents (ingestion failures)
- Prunes stale vector chunks from deleted documents
- Syncs new smart contract ABIs into the CAG search index
- Benchmarks semantic search quality weekly to detect embedding drift
- Sends daily knowledge base digest emails to admin

## Prerequisites

The platform-ops skill must be installed first (`skills/refinet-platform-ops/`), as the knowledge-curator reuses the `run_agent.sh` fallback chain.

## Testing Locally

```bash
# Check knowledge base health (read-only)
python skills/refinet-knowledge-curator/scripts/knowledge_health.py

# Check + repair orphans + prune stale chunks
python skills/refinet-knowledge-curator/scripts/knowledge_health.py --repair

# Full run with email report
python skills/refinet-knowledge-curator/scripts/knowledge_health.py --repair --email

# Run curator agent task via LLM fallback chain
./skills/refinet-platform-ops/scripts/run_agent.sh knowledge-curator "Check CAG sync status"
```

## Cost Breakdown

| Component | Monthly Cost |
|---|---|
| sentence-transformers (all-MiniLM-L6-v2) | $0 (local CPU) |
| SQLite FTS5 indexing | $0 (built into SQLite) |
| Embedding inference on ARM A1 | $0 (CPU-native) |
| GitHub Actions runner | $0 (shared with platform-ops) |
| Self-hosted SMTP alerts | $0 (Haraka) |
| **Total** | **$0/month** |
```

## STEP 9 — Verify and report

After completing all steps, verify:

1. `ls skills/refinet-knowledge-curator/` shows: SKILL.md, scripts/, references/
2. `ls skills/refinet-knowledge-curator/scripts/` shows: knowledge_health.py
3. `ls skills/refinet-knowledge-curator/references/` shows: knowledge-api.md, embedding-pipeline.md
4. `cat configs/knowledge-curator-cron.yaml` exists and has 5 schedule entries
5. `cat .github/workflows/knowledge-curator.yml` exists and has 2 jobs
6. `cat docs/KNOWLEDGE_CURATOR_SETUP.md` exists
7. `AGENTS.md` has enhanced knowledge-curator entry
8. `MEMORY.md` has Knowledge Curator Memory Usage section
9. `HEARTBEAT.md` has Knowledge Curator Integration table
10. The platform-ops `run_agent.sh` is reused (not duplicated) — the knowledge-curator calls it for LLM fallback

Print a summary of all files created/modified with line counts, and confirm the installation is complete. Note that this is the second of four autonomous agent skills (platform-ops → knowledge-curator → contract-watcher → security-sentinel).
```
