"""
REFINET Cloud — Webhook Delivery Service
HMAC-SHA256 signed payloads, async background delivery with retry + exponential backoff.
Uses an in-process asyncio.Queue for zero-dependency background processing.
"""

import asyncio
import json
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from api.models.public import WebhookSubscription

logger = logging.getLogger("refinet.webhooks")

MAX_FAILURES = 10
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 8, 30]  # seconds between retries (exponential backoff)

# ── Async Webhook Queue ─────────────────────────────────────────────

_webhook_queue = None


def init_webhook_queue():
    """Initialize the webhook queue. Must be called from an async context (app lifespan)."""
    global _webhook_queue
    if _webhook_queue is None:
        _webhook_queue = asyncio.Queue(maxsize=1000)
    return _webhook_queue


def get_webhook_queue() -> Optional[asyncio.Queue]:
    """Get the webhook delivery queue, or None if not yet initialized."""
    return _webhook_queue


async def webhook_worker():
    """
    Background worker that processes webhook deliveries from the queue.
    Retries failed deliveries with exponential backoff (2s, 8s, 30s).
    After MAX_RETRIES, records the failure against the subscription.
    """
    queue = init_webhook_queue()
    logger.info("Webhook delivery worker started")

    while True:
        try:
            item = await queue.get()
        except asyncio.CancelledError:
            logger.info("Webhook worker cancelled")
            return

        try:
            result = await deliver_single_webhook(
                url=item["url"],
                event=item["event"],
                payload=item["payload"],
                secret_hash=item["secret_hash"],
            )

            if result["delivered"]:
                _update_subscription_status(item["sub_id"], True)
            else:
                attempt = item.get("attempt", 0)
                if attempt < MAX_RETRIES:
                    # Retry with exponential backoff
                    delay = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else RETRY_BACKOFF[-1]
                    logger.info(
                        f"Webhook {item['sub_id']} delivery failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {delay}s: {result['message']}"
                    )
                    await asyncio.sleep(delay)
                    item["attempt"] = attempt + 1
                    try:
                        queue.put_nowait(item)
                    except asyncio.QueueFull:
                        logger.warning(f"Queue full, dropping retry for {item['sub_id']}")
                        _update_subscription_status(item["sub_id"], False)
                else:
                    # All retries exhausted
                    logger.warning(
                        f"Webhook {item['sub_id']} delivery failed after {MAX_RETRIES} retries: {result['message']}"
                    )
                    _update_subscription_status(item["sub_id"], False)
        except Exception as e:
            logger.error(f"Webhook worker error for sub {item.get('sub_id')}: {e}")
        finally:
            queue.task_done()


def _update_subscription_status(sub_id: str, delivered: bool):
    """Update webhook subscription failure count after delivery attempt."""
    try:
        from api.database import get_public_session
        db = next(get_public_session())
        try:
            sub = db.query(WebhookSubscription).filter(
                WebhookSubscription.id == sub_id,
            ).first()
            if sub:
                if delivered:
                    sub.last_delivery_at = datetime.now(timezone.utc)
                    sub.failure_count = 0
                else:
                    sub.failure_count += 1
                    if sub.failure_count >= MAX_FAILURES:
                        sub.is_active = False
                        logger.warning(f"Webhook {sub_id} auto-disabled after {MAX_FAILURES} sustained failures")
                db.flush()
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to update webhook status for {sub_id}: {e}")


# ── Event Types ───────────────────────────────────────────────────────

REGISTRY_EVENTS = [
    "registry.project.created",
    "registry.project.updated",
    "registry.project.deleted",
    "registry.abi.added",
    "registry.abi.updated",
    "registry.sdk.published",
    "registry.sdk.updated",
    "registry.logic.added",
    "registry.logic.updated",
    "registry.project.starred",
    "registry.project.forked",
]

MESSAGING_EVENTS = [
    "messaging.dm.sent",
    "messaging.message.sent",
    "messaging.typing",
    "messaging.email.received",
]

SYSTEM_EVENTS = [
    "system.health.degraded",
    "system.health.recovered",
]

DEVICE_EVENTS = [
    "device.registration.new",
    "device.telemetry.received",
    "device.command.sent",
]


def _matches_event(subscribed_events: list[str], event: str) -> bool:
    """Check if an event matches any subscribed pattern (including wildcards)."""
    if event in subscribed_events or "*" in subscribed_events:
        return True
    for e in subscribed_events:
        if e.endswith("*") and event.startswith(e.rstrip("*")):
            return True
    return False


async def deliver_bus_event(event: str, data: dict):
    """
    Event bus handler: enqueue events for all matching webhook subscribers.
    Handles registry.*, messaging.*, system.*, and any other event patterns.
    """
    from api.database import get_public_session

    db = next(get_public_session())
    try:
        subs = db.query(WebhookSubscription).filter(
            WebhookSubscription.is_active == True,  # noqa: E712
        ).all()

        queue = get_webhook_queue()
        if queue is None:
            logger.debug(f"Webhook queue not initialized, skipping {event}")
            return

        for sub in subs:
            events = json.loads(sub.events)
            if not _matches_event(events, event):
                continue

            try:
                queue.put_nowait({
                    "url": sub.url,
                    "event": event,
                    "payload": data,
                    "secret_hash": sub.secret_hash,
                    "sub_id": sub.id,
                    "attempt": 0,
                })
            except asyncio.QueueFull:
                logger.warning(f"Webhook queue full, dropping {event} for sub {sub.id}")
    except Exception as e:
        logger.error(f"Webhook enqueue error for {event}: {e}")
    finally:
        db.close()


# Keep backward-compatible alias
deliver_registry_event = deliver_bus_event


def deliver_webhook_event(
    db: Session,
    user_id: str,
    event: str,
    payload: dict,
    device_id: Optional[str] = None,
):
    """
    Find all matching webhook subscriptions and enqueue delivery.
    Non-blocking: items are processed by the background webhook_worker.
    """
    query = db.query(WebhookSubscription).filter(
        WebhookSubscription.user_id == user_id,
        WebhookSubscription.is_active == True,  # noqa: E712
    )

    if device_id:
        query = query.filter(
            (WebhookSubscription.device_id == device_id) |
            (WebhookSubscription.device_id == None)  # noqa: E711
        )

    subs = query.all()
    queue = get_webhook_queue()
    if queue is None:
        return  # Queue not initialized (e.g. during tests without lifespan)

    for sub in subs:
        events = json.loads(sub.events)
        if not _matches_event(events, event):
            continue

        try:
            queue.put_nowait({
                "url": sub.url,
                "event": event,
                "payload": payload,
                "secret_hash": sub.secret_hash,
                "sub_id": sub.id,
                "attempt": 0,
            })
        except asyncio.QueueFull:
            logger.warning(f"Webhook queue full, dropping {event} for sub {sub.id}")


async def deliver_single_webhook(
    url: str,
    event: str,
    payload: dict,
    secret_hash: str,
) -> dict:
    """Deliver a single webhook with HMAC-SHA256 signature. Returns delivery result."""
    body = json.dumps({
        "event": event,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    signature = hmac.new(
        secret_hash.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-REFINET-Signature": f"sha256={signature}",
                    "X-REFINET-Event": event,
                },
            )
            return {
                "delivered": resp.status_code < 300,
                "status_code": resp.status_code,
                "message": f"HTTP {resp.status_code}",
            }
    except Exception as e:
        return {
            "delivered": False,
            "status_code": None,
            "message": str(e),
        }
