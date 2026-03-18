"""
REFINET Cloud — Network Identity Service
Wallet-based network addressing layer:
  - Deterministic pseudo-IPv6 from wallet (fd00::/8 ULA)
  - Per-chain subnet allocation (chain_id → /48 prefix)
  - Peer routing table for wallet discovery
  - Reverse lookup: pseudo-IP → wallet address
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from api.auth.chains import get_chain, SUPPORTED_CHAINS


# ── Network Identity ──────────────────────────────────────────────────

@dataclass(frozen=True)
class NetworkAddress:
    """Full network identity for a wallet on a specific chain."""
    eth_address: str
    chain_id: int
    pseudo_ipv6: str            # Full /128 address
    subnet_prefix: str          # Chain-specific /48 prefix
    interface_id: str           # Wallet-specific /80 suffix
    cidr: str                   # Full CIDR notation



def chain_to_subnet_prefix(chain_id: int) -> str:
    """
    Map a chain ID to a deterministic /48 subnet prefix.
    Uses SHA-256 of the chain_id to produce 5 bytes placed after the fd prefix.

    Format: fdXX:XXXX:XXXX::/48
    """
    h = hashlib.sha256(chain_id.to_bytes(4, "big")).digest()
    # fd prefix byte + 5 bytes from hash = 6 bytes = 3 groups = /48
    prefix_bytes = b"\xfd" + h[:5]
    groups = []
    for i in range(0, 6, 2):
        groups.append(f"{prefix_bytes[i]:02x}{prefix_bytes[i + 1]:02x}")
    return ":".join(groups)


def wallet_to_interface_id(eth_address: str) -> str:
    """
    Derive a /80 interface identifier from a wallet address.
    Uses the last 10 bytes of keccak256(address) — 5 groups.
    """
    addr_bytes = bytes.fromhex(eth_address.lower().replace("0x", ""))
    h = Web3.keccak(addr_bytes)
    iid_bytes = h[22:32]  # last 10 bytes
    groups = []
    for i in range(0, 10, 2):
        groups.append(f"{iid_bytes[i]:02x}{iid_bytes[i + 1]:02x}")
    return ":".join(groups)


def compute_network_address(eth_address: str, chain_id: int) -> NetworkAddress:
    """
    Compute the full network identity for a wallet on a given chain.

    Structure:
      fdXX:XXXX:XXXX : YYYY:YYYY : YYYY:YYYY:YYYY
      |-- subnet /48 --|-- interface id /80 ---------|
      |-- chain hash --|-- wallet hash --------------|

    This gives each chain its own subnet and each wallet a unique address
    within that subnet, enabling chain-aware peer routing.
    """
    checksummed = Web3.to_checksum_address(eth_address)
    subnet = chain_to_subnet_prefix(chain_id)
    iid = wallet_to_interface_id(checksummed)

    # Combine: subnet (3 groups) + interface (5 groups) = 8 groups = full IPv6
    full_ipv6 = f"{subnet}:{iid}"
    cidr = f"{full_ipv6}/128"

    return NetworkAddress(
        eth_address=checksummed,
        chain_id=chain_id,
        pseudo_ipv6=full_ipv6,
        subnet_prefix=f"{subnet}::/48",
        interface_id=iid,
        cidr=cidr,
    )


# ── Reverse Lookup Index ──────────────────────────────────────────────
# In-memory reverse index: pseudo_ipv6 → eth_address
# Populated as wallets authenticate; queryable for peer discovery.

_reverse_index: dict[str, str] = {}
_net_lock = threading.Lock()


def register_network_address(net_addr: NetworkAddress) -> None:
    """Register a wallet's network address in the reverse index."""
    with _net_lock:
        _reverse_index[net_addr.pseudo_ipv6] = net_addr.eth_address


def lookup_by_pseudo_ip(pseudo_ipv6: str) -> Optional[str]:
    """Reverse lookup: find the wallet address for a pseudo-IPv6."""
    return _reverse_index.get(pseudo_ipv6)


def get_reverse_index_size() -> int:
    return len(_reverse_index)


# ── Routing Table ─────────────────────────────────────────────────────
# Per-chain peer list for wallet discovery. Tracks which wallets are
# active on which chain subnets.

@dataclass
class PeerEntry:
    eth_address: str
    pseudo_ipv6: str
    chain_id: int
    chain_name: str
    subnet: str
    display_name: Optional[str] = None
    ens_name: Optional[str] = None


# chain_id → list of PeerEntry
_routing_table: dict[int, list[PeerEntry]] = {}


def register_peer(net_addr: NetworkAddress, display_name: Optional[str] = None, ens_name: Optional[str] = None) -> PeerEntry:
    """Register a wallet as an active peer on a chain."""
    chain = get_chain(net_addr.chain_id)
    peer = PeerEntry(
        eth_address=net_addr.eth_address,
        pseudo_ipv6=net_addr.pseudo_ipv6,
        chain_id=net_addr.chain_id,
        chain_name=chain.name if chain else f"Chain {net_addr.chain_id}",
        subnet=net_addr.subnet_prefix,
        display_name=display_name,
        ens_name=ens_name,
    )

    with _net_lock:
        if net_addr.chain_id not in _routing_table:
            _routing_table[net_addr.chain_id] = []

        # Deduplicate by address
        peers = _routing_table[net_addr.chain_id]
        for i, existing in enumerate(peers):
            if existing.eth_address == net_addr.eth_address:
                peers[i] = peer
                return peer

        peers.append(peer)
    return peer


def get_chain_peers(chain_id: int) -> list[PeerEntry]:
    """Get all registered peers on a chain."""
    return _routing_table.get(chain_id, [])


def get_all_peers() -> dict[int, list[PeerEntry]]:
    """Get the full routing table."""
    return dict(_routing_table)


def get_peer_count() -> dict[int, int]:
    """Get peer count per chain."""
    return {cid: len(peers) for cid, peers in _routing_table.items()}


# ── Chain Subnet Directory ────────────────────────────────────────────

def get_chain_subnets() -> list[dict]:
    """
    Get the subnet prefix for every supported chain.
    Useful for displaying the network topology.
    """
    subnets = []
    for chain_id, chain_info in SUPPORTED_CHAINS.items():
        prefix = chain_to_subnet_prefix(chain_id)
        peer_count = len(_routing_table.get(chain_id, []))
        subnets.append({
            "chain_id": chain_id,
            "chain_name": chain_info.name,
            "subnet_prefix": f"{prefix}::/48",
            "peer_count": peer_count,
        })
    return subnets
