"""Tests for the per-IP sliding-window rate limiter (app/middleware/rate_limit.py).

Most cases drive a tiny ok-app wrapped by a middleware instance configured with
a 3-request / 1-second window, so the real defaults never have to be exhausted.
The last section touches the wired app and always resets the shared limiter
afterwards so subsequent test files are not throttled.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from app.main import app as real_app
from app.middleware.body_limit import BodySizeLimitMiddleware
from app.middleware.rate_limit import (
    DEFAULT_EXEMPT_PATHS,
    MAX_TRACKED_IPS,
    RateLimitMiddleware,
)
from app.middleware.request_logging import RequestLoggingMiddleware

# Tiny budget so a burst is cheap to produce; the window is short enough that
# case (b) can wait it out without slowing the suite.
TEST_MAX_REQUESTS = 3
TEST_WINDOW_SECONDS = 1.0
# 1.0 s window + scheduling slack: sleeping this long must fully expire it.
WINDOW_EXPIRY_SLEEP_S = 1.1


async def ok_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Minimal ASGI app: always 200 with body 'ok'."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


def make_client(**kwargs) -> tuple[RateLimitMiddleware, TestClient]:
    """Wrap ok_app in a freshly-limited middleware; return both."""
    middleware = RateLimitMiddleware(
        ok_app, max_requests=TEST_MAX_REQUESTS, window_seconds=TEST_WINDOW_SECONDS
    )
    return middleware, TestClient(middleware, **kwargs)


# --- (a) budget is enforced -------------------------------------------------


def test_requests_within_budget_pass_then_429():
    _, client = make_client()
    for _ in range(TEST_MAX_REQUESTS):
        assert client.get("/anything").status_code == 200

    resp = client.get("/anything")
    assert resp.status_code == 429
    assert resp.json() == {"detail": "Too many requests — slow down"}
    assert int(resp.headers["retry-after"]) >= 1


def test_429_is_json_content_type():
    _, client = make_client()
    for _ in range(TEST_MAX_REQUESTS):
        client.get("/anything")
    assert client.get("/anything").headers["content-type"] == "application/json"


# --- (b) the window slides --------------------------------------------------


def test_window_expiry_restores_budget():
    _, client = make_client()
    for _ in range(TEST_MAX_REQUESTS):
        client.get("/anything")
    assert client.get("/anything").status_code == 429

    time.sleep(WINDOW_EXPIRY_SLEEP_S)
    assert client.get("/anything").status_code == 200


# --- (c) exemptions ---------------------------------------------------------


def test_health_is_never_throttled():
    _, client = make_client()
    for _ in range(TEST_MAX_REQUESTS * 5):
        assert client.get("/health").status_code == 200
    # Exempt hits are not counted, so the budget for other paths is intact.
    assert client.get("/anything").status_code == 200


def test_health_is_the_shipped_default_exemption():
    assert "/health" in DEFAULT_EXEMPT_PATHS


# --- (d) per-IP isolation ---------------------------------------------------


def test_clients_are_tracked_per_ip():
    middleware = RateLimitMiddleware(
        ok_app, max_requests=TEST_MAX_REQUESTS, window_seconds=TEST_WINDOW_SECONDS
    )
    noisy = TestClient(middleware, client=("1.2.3.4", 123))
    quiet = TestClient(middleware, client=("5.6.7.8", 456))

    for _ in range(TEST_MAX_REQUESTS):
        assert noisy.get("/anything").status_code == 200
    assert noisy.get("/anything").status_code == 429
    # A different IP is unaffected by the noisy one's exhausted budget.
    assert quiet.get("/anything").status_code == 200


def test_reset_clears_all_state():
    middleware, client = make_client()
    for _ in range(TEST_MAX_REQUESTS + 1):
        client.get("/anything")
    assert client.get("/anything").status_code == 429

    middleware.reset()
    assert client.get("/anything").status_code == 200


def test_non_http_scope_passes_through_untouched():
    seen: dict[str, object] = {}

    async def recording_app(scope: Scope, receive: Receive, send: Send) -> None:
        seen["scope"] = scope
        seen["receive"] = receive
        seen["send"] = send

    middleware = RateLimitMiddleware(recording_app)
    scope: Scope = {"type": "lifespan"}

    async def receive():  # pragma: no cover - never awaited
        return {"type": "lifespan.startup"}

    async def send(message):  # pragma: no cover - never awaited
        return None

    asyncio.run(middleware(scope, receive, send))
    assert seen["scope"] is scope
    assert seen["receive"] is receive
    assert seen["send"] is send


def test_overflow_cleanup_drops_expired_ips():
    """The MAX_TRACKED_IPS overflow path must evict expired buckets."""
    # window_seconds=0 makes every recorded hit immediately expired, so the
    # overflow sweep can reclaim the whole dict without any sleeping.
    middleware = RateLimitMiddleware(ok_app, max_requests=1, window_seconds=0.0)
    for index in range(MAX_TRACKED_IPS):
        middleware._register(f"10.0.{index // 256}.{index % 256}", time.monotonic())
    assert len(middleware._hits) == MAX_TRACKED_IPS

    middleware._register("192.168.1.1", time.monotonic())
    # Every prior bucket was expired, so only the new key survives.
    assert len(middleware._hits) == 1


# --- (e) the wired application ---------------------------------------------


def _stack_classes(application) -> list[str]:
    """Class names of the built middleware chain, outermost first."""
    node = application.middleware_stack
    names: list[str] = []
    while node is not None:
        names.append(type(node).__name__)
        node = getattr(node, "app", None)
    return names


def _wired_limiter(application) -> RateLimitMiddleware:
    """The RateLimitMiddleware instance inside the built stack."""
    node = application.middleware_stack
    while node is not None:
        if isinstance(node, RateLimitMiddleware):
            return node
        node = getattr(node, "app", None)
    raise AssertionError("RateLimitMiddleware is not wired into app.main.app")


@pytest.fixture()
def real_client():
    """Real-app client that leaves the shared limiter empty for other suites."""
    client = TestClient(real_app)
    client.get("/health")  # forces Starlette to build the middleware stack
    limiter = _wired_limiter(real_app)
    limiter.reset()
    try:
        yield client
    finally:
        limiter.reset()


def test_limiter_runs_outside_the_body_and_logging_middleware(real_client):
    """Execution order is asserted against the built stack, not assumed."""
    names = _stack_classes(real_app)
    assert names.index(RateLimitMiddleware.__name__) < names.index(
        BodySizeLimitMiddleware.__name__
    )
    assert names.index(BodySizeLimitMiddleware.__name__) < names.index(
        RequestLoggingMiddleware.__name__
    )


def test_real_app_health_is_never_throttled(real_client):
    # Well past DEFAULT_MAX_REQUESTS would still be fine: /health is exempt.
    for _ in range(60):
        assert real_client.get("/health").status_code == 200


def test_real_app_burst_is_eventually_refused(real_client):
    limiter = _wired_limiter(real_app)
    # Enforcement is off under pytest (see app/main.py): every TestClient
    # request shares one client IP, so a live limiter would 429 unrelated
    # suites. Turn it on for this test only, and restore it afterwards.
    limiter.enabled = True
    try:
        statuses = [real_client.get("/api/nonexistent").status_code for _ in range(130)]
    finally:
        limiter.enabled = False
    assert 429 in statuses
    # Everything before the first 429 was served normally (404, no route).
    assert statuses[0] == 404
    limiter.reset()
    assert real_client.get("/api/nonexistent").status_code == 404


def test_limiter_is_wired_but_disabled_under_pytest():
    """The production stack keeps the middleware; only enforcement is off here,
    so a future refactor that drops the limiter entirely still fails a test."""
    assert _wired_limiter(real_app).enabled is False
