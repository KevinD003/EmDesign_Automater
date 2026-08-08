"""Phase 8 — optimization engine (classical baseline).

Two production-grade, deterministic tools that don't need a GPU or trained models
(those are the *future* of Phase 8):

- ``optimize_path``  — reorder objects WITHIN each color to cut needle travel/jumps.
  ``rebuild_design`` already groups objects by color (so color changes are already
  minimal); the remaining win is a nearest-neighbour tour within each color block.
- ``analyze_quality`` — score a design (0..100) + itemized findings: over-long
  stitches (thread breakage), sub-millimetre stitches (needle/thread damage),
  excessive color changes / jumps. Rule-based and honest.

Neural digitizing / path-RL / learned quality would slot in behind the same API.
"""

from __future__ import annotations

import itertools
import math

from app.models.design import (
    Design,
    OptimizeReport,
    PathMetrics,
    QualityFinding,
    QualityReport,
)
from app.services import digitizer

LONG_STITCH_MM = 12.7  # most machines choke above ~12.7mm (0.5")
# Below this, thread shreds / needle deflects. 0.3, not 0.5 (changed v2 Part
# 15): fills legitimately connect adjacent rows with one pitch-length stitch —
# 0.4-0.45mm, the industry-standard row spacing — so flagging under-0.5 would
# penalise every properly-digitized fill by hundreds of findings. 0.3 matches
# MIN_PENETRATION_MM's grounding and stays subject to the fabric protocol.
TINY_STITCH_MM = 0.3
# No published industry benchmark for jumps-per-1,000 exists (verified by web research,
# 2026-07-29 — docs/COMPETITOR-COMPARISON.md §"what the research corrects" item 1);
# production guidance is expressed as TRIM cost: ~3-7s per trim, machine stops 6-20s.
# The rate is therefore reported as an internal, comparable-over-time metric only.
TRIM_COST_S = "3-7"  # seconds per trim, the cited production cost of a jump that needs trimming
HOOP_OVERFLOW_PENALTY = 25  # a design that cannot be hooped cannot be stitched — near-failing


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def parse_hoop(hoop_size: str | None) -> tuple[float, float] | None:
    """Parse a '100x100' / '130x180mm' hoop string → (w, h) mm, or None if unset/bad.

    Shared by quality analysis and the export validator — one tolerant parse,
    one behavior: an absent or malformed hoop is "unknown", never an error.
    """
    if not hoop_size:
        return None
    try:
        w, h = hoop_size.lower().replace("mm", "").split("x")
        return float(w), float(h)
    except (ValueError, AttributeError):
        return None


def _centroid(contour) -> tuple[float, float]:
    if not contour:
        return (0.0, 0.0)
    return (sum(p.x for p in contour) / len(contour), sum(p.y for p in contour) / len(contour))


def path_metrics(design: Design) -> PathMetrics:
    """Travel / jump / trim / color-change stats read off the stitch stream."""
    stitches = design.stitches
    color_changes = sum(1 for s in stitches if s.command == "COLOR_CHANGE")
    trims = sum(1 for s in stitches if s.command == "TRIM")
    jump_count = 0
    travel = 0.0
    prev = None
    for s in stitches:
        if prev is not None and s.command == "JUMP":
            jump_count += 1
            travel += _dist(prev.x, prev.y, s.x, s.y)
        prev = s
    return PathMetrics(
        stitch_count=len(stitches),
        color_changes=color_changes,
        trims=trims,
        jump_count=jump_count,
        travel_mm=round(travel, 1),
    )


def _nearest_neighbour_order(members: list) -> list:
    """Order objects greedily by centroid, starting from the top-left-most."""
    remaining = list(members)
    cents = {id(o): _centroid(o.contour) for o in remaining}
    # start nearest to the origin (top-left) for a stable, sensible entry
    start = min(remaining, key=lambda o: cents[id(o)][0] + cents[id(o)][1])
    ordered = [start]
    remaining.remove(start)
    while remaining:
        cx, cy = cents[id(ordered[-1])]
        nxt = min(remaining, key=lambda o: _dist(cx, cy, *cents[id(o)]))
        ordered.append(nxt)
        remaining.remove(nxt)
    return ordered


