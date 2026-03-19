"""
REFINET Cloud — Gemini Free-Tier Rate Limiter
Token-bucket per model with daily counters.
Thread-safe for concurrent FastAPI requests.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ModelBucket:
    """Per-model rate state."""
    tokens: float
    max_tokens: float
    refill_rate: float       # tokens per second (rpm / 60)
    last_refill: float       # time.monotonic()
    daily_count: int = 0
    daily_limit: int = 1500
    daily_date: str = ""     # YYYY-MM-DD for reset


class GeminiRateLimiter:
    """
    Singleton rate limiter for Gemini models.
    Uses token bucket for RPM and a daily counter.
    """

    _instance: Optional["GeminiRateLimiter"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._buckets: dict[str, ModelBucket] = {}
        self._bucket_lock = threading.Lock()

    @classmethod
    def get(cls) -> "GeminiRateLimiter":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    def _get_bucket(self, model: str) -> ModelBucket:
        if model not in self._buckets:
            # Load limits from settings
            try:
                from api.config import get_settings
                settings = get_settings()
                if "pro" in model.lower():
                    rpm = getattr(settings, "gemini_pro_rpm", 2)
                    daily = getattr(settings, "gemini_pro_daily_limit", 50)
                else:
                    rpm = getattr(settings, "gemini_flash_rpm", 15)
                    daily = getattr(settings, "gemini_flash_daily_limit", 1500)
            except Exception:
                rpm = 15 if "pro" not in model.lower() else 2
                daily = 1500 if "pro" not in model.lower() else 50

            self._buckets[model] = ModelBucket(
                tokens=float(rpm),
                max_tokens=float(rpm),
                refill_rate=rpm / 60.0,
                last_refill=time.monotonic(),
                daily_limit=daily,
            )
        return self._buckets[model]

    def acquire(self, model: str) -> tuple[bool, Optional[float]]:
        """
        Try to acquire a request slot.
        Returns (allowed, retry_after_seconds).
        """
        with self._bucket_lock:
            bucket = self._get_bucket(model)
            now = time.monotonic()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # Daily counter reset
            if bucket.daily_date != today:
                bucket.daily_date = today
                bucket.daily_count = 0

            # Check daily limit
            if bucket.daily_count >= bucket.daily_limit:
                return False, None  # No retry — daily exhausted

            # Refill token bucket
            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                bucket.max_tokens,
                bucket.tokens + elapsed * bucket.refill_rate,
            )
            bucket.last_refill = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                bucket.daily_count += 1
                return True, None
            else:
                wait = (1.0 - bucket.tokens) / bucket.refill_rate
                return False, wait

    def get_status(self, model: str) -> dict:
        """Return current rate limit status for monitoring."""
        with self._bucket_lock:
            bucket = self._get_bucket(model)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            daily_remaining = max(0, bucket.daily_limit - bucket.daily_count) \
                if bucket.daily_date == today else bucket.daily_limit
            return {
                "model": model,
                "rpm_available": round(bucket.tokens, 1),
                "rpm_limit": int(bucket.max_tokens),
                "daily_used": bucket.daily_count if bucket.daily_date == today else 0,
                "daily_limit": bucket.daily_limit,
                "daily_remaining": daily_remaining,
            }
