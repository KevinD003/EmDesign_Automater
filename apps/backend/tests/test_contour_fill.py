"""Contour fill — rows that follow the outline (v2 Part 24b).

The fourth of the six fill behaviours named in docs/COMPETITIVE-GAP-ANALYSIS.md,
and the one the badge's outer ring needed. A straight row crosses an annulus at
90 degrees at two points and runs along it at two others, so the ragged row-ends
bunch on the inside of the curve and the band reads as a stack of chords.

These tests pin the three things that were got wrong on the way here:
  * the trigger — contouring a SOLID shape (a star) tears, because its medial
    axis is a branching tree and the iso-distance rows crease along every branch;
  * the row pitch — contour rows come off a pixel-quantised distance field and
    need one pixel of margin the exact scanline fill does not;
  * the round trip — a rebuild must not silently convert contour rows back into
    straight ones.
"""

from __future__ import annotations

import math
import sys
from itertools import pairwise
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_stitch_quality as M

from app.services.digitizer import (
    _contour_fill,
    _scanline_angled,
    digitize_image,
    rebuild_design,
)


def _ring(outer=150, inner=95, size=400) -> np.ndarray:
    img = np.zeros((size, size), np.uint8)
    cv2.circle(img, (size // 2, size // 2), outer, 255, -1)
    cv2.circle(img, (size // 2, size // 2), inner, 0, -1)
    return img


def _cover(pts, region, half=2.0) -> tuple[float, float]:
    """(interior coverage %, spill %) for a point stream over a mask."""
    canvas = np.zeros(region.shape, np.uint8)
    for a, b in pairwise(pts):
        if b[2]:
            continue
        M._thread_segment(canvas, (a[0], a[1]), (b[0], b[1]), half)
    interior = cv2.erode(region, np.ones((13, 13), np.uint8))
    laid = max(1, int((canvas > 0).sum()))
    return (100.0 * float((canvas[interior > 0] > 0).mean()),
            100.0 * int(((region == 0) & (canvas > 0)).sum()) / laid)


def test_contour_rows_follow_the_ring_instead_of_crossing_it():
    """The headline claim, measured: same coverage, far fewer jumps, half the spill."""
    ring = _ring()
    straight = _scanline_angled(ring, 45.0, 4, 30, 3.0)
    contour = _contour_fill(ring, 4, 30, 3.0)

    s_cov, s_spill = _cover(straight, ring)
    c_cov, c_spill = _cover(contour, ring)

    s_jumps = sum(1 for p in straight if p[2])
    c_jumps = sum(1 for p in contour if p[2])
    assert c_jumps < s_jumps / 4, f"contour {c_jumps} jumps vs straight {s_jumps}"
    assert c_spill < s_spill / 1.5, f"contour spill {c_spill:.1f}% vs straight {s_spill:.1f}%"
    assert c_cov >= s_cov - 0.5, f"contour coverage {c_cov:.1f}% vs straight {s_cov:.1f}%"


def test_contour_rows_stay_inside_the_region():
    ring = _ring()
    for x, y, _jump in _contour_fill(ring, 4, 30, 3.0):
        assert ring[round(y), round(x)] > 0


def test_row_pitch_carries_a_pixel_of_quantisation_margin():
    """`dist` lives on the pixel grid, so an extracted row sits within +/-0.5px of
    its true iso-distance curve and two neighbours can land a full pixel further
    apart than nominal. At the nominal pitch the ring loses measurable coverage;
    one pixel tighter it does not. Pins the fix as a property, not a constant."""
    ring = _ring()
    # `_contour_fill` subtracts the margin internally, so asking it for pitch P
    # lays rows at P-1. Comparing "ask for P" against "ask for P+1" therefore
    # compares "margin applied" against "margin cancelled out" at the SAME
    # nominal density, which is the comparison that isolates the margin.
    with_margin, _ = _cover(_contour_fill(ring, 5, 30, 3.0), ring)
    without_margin, _ = _cover(_contour_fill(ring, 6, 30, 3.0), ring)
    assert with_margin > 99.0, (
        f"ring coverage {with_margin:.1f}% — the pitch margin is not doing its job"
    )
    assert with_margin > without_margin, (
        f"margin bought nothing: {with_margin:.2f}% with vs {without_margin:.2f}% without"
    )


def test_empty_and_degenerate_regions_do_not_raise():
    assert _contour_fill(np.zeros((40, 40), np.uint8), 4, 30, 3.0) == []
    speck = np.zeros((40, 40), np.uint8)
    speck[20, 20] = 255
    _contour_fill(speck, 4, 30, 3.0)  # must not raise


def test_a_ring_is_digitized_as_contour_fill_and_a_disc_is_not():
    """The trigger. A solid disc must keep the straight angled fill: contouring a
    shape whose medial axis is a branching tree (a star, a blob) tears along
    every branch — measured as 1,708 missed-interior components on fixture 07
    before the trigger excluded solids. A disc's band ratio is 1.11 against a
    ring's 0.15-0.30, so the two are separated with room on both sides."""
    def _digitize(draw):
        img = np.full((420, 420, 3), 255, np.uint8)
        draw(img)
        ok, buf = cv2.imencode(".png", img)
        assert ok
        return digitize_image(buf.tobytes(), "cotton", "130x180", max_colors=2)

    ring = _digitize(lambda i: (cv2.circle(i, (210, 210), 170, (40, 40, 200), -1),
                                cv2.circle(i, (210, 210), 125, (255, 255, 255), -1)))
    disc = _digitize(lambda i: cv2.circle(i, (210, 210), 170, (40, 40, 200), -1))

    assert any(o.stitch_type == "CONTOUR_FILL" for o in ring.objects), (
        f"ring came back as {[o.stitch_type for o in ring.objects]}"
    )
    assert not any(o.stitch_type == "CONTOUR_FILL" for o in disc.objects), (
        "a solid disc must not be contour-filled — its rows would crease on the "
        f"medial axis; got {[o.stitch_type for o in disc.objects]}"
    )


def test_contour_fill_survives_a_rebuild():
    """Without a CONTOUR_FILL branch in `rebuild_design`, editing any parameter
    would silently convert the rows back to straight ones at whatever angle the
    object happened to carry."""
    img = np.full((420, 420, 3), 255, np.uint8)
    cv2.circle(img, (210, 210), 170, (40, 40, 200), -1)
    cv2.circle(img, (210, 210), 125, (255, 255, 255), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "130x180", max_colors=2)
    assert any(o.stitch_type == "CONTOUR_FILL" for o in d.objects)

    r = rebuild_design(d)
    assert any(o.stitch_type == "CONTOUR_FILL" for o in r.objects)
    # A straight re-fill of an annulus needs far more jumps than contour rows do,
    # so the jump count is what exposes a silent conversion.
    assert sum(1 for s in r.stitches if s.command == "JUMP") < 200
    prev = None
    for s in r.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert math.hypot(s.x - prev.x, s.y - prev.y) <= 12.7
        prev = s