def optimize_path(design: Design) -> tuple[Design, OptimizeReport]:
    """Reorder objects within each color by nearest-neighbour, then rebuild.

    Returns the (possibly) improved design + a before/after report. If the design
    isn't regenerable (no contoured objects) or the reorder doesn't help, the
    original design is returned unchanged with ``reordered=False``.
    """
    objs = [o for o in design.objects if o.contour]
    before = path_metrics(design)

    if len(objs) < 2 or len(objs) != len(design.objects):
        return design, OptimizeReport(
            reordered=False,
            before=before,
            after=before,
            note="Path optimization needs a digitized design with ≥2 contoured objects.",
        )

    # Group by color, preserving the existing color order; NN-order within each group.
    groups: dict[int, list] = {}
    color_order: list[int] = []
    for o in sorted(design.objects, key=lambda o: o.sequence_order):
        if o.color_stop not in groups:
            groups[o.color_stop] = []
            color_order.append(o.color_stop)
        groups[o.color_stop].append(o)

    new_sequence = []
    for color in color_order:
        new_sequence.extend(_nearest_neighbour_order(groups[color]))

    reordered_objs = [o.model_copy(update={"sequence_order": i + 1}) for i, o in enumerate(new_sequence)]
    candidate = design.model_copy(update={"objects": reordered_objs})
    rebuilt = digitizer.rebuild_design(candidate)
    after = path_metrics(rebuilt)

    if after.travel_mm >= before.travel_mm:
        return design, OptimizeReport(
            reordered=False, before=before, after=before, note="Already near-optimal — no reorder applied."
        )

    return rebuilt, OptimizeReport(
        reordered=True,
        before=before,
        after=after,
        color_changes_saved=max(0, before.color_changes - after.color_changes),
        travel_saved_mm=round(before.travel_mm - after.travel_mm, 1),
        trims_saved=max(0, before.trims - after.trims),
    )


def _grade(score: int) -> str:
    for cutoff, g in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= cutoff:
            return g
    return "F"


def _stream_stats(stitches) -> tuple[int, int, float, float]:
    """One pass over the stream → (long_ct, tiny_ct, max_stitch_mm, mean_stitch_mm).

    long/tiny counts keep their historical basis (a STITCH landing after a STITCH
    or JUMP); max/mean cover true STITCH-to-STITCH steps only, so jump landings
    don't inflate the reported stitch lengths.
    """
    long_ct = tiny_ct = seg_ct = 0
    seg_sum = max_mm = 0.0
    prev = None
    for s in stitches:
        if prev is not None and s.command == "STITCH" and prev.command in ("STITCH", "JUMP"):
            d = _dist(prev.x, prev.y, s.x, s.y)
            if d > LONG_STITCH_MM:
                long_ct += 1
            elif 0 < d < TINY_STITCH_MM:
                tiny_ct += 1
            if prev.command == "STITCH":
                seg_ct += 1
                seg_sum += d
                max_mm = max(max_mm, d)
        prev = s
    return long_ct, tiny_ct, max_mm, (seg_sum / seg_ct if seg_ct else 0.0)


def _hoop_fit(design: Design) -> tuple[bool | None, QualityFinding | None]:
    """(fits?, overflow finding). No/unparseable hoop → (None, None): unknown, no penalty."""
    hoop = parse_hoop(design.hoop_size)
    if hoop is None:
        return None, None
    hw, hh = hoop
    if design.width_mm > hw or design.height_mm > hh:
        return False, QualityFinding(
            severity="error", code="hoop_overflow", count=1,
            message=f"Design {design.width_mm}x{design.height_mm}mm exceeds the {design.hoop_size} hoop.",
        )
    return True, None


# ── CTO A9/C11: real rejection criteria ──────────────────────────────────────
# The pre-A9 scorer checked only long/tiny stitches, jump count and color
# count, and certified broken output: 8mm lettering with jump-crossed counters
# and no ties scored 98/A. A trusted-but-wrong grade is worse than none. The
# checks below are the criteria a commercial digitizer is actually rejected
# on. Each one self-gates on assessability (toy streams have no room for
# locks; imported designs carry no contours), skipping rather than guessing.

_LOCK_WINDOW = 6          # stitches inspected around each thread end
_LOCK_SEG_MM = 1.0        # a lock = >=2 consecutive segments this short
_MIN_LOCKABLE_BLOCK = 12  # smaller blocks can't be judged for locks
_OPEN_FABRIC_MARGIN_MM = 1.5   # how far outside every region counts as open fabric
_SATIN_WIDTH_LIMIT_MM = 7.0    # SATIN_MAX_W_MM (4.5) + pull comp + real-world slack
_TRIMS_PER_1000_WARN = 50.0
_ZIGZAG_RATIO = 0.5


