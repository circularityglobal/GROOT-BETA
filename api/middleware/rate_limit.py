"""REFINET Cloud — Rate Limiting Middleware"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from api.config import get_settings


def _get_rate_key(request):
    """Use API key or IP for rate limiting."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer rf_"):
        return auth[7:19]  # first 12 chars of API key
    return get_remote_address(request)


settings = get_settings()
limiter = Limiter(
    key_func=_get_rate_key,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    storage_uri="memory://",
)
