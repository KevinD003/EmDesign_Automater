"""Why a region was classified SATIN or TATAMI, and whether the width it was
judged on is the width it actually has.

    scripts/measure_classification_width.py                    # every bench fixture
    scripts/measure_classification_width.py --only 07_circular_badge
    scripts/measure_classification_width.py --only 07_circular_badge --seq 3

Written for the CTO's 2026-08-10 classification question and kept because the
finding generalises: `median_w` is `np.median` over axis SAMPLES, so it weights
each unit of AXIS LENGTH equally rather than each unit of the shape. Anything
that multiplies axis length in one part of a region — lettering knocked out of a
band, a row of holes, a comb of spurs — gives that part extra votes and can move
the classification verdict without the shape being anything like that width.

Badge Satin 3 is the worked example: a ring band 6.98mm wide, 96.7% of its
circumference over the 4.5mm satin cap, judged at 3.62mm and sewn as satin. The
concentric ring beside it with no lettering reads 5.26mm against a true 5.51mm
and is correctly rejected — same design, same raster, same shape family, so the
difference isolates to the text.

What to look at in the output:

  bimodal=YES         two width populations, and the median is reporting one of
                      them while the other is most of the area. No scalar is
                      honest about a shape like this; see
                      docs/CTO-CLASSIFICATION-MECHANISM.md before "fixing" it by
                      moving a threshold.
  axis-density skew   samples per degree far from uniform means fragmentation is
                      doing the voting.
  true vs judged      measured off the region, no axis involved. If these
                      disagree the classifier is not looking at this shape.

The `true width` column is only meaningful for ROUGHLY ANNULAR regions — it is a
radial extent per angular sector. Non-ring shapes print it as `-`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND / "scripts"))

import cv2
import numpy as np

# IMPORTED, not retyped: a width number is only comparable with the rest of this
# series if it was produced at the same configuration.
from run_quality_bench import FIXTURE_PARAMS, RNG_SEED

from app.services.digitizer import digitize_image
from app.services.digitizer.constants import SATIN_MAX_W_MM

FIXTURE_DIR = BACKEND / "tests" / "fixtures" / "quality_bench"

# A region is called ring-like when its foreground leaves a hole around the
# centroid — enough for the radial width measure below to mean something.
RING_MIN_INNER_FRAC = 0.25


def _annular_width(region, mm_per_px: float, bins: int = 360):
    """Band width per angular sector, measured off the region alone.

    Returns (widths_mm, arc_lengths_mm) or None when the shape is not ring-like.
    Deliberately independent of the medial axis: this is the number the axis
    statistic gets checked against, so it must not share its machinery.
    """
    ys, xs = np.nonzero(region)
    if len(ys) < 50:
        return None
    cx, cy = xs.mean(), ys.mean()
    r = np.hypot(xs - cx, ys - cy)
    if r.min() < RING_MIN_INNER_FRAC * r.max():
        return None  # solid through the middle — not a band

    ang = np.arctan2(ys - cy, xs - cx)
    b = np.clip(((ang + np.pi) / (2 * np.pi) * bins).astype(int), 0, bins - 1)
    widths, arcs = [], []
    for k in range(bins):
        sel = r[b == k]
        if len(sel) < 8:
            continue
        lo, hi = np.percentile(sel, 1), np.percentile(sel, 99)
        widths.append((hi - lo) * mm_per_px)
        arcs.append(((lo + hi) / 2.0) * mm_per_px * (2 * np.pi / bins))
    if len(widths) < bins // 4:
        return None
    return np.asarray(widths), np.asarray(arcs)


def _bimodal(w: np.ndarray) -> tuple[bool, float]:
    """Is the width distribution two populations rather than one?

    Cheap and explicit rather than a mixture fit: split at the value that
    maximises between-class variance (Otsu on a 1-D histogram), then require
    both classes to be substantial and their means well separated. A stroke of
    roughly constant width fails this; a band with text knocked out passes.
    """
    if len(w) < 40:
        return False, 0.0
    lo, hi = float(w.min()), float(w.max())
    if hi - lo < 1.0:
        return False, 0.0
    best_t, best_v = lo, -1.0
    for t in np.linspace(lo, hi, 64)[1:-1]:
        a, b = w[w <= t], w[w > t]
        if len(a) < 0.15 * len(w) or len(b) < 0.15 * len(w):
            continue
        v = len(a) * len(b) * (a.mean() - b.mean()) ** 2
        if v > best_v:
            best_v, best_t = v, float(t)
    if best_v < 0:
        return False, 0.0
    a, b = w[w <= best_t], w[w > best_t]
    # Separated by more than the spread within each side.
    sep = (b.mean() - a.mean()) / max(a.std() + b.std(), 1e-6)
    return sep > 1.5, best_t


def measure(fixture: str, want_seq: int | None = None) -> list[dict]:
    """Digitize one fixture, capturing every classification decision."""
    from app.services.digitizer import columns, generation, pipeline, satin

    calls: list[dict] = []
    pending: dict = {}

    orig_samples = columns._axis_samples

    def sample_spy(branches, dist, binary, step, mm_per_px):
        used, widths, centres = orig_samples(branches, dist, binary, step, mm_per_px)
        pending["widths"] = list(widths)
        pending["centres"] = list(centres)
        pending["branches"] = len(branches)
        return used, widths, centres

    orig_spine = generation.spine_satin

    def spine_spy(region, **kw):
        pending.clear()
        attempt = orig_spine(region, **kw)
        mm_per_px = kw["mm_per_px"]
        rec = {
            "area_mm2": cv2.countNonZero(region) * mm_per_px * mm_per_px,
            "judged_w": attempt.median_w_mm,
            "uncovered": attempt.uncovered_share,
            "reason": attempt.reason,
            "decision": "SATIN" if attempt.viable else "TATAMI",
            "branches": pending.get("branches", 0),
            "widths": np.asarray(pending.get("widths", []), dtype=float),
            "centres": np.asarray(pending.get("centres", []), dtype=float).reshape(-1, 2),
            "region": region.copy(),
            "mm_per_px": mm_per_px,
        }
        calls.append(rec)
        return attempt

    columns._axis_samples = sample_spy
    satin._axis_samples = sample_spy
    generation.spine_satin = spine_spy
    pipeline.spine_satin = spine_spy
    try:
        params = FIXTURE_PARAMS[fixture]
        cv2.setRNGSeed(RNG_SEED)
        digitize_image(
            (FIXTURE_DIR / f"{fixture}.png").read_bytes(),
            fabric_type=params.get("fabric", "cotton"),
            hoop_size=params["hoop"],
            max_colors=params["colors"],
            text_mode=params.get("text", False),
        )
    finally:
        columns._axis_samples = orig_samples
        satin._axis_samples = orig_samples
        generation.spine_satin = orig_spine
        pipeline.spine_satin = orig_spine

    out = []
    for i, rec in enumerate(calls, start=1):
        if want_seq is not None and i != want_seq:
            continue
        w = rec["widths"]
        row = {k: rec[k] for k in ("area_mm2", "judged_w", "uncovered", "reason",
                                   "decision", "branches")}
        row["seq"] = i
        row["samples"] = len(w)
        row["bimodal"], row["split_mm"] = _bimodal(w) if len(w) else (False, 0.0)
        # Area-weighted mean: each sample stands for width x step of the shape.
        row["area_w"] = float((w * w).sum() / w.sum()) if len(w) and w.sum() else 0.0
        ring = _annular_width(rec["region"], rec["mm_per_px"])
        if ring is None:
            row["true_w"] = None
            row["over_cap"] = None
        else:
            tw, _arc = ring
            row["true_w"] = float(np.median(tw))
            row["over_cap"] = float((tw > SATIN_MAX_W_MM).mean())
        out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="single fixture name")
    ap.add_argument("--seq", type=int, help="single object, 1-based in call order")
    ap.add_argument("--min-area", type=float, default=50.0,
                    help="skip regions under this area in mm2 (default 50)")
    args = ap.parse_args()

    names = [args.only] if args.only else sorted(FIXTURE_PARAMS)
    print(f"satin width cap {SATIN_MAX_W_MM}mm\n")
    header = (f"{'fixture':26s} {'seq':>3s} {'area':>8s} {'judged':>7s} {'true':>7s} "
              f"{'areaW':>7s} {'over':>6s} {'smpl':>5s} {'brch':>5s} {'bimod':>6s}  decision")
    print(header)
    print("-" * len(header))

    suspects = []
    for name in names:
        for r in measure(name, args.seq):
            if r["area_mm2"] < args.min_area:
                continue
            true_s = f"{r['true_w']:7.2f}" if r["true_w"] is not None else f"{'-':>7s}"
            over_s = f"{r['over_cap']*100:5.0f}%" if r["over_cap"] is not None else f"{'-':>6s}"
            flag = "YES" if r["bimodal"] else "no"
            print(f"{name:26s} {r['seq']:3d} {r['area_mm2']:8.1f} {r['judged_w']:7.2f} {true_s} "
                  f"{r['area_w']:7.2f} {over_s} {r['samples']:5d} {r['branches']:5d} "
                  f"{flag:>6s}  {r['decision']}")
            # The failure this script exists to catch: called satin on a width
            # the shape does not have.
            if (r["decision"] == "SATIN" and r["true_w"] is not None
                    and r["true_w"] > SATIN_MAX_W_MM * 1.25):
                suspects.append((name, r))

    if suspects:
        print(f"\n{len(suspects)} object(s) sewn as SATIN whose measured band is over "
              f"{SATIN_MAX_W_MM * 1.25:.2f}mm:")
        for name, r in suspects:
            print(f"  {name} seq {r['seq']}: judged {r['judged_w']:.2f}mm, "
                  f"measured {r['true_w']:.2f}mm ({r['true_w']/max(r['judged_w'],1e-6):.1f}x), "
                  f"{r['over_cap']*100:.0f}% of the band over the cap, "
                  f"bimodal={'YES' if r['bimodal'] else 'no'}")
        print("\nSee docs/CTO-CLASSIFICATION-MECHANISM.md — moving a threshold is very "
              "probably the wrong response to this.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
