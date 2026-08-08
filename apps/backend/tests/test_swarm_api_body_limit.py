"""BodySizeLimitMiddleware: 413 on oversized bodies, no effect otherwise."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from app.main import app
from app.middleware.body_limit import BodySizeLimitMiddleware

FIXTURES = Path(__file__).parent / "fixtures"

# Tiny limit keeps the hermetic tests fast — no multi-MB allocations needed
# to cross it.
TEST_LIMIT_BYTES = 1024
# Streaming test sends 10 x 256 B = 2560 B, comfortably over TEST_LIMIT_BYTES.
CHUNK_SIZE = 256
CHUNK_COUNT = 10
# Declared-only size for the fast path: never allocated, just announced in the
# Content-Length header, so it can exceed DEFAULT_MAX_BODY_BYTES for free.
DECLARED_HUGE_BYTES = 100 * 1024 * 1024


async def _echo_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Minimal ASGI app: drains the body and answers 200 with its length."""
    assert scope["type"] == "http"
    total = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            # Disconnect: the middleware already responded on our behalf.
            return
        total += len(message.get("body", b""))
        if not message.get("more_body", False):
            break
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": str(total).encode()})


def _limited_client() -> TestClient:
    return TestClient(BodySizeLimitMiddleware(_echo_app, max_body_bytes=TEST_LIMIT_BYTES))


def test_files_parse_fixture_still_succeeds() -> None:
    client = TestClient(app)
    with (FIXTURES / "sample.dst").open("rb") as fh:
        response = client.post(
            "/api/files/parse",
            files={"file": ("sample.dst", fh, "application/octet-stream")},
        )
    assert response.status_code == 200


def test_fast_path_declared_content_length_over_limit_is_413() -> None:
    # httpx sets Content-Length for bytes bodies, so this hits the fast path.
    response = _limited_client().post("/", content=b"x" * (TEST_LIMIT_BYTES * 2))
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large (limit 1 KB)"}


def test_streaming_chunked_body_over_limit_is_413() -> None:
    def chunks():
        for _ in range(CHUNK_COUNT):
            yield b"x" * CHUNK_SIZE

    # Generator bodies go out chunked (no Content-Length): streaming path.
    response = _limited_client().post("/", content=chunks())
    assert response.status_code == 413
    assert "limit 1 KB" in response.json()["detail"]


def test_body_under_limit_passes_through() -> None:
    response = _limited_client().post("/", content=b"x" * 100)
    assert response.status_code == 200
    assert response.text == "100"


def test_health_get_unaffected() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200


def test_fast_path_refuses_before_reading_any_body_byte() -> None:
    """Declared Content-Length over the default limit -> 413, receive() never called.

    Exercises the shipped DEFAULT_MAX_BODY_BYTES through public ASGI behavior
    (not the private response buffer), and pins the "without reading the body"
    guarantee: a receive() that raises would surface as an error, not a 413.
    """
    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-length", str(DECLARED_HUGE_BYTES).encode())],
    }
    sent: list[Message] = []

    async def receive() -> Message:
        raise AssertionError("body must not be read when Content-Length is over the limit")

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(BodySizeLimitMiddleware(_echo_app)(scope, receive, send))

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    assert json.loads(body) == {"detail": "Request body too large (limit 20 MB)"}  # 20MB per CTO A11


def test_non_http_scope_passes_through_untouched() -> None:
    """websocket/lifespan get the original receive/send — no counting wrappers."""
    seen: dict[str, object] = {}

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        seen["scope"], seen["receive"], seen["send"] = scope, receive, send

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        return None

    scope: Scope = {"type": "lifespan"}
    asyncio.run(BodySizeLimitMiddleware(inner)(scope, receive, send))

    assert seen["scope"] is scope
    assert seen["receive"] is receive
    assert seen["send"] is send
