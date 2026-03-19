"""
REFINET Cloud — Broker Models
Brokered sessions where GROOT intermediates between service providers and consumers.
All tables in public.db (user-facing data).
"""

from sqlalchemy import (
    Column, String, Boolean, Float, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class BrokerSession(PublicBase):
    """Tracks a brokered interaction between client and provider."""
    __tablename__ = "broker_sessions"

    id = Column(String, primary_key=True, default=new_uuid)
    client_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider_id = Column(String, ForeignKey("users.id"), nullable=True)  # null = GROOT is provider
    service_type = Column(String, nullable=False)              # deploy | audit | consult | custom
    status = Column(String, default="requested", index=True)   # requested | active | completed | cancelled | disputed
    config_json = Column(Text, nullable=True)                  # JSON: session parameters
    result_json = Column(Text, nullable=True)                  # JSON: session outcome
    payment_record_id = Column(String, ForeignKey("payment_records.id"), nullable=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    pipeline_run_id = Column(String, ForeignKey("pipeline_runs.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class BrokerFeeConfig(PublicBase):
    """Per-service-type broker fee overrides."""
    __tablename__ = "broker_fee_configs"

    id = Column(String, primary_key=True, default=new_uuid)
    service_type = Column(String, nullable=False, unique=True, index=True)
    base_fee_usd = Column(Float, default=0.0)
    percentage_fee = Column(Float, default=5.0)
    token_options = Column(Text, nullable=True)                # JSON array: ["CIFI","USDC","REFI"]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
