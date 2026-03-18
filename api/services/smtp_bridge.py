"""
REFINET Cloud — SMTP Bridge Server
Receives inbound email and routes to wallet messaging system.

Flow: SMTP → parse email → resolve wallet alias → create message → EventBus

Supports:
  - Inbound email to wallet aliases (742d35cc@cifi.global)
  - Email-to-DM routing (creates conversation if needed)
  - Attachment metadata extraction
  - Delivery status tracking
"""

from __future__ import annotations

import asyncio
import email
import logging
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from typing import Optional

logger = logging.getLogger("refinet.smtp")

_smtp_server = None
_smtp_task: Optional[asyncio.Task] = None


# ── Inbound Email Handler ────────────────────────────────────────────

class WalletMailHandler:
    """
    aiosmtpd handler that routes inbound email to wallet messaging.
    Each email becomes a DM in the messaging system.
    """

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        """Validate recipient before accepting."""
        # Accept all addresses in our domain — we'll validate in handle_DATA
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        """Process inbound email and route to wallet messaging."""
        try:
            # Parse the email
            msg = email.message_from_bytes(envelope.content, policy=policy.default)
            from_addr = envelope.mail_from
            to_addrs = envelope.rcpt_tos
            subject = msg.get("Subject", "(no subject)")
            body = _extract_body(msg)
            attachments = _extract_attachments(msg)

            logger.info(
                f"SMTP inbound: from={from_addr} to={to_addrs} subject={subject[:50]}"
            )

            # Route each recipient
            results = []
            for to_addr in to_addrs:
                result = await _route_email_to_wallet(
                    from_email=from_addr,
                    to_email=to_addr,
                    subject=subject,
                    body=body,
                    attachments=attachments,
                )
                results.append(result)

            # If all recipients failed, reject
            if all(r.get("error") for r in results):
                first_error = results[0].get("error", "Delivery failed")
                logger.warning(f"SMTP delivery failed: {first_error}")
                return f"550 {first_error}"

            delivered = sum(1 for r in results if not r.get("error"))
            logger.info(f"SMTP delivered to {delivered}/{len(results)} recipients")
            return "250 Message accepted for delivery"

        except Exception as e:
            logger.error(f"SMTP handler error: {e}")
            return "451 Temporary failure, please retry"


async def _route_email_to_wallet(
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    attachments: list[dict],
) -> dict:
    """Route a single email to a wallet's messaging inbox."""
    from api.database import get_public_db
    from api.services.email_bridge import resolve_email_to_address
    from api.services.messaging import send_dm, resolve_recipient
    from api.models.public import User

    try:
        with get_public_db() as db:
            # Resolve recipient email → wallet address
            recipient_address = resolve_email_to_address(db, to_email)
            if not recipient_address:
                return {"error": f"Unknown recipient: {to_email}"}

            # Resolve sender — try email alias first, then treat as external
            sender_address = resolve_email_to_address(db, from_email)

            if sender_address:
                # Internal sender (has a wallet)
                sender_user = db.query(User).filter(
                    User.eth_address == sender_address
                ).first()
                if not sender_user:
                    return {"error": "Sender wallet not found"}

                # Format message content
                content = _format_email_as_message(subject, body, attachments)

                result = send_dm(
                    db, sender_user.id, sender_address,
                    recipient_address, content, "text",
                )
                return {"delivered": True, "message_id": result["message"].id}
            else:
                # External sender — create a system message in recipient's inbox
                recipient_user = db.query(User).filter(
                    User.eth_address == recipient_address
                ).first()
                if not recipient_user:
                    return {"error": "Recipient user not found"}

                # Store as inbound email record
                content = _format_email_as_message(
                    subject, body, attachments,
                    external_from=from_email,
                )

                # Record the inbound email
                from api.models.public import Message, Conversation, ConversationParticipant
                import uuid

                # Create or find the "email inbox" conversation for this user
                inbox_convo = _get_or_create_email_inbox(db, recipient_user.id, recipient_address)

                msg = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=inbox_convo.id,
                    sender_id=recipient_user.id,  # system message attributed to user
                    sender_address="smtp-bridge",
                    content=content,
                    content_type="email",
                )
                db.add(msg)
                inbox_convo.last_message_at = datetime.now(timezone.utc)
                inbox_convo.last_message_preview = f"[Email] {subject[:80]}"
                db.flush()

                # Publish event
                try:
                    from api.services.event_bus import EventBus
                    bus = EventBus.get()
                    loop = asyncio.get_running_loop()
                    loop.create_task(bus.publish("messaging.email.received", {
                        "recipient_address": recipient_address,
                        "from_email": from_email,
                        "subject": subject,
                        "message_id": msg.id,
                    }))
                except Exception:
                    pass

                return {"delivered": True, "message_id": msg.id, "external": True}

    except Exception as e:
        logger.error(f"Email routing error: {e}")
        return {"error": str(e)}


