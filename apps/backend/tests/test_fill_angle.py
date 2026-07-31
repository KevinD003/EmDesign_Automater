"""Per-object fill angle (v2 Part 24).

Up to Part 23 every tatami fill in every design was emitted at 0 degrees, which
is the single most visible difference between our output and the desktop suites':
thread reflects light along its rows, so one global angle makes every shape in a
design reflect identically. These tests pin the two halves of the replacement —
elongated shapes follow their own long axis, isotropic ones avoid their dominant
edge — and the machine-safety properties the angle must not break.
"""

from __future__ import annotations

import math
from itertools import pairwise

import cv2
import numpy as np

from app.services.digitizer import (
    FILL_ANGLE_DEFAULT_DEG,
    _fill_angle,
    _scanline_angled,
    digitize_image,
)


def _canvas(draw) -> np.ndarray:
    img = np.zeros((400, 400), np.uint8)
    draw(img)
    return img


def _dominant_stitch_direction(pts) -> float:
    """Length-weighted mean direction of the emitted segments, in degrees mod 180.

    Measured from the points the filler actually returns rather than reasoned
    about from `getRotationMatrix2D`'s sign convention, because the sign
    convention is exactly the kind of thing that is easy to get backwards and
    impossible to notice afterwards.
    """
    acc = 0j
    total = 0.0
    for a, b in pairwise(pts):
        if b[2]:  # jump: not a stitch
            continue
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1.0 or L > 40.0:  # row connectors and travel are not the fill direction
            continue
        acc += L * np.exp(2j * math.atan2(dy, dx))
        total += L
    return math.degrees(np.angle(acc / total)) / 2.0 % 180.0


def _angle_gap(a: float, b: float) -> float:
    """Separation between two ORIENTATIONS (mod 180), in [0, 90]."""
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def test_emitted_rows_run_at_the_requested_angle():
    """`_scanline_angled(region, A)` must actually lay rows in direction A."""
    img = _canvas(lambda i: cv2.circle(i, (200, 200), 150, 255, -1))
    for want in (0.0, 20.0, 45.0, 70.0, 110.0, 155.0):
        got = _dominant_stitch_direction(_scanline_angled(img, want, 4, 30, 3.0))
        assert _angle_gap(got, want) < 3.0, f"asked for {want}, rows measured {got}"


def test_elongated_shapes_follow_their_own_long_axis():
    for want in (-60.0, -20.0, 0.0, 30.0, 75.0):
        oval = _canvas(lambda i, w=want: cv2.ellipse(i, (200, 200), (160, 70), w, 0, 360, 255, -1))
        assert _angle_gap(_fill_angle(oval), want) <= 3.0


def test_isotropic_shapes_avoid_their_own_dominant_edge():
    """The point of the non-45 default: rows parallel to a strong edge are the
    classic amateur tell, and a diamond's edges run at exactly 45."""
    square = _canvas(lambda i: cv2.rectangle(i, (60, 60), (340, 340), 255, -1))
    diamond = _canvas(lambda i: cv2.fillPoly(
        i, [np.array([[200, 50], [350, 200], [200, 350], [50, 200]])], 255))
    # A square's edges run at 0 and 90, so its fill must sit near 45 off them.
    for edge in (0.0, 90.0):
        assert _angle_gap(_fill_angle(square), edge) > 30.0
    # A diamond's edges run at 45 and 135 — the very angle a flat default picks.
    for edge in (45.0, 135.0):
        assert _angle_gap(_fill_angle(diamond), edge) > 30.0


def test_disc_falls_back_to_the_industry_default():
    """A boundary with no preferred direction has nothing to avoid, so 45 — the
    value new fills get in Hatch and Wilcom — is exactly right."""
    disc = _canvas(lambda i: cv2.circle(i, (200, 200), 150, 255, -1))
    ring = _canvas(lambda i: (cv2.circle(i, (200, 200), 150, 255, -1),
                              cv2.circle(i, (200, 200), 70, 0, -1)))
    assert _fill_angle(disc) == FILL_ANGLE_DEFAULT_DEG
    assert _fill_angle(ring) == FILL_ANGLE_DEFAULT_DEG


def test_empty_region_does_not_raise():
    assert _fill_angle(np.zeros((50, 50), np.uint8)) == FILL_ANGLE_DEFAULT_DEG


def test_a_design_no_longer_stitches_every_fill_at_zero():
    """The end-to-end property, stated the way the gap analysis stated it.

    Two differently-oriented bars in one image: before Part 24 both fills came
    back at 0.0 degrees. This is the assertion that would have caught it.
    """
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.ellipse(img, (90, 150), (30, 110), 20, 0, 360, (40, 40, 200), -1)
    cv2.ellipse(img, (210, 150), (30, 110), -35, 0, 360, (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    fills = [o for o in d.objects if o.stitch_type == "TATAMI"]
    assert fills, "fixture produced no tatami fill to measure"
    assert not all(o.stitch_angle == 0.0 for o in fills)


def test_angled_fills_stay_machine_valid():
    """An angle must not manufacture an over-limit stitch. The un-rotation moves
    every point, so this is not free by construction the way the 0-degree path
    was."""
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.ellipse(img, (150, 150), (120, 60), 33, 0, 360, (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "130x180", max_colors=2)
    prev = None
    for s in d.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert math.hypot(s.x - prev.x, s.y - prev.y) <= 12.7
        prev = s
