"""The coverage instrument must not have an opinion about fill angle (v2 Part 24).

This is a test of the MEASURING TOOL, not of the digitizer, and it exists because
the tool was wrong in a way that would have silently vetoed Part 24.

Two separate biases were found and fixed:

1. `cv2.line(..., thickness)` paints a different perpendicular width depending on
   the segment's angle — 5.00px at 0 and 90 degrees but 4.25px at 45, for the
   same nominal 4px. Against a 4.5px row pitch that is the difference between
   "covers" and "leaves a gap", so the same fill scored 100.0 horizontal and
   84.5 at 45 degrees. Replaced by the segment's exact swept band.

2. Even with an exact band, a single measurement frame rewards rows that happen
   to align with the pixel grid. The real 0.05mm gap between a 0.45mm pitch and
   0.4mm thread is half a pixel at PX_PER_MM = 10, so at 0 degrees — where every
   row shares one phase — it either all shows or all vanishes, and in the corpus
   it vanished. Coverage is now averaged over four measurement frames.

Both were invisible while every fill in the corpus was emitted at 0 degrees.
"""

from __future__ import annotations

import math
import sys
from itertools import pairwise
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_stitch_quality as M

from app.services.digitizer import _scanline_angled

ANGLES = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0)


def _interior_coverage_at(angle: float) -> float:
    """Coverage of a disc filled at `angle`, on a fixed grid, in percent."""
    disc = np.zeros((400, 400), np.uint8)
    cv2.circle(disc, (200, 200), 150, 255, -1)
    interior = cv2.erode(disc, np.ones((13, 13), np.uint8))
    thread = np.zeros(disc.shape, np.uint8)
    for a, b in pairwise(_scanline_angled(disc, angle, 4, 30, 3.0)):
        if b[2]:
            continue
        M._thread_segment(thread, (a[0], a[1]), (b[0], b[1]), 2.0)
    return 100.0 * float((thread[interior > 0] > 0).mean())


def test_swept_band_paints_the_analytic_stadium_at_every_angle():
    """The primitive paints the right SHAPE in every direction.

    A stadium of half-width r swept over length L has area ``2*r*L + pi*r^2``.
    The tolerance is generous on purpose: rasterising a thin band into a binary
    grid always over-counts by roughly its perimeter, and how much of the
    boundary falls inside depends on orientation — an axis-aligned edge lands
    whole rows of pixel centres on the boundary, a 45-degree edge does not. That
    residual is a property of binary rasterisation, not an angle bias in the
    metric: in a real fill, adjacent bands overlap and it cancels, which is what
    `test_identical_fills_score_the_same_at_every_angle` demonstrates and is the
    contract that actually matters. This test only has to catch a primitive that
    is grossly wrong — a flipped normal, a degenerate quad, a missing cap.
    """
    half, length = 4.0, 160.0
    ideal = 2 * half * length + math.pi * half * half
    perimeter = 2 * length + 2 * math.pi * half
    for deg in range(0, 180, 15):
        canvas = np.zeros((300, 300), np.uint8)
        d = (np.cos(np.radians(deg)), np.sin(np.radians(deg)))
        M._thread_segment(canvas,
                          (150 - length / 2 * d[0], 150 - length / 2 * d[1]),
                          (150 + length / 2 * d[0], 150 + length / 2 * d[1]), half)
        painted = int((canvas > 0).sum())
        assert abs(painted - ideal) < perimeter, (
            f"{deg} deg: painted {painted}px, analytic stadium is {ideal:.0f}px"
        )


def test_identical_fills_score_the_same_at_every_angle():
    scores = [_interior_coverage_at(a) for a in ANGLES]
    assert max(scores) - min(scores) < 1.0, (
        "coverage depends on fill angle: "
        + ", ".join(f"{a:g}deg={s:.1f}%" for a, s in zip(ANGLES, scores))
    )


def test_old_thickness_rasteriser_would_have_failed_this():
    """Pins the defect itself, so nobody reintroduces `cv2.line(..., thickness)`
    on the grounds that it looks equivalent and is one line shorter."""
    disc = np.zeros((400, 400), np.uint8)
    cv2.circle(disc, (200, 200), 150, 255, -1)
    interior = cv2.erode(disc, np.ones((13, 13), np.uint8))
    scores = []
    for angle in ANGLES:
        thread = np.zeros(disc.shape, np.uint8)
        pts = _scanline_angled(disc, angle, 4, 30, 3.0)
        for a, b in pairwise(pts):
            if b[2]:
                continue
            cv2.line(thread, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 255, 4)
        scores.append(100.0 * float((thread[interior > 0] > 0).mean()))
    assert max(scores) - min(scores) > 3.0, (
        "the old rasteriser no longer shows its angle bias; if OpenCV changed its "
        "thick-line rendering, re-derive the fix rather than deleting this test"
    )


@pytest.mark.parametrize("pre_rotation", [0.0, 11.0, 33.0])
def test_frame_averaged_coverage_is_frame_independent(pre_rotation):
    """A real design measured in three unrelated frames must score the same.

    Single-frame coverage moved 2.6 points across frames on the Part 23 corpus
    while the stitches never moved at all.
    """
    from app.services.digitizer import digitize_image

    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (260, 260), (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    design = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    baseline = M.coverage_metrics(design)["interior_pct"]
    rotated = M.coverage_metrics(M._rotated(design, pre_rotation))["interior_pct"]
    assert abs(rotated - baseline) < 0.75, (
        f"coverage moved {abs(rotated - baseline):.2f} points when only the "
        f"measurement frame rotated by {pre_rotation} degrees"
    )
