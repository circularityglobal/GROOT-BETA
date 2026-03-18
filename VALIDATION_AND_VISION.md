# REFINET Cloud — Validation & Vision Prompt
## For Claude Code: Full System Audit + Product Vision

---

## ROLE

You are the technical lead validating REFINET Cloud ("Groot") before production deployment. This codebase is a sovereign AI cloud platform — 97+ Python files, 17 route groups, 40+ database tables, 6 protocol adapters, zero external costs, fully open-source. Your job is to:

1. Validate that every component is wired correctly and the system works end-to-end
2. Fix anything that is broken, incomplete, or misconfigured
3. Understand the final product vision described at the end of this document and ensure the codebase serves it

Do not add features. Do not restructure. Validate, fix, and align.

---

## SECTION 1 — WHAT YOU ARE VALIDATING

REFINET Cloud is a sovereign AI platform with these components:

### Backend (Python/FastAPI)
- **Location**: `api/`
- **Entry point**: `api/main.py` → `create_app()` → registers 17 route groups + 3 protocol adapters
- **Database**: Dual SQLite in WAL mode — `public.db` (30+ tables) + `internal.db` (10+ tables)
- **Auth**: SIWE-first (EIP-4361 multi-chain) + optional password (Argon2id + pepper + HKDF) + optional TOTP (pyotp + AES-256-GCM)
- **Inference**: OpenAI-compatible `/v1/chat/completions` that proxies to local BitNet b1.58 2B4T via `llama-server` on port 8080
- **RAG**: Knowledge base with document chunking + hybrid keyword/semantic search (sentence-transformers 384-dim) + system prompt injection
- **CAG**: Contract Augmented Generation — parsed ABI SDK definitions searchable alongside knowledge chunks
- **Registry**: GitHub-style smart contract registry with projects, ABIs, SDKs, stars, forks
- **GROOT Brain**: Per-user contract repository with ABI parsing, access control detection, SDK generation
- **Messaging**: Wallet-to-wallet DMs, groups, email bridge (SMTP on port 8025), typing indicators
- **P2P**: Presence tracking, gossip-based peer discovery, relay infrastructure
- **Identity**: Multi-chain wallet identity with ENS resolution, pseudo-IPv6, email aliases
- **Custodial Wallets**: Shamir Secret Sharing (5-of-3) with per-wallet AES-256-GCM encryption
- **Protocols**: 6-protocol MCP gateway (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks)
- **Config**: Pydantic Settings from `.env` — all secrets in environment, never in code

