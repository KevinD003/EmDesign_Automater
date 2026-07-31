"""Per-IP request rate limiting with a sliding window.

Pure-ASGI middleware (no BaseHTTPMiddleware, so responses are never buffered).
State is a per-process, in-memory ``dict[ip, deque[timestamp]]`` — sufficient
for the single-process LAN deployment this backend targets; it is deliberately
not shared across workers.

Timestamps come from ``time.monotonic()`` so wall-clock adjustments (NTP, DST)
cannot widen or collapse a window. The dict is guarded by a ``threading.Lock``
because TestClient and uvicorn both drive the app from several threads.
"""

from __future__ import annotations

import json
import math
import threading
import time
from collections import deque
from collections.abc import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

# 120 requests / 10 s = 12 req/s sustained per IP. Far above human clicking and
# above the frontend's parallel fetch bursts, but low enough that a runaway
# script cannot saturate the LAN deployment.
DEFAULT_MAX_REQUESTS = 120
DEFAULT_WINDOW_SECONDS = 10.0

# Monitoring must never be throttled: a probe that gets 429 reads as an outage.
DEFAULT_EXEMPT_PATHS = frozenset({"/health"})

# Bounds memory under IP churn or spoofed source addresses: 10k tracked IPs is
# ~100x the expected LAN population and costs a few MB at worst.
MAX_TRACKED_IPS = 10_000

# Retry-After is an integer number of seconds and must be >= 1; 0 would invite
# an immediate retry, which is exactly what the limiter is refusing.
MIN_RETRY_AFTER_SECONDS = 1

# Clients with no address in the scope (in-process ASGI calls) share one
# bucket rather than going unmetered.
UNKNOWN_CLIENT_KEY = "unknown"

# Peers whose X-Forwarded-For we believe: the loopback addresses a same-host
# reverse proxy (Vite dev/preview) connects from. A forwarded header from any
# other peer is attacker-controlled and is ignored.
TRUSTED_PROXY_PEERS = frozenset({"127.0.0.1", "::1", "localhost", UNKNOWN_CLIENT_KEY})

_RESPONSE_BODY = json.dumps({"detail": "Too many requests — slow down"}).encode("utf-8")


class RateLimitMiddleware:
    """Refuse requests from an IP that exceeds ``max_requests`` per window."""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        exempt_paths: Iterable[str] = DEFAULT_EXEMPT_PATHS,
        enabled: bool = True,
    ) -> None:
        self.app = app
        # Enforcement toggle (v2 Part 20). The middleware stays WIRED even when
        # disabled so the stack-ordering assertions still guard the production
        # arrangement; only counting and refusal are skipped. app.main disables
        # it under pytest, where every TestClient request shares one client IP
        # and a fast suite would otherwise trip the shared window and fail
        # unrelated tests with 429.
        self.enabled = enabled
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exempt_paths = frozenset(exempt_paths)
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Drop all tracked history (tests; also usable as an ops escape hatch)."""
        with self._lock:
            self._hits.clear()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only HTTP requests are metered; websocket/lifespan pass through.
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        if scope.get("path") in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        retry_after = self._register(self._client_key(scope), time.monotonic())
        if retry_after is not None:
            await self._send_429(send, retry_after)
            return

        await self.app(scope, receive, send)

    def _client_key(self, scope: Scope) -> str:
        """Per-client bucket key: the real caller, not the proxy (v2 Part 21).

        The documented launch topology puts Vite in front proxying /api, so
        EVERY user reaches the backend as 127.0.0.1. Keying on the raw peer
        therefore put ~100 users in ONE bucket — 12 req/s for the whole
        deployment, verified as widespread 429s under normal browsing.

        The session token (when present) identifies the actual account and is
        the most accurate key. Otherwise the leftmost X-Forwarded-For entry is
        used when the peer is a trusted local proxy; a forwarded header from a
        NON-local peer is ignored, since anyone could spoof it to get a fresh
        bucket per request and defeat the limiter entirely.
        """
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode("latin-1")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token:
                return f"tok:{token[:32]}"
        client = scope.get("client")
        peer = client[0] if client else UNKNOWN_CLIENT_KEY
        if peer in TRUSTED_PROXY_PEERS:
            fwd = headers.get(b"x-forwarded-for", b"").decode("latin-1")
            first = fwd.split(",")[0].strip()
            if first:
                return f"ip:{first}"
        return f"ip:{peer}"

    def _register(self, key: str, now: float) -> int | None:
        """Record a hit for ``key``; return Retry-After seconds if over budget.

        Returning None means the request is allowed and has been counted.
        """
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                # Cleanup runs only on the overflow path — the steady state
                # stays O(1) per request.
                if len(self._hits) >= MAX_TRACKED_IPS:
                    self._evict_expired(cutoff)
                hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                wait_seconds = self.window_seconds - (now - hits[0])
                return max(MIN_RETRY_AFTER_SECONDS, math.ceil(wait_seconds))
            hits.append(now)
            return None

    def _evict_expired(self, cutoff: float) -> None:
        """Drop IPs whose entire window has expired. Caller holds the lock."""
        stale = [ip for ip, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for ip in stale:
            del self._hits[ip]

    async def _send_429(self, send: Send, retry_after: int) -> None:
        """Emit the complete 429 JSON response."""
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_RESPONSE_BODY)).encode("latin-1")),
                    (b"retry-after", str(retry_after).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _RESPONSE_BODY})
