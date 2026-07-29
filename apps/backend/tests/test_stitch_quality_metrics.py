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
    # 11 since v2 Part 16: the checkerboard thinner fix brought the last of
    # fixture 04's eleven satin objects into the zigzag count (it previously
    # produced no same-side pairs at all and was excluded from per_object).
    assert rec["penetration"]["satin_objects"] == 11


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
    assert result.penetration["satin_objects"] == 11  # see CLI test note (Part 16 thinner fix)
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


def test_density_corpus_health_is_pinned():
    """Fixture 08 is the corpus's densest; it must stay far below the flag.

    The exact max differs by background-separation path (7 WITH rembg, 6
    WITHOUT — segmentation differs, so stitches do), so the pin brackets both.
    What must hold on either path: the healthy corpus peaks at half the flag
    level, which is what makes 14 = "a second full layer on the worst healthy
    cell" keep meaning what the Part 12 audit says it means.
    """
    from measure_stitch_quality import DENSITY_FLAG_PER_CELL, density_metrics
    from run_quality_bench import DEFAULT_PARAMS, FIXTURE_DIR, FIXTURE_PARAMS, RNG_SEED

    path = FIXTURE_DIR / "08_mascot_detail.png"
    params = FIXTURE_PARAMS.get(path.stem, DEFAULT_PARAMS)
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        path.read_bytes(), fabric_type=params["fabric"], hoop_size=params["hoop"],
        max_colors=params["colors"], text_mode=bool(params.get("text", False)),
    )
    m = density_metrics(design)
    assert m["max_per_cell"] in (6, 7)
    assert m["max_per_cell"] * 2 == DENSITY_FLAG_PER_CELL or m["max_per_cell"] < 7
    assert m["flagged_cells"] == 0


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
