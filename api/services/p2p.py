"""
REFINET Cloud — P2P Peer Discovery & Communication Service
Wallet-based peer networking layer:
  - Peer presence tracking (online/offline/away)
  - Gossip-style peer discovery across chains
  - Peer-to-peer message relay via WebSocket
  - Typing indicators and presence broadcast
  - DHT-style routing for wallet address lookups
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("refinet.p2p")

PRESENCE_TIMEOUT_SECONDS = 120  # Mark offline after 2 minutes without heartbeat
GOSSIP_MAX_PEERS = 20           # Max peers to return in gossip response


# ── Presence States ──────────────────────────────────────────────────

class PresenceStatus(str, Enum):
    ONLINE = "online"
    AWAY = "away"
    OFFLINE = "offline"


# ── Peer Record ──────────────────────────────────────────────────────

@dataclass
class Peer:
    user_id: str
    eth_address: str
    chain_id: int
    pseudo_ipv6: str
    subnet: str
    display_name: Optional[str] = None
    ens_name: Optional[str] = None
    status: PresenceStatus = PresenceStatus.ONLINE
    last_heartbeat: float = field(default_factory=time.monotonic)
    connected_at: float = field(default_factory=time.monotonic)
    ws_conn_id: Optional[str] = None  # WebSocket connection for direct relay

    @property
    def is_alive(self) -> bool:
        return (time.monotonic() - self.last_heartbeat) < PRESENCE_TIMEOUT_SECONDS

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "eth_address": self.eth_address,
            "chain_id": self.chain_id,
            "pseudo_ipv6": self.pseudo_ipv6,
            "subnet": self.subnet,
            "display_name": self.display_name,
            "ens_name": self.ens_name,
            "status": self.status.value if self.is_alive else PresenceStatus.OFFLINE.value,
            "connected_at": datetime.fromtimestamp(
                self.connected_at, tz=timezone.utc
            ).isoformat() if self.connected_at else None,
        }


# ── P2P Network Manager ─────────────────────────────────────────────

class P2PNetwork:
    """
    In-process P2P network manager.
    Tracks online peers, handles presence, and relays messages.
    """

    _instance: Optional["P2PNetwork"] = None

    def __init__(self):
        self._peers: dict[str, Peer] = {}          # user_id → Peer
        self._address_index: dict[str, str] = {}    # eth_address → user_id
        self._ip_index: dict[str, str] = {}         # pseudo_ipv6 → user_id
        self._chain_peers: dict[int, set[str]] = {} # chain_id → set[user_id]
        self._typing: dict[str, dict] = {}           # conversation_id → {user_id: timestamp}

    @classmethod
    def get(cls) -> "P2PNetwork":
        if cls._instance is None:
            cls._instance = P2PNetwork()
        return cls._instance

    # ── Peer Registration ────────────────────────────────────────

    def register_peer(
        self,
        user_id: str,
        eth_address: str,
        chain_id: int,
        pseudo_ipv6: str,
        subnet: str,
        display_name: Optional[str] = None,
        ens_name: Optional[str] = None,
        ws_conn_id: Optional[str] = None,
    ) -> Peer:
        """Register or update a peer in the network."""
        existing = self._peers.get(user_id)
        if existing:
            # Clean stale index entries before updating
            if existing.eth_address.lower() != eth_address.lower():
                self._address_index.pop(existing.eth_address.lower(), None)
            if existing.pseudo_ipv6 != pseudo_ipv6:
                self._ip_index.pop(existing.pseudo_ipv6, None)
            existing.eth_address = eth_address
            existing.chain_id = chain_id
            existing.pseudo_ipv6 = pseudo_ipv6
            existing.subnet = subnet
            existing.status = PresenceStatus.ONLINE
            existing.last_heartbeat = time.monotonic()
            existing.ws_conn_id = ws_conn_id
            if display_name:
                existing.display_name = display_name
            if ens_name:
                existing.ens_name = ens_name
            peer = existing
        else:
            peer = Peer(
                user_id=user_id,
                eth_address=eth_address,
                chain_id=chain_id,
                pseudo_ipv6=pseudo_ipv6,
                subnet=subnet,
                display_name=display_name,
                ens_name=ens_name,
                ws_conn_id=ws_conn_id,
            )
            self._peers[user_id] = peer

        # Update indexes
        self._address_index[eth_address.lower()] = user_id
        self._ip_index[pseudo_ipv6] = user_id
        if chain_id not in self._chain_peers:
            self._chain_peers[chain_id] = set()
        self._chain_peers[chain_id].add(user_id)

        logger.info(f"Peer registered: {eth_address[:10]}... on chain {chain_id}")
        return peer

    def unregister_peer(self, user_id: str) -> None:
        """Remove a peer from the network."""
        peer = self._peers.pop(user_id, None)
        if peer:
            self._address_index.pop(peer.eth_address.lower(), None)
            self._ip_index.pop(peer.pseudo_ipv6, None)
            for chain_set in self._chain_peers.values():
                chain_set.discard(user_id)
            logger.info(f"Peer unregistered: {peer.eth_address[:10]}...")

    # ── Presence ─────────────────────────────────────────────────

    def heartbeat(self, user_id: str) -> bool:
        """Update last heartbeat for a peer. Returns True if peer exists."""
        peer = self._peers.get(user_id)
        if peer:
            peer.last_heartbeat = time.monotonic()
            if peer.status == PresenceStatus.OFFLINE:
                peer.status = PresenceStatus.ONLINE
            return True
        return False

    def set_status(self, user_id: str, status: PresenceStatus) -> bool:
        """Set a peer's presence status."""
        peer = self._peers.get(user_id)
        if peer:
            peer.status = status
            peer.last_heartbeat = time.monotonic()
            return True
        return False

    def get_presence(self, user_id: str) -> Optional[dict]:
        """Get presence info for a specific peer."""
        peer = self._peers.get(user_id)
        if not peer:
            return None
        return {
            "user_id": user_id,
            "eth_address": peer.eth_address,
            "status": peer.status.value if peer.is_alive else PresenceStatus.OFFLINE.value,
            "display_name": peer.display_name,
        }

    def get_online_peers(self) -> list[Peer]:
        """Get all currently online peers."""
        return [p for p in self._peers.values() if p.is_alive]

    def cleanup_stale_peers(self) -> int:
        """Mark stale peers as offline. Returns count of peers marked offline."""
        count = 0
        for peer in self._peers.values():
            if not peer.is_alive and peer.status != PresenceStatus.OFFLINE:
                peer.status = PresenceStatus.OFFLINE
                count += 1
        return count

    # ── Peer Lookup ──────────────────────────────────────────────

    def find_by_address(self, eth_address: str) -> Optional[Peer]:
        """Find a peer by wallet address."""
        user_id = self._address_index.get(eth_address.lower())
        return self._peers.get(user_id) if user_id else None

    def find_by_ip(self, pseudo_ipv6: str) -> Optional[Peer]:
        """Find a peer by pseudo-IPv6 address."""
        user_id = self._ip_index.get(pseudo_ipv6)
        return self._peers.get(user_id) if user_id else None

    def find_by_user_id(self, user_id: str) -> Optional[Peer]:
        return self._peers.get(user_id)

    # ── Chain Peers ──────────────────────────────────────────────

    def get_chain_peers(self, chain_id: int) -> list[Peer]:
        """Get all online peers on a specific chain."""
        user_ids = self._chain_peers.get(chain_id, set())
        return [self._peers[uid] for uid in user_ids if uid in self._peers and self._peers[uid].is_alive]

    def get_chain_peer_count(self) -> dict[int, int]:
        """Get online peer count per chain."""
        result = {}
        for chain_id, user_ids in self._chain_peers.items():
            count = sum(1 for uid in user_ids if uid in self._peers and self._peers[uid].is_alive)
            if count > 0:
                result[chain_id] = count
        return result

    # ── Gossip Discovery ─────────────────────────────────────────

    def gossip_peers(self, requesting_user_id: str, chain_id: Optional[int] = None) -> list[dict]:
        """
        Return a list of known peers for gossip-style discovery.
        Excludes the requesting peer. Optionally filters by chain.
        """
        if chain_id is not None:
            candidates = self.get_chain_peers(chain_id)
        else:
            candidates = self.get_online_peers()

        peers = [p.to_dict() for p in candidates if p.user_id != requesting_user_id]
        return peers[:GOSSIP_MAX_PEERS]

    # ── Typing Indicators ────────────────────────────────────────

    def set_typing(self, conversation_id: str, user_id: str) -> None:
        """Record that a user is typing in a conversation."""
        if conversation_id not in self._typing:
            self._typing[conversation_id] = {}
        self._typing[conversation_id][user_id] = time.monotonic()

    def get_typing(self, conversation_id: str, exclude_user_id: Optional[str] = None) -> list[str]:
        """Get list of user_ids currently typing in a conversation (within last 5s)."""
        entries = self._typing.get(conversation_id, {})
        now = time.monotonic()
        typing = []
        expired = []
        for uid, ts in entries.items():
            if now - ts < 5.0:
                if uid != exclude_user_id:
                    typing.append(uid)
            else:
                expired.append(uid)
        for uid in expired:
            entries.pop(uid, None)
        if not entries and conversation_id in self._typing:
            del self._typing[conversation_id]
        return typing

    # ── Network Stats ────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get network statistics."""
        total = len(self._peers)
        online = len(self.get_online_peers())
        return {
            "total_peers": total,
            "online_peers": online,
            "offline_peers": total - online,
            "chain_distribution": self.get_chain_peer_count(),
            "address_index_size": len(self._address_index),
            "ip_index_size": len(self._ip_index),
        }
