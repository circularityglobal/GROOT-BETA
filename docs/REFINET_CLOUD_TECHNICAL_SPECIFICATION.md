# REFINET Cloud: Architecture of a Zero-Cost Sovereign AI Platform
## Technical Specification · Internal Reference Document
### Version 2.0 · March 2026

---

## Abstract

This document describes the complete technical architecture of REFINET Cloud, a sovereign AI infrastructure platform that provides OpenAI-compatible inference, a GitHub-style smart contract registry, wallet-to-wallet messaging, multi-chain identity management, IoT device connectivity, and a 6-protocol MCP gateway — all operating within the permanent free-tier constraints of a single ARM cloud instance with zero recurring infrastructure costs.

The platform consists of twelve primary subsystems: (1) a 1-bit large language model inference server running natively on ARM CPU with RAG and CAG augmentation, (2) a dual-database persistence layer with 50+ tables across physically separated security domains, (3) a wallet-first authentication system with SIWE, optional password/TOTP, and custodial wallet support via Shamir Secret Sharing, (4) a smart contract registry with ABI parsing, SDK generation, and public exploration, (5) a wallet-to-wallet messaging system with P2P presence, email bridging, and group conversations, (6) a multi-chain identity layer with ENS resolution and pseudo-IPv6 addressing, (7) a 6-protocol MCP gateway supporting REST, GraphQL, gRPC, SOAP, WebSocket, and Webhooks, (8) an autonomous multi-agent engine with persistent identity, 4-tier memory, and tool access, (9) a DApp factory with template-based assembly, (10) an app store for publishing and discovering platform extensions, (11) an on-chain event listener for blockchain automation, and (12) a task scheduler with safe script execution.

This document is intended for internal engineering reference, security audit, and academic evaluation.

---

## 1. Infrastructure Constraints and Design Principles

### 1.1 — Hardware Allocation

The entire platform operates on a single Oracle Cloud Infrastructure (OCI) Always Free VM.Standard.A1.Flex instance:

| Resource | Allocation | Usage |
|---|---|---|
| Compute | 4 x Ampere Altra Neoverse-N1 OCPUs @ 3.0 GHz | Inference + API + gRPC + proxy |
| Memory | 24 GB DDR4 | Model (~0.5GB) + application (~2.1GB) + embeddings (~0.3GB) + OS (~0.8GB) |
| Block storage | 200 GB | OS + databases + model weights + knowledge base + embeddings |
| Network egress | 10 TB/month | API responses + webhook delivery + SSE streams + WebSocket |
| Object storage | 20 GB | Model weight backups, static asset origin |
| Public IPv4 | 1 static address | DNS A record for API, frontend, and product subdomains |

The Always Free tier is a permanent allocation — not a trial. Oracle has maintained this tier since May 2021. The platform is designed so that all resource consumption fits within these bounds at projected capacity.

### 1.2 — Design Constraints

Four constraints govern every architectural decision:

**C1: Zero recurring cost.** No paid services, subscriptions, API fees, or licensing costs. Every dependency must be open-source or permanently free.

**C2: Sovereign data.** All user data, telemetry, secrets, and operational state stored on REFINET-controlled infrastructure. No external analytics, no third-party data processors, no telemetry SDKs.

**C3: Wallet-first authentication.** SIWE (Sign-In with Ethereum) as the primary authentication method, with optional password and TOTP layers. Multi-chain support across 6 EVM networks.

**C4: Universal connectivity.** Any device capable of HTTP POST can participate. Six protocol adapters (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks) ensure no protocol lock-in.

---

## 2. Process Architecture

All services run on a single machine, managed by systemd, communicating over localhost.

```
┌──────────────────────────────────────────────────────────────────┐
│                        EXTERNAL NETWORK                          │
│                  (ports 80, 443, 50051)                           │
└──────────────┬──────────────────────────────────────┬────────────┘
               │                                      │
          ┌────▼────┐                            ┌────▼────┐
          │  Nginx   │◄── TLS termination ──────►│ Certbot │
          │ :80/:443 │    Let's Encrypt           │ (timer) │
          └────┬─────┘                            └─────────┘
               │
               │ proxy_pass (HTTP/1.1, SSE, WebSocket passthrough)
               │
          ┌────▼──────────────────────────────────────────────┐
          │       FastAPI / Uvicorn                             │
          │       127.0.0.1:8000                               │
          │       2 ASGI workers                               │
          │                                                     │
          │  ┌──────────────┐  ┌────────────────────────────┐  │
          │  │ Auth Routes   │  │ Inference Route (RAG+CAG)  │  │
          │  │ (SIWE/JWT/    │  │ POST /v1/chat/completions  │  │
          │  │  API Keys)    │  │ GET /v1/models             │  │
          │  ├──────────────┤  ├────────────────────────────┤  │
          │  │ Registry      │  │ Knowledge Route            │  │
          │  │ Routes        │  │ (upload, search, compare)  │  │
          │  ├──────────────┤  ├────────────────────────────┤  │
          │  │ Repo Routes   │  │ Explore Routes             │  │
          │  │ (GROOT Brain) │  │ (public discovery)         │  │
          │  ├──────────────┤  ├────────────────────────────┤  │
          │  │ Messaging     │  │ Identity Routes            │  │
          │  │ Routes        │  │ (wallet identity, ENS)     │  │
          │  ├──────────────┤  ├────────────────────────────┤  │
          │  │ P2P Routes    │  │ Device Routes              │  │
          │  │ (presence,    │  │ (IoT, PLC, DLT)           │  │
          │  │  gossip)      │  │                            │  │
          │  ├──────────────┤  ├────────────────────────────┤  │
          │  │ Webhook       │  │ Admin Routes               │  │
          │  │ Routes        │  │ (role-gated, internal.db)  │  │
          │  ├──────────────┤  ├────────────────────────────┤  │
          │  │ MCP Routes    │  │ Keys / Agents Routes       │  │
          │  └──────────────┘  └────────────────────────────┘  │
          │                                                     │
          │  ┌───────────────────────────────────────────────┐  │
          │  │ Protocol Adapters                              │  │
          │  │ ├── GraphQL (Strawberry) → /graphql            │  │
          │  │ ├── SOAP (Spyne) → /soap                      │  │
          │  │ └── WebSocket → /ws                           │  │
          │  └───────────────────────────────────────────────┘  │
          │                                                     │
          │  ┌───────────────────────────────────────────────┐  │
          │  │ Background Workers                             │  │
          │  │ ├── TaskScheduler (10s tick)                   │  │
          │  │ │   ├── Health monitor (60s)                   │  │
          │  │ │   ├── P2P cleanup (60s)                      │  │
          │  │ │   ├── Auth cleanup (3600s)                   │  │
          │  │ │   └── Agent memory cleanup (300s)            │  │
          │  │ ├── Webhook delivery (async queue)             │  │
          │  │ ├── Chain listener (event polling)             │  │
          │  │ ├── Script runner (on-demand)                  │  │
          │  │ └── SMTP bridge (:8025)                       │  │
          │  └───────────────────────────────────────────────┘  │
          │         │              │             │              │
          │    ┌────▼────┐   ┌────▼────┐  ┌────▼────┐        │
          │    │public.db│   │internal │  │Embeddings│        │
          │    │(SQLite) │   │.db      │  │(sentence-│        │
          │    │WAL mode │   │(SQLite) │  │transform)│        │
          │    │ 40+ tbl │   │WAL mode │  │ 384-dim  │        │
          │    └─────────┘   │ 12+ tbl │  └──────────┘        │
          │                  └─────────┘                       │
          └────────────┬──────────────────┬───────────────────┘
                       │                  │
                       │ HTTP (localhost)  │ gRPC (:50051)
                       │                  │
          ┌────────────▼──────────┐  ┌───▼──────────────────┐
          │ bitnet.cpp/llama-server│  │ gRPC Server           │
          │ 127.0.0.1:8080        │  │ 127.0.0.1:50051       │
          │                       │  │                       │
          │ Model: BitNet b1.58   │  │ Services:             │
          │ Quantization: i2_s    │  │ ├── SearchProjects    │
          │ Context: 2048 tokens  │  │ ├── GetProject        │
          │ Threads: 4 OCPUs      │  │ ├── GetABI            │
          │ Memory: ~500 MB       │  │ ├── GetSDK            │
          └───────────────────────┘  │ └── GetExecutionLogic │
                                     └───────────────────────┘
```

