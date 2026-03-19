"""
REFINET Cloud — Platform Config Defaults
Seeds default SystemConfig values on startup.
Admin can override these via PUT /admin/system/config.
"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.config_defaults")

# Default platform configuration values
# These are seeded into the SystemConfig table in internal.db on startup.
# Admin can change any value at runtime via the admin dashboard.

DEFAULTS = [
    # Knowledge base quotas
    {
        "key": "knowledge.max_documents_per_user",
        "value": "10",
        "data_type": "integer",
        "description": "Maximum number of documents a user can upload to their private knowledge base",
    },
    {
        "key": "knowledge.max_file_size_mb",
        "value": "50",
        "data_type": "integer",
        "description": "Maximum file size in MB for document uploads",
    },
    {
        "key": "knowledge.max_total_storage_mb",
        "value": "500",
        "data_type": "integer",
        "description": "Maximum total storage per user in MB across all documents",
    },
    {
        "key": "knowledge.allowed_file_types",
        "value": "pdf,docx,xlsx,csv,txt,md,json,sol",
        "data_type": "string",
        "description": "Comma-separated list of allowed file extensions for document upload",
    },
    # Platform global settings
    {
        "key": "platform.maintenance_mode",
        "value": "false",
        "data_type": "boolean",
        "description": "When true, only admins can access the platform",
    },
    {
        "key": "platform.allow_user_uploads",
        "value": "true",
        "data_type": "boolean",
        "description": "When false, only admins can upload documents",
    },
    {
        "key": "platform.allow_public_documents",
        "value": "true",
        "data_type": "boolean",
        "description": "When false, users cannot make documents public (MCP-visible)",
    },
    {
        "key": "platform.max_users",
        "value": "0",
        "data_type": "integer",
        "description": "Maximum number of platform users (0 = unlimited)",
    },
    # Oracle server (future)
    {
        "key": "oracle.storage_per_user_gb",
        "value": "1",
        "data_type": "integer",
        "description": "Storage allocation per user in GB when Oracle server is live",
    },
    {
        "key": "oracle.enabled",
        "value": "false",
        "data_type": "boolean",
        "description": "Whether Oracle cloud storage is active (future)",
    },
    # Messenger integrations
    {
        "key": "messenger.telegram_bot_token",
        "value": "",
        "data_type": "string",
        "description": "Telegram Bot API token from @BotFather. Required for /webhooks/telegram endpoint.",
    },
    {
        "key": "messenger.telegram_webhook_secret",
        "value": "",
        "data_type": "string",
        "description": "Secret token for verifying incoming Telegram webhook requests (optional).",
    },
    {
        "key": "messenger.whatsapp_api_token",
        "value": "",
        "data_type": "string",
        "description": "WhatsApp Cloud API access token. Required for /webhooks/whatsapp endpoint.",
    },
    {
        "key": "messenger.whatsapp_verify_token",
        "value": "",
        "data_type": "string",
        "description": "WhatsApp webhook verification token (used during GET /webhooks/whatsapp handshake).",
    },
    {
        "key": "messenger.whatsapp_phone_number_id",
        "value": "",
        "data_type": "string",
        "description": "WhatsApp Business phone number ID for sending replies.",
    },
    # Chain listener
    {
        "key": "chain.polling_enabled",
        "value": "true",
        "data_type": "boolean",
        "description": "Enable/disable on-chain event polling globally.",
    },
    {
        "key": "chain.default_polling_interval",
        "value": "30",
        "data_type": "integer",
        "description": "Default polling interval in seconds for chain watchers.",
    },
]


def seed_config_defaults(int_db: Session):
    """
    Seed default config values into SystemConfig.
    Only inserts if key doesn't already exist (preserves admin overrides).
    """
    from api.models.internal import SystemConfig

    seeded = 0
    for default in DEFAULTS:
        existing = int_db.query(SystemConfig).filter(
            SystemConfig.key == default["key"],
        ).first()
        if existing:
            continue

        config = SystemConfig(
            key=default["key"],
            value=default["value"],
            data_type=default["data_type"],
            description=default["description"],
        )
        int_db.add(config)
        seeded += 1

    if seeded > 0:
        int_db.commit()
        logger.info(f"Seeded {seeded} default config values")


def get_config_value(int_db: Session, key: str, default: str = "") -> str:
    """Read a config value from SystemConfig. Returns default if not found."""
    from api.models.internal import SystemConfig
    config = int_db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return config.value if config else default


def get_config_int(int_db: Session, key: str, default: int = 0) -> int:
    """Read an integer config value."""
    val = get_config_value(int_db, key, str(default))
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_config_bool(int_db: Session, key: str, default: bool = False) -> bool:
    """Read a boolean config value."""
    val = get_config_value(int_db, key, str(default).lower())
    return val.lower() in ("true", "1", "yes")
