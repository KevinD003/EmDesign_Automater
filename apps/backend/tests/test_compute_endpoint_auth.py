"""CTO A11/S2: every compute endpoint requires an authenticated caller.

The review: /digitize, /lettering, /convert, /export, /optimize/* (and the
rest of the compute surface) had no current_user dependency — free CPU for
anyone plus a DoS surface. The routers now carry the dependency at router
level; these tests pin that with a local profile present, an unauthenticated
call is 401 BEFORE any body is parsed, and an authenticated one gets past
auth. The keyless fresh-install fallback (no profiles at all) is untouched —
that path is covered by the Part 21 isolation suite.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.services import user_store

# One representative (method, path) per compute router. Bodies are omitted on
# purpose: the 401 must fire at the dependency, before validation, so a bare
# request is enough — anything not 401 means the auth gate is missing.
COMPUTE_ENDPOINTS = [
    ("post", "/api/digitize"),
    ("post", "/api/lettering"),
    ("post", "/api/convert"),
    ("post", "/api/export"),
    ("post", "/api/optimize/path"),
    ("post", "/api/stitches/edit"),
    ("post", "/api/image/edit"),
    ("post", "/api/worksheet"),
    ("post", "/api/files/parse"),
]


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
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


@pytest.mark.parametrize(("method", "path"), COMPUTE_ENDPOINTS)
def test_compute_endpoint_requires_auth_once_profiles_exist(isolated, method, path):
    _signup(isolated, "alice")
    resp = getattr(isolated, method)(path)
    assert resp.status_code == 401, f"{path}: expected 401, got {resp.status_code}"


@pytest.mark.parametrize(("method", "path"), COMPUTE_ENDPOINTS)
def test_compute_endpoint_admits_an_authenticated_caller(isolated, method, path):
    token = _signup(isolated, "alice")
    resp = getattr(isolated, method)(path, headers={"Authorization": f"Bearer {token}"})
    # past the auth gate the bare request fails VALIDATION (or is a 404/405 on
    # a wrong sub-path) — anything but 401/403 proves auth admitted the caller
    assert resp.status_code not in (401, 403), f"{path}: {resp.status_code} {resp.text[:120]}"
