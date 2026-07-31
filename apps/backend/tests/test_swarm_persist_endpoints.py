"""HTTP coverage for PUT /designs/{id} (save-over) and PATCH /designs/{id} (rename).

Fallback cases run against the real on-disk local_store (STITCHIQ_DESIGNS_DIR ->
tmp_path); cloud cases monkeypatch supabase_store so nothing touches the network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import supabase_auth, supabase_store

client = TestClient(app)

# A rename body longer than the router's MAX_NAME_LEN (200) must 422, not truncate.
TOO_LONG_NAME = "x" * 201
CLOUD_ID = "11111111-1111-1111-1111-111111111111"


def _design(name: str = "Test", stitches: int = 2) -> dict:
    return {
        "name": name,
        "widthMm": 40,
        "heightMm": 30,
        "stitchCount": stitches,
        "version": 1,
        "status": "draft",
        "colorStops": [],
        "objects": [],
        "stitches": [{"x": i, "y": 0, "command": "STITCH"} for i in range(stitches)],
    }


# --------------------------------------------------------------------------- local


@pytest.fixture
def local(monkeypatch, tmp_path):
    """Force the non-Supabase branch AND the on-disk local_store backend."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: False)
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(tmp_path))
    return tmp_path


def test_put_overwrites_design_in_place(local):
    did = client.post("/api/designs", json=_design("Draft")).json()["id"]

    body = _design("Final", stitches=5)
    put = client.put(f"/api/designs/{did}", json=body)
    assert put.status_code == 200
    assert put.json()["id"] == did  # id comes from the path, not the body

    got = client.get(f"/api/designs/{did}").json()
    assert got["name"] == "Final"
    assert len(got["stitches"]) == 5
    assert len(client.get("/api/designs").json()) == 1  # overwrite, not a second row


def test_put_unknown_id_returns_404(local):
    r = client.put("/api/designs/nope", json=_design("Ghost"))
    assert r.status_code == 404
    assert client.get("/api/designs").json() == []  # PUT never creates


def test_patch_renames_and_keeps_stitches(local):
    did = client.post("/api/designs", json=_design("Old")).json()["id"]

    patched = client.patch(f"/api/designs/{did}", json={"name": "  New  "})
    assert patched.status_code == 200
    assert patched.json() == {"id": did, "name": "New"}  # stripped

    got = client.get(f"/api/designs/{did}").json()
    assert got["name"] == "New"
    assert len(got["stitches"]) == 2  # rename touches only the name
    assert client.get("/api/designs").json()[0]["name"] == "New"


@pytest.mark.parametrize("name", ["", "   ", "\t\n", TOO_LONG_NAME])
def test_patch_invalid_name_returns_422(local, name):
    did = client.post("/api/designs", json=_design("Keep")).json()["id"]
    assert client.patch(f"/api/designs/{did}", json={"name": name}).status_code == 422
    assert client.get(f"/api/designs/{did}").json()["name"] == "Keep"  # unchanged


def test_patch_unknown_id_returns_404(local):
    assert client.patch("/api/designs/nope", json={"name": "New"}).status_code == 404


# --------------------------------------------------------------------------- cloud


@pytest.fixture
def cloud(monkeypatch):
    """Supabase branch with a stubbed authenticated user; store calls are patched per test."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: True)

    async def _user(_token):
        return {"id": CLOUD_ID}

    monkeypatch.setattr(supabase_auth, "verify_token", _user)
    return monkeypatch


AUTH = {"Authorization": "Bearer x"}


async def _boom(*_a, **_k):  # would raise if the store were ever reached
    raise AssertionError("store should not be called for a malformed id")


def test_cloud_put_malformed_id_404_without_store_call(cloud):
    cloud.setattr(supabase_store, "update_design", _boom)
    r = client.put("/api/designs/not-a-uuid", json=_design("X"), headers=AUTH)
    assert r.status_code == 404


def test_cloud_put_missing_row_returns_404(cloud):
    async def _none(*_a, **_k):
        return None

    cloud.setattr(supabase_store, "update_design", _none)
    r = client.put(f"/api/designs/{CLOUD_ID}", json=_design("X"), headers=AUTH)
    assert r.status_code == 404


def test_cloud_put_success_returns_updated_design(cloud):
    async def _ok(design_id, design, _user_id):
        return design.model_copy(update={"id": design_id, "version": 4})

    cloud.setattr(supabase_store, "update_design", _ok)
    r = client.put(f"/api/designs/{CLOUD_ID}", json=_design("Saved"), headers=AUTH)
    assert r.status_code == 200
    assert r.json()["id"] == CLOUD_ID
    assert r.json()["version"] == 4


def test_cloud_patch_malformed_id_404_without_store_call(cloud):
    cloud.setattr(supabase_store, "rename_design", _boom)
    r = client.patch("/api/designs/not-a-uuid", json={"name": "New"}, headers=AUTH)
    assert r.status_code == 404


def test_cloud_patch_no_row_matched_returns_404(cloud):
    async def _false(*_a, **_k):
        return False

    cloud.setattr(supabase_store, "rename_design", _false)
    r = client.patch(f"/api/designs/{CLOUD_ID}", json={"name": "New"}, headers=AUTH)
    assert r.status_code == 404


def test_cloud_patch_success_returns_id_and_name(cloud):
    seen: list[tuple] = []

    async def _true(design_id, name, user_id):
        seen.append((design_id, name, user_id))
        return True

    cloud.setattr(supabase_store, "rename_design", _true)
    r = client.patch(f"/api/designs/{CLOUD_ID}", json={"name": "  New  "}, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"id": CLOUD_ID, "name": "New"}
    assert seen == [(CLOUD_ID, "New", CLOUD_ID)]  # store receives the stripped name


def test_cloud_patch_blank_name_422_without_store_call(cloud):
    cloud.setattr(supabase_store, "rename_design", _boom)
    r = client.patch(f"/api/designs/{CLOUD_ID}", json={"name": "   "}, headers=AUTH)
    assert r.status_code == 422
