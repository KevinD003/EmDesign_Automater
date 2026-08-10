"""Tests for the committed stitch-quality measurement (v2 Part 5).

The metrics grade the pipeline, so a wrong metric is worse than no metric: it
would silently move every audit number. These pin the definitions.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from measure_stitch_quality import coverage_metrics, penetration_metrics, same_side_spacings

from app.services.digitizer import MIN_PENETRATION_MM, digitize_image, set_penetration_floor


@pytest.fixture(autouse=True)
def _restore_penetration_floor():
    """Never let a test leak the module-level floor into the next one.

    Without this, a test that disabled the floor in a `finally` left the whole
    rest of the session running unenforced — which is how the first version of
    `test_floor_is_enforced_by_default` failed.
    """
    from app.services.digitizer import MIN_PENETRATION_MM

    yield
    set_penetration_floor(MIN_PENETRATION_MM)


class _S:
    """Minimal stitch stand-in: the metrics only read x, y and command."""

    def __init__(self, x, y, command="STITCH"):
        self.x, self.y, self.command = x, y, command


def _satin_path(pitch: float, width: float, n: int) -> list[_S]:
    """A0 B0 A1 B1 ... — a textbook satin zigzag with a known same-side pitch."""
    out = []
    for i in range(n):
        out.append(_S(i * pitch, 0.0))
        out.append(_S(i * pitch, width))
    return out


def test_same_side_spacing_equals_the_pitch():
    gaps = same_side_spacings(_satin_path(pitch=0.4, width=3.0, n=20))
    assert gaps, "a satin zigzag must yield same-side pairs"
    assert all(abs(g - 0.4) < 1e-9 for g in gaps)


def test_running_stitch_is_not_counted_as_satin():
    """A line of penetrations advancing along one path has no same-side pairs."""
    run = [_S(i * 2.0, 0.0) for i in range(20)]
    assert same_side_spacings(run) == []


def test_tatami_rows_are_not_counted_as_satin():
    """Scanline points advance ALONG a row, so no triple zigzags."""
    rows = []
    for r in range(6):
        y = r * 0.45
        xs = range(20) if r % 2 == 0 else reversed(range(20))
        rows += [_S(x * 0.5, y) for x in xs]
    assert same_side_spacings(rows) == []


def test_jump_breaks_a_run():
    path = _satin_path(0.4, 3.0, 5) + [_S(50.0, 50.0, "JUMP")] + _satin_path(0.4, 3.0, 5)
    # Two independent runs: neither contributes a pair spanning the jump.
    assert all(abs(g - 0.4) < 1e-9 for g in same_side_spacings(path))


def test_tight_curve_packs_penetrations_below_the_pitch():
    """The defect the metric exists to catch, on a synthetic concave arc.

    Outer side paced at the nominal pitch; inner side on a radius half as large
    therefore advances half as far between columns.
    """
    outer_r, inner_r, pitch = 8.0, 4.0, 0.4
    steps = 30
    path = []
    for i in range(steps):
        a = i * pitch / outer_r          # angle advance set by the OUTER boundary
        path.append(_S(outer_r * np.cos(a), outer_r * np.sin(a)))
        path.append(_S(inner_r * np.cos(a), inner_r * np.sin(a)))
    gaps = sorted(same_side_spacings(path))
    assert gaps[0] < pitch * 0.6, f"inner side should pack up, got {gaps[0]:.3f}"


def _ring_bytes(radius_px: int, stroke_px: int = 16) -> bytes:
    img = np.full((320, 320, 3), 255, np.uint8)
    cv2.circle(img, (160, 160), radius_px, (30, 30, 40), thickness=stroke_px)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_penetration_floor_removes_violations_on_a_tight_ring():
    """A ring has no terminals, so this isolates curvature. Floor off vs on."""
    art = _ring_bytes(radius_px=32)
    try:
        set_penetration_floor(None)
        loose = digitize_image(art, "cotton", "100x100", max_colors=2)
        before = penetration_metrics(loose, 0.4, 0.30)

        set_penetration_floor(0.30)
        tight = digitize_image(art, "cotton", "100x100", max_colors=2)
        after = penetration_metrics(tight, 0.4, 0.30)
    finally:
        set_penetration_floor(MIN_PENETRATION_MM)

    assert before.get("satin_objects"), "a 16px-wide ring must digitize as satin"
    assert before["below_floor"] > 0, "the tight ring must violate the floor when unenforced"
    assert after["below_floor"] == 0, f"floor left {after['below_floor']} violations"
    assert after["min_spacing_mm"] >= 0.30 - 1e-6


def test_floor_is_enforced_by_default():
    """v2 Part 6 turned enforcement on; the shipped default must honour the floor."""
    from app.services import digitizer

    assert digitizer._PENETRATION_FLOOR_MM == MIN_PENETRATION_MM
    design = digitize_image(_ring_bytes(radius_px=32), "cotton", "100x100", max_colors=2)
    pen = penetration_metrics(design, 0.4, MIN_PENETRATION_MM)
    assert pen["satin_objects"], "a 16px-wide ring must digitize as satin"
    assert pen["below_floor"] == 0, f"default build left {pen['below_floor']} violations"


def test_enforcement_does_not_change_which_objects_are_satin():
    """The floor removes columns; it must never flip a classification verdict."""
    art = _ring_bytes(radius_px=48)
    try:
        set_penetration_floor(None)
        loose = digitize_image(art, "cotton", "100x100", max_colors=2)
        set_penetration_floor(MIN_PENETRATION_MM)
        tight = digitize_image(art, "cotton", "100x100", max_colors=2)
    finally:
        set_penetration_floor(MIN_PENETRATION_MM)
    assert [o.stitch_type for o in loose.objects] == [o.stitch_type for o in tight.objects]
    assert tight.stitch_count < loose.stitch_count, "the floor should remove columns"


def test_coverage_metrics_on_a_fully_stitched_shape():
    """Interior/edge-band/spill are percentages in range, and a real fill scores high."""
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (160, 160), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    design = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    cov = coverage_metrics(design)
    assert 0.0 <= cov["edge_band_pct"] <= 100.0
    assert 0.0 <= cov["spill_pct"] <= 100.0
    assert cov["interior_pct"] is not None and cov["interior_pct"] > 80.0


def test_interior_is_none_for_a_shape_thinner_than_the_erosion():
    """A hairline has no interior; reporting 0% would read as a coverage failure."""
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.line(img, (20, 100), (180, 100), (40, 40, 40), thickness=2)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    design = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    assert coverage_metrics(design)["interior_pct"] is None


def test_measure_cli_runs_and_writes_json(tmp_path, monkeypatch, capsys):
    """The committed script must be runnable as-is — that is the point of committing it."""
    import measure_stitch_quality as msq

    out = tmp_path / "metrics.json"
    monkeypatch.setattr(
        sys, "argv",
        ["measure_stitch_quality.py", "--fixture", "04_thin_line_outline", "--json", str(out)],
    )
    assert msq._main() == 0
    printed = capsys.readouterr().out
    assert "04_thin_line_outline" in printed
    assert "edge band" in printed

    payload = __import__("json").loads(out.read_text())
    rec = payload["04_thin_line_outline"]
    assert rec["coverage"]["edge_band_pct"] > 90.0
    # 10 of the fixture's 11 satin objects yield same-side pairs; the hub circle
    # is too short to produce a zigzag triple, and is skipped rather than counted
    # as a zero-penetration object.
    # 11 after Part 16's thinner fix; 10 after Part 17's granularity upscale
    # re-measured fixture 04's hairlines at their true ~0.3mm and re-columned
    # them (one object's pairs merged). The value is a resolution-dependent
    # pin, not a safety property — the safety numbers are asserted elsewhere.
    assert rec["penetration"]["satin_objects"] == 10


def test_measure_cli_rejects_an_unknown_fixture(monkeypatch):
    import measure_stitch_quality as msq

    monkeypatch.setattr(sys, "argv", ["measure_stitch_quality.py", "--fixture", "nope"])
    assert msq._main() == 2


def test_bench_records_coverage_and_penetration(tmp_path):
    """The harness carries the metrics into the per-fixture JSON, via the shared module."""
    import run_quality_bench as bench

    fixture = bench.FIXTURE_DIR / "04_thin_line_outline.png"
    result = bench.run_fixture(fixture, tmp_path)
    assert result.ok and not result.error
    assert result.coverage["edge_band_pct"] > 90.0
    assert result.penetration["satin_objects"] == 10  # see CLI test note (Part 17 resolution)
    assert result.penetration["nominal_pitch_mm"] == 0.4
    # The safety number must be present even when nothing violates the floor.
    assert "min_spacing_mm" in result.penetration


def test_mitre_closes_a_sharp_apex_without_breaking_the_floor():
    """v2 Part 8: a sharp vertex must be covered, and still honour the floor."""
    import math

    img = np.full((320, 320, 3), 255, np.uint8)
    apex = (160, 250)
    cv2.line(img, (apex[0] - 60, apex[1] - 150), apex, (30, 30, 40), thickness=12)
    cv2.line(img, apex, (apex[0] + 60, apex[1] - 150), (30, 30, 40), thickness=12)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    from app.services import digitizer as D

    art = buf.tobytes()
    keep = D.MITRE_MIN_STALLED
    try:
        D.MITRE_MIN_STALLED = 10 ** 9          # effectively disabled
        without = coverage_metrics(digitize_image(art, "cotton", "100x100", max_colors=2))
        D.MITRE_MIN_STALLED = keep
        design = digitize_image(art, "cotton", "100x100", max_colors=2)
    finally:
        D.MITRE_MIN_STALLED = keep

    assert [o for o in design.objects if o.stitch_type == "SATIN"]
    cov = coverage_metrics(design)
    # CHARACTERISATION, not a win. On this butt-jointed V — two separate strokes
    # meeting with no rounded join — the mitre measures WORSE than leaving it off
    # (97.3 -> 95.1 interior), the opposite of the letter probe's joined apexes
    # (apex_M 96.6 -> 97.3, apex_V 98.1 -> 97.8). The shape is pinned here so the
    # regression is visible rather than tuned away; see the Part 8 audit.
    #
    # Those two figures were WRONG until v2 Part 10 — they read 97.9 and 98.7,
    # numbers from an intermediate build taken before the MIN_STITCH_MM guard.
    # The Part 9 audit reported the correction as done; the edit had silently
    # no-op'd on a mismatched search string and nobody diffed the file.
    assert cov["interior_pct"] > 90.0
    assert without["interior_pct"] > 90.0
    pen = penetration_metrics(design, 0.4, MIN_PENETRATION_MM)
    assert pen["below_floor"] == 0, f"mitre broke the floor: {pen['below_floor']}"
    assert math.isfinite(cov["spill_pct"])


def test_mitre_leaves_a_straight_stroke_alone():
    """The mitre must only fire inside a RUN of stalled stations, not on a straight bar."""
    from app.services.digitizer import MITRE_MIN_STALLED, _mitre_stalled_side

    n = 12
    a = np.array([[float(i), 0.0] for i in range(n)])       # both boundaries advancing
    b = np.array([[float(i), 4.0] for i in range(n)])
    mid = np.array([[float(i), 2.0] for i in range(n)])
    before = a.copy(), b.copy()
    moved = _mitre_stalled_side(a, b, mid, 0.5, 1.0)
    assert moved == 0, "a straight stroke has no stalled run to mitre"
    assert np.allclose(a, before[0]) and np.allclose(b, before[1])
    assert MITRE_MIN_STALLED >= 2


def test_paint_uncovered_writes_a_picture(tmp_path):
    """The uncovered-pixel painter is binding practice, so it is pinned by a test."""
    from measure_stitch_quality import paint_uncovered

    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (160, 160), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    design = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    out = tmp_path / "painted.png"
    stats = paint_uncovered(design, out)
    assert out.exists() and out.stat().st_size > 0
    assert stats["missed_interior_px"] >= 0 and stats["missed_band_px"] >= 0


def test_coalescing_restores_only_what_the_floor_needs():
    """v2 Part 10: targeted repair, not blanket protection.

    Coalescing changes WHICH points survive a satin path, and that shift can break
    the A-B-A-B alternation `_enforce_floor` depends on. v2 Part 9 protected every
    mitred endpoint from being dropped, which cost 27 extra sub-0.5mm stitches;
    this restores only the point whose absence actually leaves a same-side pair
    under the floor.
    """
    from app.services import digitizer as D

    # A0 B0 B0' A1 — B0' sits 0.1 from B0, so coalescing drops it. Its removal
    # makes A0 and A1 same-side neighbours only 0.3 apart, under a 0.35 floor.
    pts = [(0.0, 0.0, True), (0.0, 4.0, False), (0.1, 4.0, False), (0.3, 0.0, False)]
    loose = D._coalesce_short(pts, 0.5)
    assert len(loose) == 3, f"the 0.1 hop should be coalesced away: {loose}"
    same_side = D._dist(loose[0], loose[2])
    assert same_side < 0.35, f"removal should leave a sub-floor same-side pair: {same_side}"

    repaired = D._coalesce_short(pts, 0.5, floor_px=0.35)
    assert len(repaired) == 4, f"the floor repair should put the point back: {repaired}"
    assert repaired == pts


def test_floor_repair_is_a_no_op_when_nothing_violates():
    """A clean satin path must come through the repair pass byte-identical."""
    from app.services import digitizer as D

    pts = [(0.0, 0.0, True)]
    for i in range(1, 12):                       # full crossings, 4mm apart
        pts.append((i * 0.4, 4.0 if i % 2 else 0.0, False))
    assert D._coalesce_short(pts, 0.5, floor_px=0.3) == D._coalesce_short(pts, 0.5)


def test_floor_repair_ignores_a_running_stitch():
    """A running stitch advances along a line, so the zigzag test must reject it."""
    from app.services import digitizer as D

    pts = [(float(i) * 0.2, 0.0, i == 0) for i in range(12)]
    assert D._coalesce_short(pts, 0.5, floor_px=0.3) == D._coalesce_short(pts, 0.5)


def test_the_zigzag_ratio_is_defined_once():
    """v2 Part 11: the metric imports the pipeline's constant, it does not copy it.

    Two 0.9s in two files encode the same "does this triple zigzag" test, and
    nothing stopped them drifting apart. Pinning identity (not equality) means a
    future edit to one is an edit to both.
    """
    import measure_stitch_quality as M

    from app.services import digitizer as D

    assert M.ZIGZAG_RATIO is D.ZIGZAG_RATIO
    assert not hasattr(D, "COALESCE_ZIGZAG"), "the old duplicate name should be gone"


# ── v2 Part 11: running-stitch reversal repair ───────────────────────────────


def _reversal(step: float = 2.0, n: int = 4):
    """An underlay walking out along a line and back — the branch-tip double-back.

    The two points either side of the turnaround coincide exactly, so the metric
    sees a same-side gap of 0.0mm.
    """
    outbound = [(i * step, 0.0, i == 0) for i in range(n + 1)]
    back = [(i * step, 0.0, False) for i in range(n - 1, -1, -1)]
    return outbound + back


def test_underlay_reversal_produces_a_zero_same_side_gap():
    """The defect, before the repair: a turnaround reads as a 0.0mm penetration pair."""
    pts = _reversal()
    gaps = same_side_spacings([_S(x, y) for x, y, _ in pts])
    assert gaps and min(gaps) == pytest.approx(0.0, abs=1e-9)


def test_reversal_repair_removes_the_coincident_penetration():
    """v2 Part 11: drop one point of the coincident pair, keep the thread on the line."""
    from app.services import digitizer as D

    pts = _reversal()
    fixed = D._drop_floor_reversals(pts, floor_px=0.3, max_px=6.0)
    assert len(fixed) == len(pts) - 1, f"exactly one point should go: {fixed}"
    gaps = same_side_spacings([_S(x, y) for x, y, _ in fixed])
    assert not [g for g in gaps if g < 0.3], f"no sub-floor pair should remain: {gaps}"


def test_reversal_repair_is_a_no_op_on_a_plain_running_stitch():
    """A running stitch that never doubles back must come through untouched."""
    from app.services import digitizer as D

    pts = [(float(i) * 2.0, 0.0, i == 0) for i in range(12)]
    assert D._drop_floor_reversals(pts, floor_px=0.3, max_px=6.0) == pts


def test_reversal_repair_refuses_to_exceed_the_machine_stitch_limit():
    """Closing the gap must never be paid for with an over-length stitch.

    With `max_px` below the merged span, the point is kept and the violation is
    reported honestly rather than traded away.
    """
    from app.services import digitizer as D

    pts = _reversal(step=4.0)
    assert D._drop_floor_reversals(pts, floor_px=0.3, max_px=1.0) == pts


def test_reversal_repair_does_not_swallow_a_jump():
    """A jump breaks the run, so the metric never sees the triple and the flag stays."""
    from app.services import digitizer as D

    pts = [(0.0, 0.0, True), (2.0, 0.0, False), (4.0, 0.0, False),
           (2.0, 0.0, False), (99.0, 99.0, True), (99.0, 97.0, False)]
    fixed = D._drop_floor_reversals(pts, floor_px=0.3, max_px=6.0)
    assert [p[2] for p in fixed].count(True) == 2, f"both jumps must survive: {fixed}"


# ── v2 Part 12: adaptive side choice + edge-walk wiring + center-walk proof ──


def test_reversal_repair_drops_the_side_with_the_smaller_merged_stitch():
    """v2 Part 12: the drop side is chosen adaptively, not fixed.

    Part 11 always dropped the return point. Measured over 3,552 violating
    asymmetric turnarounds, that fixed choice creates the longer merged span
    49.5% of the time (mean excess 0.58mm, max 1.79mm). Here the outbound leg is
    short and the return leg long, so dropping the OUTBOUND point merges
    p->b = 1.7 while Part 11's return-drop would have merged b->d ~= 2.99 —
    the losing case, pinned.
    """
    from app.services import digitizer as D

    p, a, b = (0.3, 0.0), (1.0, 0.0), (2.0, 0.0)
    c, d = (1.02, 0.1), (-0.97, 0.303)
    run = [(*p, True), (*a, False), (*b, False), (*c, False), (*d, False)]
    fixed = D._drop_floor_reversals(run, floor_px=0.3, max_px=6.0)
    assert len(fixed) == 4
    assert (*a, False) not in fixed, f"the outbound point should be the one dropped: {fixed}"
    assert (*c, False) in fixed
    gaps = same_side_spacings([_S(x, y) for x, y, _ in fixed])
    assert not [g for g in gaps if g < 0.3]


def test_edge_walk_spike_reversal_is_repaired():
    """v2 Part 12: the repair is wired into `_edge_walk` and closes a real case.

    Where erosion leaves a hairline spike, the contour walks out the spike and
    back 2px away — the same out-and-back geometry as a medial-axis branch tip.
    No corpus fixture produces one, so this sweep constructs it: across spike
    lengths, at least one sampling phase must land a point at the tip, and the
    wired floor must then remove every violation the raw walk produced.
    """
    from app.services.digitizer import _edge_walk

    def violations(pts, floor):
        found = []
        for i in range(1, len(pts) - 1):
            a, b, c = pts[i - 1], pts[i], pts[i + 1]
            if a[2] or b[2] or c[2]:
                continue
            gap = ((a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2) ** 0.5
            legs = min(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5,
                       ((b[0] - c[0]) ** 2 + (b[1] - c[1]) ** 2) ** 0.5)
            if gap < floor and gap < 0.9 * legs:
                found.append((i, gap))
        return found

    raw_total, wired_total = 0, 0
    for spike_len in range(30, 72, 2):
        mask = np.zeros((220, 200), np.uint8)
        cv2.rectangle(mask, (30, 40), (170, 120), 255, -1)
        cv2.line(mask, (100, 120), (100, 120 + spike_len), 255, 3)
        raw_total += len(violations(_edge_walk(mask, 1, 20, 30.0), 3.0))
        wired_total += len(violations(_edge_walk(mask, 1, 20, 30.0, floor_px=3.0, max_px=60.0), 3.0))
    assert raw_total > 0, "the adversarial spike must actually reproduce the defect"
    assert wired_total == 0, "the wired floor must close every case the sweep produces"


def test_center_walk_cannot_zigzag():
    """v2 Part 12: `_center_walk` is deliberately NOT wired, and this is why.

    Its emitted points advance monotonically in rotated-x by `step_px` per
    point, and the un-rotation is an isometry, so any same-side pair is at
    least 2*step_px apart — the zigzag triple test can never pass. Property-
    checked over seeded random blob masks rather than asserted.
    """
    from app.services.digitizer import _center_walk

    rng = np.random.default_rng(20260729)
    for _ in range(30):
        mask = np.zeros((160, 160), np.uint8)
        for _blob in range(6):
            cv2.circle(mask, (int(rng.uniform(30, 130)), int(rng.uniform(30, 130))),
                       int(rng.uniform(10, 40)), 255, -1)
        rect = cv2.minAreaRect(np.argwhere(mask > 0)[:, ::-1].astype(np.float32))
        pts = _center_walk(mask, rect, 20, 30.0)
        gaps = same_side_spacings([_S(x, y) for x, y, _ in pts])
        assert gaps == [], f"a center-walk emission zigzagged: {gaps}"


# ── v2 Part 12: penetration-accumulation (density) metric ────────────────────


class _D:
    def __init__(self, stitches):
        self.stitches = stitches


def test_density_flags_a_pile_up():
    """15 penetrations into one 0.5mm cell — a stacked-object pile-up — must flag."""
    from measure_stitch_quality import DENSITY_FLAG_PER_CELL, density_metrics

    pile = [_S(10.1 + (i % 3) * 0.05, 10.1 + (i // 3) * 0.05) for i in range(15)]
    spread = [_S(30.0 + i * 2.0, 30.0) for i in range(10)]
    m = density_metrics(_D(pile + spread))
    assert m["max_per_cell"] == 15
    assert m["flagged_cells"] == 1
    assert m["flag_at"] == DENSITY_FLAG_PER_CELL
    assert m["hottest"][0]["count"] == 15


def test_density_does_not_flag_a_healthy_satin_path():
    m = __import__("measure_stitch_quality").density_metrics(_D(_satin_path(0.4, 3.0, 40)))
    assert m["flagged_cells"] == 0
    assert m["max_per_cell"] <= 4


def test_density_is_order_independent_where_the_triple_test_is_blind():
    """The defect class the triple metric structurally cannot see (v2 Part 12).

    An edge-walk contour seam puts the first and last penetrations of a loop in
    the same hole — adjacent in space, far apart in the stream, so no
    consecutive triple ever contains the pair and `same_side_spacings` returns
    nothing. The cell count sees them regardless of stream order.
    """
    from measure_stitch_quality import density_metrics

    loop = [_S(20.0 + math.cos(t / 20.0 * 2 * math.pi) * 5.0,
               20.0 + math.sin(t / 20.0 * 2 * math.pi) * 5.0) for t in range(20)]
    loop.append(_S(loop[0].x + 0.05, loop[0].y + 0.05))  # seam: re-enters the first hole
    assert same_side_spacings(loop) == [] or min(same_side_spacings(loop)) > 0.3
    m = density_metrics(_D(loop))
    seam_cell = [h for h in m["hottest"] if h["count"] >= 2]
    assert seam_cell, f"the seam pair must be visible to the cell count: {m['hottest']}"


def _flagged_cells(design, m) -> list[tuple[int, int]]:
    """The grid cells at or over `DENSITY_FLAG_PER_CELL`, as (cx, cy).

    `density_metrics` reports how MANY cells are flagged but not which, and the
    caller needs the identity to ask what is in them. Binned exactly as the
    metric bins, so the two cannot disagree about cell boundaries.
    """
    from collections import Counter

    from measure_stitch_quality import DENSITY_CELL_MM, DENSITY_FLAG_PER_CELL, _cmd

    cells: Counter = Counter()
    for s in design.stitches:
        if _cmd(s) == "STITCH":
            cells[(int(s.x / DENSITY_CELL_MM), int(s.y / DENSITY_CELL_MM))] += 1
    return [c for c, n in cells.items() if n >= DENSITY_FLAG_PER_CELL]


def _has_tieoff_signature(design, cell) -> bool:
    """Does this cell's density come from a tie-off rather than from stitching?

    A lock goes out from an anchor and comes back to it, so the SAME COORDINATE
    is stitched twice. Fill and satin never do that: a fill re-entering a region
    lands on a new row, and a satin column's two ends are a column apart. So an
    exact coordinate revisit inside the cell is the discriminator, and it is what
    was measured at fixture 08's peak — (36.006, 64.803) stitched at penetration
    8049 and again at 8052, five stitches after a JUMP.

    Compares the emitted floats exactly and deliberately: a lock RETURNS TO its
    anchor, it does not approach it. A tolerance here would start matching dense
    stitching, which is the thing being excluded.

    Read over the cell's NEIGHBOURHOOD, not the cell. The first version of this
    helper looked inside the cell alone and reported "not a tie-off" for a site
    that demonstrably is one: fixture 08's lock revisits (36.006, 64.803), which
    bins to cell (72, 129) while the flagged cell is (71, 130). The lock
    STRADDLES the grid line — which is the whole reason the cell tripped — so a
    cell-shaped test can never see it. Same mistake as the fixed-box density
    probe, made twice; the neighbourhood is every penetration within one cell
    width of a penetration in the cell, matching how `_max_per_disc` clusters.
    """
    from measure_stitch_quality import DENSITY_CELL_MM, _cmd

    cx, cy = cell
    pts = [(float(s.x), float(s.y)) for s in design.stitches if _cmd(s) == "STITCH"]
    inside = [p for p in pts
              if (int(p[0] / DENSITY_CELL_MM), int(p[1] / DENSITY_CELL_MM)) == (cx, cy)]
    if not inside:
        return False

    r2 = DENSITY_CELL_MM * DENSITY_CELL_MM
    seen: set[tuple[float, float]] = set()
    for p in pts:
        if not any((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 <= r2 for q in inside):
            continue
        if p in seen:
            return True
        seen.add(p)
    return False


def test_the_tieoff_discriminator_actually_discriminates():
    """The density gate above is only worth having if this can answer NO.

    A check that passes everything is worse than no check, because it reads in
    the diff as a safety assertion. So: the same cell count, built once as a
    tie-off and once as dense stitching, must come back True and False.
    """
    from measure_stitch_quality import DENSITY_CELL_MM

    cell = (40, 40)
    x0 = (cell[0] + 0.5) * DENSITY_CELL_MM
    y0 = (cell[1] + 0.5) * DENSITY_CELL_MM

    # Dense stitching: 14 penetrations packed into the cell on a fine lattice,
    # every one at a DISTINCT coordinate. This is the perforation case.
    packed = [
        _S(x0 + (k % 4) * 0.03 - 0.045, y0 + (k // 4) * 0.03 - 0.045)
        for k in range(14)
    ]
    assert not _has_tieoff_signature(_D(packed), cell), (
        "dense stitching with no coordinate revisit was accepted as a tie-off"
    )

    # A tie-off: out to a point and back to the anchor already stitched.
    anchor = (x0, y0)
    lock = packed[:11] + [
        _S(*anchor), _S(x0 + 0.2, y0 + 0.15), _S(*anchor),
    ]
    assert _has_tieoff_signature(_D(lock), cell), (
        "a return to an already-stitched coordinate was not recognised"
    )


def test_the_tieoff_discriminator_sees_a_lock_that_straddles_the_grid():
    """The failure the first version of the helper actually had.

    Fixture 08's lock revisits a coordinate that bins to the cell NEXT DOOR to
    the flagged one, because the cluster sits on a grid line — which is exactly
    why that cell reached the flag. A cell-shaped test reports "not a tie-off"
    on a real tie-off. Pinned so the neighbourhood cannot quietly shrink back.
    """
    from measure_stitch_quality import DENSITY_CELL_MM

    cell = (40, 40)
    lo_x = cell[0] * DENSITY_CELL_MM
    lo_y = cell[1] * DENSITY_CELL_MM

    # 12 in the cell, hard against its upper-x edge...
    inside = [_S(lo_x + 0.45, lo_y + 0.05 + k * 0.03) for k in range(12)]
    # ...and the lock's revisited anchor just OVER that edge, in cell (41, 40),
    # within a thread width of the cell's own penetrations.
    over = lo_x + DENSITY_CELL_MM + 0.05
    stitches = inside + [_S(over, lo_y + 0.2), _S(over + 0.1, lo_y + 0.3),
                         _S(over, lo_y + 0.2)]
    assert (int(over / DENSITY_CELL_MM), int((lo_y + 0.2) / DENSITY_CELL_MM)) != cell, (
        "probe bug: the revisited pair must land in a DIFFERENT cell"
    )
    assert _has_tieoff_signature(_D(stitches), cell), (
        "a tie-off straddling the cell boundary was missed — the helper is "
        "reading a box again"
    )


def test_density_corpus_health_is_pinned():
    """Fixture 08 is the corpus's densest; it must stay far below the flag.

    The exact max differs by background-separation path (7 WITH rembg, 6
    WITHOUT — segmentation differs, so stitches do), so the pin brackets both.
    What must hold on either path: the healthy corpus peaks at half the flag
    level, which is what makes 14 = "a second full layer on the worst healthy
    cell" keep meaning what the Part 12 audit says it means.
    """
    from measure_stitch_quality import density_metrics
    from run_quality_bench import DEFAULT_PARAMS, FIXTURE_DIR, FIXTURE_PARAMS, RNG_SEED

    path = FIXTURE_DIR / "08_mascot_detail.png"
    params = FIXTURE_PARAMS.get(path.stem, DEFAULT_PARAMS)
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        path.read_bytes(), fabric_type=params["fabric"], hoop_size=params["hoop"],
        max_colors=params["colors"], text_mode=bool(params.get("text", False)),
    )
    m = density_metrics(design)
    # 6-7 at the old work resolution; 8-10 after Part 17's granularity upscale;
    # 11 after Part 25's lock stitches — a tie-off is DELIBERATELY 3-4
    # penetrations clustered within a thread-width of one anchor, so the
    # densest cell in the corpus is now a lock site rather than organic
    # stitching. That is the intended trade: an unlocked end unravels, and the
    # flag level at 14 still means "a second full layer on the worst healthy
    # cell". 13 after CTO 1b (12 without rembg — the documented path split).
    #
    # 14 after the parity fix (CTO ruling 5.1). The previous revision of this
    # test said a 14 here "must be investigated, not re-pinned". It was, by
    # running the shipped code on both trees and describing the site rather than
    # counting it. What the probes established:
    #
    #   * NOT a density shift. p99_per_cell is unchanged at 5, and the whole
    #     tail below the peak is identical: 12,9,8,8,8,8,7,7,7,7,7 both sides.
    #     Exactly one cell moved.
    #   * The peak is a TWO-OBJECT COINCIDENCE, not a fill defect. `Satin 1`
    #     (#de6c26) and `Satin 19` (#30221e) both come within 0.15mm of
    #     (35.93, 65.03). Satin 1 contributes ~17 penetrations there as the
    #     pivot end of a column zigzag (2.6-4.7mm crossings, alternate ends
    #     landing in the same 0.5mm disc) — present identically BEFORE the fix.
    #   * The +3 the fix adds is Satin 19's TIE-OFF: five consecutive
    #     penetrations entered by a JUMP, steps 0.62/0.34/0.70/0.61/0.61, the
    #     last returning to exactly (36.006, 64.803) — the coordinate of the
    #     second. The pre-fix stream shows the same signature with 3 members
    #     revisiting (35.869, 64.717). Deliberate, and what stops an end
    #     unravelling.
    #
    # So the gate is rewritten to discriminate CAUSE instead of counting, which
    # is what `flagged_cells == 0` could not do. The count bound is relaxed by
    # one; in exchange a flagged cell must now PROVE it is a tie-off. A future
    # change that piles fill into a cell has no coordinate revisit and fails
    # here, where the old form would have passed it at 13.
    #
    # `max_per_cell` is grid-anchored and provably translation-dependent (see
    # `_max_per_disc`'s docstring), so the grid-free measure is pinned beside it
    # and is the one to believe.
    assert 6 <= m["max_per_cell"] <= 14
    assert m["p99_per_cell"] <= 6, "p99 moving is a density shift; a lone max is not"
    assert m["max_per_disc"] <= 26, (
        "translation-invariant peak rose above the measured lock-plus-pivot "
        "site; unlike max_per_cell this cannot be a grid artefact"
    )
    assert m["flagged_cells"] <= 1
    for cell in _flagged_cells(design, m):
        assert _has_tieoff_signature(design, cell), (
            f"cell {cell} is at or over the density flag and is NOT a tie-off — "
            f"no penetration in it returns to a coordinate already stitched. "
            f"That is fabric being perforated by stitching, which is the case "
            f"this flag exists for."
        )


def test_fixture_07_underlay_has_no_floor_violations():
    """End-to-end: the last two corpus violations, unfixed since Part 5, are closed.

    Both were medial-axis underlay turnarounds in 07 (`Satin 1` 0.1828mm and
    `Satin 13` 0.0000mm), not satin columns.
    """
    from run_quality_bench import DEFAULT_PARAMS, FIXTURE_DIR, FIXTURE_PARAMS, RNG_SEED

    path = FIXTURE_DIR / "07_circular_badge.png"
    params = FIXTURE_PARAMS.get(path.stem, DEFAULT_PARAMS)
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        path.read_bytes(), fabric_type=params["fabric"], hoop_size=params["hoop"],
        max_colors=params["colors"], text_mode=bool(params.get("text", False)),
    )
    pen = penetration_metrics(design, 0.4, MIN_PENETRATION_MM)
    assert pen["below_floor"] == 0, [
        (o["name"], o["min_mm"]) for o in pen["per_object"] if o["below_floor"]
    ]
