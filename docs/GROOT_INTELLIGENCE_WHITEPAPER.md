# GROOT Intelligence
## A First Look at Regenerative AI Infrastructure
### REFINET Cloud · March 2026

---

## Abstract

GROOT is a persistent AI intelligence layer embedded in REFINET Cloud — the Regenerative Finance Network's sovereign infrastructure platform. Unlike conventional AI services that rent intelligence from centralized providers, GROOT operates on infrastructure owned and controlled entirely by REFINET, at zero marginal cost per query. This document describes what GROOT can do, the science behind its capabilities, and what users, developers, and partners can expect when they connect.

This is not a technical implementation guide. This is an introduction to a new class of AI service: one that is free, sovereign, grounded in verifiable knowledge, and accessible to any device on the internet that can speak HTTP.

---

## 1. What GROOT Is

GROOT is the intelligence that lives inside REFINET Cloud. It is not a chatbot. It is not a wrapper around someone else's API. It is a native AI system that runs on REFINET's own hardware, trained on open-source foundations, and augmented with REFINET's proprietary knowledge layer.

When you talk to GROOT, the computation happens on machines REFINET controls. Your conversation is not routed through a third-party provider. Your data is not sold, indexed, or used to train other models. The intelligence is sovereign — owned by the network, operated for the network.

GROOT serves five roles simultaneously:

**Conversational Intelligence.** Any person can visit REFINET Cloud and ask GROOT questions in natural language. GROOT understands regenerative finance, blockchain infrastructure, sovereign computing, decentralized identity, IoT protocols, and the full REFINET product ecosystem. It responds with contextually grounded answers drawn from REFINET's curated knowledge base — not from unverified internet data.

**API Intelligence.** Any developer can call GROOT through a standard REST API that is fully compatible with the OpenAI specification. Existing code that works with OpenAI, Anthropic, or any OpenAI-compatible provider works with GROOT by changing two configuration values. No SDK. No proprietary client. No vendor dependency.

**Contract Intelligence.** GROOT understands smart contracts. Users upload ABIs to their personal contract repository, GROOT parses them into structured SDK definitions, and then uses those definitions to answer questions about contract functionality, access control, state mutability, and dangerous operations — across Ethereum, Polygon, Arbitrum, Optimism, Base, and Sepolia.

**Network Intelligence.** Any device, agent, or service that can send an HTTP request can connect to REFINET Cloud, register itself, and participate in the network. IoT sensors push telemetry. Industrial controllers receive commands. Blockchain nodes report status. Autonomous software agents register, authenticate, and request intelligence on demand. GROOT is the cognitive layer that ties the network together.

**Agent Intelligence.** GROOT powers an autonomous multi-agent platform where agents operate with persistent identity (SOUL.md), 4-tier memory (working, episodic, semantic, procedural), and a 6-phase cognitive loop (PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE). Agents access platform tools through the MCP gateway, delegate subtasks to other agents, and learn from past interactions. Built-in archetypes include contract analysis, knowledge curation, platform operations, and DApp building.

**Communication Intelligence.** GROOT powers a wallet-to-wallet messaging system where users communicate using their blockchain identities. Direct messages, group conversations, email bridging, cross-platform messenger bridge, P2P presence, and ENS-resolved identities — all integrated into the same sovereign platform.

---

## 2. The Science of GROOT

### 2.1 — Native Efficiency Architecture

GROOT's inference engine uses a class of language model specifically designed for CPU-native computation. The model architecture replaces traditional floating-point weight matrices with ternary representations — each parameter encoded as one of three discrete values — which reduces both memory footprint and computational complexity by an order of magnitude compared to conventional models.

This is not post-training compression. The model was trained natively in this representation from the beginning, on a corpus of 4 trillion tokens. The result is a system that achieves performance comparable to full-precision models at the same parameter scale, while requiring less than 500 megabytes of memory and no specialized accelerator hardware.

The practical consequence: GROOT runs on general-purpose processors at speeds that match or exceed human reading pace. No GPU cluster. No cloud API bill. No inference cost that scales with usage.

### 2.2 — Retrieval-Augmented Knowledge (RAG)

GROOT does not rely solely on its pre-trained knowledge. Every conversational turn triggers a real-time search across REFINET's structured knowledge base — a curated repository of documents, product specifications, protocol definitions, and domain expertise maintained by REFINET's team.

The retrieval process uses hybrid search:

