# Changelog

All notable changes to REFINET Cloud are documented in this file.

---

## [3.7.0] — 2026-03-20

### Added — SDK Gateway Skill (LLM-Free Contract Access)
- **New skill**: `skills/refinet-sdk-gateway/` — deterministic, LLM-free access to all public smart contract SDKs via MCP
- **4 new MCP tools** (22 total): `resolve_contract`, `fetch_sdk`, `list_chains_for_contract`, `bulk_sdk_export`
- `api/services/sdk_gateway.py` — core service: contract resolution by name/slug/address, multi-chain deployment lookup, paginated SDK catalog
- Automated workers: `sdk_sync_worker.py` (staleness detection + auto-regeneration), `sdk_indexer.py` (per-chain catalog builder)
- Usage feedback loop via `memory/working/sdk_queries.jsonl` — hot-contract detection, 30-day pruning
- Event bus cache invalidation on SDK/ABI/visibility changes
- Two core calls for agents: **contract address / network** lookup and **SDK fetch** — instant, no inference latency

### Added — XMTP-Encrypted Help Desk (Customer Support System)
- `SupportTicket` + `TicketMessage` models in `public.db` — status lifecycle: open → in_progress → waiting_on_user → resolved → closed
- `api/services/support.py` — 9 functions: create, list, reply, assign, close, update status, stats
- `api/routes/support.py` — 12 REST endpoints (6 user + 6 admin) at `/support/*`
- Tickets linked to wallet-to-wallet DM conversations via `messaging.create_dm()` — E2E encrypted when XMTP enabled
- **Help Desk page** (`/help/`) — 3-view UI: ticket list, new ticket form, conversation thread with admin/user message styling
- **Sidebar tab** — "Help Desk" with question-mark icon, positioned in Build section
- **Settings section** — "Help & Support" with quick ticket form + 5 FAQ items
- **Admin dashboard** — `SupportQueueCard` for admin/master_admin showing open tickets, priorities, avg resolution time
- Event bus: `support.ticket.created`, `support.ticket.replied`, `support.ticket.resolved`, `support.ticket.status_changed`
- Migration: `migrations/public/020_support_tickets.sql`

### Added — Admin Tab Visibility Controls (Feature Gating)
- **3-layer enforcement**: UI hiding (sidebar + top bar), client-side route redirect, API middleware (403)
- `DEFAULT_TAB_VISIBILITY` — 18 platform tabs, all default to enabled
- `GET /admin/tab-visibility` (public, no auth) + `PUT /admin/tab-visibility` (master_admin only)
- `api/middleware/tab_gate.py` — `TabGateMiddleware` with 30s in-memory cache, 16 gated route groups, 14 exempt prefixes
- Master admin always bypasses all gates — sees all tabs, accesses all routes regardless of visibility settings
- Frontend: `isTabVisible()` helper, `TAB_PATH_MAP` route guard, all 17 sidebar items + 5 top bar icons wrapped
- Admin panel: new "VISIBILITY" tab with toggle grid, save button, enabled/disabled counts
- Audit logging on all visibility changes via `AdminAuditLog`

### Added — Infrastructure Management (Oracle Cloud & Server Nodes)
- `InfraNode` model in `internal.db` — 24 columns: provider, region, instance_type, IPs, CPU/RAM/disk, role, services, health tracking
- 6 admin API endpoints: list nodes, add (master_admin), update (master_admin), remove/terminate (master_admin), health check, stats
- Health check pings node's `/health` endpoint with latency tracking
- Stats aggregation: total nodes, CPU, memory, disk, grouped by status/role/provider
- Admin panel: new "INFRASTRUCTURE" tab with stats bar, 15-field node registration form, node cards with health check/start/stop/remove
- Audit logging on all node mutations
- Migration: `migrations/internal/003_infra_nodes.sql`

### Added — Master Admin Wallet-Gated Security
- Wallet `0xE302932D42C751404AeD466C8929F1704BA89D5A` set as `master_admin` in `internal.db`
- Role grant/revoke of `master_admin` now requires `_require_master_admin()` (JWT-only, no X-Admin-Secret bypass)
- Regular admins can only grant `admin`, `operator`, `readonly` roles
- All role changes audit-logged to append-only `AdminAuditLog`

