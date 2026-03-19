"""
REFINET Cloud — Payment Service
Fee calculation, payment recording, subscription management, and revenue splits.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from api.models.payments import FeeSchedule, PaymentRecord, Subscription, RevenueSplit

logger = logging.getLogger("refinet.payments")


# ── Fee Calculation ───────────────────────────────────────────────

def get_fee(db: Session, service_type: str, user_tier: str = "free") -> dict:
    """
    Get the applicable fee for a service type with tier-based discounts.
    Returns: { fee_percentage, flat_fee_usd, tokens_accepted, fee_schedule_id }
    """
    schedule = db.query(FeeSchedule).filter(
        FeeSchedule.service_type == service_type,
        FeeSchedule.is_active == True,  # noqa: E712
    ).first()

    if not schedule:
        return {
            "fee_percentage": 0.0,
            "flat_fee_usd": 0.0,
            "tokens_accepted": ["CIFI", "USDC", "REFI"],
            "fee_schedule_id": None,
        }

    fee_pct = schedule.fee_percentage
    flat_fee = schedule.flat_fee_usd
    tokens = json.loads(schedule.tokens_accepted) if schedule.tokens_accepted else ["CIFI", "USDC", "REFI"]

    # Apply tier overrides
    if schedule.tier_overrides:
        overrides = json.loads(schedule.tier_overrides)
        tier_override = overrides.get(user_tier, {})
        if "fee_percentage" in tier_override:
            fee_pct = tier_override["fee_percentage"]
        if "flat_fee_usd" in tier_override:
            flat_fee = tier_override["flat_fee_usd"]

    return {
        "fee_percentage": fee_pct,
        "flat_fee_usd": flat_fee,
        "tokens_accepted": tokens,
        "fee_schedule_id": schedule.id,
    }


def get_all_fee_schedules(db: Session) -> list[dict]:
    """List all active fee schedules."""
    schedules = db.query(FeeSchedule).filter(
        FeeSchedule.is_active == True,  # noqa: E712
    ).all()
    return [
        {
            "id": s.id,
            "service_type": s.service_type,
            "fee_percentage": s.fee_percentage,
            "flat_fee_usd": s.flat_fee_usd,
            "tokens_accepted": json.loads(s.tokens_accepted) if s.tokens_accepted else [],
            "tier_overrides": json.loads(s.tier_overrides) if s.tier_overrides else {},
        }
        for s in schedules
    ]


def create_fee_schedule(
    db: Session,
    service_type: str,
    fee_percentage: float = 0.0,
    flat_fee_usd: float = 0.0,
    tokens_accepted: Optional[list] = None,
    tier_overrides: Optional[dict] = None,
) -> dict:
    """Create or update a fee schedule for a service type."""
    # Deactivate existing schedule for this service type
    existing = db.query(FeeSchedule).filter(
        FeeSchedule.service_type == service_type,
        FeeSchedule.is_active == True,  # noqa: E712
    ).all()
    for e in existing:
        e.is_active = False

    schedule = FeeSchedule(
        id=str(uuid.uuid4()),
        service_type=service_type,
        fee_percentage=fee_percentage,
        flat_fee_usd=flat_fee_usd,
        tokens_accepted=json.dumps(tokens_accepted or ["CIFI", "USDC", "REFI"]),
        tier_overrides=json.dumps(tier_overrides or {}),
        is_active=True,
    )
    db.add(schedule)
    db.flush()
    return {"id": schedule.id, "service_type": service_type, "message": "Fee schedule created"}


# ── Payment Processing ───────────────────────────────────────────

def create_payment(
    db: Session,
    payer_id: str,
    payment_type: str,
    amount_usd: float,
    token_symbol: Optional[str] = None,
    token_amount: Optional[float] = None,
    tx_hash: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    fee_schedule_id: Optional[str] = None,
) -> PaymentRecord:
    """Record a payment."""
    # Calculate platform fee
    platform_fee = 0.0
    if fee_schedule_id:
        schedule = db.query(FeeSchedule).filter(FeeSchedule.id == fee_schedule_id).first()
        if schedule:
            platform_fee = (amount_usd * schedule.fee_percentage / 100.0) + schedule.flat_fee_usd

    payment = PaymentRecord(
        id=str(uuid.uuid4()),
        payer_id=payer_id,
        recipient_id=recipient_id,
        payment_type=payment_type,
        amount_usd=amount_usd,
        token_symbol=token_symbol,
        token_amount=token_amount,
        tx_hash=tx_hash,
        status="completed" if tx_hash else "pending",
        reference_type=reference_type,
        reference_id=reference_id,
        fee_schedule_id=fee_schedule_id,
        platform_fee_usd=platform_fee,
        completed_at=datetime.now(timezone.utc) if tx_hash else None,
    )
    db.add(payment)
    db.flush()

    logger.info("Payment recorded: id=%s type=%s amount=%.2f status=%s",
                payment.id, payment_type, amount_usd, payment.status)
    return payment


def complete_payment(db: Session, payment_id: str, tx_hash: str) -> Optional[dict]:
    """Mark a pending payment as completed with on-chain tx hash."""
    payment = db.query(PaymentRecord).filter(PaymentRecord.id == payment_id).first()
    if not payment:
        return None
    payment.status = "completed"
    payment.tx_hash = tx_hash
    payment.completed_at = datetime.now(timezone.utc)
    db.flush()
    return {"id": payment.id, "status": "completed", "tx_hash": tx_hash}


def get_payment_history(
    db: Session, user_id: str, limit: int = 50, offset: int = 0,
) -> list[dict]:
    """Get payment history for a user."""
    payments = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.payer_id == user_id)
        .order_by(PaymentRecord.created_at.desc())
        .offset(offset).limit(limit)
        .all()
    )
    return [_payment_to_dict(p) for p in payments]


# ── Revenue Splits ───────────────────────────────────────────────

def execute_revenue_split(db: Session, payment_id: str) -> list[dict]:
    """
    Split a completed payment into platform + developer + broker shares.
    Creates child PaymentRecords for each recipient.
    """
    payment = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_id,
        PaymentRecord.status == "completed",
    ).first()
    if not payment:
        return []

    # Find applicable split config
    split = None
    if payment.reference_type == "app_listing":
        split = db.query(RevenueSplit).filter(
            RevenueSplit.app_id == payment.reference_id,
            RevenueSplit.is_active == True,  # noqa: E712
        ).first()

    if not split:
        # Default split by payment type
        split_type_map = {
            "app_purchase": "app_sale",
            "broker_fee": "broker_fee",
            "deploy_fee": "deploy_fee",
        }
        mapped = split_type_map.get(payment.payment_type, "app_sale")
        split = db.query(RevenueSplit).filter(
            RevenueSplit.split_type == mapped,
            RevenueSplit.app_id == None,  # noqa: E711
            RevenueSplit.is_active == True,  # noqa: E712
        ).first()

    if not split:
        # No split config — all goes to platform
        return []

    results = []
    # Split the full payment amount — platform_fee_usd is the platform's share,
    # tracked separately on the original PaymentRecord. Do not subtract it again.
    total_amount = payment.amount_usd

    # Developer share
    if split.developer_pct > 0 and payment.recipient_id:
        dev_amount = total_amount * split.developer_pct / 100.0
        dev_payment = PaymentRecord(
            id=str(uuid.uuid4()),
            payer_id=payment.payer_id,
            recipient_id=payment.recipient_id,
            payment_type=f"{payment.payment_type}_developer_share",
            amount_usd=dev_amount,
            status="completed",
            reference_type=payment.reference_type,
            reference_id=payment.reference_id,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(dev_payment)
        results.append({"recipient": "developer", "amount_usd": dev_amount})

    db.flush()
    return results


def create_revenue_split(
    db: Session,
    split_type: str,
    platform_pct: float = 50.0,
    developer_pct: float = 50.0,
    broker_pct: float = 0.0,
    app_id: Optional[str] = None,
) -> dict:
    """Create a revenue split configuration."""
    # Validate percentages
    for name, val in [("platform_pct", platform_pct), ("developer_pct", developer_pct), ("broker_pct", broker_pct)]:
        if val < 0 or val > 100:
            raise ValueError(f"{name} must be between 0 and 100, got {val}")
    total = platform_pct + developer_pct + broker_pct
    if abs(total - 100.0) > 0.01:
        raise ValueError(f"Split percentages must sum to 100, got {total}")

    split = RevenueSplit(
        id=str(uuid.uuid4()),
        app_id=app_id,
        split_type=split_type,
        platform_pct=platform_pct,
        developer_pct=developer_pct,
        broker_pct=broker_pct,
    )
    db.add(split)
    db.flush()
    return {"id": split.id, "split_type": split_type}


# ── Subscription Management ──────────────────────────────────────

def check_subscription(db: Session, user_id: str) -> Optional[dict]:
    """Check the user's active subscription."""
    sub = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == "active",
    ).first()
    if not sub:
        return {"plan_type": "free", "status": "active"}
    return {
        "id": sub.id,
        "plan_type": sub.plan_type,
        "status": sub.status,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


def upgrade_subscription(
    db: Session, user_id: str, plan_type: str, payment_record_id: Optional[str] = None,
) -> dict:
    """Upgrade or create a subscription."""
    from api.models.public import User

    # Cancel existing active subscription
    existing = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == "active",
    ).all()
    for e in existing:
        e.status = "cancelled"
        e.cancelled_at = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    sub = Subscription(
        id=str(uuid.uuid4()),
        user_id=user_id,
        plan_type=plan_type,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        payment_record_id=payment_record_id,
    )
    db.add(sub)

    # Update user tier
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.tier = plan_type

    db.flush()
    return {"id": sub.id, "plan_type": plan_type, "status": "active"}


