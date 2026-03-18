"""
REFINET Cloud — In-Process Event Bus
Lightweight pub/sub for decoupling registry mutations from WebSocket and webhook delivery.
No external dependencies (no Redis/RabbitMQ) — single-process deployment.
"""

import asyncio
import fnmatch
import logging
from collections import defaultdict
from typing import Callable, Any, Awaitable

logger = logging.getLogger(__name__)


class EventBus:
    """Singleton in-process event bus with wildcard pattern matching."""

    _instance = None

    def __init__(self):
        self._handlers: dict[str, list[Callable[[str, dict], Awaitable[None]]]] = defaultdict(list)

    @classmethod
    def get(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None

    def subscribe(self, pattern: str, handler: Callable[[str, dict], Awaitable[None]]):
        """
        Subscribe to events matching a pattern.
        Supports wildcards: "registry.*" matches "registry.project.created", etc.
        Use "*" for all events.
        """
        self._handlers[pattern].append(handler)

    def unsubscribe(self, pattern: str, handler: Callable):
        """Remove a specific handler from a pattern."""
        if pattern in self._handlers:
            self._handlers[pattern] = [h for h in self._handlers[pattern] if h != handler]

    async def publish(self, event: str, data: dict):
        """
        Publish an event. All matching handlers run as background tasks.
        Errors in handlers are logged but never propagate to the publisher.
        """
        matched_handlers = []

        for pattern, handlers in self._handlers.items():
            if pattern == "*" or fnmatch.fnmatch(event, pattern):
                matched_handlers.extend(handlers)

        for handler in matched_handlers:
            try:
                asyncio.create_task(_safe_call(handler, event, data))
            except Exception as e:
                logger.error(f"EventBus: failed to schedule handler for {event}: {e}")


async def _safe_call(handler: Callable, event: str, data: dict):
    """Call handler with error isolation."""
    try:
        await handler(event, data)
    except Exception as e:
        logger.error(f"EventBus handler error for {event}: {e}")
