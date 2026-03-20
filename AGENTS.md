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
| repo-migrator | GitHub-to-REFINET contract migration | user, webhook, cron | mcp.github.*, registry.*, repo.*, knowledge.cag.sync, contract_watcher.scan_abi, smtp.send |
| security-sentinel | Autonomous defense — auth anomaly, rate abuse, TLS, wallet forensics | cron, heartbeat, user | db.read.audit_log, db.read.rate_limits, tls.check, smtp.send |
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

## repo-migrator

**Role**: Autonomous GitHub-to-REFINET smart contract migration — repo fetching, multi-chain compilation/parsing, ABI extraction, access control classification, SDK generation, and registry import.

**Trigger sources**: User request (provides GitHub URL to GROOT), webhook (migration API endpoint), cron (daily retry, weekly stats), GitHub Actions (manual dispatch).

**LLM runtime**: Zero-cost fallback chain for non-EVM parsing — Claude Code CLI → Ollama → BitNet → Gemini Flash.

**Supported ecosystems**: Solidity (EVM), Vyper (EVM), Anchor (Solana), Move (Sui/Aptos), Clarity (Bitcoin/Stacks), TEAL (Algorand), XRPL Hooks, Hedera HTS, Soroban (Stellar/XLM).

**Tools** (MCP gateway access):
- `mcp.github.*` — GitHub MCP server (if connected)
- `registry.create_project` — Create registry project for user
- `registry.upload_abi` — Upload parsed ABI
- `repo.create_contract` — Store in user's GROOT Brain
- `knowledge.cag.sync` — Trigger CAG index update (delegates to knowledge-curator)
- `contract_watcher.scan_abi` — Trigger security scan (delegates to contract-watcher)
- `smtp.send` — Email migration reports

**Delegation policy**: `auto` — delegates to knowledge-curator (CAG sync) and contract-watcher (ABI security scan) after import. Accepts tasks from orchestrator and groot-chat. Max depth: 3.

**Key files**:
- `skills/refinet-repo-migrator/SKILL.md` — Full migration manual
- `skills/refinet-repo-migrator/scripts/repo_migrate.py` — Migration script
- `skills/refinet-repo-migrator/references/github-api.md` — GitHub API reference
- `skills/refinet-repo-migrator/references/multi-chain-parsers.md` — Parser reference
- `configs/repo-migrator-cron.yaml` — Cron schedule
- `.github/workflows/repo-migrator.yml` — GitHub Actions runner

## platform-ops

**Role**: Autonomous infrastructure oversight — platform health monitoring, agent pipeline orchestration, admin email alerts, and system maintenance.

**Trigger sources**: Heartbeat (60s), cron (5m inference check, 15m security audit, 1h memory cleanup, daily summary, weekly audit), user request, webhook.

**LLM runtime**: Zero-cost fallback chain — Claude Code CLI → Ollama → BitNet → Gemini Flash. Orchestrated by `scripts/run_agent.sh` with 7-layer context injection.

**Tools** (MCP gateway access):
- `execute_script:ops.*` — Run operational scripts
- `execute_script:maintenance.*` — Run maintenance scripts
- `health.*` — Health check endpoints (API, BitNet, DB, SMTP, disk, memory)
- `db.read.*` — Read-only database access for monitoring
- `smtp.send` — Email admin alerts (8 categories: HEALTH, SECURITY, AGENT, DEPLOY, CHAIN, REGISTRY, KNOWLEDGE, MAINTENANCE)
- `agent.delegate` — Delegate tasks to other agents

**Delegation policy**: `auto` — orchestrates all other agents. Can delegate to knowledge-curator, contract-watcher, repo-migrator, and security-sentinel. Max depth: 3.

**Key files**:
- `skills/refinet-platform-ops/SKILL.md` — Full operational manual (620 lines, 8 parts)
- `skills/refinet-platform-ops/scripts/health_check.py` — Comprehensive health checker
- `skills/refinet-platform-ops/scripts/run_agent.sh` — Zero-cost agent pipeline runner
- `skills/refinet-platform-ops/references/api-endpoints.md` — API endpoint map
- `skills/refinet-platform-ops/references/agent-engine.md` — Agent engine architecture
- `skills/refinet-platform-ops/references/email-templates.md` — HTML email templates
- `configs/platform-ops-cron.yaml` — Cron schedule
- `.github/workflows/platform-ops.yml` — GitHub Actions runner

## security-sentinel

**Role**: Autonomous defense system — authentication anomaly detection, rate limit intelligence, TLS certificate monitoring, SIWE wallet forensics, and BYOK Security Gate validation.

**Trigger sources**: Cron (15m auth scan, 1h rate analysis, daily briefing, weekly TLS/gate/forensics), heartbeat, user request.

**LLM runtime**: Zero-cost fallback chain — Claude Code CLI → Ollama → BitNet → Gemini Flash.

**Tools** (MCP gateway access):
- `db.read.audit_log` — Read append-only audit log (SIWE, login, TOTP, JWT, API key events)
- `db.read.rate_limits` — Read rate limit hit records
- `tls.check` — Check TLS certificate expiry for configured domains
- `smtp.send` — Email security alerts and briefings

**Delegation policy**: `auto` — accepts tasks from platform-ops and orchestrator. Reports to admin only — never blocks, bans, or modifies. All enforcement requires explicit admin approval. Max depth: 2.

**Alert categories**: AUTH_ANOMALY, RATE_ABUSE, TLS_EXPIRY, WALLET_FLAG, GATE_FAIL, BRIEFING.

**Detection rules**: SIWE brute force (5+ fails/IP/hour), TOTP brute force (3+ fails/user/30min), expired JWT reuse (3+ attempts), credential stuffing (3+ users from same IP), API key abuse (10+ rate hits), admin access anomaly.

**Key files**:
- `skills/refinet-security-sentinel/SKILL.md` — Full defense manual (178 lines, 7 parts)
- `skills/refinet-security-sentinel/scripts/security_scan.py` — Auth anomaly + rate limit + TLS scanner
- `skills/refinet-security-sentinel/references/auth-api.md` — Auth endpoint and audit log reference
- `skills/refinet-security-sentinel/references/threat-patterns.md` — Threat pattern catalog with SQL queries
- `configs/security-sentinel-cron.yaml` — Cron schedule
- `.github/workflows/security-sentinel.yml` — GitHub Actions runner

## Delegation Policies
- **auto**: Accept and execute delegated tasks immediately
- **approve**: Queue delegated tasks for owner approval before execution
- **none**: Reject all delegation requests
