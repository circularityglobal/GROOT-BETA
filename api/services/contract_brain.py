"""
REFINET Cloud — Contract Brain Service
CAG (Contract Augmented Generation) for GROOT.
Searches public SDK definitions to enrich GROOT's context.

Cardinal rule: GROOT only sees SDK definitions where is_public=True.
Source code is NEVER included.
"""

import json
import re
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from api.models.brain import ContractRepo, SDKDefinition, ContractFunction


def search_public_sdks(
    db: Session,
    query: str,
    chain: Optional[str] = None,
    max_results: int = 3,
) -> list[dict]:
    """
    Search public SDK definitions by keyword.
    Uses JOIN to batch queries (optimized for 1000+ contracts).
    Returns SDK excerpts for GROOT context injection.
    """
    keywords = re.findall(r'\w+', query.lower())
    if not keywords:
        return []

    # Build keyword conditions for contract name/description/tags
    kw_conditions = []
    for kw in keywords[:5]:
        safe_kw = kw.replace("%", "\\%").replace("_", "\\_")
        kw_conditions.append(or_(
            ContractRepo.name.ilike(f"%{safe_kw}%"),
            ContractRepo.description.ilike(f"%{safe_kw}%"),
            ContractRepo.tags.ilike(f"%{safe_kw}%"),
        ))

    # Also search by function name/signature (find contract IDs)
    fn_conditions = []
    for kw in keywords[:5]:
        safe_kw = kw.replace("%", "\\%").replace("_", "\\_")
        fn_conditions.append(or_(
            ContractFunction.function_name.ilike(f"%{safe_kw}%"),
            ContractFunction.signature.ilike(f"%{safe_kw}%"),
        ))

    fn_contract_ids = set()
    if fn_conditions:
        fn_results = db.query(ContractFunction.contract_id).filter(
            or_(*fn_conditions),
        ).distinct().limit(max_results * 2).all()
        fn_contract_ids = {r[0] for r in fn_results}

    # Single JOIN query: ContractRepo + SDKDefinition
    base_filter = [
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
        SDKDefinition.is_public == True,  # noqa: E712
    ]
    if chain:
        base_filter.append(ContractRepo.chain == chain)

    # Combine: contracts matching keywords OR contracts matching function search
    if fn_contract_ids:
        combined_filter = or_(
            or_(*kw_conditions) if kw_conditions else False,
            ContractRepo.id.in_(fn_contract_ids),
        )
    else:
        combined_filter = or_(*kw_conditions) if kw_conditions else False

    rows = (
        db.query(ContractRepo, SDKDefinition)
        .join(SDKDefinition, SDKDefinition.contract_id == ContractRepo.id)
        .filter(combined_filter, *base_filter)
        .limit(max_results)
        .all()
    )

    results = []
    for contract, sdk in rows:
        try:
            sdk_data = json.loads(sdk.sdk_json)
            public_fns = [f["name"] for f in sdk_data.get("functions", {}).get("public", [])]
            admin_fns = [f["name"] for f in sdk_data.get("functions", {}).get("owner_admin", [])]
            security = sdk_data.get("security_summary", {})
        except (json.JSONDecodeError, KeyError):
            public_fns = []
            admin_fns = []
            security = {}

        results.append({
            "contract_name": contract.name,
            "chain": contract.chain,
            "address": contract.address,
            "description": contract.description,
            "public_functions": public_fns,
            "admin_functions": admin_fns,
            "security_summary": security,
            "sdk_json": sdk.sdk_json,
        })

    return results


