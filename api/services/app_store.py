"""
REFINET Cloud — App Store Service
Core business logic for the App Store: publish, search, install, review, featured.
"""

import json
import re
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, or_, desc

from api.models.public import AppListing, AppReview, AppInstall, User
from api.services.event_bus import EventBus

logger = logging.getLogger("refinet.app_store")


# ── Helpers ──────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _listing_to_dict(app: AppListing, owner_username: Optional[str] = None) -> dict:
    """Serialize an AppListing to a dict."""
    return {
        "id": app.id,
        "slug": app.slug,
        "name": app.name,
        "description": app.description,
        "category": app.category,
        "chain": app.chain,
        "version": app.version,
        "icon_url": app.icon_url,
        "screenshots": json.loads(app.screenshots) if app.screenshots else [],
        "tags": json.loads(app.tags) if app.tags else [],
        "owner_id": app.owner_id,
        "owner_username": owner_username,
        "install_count": app.install_count,
        "rating_avg": round(app.rating_avg, 2) if app.rating_avg else 0.0,
        "rating_count": app.rating_count,
        "is_published": app.is_published,
        "is_verified": app.is_verified,
        "is_featured": app.is_featured,
        "registry_project_id": app.registry_project_id,
        "dapp_build_id": app.dapp_build_id,
        "agent_id": app.agent_id,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }


# ── Publish ──────────────────────────────────────────────────────

