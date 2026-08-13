"""The R005 gate run, on the population that can judge it (v2 Part 56).

Part 55 set seven gates for any fragmentation change and named the population:
the three tier-A photographs, not the ten flat-art fixtures, because the fixtures
hold 93 objects between them against 336-834 for a single photograph.

This runs the four gates that need a digitize -- object count, interior coverage,
stitch count, trim count -- before and after a candidate change. Coverage is the
one that matters most: it is the anti-cheat. Deleting content lowers the object
count and the coverage together, and only a real fix moves one without the other.

    scripts/measure_r005_gates.py                    # current tree
    git stash && scripts/measure_r005_gates.py       # baseline, then compare

Part 56's own result is recorded in `docs/benchmarks/v2-part56-audit.md`: a
majority-vote smoother on the label map, at the smallest radius that exists,
failed gates 1, 2 and 3 and was reverted.
"""

from __future__ import annotations

import json
import statistics as st
import sys
import time
from pathlib import Path

import cv2

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from measure_stitch_quality import measure

from app.services.digitizer import MIN_PENETRATION_MM, ROW_SPACING_MM, digitize_image

CORPUS = BACKEND / "tests/fixtures/corpus100"
# The population Part 55 identified. Flat art is a safety check, not a target.
CASES = (("A01_real_peacock_patch_photo", "360x350"),
         ("A02_real_neckline_black", "360x350"),
         ("A03_real_neckline_panel", "360x350"))
RNG_SEED = 20260728


def run_one(name: str, hoop: str, max_colors: int = 12) -> dict:
    cv2.setRNGSeed(RNG_SEED)
    t0 = time.perf_counter()
    design = digitize_image((CORPUS / f"{name}.png").read_bytes(), "cotton", hoop,
                            max_colors)
    seconds = time.perf_counter() - t0
    objs = [o for o in design.objects if o.contour]
    counts = [o.stream_span for o in objs] or [0]
    trims = sum(1 for s in design.stitches
                if str(getattr(s, "command", "")).upper() == "TRIM")
    m = measure(design, MIN_PENETRATION_MM, ROW_SPACING_MM)
    return {
        "objects": len(objs),
        "median_stitches": st.median(counts),
        "tiny": sum(1 for v in counts if v <= 25),
        "stitches": len(design.stitches),
        "trims": trims,
        "interior": round(m["coverage"].get("interior_pct") or -1.0, 2),
        "edge_band": round(m["coverage"].get("edge_band_pct") or -1.0, 2),
        "seconds": round(seconds, 1),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--colors", type=int, nargs="+", default=[12],
                    help="max_colors settings to sweep (Part 57)")
    args = ap.parse_args()
    out = {}
    print(f"{'design':30s} {'k':>3s} {'obj':>6s} {'med':>5s} {'tiny%':>6s} {'stitch':>7s} "
          f"{'trim':>5s} {'interior':>9s} {'edge':>6s} {'s':>6s}")
    for name, hoop in CASES:
        for k in args.colors:
            r = run_one(name, hoop, k)
            out[f"{name}@{k}"] = dict(r, design=name, colors=k)
            pct = 100.0 * r["tiny"] / max(r["objects"], 1)
            print(f"{name:30s} {k:3d} {r['objects']:6d} {r['median_stitches']:5.0f} "
                  f"{pct:5.0f}% {r['stitches']:7d} {r['trims']:5d} {r['interior']:9.2f} "
                  f"{r['edge_band']:6.2f} {r['seconds']:6.1f}", flush=True)
    print("\n" + json.dumps(out))
    print("\nGates 1-4 need a baseline to compare against; gates 5-7 (flat-art "
          "baselines,\ncorpus health, noise runtime) are separate runs. Part 55 "
          "§5 has the full list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