1. The user's query is decomposed into semantic components
2. **Keyword scoring**: SQL-based matching against chunked document content
3. **Semantic scoring**: sentence-transformer embeddings (384-dimensional) compute cosine similarity between query and stored chunks
4. Scores are combined with configurable weighting
5. The highest-scoring knowledge segments are assembled into a contextual frame
6. This frame is provided to the inference engine alongside the user's query
7. GROOT's response is grounded in verified, source-attributed information

The knowledge base supports multiple document formats: PDF, DOCX, XLSX, CSV, Markdown, JSON, Solidity source files, web URLs, and YouTube transcripts. Documents are auto-tagged, compared for similarity, and can have timelines extracted automatically.

This means GROOT's answers improve over time as REFINET adds documentation, without requiring model retraining. When REFINET publishes a new product, updates a protocol, or releases a technical specification, GROOT knows about it within seconds of the document entering the knowledge base.

### 2.3 — Contract-Augmented Generation (CAG)

GROOT extends beyond natural language knowledge into on-chain logic. Users upload smart contract ABIs to their personal GROOT Brain repository. The system automatically:

1. **Parses the ABI** into structured function and event definitions
2. **Detects access control patterns** (Ownable, AccessControl, custom modifiers)
3. **Flags dangerous operations** (delegatecall, selfdestruct, proxy patterns)
4. **Classifies state mutability** (pure, view, nonpayable, payable)
5. **Generates SDK definitions** that serve as GROOT's knowledge about the contract

When a user asks about a DeFi mechanism, a token contract, or a governance proposal, GROOT retrieves not just descriptive text but the actual logical specification of the contract — its functions, its state transitions, its access control rules, and its potential risks.

This capability — Contract-Augmented Generation — allows GROOT to reason about blockchain operations with a precision that general-purpose AI models cannot achieve. GROOT does not guess about what a contract does. It references a verified, parsed definition of what the contract does.

CAG is currently operational for Ethereum, Polygon, Arbitrum, Optimism, Base, and Sepolia ecosystems, with contracts stored in the GitHub-style smart contract registry and personal GROOT Brain repositories.

### 2.4 — Wallet-First Cryptographic Identity

Every human who accesses GROOT through an authenticated session is verified through Sign-In with Ethereum (SIWE) — a cryptographic signature proving the user controls a specific blockchain wallet. This is the primary authentication method, not an optional add-on.

**SIWE Authentication.** The user's wallet signs an EIP-4361 message containing a server-generated nonce. The server verifies the signature, recovers the wallet address, and issues a JWT with appropriate scopes. Multi-chain support means users can authenticate with wallets on Ethereum, Polygon, Arbitrum, Optimism, Base, or Sepolia.

**Optional Additional Factors.** Users can optionally add password authentication (Argon2id with per-user salt and server pepper) and TOTP two-factor authentication (compatible with Google Authenticator) for additional security layers.

**Custodial Wallet Option.** For users without a browser wallet extension, REFINET Cloud can create a custodial wallet. The private key is split via Shamir Secret Sharing into 5 shares with a 3-share reconstruction threshold. Each share is individually encrypted with AES-256-GCM. The private key is never stored — only encrypted shares exist in the internal database.

**Multi-Chain Identity.** Each user can have wallet identities across multiple chains, with ENS name resolution (Ethereum mainnet), auto-generated email aliases, pseudo-IPv6 network addresses, and configurable display names.

This is the security model of a financial system, not a chat application.

---

## 3. What Users Experience

### 3.1 — Casual Users

Visit REFINET Cloud. A clean, dark-themed interface loads. A floating chat icon pulses in the lower-right corner. Click it. Ask GROOT anything:

- *"What is regenerative finance?"*
- *"How does REFINET Cloud work?"*
- *"Explain the difference between Layer 1 and Layer 2 blockchains."*
- *"What products does REFINET offer?"*

GROOT responds with precise, grounded answers. Responses stream in token-by-token for a natural conversational feel. Anonymous users get 25 requests per day with no account required. No credit card. No signup wall.

The full chat page offers document source selection ("notebook mode"), conversation history, content generation from selected documents (summaries, FAQs, overviews, timelines), and source citations with relevance scores.

### 3.2 — Developers and Partners

Developers authenticate via SIWE and receive 250 inference requests per day through the API. Integration requires no proprietary SDK — any HTTP client or OpenAI-compatible library works.

The platform offers six protocol adapters for maximum compatibility:

