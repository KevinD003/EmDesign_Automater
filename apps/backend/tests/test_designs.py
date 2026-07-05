"""Design CRUD endpoints (spec §8). Exercises the in-memory fallback path so the
suite stays offline; the live Supabase path is covered by manual round-trip checks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import designs as designs_router
from app.services import supabase_auth, supabase_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_in_memory(monkeypatch):
    """Pin the router to its in-memory store regardless of local .env / Supabase keys."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: False)
    designs_router._DESIGNS.clear()
    yield
    designs_router._DESIGNS.clear()


def _design(name: str = "Test") -> dict:
    return {
        "name": name,
        "widthMm": 40,
        "heightMm": 30,
        "stitchCount": 2,
        "version": 1,
        "status": "draft",
        "colorStops": [],
        "objects": [],
        "stitches": [{"x": 0, "y": 0, "command": "STITCH"}, {"x": 2, "y": 0, "command": "STITCH"}],
    }


def test_create_list_get_delete_roundtrip():
    # empty to start
    assert client.get("/api/designs").json() == []

    created = client.post("/api/designs", json=_design("Logo"))
    assert created.status_code == 201
    did = created.json()["id"]
    assert did  # an id was assigned

    listing = client.get("/api/designs").json()
    assert len(listing) == 1 and listing[0]["name"] == "Logo"

    got = client.get(f"/api/designs/{did}")
    assert got.status_code == 200
    assert len(got.json()["stitches"]) == 2  # full design preserved

    assert client.delete(f"/api/designs/{did}").status_code == 204
    assert client.get(f"/api/designs/{did}").status_code == 404


def test_get_missing_returns_404():
    assert client.get("/api/designs/does-not-exist").status_code == 404


def test_inmemory_ids_not_reused_after_delete():
    """Regression: a delete must not let the next create collide with a live id."""
    a = client.post("/api/designs", json=_design("A")).json()["id"]
    b = client.post("/api/designs", json=_design("B")).json()["id"]
    client.delete(f"/api/designs/{a}")
    c = client.post("/api/designs", json=_design("C")).json()["id"]
    assert c != b  # C did NOT reuse B's id
    assert client.get(f"/api/designs/{b}").json()["name"] == "B"  # B intact
    assert client.get(f"/api/designs/{c}").json()["name"] == "C"


def test_malformed_design_id_returns_404_not_502(monkeypatch):
    """Cloud path: a non-uuid id 404s (never a 502) and never hits PostgREST."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: True)

    async def _user(_token):
        return {"id": "11111111-1111-1111-1111-111111111111"}

    async def _boom(*_a, **_k):  # would raise if the store were ever reached
        raise AssertionError("store should not be called for a malformed id")

    monkeypatch.setattr(supabase_auth, "verify_token", _user)
    monkeypatch.setattr(supabase_store, "get_design", _boom)
    r = client.get("/api/designs/not-a-uuid", headers={"Authorization": "Bearer x"})
    assert r.status_code == 404


def test_stats_reflects_saved_designs():
    empty = client.get("/api/designs/stats").json()
    assert empty == {"designCount": 0, "totalStitches": 0, "totalColors": 0, "recent": []}

    client.post("/api/designs", json=_design("A"))
    client.post("/api/designs", json=_design("B"))
    stats = client.get("/api/designs/stats").json()
    assert stats["designCount"] == 2
    assert stats["totalStitches"] == 4  # 2 stitches each
    assert {r["name"] for r in stats["recent"]} == {"A", "B"}
