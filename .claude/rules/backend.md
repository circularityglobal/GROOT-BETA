---
paths:
  - "api/**/*.py"
---

# Backend Development Rules

## Python Compatibility
- Target Python 3.9+ — use `Optional[str]` not `str | None`, `list[dict]` not `List[Dict]`
- Use `from __future__ import annotations` only when necessary for forward refs

## Imports
- Use lazy imports inside functions for cross-module dependencies to prevent circular imports
- Example: `wallet_service.py` imports from `wizard_workers.py` inside `get_groot_wallet_balance()`, not at module level
- Module-level imports only for standard library, SQLAlchemy, FastAPI, and same-package modules

## Database
- Two separate engines: `get_public_engine()` and `get_internal_engine()`
- Use `get_public_db()` / `get_internal_db()` context managers — they auto-commit on success, rollback on error
- For FastAPI routes, use `Depends(public_db_dependency)` / `Depends(internal_db_dependency)`
- New models MUST be added to `api/models/__init__.py` for `create_all()` to register them
- ForeignKey references must point to existing tables — check model exists before adding FK

## Chain Registry
- NEVER use hardcoded chain dicts directly — use `_get_rpc(chain)`, `_get_chain_id(chain)`, `_get_explorer_api(chain)` from wizard_workers.py
- These functions query `ChainRegistry` (DB) first, fall back to hardcoded dicts
- To add chain support: insert into `supported_chains` table, NOT Python dicts

## Event Bus
- Use `EventBus.get().publish(event_name, data)` for async event broadcasting
- Subscribe in `api/main.py` lifespan with pattern matching: `bus.subscribe("pipeline.*", handler)`

## Error Handling
- Workers return `{"success": False, "error": "message"}` — never raise exceptions from workers
- Routes use `raise HTTPException(status_code=..., detail=...)` for client errors
- Wrap external calls (RPC, block explorer) in try/except with timeout
