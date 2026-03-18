"""REFINET Cloud — Webhook Schemas"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime


class WebhookSubscribeRequest(BaseModel):
    url: str = Field(description="HTTPS URL to receive webhook events")
    events: list[str] = Field(min_length=1, description="Event names to subscribe to")
    device_id: Optional[str] = None


class WebhookSubscribeResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    signing_secret: str  # returned ONCE
    message: str = "Webhook registered. Save the signing secret — it won't be shown again."


class WebhookListItem(BaseModel):
    id: str
    url: str
    events: list[str]
    is_active: bool
    failure_count: int
    last_delivery_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class WebhookTestResponse(BaseModel):
    delivered: bool
    status_code: Optional[int] = None
    message: str


class WebhookDeliveryLog(BaseModel):
    event: str
    delivered: bool
    status_code: Optional[int] = None
    timestamp: datetime
