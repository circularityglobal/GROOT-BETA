# AGENTS.md — Active Agent Registry

REFINET Cloud agents execute tasks through a 6-phase cognitive loop
(PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE).
Each agent is defined by a SOUL.md identity document.

## Available Agents

| Agent | Role | Trigger Types | Tools |
|---|---|---|---|
| groot-chat | **Wizard** — Conversational Q&A + on-chain ops | user, messenger | knowledge_search, contract_search, cag_query, cag_execute, cag_act, wizard_pipeline, compile_contract, deploy_contract |
| contract-analyst | Smart contract security review | user, webhook | search_registry, get_project, get_contract_sdk |
| knowledge-curator | Autonomous RAG/CAG intelligence maintenance — ingestion, orphan repair, CAG sync, drift detection | cron, webhook, heartbeat | knowledge.search, knowledge.upload, knowledge.documents, knowledge.reindex, knowledge.cag.sync, db.read.embeddings, smtp.send |
| platform-ops | Platform metrics, health monitoring, admin email alerts, autonomous agent pipeline | cron, user, heartbeat | execute_script:ops.*, execute_script:maintenance.*, health.*, db.read.*, smtp.send, agent.delegate |
| dapp-builder | DApp assembly from registry contracts | user | search_registry, get_project, get_contract_sdk |
| device-monitor | Telemetry analysis + anomaly alerting | webhook, heartbeat | search_documents, execute_script:analysis.* |
| contract-watcher | Autonomous on-chain intelligence — event interpretation, ABI security, activity monitoring, bridge correlation | onchain, webhook, cron | chain.listeners, chain.events, registry.search, registry.get_contract_sdk, knowledge.search, smtp.send |
| onboarding | New user guidance | webhook | search_documents, search_registry |
| maintenance | System cleanup + scheduled ops | cron, heartbeat | execute_script:ops.*, execute_script:maintenance.* |
| orchestrator | Task routing + multi-agent coordination | all | * (all tools) |

## Agent Selection Rule
The Trigger Router reads the event type to select the target agent.
Only the orchestrator can reassign tasks to different agents mid-run.
Manual task submission via POST /agents/{id}/run bypasses the trigger router.

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

## contract-watcher

**Role**: Autonomous on-chain intelligence — event interpretation, ABI security analysis, contract activity monitoring, and cross-chain bridge correlation.

**Trigger sources**: On-chain (event captured), webhook (new ABI upload), cron (5m events, 15m ABI scan, 4h activity, 12h bridges, weekly report).

**LLM runtime**: Zero-cost fallback chain — Claude Code CLI → Ollama → BitNet → Gemini Flash.

**Tools** (MCP gateway access):
- `chain.listeners` — Create/manage event listeners
- `chain.events` — Query and interpret captured events
- `registry.search` — Search contract registry
- `registry.get_contract_sdk` — Load ABI + SDK for context
- `knowledge.search` — Search contract documentation via RAG
- `smtp.send` — Email admin alerts

**Delegation policy**: `auto` — accepts from platform-ops and orchestrator. Can delegate to knowledge-curator for contract documentation enrichment. Max depth: 3.

**Email alert categories**: ABI_SECURITY, EVENT_ANOMALY, ACTIVITY_ALERT, BRIDGE_ALERT, WEEKLY_REPORT.

**Dangerous pattern detection**: delegatecall, selfdestruct, tx.origin, unchecked call, infinite approval, inline assembly, proxy patterns, ownership transfer.

**Key files**:
- `skills/refinet-contract-watcher/SKILL.md` — Full operational manual
- `skills/refinet-contract-watcher/scripts/contract_scan.py` — ABI scanner
- `skills/refinet-contract-watcher/references/chain-api.md` — Chain API reference
- `skills/refinet-contract-watcher/references/registry-api.md` — Registry API reference
- `configs/contract-watcher-cron.yaml` — Cron schedule
- `.github/workflows/contract-watcher.yml` — GitHub Actions runner

## Delegation Policies
- **auto**: Accept and execute delegated tasks immediately
- **approve**: Queue delegated tasks for owner approval before execution
- **none**: Reject all delegation requests
