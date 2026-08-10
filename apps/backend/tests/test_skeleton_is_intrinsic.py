"""Thinning a shape must not depend on where the shape sits.

Companion to `test_fill_is_intrinsic.py`, one layer down and the same principle:
a shape's stitching is a property of the shape. That test caught
`_scanline_angled` rotating about the CANVAS centre. This one catches the
medial axis eroding on a schedule keyed to the CANVAS checkerboard.

CTO 2026-08-10, P1. `_thin_state` returned parity as ``(row + col + y0 + x0) % 2``
under a comment insisting the crop origin "MUST be added back — otherwise an
odd-offset region thins differently from the same region uncropped". The goal
was right and the means were exactly backwards. `_zhang_suen_thin` walks
parities in a fixed order (``for parity in (0, 1)``), so keying to absolute
(y + x) means shifting a shape ONE PIXEL swaps every pixel's checkerboard colour
and reverses the erosion schedule.

Measured through `spine_satin` on a grid of 24 bars, before the fix:

    13 of 24 bars changed stitch_type under a one-pixel shift

and on the shortest bars `median_w` swung between 0.00mm and 2.86mm, because the
axis was not merely different — it was erased outright, sending the object down
the `no_medial_axis` arm. The signature was unmistakable: (0,0) and (+1,+1)
always agreed with each other, (+1,0) and (0,+1) always agreed with each other.
That is the checkerboard, and nothing else produces that pattern.

Crop-relative parity gives BOTH invariants, which is why the old comment's
premise was false. `_fg_window` derives the crop from the foreground, so the
same region cropped or uncropped yields the same (row, col) for every pixel —
the property the absolute term was reaching for — while a translation moves
y0/x0 and leaves (row, col) untouched.

After the fix: 0 of 24, every median width identical to 2 decimal places.

WHY THIS MATTERS BEYOND DETERMINISM. It is not only that output wobbles. Every
classification measurement in this series was taken on shapes at whatever
canvas offset they happened to land, so a survey of "which objects are
misclassified" was reading a coin flip on any object near a threshold.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.digitizer.generation import spine_satin
from app.services.digitizer.skeleton import _thin_state, _zhang_suen_thin

MM_PER_PX = 1.0 / 13.3

# Deliberately spans the 4.5mm satin cap and includes SHORT bars: the flips
# clustered on short thick shapes, where the axis is only a few samples long and
# losing either end changes the verdict.
WIDTHS_MM = (2.0, 3.0, 3.5, 4.0, 4.4, 5.0)
HEIGHTS_MM = (6.0, 10.0, 16.0, 24.0)

# The canvas must be big enough that no bar is clipped by an edge. A first
# version of this probe used 400px, the 24mm bars ran off the bottom, and the
# clipping showed up as one surviving "flip" that had nothing to do with parity.
CANVAS = 700

SHIFTS = ((0, 0), (1, 0), (0, 1), (1, 1))


def _bar(w_mm: float, h_mm: float, dy: int, dx: int) -> np.ndarray:
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    w = round(w_mm / MM_PER_PX)
    h = round(h_mm / MM_PER_PX)
    y0, x0 = 100 + dy, 100 + dx
    m[y0:y0 + h, x0:x0 + w] = 255
    assert y0 + h < CANVAS and x0 + w < CANVAS, "bar clipped — raise CANVAS"
    return m


def _attempt(mask, stroke_mm: float):
    return spine_satin(
        mask, mm_per_px=MM_PER_PX, spacing_px=4, max_step_px=6, fill_step_px=4,
        connect_px=8.0, pull_mm=0.2, stroke_mm=stroke_mm, row_px=4,
    )


@pytest.mark.parametrize("w_mm", WIDTHS_MM)
@pytest.mark.parametrize("h_mm", HEIGHTS_MM)
def test_stitch_type_survives_a_one_pixel_shift(w_mm, h_mm):
    """The headline property: same artwork, one pixel over, same decision."""
    seen = {}
    for dy, dx in SHIFTS:
        a = _attempt(_bar(w_mm, h_mm, dy, dx), w_mm)
        seen[(dy, dx)] = (a.viable, round(a.median_w_mm, 2))

    decisions = {v[0] for v in seen.values()}
    assert len(decisions) == 1, (
        f"{w_mm}x{h_mm}mm bar changes stitch_type when moved one pixel: "
        + ", ".join(f"{k}={'SATIN' if v[0] else 'fill'}" for k, v in seen.items())
    )
    widths = {v[1] for v in seen.values()}
    assert len(widths) == 1, (
        f"{w_mm}x{h_mm}mm bar's measured width depends on its position: {sorted(widths)}"
    )


def test_the_skeleton_itself_is_translation_invariant():
    """Below the classifier: the thinned pixels must be the same shape.

    Compared as a set of offsets from the shape's own origin, so a translated
    input is expected to give a translated skeleton and nothing more.
    """
    for w_mm, h_mm in ((3.5, 10.0), (4.0, 16.0), (2.0, 6.0)):
        ref = None
        for dy, dx in SHIFTS:
            skel = _zhang_suen_thin(_bar(w_mm, h_mm, dy, dx))
            ys, xs = np.nonzero(skel)
            assert len(ys), f"{w_mm}x{h_mm} thinned to nothing at {(dy, dx)}"
            rel = frozenset(zip((ys - ys.min()).tolist(), (xs - xs.min()).tolist()))
            if ref is None:
                ref = rel
            else:
                assert rel == ref, (
                    f"{w_mm}x{h_mm}mm bar's skeleton changes shape at offset "
                    f"{(dy, dx)}: {len(rel ^ ref)} pixels differ"
                )


def test_parity_does_not_read_the_canvas():
    """Guard the specific line. Parity must come from crop-relative (row, col).

    Asserted behaviourally rather than by reading the source: place the SAME
    shape at two offsets of opposite absolute parity and require the parity
    arrays to match. A reintroduced `+ y0 + x0` inverts one of them.
    """
    shape = np.zeros((200, 200), np.uint8)
    cv2.rectangle(shape, (40, 40), (90, 120), 255, -1)

    moved = np.zeros((200, 200), np.uint8)
    cv2.rectangle(moved, (41, 40), (91, 120), 255, -1)  # +1 in x flips (y0 + x0)

    _w1, _p1, _i1, par_a = _thin_state(shape)
    _w2, _p2, _i2, par_b = _thin_state(moved)
    assert par_a.shape == par_b.shape
    assert np.array_equal(par_a, par_b), (
        "the thinning parity flipped when the shape moved one pixel — parity is "
        "reading the canvas again, not the crop"
    )


def test_a_cropped_region_thins_like_an_uncropped_one():
    """The invariant the old absolute-parity comment was actually after.

    It is preserved by the fix, not traded away — this is the test that would
    have caught a naive "just drop the origin term" if the crop had come from
    anywhere but the foreground.
    """
    big = np.zeros((300, 300), np.uint8)
    cv2.rectangle(big, (77, 51), (127, 171), 255, -1)  # odd origin on purpose
    small = big[45:180, 70:135].copy()

    a = _zhang_suen_thin(big)
    b = _zhang_suen_thin(small)
    ay, ax = np.nonzero(a)
    by, bx = np.nonzero(b)
    assert len(ay) and len(by)
    rel_a = frozenset(zip((ay - ay.min()).tolist(), (ax - ax.min()).tolist()))
    rel_b = frozenset(zip((by - by.min()).tolist(), (bx - bx.min()).tolist()))
    assert rel_a == rel_b, f"cropped and uncropped differ by {len(rel_a ^ rel_b)} pixels"
