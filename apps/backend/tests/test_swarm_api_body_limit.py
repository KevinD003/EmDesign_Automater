"""BodySizeLimitMiddleware: 413 on oversized bodies, no effect otherwise."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from app.main import app
from app.middleware.body_limit import BodySizeLimitMiddleware

FIXTURES = Path(__file__).parent / "fixtures"

# Tiny limit keeps the hermetic tests fast — no multi-MB allocations needed
# to cross it.
TEST_LIMIT_BYTES = 1024
# Streaming test sends 10 x 256 B = 2560 B, comfortably over TEST_LIMIT_BYTES.
CHUNK_SIZE = 256
CHUNK_COUNT = 10


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


def test_default_limit_message_says_25_mb() -> None:
    middleware = BodySizeLimitMiddleware(_echo_app)
    assert b"limit 25 MB" in middleware._response_body
