# GROOT Agent Engine — Architecture

The Agent Engine transforms GROOT from a stateless inference endpoint into a multi-agent autonomous platform with persistent identity, memory, and tool use.

## Architecture Overview

```
Agent Registration (existing)
  └── SOUL.md (identity)
  └── 4-Tier Memory
  │     ├── Working (per-task, TTL)
  │     ├── Episodic (timestamped events)
  │     ├── Semantic (learned facts + embeddings)
  │     └── Procedural (strategy patterns)
  └── Cognitive Loop
  │     └── PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE
  └── Tool Access (MCP gateway)
  └── Delegation (agent-to-agent)
```

## SOUL Identity

Each agent has a SOUL.md file that defines:
- **Persona** — who the agent is and how it communicates
- **Goals** — what the agent is trying to achieve
- **Constraints** — hard boundaries the agent must respect
- **Tools** — which MCP tools the agent can use (supports glob patterns)
- **Delegation Policy** — whether other agents can delegate to this agent

See [SOUL_FORMAT.md](SOUL_FORMAT.md) for the full format specification.

## 4-Tier Memory System

### Tier 1: Working Memory
Short-lived, per-task context with TTL. Auto-cleaned after task completion or expiration. Used for intermediate results within a cognitive loop run.

### Tier 2: Episodic Memory
Timestamped event records capturing what happened, when, and the outcome (success/failure/partial). Used for learning from past interactions.

### Tier 3: Semantic Memory
Learned facts with confidence scores and 384-dim embeddings for semantic similarity search. Facts are deduplicated and confidence is updated on re-learning.

### Tier 4: Procedural Memory
Strategy patterns with trigger conditions and action sequences. Tracks success rates and usage counts. Used to apply proven approaches to similar situations.

## Cognitive Loop

Every agent task runs through a 6-phase loop:

1. **PERCEIVE** — Parse the task, recall relevant memories from all 4 tiers, build situation awareness via BitNet inference
2. **PLAN** — Generate a structured JSON plan with steps, referencing available tools and past procedures
3. **ACT** — Execute each plan step: tool calls via MCP `dispatch_tool()` or reasoning via BitNet
4. **OBSERVE** — Evaluate results against plan expectations via BitNet
5. **REFLECT** — Extract lessons learned, identify new facts and strategy improvements via BitNet
6. **STORE** — Persist episodic memory (what happened), semantic memory (facts learned), procedural memory (strategies), clear working memory

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/{id}/soul` | Create/update agent SOUL |
| GET | `/agents/{id}/soul` | Get agent SOUL |
| POST | `/agents/{id}/run` | Submit a task (async) |
| GET | `/agents/{id}/tasks` | List agent tasks |
| GET | `/agents/{id}/tasks/{task_id}` | Get task details + execution trace |
| GET | `/agents/{id}/tasks/{task_id}/steps` | Get execution steps |
| POST | `/agents/{id}/tasks/{task_id}/cancel` | Cancel a running task |
| POST | `/agents/{id}/delegate` | Delegate subtask to another agent |

## Tool Access

Agents access platform capabilities through the MCP gateway. Available tools:
- `search_registry` / `get_project` / `list_projects` — contract registry
- `list_contract_sdks` / `get_contract_sdk` — contract SDKs
- `search_documents` / `compare_documents` — knowledge base
- `execute_script` / `list_scripts` — platform scripts
- `delegate_to_agent` — agent-to-agent delegation

Tool access is controlled per-agent via `AgentSoul.tools_allowed` with glob pattern support.

## 7-Layer Context Injection Stack

Every inference call (both public chat and agent tasks) passes through a context assembly pipeline that injects 7 layers into the system prompt. Each layer is tracked by a token budget tracker to stay within BitNet's 2,048-token context window.

**Implementation:** `api/services/agent_soul.py` → `build_agent_system_prompt()`

| Layer | Content | Budget | Source |
|---|---|---|---|
| 0 | Root `SOUL.md` — GROOT identity | 300 tokens | `context_loader.py` |
| 1 | Per-agent SOUL (persona, goals, constraints, tools) | 200 tokens | DB: `agent_souls` |
| 2 | Memory state (working memory + recent episodes) | 100 tokens | `agent_memory.py` |
| 3 | RAG context (knowledge chunks + contract SDKs) | 400 tokens | `rag.py` |
| 4 | Skills metadata (available skill summaries) | 50 tokens | `skills/*/SKILL.md` |
| 5 | `SAFETY.md` — hard constraints | 150 tokens | `context_loader.py` |
| 6 | Runtime (datetime, model, tokens remaining) | 50 tokens | Built at call time |

Total usable: 1,536 tokens (2,048 - 512 reserved for completion). Flexible layers (RAG, memory, skills) truncate first when over budget. Guaranteed layers (SOUL, SAFETY, agent SOUL, runtime) are never truncated.

When `agent_id=None`, the pipeline builds the default GROOT chat prompt (Layer 0 + Layers 3-6, no per-agent SOUL or operating protocol).

## Trigger Router

Events from 5 sources are automatically routed to agent tasks.

**Implementation:** `api/services/trigger_router.py`

| Event Pattern | Target Agent |
|---|---|
| `device.telemetry.*` | device-monitor |
| `chain.event.*` | contract-watcher |
| `knowledge.document.*` | knowledge-curator |
| `agent.task.completed` | orchestrator |
| `system.health.*` | maintenance |

Rate limited: max 1 auto-triggered task per agent per 10 seconds. Tasks run their cognitive loop in the background via `asyncio.create_task()`.

The trigger router subscribes to EventBus patterns on application startup (registered in `api/main.py` lifespan).

## Output Router

After the cognitive loop completes, results are routed to configured output targets.

**Implementation:** `api/services/output_router.py`

| Target | Description |
|---|---|
| `json_store` | Persist to task.result_json (default, always) |
| `response` | Return to API caller (default, always) |
| `memory` | Write to episodic/semantic memory (default, STORE phase) |
| `agent` | Forward result as a new task to another agent (delegation chaining) |
| `webhook` | Publish custom event to EventBus → webhook delivery |

Configure per-agent output targets in the agent registration's `config` JSON:
```json
{"output_targets": [{"type": "agent", "target_agent_id": "agent_xyz"}]}
```

## JSONL Episodic Logging

In addition to DB-backed episodic memory, events are written to JSONL files for external audit.

**Implementation:** `api/services/jsonl_logger.py`

Files written to `data/episodes/{YYYY-MM-DD}/`:
- `{agent_id}.jsonl` — Episodic events per agent
- `tasks.jsonl` — Completed task records
- `tool_calls.jsonl` — Tool call audit trail

JSONL logging is non-fatal — failures are silently caught and never block DB writes.

## Database Tables

All agent engine tables are in `public.db`:
- `agent_souls` — SOUL identity
- `agent_memory_working` — working memory (TTL)
- `agent_memory_episodic` — episodic memory
- `agent_memory_semantic` — semantic memory (with embeddings)
- `agent_memory_procedural` — procedural memory
- `agent_tasks` — task tracking
- `agent_delegations` — delegation chains
