"""
REFINET Cloud — Configuration
Pydantic Settings loads from .env with type validation.
"""

from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Core identity
    refinet_env: str = Field(default="development", alias="REFINET_ENV")
    refinet_domain: str = Field(default="localhost", alias="REFINET_DOMAIN")
    refinet_frontend_url: str = Field(default="http://localhost:4000", alias="REFINET_FRONTEND_URL")

    # Security
    secret_key: str = Field(..., alias="SECRET_KEY")
    refresh_secret: str = Field(..., alias="REFRESH_SECRET")
    server_pepper: str = Field(..., alias="SERVER_PEPPER")
    webhook_signing_key: str = Field(..., alias="WEBHOOK_SIGNING_KEY")
    internal_db_encryption_key: str = Field(..., alias="INTERNAL_DB_ENCRYPTION_KEY")
    admin_api_secret: str = Field(..., alias="ADMIN_API_SECRET")

    # JWT
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # Databases
    public_db_url: str = Field(
        default="sqlite:////opt/refinet/data/public.db",
        alias="PUBLIC_DB_URL"
    )
    internal_db_url: str = Field(
        default="sqlite:////opt/refinet/data/internal.db",
        alias="INTERNAL_DB_URL"
    )

    # ── Model Providers ─────────────────────────────────────────
    # BitNet (sovereign, Oracle Cloud)
    bitnet_host: str = Field(default="http://127.0.0.1:8080", alias="BITNET_HOST")

    # Google AI Studio / Gemini (empty = disabled)
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_models: str = Field(
        default="gemini-2.0-flash,gemini-2.5-flash,gemini-2.5-pro",
        alias="GEMINI_MODELS",
    )
    gemini_safety_threshold: str = Field(
        default="BLOCK_MEDIUM_AND_ABOVE",
        alias="GEMINI_SAFETY_THRESHOLD",
    )
    gemini_flash_rpm: int = Field(default=15, alias="GEMINI_FLASH_RPM")
    gemini_pro_rpm: int = Field(default=2, alias="GEMINI_PRO_RPM")
    gemini_flash_daily_limit: int = Field(default=1500, alias="GEMINI_FLASH_DAILY_LIMIT")
    gemini_pro_daily_limit: int = Field(default=50, alias="GEMINI_PRO_DAILY_LIMIT")

    # Ollama (empty = disabled)
    ollama_host: str = Field(default="", alias="OLLAMA_HOST")

    # LM Studio (empty = disabled)
    lmstudio_host: str = Field(default="", alias="LMSTUDIO_HOST")

    # OpenRouter (empty = disabled)
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")

    # Default model for inference when none specified
    default_model: str = Field(default="bitnet-b1.58-2b", alias="DEFAULT_MODEL")

    # Fallback chain (comma-separated provider types)
    provider_fallback_chain: str = Field(
        default="bitnet,gemini,ollama,lmstudio,openrouter",
        alias="PROVIDER_FALLBACK_CHAIN",
    )

    # Rate limits
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    free_tier_daily_requests: int = Field(default=250, alias="FREE_TIER_DAILY_REQUESTS")
    max_request_body_bytes: int = Field(default=10485760, alias="MAX_REQUEST_BODY_BYTES")

    # Anonymous (unauthenticated) inference limits
    anonymous_daily_requests: int = Field(default=25, alias="ANONYMOUS_DAILY_REQUESTS")
    anonymous_rate_per_minute: int = Field(default=5, alias="ANONYMOUS_RATE_PER_MINUTE")
    anonymous_max_tokens: int = Field(default=256, alias="ANONYMOUS_MAX_TOKENS")

    # SIWE — multi-chain
    siwe_domain: str = Field(default="api.refinet.io", alias="SIWE_DOMAIN")
    siwe_chain_id: int = Field(default=1, alias="SIWE_CHAIN_ID")
    siwe_statement: str = Field(
        default="Sign in to REFINET Cloud. Your Ethereum address is used as a cryptographic key component.",
        alias="SIWE_STATEMENT"
    )
    siwe_supported_chains: str = Field(
        default="1,137,42161,10,8453,11155111",
        alias="SIWE_SUPPORTED_CHAINS"
    )

    # Wallet identity
    wallet_email_domain: str = Field(default="cifi.global", alias="WALLET_EMAIL_DOMAIN")

    # SMTP bridge
    smtp_host: str = Field(default="127.0.0.1", alias="SMTP_HOST")
    smtp_port: int = Field(default=8025, alias="SMTP_PORT")
    smtp_enabled: bool = Field(default=True, alias="SMTP_ENABLED")

    # Platform admin wallet (owner address)
    admin_wallet: str = Field(
        default="0xE302932D42C751404AeD466C8929F1704BA89D5A",
        alias="ADMIN_WALLET",
    )

    # Product build keys
    quickcast_build_key: str = Field(default="", alias="QUICKCAST_BUILD_KEY")
    agentos_build_key: str = Field(default="", alias="AGENTOS_BUILD_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_production(self) -> bool:
        return self.refinet_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        if self.is_production:
            return [
                f"https://{self.refinet_domain}",
                self.refinet_frontend_url,
            ]
        # Development: explicit origins (wildcard "*" is rejected by browsers
        # when allow_credentials=True per the CORS spec)
        return [
            self.refinet_frontend_url,
            "http://localhost:4000",
            "http://127.0.0.1:4000",
        ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# ── YAML Config Hierarchy ─────────────────────────────────────────

_yaml_config_cache: Optional[dict] = None


def load_yaml_config() -> dict:
    """
    Load YAML configuration with merge hierarchy:
    configs/default.yaml → configs/production.yaml (if production) → ENV overrides.

    Returns merged config dict. Cached after first load.
    """
    global _yaml_config_cache
    if _yaml_config_cache is not None:
        return _yaml_config_cache

    from pathlib import Path

    config_dir = Path(__file__).resolve().parents[1] / "configs"
    config = {}

    # Load default.yaml
    default_path = config_dir / "default.yaml"
    if default_path.exists():
        config = _load_yaml_file(default_path)

    # Merge production.yaml if in production
    settings = get_settings()
    if settings.is_production:
        prod_path = config_dir / "production.yaml"
        if prod_path.exists():
            prod_config = _load_yaml_file(prod_path)
            config = _deep_merge(config, prod_config)

    _yaml_config_cache = config
    return config


def get_yaml_value(key_path: str, default=None):
    """
    Get a value from YAML config using dot-notation path.
    Example: get_yaml_value("groot.context_window", 2048)
    """
    config = load_yaml_config()
    keys = key_path.split(".")
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def _load_yaml_file(path) -> dict:
    """Load a YAML file, returning empty dict on failure."""
    try:
        import yaml
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # PyYAML not installed — parse basic YAML manually
        return _parse_basic_yaml(path)
    except Exception:
        return {}


def _parse_basic_yaml(path) -> dict:
    """Minimal YAML parser for flat/nested key-value pairs (no PyYAML needed)."""
    import re
    result = {}
    stack = [(result, -1)]

    try:
        with open(path, "r") as f:
            for line in f:
                stripped = line.rstrip()
                if not stripped or stripped.startswith("#"):
                    continue

                indent = len(line) - len(line.lstrip())
                match = re.match(r'^(\s*)([\w_-]+):\s*(.*)', line)
                if not match:
                    continue

                key = match.group(2)
                value = match.group(3).strip()

                # Pop stack to correct nesting level
                while len(stack) > 1 and stack[-1][1] >= indent:
                    stack.pop()

                parent = stack[-1][0]

                if value and not value.startswith("{") and not value.startswith("["):
                    # Scalar value
                    if value.lower() in ("true", "yes"):
                        parent[key] = True
                    elif value.lower() in ("false", "no"):
                        parent[key] = False
                    elif value.lower() == "null":
                        parent[key] = None
                    else:
                        try:
                            parent[key] = int(value)
                        except ValueError:
                            try:
                                parent[key] = float(value)
                            except ValueError:
                                parent[key] = value.strip('"').strip("'")
                elif not value:
                    # Nested dict
                    parent[key] = {}
                    stack.append((parent[key], indent))
    except Exception:
        pass

    return result


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
