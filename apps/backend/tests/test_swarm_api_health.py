"""/health payload enrichment and CORS preflight/expose-header behavior."""

from __future__ import annotations

import logging
import platform
import time

import pytest
from fastapi.testclient import TestClient

from app.main import (
    CORS_ALLOW_METHODS,
    CORS_EXPOSE_HEADERS,
    CORS_MAX_AGE_SECONDS,
    _cors_allow_credentials,
    app,
)

client = TestClient(app)

# The single origin configured in app/config.py for the dev frontend.
ALLOWED_ORIGIN = "http://localhost:5173"

# Any origin that is not configured; must never be echoed back.
FOREIGN_ORIGIN = "http://evil.example"

# Slept between the two uptime samples so the integer second counter is
# guaranteed to advance by at least one.
UPTIME_SAMPLE_GAP_SECONDS = 1


def test_health_returns_enriched_payload() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == app.version
    assert body["pythonVersion"] == platform.python_version()
    assert isinstance(body["uptimeSeconds"], int)
    assert not isinstance(body["uptimeSeconds"], bool)
    assert body["uptimeSeconds"] >= 0


def test_uptime_is_monotonically_non_decreasing() -> None:
    first = client.get("/health").json()["uptimeSeconds"]
    time.sleep(UPTIME_SAMPLE_GAP_SECONDS)
    second = client.get("/health").json()["uptimeSeconds"]
    assert second >= first
    assert second > first, "one full second should have elapsed between samples"


def test_health_never_raises_without_dependencies() -> None:
    # Ten back-to-back calls: no per-request state, no I/O, no 5xx.
    statuses = {client.get("/health").status_code for _ in range(10)}
    assert statuses == {200}


def test_preflight_from_allowed_origin_is_accepted() -> None:
    resp = client.options(
        "/api/convert",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    allowed = resp.headers["access-control-allow-methods"]
    assert "POST" in allowed
    assert resp.headers["access-control-max-age"] == str(CORS_MAX_AGE_SECONDS)


def test_preflight_rejects_unlisted_method() -> None:
    # PATCH is deliberately absent from CORS_ALLOW_METHODS. Starlette still
    # echoes the allowed origin here but fails the preflight with 400 and never
    # advertises PATCH, so the browser blocks the real request.
    assert "PATCH" not in CORS_ALLOW_METHODS
    resp = client.options(
        "/api/convert",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
        },
    )
    assert resp.status_code == 400
    assert "PATCH" not in resp.headers["access-control-allow-methods"]


def test_preflight_from_foreign_origin_gets_no_allow_origin_header() -> None:
    # Starlette answers a disallowed preflight with 400; the contract that
    # matters is the missing header, not the status code.
    resp = client.options(
        "/api/convert",
        headers={
            "Origin": FOREIGN_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


def test_simple_request_exposes_request_id_header() -> None:
    resp = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    exposed = resp.headers["access-control-expose-headers"]
    for header in CORS_EXPOSE_HEADERS:
        assert header in exposed


def test_credentials_allowed_for_explicit_origins() -> None:
    assert _cors_allow_credentials(["http://localhost:5173"]) is True


@pytest.mark.parametrize("origins", [["*"], ["http://localhost:5173", "*"]])
def test_wildcard_origin_disables_credentials_and_warns(
    origins: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="stitchiq.startup"):
        assert _cors_allow_credentials(origins) is False
    records = [r for r in caplog.records if r.name == "stitchiq.startup"]
    assert records, "expected a startup warning about wildcard CORS"
    assert "allow_credentials" in records[-1].getMessage()
