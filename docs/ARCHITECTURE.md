# REFINET Cloud — System Architecture

Technical reference for how all subsystems connect.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TRIGGER SOURCES                              │
│  Heartbeat │ Cron │ Webhook │ Chain Listener │ Messenger Bridge      │
└──────┬──────┴──┬───┴────┬────┴───────┬────────┴──────┬──────────────┘
       └─────────┴────────┴───────────┴────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   TRIGGER ROUTER    │  api/services/trigger_router.py
                    │   Event → Agent     │  Rate limited: 10s per agent
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  CONTEXT ASSEMBLY   │  api/services/agent_soul.py
                    │  8-Layer Injection  │  + token_budget.py
                    │  Stack (1536 tokens)│  + context_loader.py
                    │  SOUL→Agent→Memory  │  + contract_brain.py (CAG)
                    │  →RAG→CAG→Skills    │
                    │  →Safety→Runtime    │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  MODEL GATEWAY      │  api/services/gateway.py
                    │  BitNet → Gemini →  │  + providers/{bitnet,gemini,
                    │  Ollama → LMStudio  │    ollama,lmstudio,openrouter}.py
                    │  → OpenRouter       │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  COGNITIVE LOOP     │  api/services/agent_engine.py
                    │  PERCEIVE → PLAN →  │  6 phases, max 5 iterations
                    │  ACT → OBSERVE →    │  Tool calls via MCP gateway
                    │  REFLECT → STORE    │  CAG tools: query/execute/act
                    │                     │  Pipeline: wizard_pipeline
                    │  GROOT = Sole Wizard│  deploy via GROOT wallet (SSS)
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  OUTPUT ROUTER      │  api/services/output_router.py
                    │  → DB (always)      │  → Webhook delivery
                    │  → Agent chaining   │  → EventBus broadcast
                    │  → Memory persist   │  → JSONL audit trail
                    └──────────────────────┘