def _thread_blocks(stitches):
    """Consecutive STITCH runs split at TRIM / COLOR_CHANGE (thread cuts)."""
    block: list = []
    for s in stitches:
        c = str(s.command)
        if c == "STITCH":
            block.append((s.x, s.y))
        elif c in ("TRIM", "COLOR_CHANGE", "END"):
            if block:
                yield block
            block = []
    if block:
        yield block


def _has_lock(pts) -> bool:
    return sum(1 for a, b in itertools.pairwise(pts)
               if _dist(a[0], a[1], b[0], b[1]) <= _LOCK_SEG_MM) >= 2


def _unlocked_thread_ends(stitches) -> tuple[int, int]:
    """(unlocked, assessable) thread ends — every cut end should carry a tie."""
    unlocked = total = 0
    for block in _thread_blocks(stitches):
        if len(block) < _MIN_LOCKABLE_BLOCK:
            continue
        total += 2
        if not _has_lock(block[:_LOCK_WINDOW]):
            unlocked += 1
        if not _has_lock(block[-_LOCK_WINDOW:]):
            unlocked += 1
    return unlocked, total


def _object_polys(design):
    """Object contours (+holes) as float arrays in mm, or None if any missing."""
    import numpy as np

    if not design.objects or any(not o.contour for o in design.objects):
        return None
    polys = []
    for o in design.objects:
        polys.append((np.array([[p.x, p.y] for p in o.contour], np.float32), False))
        for h in o.holes or []:
            polys.append((np.array([[p.x, p.y] for p in h], np.float32), True))
    return polys


def _outside_all(x: float, y: float, polys) -> bool:
    import cv2

    inside_any = False
    for poly, is_hole in polys:
        d = cv2.pointPolygonTest(poly, (float(x), float(y)), True)
        if is_hole:
            if d > _OPEN_FABRIC_MARGIN_MM:
                return True      # deep inside a knocked-out counter = open fabric
        elif d >= -_OPEN_FABRIC_MARGIN_MM:
            inside_any = True
    return not inside_any


def _attached_open_fabric_segments(design) -> int | None:
    """Thread-attached segments (STITCH, or JUMP with no TRIM before it) that
    cross open fabric — the whisker/counter-crossing defect (C2). None when the
    design carries no contours to judge against (imported machine files)."""
    polys = _object_polys(design)
    if polys is None:
        return None
    count = 0
    attached = True
    prev = None
    for s in design.stitches:
        c = str(s.command)
        if c in ("TRIM", "COLOR_CHANGE"):
            attached = False
            prev = (s.x, s.y)
            continue
        if c not in ("STITCH", "JUMP"):
            prev = (s.x, s.y)
            continue
        if prev is not None and attached:
            length = _dist(prev[0], prev[1], s.x, s.y)
            if length > 2.0:
                n = max(2, int(length / 1.0))
                if any(_outside_all(prev[0] + (s.x - prev[0]) * i / n,
                                    prev[1] + (s.y - prev[1]) * i / n, polys)
                       for i in range(1, n)):
                    count += 1
        if c == "STITCH":
            attached = True
        prev = (s.x, s.y)
    return count


def _satin_width_violations(stitches) -> int:
    """Zigzag crossings wider than any real satin column should be."""
    count = 0
    for block in _thread_blocks(stitches):
        for a, b, c in zip(block, block[1:], block[2:]):
            ab = _dist(a[0], a[1], b[0], b[1])
            bc = _dist(b[0], b[1], c[0], c[1])
            gap = _dist(a[0], a[1], c[0], c[1])
            if (min(ab, bc) > _SATIN_WIDTH_LIMIT_MM
                    and gap < _ZIGZAG_RATIO * min(ab, bc)):
                count += 1
    return count


def _uniform_fill_angles(design) -> int:
    """Number of fills sharing one angle when >=3 fills exist (else 0)."""
    angles = [round(float(o.stitch_angle), 1) for o in design.objects
              if str(o.stitch_type) == "TATAMI"]
    if len(angles) >= 3 and len(set(angles)) == 1:
        return len(angles)
    return 0


