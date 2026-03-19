"""
REFINET Cloud — Broker Service
Manage brokered sessions between service providers and consumers.
Integrates with messaging (conversations), payments, and pipeline execution.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.broker import BrokerSession, BrokerFeeConfig
from api.services.event_bus import EventBus

logger = logging.getLogger("refinet.broker")


def create_session(
    db: Session,
    client_id: str,
    service_type: str,
    config: Optional[dict] = None,
    provider_id: Optional[str] = None,
) -> dict:
    """
    Create a new broker session. Optionally creates a conversation for messaging.

    Returns session details or error dict.
    """
    # Validate service type
    valid_types = {"deploy", "audit", "consult", "custom"}
    if service_type not in valid_types:
        return {"error": f"Invalid service_type. Must be one of: {valid_types}"}

    session_id = str(uuid.uuid4())

    # Create a conversation for the session (if messaging is available)
    conversation_id = None
    try:
        from api.services.messaging import create_conversation
        conv = create_conversation(
            db, creator_id=client_id,
            title=f"Broker session: {service_type}",
            is_group=bool(provider_id),
            participant_ids=[p for p in [client_id, provider_id] if p],
        )
        if conv and not conv.get("error"):
            conversation_id = conv.get("id")
    except Exception as e:
        logger.warning("Could not create conversation for broker session: %s", e)

    session = BrokerSession(
        id=session_id,
        client_id=client_id,
        provider_id=provider_id,
        service_type=service_type,
        status="requested",
        config_json=json.dumps(config or {}),
        conversation_id=conversation_id,
    )
    db.add(session)
    db.flush()

    logger.info("Broker session created: id=%s type=%s client=%s", session_id, service_type, client_id)
    return _session_to_dict(session)


def assign_provider(db: Session, session_id: str, provider_id: str) -> dict:
    """Assign a human or agent provider to a broker session."""
    session = db.query(BrokerSession).filter(BrokerSession.id == session_id).first()
    if not session:
        return {"error": "Session not found"}
    if session.status != "requested":
        return {"error": f"Session is {session.status}, cannot assign provider"}

    session.provider_id = provider_id
    session.status = "active"
    session.started_at = datetime.now(timezone.utc)
    db.flush()

    return _session_to_dict(session)


async def complete_session(
    db: Session,
    session_id: str,
    result: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> dict:
    """Complete a broker session and trigger revenue split."""
    session = db.query(BrokerSession).filter(BrokerSession.id == session_id).first()
    if not session:
        return {"error": "Session not found"}
    if session.status not in ("active", "requested"):
        return {"error": f"Session is {session.status}, cannot complete"}

    # Verify user is client or provider
    if user_id and user_id not in (session.client_id, session.provider_id):
        return {"error": "Not authorized to complete this session"}

    session.status = "completed"
    session.result_json = json.dumps(result or {})
    session.completed_at = datetime.now(timezone.utc)
    db.flush()

    # Trigger revenue split if payment exists
    if session.payment_record_id:
        try:
            from api.services.payment_service import execute_revenue_split
            execute_revenue_split(db, session.payment_record_id)
        except Exception as e:
            logger.warning("Revenue split failed for session %s: %s", session_id, e)

    # Emit event
    bus = EventBus.get()
    await bus.publish("broker.session.completed", {
        "session_id": session_id,
        "service_type": session.service_type,
        "client_id": session.client_id,
        "provider_id": session.provider_id,
    })

    return _session_to_dict(session)


def cancel_session(db: Session, session_id: str, user_id: str) -> dict:
    """Cancel a broker session."""
    session = db.query(BrokerSession).filter(BrokerSession.id == session_id).first()
    if not session:
        return {"error": "Session not found"}
    if session.status in ("completed", "cancelled"):
        return {"error": f"Session is already {session.status}"}
    if user_id not in (session.client_id, session.provider_id):
        return {"error": "Not authorized to cancel this session"}

    session.status = "cancelled"
    session.completed_at = datetime.now(timezone.utc)
    db.flush()

    return _session_to_dict(session)


def list_sessions(
    db: Session,
    user_id: str,
    role: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List broker sessions for a user (as client or provider)."""
    query = db.query(BrokerSession)
    if role == "client":
        query = query.filter(BrokerSession.client_id == user_id)
    elif role == "provider":
        query = query.filter(BrokerSession.provider_id == user_id)
    else:
        from sqlalchemy import or_
        query = query.filter(or_(
            BrokerSession.client_id == user_id,
            BrokerSession.provider_id == user_id,
        ))

    if status:
        query = query.filter(BrokerSession.status == status)

    sessions = query.order_by(BrokerSession.created_at.desc()).offset(offset).limit(limit).all()
    return [_session_to_dict(s) for s in sessions]


def get_session(db: Session, session_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    """Get a single broker session."""
    query = db.query(BrokerSession).filter(BrokerSession.id == session_id)
    session = query.first()
    if not session:
        return None
    if user_id and user_id not in (session.client_id, session.provider_id):
        return None
    return _session_to_dict(session)


# ── Fee Config ────────────────────────────────────────────────────

def get_broker_fee(db: Session, service_type: str) -> dict:
    """Get the fee config for a broker service type."""
    config = db.query(BrokerFeeConfig).filter(
        BrokerFeeConfig.service_type == service_type,
        BrokerFeeConfig.is_active == True,  # noqa: E712
    ).first()
    if not config:
        return {"base_fee_usd": 0.0, "percentage_fee": 5.0, "token_options": ["CIFI", "USDC", "REFI"]}
    return {
        "base_fee_usd": config.base_fee_usd,
        "percentage_fee": config.percentage_fee,
        "token_options": json.loads(config.token_options) if config.token_options else ["CIFI", "USDC", "REFI"],
    }


def _session_to_dict(s: BrokerSession) -> dict:
    return {
        "id": s.id,
        "client_id": s.client_id,
        "provider_id": s.provider_id,
        "service_type": s.service_type,
        "status": s.status,
        "config": json.loads(s.config_json) if s.config_json else {},
        "result": json.loads(s.result_json) if s.result_json else None,
        "payment_record_id": s.payment_record_id,
        "conversation_id": s.conversation_id,
        "pipeline_run_id": s.pipeline_run_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    }