Port 8080 (BitNet) is bound to 127.0.0.1 and blocked by UFW. Port 50051 (gRPC) runs alongside FastAPI. Port 8025 (SMTP bridge) is internal only. Port 22 (SSH) is key-only with fail2ban active.

---

## 3. Inference Subsystem

### 3.1 — Model Selection Rationale

BitNet b1.58 2B4T (Microsoft Research, April 2025) was selected for three properties:

1. **Native ternary training.** Weights are {-1, 0, +1} from initialization — not post-training quantized. This preserves model quality at extreme compression ratios. The model achieves parity with LLaMA 3.2 1B on standard benchmarks (ARC-Challenge 68.5%, HellaSwag 84.3%, MMLU 52.1%) while requiring 400MB of memory versus 2GB.

2. **CPU-native inference.** The bitnet.cpp framework replaces floating-point matrix multiplication with integer addition/subtraction via lookup table kernels (I2_S, TL1, TL2). On ARM Neoverse-N1 cores with 4 threads, the 2B model generates at approximately 20-30 tokens/second — sufficient for real-time conversational streaming.

3. **Open-source licensing.** Model weights released under MIT license. Inference framework released under MIT license. No usage restrictions, no API dependency, no cost per token.

### 3.2 — Inference Pipeline

```
User request
    │
    ▼
FastAPI route: POST /v1/chat/completions
    │
    ├── Authenticate (JWT, API key, or anonymous with IP rate limiting)
    │
    ├── _inject_rag_context()
    │   ├── Extract last user message
    │   ├── search_knowledge() → hybrid keyword + semantic scored chunk retrieval
    │   │   ├── Keyword scoring (SQL LIKE queries, max 8 terms)
    │   │   └── Semantic scoring (sentence-transformer cosine similarity, 384-dim)
    │   ├── search_contracts() → SDK definition retrieval from GROOT Brain
    │   │   ├── Keyword matching on name, description, logic_summary
    │   │   └── Chain filtering
    │   ├── build_groot_system_prompt() → assemble system prompt + RAG + CAG context
    │   └── Prepend system message to conversation
    │
    ├── Forward enriched messages to bitnet.cpp llama-server
    │   ├── Non-streaming: POST /completion → JSON response
    │   └── Streaming: POST /completion (stream=true) → SSE chunks
    │
    ├── Record usage (user_id, api_key_id, device_id, token counts, latency, endpoint)
    │
    └── Return OpenAI-compatible response
```

### 3.3 — RAG Implementation

Documents are ingested through `POST /knowledge/documents` (admin or authorized users). The ingestion pipeline:

1. Parse document content (PDF via PyMuPDF, DOCX via python-docx, XLSX via openpyxl, CSV, TXT, MD, JSON, Solidity)
2. Compute SHA-256 content hash for deduplication
3. Split document into overlapping chunks (target: 400 tokens/chunk, 50-token overlap at paragraph boundaries)
4. Generate sentence-transformer embeddings (384-dimensional) per chunk
5. Auto-tag documents using keyword extraction and category classification
6. Store full document in `knowledge_documents` table with metadata
7. Store each chunk in `knowledge_chunks` table with embeddings (JSON-serialized)

Retrieval at query time (hybrid search):

1. Decompose query into keywords (regex word extraction, limited to 8 terms)
2. Execute SQL LIKE queries against `knowledge_chunks.content` with OR conditions across keywords
3. Compute sentence-transformer embedding of query
4. Calculate cosine similarity between query embedding and stored chunk embeddings
5. Combine keyword score and semantic score with configurable weighting
6. Sort by combined score descending, return top-N chunks (default: 5)
7. For contract queries: parallel search against `sdk_definitions` table on name, description, and logic_summary fields

The assembled context is injected as a system message prefix. The model sees:

```
<|system|>
{GROOT_SYSTEM_PROMPT}

Use the following reference information...

=== REFINET Knowledge Base ===
[CATEGORY: Document Title]
{chunk content}

=== Smart Contract Reference ===
[CHAIN: Contract Name]
{description}
Logic: {logic_summary}
</s>
<|user|>
{user query}
</s>
<|assistant|>
```

### 3.4 — Throughput Analysis

| Metric | Value |
|---|---|
| Prompt evaluation | ~150 tok/s (batch, 4 threads) |
| Token generation | ~25 tok/s (sequential, 4 threads) |
| Avg. request (150 prompt + 256 completion) | ~11.2 seconds |
| Sequential throughput | ~5.3 req/min |
| Daily capacity (70% utilization) | ~5,400 requests |
| Memory per inference | ~500 MB (constant, model resident) |

The llama-server processes requests sequentially. Concurrent requests queue in the FastAPI application layer. Streaming delivery (SSE) provides perceived responsiveness even when requests are queued — users see the first token as soon as generation begins.

---

## 4. Database Architecture

### 4.1 — Dual-Database Separation

Two physically separate SQLite files in WAL (Write-Ahead Logging) mode:

**`/opt/refinet/data/public.db`** — User-facing data accessible through the API:

