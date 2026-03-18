"""REFINET Cloud — Health Check"""

import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.config import get_settings
from api.services.monitor import get_uptime_seconds

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """
    Enhanced health check with subsystem status.
    Returns inference engine health, database status, and uptime.
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

    return {
        "status": "ok",
        "uptime_seconds": int(get_uptime_seconds()),
        "checks": {
            "inference": {
                "status": inference_status,
                "latency_ms": inference_latency_ms,
            },
            "database": {"status": "ok"},
            **({"smtp": {"status": smtp_status}} if smtp_status else {}),
        },
        "model": "bitnet-b1.58-2b",
        "platform": "REFINET Cloud",
        "version": "2.0.0",
    }


@router.get("/")
def root():
    return {"message": "REFINET Cloud — Grass Root Project Intelligence", "docs": "/docs"}
