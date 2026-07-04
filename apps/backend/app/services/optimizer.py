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
TINY_STITCH_MM = 0.5    # below this, thread shreds / needle deflects


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


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


def analyze_quality(design: Design) -> QualityReport:
    """Deterministic quality score + findings from the stitch stream."""
    stitches = design.stitches
    metrics = path_metrics(design)

    long_ct = tiny_ct = 0
    prev = None
    for s in stitches:
        if prev is not None and s.command == "STITCH" and prev.command in ("STITCH", "JUMP"):
            d = _dist(prev.x, prev.y, s.x, s.y)
            if d > LONG_STITCH_MM:
                long_ct += 1
            elif 0 < d < TINY_STITCH_MM:
                tiny_ct += 1
        prev = s

    findings: list[QualityFinding] = []
    score = 100

    if long_ct:
        findings.append(QualityFinding(
            severity="error", code="long_stitch", count=long_ct,
            message=f"{long_ct} stitch(es) exceed {LONG_STITCH_MM}mm — may break or skip.",
        ))
        score -= min(30, 5 + long_ct)
    if tiny_ct:
        findings.append(QualityFinding(
            severity="warn", code="tiny_stitch", count=tiny_ct,
            message=f"{tiny_ct} stitch(es) under {TINY_STITCH_MM}mm — thread shredding / needle wear.",
        ))
        score -= min(20, tiny_ct // 2)
    if metrics.color_changes > 15:
        findings.append(QualityFinding(
            severity="warn", code="many_colors", count=metrics.color_changes,
            message=f"{metrics.color_changes} color changes — long run-time, many thread swaps.",
        ))
        score -= 10
    if stitches and metrics.jump_count > max(20, len(stitches) * 0.1):
        findings.append(QualityFinding(
            severity="warn", code="many_jumps", count=metrics.jump_count,
            message=f"{metrics.jump_count} jumps ({metrics.travel_mm}mm travel) — try Optimize to cut trims.",
        ))
        score -= 10
    if not findings:
        findings.append(QualityFinding(severity="info", code="clean", message="No quality issues detected."))

    score = max(0, min(100, score))
    return QualityReport(score=score, grade=_grade(score), metrics=metrics, findings=findings)
