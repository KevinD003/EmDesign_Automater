"""Stitch Flow: a persisted direction line for fill objects (v2 Part 62).

The contract, in the order the gates state it:

1. a stored line produces a real stitch difference on the object it is set on —
   and the rows actually run along the line, which is the point of the feature;
2. objects without a line rebuild exactly as before — byte-identical streams;
3. the line survives JSON round-trips, and designs saved before the field
   existed load and rebuild unchanged;
4. removing the line returns the object to its automatic angle — which is why
   the override never overwrites ``stitch_angle``.
"""

from __future__ import annotations

import math

from helpers import digitized_fixture as _digitized
from helpers import row_angle, stream_of as _stream

from app.models.design import Design, Point
from app.services.digitizer import _flow_line_angle, rebuild_design


def _tatami_index(design: Design) -> int:
    for i, o in enumerate(design.objects):
        st = o.stitch_type.value if hasattr(o.stitch_type, "value") else o.stitch_type
        if st == "TATAMI" and o.contour:
            return i
    raise AssertionError("fixture produced no tatami object")


def _with_line(design: Design, idx: int, line) -> Design:
    objs = list(design.objects)
    objs[idx] = objs[idx].model_copy(update={"flow_line": line})
    return design.model_copy(update={"objects": objs})


def _object_row_angle(design: Design, idx: int) -> float:
    """Row orientation inside the object's bbox — helpers.row_angle on it."""
    target = design.objects[idx]
    xs = [p.x for p in target.contour]
    ys = [p.y for p in target.contour]
    return row_angle(design, min(xs), max(xs), min(ys), max(ys))


# ── the angle helper ──────────────────────────────────────────────────────────


def test_flow_line_angle_matches_the_drawn_direction():
    assert _flow_line_angle([Point(x=0, y=0), Point(x=10, y=0)], 77.0) == 0.0
    assert _flow_line_angle([Point(x=0, y=0), Point(x=0, y=10)], 77.0) == 90.0
    got = _flow_line_angle([Point(x=0, y=0), Point(x=10, y=10)], 77.0)
    assert abs(got - 45.0) < 1e-9
    # direction has no head or tail: the reversed line is the same angle
    assert _flow_line_angle([Point(x=10, y=10), Point(x=0, y=0)], 77.0) == got


def test_degenerate_lines_fall_back_rather_than_invent_an_angle():
    assert _flow_line_angle(None, 33.0) == 33.0
    assert _flow_line_angle([], 33.0) == 33.0
    assert _flow_line_angle([Point(x=5, y=5)], 33.0) == 33.0
    assert _flow_line_angle([Point(x=5, y=5), Point(x=5, y=5)], 33.0) == 33.0


# ── the rebuild contract ──────────────────────────────────────────────────────


def test_a_flow_line_really_changes_the_stitches_and_rows_follow_it():
    d = _digitized()
    base = rebuild_design(d)
    idx = _tatami_index(d)

    # A line at 90 degrees to whatever the object currently sews at.
    current = _object_row_angle(base, idx)
    want = (current + 90.0) % 180.0
    a = math.radians(want)
    o = d.objects[idx]
    cx = sum(p.x for p in o.contour) / len(o.contour)
    cy = sum(p.y for p in o.contour) / len(o.contour)
    line = [Point(x=cx - 5 * math.cos(a), y=cy - 5 * math.sin(a)),
            Point(x=cx + 5 * math.cos(a), y=cy + 5 * math.sin(a))]

    flowed = rebuild_design(_with_line(d, idx, line))
    assert _stream(flowed) != _stream(base), "the line produced no stitch difference"

    got = _object_row_angle(flowed, idx)
    err = abs((got - want + 90) % 180 - 90)
    assert err < 10.0, f"rows at {got:.1f} deg, line asked for {want:.1f}"

    # The line rides through the rebuild, so a second Apply keeps behaving.
    assert flowed.objects[idx].flow_line is not None


def test_objects_without_a_line_rebuild_identically():
    d = _digitized()
    assert _stream(rebuild_design(d)) == _stream(rebuild_design(d))
    # Setting and then removing the line returns the exact original stream —
    # possible only because the override never overwrites stitch_angle.
    idx = _tatami_index(d)
    line = [Point(x=0, y=0), Point(x=10, y=3)]
    removed = _with_line(_with_line(d, idx, line), idx, None)
    assert _stream(rebuild_design(removed)) == _stream(rebuild_design(d))


def test_other_objects_are_untouched_by_a_neighbours_line():
    d = _digitized()
    base = rebuild_design(d)
    idx = _tatami_index(d)
    flowed = rebuild_design(_with_line(d, idx, [Point(x=0, y=0), Point(x=7, y=11)]))

    target = d.objects[idx]
    xs = [p.x for p in target.contour]
    ys = [p.y for p in target.contour]

    def outside(design):
        out = []
        for s in design.stitches:
            if str(s.command) != "STITCH":
                continue
            if not (min(xs) - 1 <= s.x <= max(xs) + 1 and min(ys) - 1 <= s.y <= max(ys) + 1):
                out.append((round(s.x, 3), round(s.y, 3)))
        return out

    assert outside(base) == outside(flowed)


# ── persistence and legacy ────────────────────────────────────────────────────


def test_the_line_survives_a_json_round_trip_under_its_camel_name():
    d = _digitized()
    idx = _tatami_index(d)
    line = [Point(x=1.5, y=2.5), Point(x=9.5, y=4.5)]
    saved = _with_line(d, idx, line).model_dump(by_alias=True)
    assert saved["objects"][idx]["flowLine"] == [
        {"x": 1.5, "y": 2.5}, {"x": 9.5, "y": 4.5}]
    loaded = Design.model_validate(saved)
    assert [(p.x, p.y) for p in loaded.objects[idx].flow_line] == [(1.5, 2.5), (9.5, 4.5)]


def test_designs_saved_before_the_field_existed_load_and_rebuild():
    d = _digitized()
    legacy = d.model_dump(by_alias=True)
    for o in legacy["objects"]:
        o.pop("flowLine", None)   # exactly what a pre-Part-62 save looks like
    loaded = Design.model_validate(legacy)
    assert all(o.flow_line is None for o in loaded.objects)
    assert _stream(rebuild_design(loaded)) == _stream(rebuild_design(d))
