"""CTO B1 — a real /health, a readiness probe that can fail, and Sentry wiring.

`/health` stays a pure liveness probe (no I/O, never raises): it answers "is
this process alive and is its loop responsive?", which is also what detects the
X1 freeze — a wedged loop stops answering. Dependency health is a SEPARATE
question, so it lives at `/health/ready`, and the failure mode it exists to
catch is a container whose data volume did not mount: liveness looks perfect
and every save is lost.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── liveness ─────────────────────────────────────────────────────────────────


def test_health_reports_deployment_identity():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["uptimeSeconds"], int)
    # Which build and which mode — the two questions asked first when a
    # deployment misbehaves, and previously unanswerable from outside.
    assert body["environment"] == "development"
    assert body["release"]  # "dev" locally, the git sha in a built image
    assert body["errorReporting"] is False  # no DSN in the test env


def test_health_touches_no_io():
    # A liveness probe that reads the disk fails when the disk fails, which is
    # exactly when an orchestrator must NOT kill the process (it should drain
    # it via readiness instead). Pin the contract structurally.
    import inspect

    from app import main

    src = inspect.getsource(main.health)
    for forbidden in ("open(", "run_in_threadpool", "local_store", "supabase"):
        assert forbidden not in src, f"/health must stay dependency-free ({forbidden})"


# ── readiness ────────────────────────────────────────────────────────────────


def test_readiness_passes_when_the_store_is_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(tmp_path / "designs"))
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "writable" in body["checks"]["store"]


def test_readiness_returns_503_when_the_store_path_is_unusable(tmp_path, monkeypatch):
    # Root-proof unusable path: the designs dir collides with an existing FILE,
    # so mkdir raises for every uid. (A misplaced bind mount produces exactly
    # this.) Liveness still says "ok"; readiness must not.
    blocker = tmp_path / "designs"
    blocker.write_text("not a directory")
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(blocker))
    r = client.get("/health/ready")
    # 503, not an exception: the orchestrator should drain this instance,
    # not restart-loop it.
    assert r.status_code == 503, r.text
    assert r.json()["status"] == "not ready"
    assert "NOT WRITABLE" in r.json()["checks"]["store"]


@pytest.mark.skipif(os.geteuid() == 0,
                    reason="running as root, which bypasses file permission "
                           "checks — chmod 0500 stays writable and the probe "
                           "would pass for the wrong reason")
def test_readiness_returns_503_on_a_read_only_volume(tmp_path, monkeypatch):
    # The headline real-world case: the compose/Fly volume did not mount, so
    # the mount point is read-only.
    readonly = tmp_path / "ro"
    readonly.mkdir()
    readonly.chmod(0o500)
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(readonly / "designs"))
    try:
        r = client.get("/health/ready")
        assert r.status_code == 503, r.text
        assert "NOT WRITABLE" in r.json()["checks"]["store"]
    finally:
        readonly.chmod(0o700)  # let pytest clean the tmpdir up


def test_readiness_reports_supabase_when_configured(monkeypatch):
    from app.services import supabase_store

    monkeypatch.setattr(supabase_store, "is_enabled", lambda: True)
    body = client.get("/health/ready").json()
    assert body["status"] == "ready"
    assert "supabase" in body["checks"]["store"]


def test_readiness_is_public():
    # Probes are unauthenticated by necessity — an orchestrator has no bearer
    # token. Both must stay outside the A11 auth surface.
    for path in ("/health", "/health/ready"):
        assert client.get(path).status_code in (200, 503), path


# ── error reporting ──────────────────────────────────────────────────────────


def test_observability_is_off_without_a_dsn(monkeypatch):
    from app.observability import init_observability

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_observability() is False


def test_observability_never_raises_when_the_sdk_is_missing(monkeypatch):
    # A slim image without sentry-sdk must still boot. Simulate the ImportError
    # path by hiding the module.
    import builtins

    from app import observability

    monkeypatch.setenv("SENTRY_DSN", "https://abc@o0.ingest.sentry.io/1")
    real_import = builtins.__import__

    def no_sentry(name, *args, **kwargs):
        if name == "sentry_sdk":
            raise ImportError("simulated: not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sentry)
    assert observability.init_observability() is False  # warns, does not raise


def test_observability_survives_a_bad_dsn(monkeypatch):
    # A malformed DSN must not take the API down with it.
    from app import observability

    monkeypatch.setenv("SENTRY_DSN", "not-a-dsn")
    assert observability.init_observability() in (True, False)  # never raises


@pytest.mark.parametrize("header", ["Authorization", "Cookie", "apikey"])
def test_scrub_redacts_secret_headers(header):
    from app.observability import _scrub

    event = {"request": {"headers": {header: "super-secret", "Accept": "*/*"}}}
    out = _scrub(event, {})
    assert out["request"]["headers"][header] == "[redacted]"
    assert out["request"]["headers"]["Accept"] == "*/*"


def test_scrub_drops_the_request_body_and_query_string():
    # The body of a /api/designs POST is an entire Design — the customer's
    # intellectual property. It must never reach a third-party error service.
    from app.observability import _scrub

    event = {
        "request": {
            "url": "https://api/designs",
            "data": '{"stitches": [{"x": 1, "y": 2}], "name": "ACME logo"}',
            "query_string": "token=abc123",
            "headers": {},
        }
    }
    out = _scrub(event, {})
    assert "data" not in out["request"] and "query_string" not in out["request"]
    assert "ACME" not in str(out) and "abc123" not in str(out)
    assert out["request"]["url"] == "https://api/designs"  # route survives
