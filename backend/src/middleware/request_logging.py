"""Request logging middleware — assigns request IDs and logs timing.

Uses pure ASGI middleware (not BaseHTTPMiddleware) to avoid ExceptionGroup
issues with Starlette's TaskGroup-based BaseHTTPMiddleware.
"""

import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.logger import get_logger

log = get_logger("middleware.request")

# Paths to skip logging (noisy health probes)
_SKIP_LOG_PATHS = frozenset({"/api/health/live"})

# Scope key for request ID — avoids State wrapper version issues
REQUEST_ID_KEY = "_request_id"


class RequestMiddleware:
    """Pure ASGI middleware for request ID assignment and access logging."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate request ID
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode() or uuid4().hex[:12]

        # Store on scope directly (read via request.scope["_request_id"])
        scope[REQUEST_ID_KEY] = request_id

        start = time.monotonic()
        status_code = 500  # default if response never starts

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                hdrs = list(message.get("headers", []))
                hdrs.append((b"x-request-id", request_id.encode()))
                message["headers"] = hdrs
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            path = scope.get("path", "")
            if path not in _SKIP_LOG_PATHS:
                method = scope.get("method", "?")
                log.info(
                    "%s %s %d %.1fms [%s]",
                    method,
                    path,
                    status_code,
                    duration_ms,
                    request_id,
                )
