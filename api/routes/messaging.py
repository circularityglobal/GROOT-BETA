"""
REFINET Cloud — Messaging Routes
Wallet-to-wallet messaging: DMs, groups, conversations, and email alias management.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.middleware.rate_limit import limiter
from api.models.public import User, ConversationParticipant
from api.services.messaging import (
    send_dm,
    send_message,
    create_group,
    get_conversations,
    get_conversation,
    get_messages,
    mark_read,
    resolve_recipient,
)
from api.services.email_bridge import (
    register_email_alias,
    set_custom_alias,
    resolve_email_to_address,
    resolve_address_to_emails,
    get_user_aliases,
)
from api.schemas.messaging import (
    SendDMRequest,
    SendMessageRequest,
    CreateGroupRequest,
    MessageResponse,
    ConversationResponse,
    ConversationListResponse,
    ConversationMessagesResponse,
    ParticipantResponse,
    SetCustomAliasRequest,
    EmailAliasResponse,
    EmailResolveRequest,
    EmailResolveResponse,
)

logger = logging.getLogger("refinet.messaging.routes")

router = APIRouter(prefix="/messages", tags=["messaging"])


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


def _message_to_response(msg) -> MessageResponse:
    metadata = None
    if msg.extra_data:
        try:
            metadata = json.loads(msg.extra_data)
        except (json.JSONDecodeError, TypeError):
            pass
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        sender_address=msg.sender_address,
        content=msg.content,
        content_type=msg.content_type,
        reply_to_id=msg.reply_to_id,
        metadata=metadata,
        is_edited=msg.is_edited,
        created_at=msg.created_at,
    )


def _publish_event(event: str, data: dict):
    """Fire-and-forget event publish to EventBus."""
    try:
        from api.services.event_bus import EventBus
        bus = EventBus.get()
        loop = asyncio.get_running_loop()
        loop.create_task(bus.publish(event, data))
    except (RuntimeError, Exception) as e:
        logger.warning(f"Failed to publish event {event}: {e}")


# ── Send DM ──────────────────────────────────────────────────────────

@router.post("/dm", response_model=MessageResponse)
@limiter.limit("30/minute")
def send_direct_message(
    req: SendDMRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Send a DM to a wallet. Recipient can be:
    - Ethereum address (0x...)
    - Email alias (742d35cc@cifi.global)
    - ENS name (alice.eth)
    Auto-creates conversation if this is the first message.
    """
    _, user = _get_current_user(request, db)

    if not user.eth_address:
        raise HTTPException(status_code=400, detail="Wallet address required to send messages")

    # Resolve recipient
    recipient_address = resolve_recipient(db, req.recipient)
    if not recipient_address:
        raise HTTPException(status_code=404, detail=f"Recipient '{req.recipient}' not found")

    try:
        result = send_dm(
            db, user.id, user.eth_address,
            recipient_address, req.content, req.content_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    msg = result["message"]
    convo = result["conversation"]

    # Publish event for real-time delivery
    _publish_event("messaging.dm.sent", {
        "conversation_id": convo.id,
        "message_id": msg.id,
        "sender_id": user.id,
        "sender_address": user.eth_address,
        "recipient_address": recipient_address,
        "content_preview": req.content[:100],
    })

    return _message_to_response(msg)


# ── Conversations ────────────────────────────────────────────────────

@router.get("/conversations", response_model=ConversationListResponse)
@limiter.limit("30/minute")
def list_conversations(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List all conversations for the current user."""
    _, user = _get_current_user(request, db)

    results = get_conversations(db, user.id)

    conversations = []
    for r in results:
        convo = r["conversation"]
        participants = [
            ParticipantResponse(
                user_id=p.user_id,
                eth_address=p.eth_address,
                display_name=p.display_name,
                role=p.role,
            )
            for p in r["participants"]
        ]
        conversations.append(ConversationResponse(
            id=convo.id,
            title=convo.title,
            is_group=convo.is_group,
            participants=participants,
            last_message_at=convo.last_message_at,
            last_message_preview=convo.last_message_preview,
            unread_count=r["unread_count"],
            my_role=r["my_role"],
            created_at=convo.created_at,
        ))

    return ConversationListResponse(
        conversations=conversations,
        total=len(conversations),
    )


@router.post("/conversations/group", response_model=ConversationResponse)
@limiter.limit("10/minute")
def create_group_conversation(
    req: CreateGroupRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create a group conversation."""
    _, user = _get_current_user(request, db)

    if not user.eth_address:
        raise HTTPException(status_code=400, detail="Wallet address required")

    # Resolve all participant addresses
    addresses = []
    for p in req.participants:
        addr = resolve_recipient(db, p)
        if not addr:
            raise HTTPException(status_code=404, detail=f"Participant '{p}' not found")
        addresses.append(addr)

    try:
        convo = create_group(db, user.id, user.eth_address, req.title, addresses)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    participants = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == convo.id,
    ).all()

    return ConversationResponse(
        id=convo.id,
        title=convo.title,
        is_group=convo.is_group,
        participants=[
            ParticipantResponse(
                user_id=p.user_id,
                eth_address=p.eth_address,
                display_name=p.display_name,
                role=p.role,
            )
            for p in participants
        ],
        my_role="owner",
        created_at=convo.created_at,
    )


# ── Conversation Messages ────────────────────────────────────────────

@router.get("/conversations/{conversation_id}", response_model=ConversationMessagesResponse)
@limiter.limit("60/minute")
def get_conversation_messages(
    conversation_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    limit: int = Query(default=50, ge=1, le=100),
    before: Optional[str] = Query(default=None),
):
    """Get messages in a conversation with cursor-based pagination."""
    _, user = _get_current_user(request, db)

    try:
        messages, has_more = get_messages(db, conversation_id, user.id, limit=limit, before_id=before)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        messages=[_message_to_response(m) for m in messages],
        has_more=has_more,
    )


