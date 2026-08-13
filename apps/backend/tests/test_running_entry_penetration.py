"""A Line object survives rebuild with its penetration count intact.

The defect this pins: `_manual_run` returned a run's first point as the bare
JUMP, so the first needle-down landed at the SECOND point. The digitize-side
emitter (the dark-linework pass) has always stitched the first point. One
penetration was therefore lost per run object on every rebuild — on the
angelfish record, whose objects are RUNNING_SINGLE 55 of 100, that is 55
penetrations gone per rebuild with nothing to notice, because RUNNING_SINGLE
had zero coverage across the fourteen fixtures.

The convention decided, not merely made consistent: a jump POSITIONS the
needle, a stitch PUTS IT DOWN, so a drawn path's first point must be a
penetration or the line starts one pitch late and a two-point path sews a
single unanchored penetration. `_manual_run`'s sole caller is rebuild's
RUNNING branch (verified: no underlay path uses it), so the flip is the whole
unification.

Constructed objects rather than fixtures, deliberately: no fixture reaches this
path — that hole is the corpus-representation item, handled separately — and a
constructed object is the fastest falsifiable acceptance. It is exactly the
acceptance the ruling stated: a Line object survives `rebuild_design` with an
unchanged penetration count.
"""

from __future__ import annotations

import math

import pytest

from app.models.design import (
    ColorStop, ConnectMethod, Design, DesignObject, Point, StitchType, UnderlayType,
)
from app.services.digitizer import rebuild_design

PITCH_MM = 2.0


def _run_design(n_points: int, stitch_type=StitchType.RUNNING_SINGLE) -> Design:
    """One run object along a straight line with `n_points` resample points.

    The path length is chosen so `_resample_open` at the object's own pitch
    reproduces exactly `n_points` — penetration_count is then known, not
    inferred: the emitter convention says one penetration per path point.
    """
    length = PITCH_MM * (n_points - 1)
    path = [Point(x=5.0 + i * length / (n_points - 1), y=5.0) for i in range(n_points)]
    passes = {StitchType.RUNNING_DOUBLE: 2, StitchType.RUNNING_TRIPLE: 3}.get(stitch_type, 1)
    pen = n_points + (n_points - 1) * (passes - 1)
    obj = DesignObject(
        sequence_order=1, name="Line 1 (#202020)", stitch_type=stitch_type,
        color_stop=1, density=1.0 / PITCH_MM, stitch_angle=0.0,
        underlay_type=UnderlayType.NONE, pull_compensation=0.0,
        connect_method=ConnectMethod.TRIM, penetration_count=pen, stream_span=pen,
        contour=path,
    )
    return Design(
        name="run-entry", width_mm=length + 10, height_mm=10.0, hoop_size="100x100",
        fabric_type="cotton", stitch_count=pen,
        color_stops=[ColorStop(stop_number=1, thread_brand="Auto", catalog_number="",
                               thread_name="Color 1", hex="#202020",
                               penetration_count=pen, stream_span=pen)],
        objects=[obj], stitches=[], version=1, status="digitized",
    )


@pytest.mark.parametrize("n_points", [2, 3, 10, 50])
def test_a_line_object_keeps_every_penetration_through_rebuild(n_points):
    design = _run_design(n_points)
    reb = rebuild_design(design, force=True)
    got = reb.objects[0].penetration_count
    assert got == n_points, (
        f"a {n_points}-point run came back with {got} penetrations. One short "
        f"means the entry convention regressed: the first point of a drawn path "
        f"is a penetration, not a bare repositioning."
    )


def test_the_two_point_line_is_anchored_at_both_ends():
    """The worst case of the old behaviour: a 2-point run sewed ONE unanchored
    penetration — thread up at the far end of a line whose start was never
    stitched. It must sew two, one per end.

    Asserted as "a penetration exists at each endpoint", not by stream position:
    `_lock_stream` inserts the tie-in immediately after the FIRST stitch (a
    first draft of this test indexed pens[1] and met the lock at 5.7mm instead
    of the far end). Lock points sit >=0.5mm off the path, so a 0.05mm
    tolerance cannot confuse them with the endpoints."""
    reb = rebuild_design(_run_design(2), force=True)
    pens = [(s.x, s.y) for s in reb.stitches if s.command == "STITCH"]
    assert reb.objects[0].penetration_count == 2
    for end in ((5.0, 5.0), (7.0, 5.0)):
        assert any(math.hypot(x - end[0], y - end[1]) < 0.05 for x, y in pens), (
            f"no penetration at path end {end} — the line is unanchored there"
        )


def test_double_run_counts_both_passes_from_an_anchored_start():
    """RUNNING_DOUBLE retraces backward: N forward + (N-1) return, MINUS ONE.

    The minus one is the penetration floor, not the entry defect: the return
    pass's first point re-enters the hole the forward pass just left (an
    A-B-A reversal at the turnaround), and `_drop_floor_reversals` removes it —
    measured on this exact design: forward ...19, 21, 23 then return 19, the
    return's 21 gone. That is the floor doing its job. What THIS test guards is
    the entry: the count is measured from an anchored start, and losing the
    entry again would read N + (N-1) - 2."""
    n = 10
    reb = rebuild_design(_run_design(n, StitchType.RUNNING_DOUBLE), force=True)
    assert reb.objects[0].penetration_count == n + (n - 1) - 1
    pens = [(s.x, s.y) for s in reb.stitches if s.command == "STITCH"]
    assert any(math.hypot(x - 5.0, y - 5.0) < 0.05 for x, y in pens)
