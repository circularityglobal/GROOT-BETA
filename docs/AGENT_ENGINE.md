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

## Database Tables

All agent engine tables are in `public.db`:
- `agent_souls` — SOUL identity
- `agent_memory_working` — working memory (TTL)
- `agent_memory_episodic` — episodic memory
- `agent_memory_semantic` — semantic memory (with embeddings)
- `agent_memory_procedural` — procedural memory
- `agent_tasks` — task tracking
- `agent_delegations` — delegation chains