def _get_or_create_email_inbox(db, user_id: str, eth_address: str):
    """Get or create the special 'Email Inbox' conversation for a user."""
    from api.models.public import Conversation, ConversationParticipant

    # Look for existing email inbox conversation
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.user_id == user_id,
    ).all()

    for p in participant:
        convo = db.query(Conversation).filter(
            Conversation.id == p.conversation_id,
            Conversation.title == "[Email Inbox]",
        ).first()
        if convo:
            return convo

    # Create new inbox
    import uuid
    convo = Conversation(
        id=str(uuid.uuid4()),
        title="[Email Inbox]",
        is_group=False,
        created_by=user_id,
    )
    db.add(convo)
    db.flush()

    db.add(ConversationParticipant(
        id=str(uuid.uuid4()),
        conversation_id=convo.id,
        user_id=user_id,
        eth_address=eth_address,
        display_name="Email Inbox",
        role="owner",
    ))
    db.flush()
    return convo


# ── Email Parsing ────────────────────────────────────────────────────

def _extract_body(msg: EmailMessage) -> str:
    """Extract plain text body from email."""
    body = msg.get_body(preferencelist=("plain", "html"))
    if body:
        content = body.get_content()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return content.strip()
    return ""


def _extract_attachments(msg: EmailMessage) -> list[dict]:
    """Extract attachment metadata (not content) from email."""
    attachments = []
    for part in msg.iter_attachments():
        attachments.append({
            "filename": part.get_filename() or "unnamed",
            "content_type": part.get_content_type(),
            "size": len(part.get_content()) if part.get_content() else 0,
        })
    return attachments


def _format_email_as_message(
    subject: str,
    body: str,
    attachments: list[dict],
    external_from: Optional[str] = None,
) -> str:
    """Format an email into a message-compatible text."""
    parts = []
    if external_from:
        parts.append(f"From: {external_from}")
    if subject and subject != "(no subject)":
        parts.append(f"Subject: {subject}")
    if parts:
        parts.append("---")
    parts.append(body[:10000] if body else "(empty)")
    if attachments:
        parts.append(f"\n[{len(attachments)} attachment(s)]")
        for a in attachments[:5]:
            parts.append(f"  - {a['filename']} ({a['content_type']})")
    return "\n".join(parts)


# ── SMTP Server Lifecycle ────────────────────────────────────────────

async def start_smtp_server(host: str = "127.0.0.1", port: int = 8025) -> None:
    """
    Start the SMTP bridge server.
    Uses port 8025 by default (avoids requiring root for port 25).
    """
    global _smtp_server, _smtp_task

    try:
        from aiosmtpd.controller import Controller

        handler = WalletMailHandler()
        controller = Controller(handler, hostname=host, port=port)
        controller.start()
        _smtp_server = controller
        logger.info(f"SMTP bridge started on {host}:{port}")
    except ImportError:
        logger.warning("aiosmtpd not installed — SMTP bridge disabled")
    except Exception as e:
        logger.warning(f"SMTP bridge failed to start: {e}")


async def stop_smtp_server() -> None:
    """Stop the SMTP bridge server."""
    global _smtp_server
    if _smtp_server:
        try:
            _smtp_server.stop()
            logger.info("SMTP bridge stopped")
        except Exception as e:
            logger.warning(f"SMTP bridge stop error: {e}")
        _smtp_server = None


def is_smtp_running() -> bool:
    """Check if SMTP bridge is running."""
    return _smtp_server is not None