| Table | Purpose | Row estimate (1000 users) |
|---|---|---|
| **Core Auth** | | |
| users | Account records (email, username, wallet, tier, auth state) | 1,000 |
| api_keys | Scoped API credentials (rf_ prefix, SHA256 hashed) | 2,500 |
| siwe_nonces | One-time SIWE nonces (64-char hex, 10-min TTL) | 100 (active) |
| refresh_tokens | JWT refresh token hashes (rotation chain) | 2,000 |
| **Wallet Identity** | | |
| wallet_identities | Per-chain wallet records with pseudo-IPv6, ENS, email alias | 3,000 |
| wallet_sessions | Device-aware login tracking (IP, user-agent, fingerprint) | 5,000 |
| **Messaging** | | |
| conversations | DM and group chat containers | 2,000 |
| conversation_participants | Per-user read state, roles (member/admin/owner) | 5,000 |
| messages | Text/attachment/system messages with threading | 50,000 |
| email_aliases | Wallet-derived email registry for SMTP bridge | 1,000 |
| **Devices & Agents** | | |
| device_registrations | IoT/PLC/DLT/webhook devices with ETH address | 5,000 |
| agent_registrations | Product agents (QuickCast, AgentOS) with remote config | 500 |
| iot_telemetry | Raw sensor data with optional ECDSA signatures | 500,000 |
| **Events** | | |
| webhook_subscriptions | Event delivery endpoints (HMAC-SHA256 signed) | 1,000 |
| usage_records | Per-request telemetry (user, key, device, tokens, latency) | 150,000/month |
| **Knowledge Base** | | |
| knowledge_documents | Admin-managed RAG documents (categories, hashing, visibility) | 500 |
| knowledge_chunks | Searchable segments with 384-dim embeddings | 25,000 |
| document_shares | Document collaboration/sharing records | 200 |
| **Smart Contract Registry** | | |
| registry_projects | GitHub-style project containers (stars, forks, categories) | 1,000 |
| registry_abis | Contract ABI entries with verification | 2,000 |
| registry_sdks | SDK definitions per language | 500 |
| execution_logic | Function/workflow/script/hook/trigger definitions | 3,000 |
| registry_stars | User stars on projects | 5,000 |
| registry_forks | Fork tracking between projects | 200 |
| **GROOT Brain** | | |
| user_repositories | Per-user contract namespace (@username) | 1,000 |
| contract_repos | Individual smart contracts (slug, chain, language, ABI) | 5,000 |
| contract_functions | Parsed ABI functions (access, mutability, selectors, danger flags) | 25,000 |
| contract_events | Parsed ABI events (topic hashes, indexed params) | 10,000 |
| sdk_definitions | Generated SDK JSON (what GROOT reads and MCP exposes) | 5,000 |
| **Agent Engine** | | |
| agent_souls | SOUL.md identity documents per agent | 500 |
| agent_memory_working | Short-lived per-task context with TTL | 5,000 |
| agent_memory_episodic | Timestamped event records (what happened, outcome) | 50,000 |
| agent_memory_semantic | Learned facts with confidence scores + 384-dim embeddings | 10,000 |
| agent_memory_procedural | Strategy patterns with trigger conditions and success rates | 2,000 |
| agent_tasks | Task tracking (pending/running/completed/failed) with execution trace | 10,000 |
| agent_delegations | Delegation chains between agents | 1,000 |
| **DApp Factory** | | |
| dapp_builds | DApp assembly records (template, config, status, output) | 2,000 |
| **App Store** | | |
| app_listings | Published DApps, agents, tools, templates | 500 |
| app_installs | Per-user install tracking | 5,000 |
| app_reviews | User ratings and reviews | 2,000 |
| **Chain Listener** | | |
| chain_watchers | Configured on-chain event monitors | 500 |
| chain_events | Detected blockchain events with decoded parameters | 50,000 |
| **Messenger Bridge** | | |
| bridge_connections | Cross-platform messaging bridge configurations | 200 |

**`/opt/refinet/data/internal.db`** — Admin-only data, never accessible through any public API endpoint:

| Table | Purpose | Access |
|---|---|---|
| server_secrets | AES-256-GCM encrypted credentials with rotation tracking | Admin CLI + admin API |
| role_assignments | User → role mappings (admin/operator/readonly) | Admin CLI + admin API |
| admin_audit_log | Append-only action log (no update/delete routes exist) | Read-only via admin API |
| product_registry | Registered REFINET products + hashed build keys | Admin CLI |
| mcp_server_registry | MCP server URLs + encrypted auth, health tracking | Admin API |
| system_config | Key-value platform configuration with audit | Admin API |
| health_check_log | System uptime tracking (inference, DB, SMTP latency) | Admin API |
| custodial_wallets | Server-managed EVM wallets (Shamir 5-of-3, encrypted salt) | Internal only |
| wallet_shares | Individual SSS encrypted shares (AES-256-GCM, per-share index) | Internal only |
| scheduled_tasks | Cron-like task definitions (handler, interval, enabled, last_run) | Admin API |
| script_executions | Script run records with output, errors, and timing | Admin API |

The internal database file has restricted filesystem permissions (600, owned by the application user). The `admin_audit_log` table is structurally append-only: no UPDATE or DELETE SQL statements for this table exist anywhere in the codebase.

### 4.2 — SQLite Configuration

Both databases use identical pragma configuration applied at connection time:

```sql
PRAGMA journal_mode = WAL;       -- Concurrent reads during writes
PRAGMA synchronous = NORMAL;     -- Durability with reasonable write speed
PRAGMA cache_size = -32000;      -- 32MB page cache per database
PRAGMA temp_store = MEMORY;      -- Temp tables in RAM
PRAGMA foreign_keys = ON;        -- Referential integrity enforced
```

WAL mode is critical for this architecture because the inference pipeline (which can run for 10+ seconds per request) must not block concurrent webhook deliveries, telemetry ingestion, messaging, or authentication checks.

---

## 5. Authentication System

### 5.1 — Wallet-First Design (SIWE Primary)

The primary authentication method is Sign-In with Ethereum (EIP-4361). Password and TOTP are optional additional factors.

```
                    ┌─────────────────────────────────┐
                    │      FULL ACCESS JWT              │
                    │  scopes: inference:read,          │
                    │  keys:write, webhooks:write,      │
                    │  devices:write, registry:read,    │
                    │  registry:write                   │
                    └──────────────▲────────────────────┘
                                   │
                    SIWE Verify    │  EIP-4361 signature verification
                    (Primary)      │  Nonce: 64-char hex, 10-min TTL, one-time use
                                   │  Multi-chain: ETH, Polygon, Arbitrum, Optimism,
                                   │               Base, Sepolia
                                   │  Recovered address → linked to user
                    ┌──────────────┴────────────────────┐
                    │     POST /auth/siwe/verify         │
                    └──────────────▲────────────────────┘
                                   │
                    SIWE Nonce     │  POST /auth/siwe/nonce
                    Request        │  Returns nonce + SIWE message template
                                   │  Chain-specific statement
                    ┌──────────────┴────────────────────┐
                    │     Wallet Connection               │
                    │     (MetaMask, WalletConnect, etc.) │
                    └─────────────────────────────────────┘

    Optional Additional Factors:
    ┌──────────────────────────────────────────────────────┐
    │  Password (Layer 1)                                   │
    │  Argon2id(HMAC-SHA256(password + salt, PEPPER))      │
    │  Parameters: time=3, memory=64MB, parallelism=4      │
    │  Per-user 16-byte random salt                         │
    ├──────────────────────────────────────────────────────┤
    │  TOTP (Layer 2)                                       │
    │  pyotp TOTP, 30s window, 1-step tolerance            │
    │  Secret: AES-256-GCM encrypted at rest               │
    └──────────────────────────────────────────────────────┘
```

