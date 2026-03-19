"""
REFINET Cloud — Webhook Routes
Subscribe to events, test delivery, and manage subscriptions.
"""

import json
import os
import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_WEBHOOKS_WRITE
from api.models.public import WebhookSubscription
from api.schemas.webhooks import (
    WebhookSubscribeRequest, WebhookSubscribeResponse,
    WebhookListItem, WebhookTestResponse,
)
from api.services.webhook_delivery import deliver_single_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _get_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not verify_scope(payload, SCOPE_WEBHOOKS_WRITE):
        raise HTTPException(status_code=403, detail="Requires webhooks:write scope")
    return payload["sub"]


@router.post("/subscribe", response_model=WebhookSubscribeResponse)
def subscribe(
    req: WebhookSubscribeRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request)

    # Generate signing secret
    raw_secret = f"whsec_{os.urandom(32).hex()}"
    secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    webhook = WebhookSubscription(
        id=str(uuid.uuid4()),
        user_id=user_id,
        device_id=req.device_id,
        url=req.url,
        secret_hash=secret_hash,
        events=json.dumps(req.events),
    )
    db.add(webhook)
    db.flush()

    return WebhookSubscribeResponse(
        id=webhook.id,
        url=webhook.url,
        events=req.events,
        signing_secret=raw_secret,
    )


@router.get("", response_model=list[WebhookListItem])
def list_webhooks(request: Request, db: Session = Depends(public_db_dependency)):
    user_id = _get_user_id(request)
    subs = db.query(WebhookSubscription).filter(
        WebhookSubscription.user_id == user_id,
    ).all()
    return [
        WebhookListItem(
            id=s.id, url=s.url,
            events=json.loads(s.events),
            is_active=s.is_active,
            failure_count=s.failure_count,
            last_delivery_at=s.last_delivery_at,
            created_at=s.created_at,
        )
        for s in subs
    ]


@router.delete("/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request)
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == webhook_id,
        WebhookSubscription.user_id == user_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(sub)
    return {"message": "Webhook deleted"}


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request)
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == webhook_id,
        WebhookSubscription.user_id == user_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")

    result = await deliver_single_webhook(
        url=sub.url,
        event="webhook.test",
        payload={"test": True, "webhook_id": webhook_id},
        secret_hash=sub.secret_hash,
    )

    return WebhookTestResponse(
        delivered=result["delivered"],
        status_code=result.get("status_code"),
        message=result.get("message", ""),
    )


# ── Telegram Webhook Receiver ────────────────────────────────────

@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Telegram Bot webhook receiver.
    No auth — verification is done via Telegram's secret token header.
    """
    # Verify Telegram secret token if configured
    from api.services.config_defaults import get_config_value
    from api.database import get_internal_session
    with get_internal_session() as int_db:
        bot_token = get_config_value(int_db, "messenger.telegram_bot_token")

    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    body = await request.json()

    from api.services.messenger_bridge import TelegramBridge
    await TelegramBridge.handle_update(db, body, bot_token)

    return {"ok": True}


# ── WhatsApp Webhook Receiver ────────────────────────────────────

@router.get("/whatsapp")
async def whatsapp_verify(request: Request):
    """WhatsApp webhook verification (hub.challenge)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    from api.services.config_defaults import get_config_value
    from api.database import get_internal_session
    with get_internal_session() as int_db:
        verify_token = get_config_value(int_db, "messenger.whatsapp_verify_token")

    if mode == "subscribe" and token == verify_token:
        return int(challenge) if challenge else 0

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """WhatsApp Cloud API webhook receiver."""
    from api.services.config_defaults import get_config_value
    from api.database import get_internal_session
    with get_internal_session() as int_db:
        api_token = get_config_value(int_db, "messenger.whatsapp_api_token")
        phone_number_id = get_config_value(int_db, "messenger.whatsapp_phone_number_id")

    if not api_token or not phone_number_id:
        raise HTTPException(status_code=503, detail="WhatsApp not configured")

    body = await request.json()

    from api.services.messenger_bridge import WhatsAppBridge
    await WhatsAppBridge.handle_update(db, body, api_token, phone_number_id)

    return {"ok": True}
