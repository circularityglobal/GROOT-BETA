# REFINET Agent Engine Architecture Reference

## SOUL.md — Agent Identity Format

Every agent has a SOUL.md that defines its persistent identity:

```yaml
# Required fields
name: platform-ops
version: "1.0"
role: "Platform operations and monitoring agent"
owner: circularityglobal

# Goals (what this agent optimizes for)
goals:
  - Keep all REFINET Cloud subsystems healthy and responsive
  - Alert admin immediately on security anomalies or health failures
  - Maintain clean episodic memory and audit trails
  - Minimize platform downtime through proactive monitoring

# Constraints (hard limits — inherited from SAFETY.md plus agent-specific)
constraints:
  - Never execute financial transactions without user confirmation
  - Never expose secrets, keys, or internal architecture
  - Max delegation depth: 3
  - Max concurrent tasks: 5
  - Token budget per task: 4096

# Tools (MCP gateway access — glob patterns)
tools:
  allow:
    - "health.*"           # All health check tools
    - "db.read.*"          # Database reads (no writes)
    - "smtp.send"          # Email sending
    - "script.run.*"       # Operational script execution
    - "agent.delegate"     # Delegate to other agents
  deny:
    - "db.write.users"     # Cannot modify user records
    - "keys.*"             # Cannot access key management
    - "auth.escalate"      # Cannot change auth levels

# Delegation policy
delegation:
  policy: auto            # none | approve | auto
  allowed_targets:
    - maintenance
    - knowledge-curator
    - contract-watcher
  max_depth: 3
```

## 6-Phase Cognitive Loop

```
PERCEIVE  → Assemble context from 7 injection layers
PLAN      → LLM reasons about task, generates structured plan
ACT       → Execute tool calls via MCP gateway
OBSERVE   → Capture results, update working memory
REFLECT   → Assess outcomes, identify learnings
STORE     → Write to episodic (events), semantic (facts), procedural (patterns)
```

## 7-Layer Context Injection Stack

Injected in this order, with token budget tracking:

| Layer | Source | Priority | Max Tokens |
|---|---|---|---|
| 1. SOUL | `SOUL.md` | Always | 500 |
| 2. Agent Config | `agents/{name}.yaml` | Always | 300 |
| 3. Memory | Working + relevant episodic | Always | 1000 |
| 4. RAG | Knowledge base search results | If relevant | 1500 |
| 5. Skills | Matched skill instructions | If triggered | 800 |
| 6. Safety | `SAFETY.md` hard constraints | Always | 200 |
| 7. Runtime | Task description + user context | Always | 500 |

Total budget: ~4800 tokens for context, leaving room for generation.

## 4-Tier Memory System

| Tier | What | Storage | TTL |
|---|---|---|---|
| Working | Current task scratch state | JSON in memory | Per-run |
| Episodic | What happened in past runs | JSONL files + DB | 90 days |
| Semantic | Distilled facts + embeddings | Vector store + DB | Permanent |
| Procedural | Learned tool use patterns | patterns.json | Permanent |

## Trigger Router

Routes events to the right agent:

| Trigger Source | Example | Routes To |
|---|---|---|
| Heartbeat | 60s pulse | platform-ops |
| Cron | `0 6 * * *` | Configured agent |
| Webhook | GitHub push, Stripe event | Configured handler |
| Chain | Contract event detected | contract-watcher |
| Messenger | User sends command | groot-chat |

## Output Router

Routes agent results to destinations:

| Target | When |
|---|---|
| DB | Always — audit log |
| HTTP Response | If user-facing task |
| Memory | Always — working + episodic |
| Agent Chain | If delegation in plan |
| Webhook | If external notification configured |
| Email | If admin alert triggered |
