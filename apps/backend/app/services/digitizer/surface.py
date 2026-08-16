"""SURFACE METRIC 1 — boundary deviation. Does the sewn edge follow the contour?

The longest-standing unbuilt item in this repository, and the one with the most
evidence behind it. Five separate findings, across four tranches, all point here:

  * the single-branch noise boundary is a PROXY, NOT A DETECTOR — its own shipped
    docstring says so — so a noise sliver that prunes to one branch gets sewn and
    no numeric gate objects;
  * ragged edges have no number anywhere in the codebase;
  * small text has no number: "HARBOR CLUB" is illegible on our easiest input;
  * the substrate fix's correctness check was a human looking at a render, and
    the only justification available for `INVISIBLE_ON_CLOTH_DE2000` was that
    same look;
  * fixture 09's three stray dashes were caught by the visual harness AFTER every
    numeric gate had passed.

## What it measures

For every satin object, for EACH SIDE SEPARATELY, the signed distance in mm from
each emitted edge penetration to the object's own stored contour. Per object:

    offset     p50 of signed distance, per side  -- WHERE the edge sits
    roughness  p95 - p5 of signed distance       -- how much it WANDERS
    max|dev|   the single worst penetration      -- the spike p95 forgives

SEPARATING OFFSET FROM ROUGHNESS IS THE LOAD-BEARING DECISION. A satin edge is
*supposed* to sit outside the contour by the object's stored pull compensation.
A metric reporting raw distance reads that intended offset as raggedness, and
then either false-alarms on every satin object or gets loosened until it cannot
fire — the DENSITY-LOCK lesson. Offset is calibration (and doubles as a free
check that pull comp is applied at all, UP1's subject); roughness is the
surface-quality number.

## Why the edge points come from generation and not from the stream

Established by a failed prototype (SURFACE-METRICS-SPEC §1.3), recorded because
the obvious implementation is the wrong one. Capturing penetrations within a
radius of the contour is confounded three ways: every object's max came back at
exactly the capture radius (the window truncates the distribution it measures),
fill interiors near the boundary enter the "edge" population (fixture 01's plain
tatami read 1.3 mm of "roughness" that was row geometry), and on a column
narrower than twice the radius both sides land in one band so the spread
measures COLUMN WIDTH. `_column_ends` already produces these points, per side,
by construction; `constants._EDGE_LOG` takes them there.

## No band, deliberately

Reported in mm AND in thread widths (40wt ≈ 0.4 mm). No pass threshold is set
here. This repository has twice been burned by a constant fitted to the corpus
that named it, so the instrument reports the distribution first and any later
gate must be argued physically ("a knife edge wanders less than half a thread"),
not fitted.
"""

from __future__ import annotations

#: 40wt embroidery thread, the corpus default. Deviations are reported in these
#: as well as in mm, because "0.31 mm" means nothing to a digitizer and
#: "three-quarters of a thread" means something immediately.
THREAD_W_MM = 0.4


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile. Written out rather than pulled from numpy
    so a one-point object degrades to that point instead of raising."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _signed_distances(points_px, contour_px, mm_per_px: float, holes=()) -> list[float]:
    """Signed mm distance from each point to the object's NEAREST boundary.

    `cv2.pointPolygonTest` with `measureDist=True` returns positive INSIDE, so
    the sign is inverted here. Getting that backwards would report a satin edge
    correctly offset outward by pull compensation as sitting inward, and the
    offset column exists precisely to be compared against the stored pull.

    HOLES ARE BOUNDARIES TOO, and the first version of this function forgot it.
    On an annulus every column has one end on the OUTER edge and one on the
    HOLE, so measuring both against the outer contour reported the ring's WIDTH
    as deviation: fixture 07's navy ring came back at 6.78 mm "roughness" with a
    −3.09 mm offset on one side, and 08's knocked-out head at 15.46 mm. Both are
    rings. Both were the instrument measuring the wrong distance, not the
    pipeline sewing badly — caught because the three worst objects in the whole
    corpus were all the ones with holes.

    So the distance is to whichever boundary is closest, with the sign taken
    from the outer polygon: outside the object, or inside a hole, is positive.
    """
    import cv2
    import numpy as np

    poly = np.asarray(contour_px, dtype=np.float32).reshape(-1, 1, 2)
    if len(poly) < 3:
        return []
    hole_polys = [np.asarray(h, dtype=np.float32).reshape(-1, 1, 2)
                  for h in (holes or ()) if h is not None and len(h) >= 3]
    # `holes` arrives as OpenCV contours (N,1,2); reshape(-1,1,2) is a no-op
    # for those and normalises a plain (N,2) list, so both callers work.
    out = []
    for x, y in points_px:
        pt = (float(x), float(y))
        d = -float(cv2.pointPolygonTest(poly, pt, True))     # + outside the shape
        for hp in hole_polys:
            dh = float(cv2.pointPolygonTest(hp, pt, True))   # + inside the hole
            if abs(dh) < abs(d):
                d = dh
        out.append(d * mm_per_px)
    return out


