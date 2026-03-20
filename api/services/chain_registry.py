"""
REFINET Cloud — Chain Registry Service
Single source of truth for EVM chain configuration.
Replaces all hardcoded CHAIN_RPC, CHAIN_IDS, EXPLORER_APIS dicts.

Usage:
    from api.services.chain_registry import ChainRegistry
    registry = ChainRegistry.get()

    rpc = registry.get_rpc("base")                 # or registry.get_rpc(8453)
    chain = registry.get_chain("ethereum")
    all_chains = registry.get_all_chains()
"""

import json
import logging
import time
import urllib.request
from typing import Optional, Union

from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.chain_registry")

# In-memory cache with TTL
_cache: dict = {}
_cache_ts: float = 0
_CACHE_TTL = 60.0  # seconds

# Legacy name → chain_id mapping (for backward compatibility with string-based lookups)
_LEGACY_NAMES = {
    "ethereum": 1, "eth": 1, "mainnet": 1,
    "polygon": 137, "matic": 137,
    "arbitrum": 42161, "arb": 42161,
    "optimism": 10, "op": 10,
    "base": 8453,
    "sepolia": 11155111,
    "goerli": 5,
    "mumbai": 80001,
    "base-sepolia": 84532,
}


class ChainRegistry:
    """Cached, database-backed chain configuration."""

    _instance = None

    @classmethod
    def get(cls) -> "ChainRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_cache(self) -> dict:
        """Load all active chains from DB into memory cache."""
        global _cache, _cache_ts
        now = time.monotonic()
        if _cache and (now - _cache_ts) < _CACHE_TTL:
            return _cache

        try:
            from api.database import get_public_db
            from api.models.chain import SupportedChain
            with get_public_db() as db:
                chains = db.query(SupportedChain).all()
                result = {}
                for c in chains:
                    entry = {
                        "chain_id": c.chain_id,
                        "name": c.name,
                        "short_name": c.short_name,
                        "currency": c.currency,
                        "rpc_url": c.rpc_url,
                        "explorer_url": c.explorer_url,
                        "explorer_api_url": c.explorer_api_url,
                        "icon_url": c.icon_url,
                        "is_testnet": c.is_testnet,
                        "is_active": c.is_active,
                    }
                    result[c.chain_id] = entry
                    result[c.short_name] = entry  # index by name too
                _cache = result
                _cache_ts = now
                return result
        except Exception as e:
            logger.warning("Chain registry cache load failed: %s", e)
            return _cache or {}

    def invalidate_cache(self):
        """Force cache refresh on next access."""
        global _cache_ts
        _cache_ts = 0

    def resolve_chain_id(self, chain: Union[str, int]) -> Optional[int]:
        """Resolve a chain name or ID to a numeric chain_id."""
        if isinstance(chain, int):
            return chain
        # Try legacy mapping first (fast)
        chain_lower = chain.lower().strip()
        if chain_lower in _LEGACY_NAMES:
            return _LEGACY_NAMES[chain_lower]
        # Try DB cache
        cache = self._load_cache()
        entry = cache.get(chain_lower)
        if entry:
            return entry["chain_id"]
        return None

    def get_chain(self, chain: Union[str, int]) -> Optional[dict]:
        """Get full chain config by name or chain_id."""
        cache = self._load_cache()
        if isinstance(chain, int):
            return cache.get(chain)
        return cache.get(chain.lower().strip())

    def get_rpc(self, chain: Union[str, int]) -> Optional[str]:
        """Get RPC URL for a chain."""
        entry = self.get_chain(chain)
        return entry["rpc_url"] if entry else None

    def get_chain_id(self, chain: Union[str, int]) -> Optional[int]:
        """Get numeric chain ID."""
        return self.resolve_chain_id(chain)

    def get_explorer_api(self, chain: Union[str, int]) -> Optional[str]:
        """Get block explorer API URL."""
        entry = self.get_chain(chain)
        return entry["explorer_api_url"] if entry else None

    def get_explorer_url(self, chain: Union[str, int]) -> Optional[str]:
        """Get block explorer base URL."""
        entry = self.get_chain(chain)
        return entry["explorer_url"] if entry else None

    def get_all_chains(self, active_only: bool = True) -> list[dict]:
        """Get all chains as a list of dicts."""
        cache = self._load_cache()
        seen = set()
        result = []
        for key, entry in cache.items():
            if isinstance(key, int) and entry["chain_id"] not in seen:
                if active_only and not entry.get("is_active", True):
                    continue
                seen.add(entry["chain_id"])
                result.append(entry)
        return sorted(result, key=lambda x: x["chain_id"])

    def get_chain_names(self, active_only: bool = True) -> list[str]:
        """Get list of short_names for all active chains."""
        return [c["short_name"] for c in self.get_all_chains(active_only)]


