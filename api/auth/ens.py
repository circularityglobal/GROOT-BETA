"""
REFINET Cloud — ENS Resolution Service
Resolves ENS names, avatars, and text records for wallet addresses.
Uses Ethereum mainnet via web3.py with in-memory TTL cache.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from web3 import Web3

from api.auth.chains import get_chain

logger = logging.getLogger("refinet.ens")

# ── ENS Resolution Result ─────────────────────────────────────────────

@dataclass
class ENSProfile:
    """Resolved ENS data for a wallet address."""
    address: str
    name: Optional[str] = None          # e.g. "vitalik.eth"
    avatar: Optional[str] = None        # avatar URL
    description: Optional[str] = None   # ENS text record: description
    url: Optional[str] = None           # ENS text record: url
    twitter: Optional[str] = None       # ENS text record: com.twitter
    github: Optional[str] = None        # ENS text record: com.github
    email: Optional[str] = None         # ENS text record: email
    resolved: bool = False
    error: Optional[str] = None


# ── TTL Cache ──────────────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    profile: ENSProfile
    expires_at: float


class _ENSCache:
    """Simple in-memory TTL cache for ENS lookups."""

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[str, _CacheEntry] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[ENSProfile]:
        entry = self._store.get(key)
        if entry and entry.expires_at > time.monotonic():
            return entry.profile
        if entry:
            del self._store[key]
        return None

    def set(self, key: str, profile: ENSProfile) -> None:
        self._store[key] = _CacheEntry(
            profile=profile,
            expires_at=time.monotonic() + self._ttl,
        )

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


# Module-level cache (1 hour TTL)
_cache = _ENSCache(ttl_seconds=3600)


# ── Web3 Provider ──────────────────────────────────────────────────────

_w3_instance: Optional[Web3] = None


def _get_w3() -> Web3:
    """Get or create a Web3 provider connected to Ethereum mainnet."""
    global _w3_instance
    if _w3_instance is not None and _w3_instance.is_connected():
        return _w3_instance

    # ENS only lives on Ethereum mainnet (chain 1)
    chain = get_chain(1)
    rpc_url = chain.rpc_url if chain else "https://eth.llamarpc.com"

    try:
        _w3_instance = Web3(Web3.HTTPProvider(
            rpc_url,
            request_kwargs={"timeout": 3},
        ))
        if _w3_instance.is_connected():
            logger.info(f"ENS provider connected to {rpc_url}")
        else:
            logger.warning(f"ENS provider failed to connect to {rpc_url}")
    except Exception as e:
        logger.warning(f"ENS provider init failed: {e}")
        _w3_instance = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))

    return _w3_instance


# ── Forward Resolution (name → address) ────────────────────────────────

def resolve_ens_name(name: str) -> Optional[str]:
    """
    Resolve an ENS name to an Ethereum address.
    Returns checksummed address or None.
    """
    if not name or not name.endswith(".eth"):
        return None

    cache_key = f"fwd:{name.lower()}"
    cached = _cache.get(cache_key)
    if cached:
        return cached.address if cached.resolved else None

    try:
        w3 = _get_w3()
        address = w3.ens.address(name)  # type: ignore[union-attr]
        if address:
            checksummed = Web3.to_checksum_address(address)
            _cache.set(cache_key, ENSProfile(address=checksummed, name=name, resolved=True))
            return checksummed
    except Exception as e:
        logger.debug(f"ENS forward resolution failed for {name}: {e}")

    _cache.set(cache_key, ENSProfile(address="", name=name, resolved=False, error="not found"))
    return None


# ── Reverse Resolution (address → name) ───────────────────────────────

def resolve_ens_reverse(address: str) -> Optional[str]:
    """
    Reverse-resolve an address to an ENS name.
    Returns ENS name (e.g. 'vitalik.eth') or None.
    """
    cache_key = f"rev:{address.lower()}"
    cached = _cache.get(cache_key)
    if cached:
        return cached.name

    try:
        w3 = _get_w3()
        checksummed = Web3.to_checksum_address(address)
        name = w3.ens.name(checksummed)  # type: ignore[union-attr]
        if name:
            _cache.set(cache_key, ENSProfile(address=checksummed, name=name, resolved=True))
            return name
    except Exception as e:
        logger.debug(f"ENS reverse resolution failed for {address}: {e}")

    _cache.set(cache_key, ENSProfile(address=address, resolved=False))
    return None


# ── Full Profile Resolution ────────────────────────────────────────────

def resolve_ens_profile(address: str) -> ENSProfile:
    """
    Resolve full ENS profile for an address: name, avatar, text records.
    Results are cached for 1 hour.
    """
    cache_key = f"profile:{address.lower()}"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    profile = ENSProfile(address=Web3.to_checksum_address(address))

    try:
        w3 = _get_w3()
        checksummed = Web3.to_checksum_address(address)

        # Step 1: Reverse resolve to get ENS name
        name = w3.ens.name(checksummed)  # type: ignore[union-attr]
        if not name:
            profile.resolved = True
            _cache.set(cache_key, profile)
            return profile

        # Step 2: Verify forward resolution matches (prevents spoofing)
        forward = w3.ens.address(name)  # type: ignore[union-attr]
        if not forward or Web3.to_checksum_address(forward) != checksummed:
            logger.debug(f"ENS forward/reverse mismatch for {name} → {forward}")
            profile.resolved = True
            _cache.set(cache_key, profile)
            return profile

        profile.name = name
        profile.resolved = True

        # Step 3: Resolve text records
        profile.avatar = _get_text_record(w3, name, "avatar")
        profile.description = _get_text_record(w3, name, "description")
        profile.url = _get_text_record(w3, name, "url")
        profile.twitter = _get_text_record(w3, name, "com.twitter")
        profile.github = _get_text_record(w3, name, "com.github")
        profile.email = _get_text_record(w3, name, "email")

    except Exception as e:
        logger.warning(f"ENS profile resolution failed for {address}: {e}")
        profile.error = str(e)
        profile.resolved = True

    _cache.set(cache_key, profile)
    return profile


def _get_text_record(w3: Web3, name: str, key: str) -> Optional[str]:
    """Safely fetch a single ENS text record using proper namehash."""
    try:
        from ens.utils import raw_name_to_hash
        resolver = w3.ens.resolver(name)  # type: ignore[union-attr]
        if resolver:
            node = raw_name_to_hash(name)
            value = resolver.caller.text(node, key)
            return value if value else None
    except Exception:
        pass
    return None


# ── Batch Resolution ──────────────────────────────────────────────────

def resolve_ens_batch(addresses: list[str]) -> dict[str, ENSProfile]:
    """
    Resolve ENS profiles for multiple addresses.
    Uses cache where available, only fetches uncached addresses.
    """
    results: dict[str, ENSProfile] = {}
    uncached: list[str] = []

    for addr in addresses:
        cache_key = f"profile:{addr.lower()}"
        cached = _cache.get(cache_key)
        if cached:
            results[addr] = cached
        else:
            uncached.append(addr)

    for addr in uncached:
        results[addr] = resolve_ens_profile(addr)

    return results


# ── Cache Management ──────────────────────────────────────────────────

def invalidate_ens_cache(address: str, ens_name: Optional[str] = None) -> None:
    """Invalidate all cached ENS data for an address (and optional forward name)."""
    lower = address.lower()
    _cache.invalidate(f"profile:{lower}")
    _cache.invalidate(f"rev:{lower}")
    if ens_name:
        _cache.invalidate(f"fwd:{ens_name.lower()}")


def get_cache_stats() -> dict:
    """Return cache statistics."""
    return {"entries": _cache.size, "ttl_seconds": _cache._ttl}
