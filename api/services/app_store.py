"""
REFINET Cloud — App Store Service
Core business logic for the App Store: publish, search, install, review, featured.
Admin functions: verify, feature, deactivate, admin-publish, stats.
Asset migration: import DApps, agents, and registry projects into the store.
"""

import asyncio
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

VALID_CATEGORIES = ("dapp", "agent", "tool", "template", "dataset", "api-service", "digital-asset")
VALID_PRICE_TYPES = ("free", "one-time", "subscription")
VALID_LICENSE_TYPES = ("open", "single-use", "multi-use", "enterprise")


# ── Helpers ──────────────────────────────────────────────────────

def _validate_url(url: Optional[str]) -> bool:
    """Validate that a URL is safe (HTTP/HTTPS only, no javascript:, file:, etc.)."""
    if not url:
        return True
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


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
        "download_count": app.download_count or 0,
        "rating_avg": round(app.rating_avg, 2) if app.rating_avg else 0.0,
        "rating_count": app.rating_count,
        "is_published": app.is_published,
        "is_verified": app.is_verified,
        "is_featured": app.is_featured,
        "listed_by_admin": app.listed_by_admin,
        "price_type": app.price_type or "free",
        "price_amount": app.price_amount or 0.0,
        "price_token": app.price_token,
        "price_token_amount": app.price_token_amount,
        "license_type": app.license_type or "open",
        "download_url": app.download_url,
        "external_url": app.external_url,
        "registry_project_id": app.registry_project_id,
        "dapp_build_id": app.dapp_build_id,
        "agent_id": app.agent_id,
        "is_active": app.is_active,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }


def _emit_event(event: str, data: dict):
    """Fire-and-forget event bus publish. Safe to call from sync or async context."""
    try:
        bus = EventBus.get()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(bus.publish(event, data))
        except RuntimeError:
            # No running loop (sync context in threadpool) — skip silently.
            # Events will still fire from async route handlers.
            pass
    except Exception:
        logger.debug("EventBus publish failed for %s", event)


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
    price_type: str = "free",
    price_amount: float = 0.0,
    price_token: Optional[str] = None,
    price_token_amount: Optional[float] = None,
    license_type: str = "open",
    download_url: Optional[str] = None,
    external_url: Optional[str] = None,
) -> dict:
    """Create or update an app listing."""
    if category not in VALID_CATEGORIES:
        return {"error": f"category must be one of: {', '.join(VALID_CATEGORIES)}"}

    if price_type not in VALID_PRICE_TYPES:
        return {"error": f"price_type must be one of: {', '.join(VALID_PRICE_TYPES)}"}

    if license_type not in VALID_LICENSE_TYPES:
        return {"error": f"license_type must be one of: {', '.join(VALID_LICENSE_TYPES)}"}

    # URL validation — prevent SSRF, javascript: injection
    for url_field, url_val in [("icon_url", icon_url), ("download_url", download_url), ("external_url", external_url)]:
        if url_val and not _validate_url(url_val):
            return {"error": f"{url_field} must be a valid HTTP or HTTPS URL"}

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
        existing.price_type = price_type
        existing.price_amount = price_amount
        existing.price_token = price_token
        existing.price_token_amount = price_token_amount
        existing.license_type = license_type
        existing.download_url = download_url or existing.download_url
        existing.external_url = external_url or existing.external_url
        existing.is_published = True
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()

        result = _listing_to_dict(existing, owner.username)
        _emit_event("appstore.app.updated", {"slug": slug, "app_id": existing.id, "owner_id": owner_id})
        return result

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
        price_type=price_type,
        price_amount=price_amount,
        price_token=price_token,
        price_token_amount=price_token_amount,
        license_type=license_type,
        download_url=download_url,
        external_url=external_url,
        is_published=True,
    )
    db.add(app)
    db.flush()

    result = _listing_to_dict(app, owner.username)
    _emit_event("appstore.app.published", {"slug": slug, "app_id": app.id, "owner_id": owner_id, "category": category})
    return result


# ── Search ───────────────────────────────────────────────────────

