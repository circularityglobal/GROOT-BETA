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

**Platform Subsystems:**
- AI Inference — OpenAI-compatible API with RAG + CAG context injection, multi-provider gateway
- Agent Engine — Autonomous multi-agent platform with SOUL identity, 4-tier memory, 6-phase cognitive loop, tool access, and delegation
- Context Assembly — 7-layer injection stack with token budget tracking (SOUL, agent, memory, RAG, skills, safety, runtime)
- Trigger Router — Unified event→agent task routing from 5 sources (heartbeat, cron, webhook, chain, messenger)
- Output Router — Multi-target task result routing (DB, response, memory, agent chaining, webhook)
- Smart Contract Registry — GitHub-style project management with ABI parsing and SDK generation
- GROOT Brain — Per-user contract repository with source code privacy
- DApp Factory — Template-based DApp assembly from registry contracts (token-dashboard, nft-gallery, staking-ui, dao-voter, multi-send)
- App Store — Publish and discover DApps, agents, tools, and templates with sandbox review pipeline
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
- Admin Panel — Role management, secrets vault, audit log, system config, MCP registry

**Cardinal Rules:**
1. User source code is PRIVATE — GROOT never reads `source_code`, only ABIs and SDKs
2. Internal DB is NEVER accessible via public API — admin operations only
3. Audit log is append-only — no update or delete routes exist
4. Custodial wallet private keys are NEVER stored — only encrypted Shamir shares
5. All 6 protocols use unified authentication middleware
6. Agents inherit owner permissions — no privilege escalation
7. Chain watchers may detect events but NEVER initiate state-changing transactions autonomously

**Scale:**
- 25 route files, 210+ API endpoints
- 50+ database tables (public + internal)
- 64 service modules, 12 auth modules
- 9 migration files, 6 middleware modules
- 10 test files, 29 operational scripts
- 16 frontend pages, 17 components, 10 documentation files
- 5 root control documents (SOUL, SAFETY, MEMORY, HEARTBEAT, AGENTS)
- 4 skills, 2 YAML config files, JSONL audit logging
