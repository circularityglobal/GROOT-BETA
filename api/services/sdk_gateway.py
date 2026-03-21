"""
REFINET Cloud — SDK Gateway Service
Deterministic, LLM-free MCP layer for instant contract address resolution
and public SDK retrieval. Agents call these functions via MCP tools.

Two core calls:
1. resolve_contract() — find contract deployments across all chains
2. fetch_sdk()        — get the full public SDK for any contract

Cardinal rule: Only is_public=True SDKs are exposed. Source code is NEVER included.
"""

import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from api.models.brain import ContractRepo, SDKDefinition, ContractFunction
from api.models.chain import ContractDeployment, SupportedChain

logger = logging.getLogger(__name__)

# ── SDK Catalog Cache ───────────────────────────────────────────────
_cache_invalid = threading.Event()
_cache_invalid.set()  # Start dirty so first call rebuilds


def invalidate_sdk_cache(event_name: str = "", data: dict = None):
    """Event bus handler — marks SDK catalog cache as stale."""
    _cache_invalid.set()
    logger.debug("SDK catalog cache invalidated by event: %s", event_name)


# ── Usage Tracking ──────────────────────────────────────────────────

_LOG_PATH = Path("memory/working/sdk_queries.jsonl")


def _log_sdk_query(contract_id: str, tool_name: str):
    """Append to JSONL log for usage analytics. Fire-and-forget."""
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "cid": contract_id,
            "tool": tool_name,
        })
        with open(_LOG_PATH, "a") as f:
            f.write(entry + "\n")
    except Exception:
        pass  # Never block MCP response for logging


# ── Shared Helpers ──────────────────────────────────────────────────

def _resolve_contracts(
    db: Session,
    query: str,
    chain: Optional[str] = None,
    max_results: int = 10,
) -> list:
    """
    Resolve contract(s) by address, slug, or name.
    Searches ContractRepo (brain) and RegistryProject (registry).
    Returns list of ContractRepo rows.
    """
    query = query.strip()
    if not query:
        return []

    base_filter = [
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
    ]
    if chain:
        base_filter.append(ContractRepo.chain == chain)

    # Strategy 1: Address lookup (exact match)
    if query.startswith("0x") and len(query) >= 40:
        addr = query.lower()
        contracts = db.query(ContractRepo).filter(
            ContractRepo.address.ilike(addr),
            *base_filter,
        ).limit(max_results).all()
        if contracts:
            return contracts
        # Try deployment table
        deps = db.query(ContractDeployment).filter(
            ContractDeployment.address.ilike(addr),
        ).limit(max_results).all()
        if deps:
            cids = [d.contract_id for d in deps]
            return db.query(ContractRepo).filter(
                ContractRepo.id.in_(cids),
                *base_filter,
            ).all()

    # Strategy 2: Slug lookup (contains "/")
    if "/" in query:
        contracts = db.query(ContractRepo).filter(
            ContractRepo.slug == query,
            *base_filter,
        ).limit(max_results).all()
        if contracts:
            return contracts
        # Try registry projects
        from api.models.registry import RegistryProject
        proj = db.query(RegistryProject).filter(
            RegistryProject.slug == query,
            RegistryProject.is_active == True,  # noqa: E712
        ).first()
        if proj:
            # Find brain contracts linked to same owner
            return db.query(ContractRepo).filter(
                ContractRepo.user_id == proj.owner_id,
                ContractRepo.name.ilike(f"%{query.split('/')[-1]}%"),
                *base_filter,
            ).limit(max_results).all()

    # Strategy 3: Name/keyword search (ILIKE)
    safe_q = query.replace("%", "\\%").replace("_", "\\_")
    contracts = db.query(ContractRepo).filter(
        or_(
            ContractRepo.name.ilike(f"%{safe_q}%"),
            ContractRepo.description.ilike(f"%{safe_q}%"),
            ContractRepo.tags.ilike(f"%{safe_q}%"),
        ),
        *base_filter,
    ).limit(max_results).all()
    return contracts


