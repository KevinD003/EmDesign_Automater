"""Endpoint tests for the local (offline/LAN) auth router."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth_local
from app.services import user_store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Repoint the process-wide store at a throwaway file for each test.
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(tmp_path / "u.json"))
    user_store.reset_store_cache()
    app = FastAPI()
    app.include_router(auth_local.router, prefix="/api")
    yield TestClient(app)
    user_store.reset_store_cache()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_returns_201_camelcase_session(client):
    resp = client.post(
        "/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "Ada"
    assert body["hasPin"] is True
    assert body["userId"].startswith("local-")
    assert isinstance(body["accessToken"], str) and body["accessToken"]
    # snake_case keys must not leak onto the wire.
    assert "access_token" not in body and "user_id" not in body


def test_create_duplicate_username_409(client):
    assert (
        client.post(
            "/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"}
        ).status_code
        == 201
    )
    resp = client.post(
        "/api/auth/local/profiles", json={"username": "ada", "pin": "9999"}
    )
    assert resp.status_code == 409


def test_create_bad_username_422(client):
    resp = client.post(
        "/api/auth/local/profiles", json={"username": "no/slash", "pin": "1234"}
    )
    assert resp.status_code == 422


def test_login_right_and_wrong_pin(client):
    client.post("/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"})
    ok = client.post("/api/auth/local/login", json={"username": "ada", "pin": "1234"})
    assert ok.status_code == 200
    assert ok.json()["username"] == "Ada"
    assert ok.json()["accessToken"]

    bad = client.post("/api/auth/local/login", json={"username": "ada", "pin": "0000"})
    assert bad.status_code == 401
    assert bad.json()["detail"] == "invalid username or PIN"


def test_login_unknown_user_same_message(client):
    resp = client.post(
        "/api/auth/local/login", json={"username": "ghost", "pin": "1234"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid username or PIN"


def test_list_profiles_shows_haspin_without_secrets(client):
    client.post("/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"})
    client.post("/api/auth/local/profiles", json={"username": "Bob", "pin": None})
    resp = client.get("/api/auth/local/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert [p["username"] for p in profiles] == ["Ada", "Bob"]
    assert [p["hasPin"] for p in profiles] == [True, False]
    for p in profiles:
        assert set(p) == {"userId", "username", "hasPin", "createdAt"}


def test_me_with_issued_token(client):
    created = client.post(
        "/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"}
    ).json()
    resp = client.get("/api/auth/local/me", headers=_auth(created["accessToken"]))
    assert resp.status_code == 200
    assert resp.json() == {"userId": created["userId"], "username": "Ada"}


def test_me_garbage_token_and_missing_header_401(client):
    assert (
        client.get("/api/auth/local/me", headers=_auth("garbage")).status_code == 401
    )
    assert client.get("/api/auth/local/me").status_code == 401


def test_logout_then_me_401(client):
    token = client.post(
        "/api/auth/local/profiles", json={"username": "Ada", "pin": "1234"}
    ).json()["accessToken"]
    assert client.post("/api/auth/local/logout", headers=_auth(token)).status_code == 204
    assert client.get("/api/auth/local/me", headers=_auth(token)).status_code == 401


def test_logout_unknown_token_204(client):
    resp = client.post("/api/auth/local/logout", headers=_auth("never-issued"))
    assert resp.status_code == 204
    # No header at all is also an idempotent no-op.
    assert client.post("/api/auth/local/logout").status_code == 204
