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

import math

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


def _satin_bar(stitch_type: StitchType, angle: float) -> Design:
    o = DesignObject(
        sequence_order=1, name="s", stitch_type=stitch_type, color_stop=1,
        density=4.0, stitch_angle=angle, underlay_type=UnderlayType.NONE,
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


@pytest.mark.xfail(strict=True,
                   reason="A5 open: satin rebuild ignores stitch_angle (identical streams)")
def test_probe4_satin_angle_edit_changes_the_stream():
    s0 = rebuild_design(_satin_bar(StitchType.SATIN, 0.0))
    s77 = rebuild_design(_satin_bar(StitchType.SATIN, 77.0))
    a = [(str(s.command), round(s.x, 3), round(s.y, 3)) for s in s0.stitches]
    b = [(str(s.command), round(s.x, 3), round(s.y, 3)) for s in s77.stitches]
    assert a != b


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


# ── P6: fidelity test — rebuild of an unedited design ────────────────────────


@pytest.mark.xfail(strict=True,
                   reason="A8 open: digitize 4820 vs rebuild 2298 stitches at baseline "
                          "(rebuild re-rasters at <=4px/mm)")
def test_probe6_rebuild_of_unedited_design_is_faithful():
    from helpers import digitized_fixture

    d = digitized_fixture()
    r = rebuild_design(d)
    assert abs(r.stitch_count - d.stitch_count) <= 0.01 * d.stitch_count
