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
    """List supported chains with public contract counts."""
    results = db.query(
        ContractRepo.chain,
        sqlfunc.count(ContractRepo.id).label("count"),
    ).filter(
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
    ).group_by(ContractRepo.chain).all()

    return [{"chain": chain, "count": count} for chain, count in results]


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
