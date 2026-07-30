"""RequestLoggingMiddleware: X-Request-ID handling and access-log output."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.request_logging import REQUEST_ID_PATTERN

client = TestClient(app)


def test_health_response_carries_request_id() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None
    assert REQUEST_ID_PATTERN.fullmatch(rid)


def test_valid_supplied_request_id_is_echoed() -> None:
    supplied = "abc-123-XYZ"
    resp = client.get("/health", headers={"X-Request-ID": supplied})
    assert resp.headers["X-Request-ID"] == supplied


@pytest.mark.parametrize(
    "bad_id",
    [
        "x" * 200,  # over the 64-char bound
        "has spaces in it",  # disallowed characters
    ],
)
def test_invalid_supplied_request_id_is_replaced(bad_id: str) -> None:
    resp = client.get("/health", headers={"X-Request-ID": bad_id})
    rid = resp.headers["X-Request-ID"]
    assert rid != bad_id
    assert REQUEST_ID_PATTERN.fullmatch(rid)


def test_access_log_line_emitted(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="stitchiq.access"):
        client.get("/health")
    records = [r for r in caplog.records if r.name == "stitchiq.access"]
    assert records, "expected an access log line"
    line = records[-1].getMessage()
    assert "GET" in line
    assert "/health" in line
    assert "200" in line
