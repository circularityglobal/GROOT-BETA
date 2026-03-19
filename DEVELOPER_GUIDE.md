# REFINET Cloud — Developer Guide

Start here. This guide gets you from zero to productive.

---

## What is REFINET Cloud?

REFINET Cloud is a sovereign AI platform for the Regenerative Finance Network. It combines free AI inference (BitNet), a multi-agent autonomous engine, smart contract registry, DApp factory, app store, encrypted messaging, and IoT connectivity — all on permanently free Oracle Cloud infrastructure.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 + SQLite (WAL mode) |
| Inference | BitNet b1.58 via bitnet.cpp (CPU-native, ARM-optimized) |
| Multi-Provider | BitNet → Gemini → Ollama → LM Studio → OpenRouter fallback |
| RAG | sentence-transformers (384-dim) + FTS5 full-text search |
| Frontend | Next.js 14 + React 18 + TypeScript + Tailwind CSS |
| Web3 | wagmi + viem (frontend) + web3.py + eth-account (backend) |
| Auth | SIWE (EIP-4361) + Argon2id + TOTP + JWT (12 scopes) |
| Protocols | 6-protocol MCP Gateway (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks) |
| Server | Oracle Cloud ARM A1 Flex (4 OCPUs, 24GB RAM) |

## Quickstart

```bash
# 1. Clone
git clone <repo-url> groot && cd groot

# 2. Environment
cp .env.example .env
# Edit .env — fill in SECRET_KEY, REFRESH_SECRET, SERVER_PEPPER,
# WEBHOOK_SIGNING_KEY, INTERNAL_DB_ENCRYPTION_KEY, ADMIN_API_SECRET
# (generate each with: python3 -c "import secrets; print(secrets.token_hex(32))")

# 3. Run with Docker
docker-compose up --build

# 4. Verify
curl http://localhost:8000/health          # API health
curl http://localhost:4000                  # Frontend
```

