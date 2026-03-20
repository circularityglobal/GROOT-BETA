# MEMORY.md — Memory Access Protocol

## Tiers

| Tier | Access | TTL | Format | Description |
|---|---|---|---|---|
| Working | Read/write per-run | Per-task (auto-cleared) | JSON | Ephemeral task state, intermediate results |
| Episodic | Append + query | 90 days | DB + JSONL | Timestamped event records with outcomes |
| Semantic | RAG search | Permanent | Chunks + embeddings | Learned facts with confidence scores |
| Procedural | Read + update on reflect | Permanent | JSON patterns | Strategy patterns with success rates |

## Rules
- Agents write to memory ONLY during the REFLECT/STORE phases, never mid-action.
- Only the context builder reads from semantic memory. Agents never query directly.
- Working memory is cleared at the start of each new task.
- Episodic memory is queryable by: agent name, task type, date range, outcome.
- Procedural memory stores learned patterns: which tool sequences work for which task types.
- Agent memories belong to the agent's owner and are never shared across users.

## Access Control
- Private documents (visibility: private) are only accessible to their owner.
- Contract source code is never included in agent context — SDKs only.
- Working memory is scoped to a single task and auto-cleaned after completion.

## File-Based Memory Directories

In addition to DB-backed memory, agents write to persistent file-based directories for cross-run state:

| Directory | Format | Purpose |
|---|---|---|
| `memory/working/` | `{agent_name}.json` | Latest run state per agent (overwritten each run) |
| `memory/episodic/` | `{agent_name}.jsonl` | Append-only log of all agent runs (JSONL) |
| `memory/semantic/` | JSON files | Distilled facts extracted during REFLECT phase |
| `memory/procedural/` | JSON files | Learned tool-use patterns with success rates |

The `run_agent.sh` pipeline runner (`skills/refinet-platform-ops/scripts/`) writes to these directories automatically. Runtime data (`*.json`, `*.jsonl`) is gitignored; directories are tracked via `.gitkeep`.

## Knowledge Curator Memory Usage

The knowledge-curator agent uses the 4-tier memory system as follows:

| Tier | What the Curator Stores |
|---|---|
| Working | Current ingestion batch state, documents being processed |
| Episodic | Ingestion events, orphan repairs, benchmark scores over time |
| Semantic | Embedding quality baselines, document format patterns |
| Procedural | Learned chunking strategies per format, optimal re-embed timing |

The curator's episodic memory is critical for embedding drift detection — it compares current benchmark scores against historical entries to identify downward trends. If 3+ consecutive benchmarks show declining recall, the agent escalates to admin with a full re-embed recommendation.

## Current State
{injected at runtime: working memory summary, recent episodic entries, relevant procedural patterns}