def enforce_tier(db: Session, user_id: str, required_tier: str) -> bool:
    """Check if user's tier meets the required level."""
    from api.models.public import User
    tier_hierarchy = {"free": 0, "developer": 1, "pro": 2, "admin": 3}
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    user_level = tier_hierarchy.get(user.tier, 0)
    required_level = tier_hierarchy.get(required_tier, 0)
    return user_level >= required_level


# ── Revenue Dashboard ────────────────────────────────────────────

def get_revenue_summary(db: Session) -> dict:
    """Get revenue summary for admin dashboard."""
    from sqlalchemy import func as sqlfunc

    total = db.query(
        sqlfunc.sum(PaymentRecord.amount_usd),
        sqlfunc.sum(PaymentRecord.platform_fee_usd),
        sqlfunc.count(PaymentRecord.id),
    ).filter(PaymentRecord.status == "completed").first()

    return {
        "total_revenue_usd": total[0] or 0.0,
        "total_platform_fees_usd": total[1] or 0.0,
        "total_payments": total[2] or 0,
    }


def get_revenue_splits_list(db: Session) -> list[dict]:
    """List all revenue split configurations."""
    splits = db.query(RevenueSplit).filter(RevenueSplit.is_active == True).all()  # noqa: E712
    return [
        {
            "id": s.id,
            "app_id": s.app_id,
            "split_type": s.split_type,
            "platform_pct": s.platform_pct,
            "developer_pct": s.developer_pct,
            "broker_pct": s.broker_pct,
        }
        for s in splits
    ]


# ── Helpers ───────────────────────────────────────────────────────

def _payment_to_dict(p: PaymentRecord) -> dict:
    return {
        "id": p.id,
        "payment_type": p.payment_type,
        "amount_usd": p.amount_usd,
        "token_symbol": p.token_symbol,
        "token_amount": p.token_amount,
        "tx_hash": p.tx_hash,
        "status": p.status,
        "reference_type": p.reference_type,
        "reference_id": p.reference_id,
        "platform_fee_usd": p.platform_fee_usd,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
    }
