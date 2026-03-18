"""
REFINET Cloud — P2P Network & SMTP Bridge Routes
Peer discovery, presence, gossip, typing indicators, and SMTP bridge management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.network_identity import compute_network_address
from api.models.public import User
from api.services.p2p import P2PNetwork, PresenceStatus
from api.services.smtp_bridge import is_smtp_running
from api.config import get_settings
from api.schemas.p2p import (
    PeerInfoResponse,
    PresenceUpdateRequest,
    PresenceResponse,
    OnlinePeersResponse,
    GossipResponse,
    TypingRequest,
    TypingResponse,
    P2PStatsResponse,
    SMTPStatusResponse,
    SendEmailRequest,
    SendEmailResponse,
)

logger = logging.getLogger("refinet.p2p.routes")

router = APIRouter(prefix="/p2p", tags=["p2p"])


# ── Helpers ──────────────────────────────────────────────────────────

def _get_current_user(request: Request, db: Session) -> tuple[dict, User]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    try:
        payload = decode_access_token(auth_header[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return payload, user


def _peer_to_response(peer) -> PeerInfoResponse:
    d = peer.to_dict()
    return PeerInfoResponse(**d)


# ── Peer Registration (auto on connect) ──────────────────────────────

@router.post("/connect", response_model=PeerInfoResponse)
def peer_connect(
    request: Request,
    db: Session = Depends(public_db_dependency),
    chain_id: int = Query(default=1, ge=1),
):
    """
    Register as a peer on the P2P network.
    Call this on app startup or when switching chains.
    """
    _, user = _get_current_user(request, db)
    if not user.eth_address:
        raise HTTPException(status_code=400, detail="Wallet address required")

    net_addr = compute_network_address(user.eth_address, chain_id)
    network = P2PNetwork.get()

    # Get display name from identity
    from api.auth.wallet_identity import get_primary_identity
    identity = get_primary_identity(db, user.id)
    display_name = identity.display_name if identity else None
    ens_name = identity.ens_name if identity else None

    peer = network.register_peer(
        user_id=user.id,
        eth_address=user.eth_address,
        chain_id=chain_id,
        pseudo_ipv6=net_addr.pseudo_ipv6,
        subnet=net_addr.subnet_prefix,
        display_name=display_name,
        ens_name=ens_name,
    )

    return _peer_to_response(peer)


@router.post("/disconnect")
def peer_disconnect(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Unregister from the P2P network."""
    _, user = _get_current_user(request, db)
    network = P2PNetwork.get()
    network.unregister_peer(user.id)
    return {"message": "Disconnected from P2P network."}


# ── Presence ─────────────────────────────────────────────────────────

