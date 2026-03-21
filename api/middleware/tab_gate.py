"""
REFINET Cloud — Tab Gate Middleware
Enforces tab visibility at the API route level.
Disabled tabs return 403 for all non-master-admin users.
Master admin always passes through.
"""

import json
import logging
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("refinet.tab_gate")

# Map tab keys to their API route prefixes
TAB_ROUTE_MAP = {
    "chat": ["/v1/chat"],
    "agents": ["/agents"],
    "knowledge": ["/knowledge"],
    "devices": ["/devices"],
    "messages": ["/messages"],
    "network": ["/p2p"],
    "pipeline": ["/pipeline"],
    "deployments": ["/deployments"],
    "dapp": ["/dapp"],
    "projects": ["/projects"],
    "explore": ["/explore", "/registry"],
    "store": ["/store", "/submissions", "/apps"],
    "repo": ["/repo"],
    "webhooks": ["/webhooks"],
    "payments": ["/payments"],
    "help": ["/support"],
}

# Routes that should NEVER be gated (health, auth, admin, MCP, etc.)
EXEMPT_PREFIXES = [
    "/health", "/auth", "/admin", "/mcp", "/graphql", "/ws",
    "/docs", "/openapi", "/v1/inference",
    "/identity", "/chain", "/broker", "/vector-memory", "/workers",
]

# In-memory cache for tab visibility (avoids DB hit per request)
_cache = {"tabs": None, "expires": 0.0}
_CACHE_TTL = 30  # seconds


def _get_cached_visibility() -> Optional[dict]:
    """Get cached tab visibility. Returns None if cache expired."""
    if _cache["tabs"] is not None and time.time() < _cache["expires"]:
        return _cache["tabs"]
    return None


def _refresh_cache():
    """Refresh the tab visibility cache from the database."""
    try:
        from api.database import get_internal_db
        from api.models.internal import SystemConfig
        with get_internal_db() as db:
            config = db.query(SystemConfig).filter(
                SystemConfig.key == "tab_visibility"
            ).first()
            if config and config.value:
                tabs = json.loads(config.value)
            else:
                tabs = {}  # Empty = all enabled (defaults apply)
        _cache["tabs"] = tabs
        _cache["expires"] = time.time() + _CACHE_TTL
        return tabs
    except Exception as e:
        logger.warning("Tab gate cache refresh failed: %s", e)
        _cache["tabs"] = {}
        _cache["expires"] = time.time() + _CACHE_TTL
        return {}


def _is_master_admin(token: str) -> bool:
    """Check if the Bearer token belongs to a master_admin."""
    try:
        from api.auth.jwt import decode_access_token
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return False
        from api.database import get_internal_db
        from api.auth.roles import is_master_admin
        with get_internal_db() as db:
            return is_master_admin(db, user_id)
    except Exception:
        return False


class TabGateMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks API access to disabled tabs.
    Master admin bypasses all gates.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip exempt routes (admin, auth, health, etc.)
        for prefix in EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Get tab visibility
        tabs = _get_cached_visibility()
        if tabs is None:
            tabs = _refresh_cache()

        # Check if this path belongs to a disabled tab
        disabled_tab = None
        for tab_key, prefixes in TAB_ROUTE_MAP.items():
            if tabs.get(tab_key) is False:
                for prefix in prefixes:
                    if path.startswith(prefix):
                        disabled_tab = tab_key
                        break
            if disabled_tab:
                break

        if not disabled_tab:
            return await call_next(request)

        # Tab is disabled — check if user is master_admin
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if _is_master_admin(token):
                return await call_next(request)

        # Block access
        return JSONResponse(
            status_code=403,
            content={"detail": "This feature is not currently available"},
        )


def invalidate_tab_cache():
    """Call this when tab visibility is updated to force cache refresh."""
    _cache["tabs"] = None
    _cache["expires"] = 0.0
