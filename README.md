# REFINET Cloud

**Grass Root Project Intelligence**

REFINET Cloud is the sovereign cloud infrastructure for the Regenerative Finance Network. It provides free, OpenAI-compatible AI inference powered by BitNet, a multi-agent autonomous engine, a GitHub-style smart contract registry, DApp factory, app store, wallet-to-wallet encrypted messaging, multi-chain identity management, on-chain event automation, IoT device connectivity, a DAG-coordinated wizard pipeline for compiling, testing, and deploying smart contracts, a broker system for paid services, a payment and subscription engine, and a 6-protocol MCP gateway — all running on permanently free infrastructure with zero recurring costs.

**New developer?** Start with [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for quickstart and onboarding. For architecture deep dive, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What is Groot?

Groot is the AI that lives in REFINET Cloud. Talk to it at `app.refinet.io`. By default it runs on BitNet b1.58 2B4T — a 1-bit open-source LLM that runs natively on CPU. No GPU required. No subscription. No vendor lock-in.

Groot also connects to **any AI provider** through the Universal Model Gateway: Google Gemini (free tier), Ollama, LM Studio, OpenRouter, and user-provided keys for OpenAI, Anthropic, Groq, Mistral, Replicate, Stability AI, Together AI, Perplexity, and more. Switch models in the chat header or bring your own API keys in Settings.

Groot is a **Wizard** — an agent with a wallet and the ability to act on-chain. It is the **sole Wizard** in the REFINET ecosystem. Users interact with GROOT to deploy contracts, query on-chain state, and request transactions. GROOT never acts alone — every on-chain action requires **master_admin** approval.

Groot is augmented with two knowledge systems:
- **RAG** (Retrieval-Augmented Generation) — searches a curated knowledge base of documents, PDFs, spreadsheets, and markdown before every response
- **CAG** (Contract-Augmented Generation) — searches public smart contract ABIs and SDK definitions for blockchain-aware answers. Three access modes:
  - **Query** — search public SDKs to answer questions (autonomous)
  - **Execute** — call view/pure functions on-chain to read state (autonomous, no gas)
  - **Act** — request state-changing transactions (creates PendingAction for master_admin approval)

## Products

REFINET Cloud ships 4 downloadable products — all open source, all free.

| Product | Description | Status |
|---|---|---|
| [REFINET Browser](https://github.com/circularityglobal/REFINET-BROWSER) | Privacy browser with decentralized DNS, encrypted transit, and GROOT AI sidebar | Coming Soon |
| [REFINET Pillars](https://github.com/circularityglobal/REFINET-PILLARS) | Sovereign infrastructure: encrypted mesh, anonymized routing, Gopher protocol, vault | **Available v0.3.0** |
| [WizardOS](https://github.com/circularityglobal/CIFI-WIZARDOS) | Desktop AI OS powered by GROOT — agents, personalities, local memory | Coming Soon |
| REFINET Cluster | Distributed GROOT nodes on Oracle Cloud ARM (Always Free tier) | **Available** |

Product pages at `www.refinet.io/products/`. Downloads require name + email (lead capture), wallet address auto-pulled if connected. All leads stored with 384-dim semantic embeddings for analytics.

## Platform Features

### AI Inference (Multi-Provider)
- OpenAI-compatible API (`POST /v1/chat/completions`)
- Universal Model Gateway: BitNet (sovereign), Gemini, Ollama, LM Studio, OpenRouter
- BYOK (Bring Your Own Key): Connect OpenAI, Anthropic, Groq, Mistral, Replicate, Stability, Together, Perplexity, or any OpenAI-compatible endpoint
- Streaming SSE responses with provider-agnostic normalization
- RAG + CAG context injection (works identically across all providers)
- Google Search grounding for Gemini models
- Automatic fallback chain when providers are unavailable
- Anonymous access (25 req/day) and authenticated tiers (250+ req/day)

### Agent Engine
- Autonomous multi-agent platform with persistent identity (SOUL.md)
- 6-phase cognitive loop: PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE
- 7-layer context injection stack with token budget tracking (SOUL, agent, memory, RAG, skills, safety, runtime)
- 4-tier memory system: Working (TTL), Episodic (events), Semantic (facts + embeddings), Procedural (strategies)
- Trigger router: automatic event→agent task routing from 7 sources (heartbeat, cron, webhook, chain, messenger, pipeline, broker)
- Output router: multi-target result routing (DB, response, memory, agent chaining, webhook)
- Tool access via MCP gateway with glob-pattern permissions
- Agent-to-agent delegation with configurable policies (none/approve/auto)
- Pipeline dispatch: agents can trigger `deploy_contract`, `compile_contract`, and `compile_test` actions that create DAG-coordinated worker pipelines
- JSONL episodic audit trail alongside DB storage
- 10 built-in archetypes: groot-chat, contract-analyst, knowledge-curator, platform-ops, dapp-builder, device-monitor, contract-watcher, onboarding, maintenance, orchestrator
- YAML configuration hierarchy (default → production → ENV)

### Wizard Pipeline (DAG Orchestrator)
- **GROOT is the sole Wizard** — all deployments are signed by GROOT's SSS-secured wallet
- Full wizard pipeline: Compile → Test → Parse → RBAC → Deploy → Re-Parse → Frontend → App Store
- **Parallel execution**: frontend generation runs alongside deployment approval (both depend on parse, not each other)
- 4 pipeline templates: `compile_test`, `deploy`, `full`, `wizard` (source code → live DApp)
- 9 deterministic workers: compile (Hardhat/solc), test (static analysis + Hardhat), parse (ABI → SDK), RBAC check (tier-based + PendingAction), deploy (GROOT wallet signs), verify (block explorer), transfer ownership, frontend (DApp generation), appstore (submission)
- Master admin approval gates for all Tier 2 actions (deploy, transfer, state-changing calls)
- Pipeline state tracking with per-step status, input/output, and error capture
- EventBus integration: `pipeline.step.completed`, `pipeline.run.completed`, `pipeline.approval.needed`

### Contract Deployment & Ownership
- GROOT deploys every contract using its sole wallet — users never need gas
- Track every contract GROOT deploys on-chain (DeploymentRecord)
- On-chain ownership verification via `owner()` call
- Ownership transfer from GROOT's wallet to user's personal wallet
- **Dynamic chain registry** — admin can add any EVM chain via chainlist.org from the dashboard
- **Multi-chain contract deployments** — one ABI can be deployed on Ethereum, Base, Polygon, Arbitrum, and more
- Supported chains seeded at startup; new chains added dynamically via `POST /admin/chains/import`

### Smart Contract Registry
- GitHub-style project management (create, star, fork)
- ABI upload, parsing, and verification
- Automatic function/event extraction with access control detection
- **Automated ABI security scanning** — 8 dangerous pattern categories (delegatecall, selfdestruct, tx.origin, unchecked call, infinite approval, inline assembly, proxy patterns, ownership transfer) with severity classification (CRITICAL/HIGH/MEDIUM)
- Security flags persisted to `contract_security_flags` table and exposed via `GET /registry/abis/{id}/security-flags`
- SDK generation from parsed ABIs
- Public explorer for discovering contracts across chains
- Tag taxonomy: 11 categories (DeFi, Token, Governance, NFT, Security, Oracle, Identity, Payment, Infrastructure, Gaming, ReFi) with 95 subcategories
- Tag-based search and auto-suggestion from ABI function signatures
- Categories: DeFi, Token, Governance, Bridge, Utility, Oracle, NFT, DAO, SDK, Library

### GROOT Brain (Personal Contract Repository)
- Per-user contract namespace (`@username`)
- Upload Solidity/Vyper/Rust/Move contracts
- ABI parsing with dangerous operation flagging (delegatecall, selfdestruct)
- Per-function SDK enable/disable
- Source code privacy — GROOT never reads source code, only ABIs and SDKs

### DApp Factory
- Template-based DApp assembly from registry contracts
- Pre-built templates: simple-dashboard, token-manager, staking-ui, governance-voting
- Configurable chain, contract address, and ABI settings
- Build validation: npm install + TypeScript type-checking in sandbox
- Self-repair loop: feeds TypeScript errors back through agent cognitive loop for auto-fix
- Downloadable project output (ZIP) for local customization

### App Store
- Publish and discover DApps, agents, tools, templates, datasets, API services, and digital assets
- Apple/Google-style submission pipeline: draft → upload → review → sandbox testing → admin approval → published
- Docker sandbox review with network isolation and resource limits
- Category-based browsing with ratings and install tracking
- Price types: free, one-time, subscription with license enforcement
- Version management with changelogs
- Developer profiles and publishing workflow

### Payment & Revenue System
- Fee schedules with tier-based discounts (free/developer/pro/admin)
- Three-token payment tracking: CIFI, USDC, REFI (with on-chain tx hash verification)
- Revenue splits: configurable platform/developer/broker percentages (must sum to 100%)
- Subscription management with period tracking and tier upgrades
- Admin revenue dashboard with total revenue, platform fees, and payment counts

### Broker System
- Brokered sessions: GROOT intermediates between service providers and consumers
- Service types: deploy, audit, consult, custom
- Session lifecycle: requested → active → completed (with cancellation)
- Integrated with messaging (auto-creates conversation per session)
- Integrated with payments (fee deduction + revenue split on completion)
- XMTP-aware: protocol wrapper with internal messaging fallback until XMTP infra is live

### Chain Listener
- On-chain event monitoring for EVM-compatible chains
- Configurable event filters by contract address, event signature, and chain
- Webhook-triggered backend actions on blockchain events
- Block tracking and reorg handling

### Multi-Chain Wallet Identity
- Wallet records per chain with pseudo-IPv6 network addresses
- ENS resolution (name, avatar, text records) with caching
- Email alias generation (`<hash>@cifi.global`)
- Multi-chain support: Ethereum, Polygon, Arbitrum, Optimism, Base, Sepolia
- Custodial wallet creation with Shamir Secret Sharing (5-of-3 threshold)

### Messaging
- Wallet-to-wallet direct messages and group conversations
- Email alias routing (SMTP bridge on port 8025)
- Messenger bridge for cross-platform message relay
- Typing indicators and read receipts
- P2P presence and peer discovery with gossip protocol

### Knowledge Base
- Multi-format upload: PDF, DOCX, XLSX, CSV, TXT, Markdown, JSON, Solidity
- Auto-chunking with sentence-transformer embeddings (384-dim)
- Hybrid search: semantic similarity + keyword scoring + FTS5 full-text indexing
- Document comparison, timeline extraction, auto-tagging
- YouTube transcript and URL ingestion

### 6-Protocol MCP Gateway
- **REST** — FastAPI with 287 endpoints across 27 route groups
- **GraphQL** — Strawberry GraphQL at `/graphql`
- **gRPC** — Port 50051 with registry service methods
- **SOAP** — Spyne at `/soap` via WSGI middleware
- **WebSocket** — Real-time event subscriptions at `/ws`
- **Webhooks** — HMAC-SHA256 signed payloads with exponential backoff retry

### Device & Agent Connectivity
- IoT/PLC/DLT device registration with telemetry ingestion
- ECDSA signature verification for telemetry
- Product agent management (QuickCast, AgentOS)
- Remote configuration distribution

### Task Scheduler & Script Runner
- Cron-like scheduled task execution with configurable intervals
- Health monitoring, P2P cleanup, auth cleanup, agent memory cleanup
- Safe script execution engine with category-based access control
- 36 operational scripts across 6 categories: analysis (4), chain (3), DApp (5), maintenance (10), ops (10), seed (4)

### Autonomous Agent Pipeline (3 Skills Installed)
- **Platform Ops** (`skills/refinet-platform-ops/`) — Autonomous monitoring, health checks, admin email alerts, agent pipeline orchestration
- **Knowledge Curator** (`skills/refinet-knowledge-curator/`) — RAG/CAG intelligence maintenance: orphan detection, stale chunk pruning, CAG sync, embedding drift detection, daily digest emails
- **Contract Watcher** (`skills/refinet-contract-watcher/`) — On-chain intelligence: ABI security scanning (8 dangerous patterns), event interpretation, contract activity monitoring, cross-chain bridge correlation, weekly chain reports
- Zero-cost 4-tier LLM fallback chain: Claude Code CLI (`claude -p`) → Ollama (phi3/llama3) → BitNet b1.58 → Gemini Flash (all free, no paid API calls)
- 7-layer context injection stack: SOUL → Safety → Agent Config → Working Memory → Episodic Memory → Task
- Persistent file-based agent memory: `memory/{working,episodic,semantic,procedural}/`
- 15 cron-driven autonomous tasks across 3 agents
- GitHub Actions workflows for all 3 agents (zero-cost CI/CD scheduling, 2000 min/month free)

## For Users

Visit `app.refinet.io` and start chatting. No account required for basic use. Connect your Ethereum wallet via SIWE (Sign-In with Ethereum) for full access including messaging, contract registry, and API keys.

## For Developers

REFINET Cloud exposes an OpenAI-compatible API. Change your base URL to `https://api.refinet.io/v1` and use your existing SDK.

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.refinet.io/v1",
    api_key="rf_your_key_here"
)

response = client.chat.completions.create(
    model="bitnet-b1.58-2b",  # or "gemini-2.0-flash", "gpt-4o", "claude-sonnet-4-6", etc.
    messages=[{"role": "user", "content": "Hello, Groot"}]
)
```

### API Surface (302+ endpoints across 29 route groups)

| Route Group | Endpoints | Auth |
|---|---|---|
| `/health`, `/` | 3 | No |
| `/auth/*` | 19 | Varies |
| `/v1/*` | 2 | JWT or API key |
| `/devices/*` | 9 | JWT or device key |
| `/agents/*` | 15 | JWT or build key |
| `/webhooks/*` | 7 | JWT |
| `/mcp/*` | 3 | JWT |
| `/keys/*` | 5 | Full Auth (SIWE+Password+TOTP) |
| `/provider-keys/*` | 6 | Full Auth (SIWE+Password+TOTP) |
| `/knowledge/*` | 36 | Admin (write), any (search) |
| `/admin/*` | 55 | Admin role (wallet/chains: master_admin) |
| `/registry/*` | 28 | JWT |
| `/repo/*` | 14 | JWT |
| `/explore/*` | 8 | No (cag/act requires JWT) |
| `/identity/*` | 9 | JWT |
| `/messages/*` | 9 | JWT |
| `/p2p/*` | 12 | JWT |
| `/chain/*` | 4 | JWT |
| `/dapp/*` | 6 | JWT |
| `/submissions/*` | 8 | JWT |
| `/app-store/*` | 12 | JWT |
| `/pipeline/*` | 10 | JWT (approvals: master_admin) |
| `/workers/*` | 7 | JWT (deploy/rbac/verify: master_admin) |
| `/deployments/*` | 4 | JWT |
| `/payments/*` | 10 | JWT (admin for fee config) |
| `/broker/*` | 6 | JWT |
| `/vector-memory/*` | 5 | JWT |
| `/graphql` | 1 | JWT or API key |
| `/soap` | 1 | JWT or API key |
| `/ws` | 1 | JWT or API key |

## For Agents

QuickCast, AgentOS, and any REFINET product connects to REFINET Cloud as its default LLM provider. Agents authenticate with build keys and register via `POST /agents`. The Agent Engine enables autonomous operation with SOUL.md identity, 4-tier memory, tool access, and agent-to-agent delegation. Agents can also dispatch wizard pipelines to compile, test, and deploy smart contracts. See [docs/AGENT_ENGINE.md](docs/AGENT_ENGINE.md) for the full architecture.

## For Devices

Any device that can send HTTP POST requests can register, send telemetry, and receive commands. IoT sensors, PLCs, DLT nodes, and webhook-connected services all connect through the same standardized protocol.

## Security

### Authentication (SIWE-First)
- **Primary**: Sign-In with Ethereum (EIP-4361) — native multi-wallet (MetaMask, Coinbase, Brave, Phantom, all EIP-6963 injected wallets)
- **Optional**: Password (Argon2id, per-user salt, server pepper)
- **Optional**: TOTP 2FA via QR code (Google Authenticator compatible)

### Authorization
- JWT with scope-based access control (12 scope types)
- API keys with per-key rate limits and expiration
- Role-based admin access: **master_admin** (GROOT wallet + approvals), admin, operator, readonly
- **Master admin** has exclusive control over GROOT's wallet, Tier 2 approvals, and chain management
- Tier-based access control (free, developer, pro, admin) with pipeline RBAC enforcement
- Admin secret header (`X-Admin-Secret`) audited in admin_audit_log — does NOT bypass master_admin gates

### Data Protection
- Dual-database architecture: `public.db` (user data) + `internal.db` (admin/secrets)
- AES-256-GCM encryption for secrets, TOTP keys, wallet shares, and external provider keys
- Custodial wallet keys split via Shamir Secret Sharing (5-of-3 threshold)
- Private key memory zeroing after use (ctypes.memset)
- **BYOK Security Gate**: Creating API keys or saving external provider keys requires completion of all 3 auth layers (SIWE + Password + TOTP). Incomplete layers return HTTP 403 with specific guidance.
- Append-only audit log — no delete or update routes exist
- Unified protocol authentication across all 6 protocols

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI 0.115.x + SQLAlchemy 2.0 + SQLite (WAL, dual DB, 80 tables across 11 model files) |
| Inference | BitNet b1.58 2B4T via bitnet.cpp (CPU-native, ARM-optimized) |
| Agent Engine | 6-phase cognitive loop + 5-tier memory + SOUL.md identity + MCP tool dispatch + CAG |
| Wizard Pipeline | DAG orchestrator + 9 workers + parallel execution + PendingAction approval gates |
| Frontend | Next.js 14 App Router + React 18 + TypeScript + Tailwind CSS |
| Web3 | wagmi + viem (native wallet connectors, SIWE) + web3.py + eth-account (backend) |
| Auth | Argon2id + PyJWT + pyotp + SIWE (EIP-4361) |
| Encryption | cryptography (AES-256-GCM, HKDF, Shamir SSS) |
| Embeddings | sentence-transformers (384-dim, semantic search) + FTS5 full-text indexing |
| Protocols | REST + GraphQL (Strawberry) + gRPC + SOAP (Spyne) + WebSocket + Webhooks |
| Scheduler | Background task scheduler with health monitoring + script runner |
| TLS | Let's Encrypt via Certbot |
| Server | Oracle Cloud ARM A1 Flex (4 OCPUs, 24GB RAM, 200GB storage) |

## Testing

```bash
# Run full test suite (270 pass)
python3 -m pytest api/tests/ skills/tests/ -v

# Run API tests only (214 pass)
python3 -m pytest api/tests/ -v

# Run skills pipeline tests only (56 pass)
python3 -m pytest skills/tests/ -v

# Run agent engine tests only (18/18 pass)
python3 -m pytest api/tests/test_agent_engine.py -v

# Run standalone skill health checks against real DB
DATABASE_PATH=data/public.db python3 skills/refinet-platform-ops/scripts/health_check.py
DATABASE_PATH=data/public.db python3 skills/refinet-knowledge-curator/scripts/knowledge_health.py
DATABASE_PATH=data/public.db python3 skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis
```

Test coverage: **270 passing tests** across 16 test files (12 API + 4 skills). The skills test suite validates the full autonomous pipeline: platform-ops → knowledge-curator → contract-watcher, including all 8 ABI dangerous pattern detections, orphan/stale chunk detection, report formatting, and sequential pipeline execution.

## Documentation

| Document | Description |
|---|---|
| [GROOT.md](GROOT.md) | Master architecture document — constraints, stack, subsystems, cardinal rules |
| [docs/REFINET_CLOUD_TECHNICAL_SPECIFICATION.md](docs/REFINET_CLOUD_TECHNICAL_SPECIFICATION.md) | Full technical specification — infrastructure, database, auth, protocols |
| [docs/GROOT_INTELLIGENCE_WHITEPAPER.md](docs/GROOT_INTELLIGENCE_WHITEPAPER.md) | GROOT Intelligence whitepaper — capabilities, science, vision |
| [docs/AGENT_ENGINE.md](docs/AGENT_ENGINE.md) | Agent Engine architecture — SOUL identity, memory, cognitive loop, tools |
| [docs/AGENTS.md](docs/AGENTS.md) | Built-in agent archetypes — groot-chat, contract-analyst, knowledge-curator, platform-ops, dapp-builder |
| [docs/SOUL_FORMAT.md](docs/SOUL_FORMAT.md) | SOUL.md format specification — agent identity, goals, constraints, tools, delegation |
| [docs/SAFETY.md](docs/SAFETY.md) | Platform-wide agent safety constraints — hard rules all agents must respect |
| [docs/HEARTBEAT.md](docs/HEARTBEAT.md) | System heartbeat protocol — health checks, scheduled tasks, uptime tracking |
| [docs/APP_STORE.md](docs/APP_STORE.md) | App Store submission pipeline — sandbox, review, approval |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Complete API reference — all endpoints, schemas, auth requirements |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Developer quickstart, project structure, key concepts |
| [skills/refinet-platform-ops/SKILL.md](skills/refinet-platform-ops/SKILL.md) | Platform ops skill — autonomous monitoring, health checks, agent pipeline |
| [skills/refinet-knowledge-curator/SKILL.md](skills/refinet-knowledge-curator/SKILL.md) | Knowledge curator skill — RAG/CAG maintenance and drift detection |
| [skills/refinet-contract-watcher/SKILL.md](skills/refinet-contract-watcher/SKILL.md) | Contract watcher skill — on-chain intelligence and ABI security |
| [docs/KNOWLEDGE_CURATOR_SETUP.md](docs/KNOWLEDGE_CURATOR_SETUP.md) | Knowledge curator setup guide |
| [docs/CONTRACT_WATCHER_SETUP.md](docs/CONTRACT_WATCHER_SETUP.md) | Contract watcher setup guide |
| [DEPLOY_ORACLE_CLOUD.md](DEPLOY_ORACLE_CLOUD.md) | Step-by-step Oracle Cloud ARM deployment |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |

## Infrastructure

Runs entirely on Oracle Cloud Always Free tier. One ARM A1 Flex instance. Zero recurring cost. Sovereign data. No telemetry to third parties.

## License

AGPL-3.0 — Free as in freedom, and free as in beer.
