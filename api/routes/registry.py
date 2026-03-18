"""
REFINET Cloud — Registry Routes
GitHub-style registry for smart contract ABIs, SDKs, and execution logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import Optional

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_REGISTRY_READ, SCOPE_REGISTRY_WRITE
from api.models.public import User
from api.services import registry_service
from api.schemas.registry import (
    ProjectCreateRequest, ProjectUpdateRequest,
    ABICreateRequest, SDKCreateRequest, ExecutionLogicCreateRequest,
)

router = APIRouter(prefix="/registry", tags=["registry"])


# ── Auth Helpers ─────────────────────────────────────────────────────

def _get_current_user(request: Request, db: Session) -> tuple:
    """Extract (user_id, username) from JWT. Returns (None, None) if no auth."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None
    try:
        payload = decode_access_token(auth_header[7:])
        user_id = payload["sub"]
        user = db.query(User).filter(User.id == user_id).first()
        return user_id, user.username if user else None
    except Exception:
        return None, None


def _require_auth(request: Request, db: Session, scope: str = SCOPE_REGISTRY_READ) -> tuple:
    """Require authentication with scope check. Returns (user_id, username) or raises 401/403."""
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
    """Require write authentication."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_access_token(auth_header[7:])
        scopes = payload.get("scopes", [])
        if SCOPE_REGISTRY_WRITE not in scopes:
            raise HTTPException(status_code=403, detail="Requires registry:write scope")
        user_id = payload["sub"]
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user_id, user.username
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Project Routes ───────────────────────────────────────────────────

@router.post("/projects")
def create_project(
    req: ProjectCreateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, username = _require_write(request, db)
    try:
        project = registry_service.create_project(
            db,
            owner_id=user_id,
            owner_username=username,
            name=req.name,
            description=req.description,
            readme=req.readme,
            visibility=req.visibility,
            category=req.category,
            chain=req.chain,
            tags=req.tags,
            license=req.license,
            website_url=req.website_url,
            repo_url=req.repo_url,
        )
        return {
            "id": project.id,
            "slug": project.slug,
            "name": project.name,
            "message": "Project created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/projects")
def list_projects(
    request: Request,
    q: Optional[str] = Query(None, description="Search keyword"),
    category: Optional[str] = Query(None),
    chain: Optional[str] = Query(None),
    sort: str = Query("stars", description="Sort by: stars, recent, name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(public_db_dependency),
):
    return registry_service.search_projects(
        db,
        query=q,
        category=category,
        chain=chain,
        sort_by=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/projects/trending")
def trending_projects(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(public_db_dependency),
):
    return registry_service.get_trending_projects(db, limit=limit)


@router.get("/projects/{slug:path}")
def get_project(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _get_current_user(request, db)
    result = registry_service.get_project_by_slug(db, slug, requesting_user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.put("/projects/{slug:path}")
def update_project(
    slug: str,
    req: ProjectUpdateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    update_data = req.model_dump(exclude_none=True)
    try:
        project = registry_service.update_project(db, slug, user_id, **update_data)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or not owned by you")
        return {"slug": project.slug, "message": "Project updated"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/projects/{slug:path}")
def delete_project(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    if not registry_service.delete_project(db, slug, user_id):
        raise HTTPException(status_code=404, detail="Project not found or not owned by you")
    return {"message": "Project deleted"}


# ── ABI Routes ───────────────────────────────────────────────────────

@router.post("/projects/{slug:path}/abis")
def add_abi(
    slug: str,
    req: ABICreateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    project = registry_service.get_project_by_slug(db, slug, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    abi = registry_service.add_abi(
        db, project["id"], user_id,
        contract_name=req.contract_name,
        abi_json=req.abi_json,
        contract_address=req.contract_address,
        chain=req.chain,
        compiler_version=req.compiler_version,
        optimization_enabled=req.optimization_enabled,
        source_hash=req.source_hash,
        bytecode_hash=req.bytecode_hash,
    )
    if not abi:
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")
    return {"id": abi.id, "contract_name": abi.contract_name, "message": "ABI added"}


@router.get("/projects/{slug:path}/abis")
def list_abis(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _get_current_user(request, db)
    project = registry_service.get_project_by_slug(db, slug, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    abis = registry_service.list_abis(db, project["id"])
    return [
        {
            "id": a.id,
            "contract_name": a.contract_name,
            "contract_address": a.contract_address,
            "chain": a.chain,
            "compiler_version": a.compiler_version,
            "is_verified": a.is_verified,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in abis
    ]


@router.get("/abis/{abi_id}")
def get_abi_detail(
    abi_id: str,
    db: Session = Depends(public_db_dependency),
):
    abi = registry_service.get_abi(db, abi_id)
    if not abi:
        raise HTTPException(status_code=404, detail="ABI not found")
    return {
        "id": abi.id,
        "project_id": abi.project_id,
        "contract_name": abi.contract_name,
        "contract_address": abi.contract_address,
        "chain": abi.chain,
        "abi_json": abi.abi_json,
        "compiler_version": abi.compiler_version,
        "optimization_enabled": abi.optimization_enabled,
        "source_hash": abi.source_hash,
        "bytecode_hash": abi.bytecode_hash,
        "is_verified": abi.is_verified,
        "created_at": abi.created_at.isoformat() if abi.created_at else None,
    }


@router.delete("/abis/{abi_id}")
def delete_abi(
    abi_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    if not registry_service.delete_abi(db, abi_id, user_id):
        raise HTTPException(status_code=404, detail="ABI not found or not authorized")
    return {"message": "ABI deleted"}


# ── SDK Routes ───────────────────────────────────────────────────────

@router.post("/projects/{slug:path}/sdks")
def add_sdk(
    slug: str,
    req: SDKCreateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    project = registry_service.get_project_by_slug(db, slug, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    sdk = registry_service.add_sdk(
        db, project["id"], user_id,
        name=req.name,
        language=req.language,
        version=req.version,
        package_name=req.package_name,
        install_command=req.install_command,
        reference_url=req.reference_url,
        documentation=req.documentation,
        code_samples=req.code_samples,
        readme_content=req.readme_content,
    )
    if not sdk:
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")
    return {"id": sdk.id, "name": sdk.name, "message": "SDK added"}


@router.get("/projects/{slug:path}/sdks")
def list_sdks(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _get_current_user(request, db)
    project = registry_service.get_project_by_slug(db, slug, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    sdks = registry_service.list_sdks(db, project["id"])
    return [
        {
            "id": s.id,
            "name": s.name,
            "language": s.language,
            "version": s.version,
            "package_name": s.package_name,
            "install_command": s.install_command,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sdks
    ]


@router.get("/sdks/{sdk_id}")
def get_sdk_detail(
    sdk_id: str,
    db: Session = Depends(public_db_dependency),
):
    sdk = registry_service.get_sdk(db, sdk_id)
    if not sdk:
        raise HTTPException(status_code=404, detail="SDK not found")
    return {
        "id": sdk.id,
        "project_id": sdk.project_id,
        "name": sdk.name,
        "language": sdk.language,
        "version": sdk.version,
        "package_name": sdk.package_name,
        "install_command": sdk.install_command,
        "reference_url": sdk.reference_url,
        "documentation": sdk.documentation,
        "code_samples": sdk.code_samples,
        "readme_content": sdk.readme_content,
        "created_at": sdk.created_at.isoformat() if sdk.created_at else None,
    }


@router.delete("/sdks/{sdk_id}")
def delete_sdk(
    sdk_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    if not registry_service.delete_sdk(db, sdk_id, user_id):
        raise HTTPException(status_code=404, detail="SDK not found or not authorized")
    return {"message": "SDK deleted"}


# ── Execution Logic Routes ───────────────────────────────────────────

@router.post("/projects/{slug:path}/logic")
def add_logic(
    slug: str,
    req: ExecutionLogicCreateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    project = registry_service.get_project_by_slug(db, slug, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logic = registry_service.add_execution_logic(
        db, project["id"], user_id,
        name=req.name,
        logic_type=req.logic_type,
        description=req.description,
        function_signature=req.function_signature,
        input_schema=req.input_schema,
        output_schema=req.output_schema,
        code_reference=req.code_reference,
        chain=req.chain,
        gas_estimate=req.gas_estimate,
        is_read_only=req.is_read_only,
        preconditions=req.preconditions,
        abi_id=req.abi_id,
        version=req.version,
    )
    if not logic:
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")
    return {"id": logic.id, "name": logic.name, "message": "Execution logic added"}


@router.get("/projects/{slug:path}/logic")
def list_logic(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _get_current_user(request, db)
    project = registry_service.get_project_by_slug(db, slug, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    items = registry_service.list_execution_logic(db, project["id"])
    return [
        {
            "id": l.id,
            "name": l.name,
            "version": l.version,
            "logic_type": l.logic_type,
            "description": l.description,
            "function_signature": l.function_signature,
            "chain": l.chain,
            "gas_estimate": l.gas_estimate,
            "is_read_only": l.is_read_only,
            "is_verified": l.is_verified,
            "execution_count": l.execution_count,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in items
    ]


@router.get("/logic/{logic_id}")
def get_logic_detail(
    logic_id: str,
    db: Session = Depends(public_db_dependency),
):
    logic = registry_service.get_execution_logic(db, logic_id)
    if not logic:
        raise HTTPException(status_code=404, detail="Execution logic not found")
    return {
        "id": logic.id,
        "project_id": logic.project_id,
        "abi_id": logic.abi_id,
        "name": logic.name,
        "version": logic.version,
        "logic_type": logic.logic_type,
        "description": logic.description,
        "function_signature": logic.function_signature,
        "input_schema": logic.input_schema,
        "output_schema": logic.output_schema,
        "code_reference": logic.code_reference,
        "chain": logic.chain,
        "gas_estimate": logic.gas_estimate,
        "is_read_only": logic.is_read_only,
        "preconditions": logic.preconditions,
        "is_verified": logic.is_verified,
        "verified_by": logic.verified_by,
        "execution_count": logic.execution_count,
        "created_at": logic.created_at.isoformat() if logic.created_at else None,
    }


@router.delete("/logic/{logic_id}")
def delete_logic(
    logic_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_write(request, db)
    if not registry_service.delete_execution_logic(db, logic_id, user_id):
        raise HTTPException(status_code=404, detail="Logic not found or not authorized")
    return {"message": "Execution logic deleted"}


# ── Social Routes ────────────────────────────────────────────────────

@router.post("/projects/{slug:path}/star")
def toggle_star(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, _ = _require_auth(request, db)
    project_data = registry_service.get_project_by_slug(db, slug, user_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        is_starred = registry_service.toggle_star(db, user_id, project_data["id"])
        return {"starred": is_starred, "stars_count": project_data["stars_count"] + (1 if is_starred else -1)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projects/{slug:path}/fork")
def fork_project(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id, username = _require_write(request, db)
    forked = registry_service.fork_project(db, slug, user_id, username)
    if not forked:
        raise HTTPException(status_code=404, detail="Source project not found")
    return {"id": forked.id, "slug": forked.slug, "message": "Project forked successfully"}


@router.get("/projects/{slug:path}/stargazers")
def get_stargazers(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    from api.models.registry import RegistryStar, RegistryProject
    project = db.query(RegistryProject).filter(
        RegistryProject.slug == slug,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stars = db.query(RegistryStar).filter(
        RegistryStar.project_id == project.id,
    ).order_by(RegistryStar.created_at.desc()).limit(100).all()

    users = []
    for star in stars:
        user = db.query(User).filter(User.id == star.user_id).first()
        if user:
            users.append({"username": user.username, "starred_at": star.created_at.isoformat() if star.created_at else None})
    return users


# ── User Profile Routes ──────────────────────────────────────────────

@router.get("/users/{username}")
def get_user_profile(
    username: str,
    db: Session = Depends(public_db_dependency),
):
    profile = registry_service.get_user_registry_profile(db, username)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


@router.get("/users/{username}/projects")
def get_user_projects(
    username: str,
    db: Session = Depends(public_db_dependency),
):
    return registry_service.get_user_projects(db, username)


@router.get("/users/{username}/stars")
def get_user_starred(
    username: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(public_db_dependency),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return registry_service.get_user_stars(db, user.id, page=page, page_size=page_size)
