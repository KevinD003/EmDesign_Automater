"""Oversized designs get a 413, never a 500 or a silently corrupt machine file.

VP3 is the only advertised format with an empirically measured container ceiling
(see embroidery_io.FORMAT_CAPS: pyembroidery 1.5.1 wraps VP3 coordinates above
3276.7mm). Everything else round-trips cleanly at 100_000mm, so its cap is None
and an oversized design must still export 200.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.design import ColorStop, Design, Stitch
from app.services import embroidery_io

client = TestClient(app)

# The format whose FORMAT_CAPS row carries a finite limit; 'dst' is the unlimited foil.
_LIMITED_FMT = "vp3"
_UNLIMITED_FMT = "dst"
_LIMIT_MM: float = embroidery_io.FORMAT_CAPS[_LIMITED_FMT]["max_width_mm"]
_OVER_MM = _LIMIT_MM + 50.0  # comfortably past the cap, per the task spec
_UNDER_MM = 100.0


def _design(span_mm: float) -> Design:
    """A 2-stitch design whose stitch bounds span ``span_mm`` on both axes."""
    return Design(
        name="oversize probe",
        width_mm=span_mm,
        height_mm=span_mm,
        stitch_count=2,
        color_stops=[
            ColorStop(
                stop_number=1,
                thread_brand="Test",
                catalog_number="1",
                thread_name="Red",
                hex="#ff0000",
            )
        ],
        stitches=[
            Stitch(x=0.0, y=0.0, command="STITCH"),
            Stitch(x=span_mm, y=span_mm, command="STITCH"),
        ],
    )


def _post(endpoint: str, span_mm: float, fmt: str):
    return client.post(
        endpoint, params={"format": fmt}, json=_design(span_mm).model_dump(by_alias=True)
    )


def test_oversized_export_returns_413_naming_format_and_mm():
    resp = _post("/api/export", _OVER_MM, _LIMITED_FMT)
    assert resp.status_code == 413, resp.text
    detail = resp.json()["detail"]
    assert f".{_LIMITED_FMT}" in detail
    assert "mm" in detail


def test_oversized_package_returns_413():
    resp = _post("/api/export/package", _OVER_MM, _LIMITED_FMT)
    assert resp.status_code == 413, resp.text
    assert f".{_LIMITED_FMT}" in resp.json()["detail"]


def test_oversized_design_still_exports_for_unlimited_format():
    assert embroidery_io.FORMAT_CAPS[_UNLIMITED_FMT]["max_width_mm"] is None
    resp = _post("/api/export", _OVER_MM, _UNLIMITED_FMT)
    assert resp.status_code == 200, resp.text
    assert resp.content


def test_design_within_limit_exports():
    resp = _post("/api/export", _UNDER_MM, _LIMITED_FMT)
    assert resp.status_code == 200, resp.text
    assert resp.content


def test_design_too_large_error_is_a_valueerror():
    # convert.py / files.py catch ValueError from embroidery_io to return 4xx;
    # breaking this subclass relationship turns those endpoints into 500s.
    assert issubclass(embroidery_io.DesignTooLargeError, ValueError)


def test_unsupported_format_still_returns_415():
    resp = _post("/api/export", _UNDER_MM, "zzz")
    assert resp.status_code == 415, resp.text


def test_stitchless_design_falls_back_to_declared_dimensions():
    design = Design(name="no stitches", width_mm=_OVER_MM, height_mm=_OVER_MM, stitch_count=0)
    resp = client.post(
        "/api/export",
        params={"format": _LIMITED_FMT},
        json=design.model_dump(by_alias=True),
    )
    assert resp.status_code == 413, resp.text
