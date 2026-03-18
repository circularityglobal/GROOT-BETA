"""
REFINET Cloud — Uptime Monitor Service
Background health checks with logging to internal DB.
Fires system.health.degraded event via EventBus when subsystems fail.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from api.config import get_settings
from api.models.internal import HealthCheckLog

logger = logging.getLogger("refinet.monitor")

_startup_time = time.monotonic()
_consecutive_inference_failures = 0
_was_degraded = False  # tracks whether we've fired a degraded event (for recovery)


async def run_health_check(internal_db: Session) -> dict:
    """
    Run a full health check across all subsystems.
    Logs result to internal DB. Returns status dict.
    """
    global _consecutive_inference_failures
    settings = get_settings()

    # Check inference engine
    inference_ok = False
    inference_latency_ms = None
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.bitnet_host}/health")
            inference_ok = resp.status_code == 200
        inference_latency_ms = int((time.monotonic() - start) * 1000)
    except Exception:
        inference_ok = False

    # Check database (internal DB is the one we're writing to)
    database_ok = True
    try:
        internal_db.execute(sqlfunc.now())
    except Exception:
        database_ok = False

    # Check SMTP
    smtp_ok = None
    if settings.smtp_enabled:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((settings.smtp_host, settings.smtp_port))
            s.close()
            smtp_ok = True
        except Exception:
            smtp_ok = False

    # Track consecutive inference failures for alerting
    global _was_degraded
    if not inference_ok:
        _consecutive_inference_failures += 1
    else:
        _consecutive_inference_failures = 0

    # Log to internal DB
    notes = None
    if _consecutive_inference_failures >= 3:
        notes = f"Inference down for {_consecutive_inference_failures} consecutive checks"
        logger.critical(notes)

    log_entry = HealthCheckLog(
        inference_ok=inference_ok,
        inference_latency_ms=inference_latency_ms,
        database_ok=database_ok,
        smtp_ok=smtp_ok,
        notes=notes,
    )
    internal_db.add(log_entry)
    internal_db.flush()

    # Fire degraded/recovered events via EventBus → webhook delivery
    try:
        from api.services.event_bus import EventBus
        import asyncio
        bus = EventBus.get()
        loop = asyncio.get_running_loop()

        if _consecutive_inference_failures == 3 and not _was_degraded:
            _was_degraded = True
            loop.create_task(bus.publish(
                "system.health.degraded",
                {
                    "subsystem": "inference",
                    "consecutive_failures": _consecutive_inference_failures,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ))
            logger.warning("Fired system.health.degraded event")

        elif _consecutive_inference_failures == 0 and _was_degraded:
            _was_degraded = False
            loop.create_task(bus.publish(
                "system.health.recovered",
                {
                    "subsystem": "inference",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ))
            logger.info("Fired system.health.recovered event")
    except Exception:
        pass

    return {
        "inference_ok": inference_ok,
        "inference_latency_ms": inference_latency_ms,
        "database_ok": database_ok,
        "smtp_ok": smtp_ok,
    }


def compute_uptime(internal_db: Session, hours: int = 24) -> dict:
    """
    Compute uptime percentage from health check logs.
    Returns uptime stats for the given time window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    total = internal_db.query(sqlfunc.count(HealthCheckLog.id)).filter(
        HealthCheckLog.timestamp >= cutoff,
    ).scalar() or 0

    if total == 0:
        return {"period_hours": hours, "total_checks": 0, "uptime_pct": None}

    healthy = internal_db.query(sqlfunc.count(HealthCheckLog.id)).filter(
        HealthCheckLog.timestamp >= cutoff,
        HealthCheckLog.inference_ok == True,  # noqa: E712
        HealthCheckLog.database_ok == True,  # noqa: E712
    ).scalar() or 0

    avg_latency = internal_db.query(
        sqlfunc.avg(HealthCheckLog.inference_latency_ms),
    ).filter(
        HealthCheckLog.timestamp >= cutoff,
        HealthCheckLog.inference_ok == True,  # noqa: E712
        HealthCheckLog.inference_latency_ms != None,  # noqa: E711
    ).scalar()

    return {
        "period_hours": hours,
        "total_checks": total,
        "healthy_checks": healthy,
        "uptime_pct": round((healthy / total) * 100, 2),
        "avg_inference_latency_ms": round(avg_latency) if avg_latency else None,
    }


def get_uptime_seconds() -> float:
    """Get seconds since server started."""
    return time.monotonic() - _startup_time
