"""Stitch-quality measurement, committed rather than reconstructed (v2 Part 5).

Two families of measurement, both taken from the STITCH STREAM and the object
outlines — never from the preview bitmap, and never from a digitizer internal.
What a machine sews is the stitch stream, so that is what gets graded.

**Coverage** (used by every audit since Part 2.5, described in prose each time
and never committed until now):

  * ``interior``  — share of the design's interior covered by thread, where
    interior is the object outline eroded by ``EROSION_MM``.
  * ``edge_band`` — share of the outline's outer ``EROSION_MM`` covered.
    Separating this from the interior is the point: a fill can look complete
    while leaving the outline ragged, and averaging the two hides exactly that.
  * ``spill``     — thread area falling OUTSIDE the outline, as a share of all
    thread. Introduced in Part 2.5 because edge-band coverage alone flatters any
    fill that overshoots its outline.

**Penetration density** (new in Part 5) — the production-safety metric Part 4
§8 flagged as missing. Boundary-paced satin sets its pitch by the FASTER of a
stroke's two boundaries, so on the inside of a curve the slower boundary gets
its penetrations closer together than the nominal pitch. Too close and the
needle perforates the fabric along a line rather than stitching on it.

Same-side penetrations are found from the stream alone, with no help from the
generator: a satin path alternates sides (``A0 B0 A1 B1 …``), so points ``i-1``
and ``i+1`` are the same-side pair, and the triple is recognisable because it
ZIGZAGS — the same-side gap is shorter than either crossing. A running-stitch
underlay or a tatami row fails that test (their points advance along a line),
so they cannot pollute the number.

Usage
-----
    python scripts/measure_stitch_quality.py                 # whole bench corpus
    python scripts/measure_stitch_quality.py --fixture 04_thin_line_outline
    python scripts/measure_stitch_quality.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PROBE_DIR = BACKEND_ROOT / "tests" / "fixtures" / "curvature_probe"

PX_PER_MM = 10.0        # raster resolution for the coverage masks
THREAD_WIDTH_MM = 0.4   # 40wt thread
EROSION_MM = 0.6        # interior = outline eroded by this; the rest is edge band
MIN_INTERIOR_FRAC = 0.05  # below this the shape has no interior to speak of
# A satin triple must actually zigzag to count as a same-side penetration pair.
# Guards against reading a running-stitch underlay or a tatami row as satin.
ZIGZAG_RATIO = 0.9


def _cmd(stitch) -> str:
    return stitch.command.value if hasattr(stitch.command, "value") else str(stitch.command)


# ── Penetration density ──────────────────────────────────────────────────────


def _runs(stitches):
    """Split a stitch stream into uninterrupted STITCH runs (a jump/trim breaks one)."""
    run, out = [], []
    for s in stitches:
        if _cmd(s) == "STITCH":
            run.append((s.x, s.y))
        else:
            if len(run) >= 3:
                out.append(run)
            run = []
    if len(run) >= 3:
        out.append(run)
    return out


def same_side_spacings(stitches) -> list[float]:
    """Distances between consecutive SAME-SIDE needle penetrations, in mm.

    In a satin path the sides alternate, so ``i-1`` and ``i+1`` are the same-side
    pair. The triple only counts when it zigzags — the same-side gap shorter than
    either crossing — which is true of a satin column pair and false of any
    stitch sequence that advances along a line.
    """
    out: list[float] = []
    for run in _runs(stitches):
        for a, b, c in zip(run, run[1:], run[2:]):
            gap = math.dist(a, c)
            if gap < ZIGZAG_RATIO * min(math.dist(a, b), math.dist(b, c)):
                out.append(gap)
    return out


def penetration_metrics(design, pitch_mm: float, floor_mm: float) -> dict:
    """Same-side penetration spacing for the design and for its tightest object.

    ``min_spacing_mm`` is the safety number: the closest two same-side
    penetrations come anywhere in the design. It necessarily falls on the
    concave side of the tightest curve, because that is the boundary the
    boundary-paced pitch under-serves.
    """
    per_object = []
    for obj, stitches in _object_slices(design):
        kind = obj.stitch_type.value if hasattr(obj.stitch_type, "value") else str(obj.stitch_type)
        if kind != "SATIN":
            continue
        gaps = same_side_spacings(stitches)
        if not gaps:
            continue
        gaps.sort()
        per_object.append({
            "object": obj.sequence_order,
            "name": obj.name,
            "penetrations": len(gaps),
            "min_mm": round(gaps[0], 3),
            "p05_mm": round(gaps[max(0, len(gaps) // 20)], 3),
            "median_mm": round(gaps[len(gaps) // 2], 3),
            "below_floor": sum(1 for g in gaps if g < floor_mm),
        })
    if not per_object:
        return {"satin_objects": 0}
    tightest = min(per_object, key=lambda r: r["min_mm"])
    total = sum(r["penetrations"] for r in per_object)
    below = sum(r["below_floor"] for r in per_object)
    return {
        "satin_objects": len(per_object),
        "penetrations": total,
        "nominal_pitch_mm": pitch_mm,
        "floor_mm": floor_mm,
        "min_spacing_mm": tightest["min_mm"],
        "min_spacing_object": tightest["name"],
        "below_floor": below,
        "below_floor_share": round(below / total, 4) if total else 0.0,
        "per_object": per_object,
    }


def _object_slices(design):
    """Pair each object with its own slice of the stitch stream.

    Objects are emitted contiguously in sequence order and ``stitch_count``
    covers exactly that object's entries; COLOR_CHANGE markers sit between
    objects and belong to none of them, and END closes the stream.
    """
    stitches = list(design.stitches)
    i = 0
    for obj in sorted(design.objects, key=lambda o: o.sequence_order):
        while i < len(stitches) and _cmd(stitches[i]) in ("COLOR_CHANGE", "END"):
            i += 1
        yield obj, stitches[i:i + obj.stitch_count]
        i += obj.stitch_count


# ── Coverage: interior / edge band / spill ───────────────────────────────────


def _rasterise(design):
    """(outline_mask, thread_mask) at ``PX_PER_MM``, in a canvas sized to the real extents.

    Design coordinates live in HOOP space, not a 0-based box — fixture 05 runs to
    x=111.9mm on a 106.2mm-wide design — so the canvas is sized from the extents
    rather than from ``width_mm``/``height_mm``.
    """
    import cv2
    import numpy as np

    xs = [p.x for o in design.objects for p in (o.contour or [])] + [s.x for s in design.stitches]
    ys = [p.y for o in design.objects for p in (o.contour or [])] + [s.y for s in design.stitches]
    if not xs:
        return None, None
    w, h = int(max(xs) * PX_PER_MM) + 20, int(max(ys) * PX_PER_MM) + 20

    outline = np.zeros((h, w), np.uint8)
    for o in design.objects:
        if not o.contour:
            continue
        # Each object is rasterised on its OWN canvas before being OR-ed in.
        # Punching holes straight into the union would let one object's counter
        # erase another object's fill — concentric rings sit exactly like that.
        one = np.zeros((h, w), np.uint8)
        cv2.fillPoly(one, [_poly(o.contour)], 255)
        for hole in (o.holes or []):
            cv2.fillPoly(one, [_poly(hole)], 0)
        outline = cv2.bitwise_or(outline, one)

    thread = np.zeros((h, w), np.uint8)
    width_px = max(1, round(THREAD_WIDTH_MM * PX_PER_MM))
    prev = None
    for s in design.stitches:
        here = (int(s.x * PX_PER_MM), int(s.y * PX_PER_MM))
        if _cmd(s) == "STITCH" and prev is not None:
            cv2.line(thread, prev, here, 255, width_px)
        prev = here if _cmd(s) in ("STITCH", "JUMP") else None
    return outline, thread


def _poly(points):
    import numpy as np

    # TRUNCATION, not rounding, and deliberately so. Rounding is the more correct
    # rasterisation, but every audit number since Part 2.5 was produced with
    # truncation; switching moved fixture 07's spill 5.0 -> 5.1, which would make
    # this script disagree with the history it exists to make reproducible.
    return np.array([[int(p.x * PX_PER_MM), int(p.y * PX_PER_MM)] for p in points], np.int32)


def coverage_metrics(design) -> dict:
    """Interior / edge-band / spill coverage, in percent."""
    import cv2

    outline, thread = _rasterise(design)
    if outline is None:
        return {}
    k = max(1, round(EROSION_MM * PX_PER_MM))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
    interior = cv2.erode(outline, kernel)
    band = cv2.subtract(outline, interior)
    total = max(cv2.countNonZero(outline), 1)
    frac = cv2.countNonZero(interior) / total

    def covered(mask):
        return cv2.countNonZero(cv2.bitwise_and(thread, mask)) / max(cv2.countNonZero(mask), 1) * 100.0

    spill = cv2.countNonZero(cv2.bitwise_and(thread, cv2.bitwise_not(outline)))
    return {
        # A shape thinner than 2x the erosion has no interior — it is edge band all
        # the way through. Reporting 0% there would read as a coverage failure.
        "interior_pct": round(covered(interior), 1) if frac >= MIN_INTERIOR_FRAC else None,
        "edge_band_pct": round(covered(band), 1),
        "spill_pct": round(spill / max(cv2.countNonZero(thread), 1) * 100.0, 1),
        "interior_frac": round(frac, 3),
    }


def measure(design, pitch_mm: float, floor_mm: float) -> dict:
    """Every metric in this module for one design."""
    return {"coverage": coverage_metrics(design), "penetration": penetration_metrics(design, pitch_mm, floor_mm)}


# ── CLI ──────────────────────────────────────────────────────────────────────


def _parse_args():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", help="measure only this fixture stem")
    ap.add_argument("--probe", action="store_true",
                    help="measure the curvature probe instead of the bench corpus")
    ap.add_argument("--floor-mm", type=float, default=None,
                    help="enforce this same-side penetration floor (default: report only)")
    ap.add_argument("--json", type=Path, help="write the full result here")
    return ap.parse_args()


def _print_row(name: str, res: dict) -> None:
    cov, pen = res["coverage"], res["penetration"]
    interior = "—" if cov.get("interior_pct") is None else f"{cov['interior_pct']:.1f}"
    pen_min = f"{pen['min_spacing_mm']:.3f}" if pen.get("satin_objects") else "—"
    below = str(pen.get("below_floor", "—")) if pen.get("satin_objects") else "—"
    print(f"{name:28} {interior:>9} {cov['edge_band_pct']:>10.1f} "
          f"{cov['spill_pct']:>7.1f} {pen_min:>9} {below:>7}")


def _print_detail(results: dict, per_object: bool) -> None:
    """Per-object rows (when targeting), then the single tightest penetration seen."""
    if per_object:
        for name, res in results.items():
            for row in res["penetration"].get("per_object", []):
                print(f"    {name} · {row['name']:<28} min={row['min_mm']:.3f}mm  "
                      f"p05={row['p05_mm']:.3f}  median={row['median_mm']:.3f}  "
                      f"below floor {row['below_floor']}/{row['penetrations']}")
    tight = [(n, r) for n, r in results.items() if r["penetration"].get("satin_objects")]
    if not tight:
        return
    name, res = min(tight, key=lambda kv: kv[1]["penetration"]["min_spacing_mm"])
    pen = res["penetration"]
    print(f"\ntightest same-side penetration in this run: {pen['min_spacing_mm']:.3f}mm "
          f"on {name} / {pen['min_spacing_object']} "
          f"(nominal pitch {pen['nominal_pitch_mm']}mm, floor {pen['floor_mm']}mm)")


def _main() -> int:
    import cv2
    from run_quality_bench import DEFAULT_PARAMS, FIXTURE_DIR, FIXTURE_PARAMS, RNG_SEED

    from app.services.digitizer import (
        MIN_PENETRATION_MM,
        SATIN_SPACING_MM,
        digitize_image,
        set_penetration_floor,
    )

    args = _parse_args()
    set_penetration_floor(args.floor_mm)
    floor_report = MIN_PENETRATION_MM if args.floor_mm is None else args.floor_mm

    results = {}
    src = PROBE_DIR if args.probe else FIXTURE_DIR
    paths = sorted(src.glob("*.png"))
    if args.fixture:
        paths = [p for p in paths if p.stem == args.fixture]
        if not paths:
            print(f"no fixture named {args.fixture!r}", file=sys.stderr)
            return 2

    hdr = f"{'fixture':28} {'interior':>9} {'edge band':>10} {'spill':>7} {'min pen.':>9} {'<floor':>7}"
    print(hdr)
    print("-" * len(hdr))
    for path in paths:
        params = FIXTURE_PARAMS.get(path.stem, DEFAULT_PARAMS)
        cv2.setRNGSeed(RNG_SEED)
        design = digitize_image(
            path.read_bytes(),
            fabric_type=params["fabric"],
            hoop_size=params["hoop"],
            max_colors=params["colors"],
            text_mode=bool(params.get("text", False)),
        )
        results[path.stem] = measure(design, SATIN_SPACING_MM, floor_report)
        _print_row(path.stem, results[path.stem])

    _print_detail(results, per_object=bool(args.probe or args.fixture))
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
