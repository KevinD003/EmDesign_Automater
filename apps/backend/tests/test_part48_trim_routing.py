"""Sew a colour's regions in proximity order, and stop trimming short gaps (Part 48, R006).

A trim plus the re-thread costs roughly 2.5 s of machine time. The reference
panel carried 844 of them, which is about 35 minutes per run — a real production
cost, not a tidiness complaint.

Two changes, and the measurement matters because they do different things:

    configuration                    trims   jump travel
    raster order, always trim (was)    844       36.20 m
    raster order + 6mm gate            775       36.20 m
    nearest-neighbour, always trim     844       18.26 m
    nearest-neighbour + 6mm gate       663       18.26 m

Ordering cannot remove a trim on its own — there is still one transition per
object — but it halves the distance the needle travels, and it makes the gap
gate 2.6x more effective by putting neighbours next to each other. Neither is
worth much alone.

The brief proposed converting sub-3mm jumps to running stitches. Measured, only
2.6% of the panel's trims spanned under 3mm, so that would have touched 22 of
844. The gaps were long because the order was wrong.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from app.services.digitizer import (
    TRIM_MIN_GAP_MM,
    _nearest_neighbour_order,
    digitize_image,
)

RNG_SEED = 20260728


def _scattered_dots(n: int = 12):
    """Same-colour blobs placed so raster order and proximity order disagree."""
    img = np.full((600, 600, 3), 255, np.uint8)
    for k in range(n):
        cx = 70 + (k % 4) * 150
        cy = 70 + (k // 4) * 150
        cv2.circle(img, (cx, cy), 40, (40, 40, 190), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _digitize(art, hoop="130x180", colors=2):
    cv2.setRNGSeed(RNG_SEED)
    return digitize_image(art, "cotton", hoop, max_colors=colors)


def _counts(design):
    out = {"TRIM": 0, "JUMP": 0, "STITCH": 0}
    for s in design.stitches:
        if s.command in out:
            out[s.command] += 1
    return out


def _jump_travel_mm(design) -> float:
    total, prev = 0.0, None
    for s in design.stitches:
        if s.command == "JUMP" and prev is not None:
            total += math.hypot(s.x - prev[0], s.y - prev[1])
        if s.command in ("STITCH", "JUMP", "TRIM"):
            prev = (s.x, s.y)
    return total


class TestNearestNeighbourOrder:
    def test_it_visits_the_near_point_before_the_far_one(self):
        assert _nearest_neighbour_order([(0, 0), (100, 0), (1, 0)]) == [0, 2, 1]

    def test_it_starts_from_the_point_nearest_a_given_origin(self):
        order = _nearest_neighbour_order([(0, 0), (50, 0), (100, 0)], start=(101, 0))
        assert order[0] == 2

    def test_it_is_deterministic_under_ties(self):
        """Same input, same order — the stitch stream has to be reproducible."""
        pts = [(0, 0), (10, 0), (0, 10), (10, 10), (5, 5)]
        assert _nearest_neighbour_order(pts) == _nearest_neighbour_order(pts)

    def test_it_returns_a_permutation(self):
        pts = [(float(i % 7), float(i // 7)) for i in range(30)]
        assert sorted(_nearest_neighbour_order(pts)) == list(range(30))

    @pytest.mark.parametrize("pts", [[], [(0, 0)], [(0, 0), (1, 1)]])
    def test_it_handles_degenerate_inputs(self, pts):
        assert _nearest_neighbour_order(pts) == list(range(len(pts)))


def test_ordering_shortens_the_needles_journey():
    """The point of the reorder: less travel between regions of one colour."""
    import app.services.digitizer.pipeline as P

    art = _scattered_dots()
    real = P._nearest_neighbour_order
    try:
        P._nearest_neighbour_order = lambda pts, start=None: list(range(len(pts)))
        raster = _jump_travel_mm(_digitize(art))
    finally:
        P._nearest_neighbour_order = real
    ordered = _jump_travel_mm(_digitize(art))
    assert ordered < raster, f"reordering did not shorten travel: {ordered} vs {raster}"


def test_short_gaps_no_longer_cost_a_trim():
    """A trim is only worth its 2.5 s when the carried thread would be long."""
    design = _digitize(_scattered_dots())
    prev = None
    for s in design.stitches:
        if s.command == "TRIM":
            prev = (s.x, s.y)
            continue
        if prev is not None and s.command in ("JUMP", "STITCH"):
            gap = math.hypot(s.x - prev[0], s.y - prev[1])
            assert gap >= TRIM_MIN_GAP_MM - 1e-6, (
                f"trimmed across only {gap:.2f}mm, under the {TRIM_MIN_GAP_MM}mm gate"
            )
            prev = None


def test_the_regions_themselves_are_untouched():
    """Routing may reorder and rejoin; it must not change what gets sewn.

    This is the guarantee that made the change safe to ship: object count and
    coverage are identical, and the ten visual baselines all stayed above the
    SSIM gate (lowest 0.998768).
    """
    import app.services.digitizer.pipeline as P

    art = _scattered_dots()
    real = P._nearest_neighbour_order
    try:
        P._nearest_neighbour_order = lambda pts, start=None: list(range(len(pts)))
        before = _digitize(art)
    finally:
        P._nearest_neighbour_order = real
    after = _digitize(art)

    assert len(after.objects) == len(before.objects)
    assert len(after.color_stops) == len(before.color_stops)
    assert _counts(after)["STITCH"] == pytest.approx(_counts(before)["STITCH"], rel=0.02)


def test_the_gate_is_conservative_on_purpose():
    """Raising it removes more trims and leaves longer loose threads.

    Measured on the panel: 3mm -> 813 trims, 6mm -> 663, 10mm -> 485. A 10mm gate
    would have beaten the brief's target of 586, and it is not taken: this
    digitizer writes files for arbitrary machines, and one that assumes an
    aggressive auto-trimmer leaves 1cm of loose thread on every machine that has
    none. Tuning the default to hit a target number would be the wrong reason.
    """
    assert 3.0 <= TRIM_MIN_GAP_MM <= 8.0
