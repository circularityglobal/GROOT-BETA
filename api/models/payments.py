"""
REFINET Cloud — Payment & Revenue Models
Fee schedules, payment records, subscriptions, and revenue splits.
All tables in public.db (user-facing data).
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, Float, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Fee Schedule ──────────────────────────────────────────────────

class FeeSchedule(PublicBase):
    """Platform fee structure for services."""
    __tablename__ = "fee_schedules"

    id = Column(String, primary_key=True, default=new_uuid)
    service_type = Column(String, nullable=False, index=True)  # deploy | broker_session | app_purchase | subscription
    fee_percentage = Column(Float, default=0.0)                # e.g., 2.5 = 2.5%
    flat_fee_usd = Column(Float, default=0.0)                 # flat fee in USD
    tokens_accepted = Column(Text, nullable=True)              # JSON array: ["CIFI","USDC","REFI"]
    tier_overrides = Column(Text, nullable=True)               # JSON: {"pro": {"fee_percentage": 1.5}, ...}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


# ── Payment Records ──────────────────────────────────────────────

class PaymentRecord(PublicBase):
    """Individual payment transaction."""
    __tablename__ = "payment_records"

    id = Column(String, primary_key=True, default=new_uuid)
    payer_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=True)  # null = platform fee
    payment_type = Column(String, nullable=False)              # app_purchase | subscription | deploy_fee | broker_fee
    amount_usd = Column(Float, nullable=False)
    token_symbol = Column(String, nullable=True)               # CIFI | USDC | REFI | ETH
    token_amount = Column(Float, nullable=True)
    tx_hash = Column(String, nullable=True)                    # on-chain tx if crypto payment
    status = Column(String, default="pending", index=True)     # pending | completed | failed | refunded
    reference_type = Column(String, nullable=True)             # app_listing | pipeline_run | broker_session
    reference_id = Column(String, nullable=True)               # FK to the referenced entity
    fee_schedule_id = Column(String, ForeignKey("fee_schedules.id"), nullable=True)
    platform_fee_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


# ── Subscriptions ────────────────────────────────────────────────

class Subscription(PublicBase):
    """Recurring subscription tracking."""
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    app_id = Column(String, ForeignKey("app_listings.id"), nullable=True)
    plan_type = Column(String, nullable=False)                 # free | developer | pro
    status = Column(String, default="active", index=True)      # active | cancelled | expired | past_due
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    payment_record_id = Column(String, ForeignKey("payment_records.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    cancelled_at = Column(DateTime, nullable=True)


# ── Revenue Splits ───────────────────────────────────────────────

class RevenueSplit(PublicBase):
    """Defines how revenue is distributed."""
    __tablename__ = "revenue_splits"

    id = Column(String, primary_key=True, default=new_uuid)
    app_id = Column(String, ForeignKey("app_listings.id"), nullable=True)
    split_type = Column(String, nullable=False)                # app_sale | broker_fee | deploy_fee
    platform_pct = Column(Float, default=50.0)                 # percentage to platform
    developer_pct = Column(Float, default=50.0)                # percentage to developer/creator
    broker_pct = Column(Float, default=0.0)                    # percentage to broker (if applicable)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
