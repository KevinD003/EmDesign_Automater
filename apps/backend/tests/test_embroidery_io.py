"""Round-trip + parsing tests for the embroidery I/O service (Phase 1)."""

from __future__ import annotations

import pyembroidery as pe
import pytest

from app.services import embroidery_io
from app.services.worksheet_pdf import build_worksheet


def _pattern() -> pe.EmbPattern:
    p = pe.EmbPattern()
    red = pe.EmbThread()
    red.set_color(200, 30, 40)
    red.description, red.brand, red.catalog_number = "Red", "Madeira", "1147"
    blue = pe.EmbThread()
    blue.set_color(30, 60, 200)
    blue.description, blue.brand, blue.catalog_number = "Blue", "Madeira", "1733"
    p.add_thread(red)
    for x, y in [(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)]:
        p.add_stitch_absolute(pe.STITCH, x, y)
    p.color_change()
    p.add_thread(blue)
    p.add_stitch_absolute(pe.STITCH, 100, 100)
    p.add_stitch_absolute(pe.STITCH, 400, 400)
    p.end()
    return p


def _dst_bytes(tmp_path) -> bytes:
    f = tmp_path / "x.dst"
    pe.write_dst(_pattern(), str(f))
    return f.read_bytes()


def test_read_parses_dimensions_and_stops(tmp_path):
    design = embroidery_io.read_embroidery(_dst_bytes(tmp_path), "dst")
    assert design.stitch_count > 0
    assert len(design.color_stops) == 2
    assert abs(design.width_mm - 50.0) < 0.5   # 500 tenths -> 50mm
    assert abs(design.height_mm - 50.0) < 0.5
    assert design.stitches[0].command in ("STITCH", "JUMP", "TRIM")


def test_roundtrip_preserves_bounds(tmp_path):
    # NOTE: exact stitch count is NOT preserved (DST writer adds ties/trims and
    # splits long moves). Bounds ARE the stable invariant.
    design = embroidery_io.read_embroidery(_dst_bytes(tmp_path), "dst")
    again = embroidery_io.read_embroidery(embroidery_io.write_embroidery(design, "dst"), "dst")
    assert abs(again.width_mm - design.width_mm) < 1.0
    assert abs(again.height_mm - design.height_mm) < 1.0


@pytest.mark.parametrize("fmt", ["jef", "exp", "vp3", "xxx", "pec"])
def test_roundtrip_preserves_bounds_across_formats(tmp_path, fmt):
    # Same invariant (and tolerances) as the DST round-trip: write → read → bounds.
    design = embroidery_io.read_embroidery(_dst_bytes(tmp_path), "dst")
    again = embroidery_io.read_embroidery(embroidery_io.write_embroidery(design, fmt), fmt)
    assert abs(again.width_mm - design.width_mm) < 1.0
    assert abs(again.height_mm - design.height_mm) < 1.0


def test_pes_preserves_threads(tmp_path):
    f = tmp_path / "x.pes"
    pe.write_pes(_pattern(), str(f))
    design = embroidery_io.read_embroidery(f.read_bytes(), "pes")
    assert len(design.color_stops) == 2


def test_unsupported_ext_raises():
    with pytest.raises(ValueError):
        embroidery_io.read_embroidery(b"not-an-embroidery-file", "zzz")


def test_worksheet_derives_from_design(tmp_path):
    design = embroidery_io.read_embroidery(_dst_bytes(tmp_path), "dst")
    ws = build_worksheet(design)
    assert ws.estimated_stitch_count == design.stitch_count
    assert len(ws.color_sequence) == len(design.color_stops)
    assert ws.estimated_sew_minutes >= 0