def publish_app(
    db: Session,
    owner_id: str,
    name: str,
    description: str,
    category: str,
    chain: Optional[str] = None,
    version: str = "1.0.0",
    readme: Optional[str] = None,
    icon_url: Optional[str] = None,
    screenshots: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    registry_project_id: Optional[str] = None,
    dapp_build_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> dict:
    """Create or update an app listing."""
    if category not in ("dapp", "agent", "tool", "template"):
        return {"error": "category must be: dapp, agent, tool, or template"}

    # Get owner username for slug
    owner = db.query(User).filter(User.id == owner_id).first()
    if not owner:
        return {"error": "Owner user not found"}

    slug = f"{owner.username}/{_slugify(name)}"

    # Check for existing listing with same slug
    existing = db.query(AppListing).filter(AppListing.slug == slug).first()

    if existing:
        if existing.owner_id != owner_id:
            return {"error": f"Slug '{slug}' is already taken by another user"}

        # Update existing
        existing.name = name
        existing.description = description
        existing.category = category
        existing.chain = chain
        existing.version = version
        existing.readme = readme
        existing.icon_url = icon_url
        existing.screenshots = json.dumps(screenshots) if screenshots else existing.screenshots
        existing.tags = json.dumps(tags) if tags else existing.tags
        existing.registry_project_id = registry_project_id or existing.registry_project_id
        existing.dapp_build_id = dapp_build_id or existing.dapp_build_id
        existing.agent_id = agent_id or existing.agent_id
        existing.is_published = True
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()

        return _listing_to_dict(existing, owner.username)

    # Create new
    app = AppListing(
        owner_id=owner_id,
        name=name,
        slug=slug,
        description=description,
        readme=readme,
        category=category,
        chain=chain,
        version=version,
        icon_url=icon_url,
        screenshots=json.dumps(screenshots) if screenshots else None,
        tags=json.dumps(tags) if tags else None,
        registry_project_id=registry_project_id,
        dapp_build_id=dapp_build_id,
        agent_id=agent_id,
        is_published=True,
    )
    db.add(app)
    db.flush()

    return _listing_to_dict(app, owner.username)


# ── Search ───────────────────────────────────────────────────────

def search_apps(
    db: Session,
    query: Optional[str] = None,
    category: Optional[str] = None,
    chain: Optional[str] = None,
    sort_by: str = "installs",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search published apps with filters and sorting."""
    q = db.query(AppListing).filter(
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    )

    if query:
        keywords = re.findall(r'\w+', query.lower())
        if keywords:
            conditions = []
            for kw in keywords[:5]:
                conditions.append(AppListing.name.ilike(f"%{kw}%"))
                conditions.append(AppListing.description.ilike(f"%{kw}%"))
                conditions.append(AppListing.tags.ilike(f"%{kw}%"))
            q = q.filter(or_(*conditions))

    if category:
        q = q.filter(AppListing.category == category)
    if chain:
        q = q.filter(AppListing.chain == chain)

    # Sorting
    if sort_by == "rating":
        q = q.order_by(desc(AppListing.rating_avg), desc(AppListing.rating_count))
    elif sort_by == "recent":
        q = q.order_by(desc(AppListing.created_at))
    elif sort_by == "name":
        q = q.order_by(AppListing.name)
    else:  # "installs" (default)
        q = q.order_by(desc(AppListing.install_count))

    total = q.count()
    offset = (page - 1) * page_size
    apps = q.offset(offset).limit(page_size).all()

    # Batch-fetch owner usernames
    owner_ids = list({a.owner_id for a in apps})
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    return {
        "apps": [_listing_to_dict(a, owners.get(a.owner_id)) for a in apps],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ── Get Detail ───────────────────────────────────────────────────

def get_app_by_slug(db: Session, slug: str) -> Optional[dict]:
    """Get a single app listing by slug, including readme and reviews."""
    app = db.query(AppListing).filter(
        AppListing.slug == slug,
        AppListing.is_active == True,  # noqa: E712
    ).first()

    if not app:
        return None

    owner = db.query(User).filter(User.id == app.owner_id).first()
    result = _listing_to_dict(app, owner.username if owner else None)
    result["readme"] = app.readme

    # Include recent reviews
    reviews = db.query(AppReview).filter(
        AppReview.app_id == app.id,
    ).order_by(desc(AppReview.created_at)).limit(10).all()

    review_user_ids = list({r.user_id for r in reviews})
    review_users = {
        u.id: u.username
        for u in db.query(User).filter(User.id.in_(review_user_ids)).all()
    } if review_user_ids else {}

    result["reviews"] = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "username": review_users.get(r.user_id),
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reviews
    ]

    return result


# ── Install / Uninstall ──────────────────────────────────────────

def install_app(db: Session, app_id: str, user_id: str) -> dict:
    """Install an app for a user. Increments install_count."""
    app = db.query(AppListing).filter(
        AppListing.id == app_id,
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    ).first()

    if not app:
        return {"error": "App not found"}

    # Check if already installed
    existing = db.query(AppInstall).filter(
        AppInstall.app_id == app_id,
        AppInstall.user_id == user_id,
        AppInstall.uninstalled_at == None,  # noqa: E711
    ).first()

    if existing:
        return {"error": "App already installed"}

    # Check for previous install that was uninstalled — reactivate
    prev = db.query(AppInstall).filter(
        AppInstall.app_id == app_id,
        AppInstall.user_id == user_id,
    ).first()

    if prev:
        prev.uninstalled_at = None
        prev.installed_at = datetime.now(timezone.utc)
    else:
        install = AppInstall(
            app_id=app_id,
            user_id=user_id,
        )
        db.add(install)

    app.install_count += 1
    db.flush()

    return {"message": "App installed", "install_count": app.install_count}


def uninstall_app(db: Session, app_id: str, user_id: str) -> dict:
    """Uninstall an app for a user. Decrements install_count."""
    install = db.query(AppInstall).filter(
        AppInstall.app_id == app_id,
        AppInstall.user_id == user_id,
        AppInstall.uninstalled_at == None,  # noqa: E711
    ).first()

    if not install:
        return {"error": "App not installed"}

    install.uninstalled_at = datetime.now(timezone.utc)

    app = db.query(AppListing).filter(AppListing.id == app_id).first()
    if app and app.install_count > 0:
        app.install_count -= 1

    db.flush()
    return {"message": "App uninstalled"}


# ── Reviews ──────────────────────────────────────────────────────

def review_app(
    db: Session,
    app_id: str,
    user_id: str,
    rating: int,
    comment: Optional[str] = None,
) -> dict:
    """Add or update a review. Recalculates the app's average rating."""
    if rating < 1 or rating > 5:
        return {"error": "Rating must be between 1 and 5"}

    app = db.query(AppListing).filter(
        AppListing.id == app_id,
        AppListing.is_active == True,  # noqa: E712
    ).first()

    if not app:
        return {"error": "App not found"}

    # Can't review your own app
    if app.owner_id == user_id:
        return {"error": "Cannot review your own app"}

    # Upsert review (unique constraint on app_id + user_id)
    existing = db.query(AppReview).filter(
        AppReview.app_id == app_id,
        AppReview.user_id == user_id,
    ).first()

    if existing:
        existing.rating = rating
        existing.comment = comment
        existing.updated_at = datetime.now(timezone.utc)
    else:
        review = AppReview(
            app_id=app_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
        )
        db.add(review)

    db.flush()

    # Recalculate average rating
    avg_result = db.query(
        sqlfunc.avg(AppReview.rating),
        sqlfunc.count(AppReview.id),
    ).filter(AppReview.app_id == app_id).first()

    app.rating_avg = float(avg_result[0]) if avg_result[0] else 0.0
    app.rating_count = avg_result[1] or 0
    db.flush()

    return {
        "message": "Review submitted",
        "rating_avg": round(app.rating_avg, 2),
        "rating_count": app.rating_count,
    }


# ── Featured / Trending ─────────────────────────────────────────

def get_featured(db: Session, limit: int = 12) -> list[dict]:
    """Get featured and trending apps."""
    # First: admin-curated featured apps
    featured = db.query(AppListing).filter(
        AppListing.is_featured == True,  # noqa: E712
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    ).order_by(desc(AppListing.install_count)).limit(limit).all()

    # If not enough featured, fill with top-rated
    if len(featured) < limit:
        featured_ids = {a.id for a in featured}
        remaining = limit - len(featured)
        q = db.query(AppListing).filter(
            AppListing.is_published == True,  # noqa: E712
            AppListing.is_active == True,     # noqa: E712
        )
        if featured_ids:
            q = q.filter(~AppListing.id.in_(featured_ids))
        trending = q.order_by(
            desc(AppListing.install_count),
            desc(AppListing.rating_avg),
        ).limit(remaining).all()
        featured.extend(trending)

    # Batch-fetch owner usernames
    owner_ids = list({a.owner_id for a in featured})
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    return [_listing_to_dict(a, owners.get(a.owner_id)) for a in featured]


# ── User's Installed Apps ────────────────────────────────────────

def get_user_installs(db: Session, user_id: str) -> list[dict]:
    """Get all apps installed by a user."""
    installs = db.query(AppInstall).filter(
        AppInstall.user_id == user_id,
        AppInstall.uninstalled_at == None,  # noqa: E711
    ).all()

    if not installs:
        return []

    app_ids = [i.app_id for i in installs]
    apps = db.query(AppListing).filter(AppListing.id.in_(app_ids)).all()

    owner_ids = list({a.owner_id for a in apps})
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    return [_listing_to_dict(a, owners.get(a.owner_id)) for a in apps]
