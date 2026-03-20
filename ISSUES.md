# REFINET Cloud — Current Status & Known Issues

Last updated: March 2026

---

## Platform Status

### Test Suite

```
Total test cases: 212
Passed:           207
Failed:             5 (pre-existing, non-critical)
Test files:        10
```

**Passing test suites:** agent_engine (18/18), registry (96 tests), brain, admin, ABI parser, webhooks (7/7), devices, document ingestion.

**Known test failures (5):**
- `test_auth.py` (3 failures): Tests reference `/auth/register` endpoint path that was renamed during SIWE-first refactor. Auth system works correctly — tests need path update.
- `test_inference.py` (2 failures): Mock target `api.routes.inference.call_bitnet` no longer matches actual import path after multi-provider gateway refactor. Inference works correctly — tests need mock path update.

### Architecture (GROOT Agent PRD v1.0)

All 9 architecture gaps identified in the agent architecture audit have been closed:

| Gap | Status | Implementation |
|---|---|---|
| Root-level control documents (SOUL, SAFETY, MEMORY, HEARTBEAT, AGENTS) | CLOSED | 5 files at project root |
| 7-layer context injection stack | CLOSED | `agent_soul.py` → `build_agent_system_prompt()` |
| Token budget management (BitNet 2048-token window) | CLOSED | `token_budget.py` |
| Trigger router (event → agent task routing) | CLOSED | `trigger_router.py` + pipeline/broker patterns |
| Output router (multi-target result routing) | CLOSED | `output_router.py` + wired into `agent_engine.py` |
| Missing agent archetypes (5 of 10) | CLOSED | All 10 in `docs/AGENTS.md` |
| Configuration YAML hierarchy | CLOSED | `configs/default.yaml` + `production.yaml` |
| Skills directory | CLOSED | `skills/` with 3 skill definitions |
| JSONL file-based logging | CLOSED | `jsonl_logger.py` + wired into `agent_memory.py` |

### Wizard/Broker PRD Gaps (All Closed)

| Gap | Status | Implementation |
|---|---|---|
| DAG orchestrator for worker pipeline | CLOSED | `dag_orchestrator.py` — 4 pipeline templates (compile_test, deploy, full, **wizard**) |
| Wizard workers (compile, test, deploy) | CLOSED | `wizard_workers.py` — **9 workers** (compile, test, parse, RBAC, deploy, verify, transfer, frontend, appstore) |
| GROOT as sole Wizard | CLOSED | `deploy_worker` + `transfer_ownership_worker` use GROOT wallet exclusively |
| PendingAction approval flow | CLOSED | `PendingAction` model + **master_admin** approve/reject endpoints |
| RBAC worker for permission enforcement | CLOSED | `rbac_check_worker` with tier-based + admin gates |
| Deployment tracking + ownership transfer | CLOSED | `DeploymentRecord` model + `ownership.py` |
| CAG three access modes (Query/Execute/Act) | CLOSED | `contract_brain.py` — cag_query, cag_execute, cag_act |
| Dynamic chain registry | CLOSED | `SupportedChain` model + `chain_registry.py` + chainlist.org import |
| Multi-chain contract deployments | CLOSED | `ContractDeployment` model + flat ABI folder structure |
| Master admin role | CLOSED | `master_admin` role gates all GROOT wallet + Tier 2 actions |
| Broker session management | CLOSED | `BrokerSession` model + `broker.py` service |
| Fee schedule + pricing | CLOSED | `FeeSchedule` model + `payment_service.py` |
| Three-token payment (CIFI/USDC/REFI) | CLOSED | `PaymentRecord` with token tracking |
| Revenue split execution | CLOSED | `RevenueSplit` model + `execute_revenue_split()` |
| Tag taxonomy for contract discovery | CLOSED | `tag_taxonomy.py` — 11 categories, 95 subcategories |
| DApp validation (npm + tsc) | CLOSED | `dapp_validator.py` + self-repair loop |
| Block explorer ABI fetch | CLOSED | `GET /explore/fetch-abi` + frontend "Import from Explorer" |
| Contract testing UI | CLOSED | "Test" button on view/pure functions in repo page |
| Performance indexes | CLOSED | Migration 015 — 15+ indexes + FTS5 for contract search |
| Frontend wizard pages | CLOSED | `/pipeline`, `/deployments`, `/dapp`, admin Networks/Wallet/Actions panels |
| Missing execution scripts (~14) | CLOSED | 40+ total scripts |
| XMTP integration | CLOSED (stub) | `xmtp.py` — protocol wrapper with internal fallback |

---

## Known Issues

### K1. Python 3.9 Compatibility — RESOLVED

- **File:** `api/auth/enforce.py`
- **Issue:** Used Python 3.10+ union syntax (`str | None`)
- **Fix applied:** Changed to `Optional[str]` and `Tuple[str, User]` with proper imports
- **Status:** RESOLVED — all tests now run on Python 3.9+

### K2. SAFETY.md Injection in Messenger Bridge

- **File:** `api/services/messenger_bridge.py`
- **Issue:** Telegram/WhatsApp bridges call `build_groot_system_prompt()` which uses the 7-layer context assembly. Not independently verified with a live bot.
- **Impact:** Low — safety constraints should be injected via the context assembly pipeline.
- **Status:** Needs integration testing with live Telegram bot

### K3. XMTP Not Live

- **File:** `api/services/xmtp.py`
- **Issue:** XMTP SDK not yet integrated. The `xmtp.py` wrapper falls back to internal wallet-to-wallet messaging.
- **Impact:** Broker sessions use internal messaging instead of XMTP encrypted channels
- **Status:** Stub in place — replace with XMTP SDK when infra is ready

---

## Resolved Issues (Historical)

### SIWE Communication Infrastructure (Phase 1-4)

All 14 issues from the SIWE implementation phase were resolved. 52/52 functional tests pass. See git history for details:
- H1-H4: URI format, N+1 queries, error handling (all resolved)
- M1-M6: Code quality, validation, edge cases (all resolved)
- L1-L10: Performance, cleanup, hardening (all resolved)
