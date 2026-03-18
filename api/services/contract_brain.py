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
    Returns SDK excerpts for GROOT context injection.
    """
    keywords = re.findall(r'\w+', query.lower())
    if not keywords:
        return []

    # Search contracts by name, description, tags
    conditions = []
    for kw in keywords[:5]:
        safe_kw = kw.replace("%", "\\%").replace("_", "\\_")
        conditions.append(or_(
            ContractRepo.name.ilike(f"%{safe_kw}%"),
            ContractRepo.description.ilike(f"%{safe_kw}%"),
            ContractRepo.tags.ilike(f"%{safe_kw}%"),
        ))

    q = db.query(ContractRepo).filter(
        or_(*conditions),
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
    )
    if chain:
        q = q.filter(ContractRepo.chain == chain)

    contracts = q.limit(max_results * 2).all()

    # Also search by function name/signature
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
        ).distinct().limit(max_results).all()
        fn_contract_ids = {r[0] for r in fn_results}

    # Merge contract IDs
    contract_ids = {c.id for c in contracts} | fn_contract_ids

    # Score and return
    results = []
    for contract_id in list(contract_ids)[:max_results]:
        contract = db.query(ContractRepo).filter(
            ContractRepo.id == contract_id,
            ContractRepo.is_public == True,  # noqa: E712
            ContractRepo.is_active == True,  # noqa: E712
        ).first()
        if not contract:
            continue

        sdk = db.query(SDKDefinition).filter(
            SDKDefinition.contract_id == contract_id,
            SDKDefinition.is_public == True,  # noqa: E712
        ).first()
        if not sdk:
            continue

        # Extract function names from SDK for context
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
