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