### Scale
- **30 route files, 330+ API endpoints** (was 29/302)
- **75+ database tables** (was 71) — added support_tickets, ticket_messages, infra_nodes
- **13 admin panel tabs** — stats, onboarding, users, reviews, store, providers, wallets, networks, infrastructure, audit, MCP, secrets, visibility
- **22 MCP tools** (was 18) — added resolve_contract, fetch_sdk, list_chains_for_contract, bulk_sdk_export
- **7 middleware modules** (was 6) — added tab_gate.py
- **5 installed skills** (was 3+4 base) — added refinet-sdk-gateway

### Tests
- **214/214 API tests passing** — zero regressions across all changes

---

## [3.6.0] — 2026-03-20

### Added — Landing Page Overhaul & Brand Refresh
- 7-panel horizontal scroll landing page (was 5): Hero, Mission, Infrastructure, Developers, For Everyone, Browser, AgentOS
- **PanelMission** — 6 pillars: Sovereign by Design, Zero Extraction, Regenerative Finance, Community Governed, Cryptographic Identity, Intelligence for All
- **PanelInfrastructure** — self-operating platform showcase: $0/month stats, 5 autonomous agents with live status, 317 endpoints, 9 blockchain ecosystems
- Regenerative mission messaging throughout: "A new internet built to regenerate the world"
- Consistent teal branding (#5CE0D2) across all panels — removed off-brand matrix green (#00FF41) from browser section
- Transparent logo — removed black square background from `refi-logo.png`, removed `border-radius: 50%` / `rounded-full` from all 12 logo references

### Added — `/login` Route & Native Wallet Connection
- New `/login` page with lazy-loaded `AuthFlow` (page shell: 91.7 KB, wallet UI loads async)
- Native EIP-1193 + EIP-6963 wallet connection — zero third-party dependencies (no WalletConnect SDK)
- 10 wallet brands with real SVG logos: MetaMask, Rabby, Coinbase, Trust, Phantom, D'CENT, Trezor, Ledger, OKX, Brave
- Auto chain switching with `wallet_addEthereumChain` for XDC (50) and Avalanche Fuji (43113)
- `/settings` now redirects to `/login` (unauthenticated) or `/dashboard` (authenticated)

### Added — XDC Network & Avalanche Fuji Chain Support
- `api/auth/chains.py` — dynamic chain registry: queries `supported_chains` DB table, merges with hardcoded fallbacks
- XDC Network (chain 50) and Avalanche Fuji (chain 43113) added to both DB fallbacks and frontend wagmi config
- `DEFAULT_CHAIN_ID = 43113` (testing) — swap to `50` for XDC production
- `lib/wallet.ts` — added XDC and Avalanche Fuji to wagmi chain config with custom RPC endpoints

### Added — Centralized SPA Auth Guard
- Single auth guard in `client-layout.tsx` replaces 14 per-page `window.location.href` redirects
- Protected routes redirect to `/` (home) — not `/login` — preventing crash loops
- Global transition overlay (z-index 99999) during login/logout — eliminates skeleton flash
- All navigation uses `router.push()` / `router.replace()` — zero full-page reloads

### Added — Dark Theme Lock
- Landing page, login page: always dark, no toggle, `ForceDarkTheme` component
- Dashboard: starts dark every session, user can toggle to light (not persisted)
- `ThemeProvider` defaults to dark on mount, no localStorage read
- HTML `<html data-theme="dark">` set at SSR level
- All loading screens use hardcoded `#050505` background

### Fixed — Database Schema Migration
- Added 11 missing columns to `users` table: `auth_layer_1_completed_at`, `auth_layer_2_completed_at`, `auth_layer_3_completed_at`, `onboarding_completed_at`, `marketing_consent`, `marketing_consent_at`, `cifi_verified`, `cifi_username`, `cifi_verified_at`, `cifi_kyc_level`, `cifi_display_name`
- Migration saved: `migrations/public/019_users_onboarding_cifi.sql`

### Fixed — Build Errors & SPA Routing
- `app/agents/page.tsx` — type error on `data.soul_md` (added `Record<string, string>` annotation)
- `app/store/[...slug]` — converted from catch-all to `[slug]` with `generateStaticParams` + `dynamicParams = true` for static export compatibility
- CORS: added `localhost:4001` to allowed origins for dev
- WagmiProvider moved to wrap only authenticated AppShell — public pages load without wallet overhead

### Performance
- Login page: 220 KB → 91.7 KB (AuthFlow lazy-loaded via `dynamic()`)
- All panel CTAs: `<a href>` → `<Link prefetch>` (client-side SPA navigation)
- Nonce prefetched during login page load for faster SIWE signing
- WagmiProvider scoped to authenticated pages only

### Tests
- **270/270 passing** (214 API + 56 skills) — zero regressions

---

## [3.5.0] — 2026-03-20

### Added — Contract Security Analysis Pipeline
- `ContractSecurityFlag` SQLAlchemy model in `api/models/registry.py` — persists ABI security scan results (pattern, severity, location, description, risk) with CASCADE FK to `registry_abis`
- `GET /registry/abis/{abi_id}/security-flags` endpoint — retrieve security analysis flags for any ABI
- Automated ABI security scanning via `contract_scan.py` stores flags in DB and exposes them through the API

### Added — Skills Test Suite (56 Tests)
- `skills/tests/conftest.py` — shared fixtures with full real schema (knowledge, registry, chain tables), mock SMTP/httpx, sample ABIs
- `skills/tests/test_platform_ops.py` — 12 tests: subsystem checks, DB connectivity, report formatting, email delivery
- `skills/tests/test_knowledge_curator.py` — 16 tests: stats accuracy, orphan detection, stale chunk pruning, CAG sync, report validation
- `skills/tests/test_contract_watcher.py` — 21 tests: all 8 dangerous pattern detections, clean ABI verification, risk scoring, flag persistence, event/registry stats
- `skills/tests/test_pipeline_integration.py` — 7 tests: sequential pipeline (platform-ops → knowledge-curator → contract-watcher), report format validation, exit code verification
- Total test count: **270 passing** (214 API + 56 skills)

### Fixed — Critical Schema Mismatches in Skill Scripts
- `knowledge_health.py` — 7 SQL fixes: `documents` → `knowledge_documents`, `document_chunks` → `knowledge_chunks`, removed nonexistent `chunk_embeddings` table (embeddings are a column on `knowledge_chunks`), `d.format` → `d.doc_type`, `cag_index` → `contract_definitions`, `contract_abis` → `registry_abis`, renamed `chunk_count` alias to `num_chunks` to avoid SQLite column-alias collision in HAVING clause
- `contract_scan.py` — 7 SQL fixes: `contract_abis` → `registry_abis`, `ca.chain_id` → `ca.chain`, `ca.name` → `ca.contract_name`, `chain_listeners` → `chain_watchers`, removed nonexistent `chain_events.status` column, `chain_events.created_at` → `received_at`, `chain_events.chain_id` → `chain`

### Fixed — Documentation Alignment with Actual Schema
- `skills/refinet-knowledge-curator/SKILL.md` — ~15 table name corrections across storage architecture, pseudo-code examples, and cron schedule descriptions
- `skills/refinet-contract-watcher/SKILL.md` — ~8 table name corrections across storage architecture, activity monitoring, and bridge correlation pseudo-code
- `skills/refinet-knowledge-curator/references/knowledge-api.md` — rewrote all 4 CREATE TABLE schemas to match actual models (`knowledge_documents`, `knowledge_chunks`, `contract_definitions`)
- `skills/refinet-contract-watcher/references/chain-api.md` — rewrote all 3 CREATE TABLE schemas to match actual models (`chain_watchers`, `chain_events` with correct columns, `contract_security_flags` with FK to `registry_abis`)
- `configs/knowledge-curator-cron.yaml` — corrected table references in task descriptions
- `configs/contract-watcher-cron.yaml` — corrected table references in task descriptions

---

## [3.4.0] — 2026-03-20

### Added — Knowledge Curator Skill (Autonomous RAG/CAG Maintenance)
- `skills/refinet-knowledge-curator/` — 546-line skill for autonomous knowledge base intelligence maintenance
  - `SKILL.md` — 7-part skill: KB architecture, autonomous pipelines, email notifications, cron schedule, operating procedures, safety, references
  - `scripts/knowledge_health.py` — KB health checker: orphan detection, stale chunk pruning, CAG sync check, embedding stats, HTML email reporting
  - `references/knowledge-api.md` — Knowledge base API endpoints and SQLite schema (documents, chunks, embeddings, FTS5, cag_index)
  - `references/embedding-pipeline.md` — Embedding pipeline flow, hybrid 3-signal search algorithm, re-embedding strategy, ARM capacity planning
- `configs/knowledge-curator-cron.yaml` — 5 scheduled tasks: 30m ingestion check, 6h orphan repair, 6h CAG sync, daily benchmark, daily digest
- `.github/workflows/knowledge-curator.yml` — GitHub Actions for scheduled health checks and manual curator tasks
- `scripts/install_knowledge_curator_cron.sh` — Server cron installer with --remove support
- `docs/KNOWLEDGE_CURATOR_SETUP.md` — Setup guide, prerequisites, local testing commands, $0/month cost breakdown

### Added — Contract Watcher Skill (Autonomous On-Chain Intelligence)
- `skills/refinet-contract-watcher/` — 620-line skill for autonomous on-chain intelligence across 6 EVM chains
  - `SKILL.md` — 7-part skill: on-chain architecture, autonomous pipelines (event interpretation, ABI security, activity monitoring, bridge correlation), email notifications, cron schedule, operating procedures, safety, references
  - `scripts/contract_scan.py` — ABI security scanner: 8 dangerous pattern categories (delegatecall, selfdestruct, tx.origin, unchecked call, infinite approval, inline assembly, proxy patterns, ownership transfer), chain event stats, registry stats, HTML email reporting
  - `references/chain-api.md` — Chain listener API, 6-chain RPC configuration (free public endpoints), DB schemas
  - `references/registry-api.md` — Smart contract registry API, security flag format, SDK generation pipeline
- `configs/contract-watcher-cron.yaml` — 5 scheduled tasks: 5m event processing, 15m ABI scan, 4h activity monitor, 12h bridge correlation, weekly report
- `.github/workflows/contract-watcher.yml` — GitHub Actions with 3 jobs: abi-scan, watcher-task, weekly-report
- `scripts/install_contract_watcher_cron.sh` — Server cron installer with --remove support
- `docs/CONTRACT_WATCHER_SETUP.md` — Setup guide, prerequisites, local testing commands, $0/month cost breakdown

---

## [3.3.0] — 2026-03-20

### Added — Platform Ops Skill & Autonomous Agent Pipeline
- `skills/refinet-platform-ops/` — 620-line skill definition teaching Claude Code how to autonomously operate REFINET Cloud
  - `SKILL.md` — 8-part skill covering architecture map, admin email system, pipeline architecture, health checks, deployment strategies, operating procedures, safety constraints, and reference files
  - `scripts/health_check.py` — Comprehensive platform health checker (API, BitNet, DB, SMTP, disk, memory) with HTML email reporting via self-hosted SMTP
  - `scripts/run_agent.sh` — Zero-cost agent pipeline runner with 4-tier LLM fallback chain: Claude Code CLI → Ollama → BitNet → Gemini Flash (all free)
  - `references/api-endpoints.md` — Quick-reference for 210+ API endpoints across 22 route groups
  - `references/agent-engine.md` — Agent Engine architecture reference (SOUL format, cognitive loop, context injection, memory tiers)
  - `references/email-templates.md` — Python functions for HTML admin alert emails (health, security, daily summary)

### Added — File-Based Agent Memory Directories
- `memory/working/` — Per-agent working memory state (JSON, per-run TTL)
- `memory/episodic/` — Timestamped agent run logs (JSONL, append-only)
- `memory/semantic/` — Distilled facts and embeddings (JSON, permanent)
- `memory/procedural/` — Learned tool-use patterns (JSON, permanent)
- `.gitkeep` files ensure directories are tracked; `.gitignore` excludes runtime data (`*.json`, `*.jsonl`)

### Added — Zero-Cost Autonomous Agent Execution
- 4-tier LLM fallback chain: Claude Code CLI (`claude -p`) → Ollama (phi3/llama3) → BitNet b1.58 2B4T → Gemini Flash (free tier)
- 7-layer context injection stack assembled from repo files: SOUL → Safety → Agent Config → Working Memory → Episodic Memory → Task
- All agent results written to episodic memory as JSONL for audit trail
- Cron-driven pipeline configuration in `configs/platform-ops-cron.yaml` (heartbeat 60s, inference check 5m, security audit 15m, memory cleanup 1h, knowledge integrity 6h, daily summary, weekly audit)
- GitHub Actions workflow template for scheduled health checks and weekly audits at zero cost

### Added — Admin Email Notification System
- 8 alert categories with structured subject prefixes: HEALTH, SECURITY, AGENT, DEPLOY, CHAIN, REGISTRY, KNOWLEDGE, MAINTENANCE
- Self-hosted SMTP via REFINET bridge on port 8025 (zero cost, no third-party providers)
- HTML email templates with inline CSS for universal client compatibility
- `send_admin_alert()` function pattern for all ops scripts and agents

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
