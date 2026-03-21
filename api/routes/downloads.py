"""
REFINET Cloud — Product Download & Lead Capture Routes
Public endpoints for product downloads, waitlist signups, and lead tracking.
Admin endpoint for download analytics and lead management.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from api.database import public_db_dependency, internal_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.roles import is_admin
from api.models.public import DownloadLead
from api.schemas.downloads import (
    DownloadRegisterRequest,
    DownloadRegisterResponse,
    ProductCatalogResponse,
    ProductInfo,
    DownloadStatsResponse,
)

logger = logging.getLogger("refinet.downloads")
router = APIRouter(prefix="/downloads", tags=["Downloads"])

# ── Product Catalog ────────────────────────────────────────────────
# Source of truth for product metadata and download URLs.
# Download paths are relative — frontend prepends the site origin.

PRODUCT_CATALOG = [
    {
        "name": "browser",
        "display_name": "REFINET Browser",
        "tagline": "Sovereign Internet Access",
        "description": "Privacy browser routing through Pillars with GROOT AI sidebar. "
                       "Decentralized DNS, encrypted transit, IPFS native, wallet-based identity.",
        "repo": "https://github.com/circularityglobal/REFINET-BROWSER",
        "available": False,
        "version": None,
        "downloads": {},
    },
    {
        "name": "pillars",
        "display_name": "REFINET Pillars",
        "tagline": "Sovereign Infrastructure",
        "description": "Permissionless mesh networking, anonymized proxy routing, "
                       "Gopher protocol, and encrypted vault for sovereign infrastructure.",
        "repo": "https://github.com/circularityglobal/REFINET-PILLARS",
        "available": True,
        "version": "0.3.0",
        "downloads": {
            "windows": "/public-downloads/pillar/product/refinet-pillar-setup.exe",
            "macos": "/public-downloads/pillar/product/refinet-pillar.dmg",
            "linux": "/public-downloads/pillar/product/refinet-pillar.AppImage",
            "debian": "/public-downloads/pillar/product/refinet-pillar.deb",
        },
    },
    {
        "name": "wizardos",
        "display_name": "WizardOS",
        "tagline": "Sovereign AI Desktop",
        "description": "Desktop AI operating system powered by GROOT. "
                       "Sovereign inference, agent execution, multi-mode personalities, local memory.",
        "repo": "https://github.com/circularityglobal/CIFI-WIZARDOS",
        "available": False,
        "version": None,
        "downloads": {},
    },
    {
        "name": "cluster",
        "display_name": "REFINET Cluster",
        "tagline": "Distributed Compute",
        "description": "Run a GROOT node on Oracle Cloud ARM. "
                       "BitNet inference, auto-registration, health monitoring.",
        "repo": "",
        "available": True,
        "version": None,
        "downloads": {
            "linux": "/public-downloads/cluster/product/cluster_setup.sh",
        },
    },
]

VALID_PRODUCTS = {p["name"] for p in PRODUCT_CATALOG}


def _get_product(name: str) -> Optional[dict]:
    for p in PRODUCT_CATALOG:
        if p["name"] == name:
            return p
    return None


def _hash_ip(request: Request) -> Optional[str]:
    """SHA-256 hash of client IP for privacy-safe dedup tracking."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def _try_embed(text: str) -> Optional[str]:
    """Generate 384-dim embedding and return as JSON string. Returns None on failure."""
    try:
        from api.services.embedding import embed_text, is_available
        if not is_available():
            return None
        vec = embed_text(text)
        if vec is not None:
            return json.dumps([round(float(v), 6) for v in vec])
    except Exception as e:
        logger.warning("Embedding failed for download lead: %s", e)
    return None


def _try_publish_event(event_name: str, data: dict) -> None:
    """Fire-and-forget async event publish to EventBus."""
    try:
        import asyncio
        from api.services.event_bus import EventBus
        bus = EventBus.get()
        loop = asyncio.get_running_loop()
        loop.create_task(bus.publish(event_name, data))
    except (RuntimeError, Exception) as e:
        logger.debug("Event publish failed: %s", e)


def _get_optional_user_id(request: Request) -> Optional[str]:
    """Extract user_id from Bearer token if present. Returns None if not authenticated."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = decode_access_token(auth[7:])
        return payload.get("sub")
    except Exception:
        return None


def _require_admin(request: Request, internal_db: Session) -> str:
    """Return user_id if admin. Raises 403 otherwise."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(auth[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload["sub"]
    if not is_admin(internal_db, user_id):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user_id


# ── Public Endpoints ───────────────────────────────────────────────


@router.get("/products")
def get_products():
    """Return the product catalog with availability status."""
    return {"products": PRODUCT_CATALOG}