@router.post("/heartbeat")
def heartbeat(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Send a heartbeat to maintain online presence. Call every 60s."""
    _, user = _get_current_user(request, db)
    network = P2PNetwork.get()
    if not network.heartbeat(user.id):
        raise HTTPException(status_code=404, detail="Not connected. Call POST /p2p/connect first.")
    return {"status": "ok"}


@router.put("/presence", response_model=PresenceResponse)
def update_presence(
    req: PresenceUpdateRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Update your presence status (online/away/offline)."""
    _, user = _get_current_user(request, db)
    network = P2PNetwork.get()

    try:
        status = PresenceStatus(req.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not network.set_status(user.id, status):
        raise HTTPException(status_code=404, detail="Not connected")

    presence = network.get_presence(user.id)
    return PresenceResponse(**presence)


@router.get("/presence/{eth_address}", response_model=PresenceResponse)
def get_peer_presence(
    eth_address: str,
    db: Session = Depends(public_db_dependency),
):
    """Get presence status for a specific wallet address."""
    network = P2PNetwork.get()
    peer = network.find_by_address(eth_address)
    if not peer:
        return PresenceResponse(
            user_id="",
            eth_address=eth_address,
            status="offline",
        )
    return PresenceResponse(
        user_id=peer.user_id,
        eth_address=peer.eth_address,
        status=peer.status.value if peer.is_alive else "offline",
        display_name=peer.display_name,
    )


# ── Peer Discovery (Gossip) ─────────────────────────────────────────

@router.get("/peers", response_model=OnlinePeersResponse)
def list_online_peers(
    request: Request,
    db: Session = Depends(public_db_dependency),
    chain_id: Optional[int] = Query(default=None),
):
    """List all online peers. Optionally filter by chain."""
    _, user = _get_current_user(request, db)
    network = P2PNetwork.get()

    if chain_id is not None:
        peers = network.get_chain_peers(chain_id)
    else:
        peers = network.get_online_peers()

    return OnlinePeersResponse(
        peers=[_peer_to_response(p) for p in peers],
        total=len(peers),
    )


@router.get("/gossip", response_model=GossipResponse)
def gossip_discover(
    request: Request,
    db: Session = Depends(public_db_dependency),
    chain_id: Optional[int] = Query(default=None),
):
    """
    Gossip-style peer discovery. Returns known peers for the requesting wallet.
    Use this to build a local peer table for direct communication.
    """
    _, user = _get_current_user(request, db)
    network = P2PNetwork.get()

    peer_dicts = network.gossip_peers(user.id, chain_id=chain_id)
    my_peer = network.find_by_user_id(user.id)

    return GossipResponse(
        peers=[PeerInfoResponse(**p) for p in peer_dicts],
        your_peer=_peer_to_response(my_peer) if my_peer else None,
    )


# ── Typing Indicators ───────────────────────────────────────────────

@router.post("/typing", response_model=TypingResponse)
def send_typing(
    req: TypingRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Signal that you're typing in a conversation."""
    _, user = _get_current_user(request, db)
    network = P2PNetwork.get()
    network.set_typing(req.conversation_id, user.id)

    # Publish typing event
    try:
        from api.services.event_bus import EventBus
        bus = EventBus.get()
        loop = asyncio.get_running_loop()
        loop.create_task(bus.publish("messaging.typing", {
            "conversation_id": req.conversation_id,
            "user_id": user.id,
            "eth_address": user.eth_address,
        }))
    except (RuntimeError, Exception):
        pass

    typing_users = network.get_typing(req.conversation_id, exclude_user_id=user.id)
    return TypingResponse(
        conversation_id=req.conversation_id,
        typing_users=typing_users,
    )


@router.get("/typing/{conversation_id}", response_model=TypingResponse)
def get_typing(
    conversation_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get who's currently typing in a conversation."""
    _, user = _get_current_user(request, db)
    network = P2PNetwork.get()
    typing_users = network.get_typing(conversation_id, exclude_user_id=user.id)
    return TypingResponse(
        conversation_id=conversation_id,
        typing_users=typing_users,
    )


# ── SMTP Bridge Status ──────────────────────────────────────────────

@router.get("/smtp/status", response_model=SMTPStatusResponse)
def smtp_status():
    """Check if the SMTP bridge is running."""
    settings = get_settings()
    smtp_port = int(getattr(settings, "smtp_port", 8025))
    smtp_host = getattr(settings, "smtp_host", "127.0.0.1")
    return SMTPStatusResponse(
        running=is_smtp_running(),
        host=smtp_host,
        port=smtp_port,
    )


@router.post("/smtp/send", response_model=SendEmailResponse)
def send_outbound_email(
    req: SendEmailRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Send an outbound email from your wallet's email alias.
    Uses the SMTP bridge to relay the message.
    Note: Requires external SMTP relay for actual delivery (future).
    Currently stores as outbound message in conversation system.
    """
    _, user = _get_current_user(request, db)
    if not user.eth_address:
        raise HTTPException(status_code=400, detail="Wallet address required")

    # Get sender's email alias
    from api.services.email_bridge import get_user_aliases, register_email_alias
    aliases = get_user_aliases(db, user.id)
    if not aliases:
        register_email_alias(db, user.id, user.eth_address)
        aliases = get_user_aliases(db, user.id)

    if not aliases:
        raise HTTPException(status_code=400, detail="No email alias available")

    from_alias = aliases[0].custom_alias or aliases[0].email_alias

    # Check if recipient is an internal wallet alias
    from api.services.messaging import resolve_recipient, send_dm
    recipient_address = resolve_recipient(db, req.to_email)

    if recipient_address:
        # Internal delivery — route as DM
        content = f"Subject: {req.subject}\n---\n{req.body}" if req.subject else req.body
        try:
            result = send_dm(
                db, user.id, user.eth_address,
                recipient_address, content, "email",
            )
            return SendEmailResponse(
                sent=True,
                from_alias=from_alias,
                to_email=req.to_email,
                message=f"Delivered internally to wallet {recipient_address[:10]}...",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # External delivery — log for future SMTP relay
        logger.info(f"Outbound email queued: {from_alias} → {req.to_email}")
        return SendEmailResponse(
            sent=False,
            from_alias=from_alias,
            to_email=req.to_email,
            message="External email delivery not yet configured. Message queued.",
        )


# ── Network Stats ───────────────────────────────────────────────────

@router.get("/stats", response_model=P2PStatsResponse)
def network_stats():
    """Get P2P network statistics."""
    network = P2PNetwork.get()
    stats = network.get_stats()
    # Convert int keys to string for JSON
    chain_dist = {str(k): v for k, v in stats.get("chain_distribution", {}).items()}
    return P2PStatsResponse(
        total_peers=stats["total_peers"],
        online_peers=stats["online_peers"],
        offline_peers=stats["offline_peers"],
        chain_distribution=chain_dist,
        smtp_bridge_running=is_smtp_running(),
    )
