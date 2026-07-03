"""Tests for thread catalog + nearest-match (spec §4.4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import threads as t

client = TestClient(app)


def test_hex_to_lab_endpoints():
    # black → L≈0, white → L≈100
    assert t.hex_to_lab("#000000")[0] < 1
    assert t.hex_to_lab("#ffffff")[0] > 99


def test_nearest_thread_picks_closest_catalog_color():
    cat = t.list_threads()  # Flame #F4511E, Black #0A0A0A, White #FFFFFF, Royal #1E40AF, Kelly #15803D
    assert t.nearest_thread("#0A0A0A", cat).color_name == "Black"      # exact
    assert t.nearest_thread("#111111", cat).color_name == "Black"      # near-black
    assert t.nearest_thread("#FDFDFD", cat).color_name == "White"
    assert t.nearest_thread("#FF5A2A", cat).color_name == "Flame"      # orange-red
    assert t.nearest_thread("#123Fb0", cat).color_name == "Royal Blue"


def test_nearest_thread_bad_hex_raises():
    with pytest.raises(ValueError):
        t.nearest_thread("nope", t.list_threads())


def test_nearest_thread_empty_catalog_raises():
    with pytest.raises(ValueError):
        t.nearest_thread("#000000", [])


def test_match_endpoint():
    r = client.post("/api/threads/match", params={"hex": "#0b0b0b"})
    assert r.status_code == 200
    assert r.json()["colorName"] == "Black"
    bad = client.post("/api/threads/match", params={"hex": "zzz"})
    assert bad.status_code == 422