| Protocol | Endpoint | Use Case |
|---|---|---|
| REST | `POST /v1/chat/completions` | Standard API integration |
| GraphQL | `/graphql` | Flexible query/mutation interface |
| gRPC | `:50051` | High-performance service-to-service |
| SOAP | `/soap` | Enterprise system integration |
| WebSocket | `/ws` | Real-time event subscriptions |
| Webhooks | Event-driven POST | Async event processing |

The **Smart Contract Registry** gives developers a GitHub-style experience for managing on-chain code: create projects, upload ABIs, generate SDKs, star and fork other projects, and browse a public explorer of contracts across multiple chains.

The **GROOT Brain** personal repository lets developers upload contracts with automatic ABI parsing, access control detection, dangerous operation flagging, and per-function SDK generation — all while keeping source code private.

The **DApp Factory** lets developers assemble downloadable DApp projects from registry contracts using pre-built templates (token-dashboard, nft-gallery, staking-ui, dao-voter, multi-send). Configure chain, address, and ABI — then download a ready-to-customize project.

The **App Store** provides a marketplace for publishing and discovering DApps, agents, tools, and templates built on the REFINET platform.

### 3.3 — Connected Devices and Agents

Any device that can make an HTTP POST request is a potential participant in the REFINET network. The connection model is universal:

1. A human registers the device through REFINET Cloud (or the device self-registers with a pre-provisioned key)
2. The device receives a scoped API credential
3. The device sends telemetry (with optional ECDSA signature verification), receives commands, and subscribes to events — all over standard HTTPS
4. Webhook events propagate to any subscribed endpoint in real time

Industrial PLCs report sensor readings. IoT gateways relay environmental data. Blockchain nodes report chain health. Autonomous software agents request inference, report results, and coordinate with other agents — all through the same protocol.

### 3.4 — Messaging Users

REFINET Cloud provides wallet-to-wallet messaging:

- **Direct messages** between any two wallet addresses
- **Group conversations** with role-based permissions (member, admin, owner)
- **Email bridge** — receive messages via email aliases (`<hash>@cifi.global`)
- **ENS integration** — send messages to ENS names, not just addresses
- **P2P presence** — see who is online, typing indicators, peer discovery
- **Read receipts** — per-participant read state tracking

All messaging is tied to wallet identity, not email accounts or phone numbers. Your blockchain address is your inbox.

---

## 4. What Makes This Different

### 4.1 — Zero Cost, Permanently

GROOT is not free because REFINET is subsidizing a growth strategy. GROOT is free because the architecture was designed from the beginning to eliminate the cost drivers that make AI expensive: GPU rental, third-party API fees, database licensing, and cloud service subscriptions.

The inference engine runs on CPU. The database is embedded. The web server is open-source. The TLS certificates are automated and free. The hosting is on a permanent free tier that Oracle has maintained since 2021. There is no credit card on file. There is no monthly invoice. The marginal cost of the next query is zero.

### 4.2 — Sovereign by Default

When a user talks to GROOT, the conversation does not transit through a third party. The data does not enter a training pipeline controlled by another organization.

The platform operates two physically separate databases — one for user-facing operations (40+ tables), one for internal administration (12+ tables). The internal database is not accessible through any public interface. The administrative audit log is append-only and cannot be modified through any API endpoint.

Custodial wallet private keys are never stored — only Shamir shares encrypted with per-wallet keys exist. Even a complete database compromise cannot reconstruct wallet keys without the server's encryption key.

### 4.3 — Grounded, Not Generative

Most AI systems generate text from statistical patterns in their training data. GROOT does this too — but every conversational turn also searches a curated, source-attributed knowledge base using hybrid keyword and semantic search before generating a response.

For blockchain queries, GROOT goes further: it searches parsed ABI definitions and SDK specifications to provide answers grounded in actual contract logic, not guesses.

### 4.4 — Multi-Protocol, Multi-Chain

REFINET Cloud speaks six protocols (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks) and supports six EVM chains (Ethereum, Polygon, Arbitrum, Optimism, Base, Sepolia). All protocols use the same unified authentication middleware. No protocol lock-in. No chain lock-in.

### 4.5 — Identity-Native

Unlike platforms where identity is an afterthought, REFINET Cloud is built around wallet identity from the ground up. Your Ethereum address is your primary identifier. ENS names are resolved and cached. Email aliases are auto-generated. Pseudo-IPv6 addresses enable DHT-style peer addressing. Every message, every contract, every API call is tied to a cryptographic identity.