def ingest_sdk_to_knowledge(db: Session, contract: "ContractRepo", sdk: "SDKDefinition") -> Optional[str]:
    """
    Bridge SDK definitions into the knowledge base for RAG.
    Creates a KnowledgeDocument + KnowledgeChunks from the SDK's textual content
    so GROOT can find contract info through normal RAG search.

    Returns the document_id if created, None if already exists or failed.
    """
    try:
        sdk_data = json.loads(sdk.sdk_json)
    except (json.JSONDecodeError, TypeError):
        return None

    # Build a human-readable summary from the SDK
    parts = [f"# {contract.name} — Smart Contract SDK"]
    if contract.description:
        parts.append(f"\n{contract.description}")
    parts.append(f"\nChain: {contract.chain}")
    if contract.address:
        parts.append(f"Address: {contract.address}")

    # Public functions
    public_fns = sdk_data.get("functions", {}).get("public", [])
    if public_fns:
        parts.append("\n## Public Functions")
        for fn in public_fns:
            sig = fn.get("signature", fn.get("name", ""))
            desc = fn.get("natspec_notice", "")
            parts.append(f"- `{sig}`{': ' + desc if desc else ''}")

    # Admin functions
    admin_fns = sdk_data.get("functions", {}).get("owner_admin", [])
    if admin_fns:
        parts.append("\n## Admin/Owner Functions (Restricted)")
        for fn in admin_fns:
            sig = fn.get("signature", fn.get("name", ""))
            modifier = fn.get("access_modifier", "")
            parts.append(f"- `{sig}` [{modifier}]")

    # Events
    events = sdk_data.get("events", [])
    if events:
        parts.append("\n## Events")
        for ev in events:
            parts.append(f"- {ev.get('name', '')}({ev.get('signature', '')})")

    # Security summary
    security = sdk_data.get("security_summary", {})
    if security:
        parts.append("\n## Security")
        parts.append(f"Access control: {security.get('access_control_pattern', 'unknown')}")
        if security.get("dangerous_functions"):
            parts.append(f"Dangerous functions detected: {', '.join(security['dangerous_functions'])}")

    content = "\n".join(parts)

    # Use the RAG ingest pipeline
    from api.services.rag import ingest_document

    tags = []
    if contract.tags:
        try:
            tags = json.loads(contract.tags)
        except (json.JSONDecodeError, TypeError):
            pass
    tags.append("contract-sdk")
    tags.append(contract.chain)

    doc = ingest_document(
        db=db,
        title=f"{contract.name} SDK ({contract.chain})",
        content=content,
        category="contract-sdk",
        uploaded_by=contract.user_id,
        source_filename=f"{contract.slug}.sdk.json",
        tags=tags,
    )
    return doc.id if doc else None


def get_sdk_context_for_groot(
    db: Session,
    query: str,
    max_results: int = 2,
) -> str:
    """
    Build a context string from public SDK definitions for GROOT's system prompt.
    This is what makes user-uploaded contract SDKs part of GROOT's brain.

    NEVER includes source code — only SDK definitions.
    """
    results = search_public_sdks(db, query, max_results=max_results)
    if not results:
        return ""

    parts = ["=== User Contract SDKs ==="]

    for r in results:
        header = f"[{r['chain'].upper()}: {r['contract_name']}]"
        if r.get("address"):
            header += f" at {r['address']}"
        parts.append(header)

        if r.get("description"):
            parts.append(f"  {r['description']}")

        if r.get("public_functions"):
            fn_list = ", ".join(r["public_functions"][:8])
            parts.append(f"  Public functions: {fn_list}")

        if r.get("admin_functions"):
            admin_list = ", ".join(r["admin_functions"][:5])
            parts.append(f"  Admin functions (restricted): {admin_list}")

        security = r.get("security_summary", {})
        if security:
            parts.append(
                f"  Security: {security.get('public_functions', 0)} public, "
                f"{security.get('admin_functions', 0)} admin, "
                f"pattern: {security.get('access_control_pattern', 'unknown')}"
            )

        parts.append("")  # blank line between contracts

    return "\n".join(parts)


# ── CAG Three Access Modes ───────────────────────────────────────
# Mode 1: QUERY  — search public SDKs (above: search_public_sdks)
# Mode 2: EXECUTE — read on-chain state via view/pure calls
# Mode 3: ACT    — sign transactions after approval

def cag_query(
    db: Session,
    query: str,
    chain: Optional[str] = None,
    max_results: int = 3,
) -> list[dict]:
    """
    CAG Mode 1: QUERY — Search public SDKs to answer user questions.
    Autonomous, no approval needed. GROOT searches public SDK definitions.
    """
    return search_public_sdks(db, query, chain=chain, max_results=max_results)