@router.post("/register", response_model=DownloadRegisterResponse)
def register_download(
    body: DownloadRegisterRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Register a download lead and return the download URL."""
    product = _get_product(body.product)
    if not product:
        raise HTTPException(status_code=400, detail=f"Unknown product: {body.product}")

    if not product["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"{product['display_name']} is not yet available. Use /downloads/waitlist instead.",
        )

    # Resolve download URL for the requested platform
    download_url = None
    if body.platform and body.platform in product["downloads"]:
        download_url = product["downloads"][body.platform]
    elif product["downloads"]:
        # Default to first available platform
        download_url = next(iter(product["downloads"].values()))

    if not download_url:
        raise HTTPException(status_code=400, detail="No download available for this platform")

    # Create lead record
    import uuid
    lead = DownloadLead(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email,
        eth_address=body.eth_address,
        product=body.product,
        platform=body.platform,
        version=product.get("version"),
        user_id=_get_optional_user_id(request),
        referrer=body.referrer,
        ip_hash=_hash_ip(request),
        user_agent=request.headers.get("user-agent", "")[:500],
        marketing_consent=body.marketing_consent,
        download_type="download",
    )

    # Generate semantic embedding for GROOT reasoning
    embed_text = f"Download {product['display_name']} for {body.platform or 'unknown'} by {body.name}"
    lead.embedding_json = _try_embed(embed_text)

    db.add(lead)
    db.commit()

    # Publish event for real-time dashboard
    _try_publish_event("download.registered", {
        "lead_id": lead.id,
        "product": body.product,
        "platform": body.platform,
        "email": body.email,
        "type": "download",
    })

    logger.info("Download lead registered: %s for %s (%s)", body.email, body.product, body.platform)

    return DownloadRegisterResponse(
        lead_id=lead.id,
        download_url=download_url,
        product=body.product,
        message=f"Download ready for {product['display_name']}",
    )


@router.post("/waitlist", response_model=DownloadRegisterResponse)
def join_waitlist(
    body: DownloadRegisterRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Register for the waitlist for a product not yet available."""
    product = _get_product(body.product)
    if not product:
        raise HTTPException(status_code=400, detail=f"Unknown product: {body.product}")

    import uuid
    lead = DownloadLead(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email,
        eth_address=body.eth_address,
        product=body.product,
        platform=body.platform,
        user_id=_get_optional_user_id(request),
        referrer=body.referrer,
        ip_hash=_hash_ip(request),
        user_agent=request.headers.get("user-agent", "")[:500],
        marketing_consent=body.marketing_consent,
        download_type="waitlist",
    )

    embed_text = f"Waitlist signup for {product['display_name']} by {body.name}"
    lead.embedding_json = _try_embed(embed_text)

    db.add(lead)
    db.commit()

    _try_publish_event("download.waitlist", {
        "lead_id": lead.id,
        "product": body.product,
        "email": body.email,
        "type": "waitlist",
    })

    logger.info("Waitlist signup: %s for %s", body.email, body.product)

    return DownloadRegisterResponse(
        lead_id=lead.id,
        download_url=None,
        product=body.product,
        message=f"You're on the waitlist for {product['display_name']}! We'll notify you when it's ready.",
    )


# ── Admin Endpoints ───────────────────────────────────────────────


@router.get("/admin/stats")
def get_download_stats(
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin-only: download analytics and lead management."""
    _require_admin(request, internal_db)

    # Total counts by type
    total_downloads = db.query(sa_func.count(DownloadLead.id)).filter(
        DownloadLead.download_type == "download"
    ).scalar() or 0
    total_waitlist = db.query(sa_func.count(DownloadLead.id)).filter(
        DownloadLead.download_type == "waitlist"
    ).scalar() or 0

    # By product
    by_product = {}
    product_rows = db.query(
        DownloadLead.product, sa_func.count(DownloadLead.id)
    ).group_by(DownloadLead.product).all()
    for product, count in product_rows:
        by_product[product] = count

    # By platform
    by_platform = {}
    platform_rows = db.query(
        DownloadLead.platform, sa_func.count(DownloadLead.id)
    ).filter(DownloadLead.platform.isnot(None)).group_by(DownloadLead.platform).all()
    for platform, count in platform_rows:
        by_platform[platform] = count

    # By type
    by_type = {"download": total_downloads, "waitlist": total_waitlist}

    # Recent leads (last 50)
    recent = db.query(DownloadLead).order_by(
        DownloadLead.created_at.desc()
    ).limit(50).all()
    recent_leads = [
        {
            "id": l.id,
            "name": l.name,
            "email": l.email,
            "eth_address": l.eth_address,
            "product": l.product,
            "platform": l.platform,
            "download_type": l.download_type,
            "marketing_consent": l.marketing_consent,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in recent
    ]

    # Daily counts (last 30 days)
    from sqlalchemy import cast, Date
    daily = db.query(
        cast(DownloadLead.created_at, Date).label("date"),
        sa_func.count(DownloadLead.id).label("count"),
    ).group_by("date").order_by(sa_func.desc("date")).limit(30).all()
    daily_counts = [
        {"date": str(row.date), "count": row.count}
        for row in daily
    ]

    return {
        "total_downloads": total_downloads,
        "total_waitlist": total_waitlist,
        "by_product": by_product,
        "by_platform": by_platform,
        "by_type": by_type,
        "recent_leads": recent_leads,
        "daily_counts": daily_counts,
    }


@router.get("/admin/export")
def export_leads_csv(
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin-only: export all download leads as CSV."""
    _require_admin(request, internal_db)

    from fastapi.responses import StreamingResponse
    import io
    import csv

    leads = db.query(DownloadLead).order_by(DownloadLead.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "email", "eth_address", "product", "platform",
                      "download_type", "marketing_consent", "created_at"])
    for l in leads:
        writer.writerow([
            l.id, l.name, l.email, l.eth_address, l.product, l.platform,
            l.download_type, l.marketing_consent,
            l.created_at.isoformat() if l.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=download_leads.csv"},
    )
