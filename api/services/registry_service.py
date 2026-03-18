"""
REFINET Cloud — Registry Service
Core business logic for the smart contract registry.
All protocol adapters (REST, GraphQL, gRPC, SOAP, WebSocket) call this service.
"""

import json
import re
import logging
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, desc, asc

from api.models.registry import (
    RegistryProject, RegistryABI, RegistrySDK,
    ExecutionLogic, RegistryStar, RegistryFork,
)
from api.models.public import User
from api.services.event_bus import EventBus

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _make_slug(username: str, project_name: str) -> str:
    """Create a GitHub-style slug: username/project-name."""
    return f"{username}/{_slugify(project_name)}"


def _project_to_dict(p: RegistryProject, owner_username: str = None) -> dict:
    """Convert a project model to a serializable dict."""
    return {
        "id": p.id,
        "slug": p.slug,
        "name": p.name,
        "description": p.description,
        "readme": p.readme,
        "owner_id": p.owner_id,
        "owner_username": owner_username,
        "visibility": p.visibility,
        "category": p.category,
        "chain": p.chain,
        "tags": json.loads(p.tags) if p.tags else [],
        "license": p.license,
        "website_url": p.website_url,
        "repo_url": p.repo_url,
        "logo_url": p.logo_url,
        "stars_count": p.stars_count,
        "forks_count": p.forks_count,
        "watchers_count": p.watchers_count,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── Project CRUD ─────────────────────────────────────────────────────

def create_project(
    db: Session,
    owner_id: str,
    owner_username: str,
    name: str,
    description: Optional[str] = None,
    readme: Optional[str] = None,
    visibility: str = "public",
    category: str = "utility",
    chain: str = "ethereum",
    tags: Optional[List[str]] = None,
    license: Optional[str] = None,
    website_url: Optional[str] = None,
    repo_url: Optional[str] = None,
) -> RegistryProject:
    """Create a new registry project."""
    slug = _make_slug(owner_username, name)

    # Check slug uniqueness
    existing = db.query(RegistryProject).filter(
        RegistryProject.slug == slug,
    ).first()
    if existing:
        raise ValueError(f"Project with slug '{slug}' already exists")

    project = RegistryProject(
        owner_id=owner_id,
        slug=slug,
        name=name,
        description=description,
        readme=readme,
        visibility=visibility,
        category=category,
        chain=chain,
        tags=json.dumps(tags) if tags else None,
        license=license,
        website_url=website_url,
        repo_url=repo_url,
    )
    db.add(project)
    db.flush()

    return project


def get_project_by_slug(
    db: Session,
    slug: str,
    requesting_user_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Get a project by slug. Returns None if not found or not accessible.
    Private projects only visible to owner. Platform projects visible to all.
    """
    project = db.query(RegistryProject).filter(
        RegistryProject.slug == slug,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()

    if not project:
        return None

    # Access control
    if project.visibility == "private" and project.owner_id != requesting_user_id:
        return None

    # Get owner username
    owner = db.query(User).filter(User.id == project.owner_id).first()
    owner_username = owner.username if owner else "unknown"

    result = _project_to_dict(project, owner_username)

    # Check if requesting user has starred
    if requesting_user_id:
        star = db.query(RegistryStar).filter(
            RegistryStar.user_id == requesting_user_id,
            RegistryStar.project_id == project.id,
        ).first()
        result["is_starred"] = star is not None
    else:
        result["is_starred"] = False

    # Counts
    result["abi_count"] = db.query(RegistryABI).filter(
        RegistryABI.project_id == project.id,
    ).count()
    result["sdk_count"] = db.query(RegistrySDK).filter(
        RegistrySDK.project_id == project.id,
    ).count()
    result["logic_count"] = db.query(ExecutionLogic).filter(
        ExecutionLogic.project_id == project.id,
    ).count()

    return result


def update_project(
    db: Session,
    slug: str,
    owner_id: str,
    **kwargs,
) -> Optional[RegistryProject]:
    """Update a project. Only the owner can update."""
    project = db.query(RegistryProject).filter(
        RegistryProject.slug == slug,
        RegistryProject.owner_id == owner_id,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()

    if not project:
        return None

    for key, value in kwargs.items():
        if value is not None and hasattr(project, key):
            if key == "tags":
                setattr(project, key, json.dumps(value))
            elif key == "name":
                # Regenerate slug if name changes, check uniqueness
                owner = db.query(User).filter(User.id == owner_id).first()
                if owner:
                    new_slug = _make_slug(owner.username, value)
                    existing = db.query(RegistryProject).filter(
                        RegistryProject.slug == new_slug,
                        RegistryProject.id != project.id,
                    ).first()
                    if existing:
                        raise ValueError(f"Project with slug '{new_slug}' already exists")
                    project.slug = new_slug
                setattr(project, key, value)
            else:
                setattr(project, key, value)

    project.updated_at = datetime.now(timezone.utc)
    db.flush()
    return project


def delete_project(db: Session, slug: str, owner_id: str) -> bool:
    """Soft-delete a project. Only the owner can delete."""
    project = db.query(RegistryProject).filter(
        RegistryProject.slug == slug,
        RegistryProject.owner_id == owner_id,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()

    if not project:
        return False

    project.is_active = False
    project.updated_at = datetime.now(timezone.utc)
    db.flush()
    return True


# ── Search & Discovery ───────────────────────────────────────────────

def search_projects(
    db: Session,
    query: Optional[str] = None,
    category: Optional[str] = None,
    chain: Optional[str] = None,
    visibility: str = "public",
    sort_by: str = "stars",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search projects with filters, pagination, and sorting."""
    q = db.query(RegistryProject).filter(
        RegistryProject.is_active == True,  # noqa: E712
    )

    # Visibility filter
    if visibility == "public":
        q = q.filter(RegistryProject.visibility.in_(["public", "platform"]))
    elif visibility == "platform":
        q = q.filter(RegistryProject.visibility == "platform")

    # Keyword search (escape SQL LIKE wildcards in user input)
    if query:
        safe_query = query.replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{safe_query}%"
        q = q.filter(
            (RegistryProject.name.ilike(search_term)) |
            (RegistryProject.description.ilike(search_term)) |
            (RegistryProject.tags.ilike(search_term))
        )

    # Category filter
    if category:
        q = q.filter(RegistryProject.category == category)

    # Chain filter
    if chain:
        q = q.filter(RegistryProject.chain == chain)

    # Total count before pagination
    total = q.count()

    # Sorting
    if sort_by == "stars":
        q = q.order_by(desc(RegistryProject.stars_count))
    elif sort_by == "recent":
        q = q.order_by(desc(RegistryProject.updated_at))
    elif sort_by == "name":
        q = q.order_by(asc(RegistryProject.name))
    else:
        q = q.order_by(desc(RegistryProject.stars_count))

    # Pagination
    offset = (page - 1) * page_size
    projects = q.offset(offset).limit(page_size).all()

    # Batch-fetch owner usernames (avoid N+1 queries)
    owner_ids = list({p.owner_id for p in projects})
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    items = [_project_to_dict(p, owners.get(p.owner_id, "unknown")) for p in projects]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (offset + page_size) < total,
    }


def get_trending_projects(db: Session, limit: int = 10) -> List[dict]:
    """Get projects sorted by stars (trending)."""
    projects = db.query(RegistryProject).filter(
        RegistryProject.is_active == True,  # noqa: E712
        RegistryProject.visibility.in_(["public", "platform"]),
    ).order_by(
        desc(RegistryProject.stars_count),
    ).limit(limit).all()

    owner_ids = list({p.owner_id for p in projects})
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
    return [_project_to_dict(p, owners.get(p.owner_id, "unknown")) for p in projects]


def get_user_projects(
    db: Session,
    username: str,
    include_private: bool = False,
) -> List[dict]:
    """Get all projects for a user."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return []

    q = db.query(RegistryProject).filter(
        RegistryProject.owner_id == user.id,
        RegistryProject.is_active == True,  # noqa: E712
    )

    if not include_private:
        q = q.filter(RegistryProject.visibility.in_(["public", "platform"]))

    projects = q.order_by(desc(RegistryProject.updated_at)).all()
    return [_project_to_dict(p, username) for p in projects]


# ── Social ───────────────────────────────────────────────────────────

def toggle_star(db: Session, user_id: str, project_id: str) -> bool:
    """Toggle star on a project. Returns True if starred, False if unstarred."""
    existing = db.query(RegistryStar).filter(
        RegistryStar.user_id == user_id,
        RegistryStar.project_id == project_id,
    ).first()

    project = db.query(RegistryProject).filter(
        RegistryProject.id == project_id,
    ).first()

    if not project:
        raise ValueError("Project not found")

    if existing:
        db.delete(existing)
        project.stars_count = max(0, project.stars_count - 1)
        db.flush()
        return False
    else:
        star = RegistryStar(user_id=user_id, project_id=project_id)
        db.add(star)
        project.stars_count += 1
        db.flush()
        return True


def get_user_stars(
    db: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Get projects starred by a user."""
    q = db.query(RegistryProject).join(
        RegistryStar, RegistryStar.project_id == RegistryProject.id,
    ).filter(
        RegistryStar.user_id == user_id,
        RegistryProject.is_active == True,  # noqa: E712
    )

    total = q.count()
    offset = (page - 1) * page_size
    projects = q.order_by(desc(RegistryStar.created_at)).offset(offset).limit(page_size).all()

    items = []
    for p in projects:
        owner = db.query(User).filter(User.id == p.owner_id).first()
        items.append(_project_to_dict(p, owner.username if owner else "unknown"))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (offset + page_size) < total,
    }