def _penalty_findings(design: Design, metrics, long_ct: int, tiny_ct: int) -> tuple[list[QualityFinding], int]:
    """Score-affecting findings + total penalty. Thresholds unchanged from v1."""
    findings: list[QualityFinding] = []
    penalty = 0
    if long_ct:
        findings.append(QualityFinding(
            severity="error", code="long_stitch", count=long_ct,
            message=f"{long_ct} stitch(es) exceed {LONG_STITCH_MM}mm — may break or skip.",
        ))
        penalty += min(30, 5 + long_ct)
    if tiny_ct:
        findings.append(QualityFinding(
            severity="warn", code="tiny_stitch", count=tiny_ct,
            message=f"{tiny_ct} stitch(es) under {TINY_STITCH_MM}mm — thread shredding / needle wear.",
        ))
        penalty += min(20, tiny_ct // 2)
    if metrics.color_changes > 15:
        findings.append(QualityFinding(
            severity="warn", code="many_colors", count=metrics.color_changes,
            message=f"{metrics.color_changes} color changes — long run-time, many thread swaps.",
        ))
        penalty += 10
    if design.stitches and metrics.jump_count > max(20, len(design.stitches) * 0.1):
        findings.append(QualityFinding(
            severity="warn", code="many_jumps", count=metrics.jump_count,
            message=f"{metrics.jump_count} jumps ({metrics.travel_mm}mm travel) — try Optimize to cut trims.",
        ))
        penalty += 10

    # ── Real rejection criteria (CTO A9/C11) ────────────────────────────────
    unlocked, assessable = _unlocked_thread_ends(design.stitches)
    if unlocked:
        findings.append(QualityFinding(
            severity="error", code="unlocked_ends", count=unlocked,
            message=(f"{unlocked} of {assessable} thread ends have no tie-in/tie-off lock "
                     f"— the design unravels at first wash or pulls out mid-run."),
        ))
        penalty += min(35, 10 + 2 * unlocked)
    open_jumps = _attached_open_fabric_segments(design)
    if open_jumps:
        findings.append(QualityFinding(
            severity="error", code="open_fabric_travel", count=open_jumps,
            message=(f"{open_jumps} thread-attached segment(s) cross open fabric — "
                     f"visible whiskers over bare cloth (or across knocked-out counters)."),
        ))
        penalty += min(35, 10 + 2 * open_jumps)
    wide = _satin_width_violations(design.stitches)
    if wide:
        findings.append(QualityFinding(
            severity="error", code="satin_too_wide", count=wide,
            message=(f"{wide} satin crossing(s) wider than {_SATIN_WIDTH_LIMIT_MM}mm — "
                     f"loose floats that snag and collapse."),
        ))
        penalty += min(25, 5 + wide)
    uniform = _uniform_fill_angles(design)
    if uniform:
        findings.append(QualityFinding(
            severity="warn", code="uniform_fill_angles", count=uniform,
            message=(f"All {uniform} fills sew at one angle — push/pull accumulates in "
                     f"one direction and the result reads visually flat."),
        ))
        penalty += 5
    if design.stitches:
        trims_per_1000 = metrics.trims / max(metrics.stitch_count, 1) * 1000
        if trims_per_1000 > _TRIMS_PER_1000_WARN:
            findings.append(QualityFinding(
                severity="warn", code="high_trim_rate", count=metrics.trims,
                message=(f"{trims_per_1000:.0f} trims per 1,000 stitches — each costs "
                         f"~{TRIM_COST_S}s of machine time plus two untied tails."),
            ))
            penalty += 10
    return findings, penalty


def analyze_quality(design: Design) -> QualityReport:
    """Deterministic quality score + findings from the stitch stream."""
    stitches = design.stitches
    metrics = path_metrics(design)
    long_ct, tiny_ct, max_mm, mean_mm = _stream_stats(stitches)

    findings, penalty = _penalty_findings(design, metrics, long_ct, tiny_ct)
    hoop_fit, overflow = _hoop_fit(design)
    if overflow is not None:
        findings.append(overflow)
        penalty += HOOP_OVERFLOW_PENALTY
    if not findings:
        findings.append(QualityFinding(severity="info", code="clean", message="No quality issues detected."))

    # Informational jump rate — reported alongside (NOT replacing) the many_jumps penalty.
    jumps_per_1000 = round(metrics.jump_count / max(metrics.stitch_count, 1) * 1000, 1)
    if stitches:
        findings.append(QualityFinding(
            severity="info", code="jump_rate", count=metrics.jump_count,
            message=(
                f"{jumps_per_1000} jumps per 1,000 stitches — each trimmed jump costs "
                f"~{TRIM_COST_S}s of machine time; lower is faster to run."
            ),
        ))

    score = max(0, min(100, 100 - penalty))
    return QualityReport(
        score=score, grade=_grade(score), metrics=metrics, findings=findings,
        max_stitch_mm=round(max_mm, 2), mean_stitch_mm=round(mean_mm, 2),
        jumps_per_1000=jumps_per_1000, hoop_fit=hoop_fit,
    )
