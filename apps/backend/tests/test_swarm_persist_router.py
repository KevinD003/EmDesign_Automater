"""End-to-end HTTP coverage for the designs router's local_store DISK fallback.

Unlike tests/test_designs.py (pytest-mode in-memory dict), these tests point
STITCHIQ_DESIGNS_DIR at tmp_path so every request round-trips through real JSON
files — proving a keyless localhost deployment persists designs across requests.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import supabase_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _disk_fallback(monkeypatch, tmp_path):
    """Force the non-Supabase branch AND the on-disk local_store backend."""
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: False)
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(tmp_path))
    yield


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


def _file_for(tmp_path, design_id: str):
    matches = list(tmp_path.rglob(f"{design_id}.json"))
    assert len(matches) == 1, f"expected exactly one file for {design_id}, got {matches}"
    return matches[0]


def test_create_writes_json_file(tmp_path):
    resp = client.post("/api/designs", json=_design("Logo"))
    assert resp.status_code == 201
    did = resp.json()["id"]
    assert did  # a non-empty id was assigned
    path = _file_for(tmp_path, did)
    assert json.loads(path.read_text(encoding="utf-8"))["name"] == "Logo"


def test_list_strips_stitches_and_keeps_name():
    client.post("/api/designs", json=_design("Badge"))
    listing = client.get("/api/designs").json()
    assert len(listing) == 1
    assert listing[0]["name"] == "Badge"
    assert listing[0]["stitches"] == []  # listing is metadata-only
    assert listing[0]["stitchCount"] == 2  # count survives the strip


def test_get_returns_full_stitches():
    did = client.post("/api/designs", json=_design("Full")).json()["id"]
    got = client.get(f"/api/designs/{did}")
    assert got.status_code == 200
    assert len(got.json()["stitches"]) == 2


def test_delete_then_get_404(tmp_path):
    did = client.post("/api/designs", json=_design("Gone")).json()["id"]
    assert client.delete(f"/api/designs/{did}").status_code == 204
    assert client.get(f"/api/designs/{did}").status_code == 404
    assert list(tmp_path.rglob(f"{did}.json")) == []  # file removed from disk


def test_stats_reflects_two_saved_designs():
    client.post("/api/designs", json=_design("A"))
    client.post("/api/designs", json=_design("B"))
    stats = client.get("/api/designs/stats").json()
    assert stats["designCount"] == 2
    assert stats["totalStitches"] == 4  # 2 stitches each
    assert stats["totalColors"] == 0
    assert {r["name"] for r in stats["recent"]} == {"A", "B"}


def test_data_survives_across_requests(tmp_path):
    """Every GET re-reads from disk — a design outlives the request that made it."""
    did = client.post("/api/designs", json=_design("Durable")).json()["id"]
    raw = _file_for(tmp_path, did).read_bytes()  # bytes really are on disk
    assert b"Durable" in raw
    got = client.get(f"/api/designs/{did}")  # served from that file, not memory
    assert got.status_code == 200
    assert got.json()["name"] == "Durable"
