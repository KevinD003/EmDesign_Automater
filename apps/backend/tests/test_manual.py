"""Manual digitizing — running stitch along a drawn path (rebuild RUNNING branch)."""

from __future__ import annotations

from app.models.design import ColorStop, Design, DesignObject, Point
from app.services.digitizer import rebuild_design


def _design(objs):
    return Design(
        name="manual",
        stitch_count=0,
        version=1,
        status="draft",
        color_stops=[
            ColorStop(stop_number=1, thread_brand="Manual", catalog_number="-", thread_name="C1", hex="#3a6ea5", stitch_count=0)
        ],
        objects=objs,
        stitches=[],
    )


def _obj(stitch_type, contour, **kw):
    return DesignObject(
        sequence_order=kw.get("seq", 1),
        name="obj",
        stitch_type=stitch_type,
        color_stop=1,
        density=kw.get("density", 0),
        stitch_angle=0,
        underlay_type=kw.get("underlay", "NONE"),
        pull_compensation=0,
        connect_method="TRIM",
        stitch_count=0,
        contour=contour,
    )


def test_running_stitch_follows_path_not_fill():
    path = [Point(x=10, y=10), Point(x=40, y=10), Point(x=40, y=40)]  # ~60mm L-path
    single = rebuild_design(_design([_obj("RUNNING_SINGLE", path)]))
    double = rebuild_design(_design([_obj("RUNNING_DOUBLE", path)]))
    assert single.objects[0].stitch_count > 0
    # double pass ~= twice the single-pass stitch count (retrace)
    assert double.objects[0].stitch_count > single.objects[0].stitch_count
    # a running stitch is far leaner than a tatami fill of the same triangle
    fill = rebuild_design(_design([_obj("TATAMI", path, density=1.4, underlay="EDGE_WALK")]))
    assert fill.objects[0].stitch_count > double.objects[0].stitch_count


def test_manual_run_stitch_length_capped():
    # a single 100mm segment must be subdivided to <= machine max, not one giant stitch
    path = [Point(x=0, y=0), Point(x=100, y=0)]
    out = rebuild_design(_design([_obj("RUNNING_SINGLE", path)]))
    xs = [s for s in out.stitches if s.command in ("STITCH", "JUMP")]
    assert len(xs) >= 15  # 100mm / ~6mm step
    # no two consecutive stitch points more than ~7mm apart
    pts = [(s.x, s.y) for s in out.stitches if s.command == "STITCH"]
    gaps = [((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:])]
    assert gaps and max(gaps) <= 7.0


def test_double_run_has_no_zero_length_turnaround():
    """Regression: RUNNING_DOUBLE must not duplicate the turnaround vertex (0-length stitch)."""
    out = rebuild_design(_design([_obj("RUNNING_DOUBLE", [Point(x=0, y=0), Point(x=30, y=0)])]))
    pts = [(s.x, s.y) for s in out.stitches if s.command == "STITCH"]
    gaps = [((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:])]
    assert gaps and min(gaps) > 1e-6, "no zero-length stitch at the pass junction"


def test_mixed_run_and_fill_rebuild():
    run = _obj("RUNNING_DOUBLE", [Point(x=5, y=5), Point(x=45, y=5)], seq=1)
    fill = _obj("TATAMI", [Point(x=50, y=50), Point(x=80, y=50), Point(x=80, y=80), Point(x=50, y=80)],
               seq=2, density=1.4, underlay="EDGE_WALK")
    out = rebuild_design(_design([run, fill]))
    assert len(out.objects) == 2
    assert out.stitch_count > 0
