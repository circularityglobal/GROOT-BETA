"""
REFINET Cloud — XMTP Protocol Wrapper
Protocol-aware messaging layer that falls back to internal messaging
until full XMTP SDK integration is available.

When XMTP infra is ready, replace the stub implementations with actual
XMTP SDK calls. The interface remains the same.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.xmtp")


def is_xmtp_available(db: Session, user_id: str) -> bool:
    """Check if a user has XMTP enabled on their wallet identity."""
    try:
        from api.models.public import WalletIdentity
        identity = db.query(WalletIdentity).filter(
            WalletIdentity.user_id == user_id,
        ).first()
        return bool(identity and identity.xmtp_enabled)
    except Exception:
        return False


async def send_via_xmtp(
    from_address: str,
    to_address: str,
    message: str,
    content_type: str = "text",
) -> dict:
    """
    Send a message via XMTP protocol.
    Currently falls back to internal messaging system.

    When XMTP SDK is integrated, this will:
    1. Check if both parties have XMTP identity keys
    2. Encrypt using X3DH + Double Ratchet
    3. Send via XMTP network
    """
    logger.info("XMTP send requested: %s → %s (falling back to internal)", from_address, to_address)

    # Fallback: route through internal messaging
    try:
        from api.database import get_public_db
        from api.services.messaging import send_message, get_or_create_dm

        with get_public_db() as db:
            # Find or create DM conversation
            conv = get_or_create_dm(db, from_address, to_address)
            if not conv or conv.get("error"):
                return {
                    "success": False,
                    "protocol": "internal_fallback",
                    "error": "Could not create conversation",
                }

            msg = send_message(
                db,
                conversation_id=conv["id"],
                sender_id=from_address,
                content=message,
                content_type=content_type,
            )
            db.commit()

            return {
                "success": True,
                "protocol": "internal_fallback",
                "message_id": msg.get("id") if isinstance(msg, dict) else None,
                "note": "XMTP not yet available — delivered via internal messaging",
            }
    except Exception as e:
        logger.warning("XMTP fallback failed: %s", e)
        return {
            "success": False,
            "protocol": "internal_fallback",
            "error": str(e),
        }


def get_xmtp_status() -> dict:
    """Get XMTP integration status."""
    return {
        "available": False,
        "protocol_version": None,
        "fallback": "internal_messaging",
        "note": "XMTP integration pending — using internal wallet-to-wallet messaging",
    }