**Without Docker:**
```bash
# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Project Structure

```
groot/
├── SOUL.md                        # GROOT's AI identity (always loaded)
├── SAFETY.md                      # Hard constraints (always injected into inference)
├── MEMORY.md                      # Memory access protocol
├── HEARTBEAT.md                   # System health pulse config
├── AGENTS.md                      # Active agent registry (10 archetypes)
│
├── api/                           # Python backend (FastAPI)
│   ├── main.py                    # App factory, router registration, lifespan
│   ├── config.py                  # Settings (env vars + YAML hierarchy)
│   ├── database.py                # SQLAlchemy sessions (public.db + internal.db)
│   ├── auth/                      # 12 auth modules (SIWE, JWT, API keys, TOTP, etc.)
│   ├── middleware/                # CORS, rate limiting, request logging, protocol auth
│   ├── models/                    # SQLAlchemy ORM (7 model files, 50+ tables)
│   ├── routes/                    # 25 route files, 210+ endpoints
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── services/                  # 64 service modules (business logic)
│   │   ├── providers/             # Model provider plugins (BitNet, Gemini, Ollama, etc.)
│   │   ├── agent_engine.py        # 6-phase cognitive loop
│   │   ├── agent_soul.py          # 7-layer context injection stack
│   │   ├── agent_memory.py        # 4-tier memory system
│   │   ├── trigger_router.py      # Event → agent task routing
│   │   ├── output_router.py       # Task result → multi-target routing
│   │   ├── token_budget.py        # Context window token management
│   │   ├── context_loader.py      # Cached filesystem doc loader
│   │   ├── rag.py                 # Retrieval-Augmented Generation
│   │   ├── gateway.py             # Universal model gateway
│   │   ├── mcp_gateway.py         # MCP tool dispatcher
│   │   ├── scheduler.py           # Cron/interval task scheduler
│   │   ├── event_bus.py           # In-process pub/sub
│   │   ├── webhook_delivery.py    # HMAC-signed webhook delivery
│   │   ├── chain_listener.py      # On-chain event polling
│   │   ├── messenger_bridge.py    # Telegram/WhatsApp bridges
│   │   ├── sandbox.py             # Docker container isolation
│   │   ├── jsonl_logger.py        # JSONL episodic audit trail
│   │   └── workers.py             # 5 deterministic background workers
│   ├── grpc/                      # gRPC server (port 50051)
│   └── tests/                     # 10 test files
│
├── frontend/                      # Next.js 14 frontend
│   ├── app/                       # 16 page directories
│   ├── components/                # 17 component directories
│   └── lib/                       # API client, config, wallet
│
├── configs/                       # YAML configuration hierarchy
│   ├── default.yaml               # Base settings (merged first)
│   └── production.yaml            # Production overrides
│
├── skills/                        # GROOT skill definitions (SKILL.md)
│   ├── answer-question/
│   ├── analyze-telemetry/
│   └── summarize-contract/
│
├── docs/                          # Technical documentation
│   ├── ARCHITECTURE.md            # System architecture deep dive
│   ├── AGENT_ENGINE.md            # Agent engine specification
│   ├── API_REFERENCE.md           # Complete API reference
│   ├── APP_STORE.md               # App store pipeline
│   ├── SAFETY.md                  # Safety constraints (detailed)
│   ├── SOUL_FORMAT.md             # SOUL.md format specification
│   ├── HEARTBEAT.md               # Health monitoring (detailed)
│   └── GROOT_INTELLIGENCE_WHITEPAPER.md
│
├── scripts/                       # Admin, analysis, maintenance, seed scripts
├── migrations/                    # SQL schema migrations (9 files)
├── nginx/                         # Nginx config for production
└── docker-compose.yml             # Development environment
```

## Key Concepts

### 1. SOUL Identity
Every agent has a SOUL.md defining its persona, goals, constraints, tools, and delegation policy. The root `SOUL.md` defines GROOT's default identity. See `docs/SOUL_FORMAT.md`.

### 2. 7-Layer Context Injection
Every inference call passes through a context assembly pipeline that injects 7 layers into the system prompt, managed by a token budget tracker:

| Layer | Content | Budget | File |
|---|---|---|---|
| 0 | Root SOUL.md (GROOT identity) | 300 tokens | `context_loader.py` |
| 1 | Agent-specific SOUL (from DB) | 200 tokens | `agent_soul.py` |
| 2 | Memory state (working + episodic) | 100 tokens | `agent_memory.py` |
| 3 | RAG context (knowledge + contracts) | 400 tokens | `rag.py` |
| 4 | Skills metadata (from skills/) | 50 tokens | `context_loader.py` |
| 5 | SAFETY.md (hard constraints) | 150 tokens | `context_loader.py` |
| 6 | Runtime (datetime, model, tokens) | 50 tokens | `agent_soul.py` |

Total: 1,536 usable tokens out of BitNet's 2,048 context window (512 reserved for completion).

### 3. Trigger Router
Events from 5 sources (heartbeat, cron, webhook, chain, messenger) are normalized into agent tasks via the trigger router:
```
device.telemetry.*  → device-monitor agent
chain.event.*       → contract-watcher agent
knowledge.document.* → knowledge-curator agent
system.health.*     → maintenance agent
```

### 4. Output Router
After a cognitive loop completes, results route to configured targets:
- `json_store` — persist to DB (default)
- `response` — return to API caller (default)
- `memory` — write to episodic/semantic memory (default)
- `agent` — chain result to another agent's task
- `webhook` — publish to EventBus → webhook delivery

### 5. Multi-Provider Gateway
Inference requests go through a universal gateway with automatic fallback:
```
BitNet (sovereign, free) → Gemini (free tier) → Ollama (local) → LM Studio (local) → OpenRouter (paid)
```
Users can also bring their own API keys for any OpenAI-compatible provider.

### 6. Event Bus
In-process pub/sub with wildcard pattern matching. All subsystems communicate via events:
```python
bus.subscribe("chain.*", handler)          # All chain events
bus.subscribe("agent.task.completed", h)   # Specific event
await bus.publish("registry.sdk.created", data)
```

## Development Workflow

### Adding a new API route
1. Create `api/routes/my_feature.py` with a FastAPI `APIRouter`
2. Register it in `api/main.py` → `create_app()` function
3. Add Pydantic schemas in `api/schemas/` if needed

### Adding a new service
1. Create `api/services/my_service.py` with business logic functions
2. Import and use from routes or other services

### Adding an agent archetype
1. Write a SOUL.md template (see `docs/SOUL_FORMAT.md`)
2. Add it to `docs/AGENTS.md` with Identity, Goals, Constraints, Tools, Delegation
3. Add the trigger mapping to `api/services/trigger_router.py` TRIGGER_MAP
4. Register via API: `POST /agents/register` + `POST /agents/{id}/soul`

### Adding a skill
1. Create `skills/my-skill/SKILL.md` with YAML frontmatter (name, description, trigger, agent, input, output)
2. Skills metadata is automatically loaded into Layer 4 of the context injection stack

### Adding a config key
1. Add to `configs/default.yaml` with a sensible default
2. Access in code: `from api.config import get_yaml_value; val = get_yaml_value("section.key", default)`

## Testing

```bash
# Run all agent engine tests (always pass)
python3 -m pytest api/tests/test_agent_engine.py -v

# Run specific test file
python3 -m pytest api/tests/test_webhooks.py -v

# Run all tests (some require Python 3.10+ due to auth/enforce.py)
python3 -m pytest api/tests/ -v
```

## Documentation Index

| Document | Purpose |
|---|---|
| `DEVELOPER_GUIDE.md` | You are here |
| `README.md` | Platform overview and feature list |
| `GROOT.md` | Master architecture document with constraints and rules |
| `DEPLOY_ORACLE_CLOUD.md` | Step-by-step production deployment |
| `docs/ARCHITECTURE.md` | Technical architecture deep dive |
| `docs/AGENT_ENGINE.md` | Agent engine specification |
| `docs/API_REFERENCE.md` | Complete API endpoint reference |
| `docs/APP_STORE.md` | App store submission and review pipeline |
| `docs/SAFETY.md` | Platform-wide safety constraints |
| `docs/SOUL_FORMAT.md` | Agent SOUL.md format specification |
| `docs/HEARTBEAT.md` | Health monitoring and scheduled tasks |
| `docs/GROOT_INTELLIGENCE_WHITEPAPER.md` | Vision and technical whitepaper |
| `scripts/README.md` | Script documentation and usage |
| `frontend/README.md` | Frontend structure and development |
| `configs/README.md` | YAML configuration hierarchy |
