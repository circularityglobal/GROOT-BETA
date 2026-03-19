# REFINET Cloud

**Grass Root Project Intelligence**

REFINET Cloud is the sovereign cloud infrastructure for the Regenerative Finance Network. It provides free, OpenAI-compatible AI inference powered by BitNet, a GitHub-style smart contract registry, wallet-to-wallet encrypted messaging, multi-chain identity management, IoT device connectivity, and a 6-protocol MCP gateway — all running on permanently free infrastructure with zero recurring costs.

## What is Groot?

Groot is the AI that lives in REFINET Cloud. Talk to it at `app.refinet.io`. It runs on BitNet b1.58 2B4T — a 1-bit open-source LLM that runs natively on CPU. No GPU required. No subscription. No vendor lock-in.

Groot is augmented with two knowledge systems:
- **RAG** (Retrieval-Augmented Generation) — searches a curated knowledge base of documents, PDFs, spreadsheets, and markdown before every response
- **CAG** (Contract-Augmented Generation) — searches user-uploaded smart contract ABIs and SDK definitions for blockchain-aware answers

## Platform Features

### AI Inference
- OpenAI-compatible API (`POST /v1/chat/completions`)
- Streaming SSE responses
- RAG + CAG context injection
- Anonymous access (25 req/day) and authenticated tiers (250+ req/day)

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

### Multi-Chain Wallet Identity
- Wallet records per chain with pseudo-IPv6 network addresses
- ENS resolution (name, avatar, text records) with caching
- Email alias generation (`<hash>@cifi.global`)
- Multi-chain support: Ethereum, Polygon, Arbitrum, Optimism, Base, Sepolia
- Custodial wallet creation with Shamir Secret Sharing (5-of-3 threshold)

### Messaging
- Wallet-to-wallet direct messages and group conversations
- Email alias routing (SMTP bridge on port 8025)
- Typing indicators and read receipts
- P2P presence and peer discovery with gossip protocol

### Knowledge Base
- Multi-format upload: PDF, DOCX, XLSX, CSV, TXT, Markdown, JSON, Solidity
- Auto-chunking with sentence-transformer embeddings (384-dim)
- Hybrid search: semantic similarity + keyword scoring
- Document comparison, timeline extraction, auto-tagging
- YouTube transcript and URL ingestion

### 6-Protocol MCP Gateway
- **REST** — FastAPI with 100+ endpoints across 17 route groups
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
    model="bitnet-b1.58-2b",
    messages=[{"role": "user", "content": "Hello, Groot"}]
)
```

### API Surface (100+ endpoints)

| Route Group | Endpoints | Auth |
|---|---|---|
| `/health`, `/` | 2 | No |
| `/auth/*` | 19 | Varies |
| `/v1/*` | 3 | JWT or API key |
| `/devices/*` | 6 | JWT or device key |
| `/agents/*` | 4 | JWT or build key |
| `/webhooks/*` | 5 | JWT |
| `/mcp/*` | 3 | JWT |
| `/keys/*` | 4 | JWT |
| `/knowledge/*` | 5+ | Admin (write), any (search) |
| `/admin/*` | 14+ | Admin role |
| `/registry/*` | 12+ | JWT |
| `/repo/*` | 8+ | JWT |
| `/explore/*` | 4 | No |
| `/identity/*` | 4+ | JWT |
| `/messages/*` | 8+ | JWT |
| `/p2p/*` | 3 | JWT |
| `/graphql` | 1 | JWT or API key |
| `/soap` | 1 | JWT or API key |
| `/ws` | 1 | JWT or API key |

## For Agents

QuickCast, AgentOS, and any REFINET product connects to REFINET Cloud as its default LLM provider. Agents authenticate with build keys and register via `POST /agents`.

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
- AES-256-GCM encryption for secrets, TOTP keys, and wallet shares
- Custodial wallet keys split via Shamir Secret Sharing (5-of-3 threshold)
- Append-only audit log — no delete or update routes exist
- Unified protocol authentication across all 6 protocols

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI 0.115.x + SQLAlchemy 2.0 + SQLite (WAL, dual DB) |
| Inference | BitNet b1.58 2B4T via bitnet.cpp (CPU-native, ARM-optimized) |
| Frontend | Next.js 14 App Router + React 18 + TypeScript + Tailwind CSS |
| Web3 | wagmi + viem (native wallet connectors, no WalletConnect) + web3.py + eth-account (backend) |
| Auth | Argon2id + PyJWT + pyotp + SIWE (EIP-4361) |
| Encryption | cryptography (AES-256-GCM, HKDF, Shamir SSS) |
| Embeddings | sentence-transformers (384-dim, semantic search) |
| Protocols | REST + GraphQL (Strawberry) + gRPC + SOAP (Spyne) + WebSocket + Webhooks |
| TLS | Let's Encrypt via Certbot |
| Server | Oracle Cloud ARM A1 Flex (4 OCPUs, 24GB RAM, 200GB storage) |

## Infrastructure

Runs entirely on Oracle Cloud Always Free tier. One ARM A1 Flex instance. Zero recurring cost. Sovereign data. No telemetry to third parties.

## License

AGPL-3.0 — Free as in freedom, and free as in beer.
