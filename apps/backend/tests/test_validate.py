"""Tests for POST /api/export/validate (spec §4.8) — pre-export checks."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _design(stitches, width_mm=50.0, height_mm=50.0, stitch_count=None):
    sc = stitch_count if stitch_count is not None else sum(1 for s in stitches if s["command"] == "STITCH")
    return {
        "name": "t", "widthMm": width_mm, "heightMm": height_mm, "stitchCount": sc,
        "version": 1, "status": "digitized", "colorStops": [], "objects": [], "stitches": stitches,
    }


def _st(x, y, command="STITCH"):
    return {"x": x, "y": y, "command": command}


def test_validate_empty_design_fails():
    r = client.post("/api/export/validate", json=_design([], stitch_count=0))
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert body["issues"]


def test_validate_normal_design_passes():
    body = client.post("/api/export/validate", json=_design([_st(0, 0), _st(2, 0), _st(2, 2)])).json()
    assert body["passed"] is True
    assert body["issues"] == []


def test_validate_oversize_warns():
    body = client.post("/api/export/validate", json=_design([_st(0, 0), _st(2, 0)], width_mm=260)).json()
    assert body["passed"] is True  # a warning, not a blocking issue
    assert any("hoop" in w.lower() for w in body["warnings"])


def test_validate_long_stitch_warns():
    body = client.post("/api/export/validate", json=_design([_st(0, 0), _st(20, 0)])).json()
    assert any("exceed" in w.lower() for w in body["warnings"])


def test_validate_hoop_fit_is_blocking_issue():
    d = _design([_st(0, 0), _st(2, 0)], width_mm=150, height_mm=50)
    d["hoopSize"] = "100x100"
    body = client.post("/api/export/validate", json=d).json()
    assert body["passed"] is False
    assert any("does not fit" in m for m in body["issues"])


def test_validate_fits_hoop_passes():
    d = _design([_st(0, 0), _st(2, 0)], width_mm=90, height_mm=90)
    d["hoopSize"] = "100x100"
    body = client.post("/api/export/validate", json=d).json()
    assert body["passed"] is True


def test_validate_many_color_changes_warn():
    stitches = []
    for _ in range(20):
        stitches += [_st(0, 0), _st(1, 0), _st(1, 0, "COLOR_CHANGE")]
    body = client.post("/api/export/validate", json=_design(stitches)).json()
    assert any("color changes" in w for w in body["warnings"])
