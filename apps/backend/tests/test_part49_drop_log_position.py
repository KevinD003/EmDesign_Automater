"""The speck log records WHERE, not just how much (v2 Part 49, R008).

R008 asked for a bead-chain detector. Step 1 of that brief was to measure whether
the dropped-speck population separates into "ornament" and "noise", and to stop
if it does not. It does not — see `docs/benchmarks/v2-part49-audit.md`.

What survives from the attempt is this: `_DROP_LOG` now carries each dropped
region's centroid. Without it the log could only answer "how much was dropped"
and "how big", never "was it structured", and any future attempt at recovering a
filtered ornament has to start from the positions.

Re-deriving them outside the pipeline is not equivalent, and that is worth a test
rather than a comment: the morphological open inside the loop removes
single-pixel noise, so a naive re-derivation on the raw cluster mask counted
25,822 regions where the pipeline drops 768.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services.digitizer import constants as K
from app.services.digitizer import digitize_image

RNG_SEED = 20260728


def _speckled_art():
    """A solid shape plus dots small enough to fall under the 2mm2 floor."""
    img = np.full((600, 600, 3), 255, np.uint8)
    cv2.rectangle(img, (60, 60), (540, 240), (40, 40, 190), -1)
    for k in range(24):
        cx = 80 + (k % 12) * 38
        cy = 400 + (k // 12) * 60
        cv2.circle(img, (cx, cy), 5, (40, 40, 190), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _digitize():
    cv2.setRNGSeed(RNG_SEED)
    # 40x40 puts these dots under the 2mm2 floor. At 130x180 the same art keeps
    # them as objects, and at radius 3 or less they never reach the drop log at
    # all — they are removed before contouring. Both facts are why the log alone
    # cannot see a whole bead chain; see the Part 49 audit.
    return digitize_image(_speckled_art(), "cotton", "40x40", max_colors=2)


def test_every_drop_records_area_perimeter_and_position():
    _digitize()
    assert K._DROP_LOG, "this fixture must drop some specks or it tests nothing"
    for entry in K._DROP_LOG:
        assert len(entry) == 4, f"expected (area, perimeter, cx, cy), got {entry}"
        assert entry[0] > 0 and entry[1] > 0, f"non-positive area/perimeter: {entry}"
        assert all(isinstance(v, float) for v in entry)


def test_the_positions_are_real_coordinates_in_mm():
    """The failure mode that matters is a centroid that is always 0.0, or in pixels.

    Deliberately not asserted against the design's stitched extents: a dropped
    region is by definition somewhere nothing was sewn, so on this fixture the
    dots sit well outside the surviving rectangle's bounding box. Asserting
    otherwise was the first version of this test, and it was the test that was
    wrong.
    """
    design = _digitize()
    span = max(design.width_mm, design.height_mm, 1.0)
    xs = [e[2] for e in K._DROP_LOG]
    ys = [e[3] for e in K._DROP_LOG]
    assert all(0.0 <= v <= span * 4 for v in xs + ys), (
        f"centroids out of plausible mm range for a {span:.1f}mm design: "
        f"x {min(xs):.1f}..{max(xs):.1f}, y {min(ys):.1f}..{max(ys):.1f}"
    )
    assert len(set(zip(xs, ys))) > 1, "every drop reported the same position"
    assert max(ys) - min(ys) > 0.5 or max(xs) - min(xs) > 0.5, "no spread at all"


def test_the_log_is_cleared_between_runs():
    """It is module state; a stale log would silently double-count."""
    _digitize()
    first = len(K._DROP_LOG)
    _digitize()
    assert len(K._DROP_LOG) == first, "drop log accumulated across runs"


def test_the_positions_are_deterministic():
    _digitize()
    a = list(K._DROP_LOG)
    _digitize()
    assert list(K._DROP_LOG) == a


def test_recording_positions_is_cheap_on_a_speck_heavy_image():
    """The cost characteristic, not just the correctness.

    The first version took `cv2.moments` over the full-size filled probe once per
    dropped region. On a design with a few hundred specks that is invisible; on
    random noise, where one colour holds tens of thousands, it took a 1500x1500
    digitize from ~16 s to over ten minutes, and the fuzz suite caught it — 28
    minutes into a full run.

    That is the second performance regression in this loop in two parts, so the
    signal belongs somewhere fast. This image is deliberately speck-heavy: a few
    hundred dots that all fall under the floor, digitized small.
    """
    import time

    img = np.full((700, 700, 3), 255, np.uint8)
    for k in range(400):
        cv2.circle(img, (20 + (k % 20) * 34, 20 + (k // 20) * 34), 5, (40, 40, 190), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok

    cv2.setRNGSeed(RNG_SEED)
    start = time.perf_counter()
    digitize_image(buf.tobytes(), "cotton", "40x40", max_colors=2)
    elapsed = time.perf_counter() - start

    assert K._DROP_LOG, "this fixture must drop specks or it measures nothing"
    assert elapsed < 20.0, (
        f"{len(K._DROP_LOG)} dropped regions took {elapsed:.1f}s. The centroid must "
        f"come from the contour, not from moments over a full-size image."
    )
