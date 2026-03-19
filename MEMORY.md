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

## Current State
{injected at runtime: working memory summary, recent episodic entries, relevant procedural patterns}
