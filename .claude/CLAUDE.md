# GROOT / REFINET Cloud — Claude Code Instructions

## Project Overview

REFINET Cloud is a sovereign AI platform with 317 API endpoints, 75 database tables (11 model files), and 23 frontend pages. GROOT is the sole Wizard — the only entity with an on-chain wallet, deployed via Shamir Secret Sharing (3-of-5 threshold).

**Read these files for full context:**
- @GROOT.md — Master architecture, constraints, subsystems
- @DEVELOPER_GUIDE.md — Quickstart, project structure, key concepts
- @CHANGELOG.md — Version history and recent changes

## Tech Stack

- **Backend:** Python 3.9+ / FastAPI 0.115 / SQLAlchemy 2.0 / SQLite (WAL mode, dual DB)
- **Frontend:** Next.js 14 (App Router) / React 18 / TypeScript 5.5 / Tailwind CSS 3.4
- **Web3:** web3.py + eth-account (backend) / wagmi + viem + ethers (frontend)
- **AI:** BitNet b1.58 (CPU-native) + multi-provider gateway (Gemini, Ollama, OpenRouter)
- **Auth:** SIWE (EIP-4361) + Argon2id + PyJWT + TOTP

## Build & Run Commands

```bash
# Backend
source venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev     # http://localhost:4000

# Tests (270 pass)
python3 -m pytest api/tests/ skills/tests/ -v

# Import contracts
python3 scripts/import_contracts.py

# Initialize GROOT wallet (one-time)
python3 scripts/init_groot_wallet.py
```

## Project Structure

```
api/
├── auth/          # SIWE, JWT, roles, TOTP, API keys
├── models/        # SQLAlchemy models (public.py, internal.py, brain.py, chain.py, pipeline.py, ...)
├── routes/        # FastAPI route handlers (29 files, 302+ endpoints)
├── services/      # Business logic (70+ modules)
├── schemas/       # Pydantic request/response models
├── middleware/     # CORS, rate limiting, logging, request ID, response cache
└── main.py        # App factory with lifespan, router registration

frontend/
├── app/           # Next.js App Router pages (24 routes)
├── components/    # React components (AuthFlow, WalletOnboarding, etc.)
└── lib/           # API client (api.ts), config, wallet utils

skills/
├── refinet-platform-ops/       # Platform ops (monitoring, health checks, agent pipeline)
│   ├── SKILL.md                # 620-line skill (8 parts)
│   ├── scripts/                # health_check.py, run_agent.sh (zero-cost pipeline runner)
│   └── references/             # api-endpoints.md, agent-engine.md, email-templates.md
├── refinet-knowledge-curator/  # Knowledge base maintenance (RAG/CAG integrity)
│   ├── SKILL.md                # 546-line skill (7 parts)
│   ├── scripts/                # knowledge_health.py (orphan/stale/CAG checker)
│   └── references/             # knowledge-api.md, embedding-pipeline.md
├── refinet-contract-watcher/   # On-chain intelligence (ABI security, events, bridges)
│   ├── SKILL.md                # 620-line skill (7 parts)
│   ├── scripts/                # contract_scan.py (ABI scanner, 8 dangerous patterns)
│   └── references/             # chain-api.md, registry-api.md
├── answer-question/            # RAG knowledge base query skill
├── analyze-telemetry/          # IoT anomaly detection skill
└── summarize-contract/         # Contract SDK summarization skill

memory/                    # Persistent agent memory (runtime data gitignored)
├── working/               # Per-agent working state (JSON, per-run)
├── episodic/              # Agent run logs (JSONL, append-only)
├── semantic/              # Distilled facts + embeddings (permanent)
└── procedural/            # Learned tool-use patterns (permanent)

scripts/           # 40+ operational scripts (import, seed, maintenance, chain)
configs/           # YAML config hierarchy (default.yaml, production.yaml)
migrations/        # SQL migrations (public/ and internal/)
data/              # Runtime data (gitignored — databases, contract ABIs)
```

## Database Architecture

Two physically separate SQLite databases in WAL mode:
- **public.db** — User-facing data (users, contracts, SDKs, knowledge, pipelines, deployments)
- **internal.db** — Admin-only (secrets, roles, audit log, GROOT wallet shares, scheduled tasks)

Models MUST be imported in `api/models/__init__.py` for `create_all()` to work.

When adding new tables: create model in `api/models/`, export in `__init__.py`, optionally add migration SQL in `migrations/`.

## Key Architectural Patterns

### GROOT is the Sole Wizard
- ONE wallet (`user_id="__groot__"`) for all on-chain operations
- `deploy_worker` and `transfer_ownership_worker` use `sign_transaction_with_groot_wallet()`
- Users NEVER have their own deployment wallets — GROOT deploys, then transfers ownership
- All Tier 2 actions require `master_admin` approval via PendingAction

