"""SURFACE METRIC 1 across the standing set: does the sewn edge follow the contour?

    scripts/measure_surface.py                 # table
    scripts/measure_surface.py --json out.json
    scripts/measure_surface.py --objects 08_mascot_detail   # per-object detail

Reports OBSERVATIONS. No band, no pass condition, deliberately: this repository
has twice shipped a constant fitted to the corpus that named it, so the
distribution comes first and any later gate must be argued in thread widths as a
physical claim.

Numbers come from `constants._SURFACE_LOG`, written at generation against each
object's OWN stored contour — see `surface.py` for why a post-hoc capture cannot
work.
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

    from app.services.digitizer import digitize_image
    from app.services.digitizer.constants import _SURFACE_LOG
    from app.services.digitizer.surface import design_summary

    cv2.setRNGSeed(RNG_SEED)
    digitize_image(
        path.read_bytes(), fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"], max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    rows = [dict(r) for r in _SURFACE_LOG]
    return {
        "fixture": name,
        "conditions": f"{params.get('fabric', 'cotton')} @ {params['hoop']}",
        "summary": design_summary(rows),
        "objects": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--objects", metavar="FIXTURE", help="per-object rows for one fixture")
    args = ap.parse_args()

    docs = []
    print(f"  {'fixture':28s} {'objs':>4s} {'median':>9s} {'worst':>9s} "
          f"{'thr':>6s} {'max|d|':>8s}  worst object")
    for name, path, params in _audit_fixtures():
        if not path.exists():
            raise SystemExit(f"missing fixture {path}")
        d = measure_one(name, path, params)
        docs.append(d)
        s = d["summary"]
        if not s.get("objects_measured"):
            print(f"  {name:28s} {0:4d}         —         —      —        —  "
                  f"(no satin objects)")
            continue
        print(f"  {name:28s} {s['objects_measured']:4d} "
              f"{s['median_roughness_mm']:9.4f} {s['worst_roughness_mm']:9.4f} "
              f"{s['worst_roughness_threads']:6.2f} {s['max_abs_mm']:8.4f}  "
              f"seq {s['worst_object_seq']}")
        if args.objects == name:
            for r in sorted(d["objects"], key=lambda r: -(r["boundary"] or {}).get(
                    "roughness_mm", 0.0)):
                b = r["boundary"]
                if not b:
                    continue
                sa, sb = b["sides"].get("a", {}), b["sides"].get("b", {})
                print(f"      seq {r['seq']:4d}  cols {b['columns']:4d}  "
                      f"rough {b['roughness_mm']:7.4f}mm ({b['roughness_threads']:5.2f} thr)  "
                      f"offset a {sa.get('offset_p50_mm', 0):+7.4f} b "
                      f"{sb.get('offset_p50_mm', 0):+7.4f}  "
                      f"asym {b.get('offset_asymmetry_mm', 0):.4f}  "
                      f"max {b['max_abs_mm']:7.4f}")
    doc = {
        "produced_by": "scripts/measure_surface.py",
        "code": code_provenance(), "toolchain": toolchain(), "rng_seed": RNG_SEED,
        "fixture_set": [d["fixture"] for d in docs],
        "fixtures": docs,
    }
    print(f"\ntree: {describe(doc['code'])}   fixtures: {len(docs)}")
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
