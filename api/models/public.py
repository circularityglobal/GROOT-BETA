"""
REFINET Cloud — Public Database Models
All tables in public.db (user-facing data).
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(PublicBase):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=new_uuid)
    email = Column(String, unique=True, nullable=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    email_salt = Column(String, nullable=True)
    tier = Column(String, default="free")  # free | developer | pro | admin
    eth_address = Column(String, unique=True, nullable=True)
    eth_address_hash = Column(String, nullable=True)
    totp_secret = Column(String, nullable=True)  # AES-256-GCM encrypted
    totp_enabled = Column(Boolean, default=False)
    siwe_enabled = Column(Boolean, default=False)
    auth_layer_1_complete = Column(Boolean, default=False)
    auth_layer_2_complete = Column(Boolean, default=False)
    auth_layer_3_complete = Column(Boolean, default=False)
    is_custodial_wallet = Column(Boolean, default=False)
    primary_chain_id = Column(Integer, default=1)       # chain used for first SIWE auth
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    last_login_at = Column(DateTime, nullable=True)


class ApiKey(PublicBase):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    key_hash = Column(String, unique=True, nullable=False, index=True)
    key_prefix = Column(String, nullable=False)
    name = Column(String, nullable=False)
    scopes = Column(String, default="")  # space-separated scope list
    is_active = Column(Boolean, default=True)
    daily_limit = Column(Integer, default=250)
    requests_today = Column(Integer, default=0)
    last_reset_date = Column(String, nullable=True)  # YYYY-MM-DD for daily counter reset
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)


class DeviceRegistration(PublicBase):
    __tablename__ = "device_registrations"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    device_type = Column(String, nullable=False)  # iot | plc | dlt | agent | webhook | api
    eth_address = Column(String, unique=True, nullable=True)
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    telemetry_count = Column(Integer, default=0)
    status = Column(String, default="active")  # active | suspended | deregistered
    device_metadata = Column(Text, nullable=True)  # JSON blob
    created_at = Column(DateTime, server_default=func.now())


class AgentRegistration(PublicBase):
    __tablename__ = "agent_registrations"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    product = Column(String, nullable=False)
    eth_address = Column(String, unique=True, nullable=True)
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)
    version = Column(String, nullable=True)
    config = Column(Text, nullable=True)  # JSON remote config blob
    last_connected_at = Column(DateTime, nullable=True)
    total_inference_calls = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class IoTTelemetry(PublicBase):
    __tablename__ = "iot_telemetry"

    id = Column(String, primary_key=True, default=new_uuid)
    device_id = Column(String, ForeignKey("device_registrations.id"), nullable=False, index=True)
    payload = Column(Text, nullable=False)  # JSON telemetry blob
    signature = Column(String, nullable=True)  # optional ECDSA signature
    received_at = Column(DateTime, server_default=func.now())
    processed = Column(Boolean, default=False)


class WebhookSubscription(PublicBase):
    __tablename__ = "webhook_subscriptions"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String, ForeignKey("device_registrations.id"), nullable=True)
    url = Column(String, nullable=False)
    secret_hash = Column(String, nullable=False)
    events = Column(Text, nullable=False)  # JSON array of event names
    is_active = Column(Boolean, default=True)
    failure_count = Column(Integer, default=0)
    last_delivery_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class UsageRecord(PublicBase):
    __tablename__ = "usage_records"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)
    device_id = Column(String, ForeignKey("device_registrations.id"), nullable=True)
    model = Column(String, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    endpoint = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class SIWENonce(PublicBase):
    __tablename__ = "siwe_nonces"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, nullable=True)
    nonce = Column(String, unique=True, nullable=False, index=True)
    issued_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    is_used = Column(Boolean, default=False)


class RefreshToken(PublicBase):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    issued_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
    replaced_by = Column(String, nullable=True)


class WalletIdentity(PublicBase):
    """
    Per-chain wallet identity record.
    A single user can have wallets linked across multiple chains.
    The primary_chain_id is the chain they first authenticated on.
    """
    __tablename__ = "wallet_identities"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    eth_address = Column(String, nullable=False, index=True)
    chain_id = Column(Integer, nullable=False)
    chain_name = Column(String, nullable=False)
    is_primary = Column(Boolean, default=False)

    # Wallet-derived identity fields
    pseudo_ipv6 = Column(String, nullable=True)       # deterministic IPv6 from wallet+chain
    subnet_prefix = Column(String, nullable=True)     # chain-specific /48 subnet
    interface_id = Column(String, nullable=True)       # wallet-specific /80 suffix
    ens_name = Column(String, nullable=True)           # resolved ENS name (cached)
    ens_avatar = Column(String, nullable=True)         # resolved ENS avatar URL
    ens_description = Column(String, nullable=True)    # ENS text record: description
    ens_url = Column(String, nullable=True)            # ENS text record: url
    ens_twitter = Column(String, nullable=True)        # ENS text record: com.twitter
    ens_github = Column(String, nullable=True)         # ENS text record: com.github
    ens_email = Column(String, nullable=True)            # ENS text record: email
    ens_resolved_at = Column(DateTime, nullable=True)  # last ENS resolution timestamp
    display_name = Column(String, nullable=True)       # user-chosen or ENS-derived
    email_alias = Column(String, nullable=True)        # wallet-derived email (e.g. 0xAb12@cifi.global)
    public_key = Column(String, nullable=True)         # secp256k1 public key (for E2EE)

    # Messaging permissions
    xmtp_enabled = Column(Boolean, default=False)
    messaging_permissions = Column(Text, nullable=True)  # JSON: {allow_dm, allow_group, blocklist}

    # Metadata
    verified_at = Column(DateTime, nullable=True)
    last_active_chain_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class WalletSession(PublicBase):
    """
    Device-aware login session tracking.
    Each SIWE sign-in creates a session record for audit + multi-device support.
    """
    __tablename__ = "wallet_sessions"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    wallet_identity_id = Column(String, ForeignKey("wallet_identities.id"), nullable=True)
    chain_id = Column(Integer, nullable=False, default=1)
    eth_address = Column(String, nullable=False)

    # Device fingerprint
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    device_label = Column(String, nullable=True)       # e.g. "Chrome on macOS"

    # Session state
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


# ── Messaging Models ─────────────────────────────────────────────────

class Conversation(PublicBase):
    """
    A conversation between two or more wallets.
    Supports DMs (2 participants) and group chats (3+).
    """
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=new_uuid)
    title = Column(String, nullable=True)               # group name (null for DMs)
    is_group = Column(Boolean, default=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    last_message_at = Column(DateTime, nullable=True)
    last_message_preview = Column(String, nullable=True)  # first 100 chars
    created_at = Column(DateTime, server_default=func.now())


class ConversationParticipant(PublicBase):
    """
    Tracks participants in a conversation with per-user read state.
    """
    __tablename__ = "conversation_participants"

    id = Column(String, primary_key=True, default=new_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    eth_address = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    role = Column(String, default="member")             # member | admin | owner
    last_read_at = Column(DateTime, nullable=True)
    is_muted = Column(Boolean, default=False)
    joined_at = Column(DateTime, server_default=func.now())


class Message(PublicBase):
    """
    A message in a conversation. Supports text, metadata, and reply threads.
    Content is stored in plaintext for now — E2EE will encrypt before storage.
    """
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=new_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    sender_address = Column(String, nullable=False)

    # Content
    content = Column(Text, nullable=False)
    content_type = Column(String, default="text")       # text | attachment | system
    extra_data = Column(Text, nullable=True)            # JSON: attachments, reactions, etc.

    # Threading
    reply_to_id = Column(String, ForeignKey("messages.id"), nullable=True)

    # State
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class EmailAlias(PublicBase):
    """
    Wallet-derived email alias registry.
    Maps email addresses to wallet addresses for the SMTP bridge.
    """
    __tablename__ = "email_aliases"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    eth_address = Column(String, nullable=False, index=True)
    email_alias = Column(String, unique=True, nullable=False, index=True)  # e.g. 742d35cc@cifi.global
    custom_alias = Column(String, unique=True, nullable=True, index=True)  # e.g. alice@cifi.global
    ens_alias = Column(String, unique=True, nullable=True, index=True)     # e.g. alice.eth@cifi.global
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
