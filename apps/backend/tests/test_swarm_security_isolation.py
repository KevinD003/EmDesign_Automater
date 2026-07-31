"""v2 Part 21 — the security properties the launch review found missing.

Every case here reproduces a defect the review layer demonstrated live against
a running server. They exist because the full suite passed 662 green while an
unauthenticated caller could delete any user's designs: no test asserted
cross-user isolation, so nothing failed.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.services import user_store


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """A client whose user store and design dir are private to this test."""
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(tmp_path / "users.json"))
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(tmp_path / "designs"))
    monkeypatch.delenv("STITCHIQ_OPEN_ACCESS", raising=False)
    user_store.reset_store_cache()
    from app import main

    importlib.reload(main)
    with TestClient(main.app) as client:
        yield client
    user_store.reset_store_cache()


def _signup(client, username: str) -> str:
    resp = client.post("/api/auth/local/profiles", json={"username": username, "pin": "1234"})
    assert resp.status_code == 201, resp.text
    return resp.json()["accessToken"]


def _design(name: str) -> dict:
    return {"name": name, "widthMm": 10, "heightMm": 10, "stitchCount": 0,
            "colorStops": [], "objects": [], "stitches": [], "status": "digitized"}


def test_a_user_cannot_read_another_users_designs(isolated):
    """The blocker: every user shared the 'local-dev' namespace."""
    alice, bob = _signup(isolated, "alice"), _signup(isolated, "bob")
    created = isolated.post("/api/designs", json=_design("ALICE PRIVATE"),
                            headers={"Authorization": f"Bearer {alice}"})
    assert created.status_code in (200, 201), created.text

    listed = isolated.get("/api/designs", headers={"Authorization": f"Bearer {bob}"})
    assert listed.status_code == 200
    assert all(d.get("name") != "ALICE PRIVATE" for d in listed.json()), \
        "Bob can see Alice's designs"


def test_anonymous_callers_are_refused_once_profiles_exist(isolated):
    """Reproduced live: no Authorization header still listed and DELETED designs."""
    alice = _signup(isolated, "alice")
    isolated.post("/api/designs", json=_design("ALICE PRIVATE"),
                  headers={"Authorization": f"Bearer {alice}"})
    assert isolated.get("/api/designs").status_code == 401
    assert isolated.post("/api/designs", json=_design("anon")).status_code == 401


def test_a_bogus_token_is_refused(isolated):
    _signup(isolated, "alice")
    assert isolated.get("/api/designs",
                        headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


def test_a_revoked_token_stops_working_on_design_routes(isolated):
    """Logout revoked only /auth routes; /api/designs never consulted the token."""
    alice = _signup(isolated, "alice")
    hdr = {"Authorization": f"Bearer {alice}"}
    assert isolated.get("/api/designs", headers=hdr).status_code == 200
    assert isolated.post("/api/auth/local/logout", headers=hdr).status_code in (200, 204)
    assert isolated.get("/api/designs", headers=hdr).status_code == 401


def test_expired_sessions_are_rejected(tmp_path, monkeypatch):
    """A token committed to git still authenticated 22h later; now it ages out."""
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(tmp_path / "users.json"))
    user_store.reset_store_cache()
    store = user_store.get_store()
    profile = store.create_profile("alice", pin="1234")
    token = store.issue_token(profile["userId"])
    assert store.verify_token(token) is not None

    stale = "2020-01-01T00:00:00+00:00"
    store._data["sessions"][token]["issued_at"] = stale
    assert store.verify_token(token) is None, "a token older than the TTL must be refused"
    user_store.reset_store_cache()


def test_rate_limiter_separates_users_behind_one_proxy_ip():
    """All ~100 users arrived as 127.0.0.1 through Vite and shared one bucket."""
    from app.middleware.rate_limit import RateLimitMiddleware

    limiter = RateLimitMiddleware(None, max_requests=2, window_seconds=60.0)
    scope_a = {"type": "http", "client": ("127.0.0.1", 1), "headers": [(b"authorization", b"Bearer aaa")]}
    scope_b = {"type": "http", "client": ("127.0.0.1", 2), "headers": [(b"authorization", b"Bearer bbb")]}
    assert limiter._client_key(scope_a) != limiter._client_key(scope_b)


def test_forwarded_header_is_ignored_from_an_untrusted_peer():
    """Otherwise any client could mint a fresh bucket per request."""
    from app.middleware.rate_limit import RateLimitMiddleware

    limiter = RateLimitMiddleware(None)
    spoofed = {"type": "http", "client": ("203.0.113.9", 1),
               "headers": [(b"x-forwarded-for", b"10.0.0.1")]}
    assert limiter._client_key(spoofed) == "ip:203.0.113.9"


def test_credential_store_is_not_tracked_by_git():
    """The live auth DB with working tokens was committed."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    tracked = subprocess.run(["git", "ls-files", "apps/backend/data/"],
                             cwd=root, capture_output=True, text=True).stdout
    assert tracked.strip() == "", f"credential/runtime data is tracked: {tracked}"
