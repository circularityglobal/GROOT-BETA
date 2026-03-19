# AGENTS.md — Active Agent Registry

REFINET Cloud agents execute tasks through a 6-phase cognitive loop
(PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE).
Each agent is defined by a SOUL.md identity document.

## Available Agents

| Agent | Role | Trigger Types | Tools |
|---|---|---|---|
| groot-chat | Conversational Q&A with RAG | user, messenger | knowledge_search, contract_search |
| contract-analyst | Smart contract security review | user, webhook | search_registry, get_project, get_contract_sdk |
| knowledge-curator | Knowledge base maintenance | cron, webhook | search_documents, compare_documents, get_document_tags |
| platform-ops | Platform metrics + health monitoring | cron, user | execute_script:ops.*, execute_script:maintenance.* |
| dapp-builder | DApp assembly from registry contracts | user | search_registry, get_project, get_contract_sdk |
| device-monitor | Telemetry analysis + anomaly alerting | webhook, heartbeat | search_documents, execute_script:analysis.* |
| contract-watcher | On-chain event interpretation | onchain, webhook | search_registry, get_contract_sdk, search_documents |
| onboarding | New user guidance | webhook | search_documents, search_registry |
| maintenance | System cleanup + scheduled ops | cron, heartbeat | execute_script:ops.*, execute_script:maintenance.* |
| orchestrator | Task routing + multi-agent coordination | all | * (all tools) |

## Agent Selection Rule
The Trigger Router reads the event type to select the target agent.
Only the orchestrator can reassign tasks to different agents mid-run.
Manual task submission via POST /agents/{id}/run bypasses the trigger router.

## Delegation Policies
- **auto**: Accept and execute delegated tasks immediately
- **approve**: Queue delegated tasks for owner approval before execution
- **none**: Reject all delegation requests
