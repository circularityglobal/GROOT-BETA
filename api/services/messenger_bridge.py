"""
REFINET Cloud — Messenger Bridge Service
Routes incoming Telegram/WhatsApp messages to GROOT inference
and sends AI-generated replies back through the messenger platform.
"""

import json
import logging
import urllib.request
from typing import Optional

from sqlalchemy.orm import Session

from api.models.public import MessengerLink, User

logger = logging.getLogger("refinet.messenger")


# ── Telegram Bridge ──────────────────────────────────────────────

class TelegramBridge:
    """
    Handles incoming Telegram webhook updates.
    Routes messages to GROOT inference and replies via Telegram Bot API.
    """

    @staticmethod
    async def handle_update(db: Session, update: dict, bot_token: str) -> Optional[str]:
        """
        Process a Telegram webhook update.
        Returns the reply text if a message was processed, None otherwise.
        """
        message = update.get("message")
        if not message:
            return None

        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        telegram_user_id = str(message.get("from", {}).get("id", ""))

        if not chat_id or not text:
            return None

        # Skip bot commands that aren't messages
        if text.startswith("/start"):
            reply = "Welcome to REFINET Cloud! Send me a message and I'll respond using GROOT AI.\n\nLink your account with /link <your_username>"
            TelegramBridge._send_message(bot_token, chat_id, reply)
            return reply

        if text.startswith("/link "):
            username = text.split(" ", 1)[1].strip()
            return await TelegramBridge._link_account(db, telegram_user_id, username, chat_id, bot_token)

        # Find linked REFINET user
        link = db.query(MessengerLink).filter(
            MessengerLink.platform == "telegram",
            MessengerLink.platform_user_id == telegram_user_id,
            MessengerLink.is_verified == True,  # noqa: E712
        ).first()

        user_id = link.user_id if link else None

        # Call GROOT inference
        try:
            from api.services.inference import call_bitnet
            from api.services.rag import build_groot_system_prompt

            system_prompt, _ = build_groot_system_prompt(db, text, user_id=user_id)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ]

            result = await call_bitnet(messages=messages, temperature=0.7, max_tokens=512)
            reply = result.get("content", "I couldn't generate a response.")

        except Exception as e:
            logger.error(f"Telegram inference error: {e}")
            reply = "Sorry, I'm having trouble processing your request right now."

        # Send reply
        TelegramBridge._send_message(bot_token, chat_id, reply)
        return reply

    @staticmethod
    async def _link_account(
        db: Session, telegram_user_id: str, username: str, chat_id: int, bot_token: str,
    ) -> str:
        """Link a Telegram account to a REFINET user."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            reply = f"User '{username}' not found. Check your REFINET username."
            TelegramBridge._send_message(bot_token, chat_id, reply)
            return reply

        # Check if already linked
        existing = db.query(MessengerLink).filter(
            MessengerLink.platform == "telegram",
            MessengerLink.platform_user_id == telegram_user_id,
        ).first()

        if existing:
            existing.user_id = user.id
            existing.is_verified = True
        else:
            link = MessengerLink(
                user_id=user.id,
                platform="telegram",
                platform_user_id=telegram_user_id,
                platform_username=username,
                is_verified=True,
            )
            db.add(link)

        db.flush()
        reply = f"Linked to REFINET account '{username}'. Your messages now use your personal knowledge base."
        TelegramBridge._send_message(bot_token, chat_id, reply)
        return reply

    @staticmethod
    def _send_message(bot_token: str, chat_id: int, text: str):
        """Send a message via Telegram Bot API."""
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = json.dumps({
                "chat_id": chat_id,
                "text": text[:4096],  # Telegram message limit
                "parse_mode": "Markdown",
            }).encode()

            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
        except Exception as e:
            logger.error(f"Telegram send error: {e}")


# ── WhatsApp Bridge ──────────────────────────────────────────────

class WhatsAppBridge:
    """
    Handles incoming WhatsApp Cloud API webhook updates.
    Similar pattern to Telegram: receive → infer → reply.
    """

    @staticmethod
    async def handle_update(db: Session, update: dict, api_token: str, phone_number_id: str) -> Optional[str]:
        """Process a WhatsApp webhook update."""
        entry = update.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return None

        msg = messages[0]
        wa_user_id = msg.get("from", "")
        text = msg.get("text", {}).get("body", "")

        if not wa_user_id or not text:
            return None

        # Find linked user
        link = db.query(MessengerLink).filter(
            MessengerLink.platform == "whatsapp",
            MessengerLink.platform_user_id == wa_user_id,
            MessengerLink.is_verified == True,  # noqa: E712
        ).first()

        user_id = link.user_id if link else None

        # Call GROOT inference
        try:
            from api.services.inference import call_bitnet
            from api.services.rag import build_groot_system_prompt

            system_prompt, _ = build_groot_system_prompt(db, text, user_id=user_id)
            result = await call_bitnet(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.7,
                max_tokens=512,
            )
            reply = result.get("content", "I couldn't generate a response.")
        except Exception as e:
            logger.error(f"WhatsApp inference error: {e}")
            reply = "Sorry, I'm having trouble right now."

        # Send reply
        WhatsAppBridge._send_message(api_token, phone_number_id, wa_user_id, reply)
        return reply

    @staticmethod
    def _send_message(api_token: str, phone_number_id: str, to: str, text: str):
        """Send a message via WhatsApp Cloud API."""
        try:
            url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
            payload = json.dumps({
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text[:4096]},
            }).encode()

            req = urllib.request.Request(
                url, data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_token}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