### CAG (Contract-Augmented Generation)
Three access modes in `api/services/contract_brain.py`:
- `cag_query()` — search public SDKs (autonomous)
- `cag_execute()` — view/pure calls on-chain (autonomous)
- `cag_act()` — state-changing calls (creates PendingAction)

CAG context injected as Layer 3.5 in GROOT's 8-layer prompt stack (agent_soul.py).

### Dynamic Chain Registry
Chains stored in `supported_chains` table, NOT hardcoded dicts. Use `ChainRegistry.get()` from `api/services/chain_registry.py` for all chain lookups. Hardcoded fallbacks exist in wizard_workers.py for when DB is unavailable.

### Pipeline DAG
4 templates in `api/services/dag_orchestrator.py`: `compile_test`, `deploy`, `full`, `wizard`.
The `wizard` template has parallel paths — frontend depends on parse (not deploy).

## Coding Standards

### Python (Backend)
- Python 3.9 compatible — use `Optional[str]` not `str | None`, `list[dict]` not `List[Dict]`
- Lazy imports inside functions for cross-module dependencies (prevents circular imports)
- All wallet/key operations must zero sensitive bytes after use (`ctypes.memset`)
- Source code is PRIVATE — never include in API responses or GROOT context
- Use `get_public_db()` / `get_internal_db()` context managers for DB sessions
- Internal DB is NEVER exposed via public API endpoints

### TypeScript (Frontend)
- `'use client'` directive on all interactive pages
- Fetch chains dynamically from `/explore/chains`, never hardcode chain arrays
- Auth token from `localStorage.getItem('refinet_token')`
- API calls via `API_URL` from `@/lib/config`

### Security Rules
- NEVER commit `.env`, `*.db`, `*.pem`, `*.key` files
- NEVER store private keys — only SSS-encrypted shares
- NEVER bypass `_require_master_admin` for GROOT wallet operations
- NEVER expose `internal.db` data through public API endpoints
- Audit log is append-only — no UPDATE or DELETE routes

## Testing

```bash
python3 -m pytest api/tests/ skills/tests/ -v  # Full suite (270 pass)
python3 -m pytest api/tests/ -v                # API tests only (214 pass)
python3 -m pytest skills/tests/ -v             # Skills pipeline tests (56 pass)
python3 -m pytest api/tests/test_agent_engine.py -v  # Agent engine (18/18)

# Standalone skill health checks (against real DB)
DATABASE_PATH=data/public.db python3 skills/refinet-platform-ops/scripts/health_check.py
DATABASE_PATH=data/public.db python3 skills/refinet-knowledge-curator/scripts/knowledge_health.py
DATABASE_PATH=data/public.db python3 skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis
```

## Common Tasks

### Add a new API endpoint
1. Create/edit route in `api/routes/`
2. Register router in `api/main.py` if new file
3. Add Pydantic schemas in `api/schemas/` if needed
4. Update `docs/API_REFERENCE.md`

### Add a new database table
1. Create model in `api/models/` (use `PublicBase` or `InternalBase`)
2. Export in `api/models/__init__.py`
3. Add migration in `migrations/public/` or `migrations/internal/`
4. `init_databases()` calls `create_all()` automatically

### Add a new EVM chain
Admin dashboard → Networks tab → enter chain ID → Import from chainlist.org.
Or: `POST /admin/chains/import { "chain_id": 43114 }` (master_admin required).

### Import contracts
Place JSON in `data/contracts/abis/`, run `python3 scripts/import_contracts.py`.
Format: `{"name": "...", "abi": [...], "deployments": [{"chain_id": 1, "address": "0x..."}]}`

### Run the autonomous agent pipeline
```bash
# Run a single agent task (uses 4-tier LLM fallback: Claude Code → Ollama → BitNet → Gemini)
./skills/refinet-platform-ops/scripts/run_agent.sh platform-ops "Run health check and email admin"

# Platform health check with email alerts
python3 skills/refinet-platform-ops/scripts/health_check.py --email --always

# Knowledge base health check (orphans, stale chunks, CAG sync)
python3 skills/refinet-knowledge-curator/scripts/knowledge_health.py --repair --email

# ABI security scan (8 dangerous patterns)
python3 skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis --email
```

### Add a new skill
1. Create `skills/my-skill/SKILL.md` with YAML frontmatter (name, description)
2. Add scripts in `skills/my-skill/scripts/` if needed
3. Add references in `skills/my-skill/references/` if needed
4. Skills metadata is auto-loaded into Layer 4 of the context injection stack