def add_chain(
    db: Session,
    chain_id: int,
    name: str,
    short_name: str,
    rpc_url: str,
    currency: str = "ETH",
    explorer_url: Optional[str] = None,
    explorer_api_url: Optional[str] = None,
    icon_url: Optional[str] = None,
    is_testnet: bool = False,
    added_by: str = "system",
) -> dict:
    """Add a new chain to the registry."""
    from api.models.chain import SupportedChain

    existing = db.query(SupportedChain).filter(SupportedChain.chain_id == chain_id).first()
    if existing:
        return {"error": f"Chain {chain_id} already exists: {existing.name}"}

    chain = SupportedChain(
        chain_id=chain_id,
        name=name,
        short_name=short_name.lower().strip(),
        currency=currency,
        rpc_url=rpc_url,
        explorer_url=explorer_url,
        explorer_api_url=explorer_api_url,
        icon_url=icon_url,
        is_testnet=is_testnet,
        added_by=added_by,
    )
    db.add(chain)
    db.flush()

    # Invalidate cache
    ChainRegistry.get().invalidate_cache()

    logger.info("Chain added: %d %s (%s)", chain_id, name, short_name)
    return {
        "chain_id": chain_id,
        "name": name,
        "short_name": short_name,
        "rpc_url": rpc_url,
        "status": "added",
    }


def import_from_chainlist(db: Session, chain_id: int, added_by: str = "system") -> dict:
    """
    Import chain config from chainlist.org API.
    Fetches chain metadata by chain_id and adds to registry.
    """
    try:
        url = f"https://raw.githubusercontent.com/ethereum-lists/chains/master/_data/chains/eip155-{chain_id}.json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {"error": f"Failed to fetch chain {chain_id} from chainlist: {e}"}

    name = data.get("name", f"Chain {chain_id}")
    short_name = data.get("shortName", f"chain{chain_id}").lower()
    currency = "ETH"
    native = data.get("nativeCurrency", {})
    if native:
        currency = native.get("symbol", "ETH")

    # Pick first public RPC
    rpc_urls = data.get("rpc", [])
    rpc_url = None
    for r in rpc_urls:
        if isinstance(r, str) and r.startswith("https://") and "${" not in r:
            rpc_url = r
            break
    if not rpc_url:
        return {"error": f"No public HTTPS RPC found for chain {chain_id}"}

    # Explorer
    explorers = data.get("explorers", [])
    explorer_url = None
    explorer_api_url = None
    if explorers:
        explorer_url = explorers[0].get("url")

    is_testnet = "testnet" in name.lower() or data.get("testnet", False)

    icon_url = None
    if data.get("icon"):
        icon_url = f"https://icons.llamao.fi/icons/chains/rsz_{short_name}.jpg"

    return add_chain(
        db, chain_id=chain_id, name=name, short_name=short_name,
        rpc_url=rpc_url, currency=currency,
        explorer_url=explorer_url, explorer_api_url=explorer_api_url,
        icon_url=icon_url, is_testnet=is_testnet, added_by=added_by,
    )
