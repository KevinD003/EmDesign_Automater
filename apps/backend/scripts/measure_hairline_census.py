"""The refused-region census, as a script instead of a memory (RS1, re-measured).

`hairline_runs`' docstring shipped a MEASURED claim — "14 refused regions across
the fourteen fixtures, every one 0.20-0.23 mm wide" — taken once, by hand, in a
scratchpad that no longer exists. Two things then happened to it:

  * the single-branch boundary landed, which changed what "refused" MEANS (a
    region that runs is no longer refused; a multi-branch region now is);
  * the standing set went from fourteen to sixteen.

Neither event could touch the sentence, because there was no instrument to
re-run. The ruling of 2026-08-22 required the number re-MEASURED rather than
reworded, and this is the instrument that makes the next re-measure cheap.

    scripts/measure_hairline_census.py                 # table + summary
    scripts/measure_hairline_census.py --json out.json

Everything here is READ FROM THE PIPELINE — `_CLASSIFICATION_LOG` for the width
and the decision, `generation._LAST_HAIRLINE_BRANCHES` for the pruned branch
count. Nothing is recomputed: a second implementation of "how wide is this
region" would only prove that two of my functions agree.

WHAT A ROW MEANS. A region reaches this census when its median width is under
`MIN_FEATURE_W_MM` — too thin to hold a satin COLUMN. From there:

    pruned_branches == 0   nothing survived spur pruning     -> SKIPPED
    pruned_branches == 1   one clean centreline              -> RUN
    pruned_branches >  1   refused by the single-branch boundary -> SKIPPED

The middle case is the only one that sews. The third is the one a future noise
criterion would reopen, so it is counted separately rather than folded into a
single "refused" total — that fold is what made the old sentence unable to
survive the boundary that changed it.
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

from _provenance import code_provenance, describe, toolchain
from coverage_audit import fixtures as _audit_fixtures
from run_quality_bench import RNG_SEED


def measure_one(name: str, path: Path, params: dict) -> dict:
    import cv2

    from app.services.digitizer import digitize_image, pipeline
    from app.services.digitizer.generation import _LAST_HAIRLINE_BRANCHES

    cv2.setRNGSeed(RNG_SEED)
    digitize_image(
        path.read_bytes(),
        fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    rows = [r for r in pipeline._CLASSIFICATION_LOG
            if str(r.get("reason", "")).startswith("sub_thread")]
    # The two lists must line up or the census is describing two runs. They are
    # appended one-for-one at the same call site, so a mismatch is a defect in
    # this instrument and must stop it rather than be reported.
    if len(rows) != len(_LAST_HAIRLINE_BRANCHES):
        raise SystemExit(
            f"{name}: {len(rows)} sub-thread classification rows but "
            f"{len(_LAST_HAIRLINE_BRANCHES)} branch counts — the census would be "
            f"assembled from two different traversals. Refusing."
        )
    return {
        "fixture": name,
        "conditions": f"{params.get('fabric', 'cotton')} @ {params['hoop']}",
        "max_colors": params["colors"],
        "classified_regions": len(pipeline._CLASSIFICATION_LOG),
        "sub_thread_regions": len(rows),
        "regions": [
            {
                "seq": r["seq"],
                "width_mm": round(float(r["region_median_w_mm"]), 3),
                "decision": r["decision"],
                "pruned_branches": int(r.get("pruned_branches", 0)),
            }
            for r in rows
        ],
    }


def summarise(rows: list[dict]) -> dict:
    regions = [g for r in rows for g in r["regions"]]
    run = [g for g in regions if g["decision"] == "RUN"]
    no_branch = [g for g in regions if g["decision"] == "SKIPPED" and g["pruned_branches"] == 0]
    multi = [g for g in regions if g["decision"] == "SKIPPED" and g["pruned_branches"] > 1]
    widths = sorted(g["width_mm"] for g in regions)
    return {
        "fixtures": len(rows),
        "fixtures_with_any": sum(1 for r in rows if r["regions"]),
        "sub_thread_regions": len(regions),
        "run": len(run),
        "run_objects": sum(1 for g in run),  # one branch each, by the boundary
        "skipped_no_surviving_branch": len(no_branch),
        "skipped_multi_branch": len(multi),
        "width_min_mm": widths[0] if widths else None,
        "width_max_mm": widths[-1] if widths else None,
        "width_distribution_mm": widths,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args()

    rows = []
    for name, path, params in _audit_fixtures():
        if not path.exists():
            raise SystemExit(f"missing fixture {path}")
        row = measure_one(name, path, params)
        rows.append(row)
        detail = "  ".join(
            f"{g['width_mm']:.2f}mm/{g['pruned_branches']}br/{g['decision'][:3]}"
            for g in row["regions"]
        )
        print(f"  {row['fixture']:28s} {row['sub_thread_regions']:2d} sub-thread of "
              f"{row['classified_regions']:4d}   [{row['conditions']}]  {detail}")

    s = summarise(rows)
    print(f"\n{s['sub_thread_regions']} sub-thread regions across {s['fixtures']} fixtures "
          f"({s['fixtures_with_any']} contribute any)")
    print(f"  RUN                         {s['run']}")
    print(f"  SKIPPED, no branch survived {s['skipped_no_surviving_branch']}")
    print(f"  SKIPPED, multi-branch       {s['skipped_multi_branch']}")
    if s["width_min_mm"] is not None:
        print(f"  width {s['width_min_mm']:.2f}-{s['width_max_mm']:.2f} mm")
    doc = {
        "produced_by": "scripts/measure_hairline_census.py",
        "code": code_provenance(),
        "toolchain": toolchain(),
        "rng_seed": RNG_SEED,
        "fixture_set": [r["fixture"] for r in rows],
        "summary": s,
        "rows": rows,
    }
    print(f"\ntree: {describe(doc['code'])}   fixtures: {len(rows)}")
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
