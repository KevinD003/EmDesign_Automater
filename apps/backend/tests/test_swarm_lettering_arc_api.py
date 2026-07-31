"""Arc baseline wired end-to-end: service kwargs + POST /api/lettering."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.lettering import find_font, generate_lettering

try:
    find_font()
    HAVE_FONT = True
except ValueError:
    HAVE_FONT = False

pytestmark = pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")

_ARC_REQUEST = {"text": "ARC", "heightMm": 15, "baseline": "arc", "arcRadiusMm": 30}


def _client() -> TestClient:
    return TestClient(app)


def test_arc_request_returns_a_stitched_design():
    resp = _client().post("/api/lettering", json=_ARC_REQUEST)
    assert resp.status_code == 200, resp.text
    assert resp.json()["stitchCount"] > 100


def test_arc_is_taller_than_straight_for_the_same_text():
    client = _client()
    arc = client.post("/api/lettering", json=_ARC_REQUEST)
    straight = client.post("/api/lettering", json={"text": "ARC", "heightMm": 15})
    assert arc.status_code == 200 and straight.status_code == 200, arc.text
    # Bending the baseline adds vertical extent; letter height itself is unchanged.
    assert arc.json()["heightMm"] > straight.json()["heightMm"]
    assert arc.json()["widthMm"] > 0


def test_arc_without_radius_is_422():
    resp = _client().post("/api/lettering", json={"text": "ARC", "baseline": "arc"})
    assert resp.status_code == 422
    assert "arc" in str(resp.json()["detail"])


def test_unknown_baseline_is_rejected_by_the_literal():
    resp = _client().post("/api/lettering", json={"text": "ARC", "baseline": "wavy"})
    assert resp.status_code == 422


def test_radius_below_letter_height_is_422():
    resp = _client().post(
        "/api/lettering",
        json={"text": "ARC", "heightMm": 15, "baseline": "arc", "arcRadiusMm": 5},
    )
    assert resp.status_code == 422
    assert "at least the letter height" in str(resp.json()["detail"])


def test_default_baseline_is_straight():
    default = generate_lettering("HI", 20)
    explicit = generate_lettering("HI", 20, baseline="straight")
    assert explicit.stitch_count == default.stitch_count
