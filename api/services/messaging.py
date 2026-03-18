"""
REFINET Cloud — Wallet-to-Wallet Messaging Service
XMTP-compatible messaging engine:
  - DM and group conversations between wallet addresses
  - Conversation management (create, list, read state)
  - Message send/receive with threading
  - Email alias routing for SMTP bridge compatibility
  - Real-time delivery via EventBus → WebSocket
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session
from web3 import Web3

from api.models.public import (
    User, Conversation, ConversationParticipant, Message, WalletIdentity, EmailAlias,
)

logger = logging.getLogger("refinet.messaging")

MAX_MESSAGE_LENGTH = 10_000
MAX_GROUP_SIZE = 50


# ── Conversation Management ──────────────────────────────────────────

def create_dm(
    db: Session,
    sender_id: str,
    sender_address: str,
    recipient_address: str,
) -> dict:
    """
    Create or find an existing DM conversation between two wallets.
    Returns {"conversation": Conversation, "created": bool}.
    """
    sender_addr = Web3.to_checksum_address(sender_address)
    recipient_addr = Web3.to_checksum_address(recipient_address)

    if sender_addr == recipient_addr:
        raise ValueError("Cannot create DM with yourself")

    # Look up recipient user
    recipient = db.query(User).filter(User.eth_address == recipient_addr).first()
    if not recipient:
        raise ValueError(f"Recipient {recipient_addr} is not registered")

    if not recipient.is_active:
        raise ValueError("Recipient account is inactive")

    # Check messaging permissions
    _check_messaging_permission(db, recipient.id, sender_addr)

    # Find existing DM between these two users
    existing = _find_existing_dm(db, sender_id, recipient.id)
    if existing:
        return {"conversation": existing, "created": False}

    # Create new conversation
    convo = Conversation(
        created_by=sender_id,
        is_group=False,
    )
    db.add(convo)
    db.flush()

    # Add participants
    sender_display = _get_display_name(db, sender_id, sender_addr)
    recipient_display = _get_display_name(db, recipient.id, recipient_addr)

    db.add(ConversationParticipant(
        conversation_id=convo.id,
        user_id=sender_id,
        eth_address=sender_addr,
        display_name=sender_display,
        role="owner",
    ))
    db.add(ConversationParticipant(
        conversation_id=convo.id,
        user_id=recipient.id,
        eth_address=recipient_addr,
        display_name=recipient_display,
        role="member",
    ))
    db.flush()

    return {"conversation": convo, "created": True}


def create_group(
    db: Session,
    creator_id: str,
    creator_address: str,
    title: str,
    participant_addresses: list[str],
) -> Conversation:
    """Create a group conversation with multiple participants."""
    creator_addr = Web3.to_checksum_address(creator_address)

    if len(participant_addresses) > MAX_GROUP_SIZE:
        raise ValueError(f"Group cannot exceed {MAX_GROUP_SIZE} participants")

    # Deduplicate and validate
    all_addresses = list({Web3.to_checksum_address(a) for a in participant_addresses})
    if creator_addr not in all_addresses:
        all_addresses.append(creator_addr)

    if len(all_addresses) < 2:
        raise ValueError("Group requires at least 2 participants")

    # Look up all participants and check permissions
    participants = []
    for addr in all_addresses:
        user = db.query(User).filter(User.eth_address == addr).first()
        if not user:
            raise ValueError(f"Address {addr} is not registered")
        if not user.is_active:
            raise ValueError(f"User {addr} is inactive")
        # Check group messaging permission (skip for creator)
        if user.id != creator_id:
            _check_group_permission(db, user.id, creator_addr)
        participants.append((user, addr))

    convo = Conversation(
        created_by=creator_id,
        title=title,
        is_group=True,
    )
    db.add(convo)
    db.flush()

    for user, addr in participants:
        role = "owner" if user.id == creator_id else "member"
        display = _get_display_name(db, user.id, addr)
        db.add(ConversationParticipant(
            conversation_id=convo.id,
            user_id=user.id,
            eth_address=addr,
            display_name=display,
            role=role,
        ))

    db.flush()
    return convo


def get_conversations(db: Session, user_id: str) -> list[dict]:
    """
    List all conversations for a user, ordered by last message time.
    Uses bulk queries instead of N+1 loops.
    """
    # 1. Get user's participations (1 query)
    my_parts = db.query(ConversationParticipant).filter(
        ConversationParticipant.user_id == user_id,
    ).all()

    if not my_parts:
        return []

    convo_ids = [p.conversation_id for p in my_parts]
    my_parts_map = {p.conversation_id: p for p in my_parts}

    # 2. Fetch all conversations in bulk (1 query)
    convos = db.query(Conversation).filter(
        Conversation.id.in_(convo_ids),
    ).all()
    convo_map = {c.id: c for c in convos}

    # 3. Fetch all other participants in bulk (1 query)
    all_others = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id.in_(convo_ids),
        ConversationParticipant.user_id != user_id,
    ).all()
    others_map: dict[str, list] = {}
    for o in all_others:
        others_map.setdefault(o.conversation_id, []).append(o)

    # 4. Compute unread counts in bulk
    # For never-read conversations: count all non-self messages
    # For read conversations: count messages after last_read_at
    # Both done in at most 2 queries (no per-conversation loop)
    unread_map: dict[str, int] = {}

    never_read_ids = [cid for cid, p in my_parts_map.items() if not p.last_read_at]
    read_convo_ids = [cid for cid, p in my_parts_map.items() if p.last_read_at]

    # Batch 1: never-read conversations — all other-party messages are unread
    if never_read_ids:
        rows = db.query(
            Message.conversation_id,
            sa_func.count(Message.id),
        ).filter(
            Message.conversation_id.in_(never_read_ids),
            Message.sender_id != user_id,
            Message.is_deleted == False,  # noqa: E712
        ).group_by(Message.conversation_id).all()
        for cid, cnt in rows:
            unread_map[cid] = cnt

    # Batch 2: read conversations — use OR filters to count in a single query
    if read_convo_ids:
        from sqlalchemy import and_, or_
        filters = [
            and_(
                Message.conversation_id == cid,
                Message.created_at > my_parts_map[cid].last_read_at,
            )
            for cid in read_convo_ids
        ]
        rows = db.query(
            Message.conversation_id,
            sa_func.count(Message.id),
        ).filter(
            or_(*filters),
            Message.sender_id != user_id,
            Message.is_deleted == False,  # noqa: E712
        ).group_by(Message.conversation_id).all()
        for cid, cnt in rows:
            unread_map[cid] = cnt

    # Fill zeros for conversations with no unread messages
    for cid in convo_ids:
        unread_map.setdefault(cid, 0)

    # 5. Assemble results
    results = []
    for cid in convo_ids:
        convo = convo_map.get(cid)
        if not convo:
            continue
        p = my_parts_map[cid]
        results.append({
            "conversation": convo,
            "participants": others_map.get(cid, []),
            "unread_count": unread_map.get(cid, 0),
            "is_muted": p.is_muted,
            "my_role": p.role,
        })

    results.sort(
        key=lambda x: x["conversation"].last_message_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return results


def get_conversation(db: Session, conversation_id: str, user_id: str) -> Optional[dict]:
    """Get a single conversation with participant info. Returns None if user is not a participant."""
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id,
    ).first()

    if not participant:
        return None

    convo = db.query(Conversation).filter(
        Conversation.id == conversation_id,
    ).first()

    others = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id != user_id,
    ).all()

    return {
        "conversation": convo,
        "participants": others,
        "my_role": participant.role,
    }


# ── Message Operations ───────────────────────────────────────────────

def send_message(
    db: Session,
    conversation_id: str,
    sender_id: str,
    sender_address: str,
    content: str,
    content_type: str = "text",
    reply_to_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Message:
    """Send a message in a conversation."""
    # Validate participation
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == sender_id,
    ).first()

    if not participant:
        raise ValueError("You are not a participant in this conversation")

    # Validate content
    if not content or not content.strip():
        raise ValueError("Message content cannot be empty")
    if len(content) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message exceeds {MAX_MESSAGE_LENGTH} character limit")

    # Validate reply target
    if reply_to_id:
        reply_target = db.query(Message).filter(
            Message.id == reply_to_id,
            Message.conversation_id == conversation_id,
        ).first()
        if not reply_target:
            raise ValueError("Reply target message not found in this conversation")

    msg = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        sender_address=Web3.to_checksum_address(sender_address),
        content=content.strip(),
        content_type=content_type,
        reply_to_id=reply_to_id,
        extra_data=json.dumps(metadata) if metadata else None,
    )
    db.add(msg)

    # Update conversation metadata
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if convo:
        convo.last_message_at = datetime.now(timezone.utc)
        convo.last_message_preview = content.strip()[:100]

    # Auto-mark as read for sender
    participant.last_read_at = datetime.now(timezone.utc)

    db.flush()
    return msg


def get_messages(
    db: Session,
    conversation_id: str,
    user_id: str,
    limit: int = 50,
    before_id: Optional[str] = None,
) -> tuple[list[Message], bool]:
    """Get messages in a conversation with cursor-based pagination. Returns (messages, has_more)."""
    # Verify participation
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id,
    ).first()

    if not participant:
        raise ValueError("You are not a participant in this conversation")

    query = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.is_deleted == False,  # noqa: E712
    )

    if before_id:
        cursor_msg = db.query(Message).filter(Message.id == before_id).first()
        if cursor_msg:
            query = query.filter(Message.created_at < cursor_msg.created_at)

    capped = min(limit, 100)
    # Fetch one extra to determine if there are more
    messages = query.order_by(Message.created_at.desc()).limit(capped + 1).all()
    has_more = len(messages) > capped
    if has_more:
        messages = messages[:capped]
    messages.reverse()  # Return in chronological order
    return messages, has_more


def mark_read(db: Session, conversation_id: str, user_id: str) -> None:
    """Mark all messages in a conversation as read for the user."""
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id,
    ).first()

    if participant:
        participant.last_read_at = datetime.now(timezone.utc)
        db.flush()


# ── Direct Message by Address ────────────────────────────────────────

def send_dm(
    db: Session,
    sender_id: str,
    sender_address: str,
    recipient_address: str,
    content: str,
    content_type: str = "text",
) -> dict:
    """
    Send a DM to a wallet address. Auto-creates conversation if needed.
    Returns {"message": Message, "conversation": Conversation, "created": bool}.
    """
    result = create_dm(db, sender_id, sender_address, recipient_address)
    convo = result["conversation"]
    created = result["created"]

    msg = send_message(
        db, convo.id, sender_id, sender_address, content, content_type,
    )

    return {
        "message": msg,
        "conversation": convo,
        "created": created,
    }


# ── Email Alias Routing ──────────────────────────────────────────────

def resolve_recipient(db: Session, recipient: str) -> Optional[str]:
    """
    Resolve a recipient identifier to a checksummed Ethereum address.
    Supports: Ethereum address, email alias, ENS name.
    """
    # Direct address
    if recipient.startswith("0x") and len(recipient) == 42:
        try:
            return Web3.to_checksum_address(recipient)
        except Exception:
            return None

    # Email alias (e.g. 742d35cc@cifi.global)
    if "@" in recipient:
        alias = db.query(EmailAlias).filter(
            (EmailAlias.email_alias == recipient.lower()) |
            (EmailAlias.custom_alias == recipient.lower()) |
            (EmailAlias.ens_alias == recipient.lower()),
            EmailAlias.is_active == True,  # noqa: E712
        ).first()
        if alias:
            return Web3.to_checksum_address(alias.eth_address)

        # Also check WalletIdentity email_alias field
        identity = db.query(WalletIdentity).filter(
            WalletIdentity.email_alias == recipient.lower(),
        ).first()
        if identity:
            return Web3.to_checksum_address(identity.eth_address)
        return None

    # ENS name (e.g. alice.eth)
    if recipient.endswith(".eth"):
        from api.auth.ens import resolve_ens_name
        return resolve_ens_name(recipient)

    return None


# ── Helpers ──────────────────────────────────────────────────────────

def _find_existing_dm(db: Session, user_a_id: str, user_b_id: str) -> Optional[Conversation]:
    """Find an existing DM between two users. Single JOIN query."""
    a_convos = db.query(ConversationParticipant.conversation_id).filter(
        ConversationParticipant.user_id == user_a_id,
    ).subquery()

    return db.query(Conversation).join(
        ConversationParticipant,
        Conversation.id == ConversationParticipant.conversation_id,
    ).filter(
        ConversationParticipant.user_id == user_b_id,
        ConversationParticipant.conversation_id.in_(a_convos),
        Conversation.is_group == False,  # noqa: E712
    ).first()


def _check_group_permission(db: Session, user_id: str, inviter_address: str) -> None:
    """Check if a user allows being added to groups."""
    identity = db.query(WalletIdentity).filter(
        WalletIdentity.user_id == user_id,
        WalletIdentity.is_primary == True,  # noqa: E712
    ).first()

    if not identity or not identity.messaging_permissions:
        return

    try:
        perms = json.loads(identity.messaging_permissions)
    except (json.JSONDecodeError, TypeError):
        return

    if not perms.get("allow_group", True):
        logger.warning(f"Group invite blocked: {inviter_address} -> {identity.eth_address} (groups disabled)")
        raise ValueError(f"User {identity.eth_address} has disabled group invites")

    blocklist = perms.get("blocklist", [])
    if inviter_address.lower() in [b.lower() for b in blocklist]:
        logger.warning(f"Group invite blocked: {inviter_address} -> {identity.eth_address} (blocklisted)")
        raise ValueError(f"User {identity.eth_address} has blocked you")


def _check_messaging_permission(db: Session, recipient_user_id: str, sender_address: str) -> None:
    """Check if the recipient allows messages from this sender."""
    identity = db.query(WalletIdentity).filter(
        WalletIdentity.user_id == recipient_user_id,
        WalletIdentity.is_primary == True,  # noqa: E712
    ).first()

    if not identity or not identity.messaging_permissions:
        return  # No restrictions

    try:
        perms = json.loads(identity.messaging_permissions)
    except (json.JSONDecodeError, TypeError):
        return

    if not perms.get("allow_dm", True):
        raise ValueError("Recipient has disabled direct messages")

    blocklist = perms.get("blocklist", [])
    if sender_address.lower() in [b.lower() for b in blocklist]:
        raise ValueError("You are blocked by this recipient")


def _get_display_name(db: Session, user_id: str, eth_address: str) -> str:
    """Get the best display name for a user."""
    identity = db.query(WalletIdentity).filter(
        WalletIdentity.user_id == user_id,
        WalletIdentity.is_primary == True,  # noqa: E712
    ).first()

    if identity:
        if identity.ens_name:
            return identity.ens_name
        if identity.display_name:
            return identity.display_name

    return f"{eth_address[:6]}...{eth_address[-4:]}"
