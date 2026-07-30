"""Round-trip export tests for EVERY format advertised by GET /api/formats.

The parametrize list is fetched live from the endpoint at collection time, so a
format added to MACHINE_EXPORT_FORMATS later is covered automatically with no
test edit. Complements test_export.py (advertising rules) and
test_embroidery_io.py (service-level round-trips) by exercising the HTTP path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import Design
from app.services import embroidery_io

client = TestClient(app)

_FIXTURE = Path(__file__).parent / "fixtures" / "sample.pes"

# Fetched at collection time so parametrization always mirrors the live endpoint.
ADVERTISED_FORMATS: list[str] = client.get("/api/formats").json()["export"]

# Machine writers add tie-ins/tie-offs and split long jumps, so exact stitch
# counts are NOT stable across a write/read cycle. Bounds are the invariant;
# 1.5mm absorbs per-format quantization (see test_embroidery_io.py).
_BOUNDS_TOLERANCE_MM = 1.5


def _fixture_design() -> Design:
    """sample.pes decoded to a multi-color Design with real stitches."""
    design = embroidery_io.read_embroidery(_FIXTURE.read_bytes(), "pes")
    assert len(design.color_stops) >= 2, "fixture must be multi-color"
    assert design.stitch_count > 0, "fixture must have real stitches"
    return design


def _export(design: Design, fmt: str):
    return client.post(
        f"/api/export?format={fmt}",
        json=design.model_dump(by_alias=True),
    )


def test_formats_endpoint_advertises_something():
    assert ADVERTISED_FORMATS, "GET /api/formats must advertise at least one format"


@pytest.mark.parametrize("fmt", ADVERTISED_FORMATS)
def test_export_returns_file_for_every_advertised_format(fmt):
    design = _fixture_design()
    resp = _export(design, fmt)
    assert resp.status_code == 200, f"{fmt}: {resp.text}"
    assert resp.content, f"{fmt} returned an empty body"
    assert f".{fmt}" in resp.headers["content-disposition"]


@pytest.mark.parametrize("fmt", ADVERTISED_FORMATS)
def test_exported_bytes_reread_within_bounds(fmt):
    if fmt not in embroidery_io._supported_read_exts():
        pytest.skip(f".{fmt} is write-only in pyembroidery")
    design = _fixture_design()
    resp = _export(design, fmt)
    assert resp.status_code == 200, f"{fmt}: {resp.text}"
    again = embroidery_io.read_embroidery(resp.content, fmt)
    assert again.stitch_count > 0
    assert abs(again.width_mm - design.width_mm) < _BOUNDS_TOLERANCE_MM
    assert abs(again.height_mm - design.height_mm) < _BOUNDS_TOLERANCE_MM


def test_uppercase_format_param_matches_lowercase():
    # write_embroidery lowercases the ext and the router lowercases the
    # filename, so 'DST' must behave exactly like 'dst'.
    design = _fixture_design()
    upper = _export(design, "DST")
    lower = _export(design, "dst")
    assert lower.status_code == 200
    assert upper.status_code == 200, f"uppercase format rejected: {upper.text}"
    assert upper.content == lower.content
    assert upper.headers["content-disposition"] == lower.headers["content-disposition"]