def search_apps(
    db: Session,
    query: Optional[str] = None,
    category: Optional[str] = None,
    chain: Optional[str] = None,
    price_type: Optional[str] = None,
    sort_by: str = "installs",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search published apps with filters and sorting."""
    # Input guards
    page = max(1, min(page, 1000))
    page_size = max(1, min(page_size, 50))

    q = db.query(AppListing).filter(
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    )

    if query:
        query = query[:500]  # Cap query length to prevent abuse
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
    if price_type:
        q = q.filter(AppListing.price_type == price_type)

    # Sorting
    if sort_by == "rating":
        q = q.order_by(desc(AppListing.rating_avg), desc(AppListing.rating_count))
    elif sort_by == "recent":
        q = q.order_by(desc(AppListing.created_at))
    elif sort_by == "name":
        q = q.order_by(AppListing.name)
    elif sort_by == "price_low":
        q = q.order_by(AppListing.price_amount)
    elif sort_by == "price_high":
        q = q.order_by(desc(AppListing.price_amount))
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

    # Atomic increment — prevents race condition with concurrent installs
    db.query(AppListing).filter(AppListing.id == app_id).update(
        {AppListing.install_count: AppListing.install_count + 1}
    )
    db.flush()
    db.refresh(app)

    _emit_event("appstore.app.installed", {"app_id": app_id, "user_id": user_id, "slug": app.slug})
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

    # Atomic decrement — prevents race condition
    db.query(AppListing).filter(
        AppListing.id == app_id,
        AppListing.install_count > 0,
    ).update({AppListing.install_count: AppListing.install_count - 1})

    db.flush()

    _emit_event("appstore.app.uninstalled", {"app_id": app_id, "user_id": user_id})
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

    _emit_event("appstore.app.reviewed", {"app_id": app_id, "user_id": user_id, "rating": rating, "slug": app.slug})
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


# ══════════════════════════════════════════════════════════════════
# ADMIN FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def admin_list_apps(
    db: Session,
    include_inactive: bool = False,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Admin: list all apps, including unpublished and inactive."""
    q = db.query(AppListing)
    if not include_inactive:
        q = q.filter(AppListing.is_active == True)  # noqa: E712
    if category:
        q = q.filter(AppListing.category == category)

    total = q.count()
    offset = (page - 1) * page_size
    apps = q.order_by(desc(AppListing.created_at)).offset(offset).limit(page_size).all()

    owner_ids = list({a.owner_id for a in apps})
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    return {
        "apps": [_listing_to_dict(a, owners.get(a.owner_id)) for a in apps],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


def admin_verify_app(db: Session, app_id: str, verified: bool = True) -> dict:
    """Admin: set is_verified flag on an app."""
    app = db.query(AppListing).filter(AppListing.id == app_id).first()
    if not app:
        return {"error": "App not found"}
    app.is_verified = verified
    app.updated_at = datetime.now(timezone.utc)
    db.flush()
    _emit_event("appstore.app.verified", {"app_id": app_id, "verified": verified, "slug": app.slug})
    return {"message": f"App {'verified' if verified else 'unverified'}", "app_id": app_id}


def admin_feature_app(db: Session, app_id: str, featured: bool = True) -> dict:
    """Admin: set is_featured flag on an app."""
    app = db.query(AppListing).filter(AppListing.id == app_id).first()
    if not app:
        return {"error": "App not found"}
    app.is_featured = featured
    app.updated_at = datetime.now(timezone.utc)
    db.flush()
    _emit_event("appstore.app.featured", {"app_id": app_id, "featured": featured, "slug": app.slug})
    return {"message": f"App {'featured' if featured else 'unfeatured'}", "app_id": app_id}


def admin_deactivate_app(db: Session, app_id: str, active: bool = False) -> dict:
    """Admin: activate or deactivate an app listing."""
    app = db.query(AppListing).filter(AppListing.id == app_id).first()
    if not app:
        return {"error": "App not found"}
    app.is_active = active
    app.updated_at = datetime.now(timezone.utc)
    db.flush()
    _emit_event("appstore.app.status_changed", {"app_id": app_id, "is_active": active, "slug": app.slug})
    return {"message": f"App {'activated' if active else 'deactivated'}", "app_id": app_id}


def admin_publish_product(
    db: Session,
    admin_user_id: str,
    name: str,
    description: str,
    category: str,
    readme: Optional[str] = None,
    chain: Optional[str] = None,
    version: str = "1.0.0",
    icon_url: Optional[str] = None,
    screenshots: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    price_type: str = "free",
    price_amount: float = 0.0,
    price_token: Optional[str] = None,
    price_token_amount: Optional[float] = None,
    license_type: str = "open",
    download_url: Optional[str] = None,
    external_url: Optional[str] = None,
) -> dict:
    """Admin: publish a product directly to the store (platform-listed)."""
    if category not in VALID_CATEGORIES:
        return {"error": f"category must be one of: {', '.join(VALID_CATEGORIES)}"}

    # When using X-Admin-Secret, admin_user_id is "system" — find or use first admin user
    admin_user = db.query(User).filter(User.id == admin_user_id).first()
    if not admin_user:
        # Fallback: use the first available user as the platform owner
        admin_user = db.query(User).first()
        if not admin_user:
            return {"error": "No users exist to own platform listings"}
        admin_user_id = admin_user.id

    slug = f"platform/{_slugify(name)}"

    existing = db.query(AppListing).filter(AppListing.slug == slug).first()
    if existing:
        # Update existing platform listing
        existing.name = name
        existing.description = description
        existing.category = category
        existing.chain = chain
        existing.version = version
        existing.readme = readme
        existing.icon_url = icon_url
        existing.screenshots = json.dumps(screenshots) if screenshots else existing.screenshots
        existing.tags = json.dumps(tags) if tags else existing.tags
        existing.price_type = price_type
        existing.price_amount = price_amount
        existing.price_token = price_token
        existing.price_token_amount = price_token_amount
        existing.license_type = license_type
        existing.download_url = download_url or existing.download_url
        existing.external_url = external_url or existing.external_url
        existing.is_published = True
        existing.is_verified = True
        existing.listed_by_admin = True
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        return _listing_to_dict(existing, "platform")

    app = AppListing(
        owner_id=admin_user_id,
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
        price_type=price_type,
        price_amount=price_amount,
        price_token=price_token,
        price_token_amount=price_token_amount,
        license_type=license_type,
        download_url=download_url,
        external_url=external_url,
        is_published=True,
        is_verified=True,
        is_featured=True,
        listed_by_admin=True,
    )
    db.add(app)
    db.flush()

    _emit_event("appstore.product.listed", {"app_id": app.id, "slug": slug, "category": category, "admin": admin_user_id})
    return _listing_to_dict(app, "platform")


def admin_store_stats(db: Session) -> dict:
    """Admin: get app store statistics."""
    total_apps = db.query(AppListing).filter(AppListing.is_active == True).count()  # noqa: E712
    published_apps = db.query(AppListing).filter(
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    ).count()
    verified_apps = db.query(AppListing).filter(AppListing.is_verified == True).count()  # noqa: E712
    featured_apps = db.query(AppListing).filter(AppListing.is_featured == True).count()  # noqa: E712
    total_installs = db.query(sqlfunc.sum(AppListing.install_count)).scalar() or 0
    total_reviews = db.query(AppReview).count()
    total_downloads = db.query(sqlfunc.sum(AppListing.download_count)).scalar() or 0

    # Category breakdown
    categories = db.query(
        AppListing.category,
        sqlfunc.count(AppListing.id),
    ).filter(
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    ).group_by(AppListing.category).all()

    # Pricing breakdown
    pricing = db.query(
        AppListing.price_type,
        sqlfunc.count(AppListing.id),
    ).filter(
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    ).group_by(AppListing.price_type).all()

    # Top 5 apps by installs
    top_apps = db.query(AppListing).filter(
        AppListing.is_published == True,  # noqa: E712
        AppListing.is_active == True,     # noqa: E712
    ).order_by(desc(AppListing.install_count)).limit(5).all()

    owner_ids = list({a.owner_id for a in top_apps})
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    return {
        "total_apps": total_apps,
        "published_apps": published_apps,
        "verified_apps": verified_apps,
        "featured_apps": featured_apps,
        "total_installs": total_installs,
        "total_reviews": total_reviews,
        "total_downloads": total_downloads,
        "categories": {row[0]: row[1] for row in categories},
        "pricing": {row[0]: row[1] for row in pricing},
        "top_apps": [
            {"name": a.name, "slug": a.slug, "installs": a.install_count, "owner": owners.get(a.owner_id)}
            for a in top_apps
        ],
    }


# ══════════════════════════════════════════════════════════════════
# ASSET MIGRATION — Import existing DApps, Agents, Registry → Store
# ══════════════════════════════════════════════════════════════════

def migrate_dapp_to_store(
    db: Session,
    dapp_build_id: str,
    owner_id: str,
    name: Optional[str] = None,
    description: str = "",
    price_type: str = "free",
    price_amount: float = 0.0,
    tags: Optional[list[str]] = None,
) -> dict:
    """Migrate an existing DApp build into the App Store."""
    from api.models.public import DAppBuild

    build = db.query(DAppBuild).filter(DAppBuild.id == dapp_build_id).first()
    if not build:
        return {"error": "DApp build not found"}
    if build.status != "ready":
        return {"error": "DApp build is not ready (status must be 'ready')"}
    if build.user_id != owner_id:
        return {"error": "You can only migrate your own DApp builds"}

    app_name = name or f"{build.template_name} DApp"
    download = f"/dapp/builds/{build.id}/download" if build.output_filename else None

    return publish_app(
        db,
        owner_id=owner_id,
        name=app_name,
        description=description or f"DApp built from {build.template_name} template",
        category="dapp",
        dapp_build_id=dapp_build_id,
        tags=tags or [build.template_name, "dapp"],
        price_type=price_type,
        price_amount=price_amount,
        download_url=download,
    )


def migrate_agent_to_store(
    db: Session,
    agent_id: str,
    owner_id: str,
    name: Optional[str] = None,
    description: str = "",
    price_type: str = "free",
    price_amount: float = 0.0,
    tags: Optional[list[str]] = None,
) -> dict:
    """Migrate an existing agent registration into the App Store."""
    from api.models.public import AgentRegistration

    agent = db.query(AgentRegistration).filter(AgentRegistration.id == agent_id).first()
    if not agent:
        return {"error": "Agent not found"}
    if agent.user_id != owner_id:
        return {"error": "You can only migrate your own agents"}

    app_name = name or agent.name

    return publish_app(
        db,
        owner_id=owner_id,
        name=app_name,
        description=description or f"AI agent: {agent.name}",
        category="agent",
        agent_id=agent_id,
        tags=tags or (["agent", agent.product] if agent.product else ["agent"]),
        price_type=price_type,
        price_amount=price_amount,
    )


def migrate_registry_to_store(
    db: Session,
    registry_project_id: str,
    owner_id: str,
    name: Optional[str] = None,
    description: str = "",
    category: str = "tool",
    price_type: str = "free",
    price_amount: float = 0.0,
    tags: Optional[list[str]] = None,
) -> dict:
    """Migrate a registry project into the App Store."""
    from api.models.registry import RegistryProject

    project = db.query(RegistryProject).filter(RegistryProject.id == registry_project_id).first()
    if not project:
        return {"error": "Registry project not found"}
    if project.owner_id != owner_id:
        return {"error": "You can only migrate your own registry projects"}

    app_name = name or project.name

    return publish_app(
        db,
        owner_id=owner_id,
        name=app_name,
        description=description or project.description or f"Registry project: {project.name}",
        category=category,
        chain=project.chain if hasattr(project, "chain") else None,
        registry_project_id=registry_project_id,
        tags=tags or ["registry"],
        price_type=price_type,
        price_amount=price_amount,
    )
