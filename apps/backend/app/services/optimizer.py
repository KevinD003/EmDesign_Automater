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
DAMAGING_STITCH_MM = 0.2  # unambiguous needle/thread damage, never a legitimate turn

# Craft thresholds (spec §4.3/§4.6) — these are what separates a design that RUNS from
# a design that LOOKS right. The v1 scorer checked only machine health, so a design
# with every letter tatami-filled and no underlay still scored 100/100.
SATIN_MAX_SAFE_MM = 6.0   # wider columns snag and loop; split or convert to fill
SATIN_MIN_SAFE_MM = 0.8   # narrower than this the column disappears into the fabric
MIN_FILL_AREA_MM2 = 4.0   # fills smaller than this should be satin/run instead
SPARSE_SPACING_MM = 0.5   # row pitch above this lets fabric show through a fill


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


def _poly_area_mm2(contour) -> float:
    """Shoelace area of an object's outline."""
    if not contour or len(contour) < 3:
        return 0.0
    a = 0.0
    for p, q in zip(contour, contour[1:] + contour[:1]):
        a += p.x * q.y - q.x * p.y
    return abs(a) / 2.0


def _stroke_width_mm(contour) -> float:
    """True stroke width of an object's outline, via its medial axis.

    A bounding box cannot measure this: a curved 3mm swoosh has a 42mm bounding box.
    The contour is rasterized and handed to ``shape.local_width``, which reads the
    width off the distance transform and is therefore curvature-invariant.
    Returns 0.0 when it cannot be measured (caller should skip the check).
    """
    if not contour or len(contour) < 8:
        return 0.0
    try:
        import cv2
        import numpy as np

        from app.services import shape
    except ModuleNotFoundError:  # cv2 is optional at runtime — skip the check
        return 0.0

    xs = [p.x for p in contour]
    ys = [p.y for p in contour]
    w_mm, h_mm = max(xs) - min(xs), max(ys) - min(ys)
    if w_mm <= 0 or h_mm <= 0:
        return 0.0
    px_per_mm = min(6.0, 400.0 / max(w_mm, h_mm))
    pad = 3
    cw, ch = int(w_mm * px_per_mm) + 2 * pad, int(h_mm * px_per_mm) + 2 * pad
    if cw < 8 or ch < 8:
        return 0.0
    mask = np.zeros((ch, cw), np.uint8)
    poly = np.array(
        [[int((p.x - min(xs)) * px_per_mm) + pad, int((p.y - min(ys)) * px_per_mm) + pad] for p in contour],
        np.int32,
    )
    cv2.fillPoly(mask, [poly], 255)
    med_px, _ = shape.local_width(mask)
    return med_px / px_per_mm


def _is_narrow_column(contour, area_mm2: float) -> bool:
    """True when a *filled* object is really a narrow stroke that should be satin.

    A tatami fill on a letter stem, an outline or a swoosh is the single most visible
    auto-digitizing defect: it frays, it reads as fuzzy, and it costs several times the
    stitches a satin column would.
    """
    if area_mm2 <= 0:
        return False
    width_mm = _stroke_width_mm(contour)
    if not (SATIN_MIN_SAFE_MM <= width_mm <= SATIN_MAX_SAFE_MM):
        return False
    length_mm = area_mm2 / max(width_mm, 1e-6)
    return length_mm / max(width_mm, 1e-6) >= 2.5