```

---

## 1. 7-Layer Context Injection Stack

Every inference call assembles a system prompt from 7 layers, each tracked by the token budget tracker.

**Files:** `api/services/agent_soul.py` → `build_agent_system_prompt()`, `api/services/token_budget.py`, `api/services/context_loader.py`

| Layer | Source | Budget | Priority | Description |
|---|---|---|---|---|
| 0 | `SOUL.md` (root) | 300 | Guaranteed | GROOT's core identity — always loaded |
| 1 | Agent SOUL (DB) | 200 | Guaranteed | Per-agent persona, goals, constraints, tools |
| 2 | Memory state | 100 | Flexible | Working memory summary + recent episodes |
| 3 | RAG context | 400 | Flexible | Knowledge base chunks + contract SDKs |
| 4 | Skills metadata | 50 | Flexible | Available skill summaries from `skills/` |
| 5 | `SAFETY.md` (root) | 150 | Guaranteed | Hard constraints — always loaded |
| 6 | Runtime context | 50 | Guaranteed | Datetime, model, tokens remaining |

**Budget:** 1,536 usable tokens (2,048 context window minus 512 reserved for completion). Flexible layers truncate when over budget (RAG first, then memory, then skills). Guaranteed layers are never truncated.

**Token estimation:** 4 characters per token heuristic (matches `rag.py` chunking).

**Caching:** Control documents (`SOUL.md`, `SAFETY.md`) are cached for 60 seconds via `context_loader.py` to avoid re-reading from disk on every call.

**Dual mode:** When `agent_id=None`, the pipeline builds the default GROOT chat prompt (root SOUL only, no per-agent SOUL). This is used by the public `/v1/chat/completions` endpoint and messenger bridges.

---

## 2. Trigger Router

Maps events from 5 sources to agent tasks. Subscribes to the EventBus on startup.

**File:** `api/services/trigger_router.py`

### Event → Agent Mapping

| Event Pattern | Target Agent | Source |
|---|---|---|
| `device.telemetry.*` | device-monitor | IoT telemetry |
| `device.status.*` | device-monitor | Device status changes |
| `chain.event.*` | contract-watcher | On-chain events |
| `chain.watcher.*` | contract-watcher | Watcher lifecycle |
| `knowledge.document.*` | knowledge-curator | Document uploads |
| `agent.task.completed` | orchestrator | Task completion |
| `system.health.*` | maintenance | Health alerts |

### Rate Limiting

Max 1 auto-triggered task per agent archetype per 10 seconds. Prevents event storms from flooding the agent engine.

### Task Creation Flow

1. Event published to EventBus → trigger router handler fires
2. Match event type against `TRIGGER_MAP` using fnmatch patterns
3. Find a registered agent with matching archetype name
4. Create `AgentTask` in DB
5. Run `AgentCognitiveLoop` in background via `asyncio.create_task()`

---

## 3. Output Router

Routes completed task results to configured targets.

**File:** `api/services/output_router.py`

### Output Targets

| Target | Description | Implementation |
|---|---|---|
| `json_store` | Persist to task.result_json | Default (always done) |
| `response` | Return to API caller | Default (always done) |
| `memory` | Write to episodic/semantic memory | Default (STORE phase) |
| `agent` | Chain result to another agent | Creates delegation task |
| `webhook` | Publish custom event to EventBus | External webhook delivery |

### Agent Chaining

Configure in the agent registration's `config` JSON:
```json
{
  "output_targets": [
    {"type": "agent", "target_agent_id": "agent_xyz", "description": "Forward analysis to..."}
  ]
}
```

---

## 4. Multi-Provider Inference Gateway

**Files:** `api/services/gateway.py`, `api/services/providers/`

### Fallback Chain

```
bitnet → gemini → ollama → lmstudio → openrouter
```

Configured via `PROVIDER_FALLBACK_CHAIN` env var. Each provider has an independent health check. If the current provider fails, the gateway automatically tries the next.

### Provider Registry

| Provider | Type | Context Window | Cost |
|---|---|---|---|
| BitNet b1.58 2B4T | Local (CPU) | 2,048 | Free |
| Gemini 2.0/2.5 Flash | Cloud API | 1,048,576 | Free tier |
| Gemini 2.5 Pro | Cloud API | 1,048,576 | Free tier (limited) |
| Ollama | Local server | Varies | Free |
| LM Studio | Local server | Varies | Free |
| OpenRouter | Cloud proxy | Varies | Pay-per-use |

### BYOK (Bring Your Own Key)

Users can store their own API keys for any OpenAI-compatible provider via `POST /provider-keys/{provider}`. Keys are encrypted with AES-256-GCM and scoped to the user.

---

## 5. Event Bus

In-process pub/sub with wildcard pattern matching. Zero external dependencies.

**File:** `api/services/event_bus.py`

### Registered Patterns (from `api/main.py` lifespan)

| Pattern | Handlers |
|---|---|
| `registry.*` | WebSocket broadcast, webhook delivery |
| `messaging.*` | WebSocket broadcast, webhook delivery |
| `system.*` | WebSocket broadcast, webhook delivery |
| `knowledge.*` | WebSocket broadcast, webhook delivery, knowledge refresh |
| `registry.sdk.*` | SDK→Knowledge bridge (auto-ingest to RAG) |
| `chain.*` | WebSocket broadcast, webhook delivery |
| `agent.*` | WebSocket broadcast, webhook delivery |
| `device.*`, `chain.*`, `knowledge.*`, `system.*`, `agent.*` | Trigger router (event→agent tasks) |

---

## 6. Scheduler

Lightweight cron/interval task scheduler. DB-backed, 10-second tick, zero external dependencies.

**File:** `api/services/scheduler.py`

### Default Tasks (13)

| Task | Interval | Handler |
|---|---|---|
| health_monitor | 60s | Check BitNet, DB, SMTP health |
| p2p_cleanup | 60s | Remove stale P2P peers |
| auth_cleanup | 3600s | Expire SIWE nonces + refresh tokens |
| agent_memory_cleanup | 300s | Clear expired working memory |
| api_counter_reset | 86400s | Reset daily API key counters |
| telemetry_prune | 86400s | Remove telemetry >30 days |
| knowledge_sync | 300s | SDK ↔ Knowledge reconciliation |
| knowledge_gc | 3600s | Clean orphaned chunks/docs |
| chain_event_indexer | 60s | Index chain events into knowledge |
| data_ttl | 3600s | Enforce 4-tier data retention |
| capability_index | 600s | Build contract capability map |
| provider_health_check | 60s | Check model provider availability |
| provider_model_sync | 300s | Sync available models from providers |

---

## 7. Memory System

4-tier memory with DB storage and JSONL audit trail.

**Files:** `api/services/agent_memory.py`, `api/services/jsonl_logger.py`

| Tier | Table | TTL | Access | JSONL |
|---|---|---|---|---|
| Working | agent_memory_working | Per-task | Read/write during task | No |
| Episodic | agent_memory_episodic | 90 days | Append in STORE, query in PERCEIVE | Yes |
| Semantic | agent_memory_semantic | Permanent | Learn in STORE, search in PERCEIVE | No |
| Procedural | agent_memory_procedural | Permanent | Update in STORE, match in PLAN | No |

### JSONL Audit Trail

Episodic events are written to both DB and JSONL files at `data/episodes/{YYYY-MM-DD}/{agent_id}.jsonl`. Task results go to `tasks.jsonl`, tool calls to `tool_calls.jsonl`.

---

## 8. Configuration Hierarchy

**Files:** `api/config.py`, `configs/default.yaml`, `configs/production.yaml`

### Merge Order (lowest → highest precedence)

```
configs/default.yaml          ← Base settings
  ↓ merged with
configs/production.yaml       ← If REFINET_ENV=production
  ↓ overridden by
Environment variables (.env)  ← Highest precedence (secrets)
```

### Access

```python
from api.config import get_yaml_value
model = get_yaml_value("groot.model", "bitnet-b1.58-2b")
max_iter = get_yaml_value("orchestration.max_iterations", 5)
```

---

## 9. Data Classification

| Tier | Owner | Readable By | TTL | Example |
|---|---|---|---|---|
| Private | User | Owner only | Permanent | Source code, private ABIs, configs |
| Short-term | System | Platform agents | 7-90 days | Telemetry, sessions, nonces |
| Long-term | Platform | Agents + admin | Permanent | Episodic logs, procedural patterns |
| Public | User (toggled) | Everyone + GROOT + MCP | Permanent | Public contract SDKs, knowledge docs |

**Key rule:** GROOT and MCP only see public-tier data. Private source code is never accessible to the AI.

---

## 10. Database Architecture

Two SQLite databases with WAL mode for concurrent reads:

**public.db** — User-facing data (50+ tables)
- Users, API keys, devices, agents, telemetry
- Webhooks, usage records, SIWE nonces, refresh tokens
- Contract repos, SDKs, registry projects
- Chain watchers, events, DApp listings, app store
- Agent souls, 4 memory tables, tasks, delegations

**internal.db** — Admin-only (never exposed via API)
- Server secrets (AES-256-GCM encrypted)
- Role assignments, admin audit log (append-only)
- MCP server registry, system config
- Scheduled tasks, health check logs
- Sandbox environments, wallet shares
