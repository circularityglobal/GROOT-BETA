"""
REFINET Cloud — Device Telemetry Service
Handles telemetry ingestion, threshold alerting, and 7-day cleanup.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from api.models.public import IoTTelemetry


def cleanup_old_telemetry(db: Session, days: int = 7) -> int:
    """Delete telemetry older than N days. Called by cron."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = db.query(IoTTelemetry).filter(
        IoTTelemetry.received_at < cutoff,
    ).delete(synchronize_session=False)
    db.commit()
    return deleted
