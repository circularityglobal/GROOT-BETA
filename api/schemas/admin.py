"""REFINET Cloud — Admin Schemas"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AdminUserSummary(BaseModel):
    id: str
    email: str
    username: str
    tier: str
    auth_layer_1_complete: bool
    auth_layer_2_complete: bool
    auth_layer_3_complete: bool
    is_active: bool
    roles: list[str] = []
    created_at: Optional[datetime] = None


class RoleUpdateRequest(BaseModel):
    role: str = Field(pattern=r"^(admin|operator|readonly)$")
    action: str = Field(pattern=r"^(grant|revoke)$")


class SecretCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1)
    description: Optional[str] = None


class SecretListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_by: str
    created_at: Optional[datetime] = None
    rotated_at: Optional[datetime] = None


class AuditLogEntry(BaseModel):
    id: str
    admin_username: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: Optional[datetime] = None


class ProductRegistryItem(BaseModel):
    id: str
    name: str
    current_version: Optional[str] = None
    connection_count: int
    last_connected_at: Optional[datetime] = None


class MCPServerItem(BaseModel):
    id: str
    name: str
    url: str
    transport: str
    auth_type: str
    capabilities: Optional[list[str]] = None
    status: str
    is_healthy: bool


class MCPCallRequest(BaseModel):
    server: str
    tool: str
    arguments: Optional[dict] = None


class SystemConfigItem(BaseModel):
    key: str
    value: str
    data_type: str
    description: Optional[str] = None


class PlatformStats(BaseModel):
    total_users: int
    active_users_today: int
    total_devices: int
    total_agents: int
    total_api_keys: int
    inference_calls_today: int
    total_webhooks: int
