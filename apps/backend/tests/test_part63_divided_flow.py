"""Divided Stitch Flow: one divide line, two flow regions (v2 Part 63).

The contract, in gate order:

1. a valid divide splits a TATAMI object into two half-planes and each side's
   rows really run at that side's angle — the line whose midpoint lies on the
   side claims it, an unclaimed side sews at the automatic angle;
2. no divide means exactly Part 62 behaviour — `flow_line_b` alone is ignored,
   and set-divide-then-remove returns the byte-identical stream;
3. the richer metadata survives JSON round trips under its camel names, and
   designs saved before the fields existed (including Part-62-shaped ones that
   already carry `flowLine`) load and rebuild unchanged;
4. a neighbour object is never touched by another object's divide.

Most tests use a synthetic two-object design: rebuild is the unit under test
and a 40x20 rectangle makes the per-side row angles exact and fast. One test
runs the real digitizer output through the legacy path.
"""

from __future__ import annotations

import cv2
import numpy as np
from helpers import angle_err as _angle_err
from helpers import row_angle, stream_of as _stream

from app.models.design import (
    ColorStop,
    ConnectMethod,
    Design,
    DesignObject,
    Point,
    StitchType,
    UnderlayType,
)
from app.services.digitizer import (
    _flow_divide_valid,
    _flow_side_angles,
    _split_mask_by_line,
    rebuild_design,
)


def _obj(seq: int, contour, stop: int = 1, angle: float = 0.0) -> DesignObject:
    return DesignObject(
        sequence_order=seq, name=f"Fill {seq}", stitch_type=StitchType.TATAMI,
        color_stop=stop, density=2.0, stitch_angle=angle,
        underlay_type=UnderlayType.NONE, pull_compensation=0.0,
        connect_method=ConnectMethod.TRIM, stitch_count=0, contour=contour,
    )


def _design() -> Design:
    """A 40x20 rectangle and, well clear of it, a 10x10 square neighbour."""
    rect = [Point(x=0, y=0), Point(x=40, y=0), Point(x=40, y=20), Point(x=0, y=20)]
    sq = [Point(x=60, y=0), Point(x=70, y=0), Point(x=70, y=10), Point(x=60, y=10)]
    return Design(
        name="t", width_mm=70, height_mm=20, stitch_count=0, version=1,
        status="digitized",
        color_stops=[ColorStop(stop_number=1, thread_brand="M", catalog_number="1",
                               thread_name="a", hex="#112233", stitch_count=0)],
        objects=[_obj(1, rect), _obj(2, sq)], stitches=[],
    )


# Vertical divide through the rectangle's middle; left line at 90°, right at 0°.
DIVIDE = [Point(x=20, y=-5), Point(x=20, y=25)]
LEFT_LINE = [Point(x=10, y=5), Point(x=10, y=15)]
RIGHT_LINE = [Point(x=25, y=10), Point(x=35, y=10)]


def _with(design: Design, idx: int, **fields) -> Design:
    objs = list(design.objects)
    objs[idx] = objs[idx].model_copy(update=fields)
    return design.model_copy(update={"objects": objs})


def _row_angle(design: Design, x0: float, x1: float) -> float:
    return row_angle(design, x0, x1)


# ── the side-assignment helper ────────────────────────────────────────────────


def test_each_side_gets_the_line_whose_midpoint_lies_on_it():
    pos, neg = _flow_side_angles(DIVIDE, LEFT_LINE, RIGHT_LINE, 37.0)
    # divide points +y; left of it (smaller x) is the positive side
    assert pos == 90.0 and neg == 0.0
    # order of the two candidate lines does not matter when they sit apart
    pos2, neg2 = _flow_side_angles(DIVIDE, RIGHT_LINE, LEFT_LINE, 37.0)
    assert (pos2, neg2) == (pos, neg)


def test_an_unclaimed_side_sews_at_the_automatic_angle():
    pos, neg = _flow_side_angles(DIVIDE, LEFT_LINE, None, 37.0)
    assert pos == 90.0 and neg == 37.0
    # two lines crowding one side: the first claims it, the other side stays automatic
    left2 = [Point(x=5, y=5), Point(x=15, y=5)]
    pos, neg = _flow_side_angles(DIVIDE, LEFT_LINE, left2, 37.0)
    assert pos == 90.0 and neg == 37.0


def test_a_midpoint_exactly_on_the_divide_claims_nothing():
    on_divide = [Point(x=15, y=10), Point(x=25, y=10)]  # midpoint x=20, on the line
    pos, neg = _flow_side_angles(DIVIDE, on_divide, None, 37.0)
    assert pos == 37.0 and neg == 37.0


def test_degenerate_divides_are_invalid_not_guessed():
    assert not _flow_divide_valid(None)
    assert not _flow_divide_valid([])
    assert not _flow_divide_valid([Point(x=5, y=5)])
    assert not _flow_divide_valid([Point(x=5, y=5), Point(x=5, y=5)])
    assert _flow_divide_valid(DIVIDE)


def test_the_half_plane_masks_partition_the_region():
    mask = np.zeros((50, 80), np.uint8)
    cv2.rectangle(mask, (10, 10), (69, 39), 255, -1)
    pos, neg = _split_mask_by_line(mask, (40.0, 0.0), (40.0, 50.0))
    assert cv2.countNonZero(pos) > 0 and cv2.countNonZero(neg) > 0
    both = cv2.bitwise_or(pos, neg)
    assert np.array_equal(both > 0, mask > 0), "gap or spill outside the region"
    assert cv2.countNonZero(cv2.bitwise_and(pos, neg)) == 0, "sides overlap"