### 5.2 — Multi-Chain SIWE Support

| Chain | Chain ID | Network | RPC |
|---|---|---|---|
| Ethereum | 1 | Mainnet | Public RPC |
| Polygon | 137 | Mainnet | Public RPC |
| Arbitrum One | 42161 | Mainnet | Public RPC |
| Optimism | 10 | Mainnet | Public RPC |
| Base | 8453 | Mainnet | Public RPC |
| Sepolia | 11155111 | Testnet | Public RPC |

Each chain has a customizable SIWE statement, block explorer URL, and native token configuration. ENS resolution is Ethereum mainnet only (chain ID 1).

### 5.3 — Custodial Wallet System

For users without a browser wallet extension, REFINET Cloud provides custodial wallet creation:

1. Generate secp256k1 keypair server-side
2. Split private key via Shamir Secret Sharing (5 shares, 3 threshold)
3. Generate per-wallet encryption salt (32 bytes)
4. Derive per-share encryption key via HKDF from `INTERNAL_DB_ENCRYPTION_KEY` + salt
5. Encrypt each share with AES-256-GCM
6. Store encrypted shares in `wallet_shares` table (internal.db)
7. **Private key is NEVER stored** — only encrypted shares exist
8. For signing: reconstruct key from 3+ shares, sign, zero key memory (ctypes.memset)

### 5.4 — JWT Token Architecture

