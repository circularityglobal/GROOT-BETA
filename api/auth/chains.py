"""
REFINET Cloud — EVM Chain Registry
Supported chains for multi-chain SIWE authentication.
Queries the `supported_chains` DB table first, falls back to hardcoded defaults.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ChainInfo:
    chain_id: int
    name: str
    short_name: str
    currency: str
    rpc_url: str
    explorer_url: str
    is_testnet: bool = False


# ── Hardcoded Fallbacks (used when DB is unavailable) ────────────────

FALLBACK_CHAINS: dict[int, ChainInfo] = {
    1: ChainInfo(
        chain_id=1,
        name="Ethereum Mainnet",
        short_name="eth",
        currency="ETH",
        rpc_url="https://eth.llamarpc.com",
        explorer_url="https://etherscan.io",
    ),
    137: ChainInfo(
        chain_id=137,
        name="Polygon",
        short_name="matic",
        currency="MATIC",
        rpc_url="https://polygon-rpc.com",
        explorer_url="https://polygonscan.com",
    ),
    42161: ChainInfo(
        chain_id=42161,
        name="Arbitrum One",
        short_name="arb1",
        currency="ETH",
        rpc_url="https://arb1.arbitrum.io/rpc",
        explorer_url="https://arbiscan.io",
    ),
    10: ChainInfo(
        chain_id=10,
        name="Optimism",
        short_name="oeth",
        currency="ETH",
        rpc_url="https://mainnet.optimism.io",
        explorer_url="https://optimistic.etherscan.io",
    ),
    8453: ChainInfo(
        chain_id=8453,
        name="Base",
        short_name="base",
        currency="ETH",
        rpc_url="https://mainnet.base.org",
        explorer_url="https://basescan.org",
    ),
    11155111: ChainInfo(
        chain_id=11155111,
        name="Sepolia",
        short_name="sep",
        currency="SEP",
        rpc_url="https://rpc.sepolia.org",
        explorer_url="https://sepolia.etherscan.io",
        is_testnet=True,
    ),
    50: ChainInfo(
        chain_id=50,
        name="XDC Network",
        short_name="xdc",
        currency="XDC",
        rpc_url="https://rpc.xinfin.network",
        explorer_url="https://explorer.xinfin.network",
    ),
    43113: ChainInfo(
        chain_id=43113,
        name="Avalanche Fuji",
        short_name="fuji",
        currency="AVAX",
        rpc_url="https://api.avax-test.network/ext/bc/C/rpc",
        explorer_url="https://testnet.snowtrace.io",
        is_testnet=True,
    ),
}

DEFAULT_CHAIN_ID = 43113  # Avalanche Fuji for testing; switch to 50 (XDC) for production

# ── Backward-compat alias ────────────────────────────────────────────
SUPPORTED_CHAINS = FALLBACK_CHAINS


def _load_chains_from_db() -> Optional[dict[int, ChainInfo]]:
    """Query the supported_chains table. Returns None if DB unavailable."""
    try:
        from api.database import get_public_db
        from api.models.chain import SupportedChain
        with get_public_db() as db:
            rows = db.query(SupportedChain).filter(
                SupportedChain.is_active == True
            ).all()
            if not rows:
                return None
            return {
                r.chain_id: ChainInfo(
                    chain_id=r.chain_id,
                    name=r.name,
                    short_name=r.short_name,
                    currency=r.currency or "ETH",
                    rpc_url=r.rpc_url,
                    explorer_url=r.explorer_url or "",
                    is_testnet=r.is_testnet or False,
                )
                for r in rows
            }
    except Exception:
        return None


def _merged_chains() -> dict[int, ChainInfo]:
    """Merge DB chains with hardcoded fallbacks. DB takes priority."""
    merged = dict(FALLBACK_CHAINS)
    db_chains = _load_chains_from_db()
    if db_chains:
        merged.update(db_chains)
    return merged


def get_chain(chain_id: int) -> Optional[ChainInfo]:
    return _merged_chains().get(chain_id)


def is_supported_chain(chain_id: int) -> bool:
    return chain_id in _merged_chains()


def get_supported_chain_ids() -> list[int]:
    return list(_merged_chains().keys())


def get_chains_summary() -> list[dict]:
    """Return chain info suitable for API responses."""
    return [
        {
            "chain_id": c.chain_id,
            "name": c.name,
            "short_name": c.short_name,
            "currency": c.currency,
            "explorer_url": c.explorer_url,
            "is_testnet": c.is_testnet,
        }
        for c in _merged_chains().values()
    ]
