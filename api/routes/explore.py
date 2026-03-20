"""
REFINET Cloud — Explore Routes
Public discovery endpoints for browsing published smart contracts and SDKs.
All endpoints are public (no auth required).
Only shows contracts where is_public=True.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, or_

from api.database import public_db_dependency
from api.models.brain import (
    UserRepository, ContractRepo, ContractFunction,
    ContractEvent, SDKDefinition,
)
from api.schemas.brain import ExploreContractSummary, PaginatedContracts

router = APIRouter(prefix="/explore", tags=["explore"])


@router.get("/contracts")
def browse_public_contracts(
    q: Optional[str] = None,
    chain: Optional[str] = None,
    sort: str = Query("recent", pattern=r"^(recent|name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(public_db_dependency),
):
    """Browse public smart contracts with optional search and filters."""
    query = db.query(ContractRepo).filter(
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
        ContractRepo.status.in_(["parsed", "published"]),
    )

    if q:
        search_term = f"%{q}%"
        query = query.filter(or_(
            ContractRepo.name.ilike(search_term),
            ContractRepo.description.ilike(search_term),
            ContractRepo.tags.ilike(search_term),
        ))

    if chain:
        query = query.filter(ContractRepo.chain == chain)

    # Sort
    if sort == "name":
        query = query.order_by(ContractRepo.name.asc())
    else:  # recent
        query = query.order_by(ContractRepo.created_at.desc())

    total = query.count()
    contracts = query.offset((page - 1) * page_size).limit(page_size).all()

    # Enrich with function/event counts and owner namespace
    items = []
    for c in contracts:
        fn_count = db.query(sqlfunc.count(ContractFunction.id)).filter(
            ContractFunction.contract_id == c.id,
        ).scalar() or 0

        evt_count = db.query(sqlfunc.count(ContractEvent.id)).filter(
            ContractEvent.contract_id == c.id,
        ).scalar() or 0

        repo = db.query(UserRepository).filter(
            UserRepository.id == c.repo_id,
        ).first()

        items.append(ExploreContractSummary(
            id=c.id,
            slug=c.slug,
            name=c.name,
            chain=c.chain,
            language=c.language,
            address=c.address,
            description=c.description,
            tags=c.tags,
            owner_namespace=repo.namespace if repo else "",
            is_verified=c.is_verified,
            function_count=fn_count,
            event_count=evt_count,
            created_at=c.created_at,
        ).model_dump())

    return PaginatedContracts(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size < total),
    ).model_dump()


@router.get("/contracts/{contract_id}/sdk")
def get_public_sdk(
    contract_id: str,
    db: Session = Depends(public_db_dependency),
):
    """Get the public SDK definition for a contract."""
    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract_id,
        SDKDefinition.is_public == True,  # noqa: E712
    ).first()
    if not sdk:
        raise HTTPException(status_code=404, detail="Public SDK not found")

    return {
        "id": sdk.id,
        "contract_id": sdk.contract_id,
        "sdk_version": sdk.sdk_version,
        "sdk_json": sdk.sdk_json,
        "chain": sdk.chain,
        "contract_address": sdk.contract_address,
        "generated_at": sdk.generated_at,
    }


@router.get("/chains")
def list_chains(
    db: Session = Depends(public_db_dependency),
):
    """List all active chains from registry with public contract counts."""
    from api.services.chain_registry import ChainRegistry
    chains = ChainRegistry.get().get_all_chains(active_only=True)

    # Get contract counts per chain
    counts = db.query(
        ContractRepo.chain,
        sqlfunc.count(ContractRepo.id).label("count"),
    ).filter(
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
    ).group_by(ContractRepo.chain).all()
    count_map = {chain: count for chain, count in counts}

    # Also count via contract_deployments
    try:
        from api.models.chain import ContractDeployment
        dep_counts = db.query(
            ContractDeployment.chain_id,
            sqlfunc.count(ContractDeployment.id).label("count"),
        ).group_by(ContractDeployment.chain_id).all()
        dep_map = {cid: count for cid, count in dep_counts}
    except Exception:
        dep_map = {}

    result = []
    for c in chains:
        contract_count = count_map.get(c["short_name"], 0) + dep_map.get(c["chain_id"], 0)
        result.append({
            "chain_id": c["chain_id"],
            "name": c["name"],
            "short_name": c["short_name"],
            "currency": c["currency"],
            "icon_url": c.get("icon_url"),
            "is_testnet": c["is_testnet"],
            "contract_count": contract_count,
        })
    return result


@router.get("/search")
def search_public_sdks(
    q: str = Query(min_length=1, description="Search keyword"),
    chain: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(public_db_dependency),
):
    """Full-text search across public contracts and their functions."""
    search_term = f"%{q}%"

    # Search contracts by name/description
    contract_query = db.query(ContractRepo).filter(
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
        or_(
            ContractRepo.name.ilike(search_term),
            ContractRepo.description.ilike(search_term),
            ContractRepo.tags.ilike(search_term),
        ),
    )

    if chain:
        contract_query = contract_query.filter(ContractRepo.chain == chain)

    # Also find contracts that have matching function names
    fn_contract_ids = db.query(ContractFunction.contract_id).filter(
        or_(
            ContractFunction.function_name.ilike(search_term),
            ContractFunction.signature.ilike(search_term),
        ),
    ).distinct().subquery()

    fn_contracts = db.query(ContractRepo).filter(
        ContractRepo.id.in_(fn_contract_ids),
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
    )

    if chain:
        fn_contracts = fn_contracts.filter(ContractRepo.chain == chain)

    # Union results
    all_contracts = contract_query.union(fn_contracts)
    total = all_contracts.count()
    contracts = all_contracts.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for c in contracts:
        # Get matching function names for context
        matching_fns = db.query(ContractFunction.function_name).filter(
            ContractFunction.contract_id == c.id,
            or_(
                ContractFunction.function_name.ilike(search_term),
                ContractFunction.signature.ilike(search_term),
            ),
        ).limit(5).all()

        repo = db.query(UserRepository).filter(
            UserRepository.id == c.repo_id,
        ).first()

        items.append({
            "id": c.id,
            "slug": c.slug,
            "name": c.name,
            "chain": c.chain,
            "description": c.description,
            "owner_namespace": repo.namespace if repo else "",
            "matching_functions": [fn[0] for fn in matching_fns],
        })

    return PaginatedContracts(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size < total),
    ).model_dump()


@router.get("/@{username}/contracts")
def get_user_public_contracts(
    username: str,
    db: Session = Depends(public_db_dependency),
):
    """View a user's public contracts."""
    repo = db.query(UserRepository).filter(
        UserRepository.namespace == username,
        UserRepository.is_active == True,  # noqa: E712
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="User not found")

    contracts = db.query(ContractRepo).filter(
        ContractRepo.repo_id == repo.id,
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
    ).order_by(ContractRepo.created_at.desc()).all()

    items = []
    for c in contracts:
        fn_count = db.query(sqlfunc.count(ContractFunction.id)).filter(
            ContractFunction.contract_id == c.id,
        ).scalar() or 0

        items.append({
            "id": c.id,
            "slug": c.slug,
            "name": c.name,
            "chain": c.chain,
            "language": c.language,
            "address": c.address,
            "description": c.description,
            "is_verified": c.is_verified,
            "function_count": fn_count,
            "created_at": c.created_at,
        })

    return {
        "namespace": repo.namespace,
        "bio": repo.bio,
        "total_public": len(items),
        "contracts": items,
    }


