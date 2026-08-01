"""Spiral and radial fills (v2 Part 26) — the "curved fill effects" of the
desktop suites, user-selectable via rebuild. Generator-level properties plus the
round trip; the ten-fixture corpus is untouched because nothing in the digitize
path selects these automatically.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import pairwise

import cv2
import numpy as np

from app.services.digitizer import (
    _radial_fill,
    _spiral_fill,
    digitize_image,
    rebuild_design,
)


def _disc(r=150, size=400) -> np.ndarray:
    img = np.zeros((size, size), np.uint8)
    cv2.circle(img, (size // 2, size // 2), r, 255, -1)
    return img


def _coverage(pts, region, half=2.0) -> float:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import measure_stitch_quality as M

    canvas = np.zeros(region.shape, np.uint8)
    for a, b in pairwise(pts):
        if b[2]:
            continue
        M._thread_segment(canvas, (a[0], a[1]), (b[0], b[1]), half)
    interior = cv2.erode(region, np.ones((13, 13), np.uint8))
    return 100.0 * float((canvas[interior > 0] > 0).mean())


def test_spiral_covers_a_disc_with_one_continuous_path():
    """The point of a spiral: a disc gets ZERO interior row-ends. Measured
    against the straight fill's 77 jumps on the same disc."""
    pts = _spiral_fill(_disc(), 4, 30, 9.5)
    assert _coverage(pts, _disc()) > 99.0
    assert sum(1 for p in pts if p[2]) < 10


def test_radial_never_stacks_the_hub():
    """The first version sent every 4th spoke to r=0: 59 penetrations in one
    0.5mm cell, an order of magnitude past the density flag. No cell may exceed
    the corpus's healthy peak."""
    pts = _radial_fill(_disc(), 4, 30, 9.5)
    assert _coverage(pts, _disc()) > 99.0
    cells: Counter = Counter()
    for x, y, _j in pts:
        cells[(int(x / 5), int(y / 5))] += 1
    assert max(cells.values()) <= 12, f"hub stacking: {max(cells.values())} in one cell"


def test_curved_fills_stay_inside_the_region():
    region = _disc()
    for pts in (_spiral_fill(region, 4, 30, 9.5), _radial_fill(region, 4, 30, 9.5)):
        for x, y, _j in pts:
            assert region[round(y), round(x)] > 0


def test_empty_region_is_safe():
    empty = np.zeros((50, 50), np.uint8)
    assert _spiral_fill(empty, 4, 30, 3.0) == []
    assert _radial_fill(empty, 4, 30, 3.0) == []


def test_rebuild_to_spiral_and_back_is_machine_valid():
    """The user path: digitize a disc, switch the fill to SPIRAL_FILL in the
    properties panel, Apply -> rebuild. The stream must stay machine-valid and
    the object must round-trip its type."""
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.circle(img, (150, 150), 100, (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    for target in ("SPIRAL_FILL", "RADIAL_FILL"):
        edited = d.model_copy(update={
            "objects": [o.model_copy(update={"stitch_type": target}) for o in d.objects],
        })
        r = rebuild_design(edited)
        assert r.stitch_count > 200
        assert all(o.stitch_type == target for o in r.objects)
        prev = None
        for s in r.stitches:
            if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
                assert math.hypot(s.x - prev.x, s.y - prev.y) <= 12.7
            prev = s