def _get_deployments(db: Session, contract_id: str) -> list[dict]:
    """Get all multi-chain deployments for a contract, merged with primary address."""
    rows = (
        db.query(ContractDeployment, SupportedChain)
        .join(SupportedChain, SupportedChain.chain_id == ContractDeployment.chain_id)
        .filter(ContractDeployment.contract_id == contract_id)
        .all()
    )
    deployments = []
    seen = set()
    for dep, chain in rows:
        key = (chain.chain_id, dep.address.lower())
        if key not in seen:
            seen.add(key)
            deployments.append({
                "chain": chain.short_name,
                "chain_id": chain.chain_id,
                "address": dep.address,
                "is_verified": dep.is_verified,
                "explorer_url": chain.explorer_url,
            })
    return deployments


# ── Core MCP Functions ──────────────────────────────────────────────

def resolve_contract(
    db: Session,
    query: str,
    chain: Optional[str] = None,
) -> list[dict]:
    """
    MCP Tool: resolve_contract
    Given a contract name, slug, or address, return all deployment
    addresses across all chains. Deterministic, no LLM.
    """
    contracts = _resolve_contracts(db, query, chain=chain)
    results = []
    for c in contracts:
        deployments = _get_deployments(db, c.id)
        # Include primary address if not already in deployments
        if c.address:
            primary_key = c.address.lower()
            if not any(d["address"].lower() == primary_key for d in deployments):
                deployments.insert(0, {
                    "chain": c.chain,
                    "chain_id": None,
                    "address": c.address,
                    "is_verified": c.is_verified,
                    "explorer_url": None,
                })
        # Check if SDK exists
        has_sdk = db.query(SDKDefinition).filter(
            SDKDefinition.contract_id == c.id,
            SDKDefinition.is_public == True,  # noqa: E712
        ).first() is not None

        results.append({
            "contract_name": c.name,
            "slug": c.slug,
            "description": c.description,
            "chain": c.chain,
            "deployments": deployments,
            "has_sdk": has_sdk,
            "contract_id": c.id,
        })
        _log_sdk_query(c.id, "resolve_contract")
    return results


def fetch_sdk(
    db: Session,
    chain: Optional[str] = None,
    address: Optional[str] = None,
    slug: Optional[str] = None,
    include_abi: bool = False,
) -> dict:
    """
    MCP Tool: fetch_sdk
    Get the full public SDK for a contract. Lookup by chain+address or slug.
    Deterministic, no LLM.
    """
    contract = None

    # Lookup by slug
    if slug:
        contract = db.query(ContractRepo).filter(
            ContractRepo.slug == slug,
            ContractRepo.is_public == True,  # noqa: E712
            ContractRepo.is_active == True,  # noqa: E712
        ).first()

    # Lookup by chain + address
    if not contract and chain and address:
        contract = db.query(ContractRepo).filter(
            ContractRepo.chain == chain,
            ContractRepo.address.ilike(address),
            ContractRepo.is_public == True,  # noqa: E712
            ContractRepo.is_active == True,  # noqa: E712
        ).first()
        # Fallback: check deployment table
        if not contract:
            dep = db.query(ContractDeployment).filter(
                ContractDeployment.address.ilike(address),
            ).first()
            if dep:
                contract = db.query(ContractRepo).filter(
                    ContractRepo.id == dep.contract_id,
                    ContractRepo.is_public == True,  # noqa: E712
                    ContractRepo.is_active == True,  # noqa: E712
                ).first()

    if not contract:
        return {"error": "Public contract not found"}

    # Get SDK
    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract.id,
        SDKDefinition.is_public == True,  # noqa: E712
    ).first()
    if not sdk:
        return {"error": "SDK not available for this contract"}

    try:
        sdk_data = json.loads(sdk.sdk_json)
    except (json.JSONDecodeError, TypeError):
        return {"error": "Invalid SDK data"}

    # Build response
    result = {
        "contract": {
            "name": contract.name,
            "slug": contract.slug,
            "chain": contract.chain,
            "address": contract.address,
            "description": contract.description,
            "tags": _parse_tags(contract.tags),
            "language": contract.language,
            "is_verified": contract.is_verified,
        },
        "functions": sdk_data.get("functions", {}),
        "events": sdk_data.get("events", []),
        "security_summary": sdk_data.get("security_summary", {}),
        "sdk_version": sdk.sdk_version or "1.0.0",
        "sdk_hash": sdk.sdk_hash,
        "generated_at": sdk.generated_at.isoformat() if sdk.generated_at else None,
        "deployments": _get_deployments(db, contract.id),
    }
    if include_abi and contract.abi_json:
        result["abi"] = json.loads(contract.abi_json)

    _log_sdk_query(contract.id, "fetch_sdk")
    return result


