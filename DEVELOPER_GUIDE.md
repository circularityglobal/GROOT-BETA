# REFINET Cloud — Developer Guide

Start here. This guide gets you from zero to productive.

---

## What is REFINET Cloud?

REFINET Cloud is a sovereign AI platform for the Regenerative Finance Network. It combines free AI inference (BitNet), a multi-agent autonomous engine, smart contract registry, DApp factory, app store, encrypted messaging, IoT connectivity, a wizard pipeline for on-chain contract deployment, a broker system for paid services, and a payment engine — all on permanently free Oracle Cloud infrastructure.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 + SQLite (WAL mode, 69 tables across 2 databases) |
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
│   ├── auth/                      # Auth modules (SIWE, JWT, API keys, TOTP, enforce)
│   ├── middleware/                # CORS, rate limiting, request logging, protocol auth
│   ├── models/                    # SQLAlchemy ORM (9 model files, 69 tables)
│   │   ├── public.py              # User-facing tables (users, keys, devices, apps, wallets)
│   │   ├── internal.py            # Admin/secrets tables (wallets, config, audit)
│   │   ├── agent_engine.py        # SOUL, 4-tier memory, tasks, delegation
│   │   ├── registry.py            # Contract projects, ABIs, SDKs, stars, forks
│   │   ├── knowledge.py           # Documents, chunks, contract definitions
│   │   ├── brain.py               # Personal contract repositories
│   │   ├── pipeline.py            # Pipeline runs, steps, pending actions, deployments
│   │   ├── payments.py            # Fee schedules, payments, subscriptions, revenue splits
│   │   └── broker.py              # Broker sessions, fee configs
│   ├── routes/                    # 27 route files, 287 endpoints
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── services/                  # 61+ service modules (business logic)
│   │   ├── providers/             # Model provider plugins (BitNet, Gemini, Ollama, etc.)
│   │   ├── agent_engine.py        # 6-phase cognitive loop
│   │   ├── agent_soul.py          # 7-layer context injection stack
│   │   ├── agent_memory.py        # 4-tier memory system
│   │   ├── trigger_router.py      # Event → agent task routing
│   │   ├── output_router.py       # Task result → multi-target routing
│   │   ├── dag_orchestrator.py    # DAG pipeline coordinator (compile→test→deploy)
│   │   ├── wizard_workers.py      # 6 deterministic on-chain workers
│   │   ├── ownership.py           # Contract deployment tracking + ownership transfer
│   │   ├── payment_service.py     # Fees, payments, subscriptions, revenue splits
│   │   ├── broker.py              # Brokered session lifecycle
│   │   ├── xmtp.py                # XMTP protocol wrapper (fallback to internal messaging)
│   │   ├── dapp_validator.py      # DApp build validation + self-repair
│   │   ├── tag_taxonomy.py        # 11-category tag ontology for contract discovery
│   │   ├── gateway.py             # Universal model gateway
│   │   ├── rag.py                 # Retrieval-Augmented Generation
│   │   ├── mcp_gateway.py         # MCP tool dispatcher
│   │   ├── scheduler.py           # Cron/interval task scheduler
│   │   ├── event_bus.py           # In-process pub/sub
│   │   ├── webhook_delivery.py    # HMAC-signed webhook delivery
│   │   ├── chain_listener.py      # On-chain event polling
│   │   ├── sandbox.py             # Docker container isolation
│   │   ├── workers.py             # 5 deterministic background workers
│   │   └── wallet_service.py      # Custodial wallets with Shamir SSS
│   ├── grpc/                      # gRPC server (port 50051)
│   └── tests/                     # 10 test files, 212 test cases
│
├── frontend/                      # Next.js 14 frontend
│   ├── app/                       # Page directories
│   ├── components/                # Component directories
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
├── scripts/                       # 36 scripts across 6 categories
│   ├── analysis/                  # 4 scripts (coverage, stats, reports)
│   ├── chain/                     # 3 scripts (fetch ABI, monitor, read contract)
│   ├── dapp/                      # 5 scripts (build web/python, package, list templates)
│   ├── maintenance/               # 10 scripts (cleanup, backup, rotate, rebuild)
│   ├── ops/                       # 10 scripts (git ops, deploy, health, DB stats)
│   └── seed/                      # 4 scripts (contracts, knowledge, docs, fee schedules)
│
├── migrations/                    # SQL schema migrations (13 public + 1 internal)
│   ├── public/                    # 001-013: user-facing schema
│   └── internal/                  # 001: scheduler + script tables
│
├── docs/                          # Technical documentation (10 files)
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
Events from 7 sources (heartbeat, cron, webhook, chain, messenger, pipeline, broker) are normalized into agent tasks via the trigger router:
```
device.telemetry.*     → device-monitor agent
chain.event.*          → contract-watcher agent
knowledge.document.*   → knowledge-curator agent
system.health.*        → maintenance agent
pipeline.run.completed → orchestrator agent
pipeline.approval.needed → orchestrator agent
broker.session.*       → orchestrator agent
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

### 6. Wizard Pipeline (DAG Orchestrator)
GROOT is the **sole Wizard** — all on-chain actions go through GROOT's SSS-secured wallet. The DAG orchestrator coordinates 4 pipeline templates:

```
compile_test:  [compile] → [test]
deploy:        [compile] → [test] → [rbac_check] → [deploy] → [verify]
full:          [compile] → [test] → [rbac_check] → [deploy] → [verify] → [transfer_ownership]
wizard:        [compile] → [test] → [parse] ─┬→ [rbac_check] → [deploy] → [reparse] ─┬→ [appstore]
                                              └→ [frontend] ─────────────────────────────┘