---

## 5. Capacity and Availability

GROOT operates on dedicated infrastructure with the following service characteristics:

| Metric | Value |
|---|---|
| Inference speed | Human reading pace (~25 tokens/second) |
| Response latency | 5-15 seconds for a typical response |
| Streaming | Token-by-token delivery via Server-Sent Events |
| Anonymous daily allocation | 25 inference requests per day |
| Authenticated daily allocation | 250 inference requests per day |
| Webhook delivery | Signed, event-driven, real-time with retry |
| Device connections | Unlimited (non-inference operations) |
| Agent connections | Unlimited (non-inference operations) |
| Messaging | Unlimited (non-inference operations) |
| Telemetry ingestion | Unlimited |
| Protocol adapters | 6 (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks) |
| Supported chains | 6 (Ethereum, Polygon, Arbitrum, Optimism, Base, Sepolia) |
| Availability target | 99.5% uptime |

Inference is sequential — requests are processed one at a time in order of arrival. During periods of high demand, requests queue. The streaming delivery model means users see the first tokens of a response as soon as generation begins, which provides a responsive experience even when the system is under load.

Non-inference operations — webhooks, telemetry, authentication, device management, messaging, registry operations, knowledge search — are handled by a separate processing layer and are not constrained by inference throughput.

---

## 6. What's Built & What's Next

### Recently Shipped

**Agent Engine (v3.0).** Autonomous multi-agent platform with SOUL.md identity, 4-tier memory (working, episodic, semantic, procedural), 6-phase cognitive loop, MCP tool access, and agent-to-agent delegation. Five built-in archetypes: groot-chat, contract-analyst, knowledge-curator, platform-ops, dapp-builder.

**DApp Factory.** Template-based DApp assembly from registry contracts. Five templates: token-dashboard, nft-gallery, staking-ui, dao-voter, multi-send. Build pipeline with downloadable ZIP output.

**App Store.** Marketplace for publishing and discovering DApps, agents, tools, and templates with ratings, install tracking, and versioning.

**Chain Listener.** On-chain event monitoring for EVM-compatible chains with configurable watchers and webhook-triggered backend actions.

**Task Scheduler & Script Runner.** Cron-like background task execution with safe script runner supporting 23 operational scripts across 5 categories (analysis, maintenance, ops, chain, dapp).

**Projects Dashboard.** User-facing project collection page with getting-started guide for new users.

### Roadmap

**Multi-model routing.** As additional open-source models become available in efficient architectures, GROOT will route queries to the most appropriate model based on task complexity, with the current model serving as the default general-purpose layer.

**Contract execution simulation.** CAG will extend beyond retrieval to include simulated contract execution — allowing GROOT to explain not just what a contract does, but what would happen if a specific transaction were submitted with specific parameters.

**End-to-end encrypted messaging.** The wallet identity system stores public keys in preparation for E2EE implementation using X3DH key exchange and Double Ratchet protocol.

**Edge inference.** GROOT's underlying model architecture is designed for CPU execution. Future releases will enable partners to run inference locally on their own hardware while maintaining connection to REFINET Cloud's knowledge base and identity layer. Intelligence at the edge, grounded by the network.

---

## 7. How to Connect

**Users:** Visit `app.refinet.io` and start talking. Connect your wallet for full access.

**Developers:** Read the API documentation at `app.refinet.io/docs`. Connect your wallet, generate an API key, and make your first call in under five minutes. Choose your protocol: REST, GraphQL, gRPC, SOAP, or WebSocket.

**Contract Developers:** Upload your ABIs to GROOT Brain at `app.refinet.io/repo`. GROOT will parse, analyze, and generate SDK definitions automatically. Browse the public registry at `app.refinet.io/explore`. Build DApps from your contracts at `app.refinet.io/dapps`.

**Agent Developers:** Register agents via `POST /agents`, assign a SOUL identity, and submit tasks. Agents run autonomously through the cognitive loop with access to platform tools via MCP. See [AGENT_ENGINE.md](AGENT_ENGINE.md) for the full architecture.

**Partners:** Subscribe to webhook events for async integration. Register devices and agents for network participation. Monitor on-chain events via the chain listener.

**Devices:** Any HTTP-capable device can register via `POST /devices` with a provisioned key. No SDK required.

---

*GROOT Intelligence is a product of REFINET — the Regenerative Finance Network.*
*Infrastructure that grows from the ground up.*

*Platform licensed under AGPL-3.0.*