def cag_execute(
    db: Session,
    contract_address: str,
    chain: str,
    function_name: str,
    args: Optional[list] = None,
) -> dict:
    """
    CAG Mode 2: EXECUTE — Read on-chain state via view/pure function calls.
    Autonomous, no approval needed (no gas, no state change).

    Returns
    -------
    {"success": bool, "result": any, "function": str, "contract": str, "chain": str}

    Raises
    ------
    ValueError
        If function is not view/pure, contract not found, or chain unknown.
    """
    args = args or []

    # Look up SDK — first by direct address, then via contract_deployments
    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_address == contract_address,
        SDKDefinition.is_public == True,  # noqa: E712
    ).first()
    if not sdk:
        # Try multi-chain deployment lookup
        try:
            from api.models.chain import ContractDeployment
            dep = db.query(ContractDeployment).filter(
                ContractDeployment.address == contract_address,
            ).first()
            if dep:
                sdk = db.query(SDKDefinition).filter(
                    SDKDefinition.contract_id == dep.contract_id,
                    SDKDefinition.is_public == True,  # noqa: E712
                ).first()
        except Exception:
            pass
    if not sdk:
        return {"success": False, "error": f"No public SDK found for contract {contract_address}"}

    try:
        sdk_data = json.loads(sdk.sdk_json)
    except (json.JSONDecodeError, TypeError):
        return {"success": False, "error": "Invalid SDK JSON"}

    # Find the function in the SDK and verify it's view/pure
    target_fn = None
    for group_key in ("public", "owner_admin"):
        for fn in sdk_data.get("functions", {}).get(group_key, []):
            if fn.get("name") == function_name:
                target_fn = fn
                break
        if target_fn:
            break

    if not target_fn:
        return {"success": False, "error": f"Function '{function_name}' not found in public SDK"}

    if target_fn.get("state_mutability") or target_fn.get("mutability") not in ("view", "pure"):
        return {
            "success": False,
            "error": f"Function '{function_name}' is {target_fn.get('state_mutability')} — not a view/pure call. "
                     "Use cag_act() for state-changing functions (requires approval).",
        }

    # Build minimal ABI for the function call
    fn_abi = [{
        "type": "function",
        "name": target_fn["name"],
        "inputs": target_fn.get("inputs", []),
        "outputs": target_fn.get("outputs", []),
        "stateMutability": target_fn.get("state_mutability") or target_fn.get("mutability", "nonpayable"),
    }]

    # Execute the view call
    try:
        from web3 import Web3
        from api.services.wizard_workers import CHAIN_RPC

        rpc_url = CHAIN_RPC.get(chain)
        if not rpc_url:
            return {"success": False, "error": f"Unknown chain: {chain}"}

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=fn_abi,
        )

        fn = getattr(contract.functions, function_name)
        result = fn(*args).call()

        # Convert bytes/tuple results to JSON-serializable form
        result = _serialize_web3_result(result)

        return {
            "success": True,
            "result": result,
            "function": function_name,
            "contract": contract_address,
            "chain": chain,
        }

    except Exception as e:
        return {"success": False, "error": f"View call failed: {e}"}


def cag_act(
    db: Session,
    user_id: str,
    contract_address: str,
    chain: str,
    function_name: str,
    args: Optional[list] = None,
) -> dict:
    """
    CAG Mode 3: ACT — Create a PendingAction for state-changing function calls.
    Requires admin approval before GROOT signs and broadcasts the transaction.

    Returns
    -------
    {"pending_action_id": str, "status": "pending", "message": str}
    """
    import uuid
    from api.models.pipeline import PendingAction
    from datetime import datetime, timezone, timedelta

    args = args or []

    # Look up SDK — first by direct address, then via contract_deployments
    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_address == contract_address,
        SDKDefinition.is_public == True,  # noqa: E712
    ).first()
    if not sdk:
        try:
            from api.models.chain import ContractDeployment
            dep = db.query(ContractDeployment).filter(
                ContractDeployment.address == contract_address,
            ).first()
            if dep:
                sdk = db.query(SDKDefinition).filter(
                    SDKDefinition.contract_id == dep.contract_id,
                    SDKDefinition.is_public == True,  # noqa: E712
                ).first()
        except Exception:
            pass
    if not sdk:
        return {"success": False, "error": f"No public SDK found for contract {contract_address}"}

    try:
        sdk_data = json.loads(sdk.sdk_json)
    except (json.JSONDecodeError, TypeError):
        return {"success": False, "error": "Invalid SDK JSON"}

    target_fn = None
    for group_key in ("public", "owner_admin"):
        for fn in sdk_data.get("functions", {}).get(group_key, []):
            if fn.get("name") == function_name:
                target_fn = fn
                break
        if target_fn:
            break

    if not target_fn:
        return {"success": False, "error": f"Function '{function_name}' not found in public SDK"}

    if target_fn.get("state_mutability") or target_fn.get("mutability") in ("view", "pure"):
        return {
            "success": False,
            "error": f"Function '{function_name}' is view/pure — use cag_execute() instead.",
        }

    # Create PendingAction
    action = PendingAction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action_type="contract_call",
        target_chain=chain,
        target_address=contract_address,
        payload_json=json.dumps({
            "function_name": function_name,
            "args": args,
            "contract_address": contract_address,
            "chain": chain,
            "function_abi": {
                "type": "function",
                "name": target_fn["name"],
                "inputs": target_fn.get("inputs", []),
                "outputs": target_fn.get("outputs", []),
                "stateMutability": target_fn.get("state_mutability") or target_fn.get("mutability", "nonpayable"),
            },
        }),
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(action)
    db.flush()

    return {
        "success": True,
        "pending_action_id": action.id,
        "status": "pending",
        "message": (
            f"Action created: call {function_name}() on {contract_address} ({chain}). "
            "Requires admin approval via PUT /admin/actions/{id}/approve."
        ),
    }


def _serialize_web3_result(result):
    """Convert web3 result types to JSON-serializable form."""
    if isinstance(result, bytes):
        return "0x" + result.hex()
    if isinstance(result, (list, tuple)):
        return [_serialize_web3_result(item) for item in result]
    if isinstance(result, dict):
        return {k: _serialize_web3_result(v) for k, v in result.items()}
    if isinstance(result, int) and result > 2**53:
        return str(result)
    return result
