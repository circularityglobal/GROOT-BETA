---
paths:
  - "api/services/wizard_workers.py"
  - "api/services/dag_orchestrator.py"
  - "api/services/wallet_service.py"
  - "api/services/contract_brain.py"
  - "api/routes/pipeline.py"
  - "api/routes/workers.py"
  - "scripts/import_contracts.py"
---

# Wizard Pipeline & CAG Rules

## GROOT is the Sole Wizard
- ALL deployments go through GROOT's wallet (`user_id="__groot__"`)
- `deploy_worker` calls `sign_transaction_with_groot_wallet()`, NOT user wallets
- `transfer_ownership_worker` calls `sign_transaction_with_groot_wallet()` to hand ownership to users
- Users NEVER have deployment wallets — GROOT deploys on their behalf

## Pipeline Templates
```
wizard:  compile → test → parse → rbac_check → deploy → reparse → frontend → appstore
                                  (frontend runs PARALLEL — depends on parse, not deploy)
```

## Worker Conventions
- Workers are pure functions: `def worker_name(input_json: dict) -> dict`
- Always return `{"success": True/False, ...}` — never raise exceptions
- `rbac_check_worker` is the only worker that takes an optional `db` parameter
- Workers that touch GROOT wallet import signing functions inside the function body (lazy imports)

## CAG Access Modes
- `cag_query(db, query, chain, max_results)` — autonomous, no approval
- `cag_execute(db, contract_address, chain, function_name, args)` — autonomous, no gas
- `cag_act(db, user_id, contract_address, chain, function_name, args)` — creates PendingAction
- SDK field for mutability: check BOTH `target_fn.get("state_mutability")` and `target_fn.get("mutability")` (SDK generator uses "mutability", parser uses "state_mutability")
- Multi-chain lookup: first check `SDKDefinition.contract_address`, then `ContractDeployment.address`

## Contract Import
- ABI files in `data/contracts/abis/` are chain-agnostic (flat folder, no chain subfolders)
- Deployments array: `[{"chain_id": 1, "address": "0x..."}, ...]`
- Import script creates: User → UserRepository → ContractRepo → ContractFunction/Event → SDKDefinition → ContractDeployment
- All FK chains must be satisfied — create parent records before children

## Approval Flow
- Pipeline pauses at RBAC step → creates PendingAction → master_admin approves/rejects
- `approve_action()` handles pipeline-linked AND standalone actions (groot_transfer_funds, contract_call)
- Standalone actions execute immediately on approval via `_execute_groot_transfer()` or `_execute_groot_contract_call()`
