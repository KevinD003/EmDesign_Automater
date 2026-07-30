"""Integration tests: auth_local router wired into app.main under /api.

Proves the full path through the real app (middleware + registration), and
guards that the pre-existing Supabase auth route is still mounted.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import supabase_store, user_store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Repoint the process-wide store at a throwaway file for each test.
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(tmp_path / "u.json"))
    user_store.reset_store_cache()
    yield TestClient(app)
    user_store.reset_store_cache()


def test_create_profile_via_main_app(client):
    resp = client.post(
        "/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "Ada"
    assert body["hasPin"] is True
    assert body["userId"].startswith("local-")
    assert isinstance(body["accessToken"], str) and body["accessToken"]


def test_login_then_me_with_bearer_token(client):
    assert (
        client.post(
            "/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"}
        ).status_code
        == 201
    )
    login = client.post(
        "/api/auth/local/login", json={"username": "Ada", "pin": "1234"}
    )
    assert login.status_code == 200
    token = login.json()["accessToken"]
    assert token

    me = client.get(
        "/api/auth/local/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json() == {"userId": login.json()["userId"], "username": "Ada"}


def test_profiles_list_shows_created_profile(client):
    client.post("/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"})
    resp = client.get("/api/auth/local/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert [p["username"] for p in profiles] == ["Ada"]
    assert profiles[0]["hasPin"] is True
    # Picker payload must never leak secrets.
    assert "pinHash" not in profiles[0] and "pinSalt" not in profiles[0]


def test_supabase_me_route_still_mounted(client, monkeypatch):
    """Guard: /api/auth/me (cloud path) must not be shadowed by /auth/local."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: False)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"userId": "local-dev"}