| Scope | Grants Access To |
|---|---|
| `inference:read` | /v1/chat/completions, /v1/models |
| `keys:write` | API key CRUD |
| `webhooks:write` | Webhook subscription CRUD |
| `devices:write` | Device registration and telemetry |
| `registry:read` | Registry project browsing |
| `registry:write` | Registry project management |
| `registry:admin` | Registry admin operations |
| `admin:read` | /admin/* GET |
| `admin:write` | /admin/* POST/PUT/DELETE |

Access tokens: HS256-signed JWT, 60-minute expiry. Refresh tokens: SHA-256 hashed in database, 30-day expiry, rotated on use (old token invalidated, new token issued, linked via `replaced_by` column).

### 5.5 — API Key System

- Prefix: `rf_` (48 random bytes hex encoded)
- Storage: SHA256 hash only (original returned once at creation)
- Scopes: space-separated list per key
- Rate limiting: configurable daily limit per key with automatic reset
- Expiration: optional per-key TTL

---

## 6. Smart Contract Registry

### 6.1 — Design

A GitHub-style project system for smart contracts. Users create projects, upload ABIs, and the system generates SDK definitions that GROOT can query.

### 6.2 — Project Lifecycle

```
Create Project → Upload ABI → Parse Functions/Events → Generate SDK → Publish
      │                │                │                    │           │
      ▼                ▼                ▼                    ▼           ▼
  POST /registry/   POST /registry/  Automatic ABI      POST /repo/   Toggle
  projects          projects/{slug}  parsing with        my-contracts  visibility
                    /abis            access control      /{slug}/sdk   (public/
                                     detection                         private)
```

### 6.3 — ABI Parser

The ABI parser (`api/services/abi_parser.py`) extracts structured information from contract ABIs:

- **Function extraction**: name, selector (4-byte), signature, inputs/outputs with types
- **Event extraction**: name, topic hash (32-byte), indexed parameters
- **Access control detection**:
  - Ownable patterns: `onlyOwner`, `msg.sender == owner`
  - AccessControl patterns: `DEFAULT_ADMIN_ROLE`, `onlyRole`
  - Custom modifiers: regex-based detection
- **Danger flagging**: delegatecall, selfdestruct, proxy patterns
- **State mutability**: pure, view, nonpayable, payable
- **Security summary**: generated per contract

### 6.4 — SDK Generation

The SDK generator (`api/services/sdk_generator.py`) creates complete SDK JSON from parsed ABIs:

- Contract address, chain, language
- Function definitions with types, selectors, access levels
- Event definitions with topic hashes
- Documentation and versioning
- Hash verification for integrity

### 6.5 — Cardinal Rules

1. **Source code is PRIVATE** — the `source_code` column in `contract_repos` is NEVER returned in API responses. GROOT never reads source code.
2. **GROOT reads SDK definitions** — the `sdk_definitions` table is what GROOT queries for CAG context and what the MCP gateway exposes.
3. **Users control visibility** — contracts can be toggled between private and public. Only public SDKs are visible to GROOT and other users.

---

## 7. Messaging System

### 7.1 — Architecture

Wallet-to-wallet messaging with three delivery channels:

1. **Direct Messages** — 1-on-1 conversations identified by wallet addresses
2. **Group Conversations** — Multi-participant with roles (member, admin, owner)
3. **Email Bridge** — SMTP server on port 8025 routes inbound emails to wallet DMs

### 7.2 — Message Flow

```
Sender                    REFINET Cloud                    Recipient
  │                            │                               │
  ├── POST /messages/dm ──────►│                               │
  │   {to_address, content}    │                               │
  │                            ├── Resolve recipient wallet    │
  │                            ├── Check permissions           │
  │                            ├── Create/find conversation    │
  │                            ├── Store message               │
  │                            ├── Update read states          │
  │                            ├── Broadcast via WebSocket ───►│
  │                            ├── Fire messaging.* event      │
  │                            └── Trigger webhook delivery    │
```

### 7.3 — Email Bridge

- **SMTP server**: aiosmtpd on port 8025
- **Alias format**: `<hash>@cifi.global` (auto-generated from wallet + chain)
- **Custom aliases**: users can register custom email aliases
- **ENS email**: resolved from ENS text records
- **Inbound routing**: parse RCPT TO → resolve alias → create DM message
- **Attachment handling**: metadata extraction and storage

### 7.4 — P2P Presence

- **Heartbeat**: `POST /p2p/heartbeat` every 60 seconds
- **Timeout**: peers marked offline after 2 minutes without heartbeat
- **Gossip**: peer exchange protocol (max 20 peers per request)
- **Typing indicators**: real-time typing state per conversation
- **DHT preparation**: wallet address → peer lookup infrastructure

---

## 8. Multi-Chain Identity

### 8.1 — Wallet Identity

Each user can have multiple wallet identities across supported chains:

- **Wallet address**: Ethereum-compatible address per chain
- **Pseudo-IPv6**: deterministic network address from wallet + chain
  - /48 subnet per chain, /80 interface ID per wallet
- **ENS resolution** (Ethereum mainnet only):
  - Primary name (reverse resolution)
  - Avatar (ERC-1155/721)
  - Text records: url, twitter, github, email, description
  - Cache with 1-hour TTL
- **Email alias**: auto-generated `<first8chars>@cifi.global`
- **Display name**: user-configurable
- **Public key**: stored for future E2EE implementation
- **XMTP permissions**: allow_dm, allow_group flags

### 8.2 — Network Identity

Pseudo-IPv6 generation from wallet + chain enables DHT-style peer addressing:

```
Chain ID → /48 subnet prefix
Wallet address → /80 interface ID
Combined → unique IPv6 address per wallet per chain
```

---

## 9. 6-Protocol MCP Gateway

### 9.1 — Protocol Adapters

| Protocol | Mount Point | Transport | Status |
|---|---|---|---|
| REST | All route files | HTTP/1.1 | Always available |
| GraphQL | `/graphql` | HTTP POST | Optional (requires strawberry-graphql) |
| gRPC | `:50051` | HTTP/2 | Optional (requires grpcio) |
| SOAP | `/soap` | HTTP POST | Optional (requires spyne) |
| WebSocket | `/ws` | WS | Always available |
| Webhooks | Event-driven | HTTP POST | Always available |

### 9.2 — MCP Gateway Service

The MCP gateway (`api/services/mcp_gateway.py`) provides unified tool dispatch:

- **Tools**: search_registry, get_project, get_abi, get_sdk, get_execution_logic
- **Tool definition export**: adapts tool schemas for each protocol
- **Dynamic invocation**: protocol-agnostic tool calling
- **Input validation**: schema-based parameter checking
- **Output formatting**: per-protocol response adaptation

### 9.3 — Unified Authentication

All protocols use the same authentication middleware (`api/middleware/protocol_auth.py`):

- JWT Bearer token or API key (rf_ prefix)
- Scope verification per tool/operation
- Consistent user context across protocols
- No protocol downgrade attacks possible

### 9.4 — WebSocket Events

The WebSocket endpoint (`/ws`) supports:

- **Event subscriptions**: wildcard pattern matching (fnmatch)
- **Event channels**: registry.*, messaging.*, system.*, knowledge.*
- **Tool execution**: direct tool calling via WebSocket messages
- **Connection pooling**: per-user state tracking

### 9.5 — Graceful Degradation

Optional protocols (GraphQL, gRPC, SOAP) fail gracefully if their dependencies are not installed. The platform logs an info message and continues without the adapter. REST and WebSocket are always available.

---

## 10. Webhook Event System

### 10.1 — Design Rationale

REFINET Cloud's primary asynchronous integration mechanism is webhook delivery:

- **Decoupled scaling.** Partner systems process events independently of inference capacity.
- **Firewall compatibility.** Partners receive inbound HTTP POST — no outbound connections required.
- **Auditability.** Every delivery attempt is logged with timestamp, HTTP status, and retry count.

### 10.2 — Delivery Mechanics

```
Event occurs (telemetry, registry change, message, status change)
    │
    ▼
Query webhook_subscriptions WHERE user_id = owner AND event matches filter
    │
    ▼
For each matching subscription:
    ├── Build JSON payload: { event, payload, timestamp }
    ├── Compute signature: HMAC-SHA256(key=subscription.secret, msg=JSON_body)
    ├── Enqueue to async delivery worker
    │
    └── Worker:
        ├── POST to subscription.url with headers:
        │     Content-Type: application/json
        │     X-REFINET-Signature: sha256={hmac_hex}
        │     X-REFINET-Event: {event_name}
        ├── On success (2xx): reset failure_count, update last_delivery_at
        ├── On failure: retry with exponential backoff [2s, 8s, 30s]
        └── On failure_count >= 10: set is_active = false (auto-suspend)
```

### 10.3 — Event Taxonomy

| Event Pattern | Trigger |
|---|---|
| `device.telemetry.*` | Telemetry received, alerts, thresholds |
| `device.status.*` | Online/offline, registration |
| `device.command.*` | Command sent/acknowledged |
| `registry.*` | Project created/updated, ABI added, SDK generated |
| `messaging.*` | Message sent, conversation created |
| `system.*` | Health changes, config updates |
| `knowledge.*` | Document uploaded, chunks updated |

---

## 11. Knowledge Base

### 11.1 — Document Ingestion

Supported formats and their parsers:

| Format | Parser | Capabilities |
|---|---|---|
| PDF | PyMuPDF | Text extraction, metadata |
| DOCX | python-docx | Paragraph extraction |
| XLSX | openpyxl | Sheet/row extraction |
| CSV | Built-in | Row extraction |
| TXT/MD | Built-in | Direct content |
| JSON | Built-in | Structured extraction |
| Solidity | Built-in | Contract source |
| URL | url_parser | Web page content extraction |
| YouTube | youtube_parser | Transcript extraction |

### 11.2 — Additional Services

- **Auto-tagging** (`auto_tagger.py`): automatic tag generation and category classification
- **Document comparison** (`document_compare.py`): semantic similarity, keyword overlap, structure diff
- **Timeline extraction** (`timeline_extractor.py`): chronological event extraction from documents
- **TTS generation** (`tts_generator.py`): text-to-speech synthesis
- **Document export** (`document_exporter.py`): Markdown and HTML export

---

## 12. Agent Engine

### 12.1 — Architecture

The Agent Engine transforms GROOT from a stateless inference endpoint into a multi-agent autonomous platform. Each agent has a persistent SOUL identity, 4-tier memory, tool access via the MCP gateway, and delegation capability.

```
Agent Registration (existing)
  └── SOUL.md (identity, goals, constraints, tools, delegation policy)
  └── 4-Tier Memory
  │     ├── Working (per-task, TTL, auto-cleaned)
  │     ├── Episodic (timestamped events with outcomes)
  │     ├── Semantic (learned facts + 384-dim embeddings, deduped)
  │     └── Procedural (strategy patterns with success rates)
  └── Cognitive Loop
  │     └── PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE
  └── Tool Access (MCP gateway dispatch_tool())
  └── Delegation (agent-to-agent, max depth 3)
```

### 12.2 — Cognitive Loop

Every agent task runs through a 6-phase loop, each phase backed by BitNet inference:

1. **PERCEIVE** — Parse task, recall memories from all 4 tiers, build situation awareness
2. **PLAN** — Generate structured JSON plan with steps, referencing tools and past procedures
3. **ACT** — Execute plan steps: tool calls via MCP `dispatch_tool()` or reasoning
4. **OBSERVE** — Evaluate results against expectations
5. **REFLECT** — Extract lessons learned, identify new facts and strategy improvements
6. **STORE** — Persist episodic/semantic/procedural memories, clear working memory

### 12.3 — Safety Constraints

Platform-wide constraints apply to all agents regardless of SOUL configuration (see [SAFETY.md](SAFETY.md)):
- Never expose private keys or secrets
- Never bypass authentication or escalate privileges
- Never execute destructive on-chain operations autonomously
- Max delegation depth of 3 to prevent unbounded recursion

### 12.4 — Built-in Archetypes

Five ready-to-use SOUL templates (see [AGENTS.md](AGENTS.md)):
- `groot-chat` — Conversational AI for platform Q&A
- `contract-analyst` — Smart contract security review
- `knowledge-curator` — Knowledge base coverage monitoring
- `platform-ops` — System health and maintenance
- `dapp-builder` — DApp assembly from registry contracts

---

## 13. DApp Factory

### 13.1 — Template System

The DApp Factory assembles downloadable DApp projects from registry contracts:

| Template | Description | Required Contract Type |
|---|---|---|
| token-dashboard | ERC-20 balance, transfer, approve UI | ERC-20 ABI |
| nft-gallery | ERC-721/1155 gallery with metadata display | ERC-721/1155 ABI |
| staking-ui | Stake/unstake/claim interface | Staking contract ABI |
| dao-voter | Proposal creation and voting UI | Governor ABI |
| multi-send | Batch transfer interface | Any token ABI |

### 13.2 — Build Pipeline

```
Select Template → Configure (chain, address, ABI) → Assemble → Download ZIP
    │                    │                              │            │
    ▼                    ▼                              ▼            ▼
GET /dapp/          POST /dapp/build              Background     GET /dapp/builds/
templates           {template, config}            assembly       {id}/download
```

Build status transitions: `building` → `ready` (success) or `failed` (error).

---

## 14. App Store

### 14.1 — Listing Model

Published platform extensions with categories: `dapp`, `agent`, `tool`, `template`.

Each listing includes: name, publisher, description, version, changelog, category, chain support, install count, and aggregate rating.

### 14.2 — API

| Method | Path | Description |
|---|---|---|
| GET | `/app-store/listings` | Browse/search published apps |
| GET | `/app-store/listings/{id}` | Get listing detail |
| POST | `/app-store/listings` | Publish a listing |
| PUT | `/app-store/listings/{id}` | Update listing |
| POST | `/app-store/listings/{id}/install` | Track install |
| POST | `/app-store/listings/{id}/review` | Submit rating/review |

---

## 15. Chain Listener

### 15.1 — Event Monitoring

The chain listener monitors EVM-compatible blockchains for configured events and triggers backend actions:

```
Configure Watcher → Poll Chain RPC → Match Events → Trigger Webhook/Action
       │                    │                │                    │
       ▼                    ▼                ▼                    ▼
  POST /chain/       Block-by-block     Event signature     POST to webhook URL
  watchers           scanning            matching            or internal handler
```

### 15.2 — Safety

Chain watchers may **detect** events but may **never** initiate state-changing on-chain transactions autonomously. This is enforced at the service layer (see [SAFETY.md](SAFETY.md)).

---

## 16. Device and Agent Connectivity

### 12.1 — Device Lifecycle

```
Register → Configure → Send Telemetry → Receive Commands → Deregister
    │           │              │                │               │
    ▼           ▼              ▼                ▼               ▼
POST        Metadata      POST /devices/   Webhook        DELETE
/devices    update        {id}/telemetry   delivery       /devices/{id}
            (JSON blob)   (ECDSA signed)   to device URL
```

Device types: `iot`, `plc`, `dlt`, `webhook`. Each device can have an ETH address for ECDSA-signed telemetry verification.

### 12.2 — Agent Registration

Agents (QuickCast, AgentOS, third-party) register and receive remote configuration:

```json
POST /agents
{
  "name": "QuickCast",
  "product": "quickcast",
  "version": "1.0.0",
  "eth_address": "0x..."
}
Authorization: Bearer {BUILD_KEY}
```

Remote config is a JSON blob that agents cache locally. Admins update config via `PATCH /agents/{id}` — agents fetch updated config on next request.

---

## 17. Middleware & Cross-Cutting Concerns

| Middleware | Purpose | Configuration |
|---|---|---|
| CORS | Dynamic origin configuration per environment | Production: specific domains; Dev: localhost |
| Rate Limiting | slowapi, per-minute sliding window | 60 req/min default, 25 req/day anonymous |
| Request Size | Maximum body size enforcement | 10MB configurable |
| Protocol Auth | Unified auth for all 6 protocols | JWT or API key, scope verification |
| Logging | Async request/response logging | Structured timestamps, latency tracking |

---

## 18. Background Workers & Task Scheduler

The `TaskScheduler` singleton ticks every 10 seconds and dispatches registered tasks:

| Worker | Interval | Purpose |
|---|---|---|
| Health monitor | 60s | Check inference, DB, SMTP; log to health_check_log |
| P2P cleanup | 60s | Remove stale peers (>2 min without heartbeat) |
| Auth cleanup | 3600s | Expire nonces (>10 min) and revoked refresh tokens |
| Agent memory cleanup | 300s | Remove expired working memory entries |
| Webhook delivery | Async queue | HMAC-signed delivery with exponential backoff retry |
| Chain listener | Configurable | Block-by-block event polling per watcher |
| Script runner | On-demand | Safe execution of categorized scripts (ops, maintenance, analysis, chain, dapp) |
| SMTP bridge | Persistent | aiosmtpd server on port 8025 for email routing |
| Event bus | Event-driven | In-process pub/sub with wildcard pattern matching |

### 18.1 — Script Runner

The script runner (`api/services/script_runner.py`) executes Python scripts from the `scripts/` directory with category-based access control. Agents can only run scripts their SOUL authorizes (e.g., `execute_script:maintenance.*`).

Available script categories:
- **analysis/** — Knowledge coverage, platform stats, registry reports, usage reports
- **maintenance/** — Database backup, orphan cleanup, telemetry pruning, FTS rebuild, API counter reset, secret rotation
- **ops/** — Database stats, health reports
- **chain/** — ABI fetching, address monitoring, contract reading
- **dapp/** — DApp building, template listing

---

## 19. Network and Security Configuration

### 15.1 — Nginx Reverse Proxy

```
Port 80  → 301 redirect to HTTPS
Port 443 → TLS termination → proxy_pass to 127.0.0.1:8000

Rate limit zones:
  auth:  5 req/s per IP (burst 10)
  api:   30 req/s per IP (burst 20)

SSE support for /v1/*:
  proxy_buffering off
  proxy_cache off
  proxy_http_version 1.1
  proxy_read_timeout 120s

WebSocket support for /ws:
  proxy_set_header Upgrade $http_upgrade
  proxy_set_header Connection "upgrade"

Security headers:
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Strict-Transport-Security: max-age=31536000
  Referrer-Policy: strict-origin-when-cross-origin
```

### 15.2 — Firewall (UFW)

```
ALLOW: 22/tcp (SSH, key-only, fail2ban), 80/tcp, 443/tcp
DENY:  all other inbound
```

Ports 8080 (BitNet), 8000 (FastAPI), 8025 (SMTP), and 50051 (gRPC) are never exposed externally.

### 15.3 — Secret Management

All secrets reside in `/opt/refinet/app/.env` (mode 600). Secrets are never committed to version control, never logged, never included in API responses.

| Secret | Purpose | Length |
|---|---|---|
| SECRET_KEY | JWT access token signing | 64 bytes hex |
| REFRESH_SECRET | Refresh token signing | 64 bytes hex |
| SERVER_PEPPER | Password hash + key derivation HMAC | 64 bytes hex |
| INTERNAL_DB_ENCRYPTION_KEY | AES-256-GCM for internal.db secrets + wallet shares | 32 bytes hex |
| ADMIN_API_SECRET | Additional admin route header verification | 32 bytes hex |
| WEBHOOK_SIGNING_KEY | Default webhook HMAC key | 32 bytes hex |

---

## 20. Capacity Planning

### 16.1 — Resource Consumption at Scale

| Resource | At 100 users | At 500 users | At 1000 users | Limit |
|---|---|---|---|---|
| RAM (model + app + embeddings) | 3.0 GB | 3.4 GB | 3.8 GB | 24 GB |
| Storage (DB + model + embeddings) | 10 GB | 14 GB | 20 GB | 200 GB |
| Bandwidth/month | 0.2 GB | 0.5 GB | 1.2 GB | 10 TB |
| Inference req/day | 1,000 | 3,000 | 5,400 | ~5,400 |

### 16.2 — Scaling Path

| Stage | Capacity | Method | Cost |
|---|---|---|---|
| Current | ~5,400 req/day | Single instance | $0 |
| +Caching | ~15,000 req/day | Response cache for common queries | $0 |
| +Shorter responses | ~10,000 req/day | Reduce default max_tokens to 128 | $0 |
| +Second instance | ~10,800 req/day | Second Oracle free-tier ARM instance | $0 |
| +Paid instance | ~50,000 req/day | Oracle A1.Flex 8 OCPU ($0.04/hr) | ~$29/mo |

---

## 21. Frontend Architecture

### 17.1 — Technology

- **Framework**: Next.js 14 App Router with React 18 and TypeScript
- **Output**: Static export (`next export`) → served by Nginx as flat files
- **Styling**: Tailwind CSS with CSS custom properties for theming
- **Web3**: wagmi + viem for wallet connection and SIWE signing (native multi-wallet, no WalletConnect dependency)
- **Animations**: CSS keyframes and transitions (no external animation library)

### 17.2 — Pages

| Route | Purpose |
|---|---|
| `/` | Landing page with horizontal panels (Hero, Developers, Productivity, Browser, AgentOS) |
| `/settings/` | Authentication/login page (SIWE flow via WagmiProvider) |
| `/dashboard/` | User dashboard (stats, API keys, devices, recent activity) |
| `/chat/` | Full-featured AI chat with document source selection and conversation history |
| `/projects/` | User's project collection with getting-started guide |
| `/explore/` | Public contract discovery (registry projects, smart contracts, knowledge search) |
| `/repo/` | Personal contract repository management (@username namespace) |
| `/knowledge/` | Knowledge base admin (upload, manage, compare, RAG search) |
| `/devices/` | IoT device management (registration, telemetry, commands) |
| `/webhooks/` | Webhook subscription management |
| `/messages/` | Messaging (conversations, compose, aliases, groups) |
| `/network/` | Network visualization |
| `/docs/` | API documentation |
| `/admin/` | Admin panel (roles, secrets, audit, MCP registry) |
| `/u/[username]/` | Public user profiles |
| `/registry/[...slug]/` | Registry project detail pages |
| `/registry/new/` | Create new registry project |

### 17.3 — Design System

- **Primary color**: REFINET teal (#5CE0D2 dark, #0D9488 light)
- **Typography**: Inter (body), JetBrains Mono (code)
- **Theme**: Dark mode default with light mode toggle
- **Components**: All custom-built (no external component library)
- **State**: React hooks only (no Redux/Zustand)
- **Storage**: localStorage for tokens, theme, sidebar state, chat history

### 17.4 — Key Components

- **AppShell**: Top nav + collapsible sidebar + content area + floating Groot chat
- **AuthFlow**: SIWE wallet connection with chain selection and onboarding
- **GrootChat**: Floating chat widget with streaming SSE responses
- **SettingsModal**: Account, Security, API Keys, Admin tabs
- **ThemeProvider**: Dark/light toggle with CSS variable switching

---

## 22. Deployment Procedure

```bash
# 1. Provision Oracle Cloud Always Free ARM A1 Flex (4 OCPU, 24GB RAM)
# 2. SSH to instance
sudo bash scripts/bootstrap.sh        # Idempotent system setup + BitNet build
cp .env.example .env                   # Configure secrets
python3 scripts/admin.py users grant-role {user_id} admin
sudo systemctl start refinet-bitnet    # Start inference server
sudo systemctl start refinet-api       # Start API + gRPC + SMTP bridge
sudo certbot --nginx                   # TLS certificates

# 3. Build and deploy frontend
cd frontend && npm install && NEXT_PUBLIC_API_URL=https://api.refinet.io npm run build
sudo cp -r out/* /opt/refinet/frontend/out/

# 4. Verify
curl https://api.refinet.io/health
# → {"status":"ok","inference":"ok","model":"bitnet-b1.58-2b"}
```

---

## Appendix A — Technology Stack

| Component | Technology | License | Version |
|---|---|---|---|
| Language model | BitNet b1.58 2B4T | MIT | April 2025 |
| Inference server | bitnet.cpp (llama-server) | MIT | 2026 |
| API framework | FastAPI | MIT | 0.115.x |
| ASGI server | Uvicorn | BSD-3 | 0.32.x |
| Database | SQLite | Public domain | 3.45+ |
| ORM | SQLAlchemy | MIT | 2.0.x |
| Migration | Alembic | MIT | 1.13+ |
| Password hashing | Argon2id (argon2-cffi) | MIT | 23.x |
| TOTP | pyotp | MIT | 2.9.x |
| Ethereum auth | web3.py + eth-account | MIT | 7.x / 0.13.x |
| JWT | PyJWT | MIT | 2.10.x |
| Encryption | cryptography (Python) | Apache-2.0 / BSD | 44.x |
| HTTP client | httpx | BSD-3 | 0.28.x |
| Embeddings | sentence-transformers | Apache-2.0 | 2.7+ |
| Document parsing | PyMuPDF + python-docx + openpyxl | AGPL/MIT/MIT | Latest |
| GraphQL | Strawberry (optional) | MIT | Latest |
| gRPC | grpcio (optional) | Apache-2.0 | Latest |
| SOAP | Spyne (optional) | LGPL | Latest |
| SMTP | aiosmtpd | Apache-2.0 | 1.x |
| Rate limiting | slowapi | MIT | 0.1.x |
| Reverse proxy | Nginx | BSD-2 | 1.24+ |
| TLS | Let's Encrypt (Certbot) | Apache-2.0 | — |
| Frontend | Next.js 14 (static export) | MIT | 14.2.x |
| Frontend UI | React 18 + TypeScript | MIT | 18.x |
| Styling | Tailwind CSS | MIT | 3.4.x |
| Web3 (frontend) | wagmi + viem | MIT | 2.x / 2.x |
| OS | Ubuntu 22.04 LTS (ARM64) | GPL-2.0 | — |

Every component is open-source. No proprietary dependencies.

---

## Appendix B — API Surface Summary

| Route Group | File | Endpoints | Auth Required | Touches Inference |
|---|---|---|---|---|
| `/health`, `/` | health.py | 2 | No | No |
| `/auth/*` | auth.py | 19 | Varies by step | No |
| `/v1/*` | inference.py | 3 | JWT, API key, or anon | Yes |
| `/devices/*` | devices.py | 6 | JWT or device key | No |
| `/agents/*` | agents.py | 12+ | JWT or build key | Yes (cognitive loop) |
| `/webhooks/*` | webhooks.py | 5 | JWT | No |
| `/mcp/*` | mcp.py | 3 | JWT | No (proxied) |
| `/keys/*` | keys.py | 4 | JWT | No |
| `/knowledge/*` | knowledge.py | 5+ | Admin (write), any (search) | No |
| `/admin/*` | admin.py | 14+ | Admin role | No |
| `/registry/*` | registry.py | 12+ | JWT | No |
| `/repo/*` | repo.py | 8+ | JWT | No |
| `/explore/*` | explore.py | 4 | No | No |
| `/identity/*` | identity.py | 4+ | JWT | No |
| `/messages/*` | messaging.py | 8+ | JWT | No |
| `/p2p/*` | p2p.py | 3 | JWT | No |
| `/chain/*` | chain.py | 6+ | JWT | No |
| `/dapp/*` | dapp.py | 5+ | JWT | No |
| `/app-store/*` | app_store.py | 8+ | JWT | No |
| `/graphql` | mcp_graphql.py | 1 | JWT or API key | No |
| `/soap` | mcp_soap.py | 1 | JWT or API key | No |
| `/ws` | mcp_websocket.py | 1 | JWT or API key | No |
| **Total** | **22 files** | **210+ endpoints** | | |

Of 210+ endpoints, only the inference route and agent cognitive loop touch the BitNet server. All others operate at full FastAPI/SQLite speed (~500-1000 req/s).

---

## Appendix C — Service Modules

42 service modules in `api/services/`:

| Module | Purpose |
|---|---|
| abi_parser.py | ABI JSON parsing, function/event extraction, access control detection |
| agent_engine.py | 6-phase cognitive loop, task execution, tool dispatch |
| agent_memory.py | 4-tier memory CRUD (working, episodic, semantic, procedural) |
| agent_soul.py | SOUL.md parsing, validation, tool permission checking |
| app_store.py | App listing CRUD, install tracking, ratings |
| auto_tagger.py | Automatic tag generation and category classification |
| chain_listener.py | On-chain event monitoring, block scanning, event matching |
| contract_brain.py | CAG context search across public SDK definitions |
| config_defaults.py | Platform configuration seeding |
| crypto_utils.py | Keccak-256, function selectors, topic hashes |
| dapp_factory.py | Template-based DApp assembly, build pipeline, ZIP output |
| device_telemetry.py | Telemetry ingestion and validation |
| document_compare.py | Document similarity scoring and diff |
| document_exporter.py | Markdown/HTML export |
| document_generator.py | Template-based document generation |
| document_parser.py | PDF, DOCX, XLSX, CSV, TXT, JSON parsing |
| email_bridge.py | Email alias management and routing |
| embedding.py | Sentence-transformer integration (384-dim) |
| event_bus.py | In-process pub/sub with wildcard patterns |
| fts.py | FTS5 full-text search indexing and query |
| inference.py | BitNet HTTP client (streaming + non-streaming) |
| knowledge_refresh.py | Event-driven knowledge cache invalidation |
| mcp_gateway.py | Unified tool dispatch across all protocols |
| mcp_proxy.py | HTTP proxy for external MCP servers |
| messaging.py | DM, group, threading, read state, permissions |
| messenger_bridge.py | Cross-platform message relay and bridging |
| monitor.py | System health checks (inference, DB, SMTP) |
| p2p.py | Peer discovery, presence, gossip, relay |
| rag.py | Document chunking, hybrid search, context building |
| registry_service.py | Project CRUD, ABI/SDK/logic management, stars/forks |
| scheduler.py | Cron-like task scheduler with health monitoring |
| script_runner.py | Safe script execution with category-based access control |
| sdk_generator.py | SDK JSON generation from parsed ABIs |
| shamir.py | Shamir's Secret Sharing (split/reconstruct) |
| smtp_bridge.py | aiosmtpd SMTP server for email-to-DM routing |
| timeline_extractor.py | Chronological event extraction from documents |
| tts_generator.py | Text-to-speech synthesis |
| url_parser.py | URL content extraction |
| wallet_crypto.py | HKDF key derivation, AES-256-GCM per-wallet encryption |
| wallet_service.py | Custodial wallet creation, signing, share management |
| webhook_delivery.py | Async delivery worker with retry and backoff |
| youtube_parser.py | YouTube transcript extraction |

---

## Appendix D — Operational Scripts

23 scripts in `scripts/`:

| Category | Script | Purpose |
|---|---|---|
| analysis/ | knowledge_coverage.py | Audit knowledge base coverage across categories |
| analysis/ | platform_stats.py | Platform-wide statistics (users, projects, devices) |
| analysis/ | registry_report.py | Registry project analytics and trends |
| analysis/ | usage_report.py | API usage aggregation and reporting |
| maintenance/ | backup_db.py | Database backup to compressed archive |
| maintenance/ | cleanup_orphans.py | Remove orphaned records across tables |
| maintenance/ | prune_telemetry.py | Trim old telemetry data beyond retention window |
| maintenance/ | rebuild_fts_index.py | Rebuild FTS5 full-text search indexes |
| maintenance/ | reset_api_counters.py | Reset daily API key usage counters |
| maintenance/ | rotate_secrets.py | Rotate encryption keys and secrets |
| ops/ | db_stats.py | Database size, table counts, WAL statistics |
| ops/ | health_report.py | Comprehensive health check report |
| chain/ | fetch_abi.py | Fetch contract ABI from block explorer |
| chain/ | monitor_address.py | Monitor address for transactions |
| chain/ | read_contract.py | Read contract state via RPC |
| dapp/ | build_dapp.py | CLI DApp assembly from template |
| dapp/ | list_templates.py | List available DApp templates |
| — | backfill_sdk_knowledge.py | Backfill SDK definitions into knowledge base |

---

*This document is an internal technical reference for REFINET Cloud v3.0.*
*Classification: Internal / Academic.*
*Last updated: March 2026.*
