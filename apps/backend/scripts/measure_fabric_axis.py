"""The bench's missing axis: what changes when the FABRIC changes.

    python scripts/measure_fabric_axis.py
    python scripts/measure_fabric_axis.py --json docs/benchmarks/fabric-axis.json

WHY THIS EXISTS. All ten quality-bench fixtures are cotton, and cotton's
`pull_mm` is 0.20 near the bottom of a range that runs to 0.50 for fleece and
towel. So the bench cannot see ANY fabric-dependent behaviour: it understated
UP1 — satin receiving half the per-side pull compensation a fill receives — by
2.5x, and the physical-units contract (SZ1/SZ3/SZ4/UP2/UP3/UP4) is fabric
dependent end to end. Tuning that tranche against an all-cotton bench is tuning
blind, which is the whole reason this runs first.

WHAT IT IS NOT. Not a gate and not a baseline to re-pin. It is a SPREAD: the same
fixtures digitized across the fabric profiles, so a change to the physical-units
code can be read for what it does at 0.15mm pull and at 0.50mm pull rather than
only at 0.20. `tests/test_fabric_axis.py` asserts the axis actually
discriminates — an axis whose numbers do not move with the fabric would be
decorative, and worse than absent because it would look like coverage.

The default bench output is untouched: this is a separate sweep, so no committed
baseline moves.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cv2
import numpy as np
from measure_stitch_quality import _cmd
from run_quality_bench import FIXTURE_DIR, FIXTURE_PARAMS, RNG_SEED, SPM, TRIM_SECONDS

from app.services.digitizer import digitize_image
from app.services.digitizer.constants import FABRIC_PROFILES

# A SPREAD ACROSS THE PULL RANGE, not a list of every profile. These six span
# 0.15 to 0.50mm — the whole range the profiles define — so a fabric-dependent
# effect has to show up across them if it exists at all. Read from
# FABRIC_PROFILES rather than restated, so a profile change cannot leave this
# claiming a pull the engine no longer uses.
FABRICS = ["denim", "cotton", "cap", "knit", "jersey", "fleece"]

# One satin-dominated fixture, one tatami-dominated, one mixed. Pull compensation
# reaches satin columns and fills by DIFFERENT code paths — that asymmetry was
# UP1 — so an axis that sampled only one of them could miss the next such defect.
FIXTURES = ["05_wordmark_caps", "01_flat_2color_logo", "07_circular_badge"]


def _column_widths_mm(design) -> list[float]:
    """Step between consecutive penetrations, per colour block.

    In a satin column the path alternates across the stroke, so this step IS the
    sewn column width — the quantity pull compensation is supposed to move, and
    the one the cotton-only bench could not see moving. Chain breaks (trim, jump,
    colour change) are excluded so a travel move is never counted as a column.
    """
    out: list[float] = []
    prev = None
    for s in design.stitches:
        c = _cmd(s)
        if c != "STITCH":
            prev = None
            continue
        p = (float(s.x), float(s.y))
        if prev is not None:
            out.append(float(np.hypot(p[0] - prev[0], p[1] - prev[1])))
        prev = p
    return out


def _run(fixture: str, fabric: str) -> dict:
    params = FIXTURE_PARAMS[fixture]
    cv2.setRNGSeed(RNG_SEED)
    d = digitize_image(
        (FIXTURE_DIR / f"{fixture}.png").read_bytes(),
        fabric_type=fabric,
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=bool(params.get("text", False)),
    )
    steps = sorted(_column_widths_mm(d))
    trims = sum(1 for s in d.stitches if _cmd(s) == "TRIM")
    n = sum(1 for s in d.stitches if _cmd(s) == "STITCH")
    satin = sum(1 for o in d.objects if str(o.stitch_type) == "SATIN")
    prof = FABRIC_PROFILES.get(fabric, {})
    return {
        "fixture": fixture,
        "fabric": fabric,
        "pull_mm": prof.get("pull_mm"),
        "row_mm": prof.get("row_mm"),
        "satin_mm": prof.get("satin_mm"),
        "stitches": n,
        "objects": len(d.objects),
        "satin_objects": satin,
        "trims": trims,
        "machine_minutes": round(n / SPM + trims * TRIM_SECONDS / 60.0, 2),
        "p90_step_mm": round(steps[int(len(steps) * 0.9)], 4) if steps else 0.0,
        "median_step_mm": round(steps[len(steps) // 2], 4) if steps else 0.0,
    }


def sweep(fixtures=None, fabrics=None) -> list[dict]:
    return [_run(f, fab)
            for f in (fixtures or FIXTURES)
            for fab in (fabrics or FABRICS)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--only", help="a single fixture")
    args = ap.parse_args()

    rows = sweep([args.only] if args.only else None)
    hdr = (f"{'fixture':22s} {'fabric':9s} {'pull':>5s} {'row':>5s} {'satin':>6s} "
           f"{'stitch':>7s} {'satinO':>7s} {'trims':>6s} {'min':>6s} "
           f"{'p90step':>8s} {'medstep':>8s}")
    print(hdr)
    print("-" * len(hdr))
    last = None
    for r in rows:
        if last and r["fixture"] != last:
            print()
        last = r["fixture"]
        print(f"{r['fixture']:22s} {r['fabric']:9s} {r['pull_mm']:5.2f} "
              f"{r['row_mm']:5.2f} {r['satin_mm']:6.2f} {r['stitches']:7d} "
              f"{r['satin_objects']:7d} {r['trims']:6d} {r['machine_minutes']:6.2f} "
              f"{r['p90_step_mm']:8.4f} {r['median_step_mm']:8.4f}")

    print("\nspread per fixture (max - min across fabrics):")
    for f in sorted({r["fixture"] for r in rows}, key=lambda x: FIXTURES.index(x)
                    if x in FIXTURES else 99):
        sub = [r for r in rows if r["fixture"] == f]
        for key in ("stitches", "machine_minutes", "p90_step_mm"):
            vals = [r[key] for r in sub]
            print(f"  {f:22s} {key:16s} {min(vals):9.4f} .. {max(vals):9.4f}  "
                  f"spread {max(vals) - min(vals):.4f}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
