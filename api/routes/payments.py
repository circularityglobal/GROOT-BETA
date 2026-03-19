"""
REFINET Cloud — Payment & Subscription Routes
Fee schedules, payments, subscriptions, and revenue management.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.payment_service import (
    get_fee, get_all_fee_schedules, create_fee_schedule,
    create_payment, complete_payment, get_payment_history,
    check_subscription, upgrade_subscription,
    get_revenue_summary, get_revenue_splits_list, create_revenue_split,
)

router = APIRouter(tags=["payments"])


def _get_user_id(request: Request, db: Session) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    if token.startswith("rf_"):
        api_key = validate_api_key(db, token)
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key.user_id
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


def _require_admin(request: Request, db: Session) -> str:
    user_id = _get_user_id(request, db)
    from api.database import get_internal_db
    from api.models.internal import RoleAssignment
    with get_internal_db() as int_db:
        role = int_db.query(RoleAssignment).filter(
            RoleAssignment.user_id == user_id,
            RoleAssignment.role == "admin",
        ).first()
        if not role:
            raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


# ── Fee Schedule ──────────────────────────────────────────────────

@router.get("/payments/fee-schedule")
def get_fee_schedule(
    service_type: str = None,
    request: Request = None,
    db: Session = Depends(public_db_dependency),
):
    """View fee structure. Optionally filter by service_type for tier-aware pricing."""
    if service_type and request:
        try:
            user_id = _get_user_id(request, db)
            from api.models.public import User
            user = db.query(User).filter(User.id == user_id).first()
            tier = user.tier if user else "free"
            return get_fee(db, service_type, user_tier=tier)
        except Exception:
            # Unauthenticated — return default tier pricing
            return get_fee(db, service_type, user_tier="free")
    # Public listing of service types and base fees (no tier overrides exposed)
    schedules = get_all_fee_schedules(db)
    return [
        {"service_type": s["service_type"], "fee_percentage": s["fee_percentage"], "flat_fee_usd": s["flat_fee_usd"]}
        for s in schedules
    ]


@router.post("/admin/fee-schedule")
def create_fee_schedule_route(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create or update a fee schedule (admin only)."""
    _require_admin(request, db)
    result = create_fee_schedule(
        db,
        service_type=body.get("service_type"),
        fee_percentage=body.get("fee_percentage", 0.0),
        flat_fee_usd=body.get("flat_fee_usd", 0.0),
        tokens_accepted=body.get("tokens_accepted"),
        tier_overrides=body.get("tier_overrides"),
    )
    db.commit()
    return result


# ── Payments ──────────────────────────────────────────────────────

@router.post("/payments/checkout")
def checkout(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Initiate a payment.
    Body: { payment_type, amount_usd, token_symbol?, tx_hash?, reference_type?, reference_id?, recipient_id? }
    """
    user_id = _get_user_id(request, db)
    payment = create_payment(
        db,
        payer_id=user_id,
        payment_type=body.get("payment_type", "app_purchase"),
        amount_usd=body.get("amount_usd", 0.0),
        token_symbol=body.get("token_symbol"),
        token_amount=body.get("token_amount"),
        tx_hash=body.get("tx_hash"),
        reference_type=body.get("reference_type"),
        reference_id=body.get("reference_id"),
        recipient_id=body.get("recipient_id"),
        fee_schedule_id=body.get("fee_schedule_id"),
    )
    db.commit()
    return {
        "payment_id": payment.id,
        "status": payment.status,
        "amount_usd": payment.amount_usd,
        "platform_fee_usd": payment.platform_fee_usd,
    }


@router.post("/payments/{payment_id}/complete")
def complete_payment_route(
    payment_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Mark a pending payment as completed with tx_hash."""
    user_id = _get_user_id(request, db)
    tx_hash = body.get("tx_hash")
    if not tx_hash:
        raise HTTPException(status_code=400, detail="tx_hash is required")

    # Verify the user owns this payment
    from api.models.payments import PaymentRecord
    payment = db.query(PaymentRecord).filter(PaymentRecord.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.payer_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to complete this payment")

    result = complete_payment(db, payment_id, tx_hash)
    db.commit()
    return result


@router.get("/payments/history")
def payment_history(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(public_db_dependency),
):
    """Get payment history for the authenticated user."""
    user_id = _get_user_id(request, db)
    return get_payment_history(db, user_id, limit=limit, offset=offset)


# ── Subscriptions ────────────────────────────────────────────────

@router.get("/subscriptions/status")
def subscription_status(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get current subscription status."""
    user_id = _get_user_id(request, db)
    return check_subscription(db, user_id)


@router.post("/subscriptions/upgrade")
def upgrade(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Upgrade subscription tier.
    Body: { plan_type: "developer"|"pro", payment_record_id? }
    """
    user_id = _get_user_id(request, db)
    plan = body.get("plan_type")
    if plan not in ("developer", "pro"):
        raise HTTPException(status_code=400, detail="plan_type must be 'developer' or 'pro'")
    result = upgrade_subscription(db, user_id, plan, body.get("payment_record_id"))
    db.commit()
    return result


# ── Admin: Revenue ───────────────────────────────────────────────

@router.get("/admin/revenue")
def revenue_dashboard(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Revenue summary dashboard (admin only)."""
    _require_admin(request, db)
    return get_revenue_summary(db)


@router.get("/admin/revenue-splits")
def revenue_splits(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List all revenue split configurations (admin only)."""
    _require_admin(request, db)
    return get_revenue_splits_list(db)


@router.post("/admin/revenue-splits")
def create_split(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create a revenue split configuration (admin only)."""
    _require_admin(request, db)
    result = create_revenue_split(
        db,
        split_type=body.get("split_type", "app_sale"),
        platform_pct=body.get("platform_pct", 50.0),
        developer_pct=body.get("developer_pct", 50.0),
        broker_pct=body.get("broker_pct", 0.0),
        app_id=body.get("app_id"),
    )
    db.commit()
    return result
