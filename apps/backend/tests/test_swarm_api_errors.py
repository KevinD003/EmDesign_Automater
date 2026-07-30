"""Global error handlers: sanitized 500s and clean 4xx JSON (app.main)."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app, unhandled_exception_handler

client = TestClient(app)


def _assert_clean_422(resp) -> None:
    """Shared shape checks: FastAPI detail entries minus payload echo fields."""
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert isinstance(body["detail"], list) and body["detail"]
    for entry in body["detail"]:
        assert "loc" in entry
        assert "msg" in entry
        # 'input'/'url' would reflect user payloads back — must be stripped.
        assert "input" not in entry
        assert "url" not in entry
    assert "requestId" in body


def test_optimize_quality_validation_error_is_clean_422() -> None:
    resp = client.post("/api/optimize/quality", json={"objects": "nonsense"})
    _assert_clean_422(resp)


def test_convert_validation_error_is_clean_422() -> None:
    resp = client.post(
        "/api/convert",
        json={"inputFileBase64": ["not", "a", "string"], "fromFormat": 1.5, "toFormat": None},
    )
    _assert_clean_422(resp)


def _scratch_app() -> FastAPI:
    """Isolated app reusing the real handler — app.main gets no test-only route."""
    scratch = FastAPI()
    scratch.add_exception_handler(Exception, unhandled_exception_handler)

    @scratch.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    return scratch


def test_unhandled_exception_returns_sanitized_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    scratch_client = TestClient(_scratch_app(), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="stitchiq.error"):
        resp = scratch_client.get("/boom")

    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Internal server error"
    assert body["requestId"] is None  # scratch app has no request-id middleware
    # Exception class/message/traceback must never leak to the client.
    assert "RuntimeError" not in resp.text
    assert "secret internal detail" not in resp.text

    records = [r for r in caplog.records if r.name == "stitchiq.error"]
    assert records, "expected the unhandled exception to be logged"
    assert records[-1].exc_info is not None
    assert "RuntimeError" in (records[-1].exc_text or str(records[-1].exc_info[0]))
