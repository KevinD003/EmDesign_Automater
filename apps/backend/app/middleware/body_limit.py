"""Reject oversized request bodies with 413 before they reach the app.

Pure-ASGI middleware (no BaseHTTPMiddleware, so responses are never buffered).
Two enforcement paths:

* Fast path — a ``Content-Length`` header over the limit is refused
  immediately, without reading a single body byte.
* Streaming path — chunked / missing ``Content-Length`` bodies are counted
  as they arrive; once over the limit the middleware answers 413 itself and
  feeds the app ``http.disconnect`` so it stops reading.
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Generous cap for photo uploads to /api/digitize; protects a 100-user LAN
# deployment from accidental multi-GB posts.
DEFAULT_MAX_BODY_BYTES = 25 * 1024 * 1024

# Unit divisors for the human-readable limit in the 413 message.
BYTES_PER_MIB = 1024 * 1024
BYTES_PER_KIB = 1024

_CONTENT_LENGTH_HEADER = b"content-length"


def _human_size(num_bytes: int) -> str:
    """Render a byte count for the 413 detail message (e.g. '25 MB')."""
    if num_bytes >= BYTES_PER_MIB and num_bytes % BYTES_PER_MIB == 0:
        return f"{num_bytes // BYTES_PER_MIB} MB"
    if num_bytes >= BYTES_PER_KIB and num_bytes % BYTES_PER_KIB == 0:
        return f"{num_bytes // BYTES_PER_KIB} KB"
    return f"{num_bytes} bytes"


def _declared_content_length(scope: Scope) -> int | None:
    """Parse the request's Content-Length header, or None if absent/invalid.

    An invalid value is not rejected here — the streaming counter still
    enforces the limit on whatever bytes actually arrive.
    """
    for name, value in scope.get("headers", []):
        if name == _CONTENT_LENGTH_HEADER:
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodySizeLimitMiddleware:
    """Cap request body size; oversized requests get a JSON 413."""

    def __init__(self, app: ASGIApp, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        # Message derives its size from the configured limit so the two can
        # never drift apart.
        detail = f"Request body too large (limit {_human_size(max_body_bytes)})"
        self._response_body = json.dumps({"detail": detail}).encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only HTTP requests carry bodies we cap; websocket/lifespan pass
        # through untouched.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _declared_content_length(scope)
        if declared is not None and declared > self.max_body_bytes:
            await self._send_413(send)
            return

        await self._call_counting_body(scope, receive, send)

    async def _call_counting_body(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the app while metering body bytes; 413 once over the limit."""
        received = 0
        response_started = False
        sent_413 = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if sent_413:
                # We already answered 413; drop the app's late response so
                # the client never sees two responses.
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def receive_wrapper() -> Message:
            nonlocal received, sent_413
            message = await receive()
            if message["type"] != "http.request":
                return message
            received += len(message.get("body", b""))
            if received <= self.max_body_bytes:
                return message
            # Over the limit: answer 413 unless the app already started its
            # own response, then starve the app with a disconnect.
            if not response_started and not sent_413:
                sent_413 = True
                await self._send_413(send)
            return {"type": "http.disconnect"}

        await self.app(scope, receive_wrapper, send_wrapper)

    async def _send_413(self, send: Send) -> None:
        """Emit the complete 413 JSON response."""
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(self._response_body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": self._response_body})
