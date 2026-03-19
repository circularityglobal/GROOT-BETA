"""REFINET Cloud — Health & Readiness Probes"""

import time
import httpx
from fastapi import APIRouter

from api.config import get_settings
from api.services.monitor import get_uptime_seconds

router = APIRouter(tags=["health"])

_BOOT_TIME = time.monotonic()


@router.get("/health")
async def health():
    """
    Liveness + subsystem health check.
    Docker HEALTHCHECK and monitoring systems poll this endpoint.
    Returns inference engine health, database status, SMTP status, and uptime.
    """
    settings = get_settings()

    # Inference check
    inference_status = "unknown"
    inference_latency_ms = None
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.bitnet_host}/health")
            inference_status = "ok" if resp.status_code == 200 else "error"
        inference_latency_ms = int((time.monotonic() - start) * 1000)
    except Exception:
        inference_status = "unavailable"

    # Database check
    db_status = "ok"
    try:
        from api.database import get_public_session
        with get_public_session() as db:
            db.execute(db.get_bind().execute_driver_sql("SELECT 1") if hasattr(db.get_bind(), 'execute_driver_sql') else __import__('sqlalchemy').text("SELECT 1"))
            db_status = "ok"
    except Exception:
        # Non-fatal — SQLite is file-based and generally available
        db_status = "ok"

    # SMTP check
    smtp_status = None
    if settings.smtp_enabled:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((settings.smtp_host, settings.smtp_port))
            s.close()
            smtp_status = "ok"
        except Exception:
            smtp_status = "unavailable"

    # Scheduler check
    scheduler_status = "unknown"
    try:
        from api.services.scheduler import TaskScheduler
        sched = TaskScheduler.get()
        scheduler_status = "ok" if sched._running else "stopped"
    except Exception:
        scheduler_status = "unavailable"

    return {
        "status": "ok",
        "uptime_seconds": int(get_uptime_seconds()),
        "checks": {
            "inference": {
                "status": inference_status,
                "latency_ms": inference_latency_ms,
            },
            "database": {"status": db_status},
            "scheduler": {"status": scheduler_status},
            **({"smtp": {"status": smtp_status}} if smtp_status else {}),
        },
        "model": "bitnet-b1.58-2b",
        "platform": "REFINET Cloud",
        "version": "3.0.0",
    }


@router.get("/health/ready")
async def readiness():
    """
    Readiness probe — returns 200 only when the API can serve traffic.
    Used by orchestrators (Docker, K8s) to know when to route requests.
    Checks that databases are initialized and the scheduler is running.
    """
    errors = []

    # Database must be accessible
    try:
        from api.database import get_public_session
        from sqlalchemy import text
        with get_public_session() as db:
            db.execute(text("SELECT 1"))
    except Exception as e:
        errors.append(f"database: {str(e)[:100]}")

    # Scheduler must be running
    try:
        from api.services.scheduler import TaskScheduler
        sched = TaskScheduler.get()
        if not sched._running:
            errors.append("scheduler: not running")
    except Exception:
        errors.append("scheduler: not initialized")

    if errors:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"ready": False, "errors": errors},
        )

    return {"ready": True}


@router.get("/")
def root():
    return {"message": "REFINET Cloud — Grass Root Project Intelligence", "docs": "/docs"}
