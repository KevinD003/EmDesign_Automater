"""Why the sew-out reference cannot judge thin satin (v2 Part 53).

Part 53 is measurement only — no generator consumes the direction field and no
stitch changes. What it established, and what these tests pin, is that the
reference the whole R004 line has been scored against **cannot see thread on a
structure narrower than its own window**. On such a column the strongest
gradients are the column's two edges, so the structure tensor reports the
COLUMN'S AXIS, which is perpendicular to the thread actually lying there. A
correctly sewn column then looks ~90 deg wrong, and any contour-parallel field —
which is what `direction_field.solve` produces by construction — looks right.

That is circular, and on the reference panel it covers 77% of all satin segments.
The mechanism is provable on synthetic artwork where the truth is known, which is
what the first test does; the panel measurement is in the audit.
"""

from __future__ import annotations

import math
import sys
import typing
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND_ROOT), str(BACKEND_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from measure_direction_field import angular_error_deg
from measure_stitch_direction import orientation_field


def _column_with_thread(width_px: int, size: int = 240, pitch: int = 4):
    """A vertical band filled with HORIZONTAL threads — a satin column.

    Truth by construction: the thread runs across the band (0 deg, horizontal),
    the band's own axis runs down the image (90 deg, vertical). An instrument
    that can see thread must report ~0; one that can only see the band reports
    ~90. Nothing here is a matter of interpretation.
    """
    img = np.zeros((size, size, 3), np.uint8)
    x0 = size // 2 - width_px // 2
    x1 = x0 + width_px
    cv2.rectangle(img, (x0, 0), (x1, size), (150, 150, 150), -1)
    for y in range(0, size, pitch):
        cv2.line(img, (x0, y), (x1, y), (235, 235, 235), 1)
    return img, x0, x1


def _reported_angle(img, x0, x1, window):
    theta, coh = orientation_field(img, window=window)
    h = img.shape[0]
    # Sample the band's interior only, away from its ends.
    sel = np.zeros(theta.shape, bool)
    sel[h // 4:3 * h // 4, x0 + 1:x1 - 1] = True
    sel &= coh >= 0.35
    if sel.sum() < 20:
        return None
    return float(np.median(np.degrees(theta[sel]) % 180))


def test_a_narrow_column_reports_its_own_axis_not_its_thread():
    """The artifact, on artwork whose truth is known.

    Window 9, band 6 px: the window straddles both edges of the band, so the
    tensor is dominated by them and reports the band direction (~90) rather than
    the thread it is full of (~0).
    """
    img, x0, x1 = _column_with_thread(width_px=6)
    got = _reported_angle(img, x0, x1, window=9)
    assert got is not None
    err_thread = abs((got - 0.0 + 90) % 180 - 90)
    err_axis = abs((got - 90.0 + 90) % 180 - 90)
    assert err_axis < err_thread, (
        f"narrow band reported {got:.1f} deg; expected it to read the band axis "
        f"(90) rather than the thread (0) — the Part 53 artifact did not reproduce"
    )


def test_a_wide_column_reports_its_thread():
    """The same artwork, wide enough for the window to fit inside it.

    This is the control that makes the test above mean something: if the
    instrument reported the axis at every width it would simply be broken, and
    the width crossover measured on the panel would have another explanation.
    """
    img, x0, x1 = _column_with_thread(width_px=40)
    got = _reported_angle(img, x0, x1, window=9)
    assert got is not None
    err_thread = abs((got - 0.0 + 90) % 180 - 90)
    err_axis = abs((got - 90.0 + 90) % 180 - 90)
    assert err_thread < err_axis, (
        f"wide band reported {got:.1f} deg; a window that fits inside the band "
        f"should read the thread (0), not the band (90)"
    )


def test_the_reading_migrates_to_the_axis_as_the_window_outgrows_the_column():
    """What actually governs the artifact is window size RELATIVE to width.

    Stated precisely, because the obvious stronger claim is false: a window
    *narrower* than the band still fits inside it and reads the thread. On a 6 px
    band, window 5 reads ~42 deg — genuinely ambiguous, not the axis. So the
    property to pin is the trend: as the window outgrows the column, the reported
    orientation moves off the thread and onto the band.

    On the panel the axis won at every window from 5 to 21, because real columns
    are ~8 px with far softer thread contrast than these synthetic lines. The
    mechanism is the same; the crossover sits at a different ratio.
    """
    narrow, nx0, nx1 = _column_with_thread(width_px=6)
    readings = [(w, _reported_angle(narrow, nx0, nx1, w)) for w in (5, 9, 15, 21)]
    readings = [(w, a) for w, a in readings if a is not None]
    assert len(readings) >= 3, "not enough windows produced a reading"

    def axis_error(a):
        return abs((a - 90.0 + 90) % 180 - 90)

    first, last = readings[0][1], readings[-1][1]
    assert axis_error(last) < axis_error(first), (
        f"widening the window moved the reading from {first:.1f} to {last:.1f} deg; "
        "it should move TOWARD the band axis (90), not away from it"
    )
    # And once the window clearly outgrows the band, the axis wins outright.
    for window, angle in readings:
        if window >= 9:
            assert axis_error(angle) < abs((angle - 0.0 + 90) % 180 - 90), (
                f"window {window} on a 6 px band read {angle:.1f}; expected the axis")

    # The wide band is the control: no window tested confuses it.
    wide, wx0, wx1 = _column_with_thread(width_px=40)
    for window in (5, 9, 15):
        a = _reported_angle(wide, wx0, wx1, window)
        if a is not None:
            assert abs((a - 0.0 + 90) % 180 - 90) < axis_error(a), (
                f"window {window}: wide band read {a:.1f}, expected the thread")


def test_stitch_segments_ignore_travel():
    """A jump is the machine getting somewhere, not the design's direction."""
    import measure_field_headroom as MFH

    class _S:
        def __init__(self, x, y, command):
            self.x, self.y, self.command = x, y, command

    class _D:
        stitches: typing.ClassVar[list] = [
            _S(0.0, 0.0, "STITCH"),
            _S(1.0, 0.0, "STITCH"),     # a real 1 mm segment
            _S(50.0, 50.0, "JUMP"),     # travel — must not become a segment
            _S(51.0, 50.0, "STITCH"),
            _S(52.0, 50.0, "STITCH"),   # another real 1 mm segment
        ]

    segs = MFH.stitch_segments(_D(), lambda x, y: (x, y), 1.0)
    assert len(segs) == 2, f"expected 2 sewn segments, got {len(segs)}"
    for *_xy, length in segs:
        assert abs(length - 1.0) < 1e-6


def test_the_one_angle_oracle_is_a_real_bound():
    """No fixed angle may beat the per-region oracle — it is chosen to be best.

    The oracle exists so a later generator is measured against the ceiling of
    one-angle-per-region policies rather than against today's baseline alone. If
    it were ever beatable it would not bound anything.
    """
    import measure_field_headroom as MFH

    rng = np.random.default_rng(5)
    rows = []
    for oid in (1, 2, 3):
        centre = rng.uniform(0, math.pi)
        for _ in range(60):
            rows.append({"oid": oid, "ref": float(centre + rng.normal(0, 0.25))})

    oracle = MFH._oracle_one_angle(rows)
    ref = np.array([r["ref"] for r in rows])
    for angle in np.radians(np.arange(0, 180, 7.0)):
        fixed = float(np.mean(angular_error_deg(np.full(len(ref), angle), ref)))
        assert oracle <= fixed + 1e-6, (
            f"a fixed angle scored {fixed:.3f} against an oracle of {oracle:.3f}"
        )
