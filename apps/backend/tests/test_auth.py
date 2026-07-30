"""Auth router + the current_user gate. Mocks Supabase so the suite stays offline."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import supabase_auth, supabase_store

client = TestClient(app)


def test_me_offline_returns_local_user(monkeypatch):
    """No Supabase configured -> auth is skipped, caller is the local sentinel."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: False)
    r = client.get("/api/auth/me")
    assert r.status_code == 200 and r.json() == {"userId": "local-dev"}


def test_signup_and_login_503_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(supabase_auth, "is_enabled", lambda: False)
    body = {"email": "a@b.com", "password": "secret123"}
    assert client.post("/api/auth/signup", json=body).status_code == 503
    assert client.post("/api/auth/login", json=body).status_code == 503


def test_signup_rejects_bad_email_and_short_password(monkeypatch):
    monkeypatch.setattr(supabase_auth, "is_enabled", lambda: True)
    assert client.post("/api/auth/signup", json={"email": "nope", "password": "secret123"}).status_code == 422
    assert client.post("/api/auth/signup", json={"email": "a@b.com", "password": "x"}).status_code == 422


def test_designs_require_auth_when_supabase_enabled(monkeypatch):
    """Supabase on + no/invalid token -> 401 (the per-user gate)."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: True)

    async def _no_user(_token):
        return None

    monkeypatch.setattr(supabase_auth, "verify_token", _no_user)
    assert client.get("/api/designs").status_code == 401  # missing header
    assert client.get("/api/designs", headers={"Authorization": "Bearer bad"}).status_code == 401
