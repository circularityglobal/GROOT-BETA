# REFINET Cloud

**Grass Root Project Intelligence**

REFINET Cloud is the sovereign cloud infrastructure for the Regenerative Finance Network. It provides free, OpenAI-compatible AI inference powered by BitNet, a multi-agent autonomous engine, a GitHub-style smart contract registry, DApp factory, app store, wallet-to-wallet encrypted messaging, multi-chain identity management, on-chain event automation, IoT device connectivity, and a 6-protocol MCP gateway — all running on permanently free infrastructure with zero recurring costs.

**New developer?** Start with [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for quickstart and onboarding. For architecture deep dive, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What is Groot?

Groot is the AI that lives in REFINET Cloud. Talk to it at `app.refinet.io`. By default it runs on BitNet b1.58 2B4T — a 1-bit open-source LLM that runs natively on CPU. No GPU required. No subscription. No vendor lock-in.

Groot also connects to **any AI provider** through the Universal Model Gateway: Google Gemini (free tier), Ollama, LM Studio, OpenRouter, and user-provided keys for OpenAI, Anthropic, Groq, Mistral, Replicate, Stability AI, Together AI, Perplexity, and more. Switch models in the chat header or bring your own API keys in Settings.

Groot is augmented with two knowledge systems:
- **RAG** (Retrieval-Augmented Generation) — searches a curated knowledge base of documents, PDFs, spreadsheets, and markdown before every response
- **CAG** (Contract-Augmented Generation) — searches user-uploaded smart contract ABIs and SDK definitions for blockchain-aware answers

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
- Trigger router: automatic event→agent task routing from 5 sources (heartbeat, cron, webhook, chain, messenger)
- Output router: multi-target result routing (DB, response, memory, agent chaining, webhook)
- Tool access via MCP gateway with glob-pattern permissions
- Agent-to-agent delegation with configurable policies (none/approve/auto)
- JSONL episodic audit trail alongside DB storage
- 10 built-in archetypes: groot-chat, contract-analyst, knowledge-curator, platform-ops, dapp-builder, device-monitor, contract-watcher, onboarding, maintenance, orchestrator
- YAML configuration hierarchy (default → production → ENV)

### Smart Contract Registry
- GitHub-style project management (create, star, fork)
- ABI upload, parsing, and verification
- Automatic function/event extraction with access control detection
- SDK generation from parsed ABIs
- Public explorer for discovering contracts across chains
- Categories: DeFi, Token, Governance, Bridge, Utility, Oracle, NFT, DAO, SDK, Library

### GROOT Brain (Personal Contract Repository)
- Per-user contract namespace (`@username`)
- Upload Solidity/Vyper/Rust/Move contracts
- ABI parsing with dangerous operation flagging (delegatecall, selfdestruct)
- Per-function SDK enable/disable
- Source code privacy — GROOT never reads source code, only ABIs and SDKs

### DApp Factory
- Template-based DApp assembly from registry contracts
- Pre-built templates: token-dashboard, nft-gallery, staking-ui, dao-voter, multi-send
- Configurable chain, contract address, and ABI settings
- Downloadable project output (ZIP) for local customization

### App Store
- Publish and discover DApps, agents, tools, and templates
- Category-based browsing with ratings and install tracking
- Version management with changelogs
- Developer profiles and publishing workflow

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
- **REST** — FastAPI with 210+ endpoints across 22 route groups
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
- 23 operational scripts: analysis, maintenance, ops, chain, DApp utilities

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

### API Surface (210+ endpoints across 22 route groups)

| Route Group | Endpoints | Auth |
|---|---|---|
| `/health`, `/` | 2 | No |
| `/auth/*` | 19 | Varies |
| `/v1/*` | 3 | JWT or API key |
| `/devices/*` | 6 | JWT or device key |
| `/agents/*` | 12+ | JWT or build key |
| `/webhooks/*` | 5 | JWT |
| `/mcp/*` | 3 | JWT |
| `/keys/*` | 5 | Full Auth (SIWE+Password+TOTP) |
| `/provider-keys/*` | 6 | Full Auth (SIWE+Password+TOTP) |
| `/knowledge/*` | 5+ | Admin (write), any (search) |
| `/admin/*` | 14+ | Admin role |
| `/registry/*` | 12+ | JWT |
| `/repo/*` | 8+ | JWT |
| `/explore/*` | 4 | No |
| `/identity/*` | 4+ | JWT |
| `/messages/*` | 8+ | JWT |
| `/p2p/*` | 3 | JWT |
| `/chain/*` | 6+ | JWT |
| `/dapp/*` | 5+ | JWT |
| `/app-store/*` | 8+ | JWT |
| `/graphql` | 1 | JWT or API key |
| `/soap` | 1 | JWT or API key |
| `/ws` | 1 | JWT or API key |

## For Agents

QuickCast, AgentOS, and any REFINET product connects to REFINET Cloud as its default LLM provider. Agents authenticate with build keys and register via `POST /agents`. The Agent Engine enables autonomous operation with SOUL.md identity, 4-tier memory, tool access, and agent-to-agent delegation. See [docs/AGENT_ENGINE.md](docs/AGENT_ENGINE.md) for the full architecture.

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
- Role-based admin access (admin, operator, readonly)

### Data Protection
- Dual-database architecture: `public.db` (user data) + `internal.db` (admin/secrets)
- AES-256-GCM encryption for secrets, TOTP keys, wallet shares, and external provider keys
- Custodial wallet keys split via Shamir Secret Sharing (5-of-3 threshold)
- **BYOK Security Gate**: Creating API keys or saving external provider keys requires completion of all 3 auth layers (SIWE + Password + TOTP). Incomplete layers return HTTP 403 with specific guidance.
- Append-only audit log — no delete or update routes exist
- Unified protocol authentication across all 6 protocols

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI 0.115.x + SQLAlchemy 2.0 + SQLite (WAL, dual DB) |
| Inference | BitNet b1.58 2B4T via bitnet.cpp (CPU-native, ARM-optimized) |
| Agent Engine | 6-phase cognitive loop + 4-tier memory + SOUL.md identity + MCP tool dispatch |
| Frontend | Next.js 14 App Router + React 18 + TypeScript + Tailwind CSS |
| Web3 | wagmi + viem (native wallet connectors, SIWE) + web3.py + eth-account (backend) |
| Auth | Argon2id + PyJWT + pyotp + SIWE (EIP-4361) |
| Encryption | cryptography (AES-256-GCM, HKDF, Shamir SSS) |
| Embeddings | sentence-transformers (384-dim, semantic search) + FTS5 full-text indexing |
| Protocols | REST + GraphQL (Strawberry) + gRPC + SOAP (Spyne) + WebSocket + Webhooks |
| Scheduler | Background task scheduler with health monitoring + script runner |
| TLS | Let's Encrypt via Certbot |
| Server | Oracle Cloud ARM A1 Flex (4 OCPUs, 24GB RAM, 200GB storage) |

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
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Complete API reference — all endpoints, schemas, auth requirements, tested examples |

## Infrastructure

Runs entirely on Oracle Cloud Always Free tier. One ARM A1 Flex instance. Zero recurring cost. Sovereign data. No telemetry to third parties.

## License

AGPL-3.0 — Free as in freedom, and free as in beer.
