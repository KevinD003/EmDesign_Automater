"""Access logging with per-request correlation ids.

Pure-ASGI middleware (no BaseHTTPMiddleware) so streaming responses are not
buffered. Each request gets an ``X-Request-ID``: the client's value if it is
well-formed, otherwise a freshly generated one. The id is echoed on the
response and stored in ``scope["state"]["request_id"]`` so error handlers can
read ``request.state.request_id``.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("stitchiq.access")

# Client-supplied X-Request-ID must be 1-64 chars of [A-Za-z0-9-]; anything
# else is replaced to keep logs injection-safe and headers bounded.
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")
# Generated ids use 12 hex chars: short enough for log lines, ~2^48 space is
# collision-safe for per-request correlation.
GENERATED_ID_LENGTH = 12

_REQUEST_ID_HEADER = b"x-request-id"


def _resolve_request_id(scope: Scope) -> str:
    """Return the client's X-Request-ID if valid, else a generated id."""
    for name, value in scope.get("headers", []):
        if name == _REQUEST_ID_HEADER:
            candidate = value.decode("latin-1")
            if REQUEST_ID_PATTERN.fullmatch(candidate):
                return candidate
            break
    return uuid.uuid4().hex[:GENERATED_ID_LENGTH]


class RequestLoggingMiddleware:
    """Attach a request id and emit one access-log line per request.

    Logging is best-effort: bookkeeping failures are swallowed so they never
    mask the app's response, while app exceptions propagate unchanged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append(
                    (b"X-Request-ID", request_id.encode("latin-1"))
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Log path only — never the query string or body, which may
            # contain user data (uploads, emails, design names).
            try:
                duration_ms = (time.perf_counter() - start) * 1000
                client = scope.get("client")
                logger.info(
                    "%s %s %d %.1fms %s %s",
                    scope.get("method", "-"),
                    scope.get("path", "-"),
                    status_code,
                    duration_ms,
                    client[0] if client else "-",
                    request_id,
                )
            except Exception:  # noqa: BLE001, S110  # pragma: no cover
                # Intentional blind catch: access-log bookkeeping must never
                # mask or alter the app's response.
                pass
