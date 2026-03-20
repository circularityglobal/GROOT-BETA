# Changelog

All notable changes to REFINET Cloud are documented in this file.

---

## [3.2.0] — 2026-03-20

### Added — GROOT as Sole Wizard
- GROOT is now the **sole Wizard** — all contract deployments and on-chain actions go through GROOT's SSS-secured wallet
- `deploy_worker` and `transfer_ownership_worker` rewritten to use `sign_transaction_with_groot_wallet()` exclusively
- Users never need gas — GROOT deploys on their behalf, then transfers ownership
- `scripts/init_groot_wallet.py` — one-time wallet initialization with offline share backup

### Added — Master Admin Role
- New `master_admin` role with exclusive control over GROOT's wallet, Tier 2 approvals, and chain management
- `_require_master_admin()` gate on all wallet, approval, and deployment endpoints
- Admin secret header (`X-Admin-Secret`) cannot bypass master_admin — JWT authentication required
- All admin secret usage audited in `admin_audit_log`

### Added — CAG Three Access Modes
- **Query** (`cag_query`) — search public SDKs for contract information (autonomous)
- **Execute** (`cag_execute`) — call view/pure functions on-chain (autonomous, no gas)
- **Act** (`cag_act`) — request state-changing transactions (creates PendingAction for master_admin approval)
- CAG context injected as Layer 3.5 in GROOT's 8-layer system prompt
- Agent engine can invoke `cag_query`, `cag_execute`, `cag_act` as tool actions
- `POST /explore/cag/execute` and `POST /explore/cag/act` API endpoints

### Added — Dynamic Chain Registry
- `SupportedChain` model — database-backed chain configuration replaces 7+ hardcoded dicts
- `ChainRegistry` service — cached, single source of truth with 60s TTL
- `POST /admin/chains/import` — import any EVM chain from chainlist.org by chain_id
- `GET/POST/PUT/DELETE /admin/chains` — full CRUD for master_admin
- 6 default chains seeded on startup (Ethereum, Polygon, Arbitrum, Optimism, Base, Sepolia)
- All services (`wizard_workers`, `chain_listener`, `explore`) now use registry with hardcoded fallback

### Added — Multi-Chain Contract Deployments
- `ContractDeployment` model — maps one contract to N chain+address pairs
- ABIs are now chain-agnostic: `data/contracts/abis/USDC.json` with `"deployments": [{chain_id, address}, ...]`
- Flat folder structure: `data/contracts/abis/` (no chain subfolders)
- `scripts/import_contracts.py` handles both legacy single-chain and new multi-chain format
- `contract_brain.py` resolves addresses via `ContractDeployment` table for cross-chain lookups

### Added — Wizard Pipeline (Full 8-Stage DAG)
- New `wizard` pipeline template: compile → test → parse → RBAC → deploy → reparse → frontend → appstore
- **Parallel execution**: frontend generation runs alongside RBAC/deploy (both depend on parse)
- `parse_worker` — wraps abi_parser + sdk_generator as pipeline step
- `frontend_worker` — generates 3-page React DApp from SDK
- `appstore_worker` — submits to App Store review pipeline
- `POST /pipeline/start` endpoint for full source-to-DApp pipeline
- Hardhat compilation support with solc fallback

### Added — Frontend Pages
- `/pipeline` — start wizard pipeline, monitor DAG steps with live refresh, cancel
- `/deployments` — view GROOT-deployed contracts, transfer ownership, explorer links
- `/dapp` — browse templates, build DApps, validate, download ZIP
- Admin "Networks" tab — list chains, toggle status, import from chainlist.org
- Admin "GROOT Wallet" panel — address, balance, transactions
- Admin "Pending Actions" panel — approve/reject Tier 2 actions
- Sidebar navigation updated with Wizard, Deployments, DApp Factory links
- All chain selectors now dynamic (fetch from `/explore/chains` API)

### Added — Worker Endpoints
- `POST /workers/hardhat/compile`, `/hardhat/test`, `/parse` — Tier 1 (any user)
- `POST /workers/deploy`, `/verify`, `/rbac/check` — Tier 2 (master_admin only)
- `POST /workers/frontend/generate` — Tier 1 (any user)

