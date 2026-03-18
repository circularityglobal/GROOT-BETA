"""REFINET Cloud — P2P Network & SMTP Bridge Schemas"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Peer / Presence ──────────────────────────────────────────────────

class PeerInfoResponse(BaseModel):
    user_id: str
    eth_address: str
    chain_id: int
    pseudo_ipv6: str
    subnet: str
    display_name: Optional[str] = None
    ens_name: Optional[str] = None
    status: str = "online"
    connected_at: Optional[str] = None


class PresenceUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^(online|away|offline)$")


class PresenceResponse(BaseModel):
    user_id: str
    eth_address: str
    status: str
    display_name: Optional[str] = None


class OnlinePeersResponse(BaseModel):
    peers: list[PeerInfoResponse]
    total: int = 0


# ── Gossip Discovery ────────────────────────────────────────────────

class GossipRequest(BaseModel):
    chain_id: Optional[int] = None


class GossipResponse(BaseModel):
    peers: list[PeerInfoResponse]
    your_peer: Optional[PeerInfoResponse] = None


# ── Typing Indicators ───────────────────────────────────────────────

class TypingRequest(BaseModel):
    conversation_id: str


class TypingResponse(BaseModel):
    conversation_id: str
    typing_users: list[str]


# ── Network Stats ───────────────────────────────────────────────────

class P2PStatsResponse(BaseModel):
    total_peers: int = 0
    online_peers: int = 0
    offline_peers: int = 0
    chain_distribution: dict[str, int] = {}
    smtp_bridge_running: bool = False


# ── SMTP Bridge ─────────────────────────────────────────────────────

class SMTPStatusResponse(BaseModel):
    running: bool
    host: str
    port: int


class SendEmailRequest(BaseModel):
    """Send an outbound email from a wallet alias."""
    to_email: str = Field(..., min_length=3)
    subject: str = Field(default="", max_length=200)
    body: str = Field(..., min_length=1, max_length=50000)


class SendEmailResponse(BaseModel):
    sent: bool
    from_alias: str
    to_email: str
    message: str


class InboundEmailResponse(BaseModel):
    """Represents a received email in the inbox."""
    id: str
    from_email: str
    to_alias: str
    subject: str
    body_preview: str
    has_attachments: bool = False
    received_at: Optional[datetime] = None