def boundary_deviation(edge_pairs, contour_px, mm_per_px: float, holes=()) -> dict | None:
    """Per-object boundary deviation from the per-side edge sets.

    `edge_pairs` is `[(sideA, sideB), ...]` in working pixels, exactly as
    `_column_ends` produced it — the two sides are kept apart because a column's
    two edges are different surfaces and averaging them hides a one-sided
    defect, which is what a ragged satin usually is.

    Returns `None` when there is nothing to measure (no columns, or a contour
    too small to be a polygon), so a caller can distinguish "measured, clean"
    from "not measured" — a zero would conflate them.
    """
    if not edge_pairs or contour_px is None or len(contour_px) < 3:
        return None
    side_a = [p[0] for p in edge_pairs]
    side_b = [p[1] for p in edge_pairs]
    out: dict = {"columns": len(edge_pairs), "sides": {}}
    worst_rough = 0.0
    worst_abs = 0.0
    for name, pts in (("a", side_a), ("b", side_b)):
        d = _signed_distances(pts, contour_px, mm_per_px, holes)
        if not d:
            continue
        s = sorted(d)
        p5, p50, p95 = _percentile(s, 0.05), _percentile(s, 0.50), _percentile(s, 0.95)
        rough = p95 - p5
        mx = max(abs(v) for v in d)
        worst_rough = max(worst_rough, rough)
        worst_abs = max(worst_abs, mx)
        out["sides"][name] = {
            "n": len(d),
            "offset_p50_mm": round(p50, 4),
            "roughness_mm": round(rough, 4),
            "roughness_threads": round(rough / THREAD_W_MM, 3),
            "max_abs_mm": round(mx, 4),
            "p5_mm": round(p5, 4),
            "p95_mm": round(p95, 4),
        }
    if not out["sides"]:
        return None
    out["roughness_mm"] = round(worst_rough, 4)
    out["roughness_threads"] = round(worst_rough / THREAD_W_MM, 3)
    out["max_abs_mm"] = round(worst_abs, 4)
    # The two sides' offsets, kept separate AND differenced: a column whose sides
    # are offset by different amounts is not merely rough, it is off-centre, and
    # that is a different defect with a different cause (axis placement, not
    # edge tracking).
    if len(out["sides"]) == 2:
        out["offset_asymmetry_mm"] = round(
            abs(out["sides"]["a"]["offset_p50_mm"] - out["sides"]["b"]["offset_p50_mm"]), 4)
    return out


def design_summary(rows: list[dict]) -> dict:
    """Design-level aggregate: median and worst object roughness, worst named.

    The worst object is NAMED rather than merely counted, because "the design's
    worst edge is 1.2 mm" is unactionable and "object 47 is 1.2 mm" is a place
    to look — the same reason the drop log records positions.
    """
    measured = [r for r in rows if r.get("boundary")]
    if not measured:
        return {"objects_measured": 0}
    rough = sorted(r["boundary"]["roughness_mm"] for r in measured)
    worst = max(measured, key=lambda r: r["boundary"]["roughness_mm"])
    return {
        "objects_measured": len(measured),
        "median_roughness_mm": round(_percentile(rough, 0.5), 4),
        "median_roughness_threads": round(_percentile(rough, 0.5) / THREAD_W_MM, 3),
        "worst_roughness_mm": round(rough[-1], 4),
        "worst_roughness_threads": round(rough[-1] / THREAD_W_MM, 3),
        "worst_object_seq": worst["seq"],
        "worst_object_name": worst.get("name", ""),
        "max_abs_mm": round(max(r["boundary"]["max_abs_mm"] for r in measured), 4),
    }


def record(seq: int, contour_px, mm_per_px: float, edge_pairs, holes=()) -> None:
    """Append one object's boundary row to `constants._SURFACE_LOG`.

    The append lives here rather than inline in `pipeline.py` for the same
    reason `log_classification` does: one writer, one row shape, and two lines
    of budget back against the 1500-line gate.
    """
    from app.services.digitizer.constants import _SURFACE_LOG

    _SURFACE_LOG.append({
        "seq": seq,
        "name": f"Region {seq}",
        "boundary": boundary_deviation(edge_pairs, contour_px, mm_per_px, holes),
    })