### Added — Block Explorer Integration
- `GET /explore/fetch-abi?address=...&chain=...` — fetch verified ABI from Etherscan/Basescan/etc.
- Frontend "Import from Explorer" button on repo page
- Supports 6 explorer APIs (Etherscan, Basescan, Polygonscan, Arbiscan, Optimistic Etherscan, Sepolia)

### Added — Performance Indexes
- Migration 015: 15+ indexes on contract_repos, contract_functions, knowledge_documents
- FTS5 virtual tables for contract name/description/tags search
- FTS5 virtual table for function_name/signature search
- `search_public_sdks` optimized from N+1 queries to single JOIN (1.4ms avg at 200 contracts)

### Added — Contract Testing UI
- "Test" button on view/pure functions in repo page
- Inline args input + Call button → calls `cag_execute` → shows result
- Gas balance check before GROOT deployment attempts

### Fixed
- `sdk_definitions.user_id` NOT NULL constraint in parse_worker
- `assemble_dapp` parameter names (template_name, contract_name)
- `generate_dapp_zip` signature and return type
- `appstore_worker` uses `publish_app` instead of nonexistent `create_listing`
- SDK field name mismatch (`mutability` vs `state_mutability`) in cag_execute/cag_act
- solc ABI parsing handles both list and string ABI formats
- All 12 missing model exports added to `__init__.py`
- Duplicate unreachable return statement in admin `_require_master_admin`
- Token budget includes "cag" layer (200 tokens, flexible)
- `sources` list in agent_soul safely initialized

---

## [3.1.0] — 2026-03-19

### Added — Wizard Pipeline (DAG Orchestrator)
- `PipelineRun`, `PipelineStep`, `PendingAction` models for tracking multi-step DAG execution
- `dag_orchestrator.py` — pipeline coordinator with 3 templates: `compile_test`, `deploy`, `full`
- `wizard_workers.py` — 6 deterministic workers: compile (solc/registry), test (ABI+bytecode validation), RBAC check (tier-based + admin gates), deploy (SSS key reconstruction + web3 broadcast), verify (block explorer API), transfer ownership
- `POST /pipeline/compile-test` and `POST /pipeline/deploy` endpoints
- Admin approval flow: `GET/POST /pipeline/admin/pending-actions/{id}/approve|reject`
- Agent engine integration: agents can dispatch `deploy_contract` and `compile_contract` tool actions

### Added — Contract Deployment & Ownership Tracking
- `DeploymentRecord` model for tracking every contract GROOT deploys
- `ownership.py` service — record deployments, initiate transfers, check on-chain owner
- `GET /deployments/`, `POST /deployments/{id}/transfer`, `GET /deployments/{id}/verify-owner`

### Added — Payment & Revenue System
- `FeeSchedule`, `PaymentRecord`, `Subscription`, `RevenueSplit` models
- `payment_service.py` — fee calculation with tier discounts, payment recording, subscription management, revenue split execution
- Percentage validation on revenue splits (must sum to 100%)
- `GET /payments/fee-schedule`, `POST /payments/checkout`, `GET /payments/history`
- `GET /subscriptions/status`, `POST /subscriptions/upgrade`
- Admin: `POST /admin/fee-schedule`, `GET /admin/revenue`, `GET/POST /admin/revenue-splits`

### Added — Broker System
- `BrokerSession`, `BrokerFeeConfig` models
- `broker.py` service — session lifecycle with messaging + payment integration
- `xmtp.py` — XMTP protocol wrapper with internal messaging fallback
- `POST /broker/sessions`, `GET /broker/sessions/{id}`, `POST /broker/sessions/{id}/complete|cancel`
- EventBus events: `broker.session.completed`

### Added — DApp Validation & Self-Repair
- `dapp_validator.py` — validates generated DApps via npm install + tsc type-checking
- Self-repair loop: feeds TypeScript errors back through agent cognitive loop
- `validation_status` and `validation_errors` columns on `DAppBuild`
- `GET /dapp/builds/{id}/validation`, `POST /dapp/builds/{id}/validate`

