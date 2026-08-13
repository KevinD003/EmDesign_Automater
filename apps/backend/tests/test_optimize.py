"""Phase 8 — path optimization + quality analysis."""

from __future__ import annotations

import cv2
import numpy as np

from app.services import optimizer
from app.services.digitizer import digitize_image


def _multi_region_image() -> bytes:
    """Three separated same-color squares in a row → three fillable objects."""
    img = np.full((200, 320, 3), 255, np.uint8)
    for x in (20, 140, 260):
        cv2.rectangle(img, (x, 80), (x + 40, 120), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _digitized():
    return digitize_image(_multi_region_image(), "cotton", "100x100", max_colors=2)


def test_optimize_never_worsens_travel():
    design = _digitized()
    assert len(design.objects) >= 2
    optimized, report = optimizer.optimize_path(design)
    # travel must never increase; report is internally consistent
    assert report.after.travel_mm <= report.before.travel_mm
    assert optimized.stitch_count > 0
    if report.reordered:
        assert report.travel_saved_mm >= 0
        assert report.after.travel_mm < report.before.travel_mm


def test_optimize_reduces_travel_on_a_bad_order():
    """Force a poor object order → NN reorder should cut travel."""
    design = _digitized()
    if len(design.objects) < 3:
        return  # need ≥3 to have a suboptimal tour
    # Put the middle square last so 1→3→2 zig-zags across the design.
    objs = sorted(design.objects, key=lambda o: o.sequence_order)
    left, mid, right = objs[0], objs[1], objs[2]
    bad = design.model_copy(
        update={
            "objects": [
                left.model_copy(update={"sequence_order": 1}),
                right.model_copy(update={"sequence_order": 2}),
                mid.model_copy(update={"sequence_order": 3}),
            ]
        }
    )
    from app.services.digitizer import rebuild_design

    bad = rebuild_design(bad)
    _, report = optimizer.optimize_path(bad)
    assert report.reordered
    assert report.after.travel_mm < report.before.travel_mm


def test_optimize_noop_on_non_digitized():
    from app.models.design import Design

    plain = Design(name="imported", stitch_count=1, objects=[], color_stops=[], stitches=[])
    out, report = optimizer.optimize_path(plain)
    assert out is plain and report.reordered is False
    assert report.note


def test_quality_report_structure():
    design = _digitized()
    q = optimizer.analyze_quality(design)
    assert 0 <= q.score <= 100
    assert q.grade in {"A", "B", "C", "D", "F"}
    assert q.metrics.stitch_count == len(design.stitches)
    assert q.findings  # always at least one (an "info: clean" entry when spotless)


def test_quality_flags_long_stitches():
    from app.models.design import Design, Stitch

    # two stitches 50mm apart → one over-long stitch
    d = Design(
        name="x", stitch_count=2, objects=[], color_stops=[],
        stitches=[Stitch(x=0, y=0, command="STITCH"), Stitch(x=50, y=0, command="STITCH")],
    )
    q = optimizer.analyze_quality(d)
    assert any(f.code == "long_stitch" for f in q.findings)
    assert q.score < 100
    assert q.max_stitch_mm == 50.0


# ── Consolidated quality report (hoop fit, stitch-length stats, jump rate) ─────


def _stitch_design(stitches, **kw):
    from app.models.design import Design

    return Design(name="q", stitch_count=len(stitches), objects=[], color_stops=[],
                  stitches=stitches, **kw)


def _st(x, y, command="STITCH"):
    from app.models.design import Stitch

    return Stitch(x=x, y=y, command=command)


def test_quality_hoop_overflow_is_error_and_penalised():
    d = _stitch_design([_st(0, 0), _st(5, 0)], width_mm=150, height_mm=50, hoop_size="100x100")
    q = optimizer.analyze_quality(d)
    assert q.hoop_fit is False
    overflow = next(f for f in q.findings if f.code == "hoop_overflow")
    assert overflow.severity == "error"
    assert q.score == 100 - optimizer.HOOP_OVERFLOW_PENALTY


def test_quality_hoop_fit_true_no_penalty():
    d = _stitch_design([_st(0, 0), _st(5, 0)], width_mm=90, height_mm=90, hoop_size="100x100mm")
    q = optimizer.analyze_quality(d)
    assert q.hoop_fit is True
    assert not any(f.code == "hoop_overflow" for f in q.findings)
    assert q.score == 100


def test_quality_hoop_unknown_is_none_no_penalty():
    for hoop in (None, "garbage", "13cm round"):
        d = _stitch_design([_st(0, 0), _st(5, 0)], width_mm=500, height_mm=500, hoop_size=hoop)
        q = optimizer.analyze_quality(d)
        assert q.hoop_fit is None
        assert not any(f.code == "hoop_overflow" for f in q.findings)


def test_quality_stitch_length_stats_ignore_jump_landings():
    # STITCH steps: 0→3 (3mm) and 53→57 (4mm). The 50→53 step lands after a JUMP,
    # so it counts for long/tiny screening but NOT for max/mean stitch length.
    d = _stitch_design([_st(0, 0), _st(3, 0), _st(50, 0, "JUMP"), _st(53, 0), _st(57, 0)])
    q = optimizer.analyze_quality(d)
    assert q.max_stitch_mm == 4.0
    assert q.mean_stitch_mm == 3.5


def test_quality_jump_rate_reported_without_changing_jump_penalty():
    # 2 jumps in a 10-entry stream → 200.0 per 1,000; far below the many_jumps
    # threshold (needs >max(20, 10% of stream)), so no penalty finding appears.
    stitches = [_st(i * 5, 0) for i in range(4)]
    stitches += [_st(30, 0, "JUMP"), _st(35, 0)]
    stitches += [_st(40 + i * 5, 0) for i in range(3)]
    stitches += [_st(80, 0, "JUMP")]
    d = _stitch_design(stitches)
    q = optimizer.analyze_quality(d)
    assert q.jumps_per_1000 == 200.0
    rate = next(f for f in q.findings if f.code == "jump_rate")
    assert rate.severity == "info"
    # States the value and the TRIM cost — deliberately NOT an "industry target":
    # web research (docs/COMPETITOR-COMPARISON.md) found no published jumps/1,000
    # benchmark, so the message must not invent one.
    assert "1,000" in rate.message and "trim" in rate.message.lower()
    assert not any(f.code == "many_jumps" for f in q.findings)
    assert q.score == 100  # the info finding never affects the score


def test_quality_report_model_defaults_keep_old_payloads_valid():
    from app.models.design import PathMetrics, QualityReport

    q = QualityReport(metrics=PathMetrics())  # pre-consolidation payload shape
    assert (q.max_stitch_mm, q.mean_stitch_mm, q.jumps_per_1000) == (0.0, 0.0, 0.0)
    assert q.hoop_fit is None
    # wire names are camelCase — the frontend is built against these exact fields
    wire = q.model_dump(by_alias=True)
    for key in ("maxStitchMm", "meanStitchMm", "jumpsPer1000", "hoopFit"):
        assert key in wire


# ── CTO A9/C11: real rejection criteria ───────────────────────────────────────
# The pre-A9 scorer certified broken output (8mm lettering with jump-crossed
# counters and no ties scored 98/A). Each detector is pinned on constructed
# bad input AND on its clean twin, so neither false negatives nor false
# positives can drift back in.


def _lockish_tail(x, y):
    """Three sub-mm penetrations — the shape of a tie."""
    return [_st(x, y), _st(x + 0.5, y), _st(x, y + 0.5), _st(x, y)]


def _run_pts(x0, n, pitch=2.0, y=0.0):
    return [_st(x0 + i * pitch, y) for i in range(n)]


def test_quality_flags_unlocked_thread_ends():
    d = _stitch_design([*_run_pts(0, 20), _st(38, 0, "TRIM"), _st(60, 0, "JUMP"),
                        *_run_pts(60, 20), _st(98, 0, "END")])
    q = optimizer.analyze_quality(d)
    f = next(f for f in q.findings if f.code == "unlocked_ends")
    assert f.severity == "error" and f.count == 4  # both ends of both blocks
    assert q.score < 90


def test_quality_accepts_locked_thread_ends():
    block = [*_lockish_tail(0, 0), *_run_pts(0, 20), *_lockish_tail(38, 0)]
    d = _stitch_design([*block, _st(38, 0, "TRIM"), _st(38, 0, "END")])
    q = optimizer.analyze_quality(d)
    assert not any(f.code == "unlocked_ends" for f in q.findings)


def test_quality_flags_attached_travel_over_open_fabric():
    from app.models.design import (
        ColorStop,
        ConnectMethod,
        DesignObject,
        Point,
        StitchType,
        UnderlayType,
    )

    def _obj(seq, x0):
        return DesignObject(
            sequence_order=seq, name=f"o{seq}", stitch_type=StitchType.TATAMI,
            color_stop=1, density=2.5, stitch_angle=0.0,
            underlay_type=UnderlayType.NONE, pull_compensation=0.0,
            connect_method=ConnectMethod.TRIM, penetration_count=0,
            contour=[Point(x=x0, y=0), Point(x=x0 + 10, y=0),
                     Point(x=x0 + 10, y=10), Point(x=x0, y=10)],
        )

    stops = [ColorStop(stop_number=1, thread_brand="M", catalog_number="1",
                       thread_name="a", hex="#112233", stitch_count=0)]
    # attached stitch straight across the 30mm void between the squares
    crossing = [_st(5, 5), _st(45, 5)]
    d = _stitch_design(crossing)
    d = d.model_copy(update={"objects": [_obj(1, 0), _obj(2, 40)], "color_stops": stops})
    q = optimizer.analyze_quality(d)
    assert any(f.code == "open_fabric_travel" and f.severity == "error" for f in q.findings)

    # the same jump AFTER a trim is detached thread — normal, not a whisker
    trimmed = [_st(5, 5), _st(5, 5, "TRIM"), _st(45, 5, "JUMP"), _st(45, 5), _st(46, 5)]
    d2 = _stitch_design(trimmed)
    d2 = d2.model_copy(update={"objects": [_obj(1, 0), _obj(2, 40)], "color_stops": stops})
    q2 = optimizer.analyze_quality(d2)
    assert not any(f.code == "open_fabric_travel" for f in q2.findings)


def test_quality_flags_satin_wider_than_any_real_column():
    zig = []
    for i in range(12):  # 10mm-wide zigzag — twice any legitimate satin column
        zig.append(_st(i * 0.7, 0.0 if i % 2 else 10.0))
    q = optimizer.analyze_quality(_stitch_design(zig))
    assert any(f.code == "satin_too_wide" and f.severity == "error" for f in q.findings)


def test_quality_flags_uniform_fill_angles_but_not_varied():
    from app.models.design import ConnectMethod, DesignObject, Point, StitchType, UnderlayType

    def _fill(seq, angle):
        return DesignObject(
            sequence_order=seq, name=f"f{seq}", stitch_type=StitchType.TATAMI,
            color_stop=1, density=2.5, stitch_angle=angle,
            underlay_type=UnderlayType.NONE, pull_compensation=0.0,
            connect_method=ConnectMethod.TRIM, penetration_count=0,
            contour=[Point(x=0, y=0), Point(x=10, y=0), Point(x=10, y=10), Point(x=0, y=10)],
        )

    flat = _stitch_design(_run_pts(0, 4)).model_copy(
        update={"objects": [_fill(1, 0.0), _fill(2, 0.0), _fill(3, 0.0)]})
    q = optimizer.analyze_quality(flat)
    assert any(f.code == "uniform_fill_angles" for f in q.findings)

    varied = _stitch_design(_run_pts(0, 4)).model_copy(
        update={"objects": [_fill(1, 0.0), _fill(2, 45.0), _fill(3, 90.0)]})
    assert not any(f.code == "uniform_fill_angles"
                   for f in optimizer.analyze_quality(varied).findings)


def test_quality_flags_high_trim_rate():
    pts = []
    for k in range(10):  # 10 trims over ~40 stitches = 250/1000
        pts.extend(_run_pts(k * 12, 4))
        pts.append(_st(k * 12 + 6, 0, "TRIM"))
    q = optimizer.analyze_quality(_stitch_design(pts))
    assert any(f.code == "high_trim_rate" for f in q.findings)
