"""What share of the artwork the pipeline believes it sewed (DET2's instrument).

`uncovered_px` is the number the photographic-texture rescue fires on, and it is
the only automatic check that a region of artwork was left bare. SH2 measured
fixture 03 losing 11.96 % of its foreground to nobody while this same number
read 0.00 %, so the gate that exists to catch wholesale loss could not see it.
That gap is what this script measures, before and after.

It reports the pipeline's OWN figure — read from `pipeline._LAST_UNCOVERED_PX`,
not recomputed here — because a second implementation of the metric would only
prove that two of my functions agree. Alongside it: object and stitch counts and
the emitted warnings, since `emitted_mask` also feeds the dropped-detail warning
and a change to one must be reported together with its effect on the other.

    scripts/coverage_audit.py                      # table to stdout
    scripts/coverage_audit.py --json before.json   # and a machine-readable copy
    scripts/coverage_audit.py --compare before.json

Fourteen fixtures, not ten: the ten bench fixtures plus the four corpus100
images SH2 measured on, kept identical so its table and this one are comparable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for _p in (BACKEND, BACKEND / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# IMPORTED, not retyped — same reasoning visual_regression.py records. A
# coverage figure is only comparable against the bench numbers if it was
# produced at the bench configuration, and two hand-maintained copies drift.
from run_quality_bench import FIXTURE_PARAMS, RNG_SEED

BENCH_DIR = BACKEND / "tests" / "fixtures" / "quality_bench"
CORPUS_DIR = BACKEND / "tests" / "fixtures" / "corpus100"

# The four parametric corpus images SH2 measured. Named here rather than
# selected by pattern so the set cannot silently grow when the corpus is
# rebuilt — "0 of 14 fixtures cross 0.19" is only checkable against a fixed 14.
CORPUS_EXTRA = ("C24_many_colours", "C11_many_colours",
                "C05_gradient_field", "C18_gradient_field")
# SH2's configuration for those four, NOT run_corpus100.py's. The corpus runner
# uses max_colors=12; SH2 ran them at 4, alongside the bench fixtures. The
# difference is not cosmetic — C24 reads 12.53 % uncovered at 4 colours and
# 1.05 % at 12, so taking the corpus runner's setting here would have silently
# replaced SH2's baseline with a different measurement under the same name.
# Verified by reproducing 12.53 % and 2.66 % exactly before pinning it.
CORPUS_PARAMS = {"colors": 4, "hoop": "130x180", "fabric": "cotton"}


def fixtures() -> list[tuple[str, Path, dict]]:
    rows = [(n, BENCH_DIR / f"{n}.png", p) for n, p in sorted(FIXTURE_PARAMS.items())]
    rows += [(n, CORPUS_DIR / f"{n}.png", CORPUS_PARAMS) for n in CORPUS_EXTRA]
    return rows


def measure_one(name: str, path: Path, params: dict) -> dict:
    import cv2

    from app.services.digitizer import digitize_image, pipeline

    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        path.read_bytes(),
        fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    return {
        "fixture": name,
        "conditions": f"{params.get('fabric', 'cotton')} @ {params['hoop']}",
        "max_colors": params["colors"],
        # The pipeline's own figure, for the pipeline's own gate.
        "uncovered_px": round(float(pipeline._LAST_UNCOVERED_PX), 4),
        "objects": len(design.objects),
        "stitches": int(design.stitch_count),
        "color_stops": len(design.color_stops),
        "warnings": list(design.warnings or []),
    }


def run() -> list[dict]:
    out = []
    for name, path, params in fixtures():
        if not path.exists():
            raise SystemExit(f"missing fixture {path}")
        row = measure_one(name, path, params)
        out.append(row)
        print(f"  {row['fixture']:26s} uncovered {row['uncovered_px']:7.2%}   "
              f"{row['objects']:4d} obj  {row['stitches']:6d} st  "
              f"[{row['conditions']}]")
    return out


def compare(before: list[dict], after: list[dict]) -> None:
    idx = {r["fixture"]: r for r in before}
    print(f"\n{'fixture':26s} {'before':>9s} {'after':>9s} {'delta':>9s}   objects   stitches")
    for a in after:
        b = idx.get(a["fixture"])
        if b is None:
            print(f"  {a['fixture']:24s} {'—':>9s} {a['uncovered_px']:8.2%}")
            continue
        d = a["uncovered_px"] - b["uncovered_px"]
        print(f"  {a['fixture']:24s} {b['uncovered_px']:8.2%} {a['uncovered_px']:8.2%} "
              f"{d:+8.2%}   {b['objects']:4d}->{a['objects']:<4d} "
              f"{b['stitches']:6d}->{a['stitches']:<6d}")
        if b["warnings"] != a["warnings"]:
            for w in a["warnings"]:
                if w not in b["warnings"]:
                    print(f"      + warning: {w}")
            for w in b["warnings"]:
                if w not in a["warnings"]:
                    print(f"      - warning: {w}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", metavar="PATH", help="write the measured rows here")
    ap.add_argument("--compare", metavar="PATH", help="diff against a previous --json")
    args = ap.parse_args()

    rows = run()
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2) + "\n")
        print(f"\nwrote {args.json}")
    if args.compare:
        compare(json.loads(Path(args.compare).read_text()), rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
