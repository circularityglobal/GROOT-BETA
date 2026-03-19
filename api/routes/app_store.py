"""
REFINET Cloud — App Store Routes
Browse, publish, install, and review apps.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.app_store import (
    publish_app, search_apps, get_app_by_slug,
    install_app, uninstall_app, review_app,
    get_featured, get_user_installs,
)

router = APIRouter(prefix="/apps", tags=["app-store"])


def _get_user_id(request: Request, db: Session) -> str:
    """Extract user_id from JWT or API key."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    if token.startswith("rf_"):
        api_key = validate_api_key(db, token)
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key.user_id
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


def _optional_user_id(request: Request, db: Session):
    """Extract user_id if authenticated, None if anonymous."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return _get_user_id(request, db)
    except HTTPException:
        return None


# ── Browse / Search (public, no auth required) ───────────────────

@router.get("")
def browse_apps(
    request: Request,
    query: str = None,
    category: str = None,
    chain: str = None,
    sort_by: str = "installs",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(public_db_dependency),
):
    """Browse and search published apps."""
    if page_size > 50:
        page_size = 50

    return search_apps(
        db,
        query=query,
        category=category,
        chain=chain,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.get("/featured")
def featured_apps(
    limit: int = 12,
    db: Session = Depends(public_db_dependency),
):
    """Get featured and trending apps."""
    if limit > 50:
        limit = 50
    return get_featured(db, limit=limit)


@router.get("/installed")
def my_installed_apps(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get apps installed by the authenticated user."""
    user_id = _get_user_id(request, db)
    return get_user_installs(db, user_id)


@router.get("/{slug:path}")
def get_app_detail(
    slug: str,
    db: Session = Depends(public_db_dependency),
):
    """Get full app details including readme and reviews."""
    result = get_app_by_slug(db, slug)
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


# ── Publish (auth required) ──────────────────────────────────────

@router.post("")
def publish_app_route(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Publish a new app or update an existing one."""
    user_id = _get_user_id(request, db)

    name = body.get("name")
    description = body.get("description", "")
    category = body.get("category")

    if not name or not category:
        raise HTTPException(status_code=400, detail="'name' and 'category' are required")

    result = publish_app(
        db,
        owner_id=user_id,
        name=name,
        description=description,
        category=category,
        chain=body.get("chain"),
        version=body.get("version", "1.0.0"),
        readme=body.get("readme"),
        icon_url=body.get("icon_url"),
        screenshots=body.get("screenshots"),
        tags=body.get("tags"),
        registry_project_id=body.get("registry_project_id"),
        dapp_build_id=body.get("dapp_build_id"),
        agent_id=body.get("agent_id"),
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ── Install / Uninstall (auth required) ──────────────────────────

@router.post("/{slug:path}/install")
def install_app_route(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Install an app."""
    user_id = _get_user_id(request, db)

    from api.models.public import AppListing
    app = db.query(AppListing).filter_by(slug=slug, is_active=True).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    result = install_app(db, app.id, user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{slug:path}/uninstall")
def uninstall_app_route(
    slug: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Uninstall an app."""
    user_id = _get_user_id(request, db)

    from api.models.public import AppListing
    app = db.query(AppListing).filter_by(slug=slug, is_active=True).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    result = uninstall_app(db, app.id, user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Review (auth required) ───────────────────────────────────────

@router.post("/{slug:path}/review")
def review_app_route(
    slug: str,
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Submit or update a review for an app."""
    user_id = _get_user_id(request, db)

    rating = body.get("rating")
    if rating is None:
        raise HTTPException(status_code=400, detail="'rating' is required (1-5)")

    from api.models.public import AppListing
    app = db.query(AppListing).filter_by(slug=slug, is_active=True).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    result = review_app(
        db,
        app_id=app.id,
        user_id=user_id,
        rating=int(rating),
        comment=body.get("comment"),
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