def _craft_penalties(design: Design, findings: list[QualityFinding]) -> int:
    """Digitizing-craft checks over the OBJECTS (not just the stitch stream).

    These are the defects an embroiderer sees on the garment but a stream-only scorer
    is blind to: columns too wide to hold, elements too small to register, fills sparse
    enough to show fabric, and missing underlay.
    """
    penalty = 0
    objs = [o for o in design.objects if o.contour]
    if not objs:
        return 0

    def _type(o) -> str:
        return str(getattr(o.stitch_type, "value", o.stitch_type))

    def _underlay(o) -> str:
        return str(getattr(o.underlay_type, "value", o.underlay_type) or "NONE")

    wide, narrow, sparse, no_under, tiny_obj, should_satin = [], [], [], [], [], []
    for o in objs:
        area = _poly_area_mm2(o.contour)
        t = _type(o)
        if t == "SATIN":
            width = _stroke_width_mm(o.contour)
            if width > SATIN_MAX_SAFE_MM:
                wide.append(o.name)
            elif 0 < width < SATIN_MIN_SAFE_MM:
                narrow.append(o.name)
        elif t == "TATAMI":
            if 0 < area < MIN_FILL_AREA_MM2:
                tiny_obj.append(o.name)
            if o.density and (1.0 / max(o.density, 1e-6)) > SPARSE_SPACING_MM:
                sparse.append(o.name)
            if _is_narrow_column(o.contour, area):
                should_satin.append(o.name)
        if _underlay(o) == "NONE" and area > MIN_FILL_AREA_MM2:
            no_under.append(o.name)

    if wide:
        findings.append(QualityFinding(
            severity="error", code="satin_too_wide", count=len(wide),
            message=f"{len(wide)} satin column(s) wider than {SATIN_MAX_SAFE_MM}mm — "
                    "long stitches will snag; split them or use a fill.",
        ))
        penalty += min(20, 5 + 2 * len(wide))
    if narrow:
        findings.append(QualityFinding(
            severity="warn", code="satin_too_narrow", count=len(narrow),
            message=f"{len(narrow)} satin column(s) under {SATIN_MIN_SAFE_MM}mm — "
                    "will sink into the fabric and read as a broken line.",
        ))
        penalty += min(10, 2 * len(narrow))
    if sparse:
        findings.append(QualityFinding(
            severity="warn", code="sparse_fill", count=len(sparse),
            message=f"{len(sparse)} fill(s) with row spacing over {SPARSE_SPACING_MM}mm — "
                    "fabric will show through.",
        ))
        penalty += min(15, 3 * len(sparse))
    if tiny_obj:
        findings.append(QualityFinding(
            severity="warn", code="unstitchable_detail", count=len(tiny_obj),
            message=f"{len(tiny_obj)} filled area(s) under {MIN_FILL_AREA_MM2}mm² — too small to "
                    "register; enlarge the design or drop the detail.",
        ))
        penalty += min(10, 2 * len(tiny_obj))
    if should_satin:
        findings.append(QualityFinding(
            severity="error", code="should_be_satin", count=len(should_satin),
            message=f"{len(should_satin)} narrow element(s) stitched as a fill instead of a satin "
                    "column — they will fray and read as fuzzy edges.",
        ))
        penalty += min(25, 6 + 4 * len(should_satin))
    if no_under:
        findings.append(QualityFinding(
            severity="warn", code="no_underlay", count=len(no_under),
            message=f"{len(no_under)} area(s) stitched with no underlay — the top layer will "
                    "sink and the outline will shift.",
        ))
        penalty += min(15, 3 * len(no_under))
    return penalty


def _grade(score: int) -> str:
    for cutoff, g in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= cutoff:
            return g
    return "F"


def analyze_quality(design: Design) -> QualityReport:
    """Deterministic quality score + findings from the stitch stream."""
    stitches = design.stitches
    metrics = path_metrics(design)

    long_ct = tiny_ct = damaging_ct = 0
    prev = None
    for s in stitches:
        if prev is not None and s.command == "STITCH" and prev.command in ("STITCH", "JUMP"):
            d = _dist(prev.x, prev.y, s.x, s.y)
            if d > LONG_STITCH_MM:
                long_ct += 1
            elif 0 < d < DAMAGING_STITCH_MM:
                damaging_ct += 1
            elif 0 < d < TINY_STITCH_MM:
                tiny_ct += 1
        prev = s
    total_stitch = max(1, sum(1 for s in stitches if s.command == "STITCH"))

    findings: list[QualityFinding] = []
    score = 100

    if long_ct:
        findings.append(QualityFinding(
            severity="error", code="long_stitch", count=long_ct,
            message=f"{long_ct} stitch(es) exceed {LONG_STITCH_MM}mm — may break or skip.",
        ))
        score -= min(30, 5 + long_ct)
    if damaging_ct:
        findings.append(QualityFinding(
            severity="error", code="damaging_stitch", count=damaging_ct,
            message=f"{damaging_ct} stitch(es) under {DAMAGING_STITCH_MM}mm — needle/thread damage.",
        ))
        score -= min(20, 5 + damaging_ct // 5)
    # A dense fill legitimately turns by one row pitch (~0.4mm) at the end of every row,
    # so sub-0.5mm moves are only a defect when they dominate the design rather than
    # tracking the row count. Penalising them flat would mark correct dense fills down.
    if tiny_ct and tiny_ct > 0.15 * total_stitch:
        findings.append(QualityFinding(
            severity="warn", code="tiny_stitch", count=tiny_ct,
            message=f"{tiny_ct} stitch(es) under {TINY_STITCH_MM}mm ({tiny_ct / total_stitch:.0%} of "
                    "the design) — density is too high for the thread.",
        ))
        score -= 10

    score -= _craft_penalties(design, findings)
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
