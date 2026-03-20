"""
REFINET Cloud — Response Cache Middleware
TTL-based in-memory LRU cache for GET endpoints.
Zero dependencies — uses Python dict with timestamps.
"""

import hashlib
import logging
import time
import threading
from collections import OrderedDict
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("refinet.middleware.cache")

# Route patterns and their TTL in seconds (0 = no cache)
_ROUTE_TTLS = {
    "/explore/chains": 300,
    "/explore/contracts": 60,
    "/inference/models": 120,
    "/health": 15,
    "/health/ready": 15,
}

# Prefix patterns for broader matching
_PREFIX_TTLS = {
    "/registry/": 60,
    "/knowledge/search": 30,
}

MAX_CACHE_SIZE = 1000
MAX_BODY_SIZE = 256 * 1024  # Don't cache responses > 256KB


class _CacheEntry:
    __slots__ = ("body", "status_code", "headers", "expires_at")

    def __init__(self, body: bytes, status_code: int, headers: dict, ttl: float):
        self.body = body
        self.status_code = status_code
        self.headers = headers
        self.expires_at = time.monotonic() + ttl


class ResponseCache:
    """Thread-safe bounded LRU cache with TTL expiration."""

    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[_CacheEntry]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return entry

    def put(self, key: str, entry: _CacheEntry):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = entry
            else:
                self._store[key] = entry
                while len(self._store) > self._max_size:
                    self._store.popitem(last=False)

    def invalidate_prefix(self, prefix: str):
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]

    @property
    def stats(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
        }


# Singleton cache instance
_cache = ResponseCache()


def get_response_cache() -> ResponseCache:
    return _cache


def _get_ttl(path: str) -> int:
    """Determine cache TTL for a given path. Returns 0 for uncacheable."""
    if path in _ROUTE_TTLS:
        return _ROUTE_TTLS[path]
    for prefix, ttl in _PREFIX_TTLS.items():
        if path.startswith(prefix):
            return ttl
    return 0


def _make_cache_key(request: Request) -> str:
    """Build cache key from method + path + query + user identity."""
    user_id = "anon"
    auth = request.headers.get("authorization", "")
    if auth:
        user_id = hashlib.md5(auth.encode()).hexdigest()[:8]
    raw = f"{request.method}:{request.url.path}:{request.url.query}:{user_id}"
    return raw


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """
    Caches GET responses for configured routes.
    Adds X-Cache header (HIT/MISS) to all responses.
    """

    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            response = await call_next(request)
            response.headers["X-Cache"] = "BYPASS"
            return response

        ttl = _get_ttl(request.url.path)
        if ttl == 0:
            response = await call_next(request)
            response.headers["X-Cache"] = "BYPASS"
            return response

        cache_key = _make_cache_key(request)
        cached = _cache.get(cache_key)

        if cached is not None:
            return Response(
                content=cached.body,
                status_code=cached.status_code,
                headers={**cached.headers, "X-Cache": "HIT"},
            )

        # Cache miss — call the actual endpoint
        response = await call_next(request)

        # Only cache successful responses
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    chunk = chunk.encode()
                body += chunk

            if len(body) <= MAX_BODY_SIZE:
                headers = dict(response.headers)
                headers.pop("content-length", None)
                entry = _CacheEntry(body, response.status_code, headers, ttl)
                _cache.put(cache_key, entry)

            return Response(
                content=body,
                status_code=response.status_code,
                headers={**dict(response.headers), "X-Cache": "MISS"},
            )

        response.headers["X-Cache"] = "MISS"
        return response