# ── Block Explorer ABI Fetch ─────────────────────────────────────

EXPLORER_API_URLS = {
    "ethereum": "https://api.etherscan.io/api",
    "sepolia": "https://api-sepolia.etherscan.io/api",
    "base": "https://api.basescan.org/api",
    "polygon": "https://api.polygonscan.com/api",
    "arbitrum": "https://api.arbiscan.io/api",
    "optimism": "https://api-optimistic.etherscan.io/api",
}


@router.get("/fetch-abi")
def fetch_abi_from_explorer(
    address: str = Query(..., min_length=42, max_length=42),
    chain: str = Query("ethereum"),
    db: Session = Depends(public_db_dependency),
):
    """
    Fetch a verified contract's ABI from a block explorer (Etherscan/Basescan/etc).
    Public endpoint — helps users import contracts without manual ABI copying.
    """
    import urllib.request
    import json as _json

    api_url = EXPLORER_API_URLS.get(chain)
    if not api_url:
        raise HTTPException(status_code=400, detail=f"Unsupported chain: {chain}. Supported: {list(EXPLORER_API_URLS.keys())}")

    try:
        url = f"{api_url}?module=contract&action=getabi&address={address}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read())

        if data.get("status") != "1":
            return {
                "success": False,
                "address": address,
                "chain": chain,
                "error": data.get("result", "ABI not available — contract may not be verified"),
            }

        abi = _json.loads(data["result"])
        # Extract contract name from first function or constructor
        contract_name = "Contract"
        for entry in abi:
            if entry.get("type") == "constructor":
                continue
            if entry.get("type") == "function":
                # Guess name from common patterns
                break

        return {
            "success": True,
            "address": address,
            "chain": chain,
            "abi": abi,
            "function_count": sum(1 for e in abi if e.get("type") == "function"),
            "event_count": sum(1 for e in abi if e.get("type") == "event"),
        }
    except Exception as e:
        return {"success": False, "address": address, "chain": chain, "error": str(e)}


# ── CAG Execute & Act (Authenticated) ────────────────────────────

@router.post("/cag/execute")
def cag_execute_endpoint(
    body: dict,
    db: Session = Depends(public_db_dependency),
):
    """
    CAG Mode 2: Execute a view/pure function on-chain. No gas, no approval needed.
    Body: { contract_address, chain, function_name, args? }
    """
    from api.services.contract_brain import cag_execute
    return cag_execute(
        db,
        contract_address=body.get("contract_address", ""),
        chain=body.get("chain", "ethereum"),
        function_name=body.get("function_name", ""),
        args=body.get("args", []),
    )


@router.post("/cag/act")
def cag_act_endpoint(
    body: dict,
    request=None,
    db: Session = Depends(public_db_dependency),
):
    """
    CAG Mode 3: Request a state-changing function call.
    Creates a PendingAction that requires master_admin approval.
    Body: { contract_address, chain, function_name, args? }
    """
    from fastapi import Request
    from api.auth.jwt import decode_access_token

    # Require auth for state-changing actions
    auth_header = ""
    if request and hasattr(request, 'headers'):
        auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required for state-changing calls")
    try:
        payload = decode_access_token(auth_header[7:])
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    from api.services.contract_brain import cag_act
    return cag_act(
        db,
        user_id=user_id,
        contract_address=body.get("contract_address", ""),
        chain=body.get("chain", "ethereum"),
        function_name=body.get("function_name", ""),
        args=body.get("args", []),
    )