@router.post("/conversations/{conversation_id}", response_model=MessageResponse)
@limiter.limit("60/minute")
def send_conversation_message(
    conversation_id: str,
    req: SendMessageRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Send a message in an existing conversation."""
    _, user = _get_current_user(request, db)

    if not user.eth_address:
        raise HTTPException(status_code=400, detail="Wallet address required")

    try:
        msg = send_message(
            db, conversation_id, user.id, user.eth_address,
            req.content, req.content_type, req.reply_to_id, req.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _publish_event("messaging.message.sent", {
        "conversation_id": conversation_id,
        "message_id": msg.id,
        "sender_id": user.id,
        "sender_address": user.eth_address,
        "content_preview": req.content[:100],
    })

    return _message_to_response(msg)


@router.post("/conversations/{conversation_id}/read")
@limiter.limit("60/minute")
def mark_conversation_read(
    conversation_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Mark all messages in a conversation as read."""
    _, user = _get_current_user(request, db)
    mark_read(db, conversation_id, user.id)
    return {"message": "Marked as read."}


# ── Email Aliases ────────────────────────────────────────────────────

@router.get("/email/aliases", response_model=list[EmailAliasResponse])
@limiter.limit("30/minute")
def list_email_aliases(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List all email aliases for the current user."""
    _, user = _get_current_user(request, db)

    if not user.eth_address:
        raise HTTPException(status_code=400, detail="Wallet address required")

    aliases = get_user_aliases(db, user.id)

    if not aliases:
        # Auto-register if not exists
        alias = register_email_alias(db, user.id, user.eth_address)
        aliases = [alias]

    return [
        EmailAliasResponse(
            auto=a.email_alias,
            custom=a.custom_alias,
            ens=a.ens_alias,
            eth_address=a.eth_address,
        )
        for a in aliases
    ]


@router.post("/email/alias", response_model=EmailAliasResponse)
@limiter.limit("10/minute")
def set_custom_email_alias(
    req: SetCustomAliasRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Set a custom email alias (e.g. alice@cifi.global)."""
    _, user = _get_current_user(request, db)

    if not user.eth_address:
        raise HTTPException(status_code=400, detail="Wallet address required")

    # Ensure base alias exists
    aliases = get_user_aliases(db, user.id)
    if not aliases:
        register_email_alias(db, user.id, user.eth_address)

    try:
        alias = set_custom_alias(db, user.id, req.alias)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return EmailAliasResponse(
        auto=alias.email_alias,
        custom=alias.custom_alias,
        ens=alias.ens_alias,
        eth_address=alias.eth_address,
    )


@router.post("/email/resolve", response_model=EmailResolveResponse)
@limiter.limit("30/minute")
def resolve_email(
    req: EmailResolveRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Resolve an email alias to a wallet address. Public endpoint."""
    address = resolve_email_to_address(db, req.email)
    return EmailResolveResponse(
        email=req.email,
        eth_address=address,
        found=address is not None,
    )