# ── the rebuild contract ──────────────────────────────────────────────────────


def test_divided_rows_really_run_at_each_sides_angle():
    d = _with(_design(), 0, flow_divide=DIVIDE, flow_line=LEFT_LINE,
              flow_line_b=RIGHT_LINE)
    built = rebuild_design(d)
    assert _stream(built) != _stream(rebuild_design(_design()))
    left = _row_angle(built, 1, 18)
    right = _row_angle(built, 22, 39)
    assert _angle_err(left, 90.0) < 10.0, f"left rows at {left:.1f}, wanted 90"
    assert _angle_err(right, 0.0) < 10.0, f"right rows at {right:.1f}, wanted 0"
    # the metadata rides through the rebuild, so a second Apply keeps behaving
    assert built.objects[0].flow_divide is not None
    assert built.objects[0].flow_line_b is not None


def test_an_unclaimed_side_rebuilds_at_the_automatic_angle():
    # only the left line: right half must sew at the stored stitch_angle (0°)
    d = _with(_design(), 0, flow_divide=DIVIDE, flow_line=LEFT_LINE)
    built = rebuild_design(d)
    assert _angle_err(_row_angle(built, 1, 18), 90.0) < 10.0
    assert _angle_err(_row_angle(built, 22, 39), 0.0) < 10.0


def test_a_divide_that_misses_the_object_sews_one_region():
    # divide far left of everything: the whole object is one side; the line on
    # that side claims it, so the result equals the Part 62 single-line build
    off = [Point(x=-30, y=-5), Point(x=-30, y=25)]
    line = [Point(x=10, y=5), Point(x=10, y=15)]
    divided = rebuild_design(_with(_design(), 0, flow_divide=off, flow_line=line))
    single = rebuild_design(_with(_design(), 0, flow_line=line))
    assert _stream(divided) == _stream(single)


def test_without_a_divide_flow_line_b_is_ignored():
    base = rebuild_design(_design())
    with_b = rebuild_design(_with(_design(), 0, flow_line_b=RIGHT_LINE))
    assert _stream(with_b) == _stream(base)


def test_removing_the_divide_restores_the_exact_part62_stream():
    part62 = rebuild_design(_with(_design(), 0, flow_line=LEFT_LINE))
    d = _with(_design(), 0, flow_divide=DIVIDE, flow_line=LEFT_LINE,
              flow_line_b=RIGHT_LINE)
    removed = _with(d, 0, flow_divide=None, flow_line_b=None)
    assert _stream(rebuild_design(removed)) == _stream(part62)


def test_a_neighbour_is_untouched_by_the_divide():
    base = rebuild_design(_design())
    divided = rebuild_design(_with(_design(), 0, flow_divide=DIVIDE,
                                   flow_line=LEFT_LINE, flow_line_b=RIGHT_LINE))

    def square_stitches(design):
        return [(round(s.x, 3), round(s.y, 3)) for s in design.stitches
                if str(s.command) == "STITCH" and s.x >= 59.0]

    assert square_stitches(base) == square_stitches(divided)


# ── persistence and legacy ────────────────────────────────────────────────────


def test_the_divide_survives_a_json_round_trip_under_camel_names():
    d = _with(_design(), 0, flow_divide=DIVIDE, flow_line=LEFT_LINE,
              flow_line_b=RIGHT_LINE)
    saved = d.model_dump(by_alias=True)
    assert saved["objects"][0]["flowDivide"] == [{"x": 20.0, "y": -5.0},
                                                 {"x": 20.0, "y": 25.0}]
    assert saved["objects"][0]["flowLineB"] == [{"x": 25.0, "y": 10.0},
                                                {"x": 35.0, "y": 10.0}]
    loaded = Design.model_validate(saved)
    assert [(p.x, p.y) for p in loaded.objects[0].flow_divide] == [(20.0, -5.0), (20.0, 25.0)]
    assert _stream(rebuild_design(loaded)) == _stream(rebuild_design(d))


def test_part62_shaped_saves_load_and_rebuild_unchanged():
    d = _with(_design(), 0, flow_line=LEFT_LINE)
    legacy = d.model_dump(by_alias=True)
    for o in legacy["objects"]:
        o.pop("flowDivide", None)  # exactly what a Part 62 save looks like:
        o.pop("flowLineB", None)   # flowLine present, the new fields absent
    loaded = Design.model_validate(legacy)
    assert all(o.flow_divide is None and o.flow_line_b is None for o in loaded.objects)
    assert _stream(rebuild_design(loaded)) == _stream(rebuild_design(d))


def test_a_real_digitized_design_rebuilds_identically_without_flow_metadata():
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[0] / "fixtures/quality_bench/01_flat_2color_logo.png"
    from app.services.digitizer import digitize_image

    cv2.setRNGSeed(1234)
    d = digitize_image(fixture.read_bytes(), "cotton", "100x100", 2)
    pre63 = d.model_dump(by_alias=True)
    for o in pre63["objects"]:
        o.pop("flowDivide", None)
        o.pop("flowLineB", None)
    assert _stream(rebuild_design(Design.model_validate(pre63))) == _stream(rebuild_design(d))
