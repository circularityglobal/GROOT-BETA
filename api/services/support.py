"""
REFINET Cloud — Support / Help Desk Service
Customer support ticket management with XMTP-encrypted messaging.
Tickets are linked to wallet-to-wallet DM conversations for E2E encryption.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from api.models.public import (
    User, SupportTicket, TicketMessage, Conversation,
)

logger = logging.getLogger("refinet.support")

VALID_CATEGORIES = {"general", "bug", "billing", "security", "feature", "account"}
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_STATUSES = {"open", "in_progress", "waiting_on_user", "resolved", "closed"}


# ── Ticket Creation ─────────────────────────────────────────────────

def create_ticket(
    db: Session,
    user_id: str,
    subject: str,
    description: str,
    category: str = "general",
    priority: str = "normal",
    metadata: Optional[dict] = None,
) -> dict:
    """
    Create a support ticket and optionally link to a messaging conversation.
    Returns the created ticket as a dict.
    """
    if category not in VALID_CATEGORIES:
        category = "general"
    if priority not in VALID_PRIORITIES:
        priority = "normal"

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    # Assign ticket number (max existing + 1)
    max_num = db.query(sa_func.max(SupportTicket.ticket_number)).scalar()
    ticket_number = (max_num or 0) + 1

    # Try to create a linked messaging conversation with admin
    conversation_id = None
    is_encrypted = False
    try:
        conversation_id, is_encrypted = _create_support_conversation(
            db, user_id, user.eth_address, subject,
        )
    except Exception as e:
        logger.warning("Could not create support conversation: %s", e)

    ticket = SupportTicket(
        user_id=user_id,
        conversation_id=conversation_id,
        ticket_number=ticket_number,
        subject=subject.strip()[:200],
        description=description.strip()[:5000],
        category=category,
        priority=priority,
        is_encrypted=is_encrypted,
        extra_data=json.dumps(metadata) if metadata else None,
    )
    db.add(ticket)
    db.flush()

    # Add the initial description as the first message
    initial_msg = TicketMessage(
        ticket_id=ticket.id,
        author_id=user_id,
        message_type="reply",
        content=description.strip()[:5000],
        is_admin=False,
    )
    db.add(initial_msg)
    db.flush()

    # Publish event
    _publish_event("support.ticket.created", {
        "ticket_id": ticket.id,
        "ticket_number": ticket_number,
        "user_id": user_id,
        "subject": ticket.subject,
        "category": category,
        "priority": priority,
    })

    return _ticket_to_dict(ticket, user=user)


def _create_support_conversation(
    db: Session,
    user_id: str,
    user_address: str,
    subject: str,
) -> tuple:
    """
    Create a DM conversation between user and admin for support.
    Returns (conversation_id, is_encrypted).
    """
    # Find an admin user to link the conversation to
    admin = db.query(User).filter(
        User.role.in_(["admin", "master_admin"]),
        User.is_active == True,  # noqa: E712
    ).first()

    if not admin or not admin.eth_address:
        return None, False

    # Use the messaging service to create a DM
    from api.services.messaging import create_dm
    result = create_dm(
        db,
        sender_id=user_id,
        sender_address=user_address,
        recipient_address=admin.eth_address,
    )
    conv = result.get("conversation")
    if not conv:
        return None, False

    conv_id = conv.id if hasattr(conv, "id") else conv.get("id")

    # Check XMTP status
    is_encrypted = False
    try:
        from api.services.xmtp import is_xmtp_available
        is_encrypted = is_xmtp_available(db, user_id)
    except Exception:
        pass

    return conv_id, is_encrypted


# ── Ticket Queries ──────────────────────────────────────────────────

def list_user_tickets(
    db: Session,
    user_id: str,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List tickets for a specific user."""
    q = db.query(SupportTicket).filter(SupportTicket.user_id == user_id)
    if status and status in VALID_STATUSES:
        q = q.filter(SupportTicket.status == status)

    total = q.count()
    tickets = (
        q.order_by(SupportTicket.updated_at.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "tickets": [_ticket_to_dict(t) for t in tickets],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_all_tickets(
    db: Session,
    status: Optional[str] = None,
    category: Optional[str] = None,
    assigned_to: Optional[str] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Admin: list all tickets with filters."""
    q = db.query(SupportTicket)
    if status and status in VALID_STATUSES:
        q = q.filter(SupportTicket.status == status)
    if category and category in VALID_CATEGORIES:
        q = q.filter(SupportTicket.category == category)
    if assigned_to:
        q = q.filter(SupportTicket.assigned_to == assigned_to)
    if priority and priority in VALID_PRIORITIES:
        q = q.filter(SupportTicket.priority == priority)

    total = q.count()
    tickets = (
        q.order_by(SupportTicket.updated_at.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Batch-fetch user info
    user_ids = {t.user_id for t in tickets}
    if tickets and tickets[0].assigned_to:
        user_ids.add(tickets[0].assigned_to)
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return {
        "tickets": [_ticket_to_dict(t, user=users.get(t.user_id)) for t in tickets],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_ticket(
    db: Session,
    ticket_id: str,
    user_id: Optional[str] = None,
) -> Optional[dict]:
    """Get ticket detail with messages. If user_id provided, enforce ownership."""
    q = db.query(SupportTicket).filter(SupportTicket.id == ticket_id)
    if user_id:
        q = q.filter(SupportTicket.user_id == user_id)
    ticket = q.first()
    if not ticket:
        return None

    messages = (
        db.query(TicketMessage)
        .filter(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
        .all()
    )

    # Batch-fetch authors
    author_ids = {m.author_id for m in messages} | {ticket.user_id}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(author_ids)).all()}

    user = users.get(ticket.user_id)
    result = _ticket_to_dict(ticket, user=user)
    result["messages"] = [
        {
            "id": m.id,
            "author_id": m.author_id,
            "author_name": _display_name(users.get(m.author_id)),
            "message_type": m.message_type,
            "content": m.content,
            "is_admin": m.is_admin,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
    return result


# ── Ticket Actions ──────────────────────────────────────────────────

def add_message(
    db: Session,
    ticket_id: str,
    author_id: str,
    content: str,
    is_admin: bool = False,
    message_type: str = "reply",
) -> dict:
    """Add a reply or note to a ticket."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise ValueError("Ticket not found")

    # Non-admin can only reply to own tickets
    if not is_admin and ticket.user_id != author_id:
        raise ValueError("Not authorized")

    msg = TicketMessage(
        ticket_id=ticket_id,
        author_id=author_id,
        message_type=message_type,
        content=content.strip()[:5000],
        is_admin=is_admin,
    )
    db.add(msg)

    # Update ticket timestamp and status
    ticket.updated_at = datetime.now(timezone.utc)
    if is_admin and ticket.status == "open":
        ticket.status = "in_progress"
    elif not is_admin and ticket.status == "waiting_on_user":
        ticket.status = "in_progress"

    db.flush()

    _publish_event("support.ticket.replied", {
        "ticket_id": ticket_id,
        "ticket_number": ticket.ticket_number,
        "author_id": author_id,
        "is_admin": is_admin,
    })

    return {
        "id": msg.id,
        "ticket_id": ticket_id,
        "content": msg.content,
        "is_admin": is_admin,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def update_status(
    db: Session,
    ticket_id: str,
    admin_id: str,
    new_status: str,
) -> dict:
    """Admin: update ticket status."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise ValueError("Ticket not found")

    old_status = ticket.status
    ticket.status = new_status
    ticket.updated_at = datetime.now(timezone.utc)

    if new_status == "resolved":
        ticket.resolved_at = datetime.now(timezone.utc)

    # Add system message
    system_msg = TicketMessage(
        ticket_id=ticket_id,
        author_id=admin_id,
        message_type="system",
        content=f"Status changed from {old_status} to {new_status}",
        is_admin=True,
    )
    db.add(system_msg)
    db.flush()

    _publish_event("support.ticket.status_changed", {
        "ticket_id": ticket_id,
        "old_status": old_status,
        "new_status": new_status,
        "admin_id": admin_id,
    })

    return _ticket_to_dict(ticket)


def assign_ticket(
    db: Session,
    ticket_id: str,
    admin_id: str,
    assignee_id: str,
) -> dict:
    """Admin: assign ticket to an admin user."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise ValueError("Ticket not found")

    assignee = db.query(User).filter(User.id == assignee_id).first()
    if not assignee:
        raise ValueError("Assignee not found")

    ticket.assigned_to = assignee_id
    ticket.updated_at = datetime.now(timezone.utc)
    if ticket.status == "open":
        ticket.status = "in_progress"

    # Add system message
    system_msg = TicketMessage(
        ticket_id=ticket_id,
        author_id=admin_id,
        message_type="system",
        content=f"Assigned to {_display_name(assignee)}",
        is_admin=True,
    )
    db.add(system_msg)
    db.flush()

    return _ticket_to_dict(ticket)


def close_ticket(
    db: Session,
    ticket_id: str,
    user_id: str,
) -> dict:
    """User or admin closes a ticket."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise ValueError("Ticket not found")

    # User can only close own tickets
    user = db.query(User).filter(User.id == user_id).first()
    is_admin = user and user.role in ("admin", "master_admin")
    if not is_admin and ticket.user_id != user_id:
        raise ValueError("Not authorized")

    ticket.status = "closed"
    ticket.updated_at = datetime.now(timezone.utc)
    if not ticket.resolved_at:
        ticket.resolved_at = datetime.now(timezone.utc)

    system_msg = TicketMessage(
        ticket_id=ticket_id,
        author_id=user_id,
        message_type="system",
        content="Ticket closed",
        is_admin=is_admin,
    )
    db.add(system_msg)
    db.flush()

    _publish_event("support.ticket.resolved", {
        "ticket_id": ticket_id,
        "closed_by": user_id,
    })

    return _ticket_to_dict(ticket)


# ── Stats ───────────────────────────────────────────────────────────

def get_support_stats(db: Session) -> dict:
    """Admin: get support desk metrics."""
    total = db.query(SupportTicket).count()
    open_count = db.query(SupportTicket).filter(SupportTicket.status == "open").count()
    in_progress = db.query(SupportTicket).filter(SupportTicket.status == "in_progress").count()
    waiting = db.query(SupportTicket).filter(SupportTicket.status == "waiting_on_user").count()
    resolved = db.query(SupportTicket).filter(SupportTicket.status == "resolved").count()
    closed = db.query(SupportTicket).filter(SupportTicket.status == "closed").count()

    # Average resolution time (for resolved/closed tickets with resolved_at)
    avg_resolution = None
    resolved_tickets = db.query(SupportTicket).filter(
        SupportTicket.resolved_at.isnot(None),
    ).all()
    if resolved_tickets:
        deltas = []
        for t in resolved_tickets:
            if t.resolved_at and t.created_at:
                delta = (t.resolved_at - t.created_at).total_seconds() / 3600
                deltas.append(delta)
        if deltas:
            avg_resolution = round(sum(deltas) / len(deltas), 1)

    # Recent tickets
    recent = (
        db.query(SupportTicket)
        .filter(SupportTicket.status.in_(["open", "in_progress"]))
        .order_by(SupportTicket.created_at.desc())
        .limit(5)
        .all()
    )
    user_ids = {t.user_id for t in recent}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return {
        "total": total,
        "open": open_count,
        "in_progress": in_progress,
        "waiting_on_user": waiting,
        "resolved": resolved,
        "closed": closed,
        "avg_resolution_hours": avg_resolution,
        "recent": [_ticket_to_dict(t, user=users.get(t.user_id)) for t in recent],
    }


# ── Helpers ─────────────────────────────────────────────────────────

def _ticket_to_dict(ticket: SupportTicket, user: Optional[User] = None) -> dict:
    """Convert ticket model to API response dict."""
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "user_id": ticket.user_id,
        "user_name": _display_name(user) if user else None,
        "user_address": user.eth_address if user else None,
        "conversation_id": ticket.conversation_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "assigned_to": ticket.assigned_to,
        "is_encrypted": ticket.is_encrypted,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


def _display_name(user: Optional[User]) -> str:
    """Get display name for a user."""
    if not user:
        return "Unknown"
    if hasattr(user, "display_name") and user.display_name:
        return user.display_name
    if user.eth_address:
        return f"{user.eth_address[:6]}...{user.eth_address[-4:]}"
    return user.id[:8]


def _publish_event(event: str, data: dict):
    """Fire-and-forget event publish to EventBus."""
    try:
        from api.services.event_bus import EventBus
        bus = EventBus.get()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(bus.publish(event, data))
        except RuntimeError:
            pass  # No event loop available (e.g., during tests)
    except Exception:
        pass  # Event publishing is best-effort