### Frontend (Next.js 14 / TypeScript / Tailwind)
- **Location**: `frontend/`
- **Output**: Static export (`next export`) → served by Nginx as flat files
- **Pages**: Landing (`/`), Settings/Login (`/settings`), Dashboard (`/dashboard`), Chat (`/chat`), Explore (`/explore`), Repo (`/repo`), Knowledge (`/knowledge`), Devices (`/devices`), Webhooks (`/webhooks`), Messages (`/messages`), Network (`/network`), Docs (`/docs`), Admin (`/admin`), User Profiles (`/u/[username]`), Registry (`/registry/[...slug]`)
- **Components**: AppShell (nav + sidebar + content), GrootChat (floating chat widget), AuthFlow (SIWE wallet connection), SettingsModal (account/security/keys/admin), ThemeProvider (dark/light), WalletOnboarding (profile setup)
- **Web3**: ethers.js v6 for wallet connection and SIWE signing
- **Design system**: CSS custom properties in `globals.css` — REFINET teal (#5CE0D2), dark/light themes

### Infrastructure
- **Target**: Oracle Cloud Always Free ARM A1 Flex (4 OCPUs, 24GB RAM, 200GB storage)
- **Services**: BitNet (port 8080), FastAPI/uvicorn (port 8000), gRPC (port 50051), SMTP bridge (port 8025), Nginx (ports 80/443)
- **Scripts**: `scripts/bootstrap.sh` (server setup), `scripts/deploy.sh`, `scripts/admin.py` (CLI), `scripts/rotate_secrets.sh`

---

## SECTION 2 — VALIDATION CHECKLIST

Run through every check below. For each one, verify it passes. If it fails, fix it. Report your findings.

### 2.1 — Python Syntax & Imports

```
Verify:
- Every .py file in api/ passes Python AST parsing (no syntax errors)
- Every `from api.X import Y` statement resolves to an existing file
- api/models/__init__.py re-exports all ORM model classes:
  Public (30+): User, ApiKey, DeviceRegistration, AgentRegistration, IoTTelemetry,
                WebhookSubscription, UsageRecord, SIWENonce, RefreshToken,
                KnowledgeDocument, KnowledgeChunk, DocumentShare,
                WalletIdentity, WalletSession,
                Conversation, ConversationParticipant, Message, EmailAlias,
                RegistryProject, RegistryABI, RegistrySDK, ExecutionLogic,
                RegistryStar, RegistryFork,
                UserRepository, ContractRepo, ContractFunction, ContractEvent, SDKDefinition
  Internal (9+): ServerSecret, RoleAssignment, AdminAuditLog, ProductRegistry,
                 MCPServerRegistry, SystemConfig, HealthCheckLog,
                 CustodialWallet, WalletShare
```

### 2.2 — Database Initialization

```
Verify:
- api/database.py creates two separate SQLAlchemy engines from PUBLIC_DB_URL and INTERNAL_DB_URL
- init_databases() calls create_all() on both engines
- WAL mode is enabled via the _enable_wal_mode event listener
- Both databases create all expected tables on first run
- Public DB: 30+ tables (see model list above)
- Internal DB: 9+ tables (see model list above)
```

### 2.3 — Router Registration

```
Verify that api/main.py registers 17 route groups + 3 protocol adapters:

Route Groups:
  1.  health_router      → /health, /
  2.  auth_router        → /auth/*
  3.  inference_router    → /v1/*
  4.  devices_router      → /devices/*
  5.  agents_router       → /agents/*
  6.  webhooks_router     → /webhooks/*
  7.  mcp_router          → /mcp/*
  8.  keys_router         → /keys/*
  9.  admin_router        → /admin/*
  10. knowledge_router    → /knowledge/*
  11. registry_router     → /registry/*
  12. repo_router         → /repo/*
  13. explore_router      → /explore/*
  14. identity_router     → /identity/*
  15. messaging_router    → /messages/*
  16. p2p_router          → /p2p/*

Protocol Adapters (optional, graceful degradation):
  17. GraphQL mount       → /graphql (requires strawberry-graphql)
  18. SOAP mount          → /soap (requires spyne)
  19. WebSocket endpoint  → /ws
  20. gRPC server         → :50051 (requires grpcio, started in lifespan)
```

### 2.4 — Auth Flow (Critical Path)

```
Verify the SIWE-first auth flow works end-to-end:

Primary Flow (SIWE):
Step 1: POST /auth/siwe/nonce → returns 64-char hex nonce + SIWE message template
Step 2: Client signs message with wallet (EIP-191)
Step 3: POST /auth/siwe/verify → verifies signature, creates/links user, returns full JWT + refresh token

Optional Additional Factors:
- POST /auth/password/set → sets password (Argon2id + salt + pepper)
- POST /auth/password/login → password login (returns JWT if no TOTP, or layer2 token if TOTP enabled)
- POST /auth/totp/setup → returns QR code + manual key
- POST /auth/totp/verify → verifies TOTP code, enables 2FA

Custodial Wallet Flow:
- POST /auth/wallets → creates custodial wallet (Shamir SSS 5-of-3)
- POST /auth/wallets/login → signs challenge message, returns JWT

Verify:
- The full JWT has scopes: inference:read, keys:write, webhooks:write, devices:write, registry:read, registry:write
- Multi-chain support: nonces work for all 6 supported chains
- POST /auth/siwe/verify with used nonce → 401 (replay protection)
- POST /auth/refresh rotates the refresh token (old one invalidated)
- GET /auth/profile returns full user profile with wallet identities
- GET /auth/identities returns all wallet identities for user
- GET /auth/sessions returns active sessions
- DELETE /auth/sessions/{id} revokes a session
- GET /auth/chains returns supported chain list
```

### 2.5 — Inference + RAG Pipeline (Critical Path)

```
Verify the inference pipeline:

1. POST /v1/chat/completions receives messages
2. Authentication: JWT, API key (rf_ prefix), or anonymous (IP-based rate limiting)
3. _inject_rag_context() extracts the last user message
4. Hybrid search:
   a. knowledge_chunks: keyword scoring + semantic similarity (sentence-transformers)
   b. sdk_definitions: keyword matching on contract names, descriptions, logic summaries
   c. Combine scores, select top-N chunks
   d. Build RAG context string
   e. Prepend Groot system prompt + RAG/CAG context as system message
5. enriched_messages sent to BitNet via call_bitnet() or stream_bitnet()
6. BitNet llama-server at BITNET_HOST responds
7. Response returned in OpenAI-compatible format
8. UsageRecord created in public.db (user_id, api_key_id, device_id, token counts, latency)

Verify:
- GET /v1/models works without auth → returns bitnet-b1.58-2b
- POST /v1/chat/completions without auth → works with IP-based rate limits (25/day, 5/min, 256 max tokens)
- POST /v1/chat/completions with valid API key → 200
- Streaming (stream: true) returns SSE with data: {JSON}\n\n format
```

### 2.6 — Knowledge Base

```
Verify:
- POST /knowledge/documents → ingests document, parses (PDF/DOCX/XLSX/CSV/TXT/MD/JSON/Solidity), chunks, embeds, stores
- GET /knowledge/documents → lists documents with metadata
- DELETE /knowledge/documents/{id} → removes document and chunks
- Auto-tagging: documents receive automatic tags on upload
- Document comparison: semantic similarity, keyword overlap, structure diff
- RAG search: hybrid keyword + semantic scoring with tag filtering

Verify RAG context injection:
- Upload a document via POST /knowledge/documents
- Call POST /v1/chat/completions with relevant query
- Verify the system prompt sent to BitNet INCLUDES the uploaded document content
```

### 2.7 — Smart Contract Registry

```
Verify:
- POST /registry/projects → creates project with slug, category, chain
- GET /registry/projects/{slug} → returns project details
- POST /registry/projects/{slug}/abis → adds ABI
- POST /registry/projects/{slug}/sdks → adds SDK
- POST /registry/projects/{slug}/logic → adds execution logic
- POST /registry/projects/{slug}/star → stars/unstars project
- POST /registry/projects/{slug}/fork → forks project
- Search, filtering by category/chain/tags, pagination
```

### 2.8 — GROOT Brain (Contract Repository)

```
Verify:
- POST /repo/init → initializes user repository (@username namespace)
- POST /repo/upload → uploads contract (ABI JSON required, source code optional/private)
- GET /repo/my-contracts → lists user contracts
- GET /repo/my-contracts/{slug} → returns contract detail (source_code NEVER included)
- ABI parsing → generates functions with access control, mutability, danger flags
- POST /repo/my-contracts/{slug}/toggle-visibility → public/private toggle
- POST /repo/my-contracts/{slug}/functions/{fn_id}/toggle → SDK enable/disable per function
- GET /repo/my-contracts/{slug}/sdk → returns generated SDK JSON

Cardinal rules:
- source_code column is NEVER returned in any API response
- GROOT reads only sdk_definitions, never contract_repos.source_code
```

### 2.9 — Messaging & P2P

```
Verify:
- POST /messages/dm → creates/sends direct message
- POST /messages/groups → creates group conversation
- POST /messages/conversations/{id}/send → sends message in conversation
- GET /messages/conversations → lists conversations with unread counts
- GET /messages/conversations/{id}/messages → returns messages with pagination
- POST /messages/conversations/{id}/read → marks as read
- POST /messages/email-alias/register → registers auto email alias
- POST /messages/email-alias/custom → sets custom alias

P2P:
- POST /p2p/heartbeat → announces presence
- POST /p2p/gossip → peer discovery exchange
- POST /p2p/peers → lists nearby peers
- Typing indicators work across conversations
- Stale peers cleaned up after 2 minutes
```

### 2.10 — Wallet Identity

```
Verify:
- GET /auth/identities → returns all wallet identities with ENS, pseudo-IPv6, email aliases
- PATCH /auth/identities/{id} → updates display name, permissions
- ENS resolution fires in background thread on first login (Ethereum mainnet only)
- Pseudo-IPv6 computed deterministically from wallet + chain
- Email aliases auto-generated as <hash>@cifi.global
```

### 2.11 — Devices, Agents, Webhooks

```
Verify:
- POST /devices → registers device (iot/plc/dlt/webhook types)
- POST /devices/{id}/telemetry → stores telemetry with optional ECDSA verification
- POST /agents → registers agent with product and build key
- PATCH /agents/{id} → updates remote config
- POST /webhooks → creates subscription with event filters
- Webhook delivery: HMAC-SHA256 signed payloads with exponential backoff retry
- X-REFINET-Signature header present on all deliveries
```

### 2.12 — Admin & Internal DB

```
Verify:
- All /admin/* routes require admin role (checked against internal.db role_assignments)
- Role management: grant, revoke roles with audit logging
- Server secret management: create, read names only, rotate
- AES-256-GCM encryption with INTERNAL_DB_ENCRYPTION_KEY
- Audit log is append-only — no UPDATE or DELETE routes exist
- Platform statistics: user count, API calls, storage
- MCP server registration with health tracking
- System config key-value management
- scripts/admin.py works with direct SQLite access (no HTTP)
```

### 2.13 — 6-Protocol MCP Gateway

```
Verify:
- REST: All 17 route files load and respond
- GraphQL (/graphql): Types, queries, mutations, subscriptions (if strawberry installed)
- gRPC (:50051): SearchProjects, GetProject, GetABI, GetSDK, GetExecutionLogic (if grpcio installed)
- SOAP (/soap): Complex types and service methods (if spyne installed)
- WebSocket (/ws): Connection, subscription, event broadcasting, tool execution
- Webhooks: Delivery worker running, retry logic functional
- All protocols use unified auth middleware (protocol_auth.py)
- Missing optional dependencies → graceful fallback, no errors
```

### 2.14 — Frontend

```
Verify:
- frontend/app/layout.tsx → root layout with metadata, imports globals.css
- frontend/app/client-layout.tsx → AppShell (authenticated) or PublicNavBar (unauthenticated)
- frontend/app/globals.css → CSS custom properties for dark + light themes
- frontend/components/ThemeProvider/index.tsx → provides theme context + toggle
- frontend/components/GrootChat/index.tsx → floating chat widget (streaming SSE)
- frontend/components/AuthFlow/index.tsx → SIWE wallet connection with chain selection
- frontend/components/WalletOnboarding/index.tsx → profile creation post-SIWE
- frontend/components/SettingsModal/index.tsx → Account, Security, API Keys, Admin tabs

Pages:
- / → Landing page with horizontal panels
- /settings/ → Auth/login page
- /dashboard/ → Stats, API keys, devices, activity
- /chat/ → Full chat with document sources, conversation history, streaming
- /explore/ → Registry projects, smart contracts, knowledge search (3 tabs)
- /repo/ → Contract repository with upload, parse, publish, SDK view
- /knowledge/ → Documents, Upload, Contracts (CAG), Compare (4 tabs)
- /devices/ → Device registration, telemetry, commands
- /webhooks/ → Subscription management
- /messages/ → Conversations, compose, aliases, groups
- /admin/ → Admin panel
- /docs/ → API documentation

Sidebar navigation: Dashboard, Chat, Devices, Webhooks, Knowledge, Registry, Repositories, API Docs, Admin
Top bar: Registry, Repositories, Messages, Network + theme toggle + settings + logout
```

### 2.15 — Environment & Infrastructure

```
Verify:
- .env.example contains ALL required variables
- api/config.py (Pydantic Settings) has a field for every .env variable
- SIWE config: SIWE_DOMAIN, SIWE_CHAIN_ID, SIWE_STATEMENT, SIWE_SUPPORTED_CHAINS
- Wallet config: WALLET_EMAIL_DOMAIN (cifi.global)
- SMTP config: SMTP_HOST, SMTP_PORT, SMTP_ENABLED
- Product build keys: QUICKCAST_BUILD_KEY, AGENTOS_BUILD_KEY
- requirements.txt includes all Python dependencies (25+ packages)
- frontend/package.json has next, react, react-dom, ethers, tailwindcss, framer-motion
- nginx/refinet.conf has: HTTP→HTTPS redirect, TLS, SSE proxy, WebSocket proxy, rate limits
- docker-compose.yml defines api + frontend services with volumes
```

---

## SECTION 3 — FIX ANYTHING BROKEN

After running through the checklist above, fix every issue you find. Common things to check:

1. Any `from api.X import Y` where Y doesn't exist in that module
2. Any route handler that references a column name that was renamed
3. Any missing `__init__.py` files
4. Any Pydantic model using `EmailStr` without `email-validator` installed
5. Any SQLAlchemy model using reserved names (`metadata`, `type`, `hash`)
6. The inference route must call `_inject_rag_context()` for BOTH streaming and non-streaming paths
7. All routers must be registered in `main.py`
8. All models must be imported in `api/models/__init__.py`
9. Optional protocols (GraphQL, gRPC, SOAP) must degrade gracefully if deps not installed
10. Background workers (P2P cleanup, health monitor, auth cleanup, webhook delivery, SMTP) must start in lifespan

---

## SECTION 4 — THE PRODUCT VISION

This is what REFINET Cloud is meant to become. Every architectural decision in this codebase serves this vision. Read this and ensure the code delivers it.

### What REFINET Cloud Is

REFINET Cloud is the root node of a new kind of internet. It is infrastructure for a world where:

- **Intelligence is sovereign.** The AI runs on hardware REFINET controls — permanently free Oracle Cloud ARM infrastructure. BitNet b1.58 is a 1-bit open-source LLM that runs on CPU. No GPU. No API bill. No vendor who can revoke access.

- **Identity is cryptographic.** Every user, every device, every agent connects with wallet-based identity. SIWE authentication, ENS resolution, pseudo-IPv6 addressing, email aliases — all derived from blockchain wallets. Multi-chain support across Ethereum, Polygon, Arbitrum, Optimism, Base, and Sepolia.

- **Contracts are understood.** GROOT doesn't just chat — it understands smart contracts. Upload an ABI and GROOT parses it, detects access control patterns, flags dangerous operations, and generates SDK definitions it can reference in future conversations. The GitHub-style registry lets developers discover, star, and fork contract projects.

- **Communication is wallet-native.** Messaging is tied to wallet identity, not email or phone numbers. Direct messages, group conversations, email bridging, P2P presence — all using the same cryptographic identity that authenticates you.

- **Data is owned by the user and the platform.** Two physically separate databases. The internal database holds secrets, roles, audit logs, and custodial wallet shares — NEVER accessible via public API. The audit log is append-only. Custodial wallet keys are Shamir-split and never stored whole.

- **Any device can connect.** IoT sensors, PLCs, DLT nodes, autonomous agents — anything that speaks HTTP joins the network. Six protocol adapters ensure every system can participate: REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks.

- **Developers use it like OpenAI.** The API is OpenAI-compatible. Same JSON format. Same streaming SSE. Any code that works with OpenAI works with REFINET Cloud by changing two lines. Zero switching cost in. Zero switching cost out.

- **The cost is zero. Forever.** Oracle Cloud Always Free tier is not a trial. SQLite instead of PostgreSQL. In-memory rate limiting instead of Redis. BitNet instead of GPT. Let's Encrypt for TLS. Every dependency is open-source.

### What the User Experiences

A person visits `app.refinet.io`. They see a clean, dark-themed landing page — the REFINET leaf logo, a headline that says "Intelligence that grows from the ground up." They click "Talk to Groot" and start chatting immediately — no signup required.

When they want full access, they connect their wallet. One SIWE signature and they're in. The dashboard shows their stats, API keys, devices, and activity. The chat page lets them scope conversations to specific documents. The repo page lets them upload contracts. The explore page lets them discover the ecosystem. Messages let them talk to other wallets.

The entire experience works in dark mode and light mode. The design language is REFINET teal on near-black. The feeling is: this is infrastructure, not a toy.

### What the Developer Experiences

A developer reads the API docs. They connect their wallet, get an API key, and add two lines to their code. Everything works — streaming, function calling, error handling. They upload their contract ABIs and GROOT can answer questions about their contracts. They star interesting projects in the registry. They subscribe to webhook events.

### What the Admin Experiences

The admin grants roles via `scripts/admin.py`. They upload documents to the knowledge base and GROOT learns immediately. They add contract definitions for CAG. They monitor the audit log, manage MCP servers, and configure system settings. Everything is encrypted, audited, and append-only.

### The Network Effect

QuickCast, AgentOS, IoT sensors, PLCs, DLT nodes — they all connect to REFINET Cloud. Every connection makes the platform more valuable. Every document makes GROOT smarter. Every contract makes CAG more capable. Every wallet identity enriches the network.

This is regenerative finance applied to intelligence: a system that grows from the ground up.

### What "Done" Looks Like

The platform is done when:
- A user can visit the site, connect their wallet, and talk to GROOT about blockchain, contracts, and REFINET
- A developer can swap their OpenAI base URL and get inference in under 5 minutes
- A contract developer can upload an ABI and get a parsed SDK with access control analysis
- Wallet-to-wallet messaging works with ENS names and email aliases
- A device can POST telemetry and trigger a webhook in under 30 seconds
- An admin can upload a document and GROOT uses it in the next conversation
- All 6 protocols respond to authenticated requests
- The whole thing runs on one ARM server at zero cost with no external dependencies
- The code can be forked, deployed, and run by anyone who reads the README

That is REFINET Cloud. That is Groot. Validate that this codebase delivers it.

---

## SECTION 5 — AFTER VALIDATION

Once everything passes, report:

1. **Issues found and fixed** — list every change you made
2. **Confidence level** — rate 1-10 that this codebase is production-ready
3. **Remaining work** — anything that requires manual steps (BitNet binary compilation, DNS setup, TLS certificates)
4. **First deploy sequence** — the exact commands to go from this archive to a running platform on Oracle Cloud ARM
