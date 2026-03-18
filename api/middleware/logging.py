"""REFINET Cloud — Request/Response Structured Logging"""

import time
import logging
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("refinet.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)

        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "")[:100],
        }

        if response.status_code >= 400:
            logger.warning(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))

        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response