def fork_project(
    db: Session,
    source_slug: str,
    user_id: str,
    username: str,
) -> Optional[RegistryProject]:
    """Fork a project. Creates a copy owned by the forking user."""
    source = db.query(RegistryProject).filter(
        RegistryProject.slug == source_slug,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()

    if not source:
        return None

    # Create forked project (with collision-safe slug)
    new_slug = _make_slug(username, source.name)
    counter = 1
    while db.query(RegistryProject).filter(RegistryProject.slug == new_slug).first():
        new_slug = _make_slug(username, f"{source.name}-{counter}")
        counter += 1
        if counter > 100:
            raise ValueError("Too many forks with similar names")

    forked = RegistryProject(
        owner_id=user_id,
        slug=new_slug,
        name=source.name,
        description=source.description,
        readme=source.readme,
        visibility="public",
        category=source.category,
        chain=source.chain,
        tags=source.tags,
        license=source.license,
    )
    db.add(forked)
    db.flush()

    # Create fork record
    fork_record = RegistryFork(
        source_project_id=source.id,
        forked_project_id=forked.id,
        forked_by=user_id,
    )
    db.add(fork_record)

    # Increment fork count
    source.forks_count += 1

    # Copy ABIs
    abis = db.query(RegistryABI).filter(RegistryABI.project_id == source.id).all()
    for abi in abis:
        new_abi = RegistryABI(
            project_id=forked.id,
            contract_name=abi.contract_name,
            contract_address=abi.contract_address,
            chain=abi.chain,
            abi_json=abi.abi_json,
            compiler_version=abi.compiler_version,
            optimization_enabled=abi.optimization_enabled,
            source_hash=abi.source_hash,
        )
        db.add(new_abi)

    # Copy SDKs
    sdks = db.query(RegistrySDK).filter(RegistrySDK.project_id == source.id).all()
    for sdk in sdks:
        new_sdk = RegistrySDK(
            project_id=forked.id,
            name=sdk.name,
            language=sdk.language,
            version=sdk.version,
            package_name=sdk.package_name,
            install_command=sdk.install_command,
            documentation=sdk.documentation,
            code_samples=sdk.code_samples,
            readme_content=sdk.readme_content,
        )
        db.add(new_sdk)

    # Copy execution logic
    logic_items = db.query(ExecutionLogic).filter(ExecutionLogic.project_id == source.id).all()
    for logic in logic_items:
        new_logic = ExecutionLogic(
            project_id=forked.id,
            name=logic.name,
            version=logic.version,
            logic_type=logic.logic_type,
            description=logic.description,
            function_signature=logic.function_signature,
            input_schema=logic.input_schema,
            output_schema=logic.output_schema,
            code_reference=logic.code_reference,
            chain=logic.chain,
            gas_estimate=logic.gas_estimate,
            is_read_only=logic.is_read_only,
            preconditions=logic.preconditions,
        )
        db.add(new_logic)

    db.flush()
    return forked


# ── ABI CRUD ─────────────────────────────────────────────────────────

def add_abi(
    db: Session,
    project_id: str,
    owner_id: str,
    **kwargs,
) -> Optional[RegistryABI]:
    """Add an ABI to a project. Owner only."""
    project = db.query(RegistryProject).filter(
        RegistryProject.id == project_id,
        RegistryProject.owner_id == owner_id,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()

    if not project:
        return None

    abi = RegistryABI(project_id=project_id, **kwargs)
    db.add(abi)
    project.updated_at = datetime.now(timezone.utc)
    db.flush()
    return abi


def list_abis(db: Session, project_id: str) -> List[RegistryABI]:
    """List all ABIs for a project."""
    return db.query(RegistryABI).filter(
        RegistryABI.project_id == project_id,
    ).order_by(desc(RegistryABI.created_at)).all()


def get_abi(db: Session, abi_id: str) -> Optional[RegistryABI]:
    """Get a single ABI by ID."""
    return db.query(RegistryABI).filter(RegistryABI.id == abi_id).first()


def delete_abi(db: Session, abi_id: str, owner_id: str) -> bool:
    """Delete an ABI. Owner only."""
    abi = db.query(RegistryABI).filter(RegistryABI.id == abi_id).first()
    if not abi:
        return False

    project = db.query(RegistryProject).filter(
        RegistryProject.id == abi.project_id,
        RegistryProject.owner_id == owner_id,
    ).first()
    if not project:
        return False

    db.delete(abi)
    db.flush()
    return True


# ── SDK CRUD ─────────────────────────────────────────────────────────

def add_sdk(
    db: Session,
    project_id: str,
    owner_id: str,
    **kwargs,
) -> Optional[RegistrySDK]:
    """Add an SDK to a project. Owner only."""
    project = db.query(RegistryProject).filter(
        RegistryProject.id == project_id,
        RegistryProject.owner_id == owner_id,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()

    if not project:
        return None

    sdk = RegistrySDK(project_id=project_id, **kwargs)
    db.add(sdk)
    project.updated_at = datetime.now(timezone.utc)
    db.flush()
    return sdk


def list_sdks(db: Session, project_id: str) -> List[RegistrySDK]:
    """List all SDKs for a project."""
    return db.query(RegistrySDK).filter(
        RegistrySDK.project_id == project_id,
    ).order_by(desc(RegistrySDK.created_at)).all()


def get_sdk(db: Session, sdk_id: str) -> Optional[RegistrySDK]:
    """Get a single SDK by ID."""
    return db.query(RegistrySDK).filter(RegistrySDK.id == sdk_id).first()


def delete_sdk(db: Session, sdk_id: str, owner_id: str) -> bool:
    """Delete an SDK. Owner only."""
    sdk = db.query(RegistrySDK).filter(RegistrySDK.id == sdk_id).first()
    if not sdk:
        return False

    project = db.query(RegistryProject).filter(
        RegistryProject.id == sdk.project_id,
        RegistryProject.owner_id == owner_id,
    ).first()
    if not project:
        return False

    db.delete(sdk)
    db.flush()
    return True


# ── Execution Logic CRUD ─────────────────────────────────────────────

def add_execution_logic(
    db: Session,
    project_id: str,
    owner_id: str,
    **kwargs,
) -> Optional[ExecutionLogic]:
    """Add execution logic to a project. Owner only."""
    project = db.query(RegistryProject).filter(
        RegistryProject.id == project_id,
        RegistryProject.owner_id == owner_id,
        RegistryProject.is_active == True,  # noqa: E712
    ).first()

    if not project:
        return None

    logic = ExecutionLogic(project_id=project_id, **kwargs)
    db.add(logic)
    project.updated_at = datetime.now(timezone.utc)
    db.flush()
    return logic


def list_execution_logic(db: Session, project_id: str) -> List[ExecutionLogic]:
    """List all execution logic for a project."""
    return db.query(ExecutionLogic).filter(
        ExecutionLogic.project_id == project_id,
    ).order_by(desc(ExecutionLogic.created_at)).all()


def get_execution_logic(db: Session, logic_id: str) -> Optional[ExecutionLogic]:
    """Get a single execution logic by ID."""
    return db.query(ExecutionLogic).filter(ExecutionLogic.id == logic_id).first()


def delete_execution_logic(db: Session, logic_id: str, owner_id: str) -> bool:
    """Delete execution logic. Owner only."""
    logic = db.query(ExecutionLogic).filter(ExecutionLogic.id == logic_id).first()
    if not logic:
        return False

    project = db.query(RegistryProject).filter(
        RegistryProject.id == logic.project_id,
        RegistryProject.owner_id == owner_id,
    ).first()
    if not project:
        return False

    db.delete(logic)
    db.flush()
    return True


# ── User Profile ─────────────────────────────────────────────────────

def get_user_registry_profile(db: Session, username: str) -> Optional[dict]:
    """Get a user's registry profile with project stats."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    project_count = db.query(RegistryProject).filter(
        RegistryProject.owner_id == user.id,
        RegistryProject.is_active == True,  # noqa: E712
        RegistryProject.visibility.in_(["public", "platform"]),
    ).count()

    stars_given = db.query(RegistryStar).filter(
        RegistryStar.user_id == user.id,
    ).count()

    # Total stars received across all projects
    total_stars = db.query(sql_func.sum(RegistryProject.stars_count)).filter(
        RegistryProject.owner_id == user.id,
        RegistryProject.is_active == True,  # noqa: E712
    ).scalar() or 0

    # Pinned projects (top 6 by stars)
    pinned = db.query(RegistryProject).filter(
        RegistryProject.owner_id == user.id,
        RegistryProject.is_active == True,  # noqa: E712
        RegistryProject.visibility.in_(["public", "platform"]),
    ).order_by(desc(RegistryProject.stars_count)).limit(6).all()

    return {
        "username": user.username,
        "eth_address": user.eth_address,
        "tier": user.tier,
        "project_count": project_count,
        "stars_given": stars_given,
        "total_stars_received": total_stars,
        "joined_at": user.created_at.isoformat() if user.created_at else None,
        "pinned_projects": [_project_to_dict(p, username) for p in pinned],
    }
