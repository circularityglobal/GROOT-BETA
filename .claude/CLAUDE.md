# GROOT / REFINET Cloud — Claude Code Instructions

## Project Overview

REFINET Cloud is a sovereign AI platform with 302+ API endpoints, 71+ database tables, and 24 frontend pages. GROOT is the sole Wizard — the only entity with an on-chain wallet, deployed via Shamir Secret Sharing (3-of-5 threshold).

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

# Tests
python3 -m pytest api/tests/ -v

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
├── middleware/     # CORS, rate limiting, logging, request ID
└── main.py        # App factory with lifespan, router registration

frontend/
├── app/           # Next.js App Router pages (24 routes)
├── components/    # React components (AuthFlow, WalletOnboarding, etc.)
└── lib/           # API client (api.ts), config, wallet utils

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
python3 -m pytest api/tests/ -v          # Full suite (207 pass)
python3 -m pytest api/tests/test_agent_engine.py -v  # Agent engine (18/18)
```

Known test failures (5): auth route path rename + inference mock path — not functional issues.

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
