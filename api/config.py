"""
REFINET Cloud — Configuration
Pydantic Settings loads from .env with type validation.
"""

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

    # BitNet
    bitnet_host: str = Field(default="http://127.0.0.1:8080", alias="BITNET_HOST")

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
