# REFINET Cloud — Groot
## Grass Root Project Intelligence

This file is the master architecture document for REFINET Cloud.
See the full specification in `docs/REFINET_CLOUD_TECHNICAL_SPECIFICATION.md`.

**Four Non-Negotiable Constraints:**
1. Zero recurring cost (Oracle Cloud Always Free)
2. Sovereign data (no third-party telemetry)
3. Wallet-first authentication (SIWE + optional password/TOTP)
4. Universal connectivity (REST/GraphQL/gRPC/SOAP/WebSocket/Webhook)

**Stack:**
- Backend: FastAPI + SQLAlchemy 2.0 + SQLite (WAL mode, dual databases: public.db + internal.db)
- Inference: BitNet b1.58 2B4T via bitnet.cpp (CPU-native, ARM-optimized)
- RAG: sentence-transformers (384-dim embeddings) + hybrid keyword/semantic search
- Frontend: Next.js 14 App Router + React 18 + TypeScript + Tailwind CSS → static export → Nginx
- Web3: wagmi + viem (frontend, native multi-wallet, no WalletConnect) + web3.py + eth-account (backend) for SIWE + custodial wallets
- Auth: SIWE (EIP-4361) + Argon2id + pyotp + PyJWT (12 scope types)
- Encryption: AES-256-GCM + HKDF + Shamir Secret Sharing (5-of-3 threshold)
- Protocols: 6-protocol MCP Gateway (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks)
- TLS: Let's Encrypt via Certbot
- Server: Oracle Cloud ARM A1 Flex (4 OCPUs, 24GB RAM, 200GB storage)

**GROOT is the Sole Wizard:**
- An Agent reads. A Wizard acts. GROOT is the only Wizard in REFINET Cloud.
- GROOT has ONE wallet (SSS-secured, 3-of-5 threshold). All on-chain actions go through it.
- Users interact with GROOT to deploy, query, and transact. GROOT never acts alone — master_admin approves all Tier 2 actions.
- CAG (Contract-Augmented Generation) gives GROOT access to the contract registry: Query (search), Execute (view calls), Act (sign transactions after approval).

**Platform Subsystems:**
- AI Inference — OpenAI-compatible API with RAG + CAG context injection, multi-provider gateway
- Agent Engine — Autonomous multi-agent platform with SOUL identity, 5-tier memory, 6-phase cognitive loop, tool access, CAG integration, and delegation
- Context Assembly — 8-layer injection stack with token budget tracking (SOUL, agent, memory, RAG, **CAG**, skills, safety, runtime)
- Trigger Router — Unified event→agent task routing from 7 sources (heartbeat, cron, webhook, chain, messenger, pipeline, broker)
- Output Router — Multi-target task result routing (DB, response, memory, agent chaining, webhook)
- **Wizard Pipeline** — 8-stage DAG: compile → test → parse → RBAC → deploy → reparse → frontend → appstore, with parallel execution
- Smart Contract Registry — GitHub-style project management with ABI parsing and SDK generation
- GROOT Brain — Per-user contract repository with source code privacy + CAG three access modes
- DApp Factory — Template-based DApp assembly from registry contracts with LLM-driven component generation
- App Store — Publish and discover DApps, agents, tools, and templates with sandbox review pipeline
- **Dynamic Chain Registry** — Database-backed EVM chain management, admin adds networks via chainlist.org
- Chain Listener — On-chain event monitoring with automatic agent task creation
- Wallet Identity — Multi-chain identity with ENS resolution and pseudo-IPv6 addressing
- Messaging — Wallet-to-wallet DMs, groups, email bridge (SMTP), messenger bridge, typing indicators
- P2P Network — Presence tracking, gossip-based peer discovery, relay infrastructure
- Knowledge Base — Multi-format document ingestion, auto-tagging, comparison, timeline extraction, FTS5 full-text indexing
- Device & Agent Connectivity — IoT/PLC/DLT registration, telemetry, remote config
- Task Scheduler — Health monitoring, cleanup, memory expiry, 13 configurable scheduled tasks
- Script Runner — Safe script execution with category-based access control (ops, maintenance, analysis, chain, dapp)
- JSONL Logger — File-based episodic audit trail alongside DB storage
- Configuration — YAML hierarchy (default → production → ENV) with dot-notation access
- Help Desk — XMTP-encrypted customer support: tickets linked to messaging conversations, admin queue, FAQ
- SDK Gateway — Deterministic, LLM-free MCP tools for contract address resolution and public SDK access (4 tools: resolve_contract, fetch_sdk, list_chains_for_contract, bulk_sdk_export)
- Tab Visibility — Admin-controlled feature gating: 3-layer enforcement (UI hiding, client redirect, API middleware), master_admin bypass
- Infrastructure Manager — Oracle Cloud instance registry: node CRUD, health checks, resource aggregation, multi-provider support
- Admin Panel — Role management (master_admin, admin, operator, readonly), secrets vault, audit log, chain management, GROOT wallet, pending actions, tab visibility, infrastructure, 13 admin tabs

**Cardinal Rules:**
1. User source code is PRIVATE — GROOT never reads `source_code`, only ABIs and SDKs
2. Internal DB is NEVER accessible via public API — admin operations only
3. Audit log is append-only — no update or delete routes exist
4. Custodial wallet private keys are NEVER stored — only encrypted Shamir shares
5. All 6 protocols use unified authentication middleware
6. Agents inherit owner permissions — no privilege escalation
7. Chain watchers may detect events but NEVER initiate state-changing transactions autonomously

**Autonomous Platform Operations (4 Agent Skills Installed):**
- `skills/refinet-platform-ops/` — Platform monitoring, health checks, admin email alerts, agent pipeline orchestration
- `skills/refinet-knowledge-curator/` — RAG/CAG intelligence maintenance: orphan detection, stale chunk pruning, CAG sync, embedding drift detection
- `skills/refinet-contract-watcher/` — On-chain intelligence: ABI security scanning (8 dangerous patterns), event interpretation, contract activity monitoring, cross-chain bridge correlation
- `skills/refinet-sdk-gateway/` — Deterministic SDK access: contract resolution, SDK fetch, catalog export, automated sync workers with feedback loops
- Zero-cost agent pipeline: Claude Code CLI → Ollama → BitNet → Gemini Flash (4-tier fallback, all free)
- File-based agent memory: `memory/{working,episodic,semantic,procedural}/` for persistent agent state across runs
- 15 cron-driven autonomous tasks across 3 agents (platform-ops, knowledge-curator, contract-watcher)
- Admin email alerts via self-hosted SMTP (8+ categories: HEALTH, SECURITY, AGENT, DEPLOY, CHAIN, REGISTRY, KNOWLEDGE, MAINTENANCE, ABI_SECURITY, EVENT_ANOMALY)
- GitHub Actions workflows for all 3 agents (zero-cost CI/CD scheduling)

**Scale:**
- 30 route files, 330+ API endpoints, 22 MCP tools
- 75+ database tables (public + internal)
- 70+ service modules, 12 auth modules, 7 middleware modules
- 23 migration files (20 public + 3 internal)
- 12 test files, 214 passing tests, 40+ operational scripts
- 25 frontend pages, 20+ components, 13 admin panel tabs
- 5 root control documents (SOUL, SAFETY, MEMORY, HEARTBEAT, AGENTS)
- 8 skills (platform-ops, knowledge-curator, contract-watcher, sdk-gateway + 4 base), 4 YAML config files, JSONL audit logging
- 4 persistent memory directories for autonomous agent state
- 3 GitHub Actions workflows for autonomous agent scheduling
