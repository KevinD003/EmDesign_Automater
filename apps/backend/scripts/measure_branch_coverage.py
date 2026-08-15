"""Branch coverage of the standing set through digitize + rebuild.

Owed for three tranches after the A01/A02 promotion, and the reason it kept
slipping is that it looked like a one-liner and is not: the number is only
meaningful against a comparison, and the obvious comparison is wrong.

WHAT THIS MEASURES: the CORPUS driven through both paths, not the test suite. A
suite figure mixes in constructed tests and cannot answer "did promoting two
photographs reach code the other fourteen never did".

WHY IT TAKES A SUBSET FLAG. The pre-promotion figures (pipeline 90 %, rebuild
71 %, underlay 50 %, 2026-08-18) were measured on a DIFFERENT TREE. Everything
since — RS1, the accounting split, DET2, the substrate log, colordiff — changed
the denominators, so reading today's pipeline 88 % against that 90 % as a
promotion effect would be the C11 two-tree splice that `coverage_audit` now
refuses outright. The attributable comparison is fourteen against sixteen ON ONE
TREE, which is what `--exclude-a-tier` exists for.

    scripts/measure_branch_coverage.py                  # the sixteen
    scripts/measure_branch_coverage.py --exclude-a-tier # the fourteen, same tree

Run each under `coverage run --branch --source=app/services/digitizer` and diff
the two reports; the delta is the promotion's reach and nothing else's.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for _p in (BACKEND, BACKEND / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def main() -> int:
    import cv2
    from coverage_audit import A_TIER_PARAMS
    from coverage_audit import fixtures as _audit_fixtures
    from run_quality_bench import RNG_SEED

    from app.services.digitizer import digitize_image
    from app.services.digitizer.rebuild import rebuild_design

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exclude-a-tier", action="store_true",
                    help="the fourteen, for the same-tree comparison")
    args = ap.parse_args()

    for name, path, params in _audit_fixtures():
        if args.exclude_a_tier and name in A_TIER_PARAMS:
            continue
        cv2.setRNGSeed(RNG_SEED)
        design = digitize_image(
            path.read_bytes(), fabric_type=params.get("fabric", "cotton"),
            hoop_size=params["hoop"], max_colors=params["colors"],
            text_mode=params.get("text", False),
        )
        rebuild_design(design.model_copy(deep=True), force=True)
        print(f"  {name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
