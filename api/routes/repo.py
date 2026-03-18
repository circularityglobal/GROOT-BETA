"""
REFINET Cloud — Contract Repository Routes
User-managed smart contract namespace with ABI parsing, SDK generation,
and visibility controls.

Cardinal rule: source_code is NEVER returned in any API response.
GROOT only sees SDK definitions where is_public=True.
"""

import json
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import (
    decode_access_token, verify_scope,
    SCOPE_REGISTRY_READ, SCOPE_REGISTRY_WRITE,
)
from api.models.public import User
from api.models.brain import (
    UserRepository, ContractRepo, ContractFunction,
    ContractEvent, SDKDefinition,
)
from api.schemas.brain import (
    RepoInitRequest, ContractUploadRequest, ContractUpdateRequest,
    VisibilityToggleRequest, FunctionToggleRequest,
    UserRepoResponse, ContractSummary, ContractDetail,
    ParsedFunctionResponse, ParsedEventResponse, SDKResponse,
    PaginatedContracts,
)
from api.services import abi_parser, sdk_generator
from api.services.crypto_utils import sha256_hex

router = APIRouter(prefix="/repo", tags=["repo"])


# ── Auth Helpers ────────────────────────────────────────────────────

def _require_auth(request: Request, db: Session, scope: str = SCOPE_REGISTRY_READ) -> tuple:
    """Require JWT auth with scope. Returns (user_id, username)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_access_token(auth_header[7:])
        if not verify_scope(payload, scope):
            raise HTTPException(status_code=403, detail=f"Requires {scope} scope")
        user_id = payload["sub"]
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user_id, user.username
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _require_write(request: Request, db: Session) -> tuple:
    """Require write-level auth."""
    return _require_auth(request, db, SCOPE_REGISTRY_WRITE)


def _slugify(name: str) -> str:
    """Convert a name to URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def _get_contract_as_owner(
    db: Session, slug: str, user_id: str
) -> ContractRepo:
    """Get a contract and verify ownership."""
    contract = db.query(ContractRepo).filter(
        ContractRepo.slug == slug,
        ContractRepo.is_active == True,  # noqa: E712
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not the contract owner")
    return contract


# ── Repository Namespace ───────────────────────────────────────────

@router.post("/init")
def init_repo(
    body: RepoInitRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Initialize user's contract repository namespace."""
    user_id, username = _require_write(request, db)

    # Check if already initialized
    existing = db.query(UserRepository).filter(
        UserRepository.user_id == user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Repository already initialized")

    repo = UserRepository(
        id=str(uuid.uuid4()),
        user_id=user_id,
        namespace=username,
        bio=body.bio,
        website=body.website,
    )
    db.add(repo)
    db.flush()

    return {
        "id": repo.id,
        "namespace": repo.namespace,
        "message": f"Repository @{username} initialized",
    }


@router.get("/me")
def get_own_repo(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get own repository details."""
    user_id, _ = _require_auth(request, db)

    repo = db.query(UserRepository).filter(
        UserRepository.user_id == user_id,
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not initialized. Call POST /repo/init first.")

    return UserRepoResponse.model_validate(repo).model_dump()


@router.get("/@{username}")
def get_public_repo(
    username: str,
    db: Session = Depends(public_db_dependency),
):
    """Get public profile of a user's repository."""
    repo = db.query(UserRepository).filter(
        UserRepository.namespace == username,
        UserRepository.is_active == True,  # noqa: E712
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="User repository not found")

    return {
        "namespace": repo.namespace,
        "bio": repo.bio,
        "website": repo.website,
        "total_public": repo.total_public,
        "created_at": repo.created_at,
    }


# ── Contract Management ────────────────────────────────────────────

@router.post("/contracts")
def upload_contract(
    body: ContractUploadRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Upload a smart contract to user's repository."""
    user_id, username = _require_write(request, db)

    # Verify repo exists
    repo = db.query(UserRepository).filter(
        UserRepository.user_id == user_id,
    ).first()
    if not repo:
        raise HTTPException(status_code=400, detail="Repository not initialized. Call POST /repo/init first.")

    # Build slug
    contract_slug = _slugify(body.name)
    full_slug = f"{username}/{contract_slug}"

    # Check uniqueness
    existing = db.query(ContractRepo).filter(
        ContractRepo.slug == full_slug,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Contract '{full_slug}' already exists")

    # Compute hashes
    abi_hash = sha256_hex(body.abi_json)
    source_hash = sha256_hex(body.source_code) if body.source_code else None

    contract = ContractRepo(
        id=str(uuid.uuid4()),
        repo_id=repo.id,
        user_id=user_id,
        name=body.name,
        slug=full_slug,
        chain=body.chain,
        language=body.language,
        address=body.address,
        version=body.version or "1.0.0",
        description=body.description,
        tags=json.dumps(body.tags) if body.tags else None,
        source_code=body.source_code,  # PRIVATE — never exposed
        source_hash=source_hash,
        abi_json=body.abi_json,
        abi_hash=abi_hash,
        status="draft",
    )
    db.add(contract)

    # Update repo counts
    repo.total_contracts = (repo.total_contracts or 0) + 1
    db.flush()

    return {
        "id": contract.id,
        "slug": contract.slug,
        "message": f"Contract '{body.name}' uploaded to @{username}",
    }


@router.get("/contracts")
def list_contracts(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    chain: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(public_db_dependency),
):
    """List own contracts."""
    user_id, _ = _require_auth(request, db)

    q = db.query(ContractRepo).filter(
        ContractRepo.user_id == user_id,
        ContractRepo.is_active == True,  # noqa: E712
    )
    if chain:
        q = q.filter(ContractRepo.chain == chain)
    if status:
        q = q.filter(ContractRepo.status == status)

    total = q.count()
    contracts = q.order_by(ContractRepo.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = [ContractSummary.model_validate(c).model_dump() for c in contracts]

    return PaginatedContracts(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size < total),
    ).model_dump()


@router.get("/contracts/{slug:path}/detail")
def get_contract(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get contract details (ABI visible, source code NEVER returned)."""
    user_id, _ = _require_auth(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    return ContractDetail.model_validate(contract).model_dump()


@router.put("/contracts/{slug:path}")
def update_contract(
    slug: str,
    body: ContractUpdateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Update contract metadata."""
    user_id, _ = _require_write(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    if body.name is not None:
        contract.name = body.name
    if body.description is not None:
        contract.description = body.description
    if body.address is not None:
        contract.address = body.address
    if body.version is not None:
        contract.version = body.version
    if body.tags is not None:
        contract.tags = json.dumps(body.tags)
    if body.abi_json is not None:
        contract.abi_json = body.abi_json
        contract.abi_hash = sha256_hex(body.abi_json)
        contract.status = "draft"  # needs re-parsing
    if body.source_code is not None:
        contract.source_code = body.source_code
        contract.source_hash = sha256_hex(body.source_code)

    db.flush()
    return {"message": "Contract updated", "slug": contract.slug}


@router.delete("/contracts/{slug:path}")
def archive_contract(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Archive (soft-delete) a contract."""
    user_id, _ = _require_write(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    was_public = contract.is_public

    contract.is_active = False
    contract.status = "archived"
    contract.is_public = False

    # Update SDK visibility
    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract.id,
    ).first()
    if sdk:
        sdk.is_public = False

    # Update repo counts
    repo = db.query(UserRepository).filter(
        UserRepository.id == contract.repo_id,
    ).first()
    if repo:
        repo.total_contracts = max(0, (repo.total_contracts or 1) - 1)
        if was_public:
            repo.total_public = max(0, (repo.total_public or 1) - 1)

    db.flush()
    return {"message": "Contract archived", "slug": contract.slug}


# ── ABI Parsing & SDK Generation ──────────────────────────────────

@router.post("/contracts/{slug:path}/parse")
def parse_contract(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Trigger ABI parsing + access control analysis + SDK generation."""
    user_id, username = _require_write(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    if not contract.abi_json:
        raise HTTPException(status_code=400, detail="No ABI JSON uploaded")

    # Parse ABI
    parsed = abi_parser.parse_abi(contract.abi_json, contract.source_code)

    if parsed.errors:
        contract.parse_errors = json.dumps(parsed.errors)
        contract.status = "draft"
        db.flush()
        raise HTTPException(status_code=422, detail={
            "message": "ABI parsing failed",
            "errors": parsed.errors,
        })

    # Clear existing parsed data
    db.query(ContractFunction).filter(
        ContractFunction.contract_id == contract.id,
    ).delete()
    db.query(ContractEvent).filter(
        ContractEvent.contract_id == contract.id,
    ).delete()

    # Insert parsed functions
    for fn in parsed.functions:
        db_fn = ContractFunction(
            id=str(uuid.uuid4()),
            contract_id=contract.id,
            function_name=fn.name,
            function_type=fn.function_type,
            selector=fn.selector,
            signature=fn.signature,
            visibility=fn.visibility,
            state_mutability=fn.state_mutability,
            access_level=fn.access_level,
            access_modifier=fn.access_modifier,
            access_roles=json.dumps(fn.access_roles) if fn.access_roles else None,
            inputs=json.dumps(fn.inputs),
            outputs=json.dumps(fn.outputs),
            is_dangerous=fn.is_dangerous,
            danger_reason=fn.danger_reason,
            natspec_notice=fn.natspec_notice,
            natspec_dev=fn.natspec_dev,
        )
        db.add(db_fn)

    # Insert parsed events
    for evt in parsed.events:
        db_evt = ContractEvent(
            id=str(uuid.uuid4()),
            contract_id=contract.id,
            event_name=evt.name,
            signature=evt.signature,
            topic_hash=evt.topic_hash,
            inputs=json.dumps(evt.inputs),
        )
        db.add(db_evt)

    # Generate SDK
    tags = json.loads(contract.tags) if contract.tags else None
    sdk_dict = sdk_generator.generate_sdk(
        contract_name=contract.name,
        chain=contract.chain,
        contract_address=contract.address,
        owner_namespace=username,
        language=contract.language,
        version=contract.version or "1.0.0",
        description=contract.description,
        tags=tags,
        parsed=parsed,
        sdk_version="1.0.0",
    )
    sdk_json_str = sdk_generator.sdk_to_json(sdk_dict)
    sdk_hash = sdk_generator.compute_sdk_hash(sdk_json_str)

    # Upsert SDK definition
    existing_sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract.id,
    ).first()

    if existing_sdk:
        existing_sdk.sdk_json = sdk_json_str
        existing_sdk.sdk_hash = sdk_hash
        existing_sdk.sdk_version = "1.0.0"
        existing_sdk.chain = contract.chain
        existing_sdk.contract_address = contract.address
        existing_sdk.is_public = contract.is_public
    else:
        new_sdk = SDKDefinition(
            id=str(uuid.uuid4()),
            contract_id=contract.id,
            user_id=user_id,
            sdk_version="1.0.0",
            sdk_json=sdk_json_str,
            sdk_hash=sdk_hash,
            is_public=contract.is_public,
            chain=contract.chain,
            contract_address=contract.address,
        )
        db.add(new_sdk)

    # Update contract status
    contract.status = "parsed"
    contract.parse_errors = None
    db.flush()

    return {
        "message": "ABI parsed and SDK generated",
        "function_count": len(parsed.functions),
        "event_count": len(parsed.events),
        "dangerous_count": parsed.security.dangerous_count,
        "security_summary": {
            "public": parsed.security.public_functions,
            "owner": parsed.security.owner_functions,
            "admin": parsed.security.admin_functions,
            "role_based": parsed.security.role_based_functions,
            "unknown": parsed.security.unknown_functions,
            "access_pattern": parsed.security.access_control_pattern,
        },
    }


@router.get("/contracts/{slug:path}/functions")
def list_functions(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List parsed functions for a contract."""
    user_id, _ = _require_auth(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    functions = db.query(ContractFunction).filter(
        ContractFunction.contract_id == contract.id,
    ).all()

    return [ParsedFunctionResponse.model_validate(f).model_dump() for f in functions]


@router.get("/contracts/{slug:path}/events")
def list_events(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List parsed events for a contract."""
    user_id, _ = _require_auth(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    events = db.query(ContractEvent).filter(
        ContractEvent.contract_id == contract.id,
    ).all()

    return [ParsedEventResponse.model_validate(e).model_dump() for e in events]


@router.get("/contracts/{slug:path}/sdk")
def get_sdk(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get the generated SDK definition for a contract."""
    user_id, _ = _require_auth(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract.id,
    ).first()
    if not sdk:
        raise HTTPException(status_code=404, detail="SDK not generated. Call POST /repo/contracts/{slug}/parse first.")

    return SDKResponse.model_validate(sdk).model_dump()


# ── Visibility Toggle ──────────────────────────────────────────────

@router.put("/contracts/{slug:path}/visibility")
def toggle_visibility(
    slug: str,
    body: VisibilityToggleRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Toggle contract visibility (public/private). Public SDKs are visible to GROOT."""
    user_id, _ = _require_write(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    if body.is_public and contract.status not in ("parsed", "published"):
        raise HTTPException(
            status_code=400,
            detail="Contract must be parsed before publishing. Call POST /repo/contracts/{slug}/parse first.",
        )

    old_public = contract.is_public
    contract.is_public = body.is_public

    if body.is_public:
        contract.status = "published"
    elif contract.status == "published":
        contract.status = "parsed"

    # Update SDK visibility
    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract.id,
    ).first()
    if sdk:
        sdk.is_public = body.is_public

    # Update repo counts
    repo = db.query(UserRepository).filter(
        UserRepository.id == contract.repo_id,
    ).first()
    if repo:
        if body.is_public and not old_public:
            repo.total_public = (repo.total_public or 0) + 1
        elif not body.is_public and old_public:
            repo.total_public = max(0, (repo.total_public or 1) - 1)

    db.flush()

    action = "published" if body.is_public else "unpublished"
    return {
        "message": f"Contract {action}",
        "slug": contract.slug,
        "is_public": contract.is_public,
    }


# ── Function Toggle ────────────────────────────────────────────────

@router.put("/contracts/{slug:path}/functions/{function_id}/toggle")
def toggle_function(
    slug: str,
    function_id: str,
    body: FunctionToggleRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Enable/disable a function in the SDK output."""
    user_id, username = _require_write(request, db)
    contract = _get_contract_as_owner(db, slug, user_id)

    fn = db.query(ContractFunction).filter(
        ContractFunction.id == function_id,
        ContractFunction.contract_id == contract.id,
    ).first()
    if not fn:
        raise HTTPException(status_code=404, detail="Function not found")

    fn.is_sdk_enabled = body.is_sdk_enabled
    db.flush()

    # Regenerate SDK with updated enabled set
    _regenerate_sdk(db, contract, username)

    action = "enabled" if body.is_sdk_enabled else "disabled"
    return {
        "message": f"Function '{fn.function_name}' {action} in SDK",
        "function_id": fn.id,
        "is_sdk_enabled": fn.is_sdk_enabled,
    }


def _regenerate_sdk(db: Session, contract: ContractRepo, username: str):
    """Regenerate the SDK JSON after function toggle changes."""
    # Get enabled function names
    enabled_functions = db.query(ContractFunction).filter(
        ContractFunction.contract_id == contract.id,
        ContractFunction.is_sdk_enabled == True,  # noqa: E712
    ).all()

    enabled_names = {f.function_name for f in enabled_functions}

    # Re-parse to get fresh ParsedABI
    parsed = abi_parser.parse_abi(contract.abi_json, contract.source_code)

    tags = json.loads(contract.tags) if contract.tags else None
    sdk_dict = sdk_generator.generate_sdk(
        contract_name=contract.name,
        chain=contract.chain,
        contract_address=contract.address,
        owner_namespace=username,
        language=contract.language,
        version=contract.version or "1.0.0",
        description=contract.description,
        tags=tags,
        parsed=parsed,
        enabled_function_ids=enabled_names,
        sdk_version="1.0.0",
    )
    sdk_json_str = sdk_generator.sdk_to_json(sdk_dict)
    sdk_hash = sdk_generator.compute_sdk_hash(sdk_json_str)

    sdk = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract.id,
    ).first()
    if sdk:
        sdk.sdk_json = sdk_json_str
        sdk.sdk_hash = sdk_hash
    db.flush()
