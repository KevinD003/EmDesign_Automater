"""CTO-review §8 acceptance probes (docs/CTO-REVIEW-2026-08-07.md).

One test per probe, run against the CURRENT tree. Probes whose target is not
met yet are committed as strict xfails with the measured number in the reason
— never skipped — and flipped to plain asserts by the Phase-A item that fixes
them. Baseline measured 2026-08-08 at the reconciliation merge:

  P1 ring crossings   92        -> A3 (open)
  P2 lock coverage    96/96     -> A2 (fixed: first-start tie-in was 95/96)
  P3 lettering        102 st/letter satin (target >=150) -> Phase B4 (open)
  P4 satin angle      0deg == 77deg (no-op)  -> A5 (open)
  P5 applique STOP    absent    -> A4 (open)
  P6 fidelity         digitize 4820 vs rebuild 2298 stitches -> A8 (open)
"""

from __future__ import annotations

import itertools
import math
import pathlib

import cv2
import numpy as np
import pytest

from app.models.design import (
    ColorStop,
    ConnectMethod,
    Design,
    DesignObject,
    Point,
    StitchType,
    UnderlayType,
)
from app.services.digitizer import digitize_image, rebuild_design
from app.services.embroidery_io import read_embroidery, write_embroidery


@pytest.fixture(scope="module")
def ring() -> Design:
    """A letter-'o'-class ring: solid disc with an open counter."""
    img = np.full((600, 600, 3), 255, np.uint8)
    cv2.circle(img, (300, 300), 200, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (300, 300), 110, (255, 255, 255), -1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    cv2.setRNGSeed(1234)
    return digitize_image(buf.tobytes(), "cotton", "100x100", 2)


def _counter_crossings(design: Design) -> int:
    """Needle-path segments that pass through the counter's open area.

    The hole polygon is shrunk 7% so segments that merely kiss the rim do not
    count; each STITCH/JUMP segment is sampled every 0.3mm.
    """
    hole = next((o.holes[0] for o in design.objects if o.holes), None)
    assert hole is not None, "ring digitized without its counter"
    poly = np.array([[p.x, p.y] for p in hole], np.float32)
    cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
    shrunk = ((poly - [cx, cy]) * 0.93 + [cx, cy]).astype(np.float32)

    crossings = 0
    prev = None
    for s in design.stitches:
        cmd = str(s.command)
        if cmd in ("STITCH", "JUMP"):
            if prev is not None:
                n = max(2, int(math.dist(prev, (s.x, s.y)) / 0.3))
                for i in range(1, n):
                    t = i / n
                    x = prev[0] + (s.x - prev[0]) * t
                    y = prev[1] + (s.y - prev[1]) * t
                    if cv2.pointPolygonTest(shrunk, (float(x), float(y)), False) >= 0:
                        crossings += 1
                        break
            prev = (s.x, s.y)
        else:
            prev = (s.x, s.y)
    return crossings


def _lockish(pts: list[tuple[float, float]]) -> bool:
    """A lock: at least two consecutive segments of <=1.0mm."""
    return sum(1 for a, b in zip(pts, pts[1:]) if math.dist(a, b) <= 1.0) >= 2


def _satin_bar(stitch_type: StitchType, angle: float,
               underlay: UnderlayType = UnderlayType.NONE) -> Design:
    o = DesignObject(
        sequence_order=1, name="s", stitch_type=stitch_type, color_stop=1,
        density=4.0, stitch_angle=angle, underlay_type=underlay,
        pull_compensation=0.0, connect_method=ConnectMethod.TRIM,
        stitch_count=0,
        contour=[Point(x=0, y=0), Point(x=30, y=0), Point(x=30, y=8), Point(x=0, y=8)],
    )
    return Design(
        name="t", width_mm=30, height_mm=8, stitch_count=0, version=1,
        status="digitized",
        color_stops=[ColorStop(stop_number=1, thread_brand="M", catalog_number="1",
                               thread_name="a", hex="#112233", stitch_count=0)],
        objects=[o], stitches=[],
    )


# ── P1: ring test — zero crossings of the open counter ───────────────────────


def test_probe1_ring_has_zero_counter_crossings(ring):
    # A3 (2026-08-08): baseline was 92 trimmed jumps straight across the
    # counter. Two routing fixes took it to zero — adaptive detour resampling
    # on concave (hole) boundaries, and a routing mask padded by the border
    # overhang + pull comp so border-phase connections are routable at all.
    assert _counter_crossings(ring) == 0


# ── P2: lock test — tie-off before every trim, tie-in at every start ─────────


@pytest.fixture(scope="module")
def two_color() -> Design:
    """Two separated SAME-colour blobs plus a third colour.

    Same-colour separation is what forces explicit TRIMs (a colour change
    carries an implicit machine trim and needs none). The ring stopped being
    usable for the lock probe the moment A3 landed — with every connection
    routed inside the body it sews with ZERO trims.
    """
    img = np.full((500, 900, 3), 255, np.uint8)
    cv2.circle(img, (180, 250), 120, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (720, 250), 120, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (450, 250), 90, (150, 60, 40), -1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    cv2.setRNGSeed(1234)
    return digitize_image(buf.tobytes(), "cotton", "100x100", 3)


def test_probe2_every_thread_end_is_locked_in_the_exported_dst(two_color):
    sts = read_embroidery(write_embroidery(two_color, "dst"), "dst").stitches

    trim_idx = [i for i, s in enumerate(sts) if str(s.command) == "TRIM"]
    assert trim_idx, "probe needs at least one trim"
    for i in trim_idx:
        pts = [(s.x, s.y) for s in sts[max(0, i - 5):i] if str(s.command) == "STITCH"]
        assert len(pts) >= 3 and _lockish(pts), f"trim at {i} has no tie-off"

    starts = []
    in_block = False
    for i, s in enumerate(sts):
        c = str(s.command)
        if c in ("TRIM", "COLOR_CHANGE"):
            in_block = False
        elif c == "STITCH" and not in_block:
            starts.append(i)
            in_block = True
    assert starts
    for i in starts:
        pts = [(s.x, s.y) for s in sts[i:i + 6] if str(s.command) == "STITCH"]
        assert len(pts) >= 3 and _lockish(pts), (
            f"block start at {i} has no tie-in "
            f"({'stream start' if i == starts[0] else 'post-cut'})"
        )


# ── P3: lettering test — 'Peak' at 8mm ───────────────────────────────────────


@pytest.mark.xfail(strict=True,
                   reason="Phase B4 open: 102 st/letter satin at baseline, target >=150")
def test_probe3_lettering_peak_at_8mm_is_dense_satin():
    from app.services.lettering import generate_lettering

    cv2.setRNGSeed(1234)
    d = generate_lettering("Peak", height_mm=8.0)
    assert all(str(o.stitch_type) == "SATIN" for o in d.objects)
    assert d.stitch_count / 4 >= 150


# ── P4: angle test — satin 0deg vs 77deg must differ ─────────────────────────


def test_probe4_satin_angle_edit_changes_the_stream():
    # A5: rebuild builds the satin frame from the stored stitch_angle instead
    # of recomputing minAreaRect, so editing the angle is no longer a no-op.
    s0 = rebuild_design(_satin_bar(StitchType.SATIN, 0.0))
    s77 = rebuild_design(_satin_bar(StitchType.SATIN, 77.0))
    a = [(str(s.command), round(s.x, 3), round(s.y, 3)) for s in s0.stitches]
    b = [(str(s.command), round(s.x, 3), round(s.y, 3)) for s in s77.stitches]
    assert a != b


def _dominant_seg_angle(design) -> float:
    """Modal direction (deg, mod 180) of STITCH segments longer than 0.5mm."""
    from collections import Counter

    angles = []
    prev = None
    for s in design.stitches:
        if str(s.command) == "STITCH" and prev is not None and str(prev.command) == "STITCH":
            dx, dy = s.x - prev.x, s.y - prev.y
            if math.hypot(dx, dy) > 0.5:
                angles.append(math.degrees(math.atan2(dy, dx)) % 180.0)
        prev = s
    assert angles
    return Counter(round(a / 5) * 5 % 180 for a in angles).most_common(1)[0][0]


def test_satin_angle_semantics_axis_is_the_walk_direction():
    # Regression for A5: stitch_angle names the column-walk axis, so the satin
    # rungs (the visible thread) run PERPENDICULAR to it. Pinning the geometry
    # keeps "honored" from regressing into "consumed but rotated 90 degrees".
    rungs0 = _dominant_seg_angle(rebuild_design(_satin_bar(StitchType.SATIN, 0.0)))
    rungs90 = _dominant_seg_angle(rebuild_design(_satin_bar(StitchType.SATIN, 90.0)))
    assert abs(rungs0 - 90.0) <= 10.0, f"axis 0 should give ~90deg rungs, got {rungs0}"
    assert rungs90 <= 10.0 or rungs90 >= 170.0, f"axis 90 should give ~0deg rungs, got {rungs90}"


def test_digitize_records_the_normalized_satin_axis():
    # Regression for A5: digitize stores the axis the generators actually used
    # (minAreaRect angle + the long-axis flip, mod 180) — the raw rect[2] was
    # off by 90 whenever the flip fired, which is why rebuild couldn't trust it.
    import cv2
    import numpy as np
    from helpers import digitized_fixture

    from app.services.digitizer.satin import _satin_axis_deg

    d = digitized_fixture("04_thin_line_outline.png")  # all thin strokes → satin
    satins = [o for o in d.objects if str(o.stitch_type) == "SATIN" and o.contour]
    assert satins, "fixture has no satin objects — pick another fixture"
    for o in satins:
        pts = np.array([[p.x, p.y] for p in o.contour], np.float32)
        want = _satin_axis_deg(cv2.minAreaRect(pts))
        assert abs(o.stitch_angle - want) <= 0.06 or abs(abs(o.stitch_angle - want) - 180.0) <= 0.06, (
            f"{o.name}: stored {o.stitch_angle}, normalized axis {want:.2f}"
        )


def test_legacy_raw_rect_angle_rebuilds_in_the_normalized_frame():
    # Regression for A5's migration shim: pre-A5 saves recorded RAW
    # minAreaRect[2] (negative in this cv2) — provenance, not an edit. Such a
    # design must rebuild exactly as if it carried the normalized axis, so old
    # saved satin doesn't rotate 90 degrees on its first post-A5 rebuild.
    import cv2 as _cv2

    from app.services.digitizer.satin import _satin_axis_deg

    legacy = _satin_bar(StitchType.SATIN, 0.0)
    pts = np.array([[p.x, p.y] for p in legacy.objects[0].contour], np.float32)
    raw_rect = _cv2.minAreaRect(pts)
    raw = round(float(raw_rect[2]), 1)
    assert raw < 0.0, "shim precondition: this cv2 reports raw rect angles negative"
    legacy.objects[0].stitch_angle = raw

    normalized = _satin_bar(StitchType.SATIN, _satin_axis_deg(raw_rect))
    a = [(str(s.command), round(s.x, 3), round(s.y, 3))
         for s in rebuild_design(legacy).stitches]
    b = [(str(s.command), round(s.x, 3), round(s.y, 3))
         for s in rebuild_design(normalized).stitches]
    assert a == b


def test_underlay_selection_is_consumed_on_rebuild():
    # Regression for A5/C5: the dropdown used to collapse every non-NONE choice
    # to one generator per family. Distinct choices must now yield distinct
    # streams, and each must be a superset-length of the underlay-free build.
    bare = rebuild_design(_satin_bar(StitchType.SATIN, 0.0)).stitch_count
    center = rebuild_design(_satin_bar(StitchType.SATIN, 0.0, UnderlayType.CENTER_WALK))
    zigzag = rebuild_design(_satin_bar(StitchType.SATIN, 0.0, UnderlayType.DOUBLE_ZIGZAG))
    assert center.stitch_count > bare and zigzag.stitch_count > bare
    assert [(round(s.x, 2), round(s.y, 2)) for s in center.stitches] != \
           [(round(s.x, 2), round(s.y, 2)) for s in zigzag.stitches]

    bare_f = rebuild_design(_satin_bar(StitchType.TATAMI, 0.0)).stitch_count
    edge = rebuild_design(_satin_bar(StitchType.TATAMI, 0.0, UnderlayType.EDGE_WALK))
    par = rebuild_design(_satin_bar(StitchType.TATAMI, 0.0, UnderlayType.PARALLEL))
    assert edge.stitch_count > bare_f
    # PARALLEL = edge walk + crossing tatami layer, so it must out-stitch EDGE_WALK
    assert par.stitch_count > edge.stitch_count


# ── P5: applique test — STOP after placement and after tackdown ──────────────


def test_probe5_applique_emits_stops():
    # A4: rebuild sews applique as three machine phases (placement run,
    # tackdown run, satin cover) with a STOP after each of the first two.
    built = rebuild_design(_satin_bar(StitchType.APPLIQUE, 0.0))
    stops = sum(1 for s in built.stitches if str(s.command) == "STOP")
    assert stops >= 2, f"expected STOP after placement and after tackdown, got {stops}"


def test_applique_stops_partition_the_phases():
    # Regression for A4: the STOPs must land between sewn phases, not at the
    # stream edges — each STOP needs real stitches both before and after it,
    # so the operator genuinely pauses mid-object to place/inspect fabric.
    built = rebuild_design(_satin_bar(StitchType.APPLIQUE, 0.0))
    cmds = [str(s.command) for s in built.stitches]
    stop_idx = [i for i, c in enumerate(cmds) if c == "STOP"]
    assert len(stop_idx) == 2
    for i in stop_idx:
        assert "STITCH" in cmds[:i], f"STOP at {i} has no sewn phase before it"
        assert "STITCH" in cmds[i + 1:], f"STOP at {i} has no sewn phase after it"
    # A STOP is a pause, not a movement: it must sit on the previous needle
    # position so the machine does not drag thread while paused.
    for i in stop_idx:
        prev = built.stitches[i - 1]
        cur = built.stitches[i]
        assert (cur.x, cur.y) == (prev.x, prev.y)


def test_applique_stops_survive_file_round_trip():
    # Regression for A4: STOP must survive export/import, otherwise the
    # machine file loses the pause and the fix is cosmetic.
    from app.services.embroidery_io import read_embroidery, write_embroidery

    built = rebuild_design(_satin_bar(StitchType.APPLIQUE, 0.0))
    want = sum(1 for s in built.stitches if str(s.command) == "STOP")
    assert want >= 2
    back = read_embroidery(write_embroidery(built, "pes"), "pes")
    got = sum(1 for s in back.stitches if str(s.command) == "STOP")
    assert got == want, f"STOPs lost in round trip: wrote {want}, read {got}"


# ── A6: fill quality — stitch cap, spacing, alternated isotropic angles ──────


def test_fill_rows_never_exceed_the_fill_stitch_cap():
    # A6/C8: the stagger end-guard let end segments reach step*(1+2*guard) —
    # measured 15.9mm worst case at a 12.7mm step, over the machine limit
    # itself. The ceil() end-gap repair bounds every within-row segment by the
    # step at generation, at any angle.
    from app.services.digitizer.fills import _scanline_angled

    region = np.zeros((400, 400), np.uint8)
    region[50:350, 50:350] = 255
    step_px = 16  # 4mm at 4px/mm
    for ang in (0.0, 30.0, 77.0):
        pts = _scanline_angled(region, ang, 2, step_px, 4.0)
        gaps = [math.dist(a[:2], b[:2])
                for a, b in itertools.pairwise(pts) if not b[2]]
        assert gaps and max(gaps) <= step_px + 0.51, (
            f"angle {ang}: max within-row segment {max(gaps):.1f}px > cap {step_px}px"
        )


def test_fill_spacing_default_is_backlog_verbatim():
    from app.services.digitizer.constants import (
        FABRIC_DEFAULT,
        MAX_FILL_STITCH_MM,
        ROW_SPACING_MM,
    )

    assert ROW_SPACING_MM == 0.40
    assert FABRIC_DEFAULT["row_mm"] == 0.40
    assert MAX_FILL_STITCH_MM == 4.0


def test_successive_isotropic_fills_alternate_angles():
    # A6: two discs have no long axis, so their fallback angles are arbitrary —
    # and arbitrary repeated is push/pull accumulating one way. The second
    # isotropic fill must sew perpendicular to the first (alternation is free:
    # the edge-avoiding penalty has period 90 degrees).
    img = np.full((500, 900, 3), 255, np.uint8)
    cv2.circle(img, (230, 250), 140, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (670, 250), 140, (40, 60, 160), -1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    cv2.setRNGSeed(1234)
    d = digitize_image(buf.tobytes(), "cotton", "100x100", 2)
    fills = [o for o in d.objects if str(o.stitch_type) == "TATAMI"]
    assert len(fills) == 2, f"expected two tatami discs, got {[o.name for o in d.objects]}"
    diff = abs(fills[0].stitch_angle - fills[1].stitch_angle) % 180.0
    assert min(diff, 180.0 - diff) >= 80.0, (
        f"iso fills did not alternate: {fills[0].stitch_angle} vs {fills[1].stitch_angle}"
    )


# ── A7: run pitch 2.5mm default, density-aware ───────────────────────────────


def _run_bar(density: float) -> Design:
    o = DesignObject(
        sequence_order=1, name="r", stitch_type=StitchType.RUNNING_SINGLE,
        color_stop=1, density=density, stitch_angle=0.0,
        underlay_type=UnderlayType.NONE, pull_compensation=0.0,
        connect_method=ConnectMethod.TRIM, stitch_count=0,
        contour=[Point(x=0, y=10), Point(x=60, y=10)],
    )
    return Design(
        name="t", width_mm=60, height_mm=20, stitch_count=0, version=1,
        status="digitized",
        color_stops=[ColorStop(stop_number=1, thread_brand="M", catalog_number="1",
                               thread_name="a", hex="#112233", stitch_count=0)],
        objects=[o], stitches=[],
    )


def _median_run_pitch(design) -> float:
    gaps = []
    prev = None
    for s in design.stitches:
        if str(s.command) == "STITCH" and prev is not None and str(prev.command) == "STITCH":
            g = math.dist((prev.x, prev.y), (s.x, s.y))
            if g > 0.05:
                gaps.append(g)
        prev = s
    assert gaps
    gaps.sort()
    return gaps[len(gaps) // 2]


def test_run_pitch_defaults_to_2_5mm():
    # A7/C7: the machine cap (6mm) was reused as the run pitch. A run with
    # density unset (0 — what the manual tool stores) must sew ~2.5mm.
    pitch = _median_run_pitch(rebuild_design(_run_bar(0.0)))
    assert 2.0 <= pitch <= 3.0, f"default run pitch {pitch:.2f}mm, want ~2.5"


def test_run_density_is_honored():
    # A7/C7: density on run objects was ignored entirely. Pitch = 1/density.
    fine = _median_run_pitch(rebuild_design(_run_bar(1.0)))    # 1mm pitch
    coarse = _median_run_pitch(rebuild_design(_run_bar(0.25)))  # 4mm pitch
    assert 0.7 <= fine <= 1.4, f"density 1.0 → pitch {fine:.2f}mm, want ~1"
    assert 3.2 <= coarse <= 4.8, f"density 0.25 → pitch {coarse:.2f}mm, want ~4"


# ── A8: rebuild validation — orphan color stops raise; 0.1mm raster ──────────


def test_rebuild_raises_on_orphan_color_stop():
    # A8/C9: an object referencing a nonexistent stop used to be silently
    # filtered out of the emission loop — it simply vanished from the rebuilt
    # design. Corrupt references must fail loudly and name the object.
    d = _satin_bar(StitchType.SATIN, 0.0)
    d.objects[0].color_stop = 99
    with pytest.raises(ValueError, match=r"color stops that do not exist.*color_stop=99"):
        rebuild_design(d)


def test_rebuild_raster_is_dst_resolution():
    # A8/C6: rebuild re-rastered at <=4px/mm (0.25mm grid), roughening every
    # edge on each edit. At 10px/mm the grid is 0.1mm — DST's own coordinate
    # resolution — so rebuilt coordinates must land off the old 0.25mm grid.
    built = rebuild_design(_satin_bar(StitchType.SATIN, 0.0))
    xs = [s.x for s in built.stitches if str(s.command) == "STITCH"]
    off_coarse_grid = sum(1 for x in xs if abs(x / 0.25 - round(x / 0.25)) > 0.01)
    assert off_coarse_grid > 0, "every coordinate sits on the coarse 0.25mm grid"


# ── A15/N2: transparent PNGs keep their dark artwork ─────────────────────────


def test_transparent_png_keeps_black_artwork():
    # N2: IMREAD_COLOR strips alpha, transparent pixels decode as BLACK, and
    # the corner-average background heuristic then deletes the artwork's own
    # black linework. Reproduced pre-fix: this ring vanished entirely.
    img = np.zeros((500, 500, 4), np.uint8)  # fully transparent canvas
    cv2.circle(img, (160, 250), 100, (10, 10, 10, 255), 24, cv2.LINE_AA)
    cv2.rectangle(img, (300, 160), (440, 320), (40, 40, 200, 255), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    cv2.setRNGSeed(1234)
    d = digitize_image(buf.tobytes(), "cotton", "100x100", 3)
    hexes = {c.hex for c in d.color_stops}
    assert any(h <= "#404040" for h in hexes), f"black ring lost: {hexes}"
    assert len(d.objects) >= 2 and d.stitch_count > 500


# ── P6: fidelity test — rebuild of an unedited design ────────────────────────


def test_probe6_an_unedited_design_passes_through_untouched():
    """THIS TEST NO LONGER CLAIMS TO MEASURE FIDELITY — it measures the
    pass-through, which is a different (and also real) property.

    As written for B1.5 it asserted stitch counts within 1%, coordinates within
    0.1mm and matching commands, against `rebuild_design(d)`. But an unedited
    design short-circuits and `rebuild_design` returns *the very same object*,
    so all three assertions compared `d` to `d`. They could not fail, whatever
    the generators did — and while they sat green the regenerated stream drifted
    up to 36% on a single object (CTO verdict V2, "probe-gaming").

    The fidelity question is now asked where it can get a real answer, with the
    short-circuit disabled: `test_probes_three_paths.py::test_probe6_*`.
    """
    from helpers import digitized_fixture

    d = digitized_fixture()
    r = rebuild_design(d)
    # State the identity plainly instead of dressing it as a measurement.
    assert r is d, "an unedited design must not be re-stitched at all"


def test_probe6_fidelity_is_measured_somewhere_that_can_fail():
    """Guard against this file quietly becoming the whole story again: the real
    P6 must exist, run with the pass-through off, and carry bands."""
    import test_probes_three_paths as three

    assert three.FIDELITY_BANDS, "the real P6 has no bands"
    src = (pathlib.Path(three.__file__)).read_text()
    assert "force=True" in src, "the fidelity probe is not disabling the pass-through"