```

The `wizard` template runs **frontend generation in parallel with deployment** — both depend on parse, not each other. Master admin approval is required for all Tier 2 actions.

### 6.1 CAG (Contract-Augmented Generation)
GROOT uses the contract registry as its logic repository through three access modes:
- **Query** — search public SDKs to answer questions (autonomous)
- **Execute** — call view/pure functions on-chain to read state (autonomous, no gas)
- **Act** — request state-changing transactions (creates PendingAction for master_admin approval)

CAG context is injected as Layer 3.5 in GROOT's 8-layer system prompt (SOUL → agent → memory → RAG → **CAG** → skills → safety → runtime).

### 6.2 Roles & Authorization
- **master_admin** — exclusive control over GROOT's wallet, Tier 2 approvals, chain management
- **admin** — system administration, user management, app store review
- **operator** — monitoring and operational tasks
- **readonly** — view-only access

### 6.3 Dynamic Chain Registry
Chains are stored in the `supported_chains` database table. Admin can add any EVM chain via:
```bash
# API: import from chainlist.org
POST /admin/chains/import { "chain_id": 43114 }  # Avalanche

# Or manually
POST /admin/chains { "chain_id": 43114, "name": "Avalanche", "rpc_url": "https://..." }
```

### 6.4 Contract Import
Place chain-agnostic ABI files in `data/contracts/abis/`:
```bash
python3 scripts/import_contracts.py                    # Import all
python3 scripts/import_contracts.py --fetch 0x... --chain ethereum  # Fetch from explorer
```

### 7. Event Bus
In-process pub/sub with wildcard pattern matching. All subsystems communicate via events:
```python
bus.subscribe("chain.*", handler)          # All chain events
bus.subscribe("pipeline.run.completed", h) # Specific event
bus.subscribe("broker.session.*", h)       # All broker events
await bus.publish("registry.sdk.created", data)
```

### 8. Payment & Revenue
Fee schedules define per-service pricing with tier-based discounts. Revenue splits distribute payments between platform, developer, and broker:
```python
# Fee calculation respects user tier
fee = get_fee(db, "deploy", user_tier="developer")

# Revenue split: platform 50% / developer 50%
execute_revenue_split(db, payment_id)
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

### Adding a wizard worker
1. Add the worker function to `api/services/wizard_workers.py` following the existing pattern
2. Register it in `WORKER_DISPATCH` dict in `api/services/dag_orchestrator.py`
3. Add the step to the pipeline template in `PIPELINE_TEMPLATES`

### Adding a new execution script
1. Create `scripts/<category>/my_script.py` with `SCRIPT_META` dict and `main()` function
2. Scripts are auto-discovered by `script_runner.py` — no registration needed

## Testing

```bash
# Run all tests (207 pass, 5 known pre-existing failures)
python3 -m pytest api/tests/ -v

# Run agent engine tests only (18/18 pass)
python3 -m pytest api/tests/test_agent_engine.py -v

# Run specific test file
python3 -m pytest api/tests/test_webhooks.py -v

# Verify all imports (quick smoke test)
python3 -c "import api.models; print('Models OK')"
python3 -c "from api.services.dag_orchestrator import PIPELINE_TEMPLATES; print(f'Pipelines: {list(PIPELINE_TEMPLATES.keys())}')"
```

## Documentation Index

| Document | Purpose |
|---|---|
| `DEVELOPER_GUIDE.md` | You are here |
| `README.md` | Platform overview and feature list |
| `GROOT.md` | Master architecture document with constraints and rules |
| `DEPLOY_ORACLE_CLOUD.md` | Step-by-step production deployment |
| `CHANGELOG.md` | Version history and release notes |
| `docs/ARCHITECTURE.md` | Technical architecture deep dive |
| `docs/AGENT_ENGINE.md` | Agent engine specification |
| `docs/API_REFERENCE.md` | Complete API endpoint reference |
| `docs/APP_STORE.md` | App store submission and review pipeline |
| `docs/SAFETY.md` | Platform-wide safety constraints |
| `docs/SOUL_FORMAT.md` | Agent SOUL.md format specification |
| `docs/HEARTBEAT.md` | Health monitoring and scheduled tasks |
| `docs/GROOT_INTELLIGENCE_WHITEPAPER.md` | Vision and technical whitepaper |
| `configs/README.md` | YAML configuration hierarchy |
