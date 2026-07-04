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