### Added — Tag Taxonomy
- `tag_taxonomy.py` — hierarchical ontology with 11 categories and 95 subcategories
- Deterministic tag suggestion from contract description + ABI function signatures
- `GET /registry/tags`, `GET /registry/tags/suggest`, `GET /registry/search-by-tags`

### Added — Execution Scripts (14 new, 36 total)
- Git operations: `git_clone.py`, `git_pull.py`, `git_analyze.py`, `git_diff.py`, `git_search.py`
- DApp build: `build_web.py`, `build_python.py`, `package_app_store.py`
- Deployment: `deploy_static.py`, `deploy_service.py`, `undeploy.py`
- Seed: `seed_fee_schedules.py`
- Maintenance: `cleanup_expired_pipelines.py`, `cleanup_expired_sessions.py`

### Added — Database Migrations
- `010_pipeline_deployment_tables.sql` — pipeline_runs, pipeline_steps, pending_actions, deployment_records
- `011_payment_tables.sql` — fee_schedules, payment_records, subscriptions, revenue_splits
- `012_broker_tables.sql` — broker_sessions, broker_fee_configs
- `013_dapp_validation.sql` — validation columns on dapp_builds

### Changed — Trigger Router
- Added `pipeline.run.completed`, `pipeline.run.failed`, `pipeline.approval.needed`, `broker.session.*` patterns
- All route to `orchestrator` agent

### Changed — Event Bus
- `pipeline.*` events broadcast to WebSocket + webhook delivery
- `broker.*` events broadcast to WebSocket + webhook delivery

### Fixed — Python 3.9 Compatibility
- `api/auth/enforce.py` — replaced `str | None` with `Optional[str]` and `tuple[str, User]` with `Tuple[str, User]`
- All tests now run on Python 3.9+

### Fixed — Quality Audit (17 issues resolved)
- `dag_orchestrator.py` — added `hashlib` import, fixed NoneType crash on dependency check, fixed confusing error condition logic
- `dapp_validator.py` — fixed path traversal via `os.path.basename()`, fixed uninitialized `attempt` variable
- `payments.py` route — stripped tier overrides from unauthenticated fee-schedule response, added ownership check on payment completion
- `payment_service.py` — fixed double-counted fees in revenue split, added percentage validation (0-100, sum to 100)
- `broker.py` model — added missing FK constraint on `conversation_id`
- Migrations 011/012 — changed `BOOLEAN` to `INTEGER` for SQLite, added missing indexes on `tx_hash` and `plan_type`
- `wizard_workers.py` — removed invalid `sha3_256` import
- `dapp.py` route — added missing `db.commit()`, cleaned up duplicate JSON imports
- `ownership.py` — moved imports to module level

---

## [3.0.0] — 2026-03-19

### Added
- Multi-agent autonomous engine with SOUL identity, 4-tier memory, 6-phase cognitive loop
- 7-layer context injection stack with token budget management
- 10 agent archetypes with trigger routing, output routing, and delegation
- 6-protocol MCP gateway (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks)
- Universal Model Gateway: BitNet, Gemini, Ollama, LM Studio, OpenRouter
- BYOK (Bring Your Own Key) for 13 AI providers with AES-256-GCM encryption
- Smart contract registry with GitHub-style project management
- DApp Factory with 4 templates and ZIP download
- App Store with Docker sandbox review pipeline
- Chain listener for on-chain event monitoring
- Multi-chain wallet identity with ENS resolution
- Messaging system with P2P presence and email bridge
- Knowledge base with sentence-transformer embeddings and hybrid search
- Task scheduler and script runner
- Comprehensive developer documentation

---

## [2.0.0] — 2026-03-18

### Added
- Core API infrastructure (75 endpoints)
- SIWE authentication with 3-layer security
- OpenAI-compatible inference endpoint
- RAG knowledge system with keyword matching
- Basic contract registry
- Database architecture (public.db + internal.db)

---

## [1.0.0] — 2026-03-17

### Added
- Initial platform scaffold
- FastAPI backend with SQLite
- BitNet inference integration
- Basic authentication
