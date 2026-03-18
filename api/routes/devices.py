"""
REFINET Cloud — Device Routes
IoT, PLC, DLT device registration, telemetry ingestion, and commands.
"""

import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_DEVICES_WRITE
from api.auth.api_keys import create_api_key, validate_api_key
from api.models.public import DeviceRegistration, IoTTelemetry, WebhookSubscription
from api.schemas.devices import (
    DeviceRegisterRequest, PLCRegisterRequest, DLTRegisterRequest,
    DeviceResponse, TelemetryIngestRequest, TelemetryResponse,
    DeviceCommandRequest,
)
from api.services.webhook_delivery import deliver_webhook_event

router = APIRouter(prefix="/devices", tags=["devices"])


def _get_user_id(request: Request, db: Session) -> str:
    """Extract user_id from JWT or API key."""
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

    if not verify_scope(payload, SCOPE_DEVICES_WRITE):
        raise HTTPException(status_code=403, detail="Requires devices:write scope")
    return payload["sub"]


@router.post("/register", response_model=DeviceResponse)
def register_device(
    req: DeviceRegisterRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request, db)

    # Create a device-scoped API key
    raw_key, key_record = create_api_key(
        db, user_id,
        name=f"device:{req.name}",
        scopes="devices:write",
        daily_limit=10000,
        prefix="rf_dev_",
    )

    device = DeviceRegistration(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=req.name,
        device_type=req.device_type,
        eth_address=req.eth_address,
        api_key_id=key_record.id,
        device_metadata=json.dumps(req.metadata) if req.metadata else None,
    )
    db.add(device)
    db.flush()

    # Fire webhook event
    deliver_webhook_event(
        db, user_id, "device.registration.new",
        {"device_id": device.id, "name": device.name, "type": device.device_type},
    )

    return DeviceResponse(
        id=device.id,
        name=device.name,
        device_type=device.device_type,
        eth_address=device.eth_address,
        api_key=raw_key,  # returned ONCE
        status=device.status,
        created_at=device.created_at,
    )


@router.post("/register-plc", response_model=DeviceResponse)
def register_plc(req: PLCRegisterRequest, request: Request, db: Session = Depends(public_db_dependency)):
    """PLC-specific registration with Modbus/OPC-UA metadata."""
    return register_device(req, request, db)


@router.post("/register-dlt", response_model=DeviceResponse)
def register_dlt(req: DLTRegisterRequest, request: Request, db: Session = Depends(public_db_dependency)):
    """DLT node registration."""
    return register_device(req, request, db)


@router.get("")
def list_devices(request: Request, db: Session = Depends(public_db_dependency)):
    user_id = _get_user_id(request, db)
    devices = db.query(DeviceRegistration).filter(
        DeviceRegistration.user_id == user_id,
        DeviceRegistration.status != "deregistered",
    ).all()
    return [
        DeviceResponse(
            id=d.id, name=d.name, device_type=d.device_type,
            eth_address=d.eth_address, status=d.status,
            telemetry_count=d.telemetry_count,
            last_seen_at=d.last_seen_at,
            metadata=json.loads(d.device_metadata) if d.device_metadata else None,
            created_at=d.created_at,
        )
        for d in devices
    ]


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, request: Request, db: Session = Depends(public_db_dependency)):
    user_id = _get_user_id(request, db)
    device = db.query(DeviceRegistration).filter(
        DeviceRegistration.id == device_id,
        DeviceRegistration.user_id == user_id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse(
        id=device.id, name=device.name, device_type=device.device_type,
        eth_address=device.eth_address, status=device.status,
        telemetry_count=device.telemetry_count,
        last_seen_at=device.last_seen_at,
        metadata=json.loads(device.device_metadata) if device.device_metadata else None,
        created_at=device.created_at,
    )


@router.delete("/{device_id}")
def deregister_device(device_id: str, request: Request, db: Session = Depends(public_db_dependency)):
    user_id = _get_user_id(request, db)
    device = db.query(DeviceRegistration).filter(
        DeviceRegistration.id == device_id,
        DeviceRegistration.user_id == user_id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = "deregistered"
    return {"message": "Device deregistered"}


# ── Telemetry ──────────────────────────────────────────────────────

@router.post("/{device_id}/telemetry")
def ingest_telemetry(
    device_id: str,
    req: TelemetryIngestRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Ingest telemetry from a device. Authenticated via device API key."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth_header[7:]
    api_key = validate_api_key(db, token)
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    device = db.query(DeviceRegistration).filter(
        DeviceRegistration.id == device_id,
        DeviceRegistration.api_key_id == api_key.id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found or key mismatch")

    telemetry = IoTTelemetry(
        id=str(uuid.uuid4()),
        device_id=device_id,
        payload=json.dumps(req.payload),
        signature=req.signature,
    )
    db.add(telemetry)

    device.telemetry_count += 1
    device.last_seen_at = datetime.now(timezone.utc)
    db.flush()

    # Fire webhook
    deliver_webhook_event(
        db, device.user_id, "device.telemetry.received",
        {"device_id": device_id, "payload": req.payload},
        device_id=device_id,
    )

    return {"id": telemetry.id, "received": True}


@router.get("/{device_id}/telemetry")
def query_telemetry(
    device_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    limit: int = 100,
):
    user_id = _get_user_id(request, db)
    device = db.query(DeviceRegistration).filter(
        DeviceRegistration.id == device_id,
        DeviceRegistration.user_id == user_id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    records = db.query(IoTTelemetry).filter(
        IoTTelemetry.device_id == device_id,
    ).order_by(IoTTelemetry.received_at.desc()).limit(limit).all()

    return [
        TelemetryResponse(
            id=r.id, device_id=r.device_id,
            payload=json.loads(r.payload),
            received_at=r.received_at,
        )
        for r in records
    ]


@router.post("/{device_id}/command")
def send_command(
    device_id: str,
    req: DeviceCommandRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    user_id = _get_user_id(request, db)
    device = db.query(DeviceRegistration).filter(
        DeviceRegistration.id == device_id,
        DeviceRegistration.user_id == user_id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    deliver_webhook_event(
        db, user_id, "device.command.sent",
        {"device_id": device_id, "command": req.command, "parameters": req.parameters},
        device_id=device_id,
    )

    return {"message": "Command sent via webhook", "device_id": device_id}
