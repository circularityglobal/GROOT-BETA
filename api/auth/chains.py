"""
REFINET Cloud — EVM Chain Registry
Supported chains for multi-chain SIWE authentication.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ChainInfo:
    chain_id: int
    name: str
    short_name: str
    currency: str
    rpc_url: str
    explorer_url: str
    is_testnet: bool = False


# ── Supported Chains ──────────────────────────────────────────────────

SUPPORTED_CHAINS: dict[int, ChainInfo] = {
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
}

DEFAULT_CHAIN_ID = 1


def get_chain(chain_id: int) -> ChainInfo | None:
    return SUPPORTED_CHAINS.get(chain_id)


def is_supported_chain(chain_id: int) -> bool:
    return chain_id in SUPPORTED_CHAINS


def get_supported_chain_ids() -> list[int]:
    return list(SUPPORTED_CHAINS.keys())


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
        for c in SUPPORTED_CHAINS.values()
    ]