def list_chains_for_contract(
    db: Session,
    contract_id: Optional[str] = None,
    slug: Optional[str] = None,
) -> list[dict]:
    """
    MCP Tool: list_chains_for_contract
    Quick lookup — where is this contract deployed?
    """
    cid = contract_id
    if not cid and slug:
        contract = db.query(ContractRepo).filter(
            ContractRepo.slug == slug,
            ContractRepo.is_public == True,  # noqa: E712
            ContractRepo.is_active == True,  # noqa: E712
        ).first()
        if not contract:
            return []
        cid = contract.id

    if not cid:
        return []

    rows = (
        db.query(ContractDeployment, SupportedChain)
        .join(SupportedChain, SupportedChain.chain_id == ContractDeployment.chain_id)
        .filter(ContractDeployment.contract_id == cid)
        .all()
    )
    return [
        {
            "chain": sc.short_name,
            "chain_id": sc.chain_id,
            "chain_name": sc.name,
            "address": dep.address,
            "currency": sc.currency,
            "explorer_url": sc.explorer_url,
            "is_verified": dep.is_verified,
        }
        for dep, sc in rows
    ]


def bulk_sdk_export(
    db: Session,
    chain: Optional[str] = None,
    category: Optional[str] = None,
    compact: bool = True,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    MCP Tool: bulk_sdk_export
    Paginated catalog of all public SDKs for agent discovery/bootstrapping.
    """
    page_size = min(page_size, 200)
    offset = (max(page, 1) - 1) * page_size

    base_filter = [
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
    ]
    if chain:
        base_filter.append(ContractRepo.chain == chain)
    if category:
        base_filter.append(ContractRepo.tags.ilike(f"%{category}%"))

    # Count total
    total = db.query(ContractRepo).filter(*base_filter).count()

    # Query with optional SDK join
    rows = (
        db.query(ContractRepo, SDKDefinition)
        .outerjoin(SDKDefinition, SDKDefinition.contract_id == ContractRepo.id)
        .filter(*base_filter)
        .order_by(ContractRepo.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    contracts = []
    for contract, sdk in rows:
        entry = {
            "name": contract.name,
            "slug": contract.slug,
            "chain": contract.chain,
            "address": contract.address,
            "description": contract.description,
            "has_sdk": sdk is not None and sdk.is_public,
        }
        if not compact and sdk and sdk.is_public:
            try:
                sdk_data = json.loads(sdk.sdk_json)
                entry["functions"] = sdk_data.get("functions", {})
                entry["events"] = sdk_data.get("events", [])
                entry["security_summary"] = sdk_data.get("security_summary", {})
            except (json.JSONDecodeError, TypeError):
                pass
        elif sdk and sdk.is_public:
            # Compact mode — just function count
            try:
                sdk_data = json.loads(sdk.sdk_json)
                pub_fns = sdk_data.get("functions", {}).get("public", [])
                admin_fns = sdk_data.get("functions", {}).get("owner_admin", [])
                entry["public_function_count"] = len(pub_fns)
                entry["admin_function_count"] = len(admin_fns)
            except (json.JSONDecodeError, TypeError):
                pass
        contracts.append(entry)

    return {
        "contracts": contracts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 0,
    }


def _parse_tags(tags_str: Optional[str]) -> list:
    """Parse JSON tags string to list."""
    if not tags_str:
        return []
    try:
        return json.loads(tags_str)
    except (json.JSONDecodeError, TypeError):
        return []
