"""REFINET Cloud — Device Schemas"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DeviceRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    device_type: str = Field(pattern=r"^(iot|plc|dlt|agent|webhook|api)$")
    eth_address: Optional[str] = None
    metadata: Optional[dict] = None


class PLCRegisterRequest(DeviceRegisterRequest):
    device_type: str = "plc"
    metadata: dict = Field(description="Must include protocol, endpoint, registers")


class DLTRegisterRequest(DeviceRegisterRequest):
    device_type: str = "dlt"
    eth_address: str
    metadata: dict = Field(description="Must include chain, node_type")


class DeviceResponse(BaseModel):
    id: str
    name: str
    device_type: str
    eth_address: Optional[str] = None
    api_key: Optional[str] = None  # returned ONCE on registration
    status: str
    telemetry_count: int = 0
    last_seen_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None


class TelemetryIngestRequest(BaseModel):
    payload: dict
    signature: Optional[str] = None
    timestamp: Optional[str] = None


class TelemetryResponse(BaseModel):
    id: str
    device_id: str
    payload: dict
    received_at: datetime


class DeviceCommandRequest(BaseModel):
    command: str
    parameters: Optional[dict] = None
