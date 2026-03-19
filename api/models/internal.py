"""
REFINET Cloud — Internal Database Models
All tables in internal.db (admin-only, NEVER exposed via public API).
"""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from api.database import InternalBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class ServerSecret(InternalBase):
    __tablename__ = "server_secrets"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, unique=True, nullable=False, index=True)
    encrypted_value = Column(String, nullable=False)  # AES-256-GCM
    description = Column(Text, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    rotated_at = Column(DateTime, nullable=True)


class RoleAssignment(InternalBase):
    __tablename__ = "role_assignments"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, nullable=False, index=True)  # references public.users.id
    role = Column(String, nullable=False)  # admin | operator | readonly
    granted_by = Column(String, nullable=False)
    granted_at = Column(DateTime, server_default=func.now())
    revoked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)


class AdminAuditLog(InternalBase):
    """Append-only audit log. No updates, no deletes — ever."""
    __tablename__ = "admin_audit_log"

    id = Column(String, primary_key=True, default=new_uuid)
    admin_username = Column(String, nullable=False)
    action = Column(String, nullable=False)  # GRANT_ROLE, REVOKE_KEY, READ_SECRET, etc.
    target_type = Column(String, nullable=False)  # user | key | secret | device | config
    target_id = Column(String, nullable=True)
    details = Column(Text, nullable=True)  # JSON blob with before/after state
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())


class ProductRegistry(InternalBase):
    __tablename__ = "product_registry"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, unique=True, nullable=False)
    build_key_hash = Column(String, nullable=False)
    current_version = Column(String, nullable=True)
    connection_count = Column(Integer, default=0)
    last_connected_at = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)


class MCPServerRegistry(InternalBase):
    __tablename__ = "mcp_server_registry"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, unique=True, nullable=False, index=True)
    url = Column(String, nullable=False)
    transport = Column(String, nullable=False)  # http | stdio | sse
    auth_type = Column(String, default="none")  # none | api_key | oauth
    auth_value = Column(String, nullable=True)  # encrypted if auth required
    capabilities = Column(Text, nullable=True)  # JSON array of tool names
    status = Column(String, default="active")
    registered_at = Column(DateTime, server_default=func.now())
    last_health_check_at = Column(DateTime, nullable=True)
    is_healthy = Column(Boolean, default=True)


class SystemConfig(InternalBase):
    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    data_type = Column(String, default="string")  # string | integer | boolean | json
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now())
    updated_by = Column(String, nullable=True)


class HealthCheckLog(InternalBase):
    """System health check records for uptime tracking."""
    __tablename__ = "health_check_logs"

    id = Column(String, primary_key=True, default=new_uuid)
    timestamp = Column(DateTime, server_default=func.now())
    inference_ok = Column(Boolean, nullable=False)
    inference_latency_ms = Column(Integer, nullable=True)
    database_ok = Column(Boolean, nullable=False)
    smtp_ok = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)


class CustodialWallet(InternalBase):
    """
    Server-managed EVM wallet. Private key is never stored —
    only Shamir shares (encrypted) in the WalletShare table.
    """
    __tablename__ = "custodial_wallets"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, nullable=False, unique=True, index=True)  # references public.users.id
    eth_address = Column(String, nullable=False, unique=True, index=True)
    eth_address_hash = Column(String, nullable=False)  # HMAC for lookups
    share_count = Column(Integer, nullable=False, default=5)
    threshold = Column(Integer, nullable=False, default=3)
    chain_id = Column(Integer, nullable=False, default=1)
    encryption_salt = Column(String, nullable=False)  # 32-byte hex, per-wallet HKDF salt
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    last_signing_at = Column(DateTime, nullable=True)


class ScheduledTask(InternalBase):
    """Configurable scheduled tasks — replaces hardcoded asyncio.sleep loops."""
    __tablename__ = "scheduled_tasks"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, unique=True, nullable=False, index=True)
    task_type = Column(String, nullable=False)           # interval | cron | once
    schedule = Column(String, nullable=False)            # seconds for interval, cron expression for cron
    handler_path = Column(String, nullable=False)        # dotted path: api.services.rag.backfill_embeddings
    handler_args = Column(Text, nullable=True)           # JSON arguments
    is_enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_result = Column(String, nullable=True)          # success | error
    last_error = Column(Text, nullable=True)
    run_count = Column(Integer, default=0)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class ScriptExecution(InternalBase):
    """Tracks execution of admin/agent scripts."""
    __tablename__ = "script_executions"

    id = Column(String, primary_key=True, default=new_uuid)
    script_name = Column(String, nullable=False, index=True)
    args_json = Column(Text, nullable=True)
    status = Column(String, default="pending")           # pending | running | completed | failed
    output = Column(Text, nullable=True)                 # stdout
    error = Column(Text, nullable=True)                  # stderr
    started_by = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)


class WalletShare(InternalBase):
    """Individual AES-256-GCM encrypted Shamir share."""
    __tablename__ = "wallet_shares"

    id = Column(String, primary_key=True, default=new_uuid)
    wallet_id = Column(String, ForeignKey("custodial_wallets.id"), nullable=False, index=True)
    share_index = Column(Integer, nullable=False)  # 1..share_count
    encrypted_share = Column(Text, nullable=False)  # base64(nonce + ciphertext + tag)
    created_at = Column(DateTime, server_default=func.now())
