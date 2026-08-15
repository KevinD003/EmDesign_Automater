"""Digitize -> rebuild round trip, per object, UNBANDED (CTO ruling 2026-08-23, P1).

Watch item 2 of the A01/A02 promotion said the one-penetration-per-run-object
rebuild defect (fixed `ce254a8`) WOULD now be noticed, because A01 emits 36
`RUNNING_SINGLE` objects. The ruling's answer was that "would" is not "is": that
defect is still pinned only by constructed objects, and a real fixture has to
hold it. This is the instrument that puts a real fixture through the path.

    scripts/measure_rebuild_fidelity.py                    # A01, the promotion's case
    scripts/measure_rebuild_fidelity.py --all              # the whole standing set
    scripts/measure_rebuild_fidelity.py --fixture C24_many_colours --json out.json

NO BAND IS DERIVED HERE, DELIBERATELY. `FIDELITY_BANDS` in
`tests/test_probes_three_paths.py` covers four bench fixtures and every one of
its numbers was fitted on flat vector artwork; the fixture-set enumeration of
2026-08-21 recorded in advance that "the rebuild round trip has never been
measured on a photograph, so the promotion's first fidelity numbers on A01/A02
will be UNBANDED OBSERVATIONS". This reports the observation. Turning it into a
band is a separate decision that needs more than one photograph, and a band
fitted to the first photograph anyone measured would be the move this repository
keeps punishing.

CONDITIONS COME FROM THE AUDIT TABLE, not from the probe. The probe hard-codes
`"cotton", "100x100"` for its four bench fixtures; A01's conditions are its own
(`coverage_audit.A_TIER_PARAMS`), and running it at the probe's numbers would
report a fidelity figure under conditions no other A01 number was measured at.

`force=True` disables the rebuild pass-through, so this measures REGENERATION
rather than the stored stream being handed back — the same choice P6 makes, and
the reason its identity assertion was replaced by a parity number.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for _p in (BACKEND, BACKEND / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _provenance import code_provenance, describe, toolchain
from coverage_audit import fixtures as _audit_fixtures
from run_quality_bench import RNG_SEED


def _kind(o) -> str:
    return str(getattr(o.stitch_type, "value", o.stitch_type))


def measure_one(name: str, path: Path, params: dict) -> dict:
    import cv2

    from app.services.digitizer import digitize_image
    from app.services.digitizer.rebuild import rebuild_design

    cv2.setRNGSeed(RNG_SEED)
    dig = digitize_image(
        path.read_bytes(),
        fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    reb = rebuild_design(dig.model_copy(deep=True), force=True)

    a = {o.sequence_order: (int(o.penetration_count or 0), _kind(o)) for o in dig.objects}
    b = {o.sequence_order: (int(o.penetration_count or 0), _kind(o)) for o in reb.objects}
    common = sorted(set(a) & set(b))

    per_object = []
    for k in common:
        pa, ka = a[k]
        pb, kb = b[k]
        per_object.append({
            "sequence_order": k, "type_digitize": ka, "type_rebuild": kb,
            "pen_digitize": pa, "pen_rebuild": pb,
            "delta": pb - pa,
            "loss_share": None if pa == 0 else round(pb / pa - 1.0, 6),
        })

    def _slice(rows: list[dict], label: str) -> dict:
        losses = [r["loss_share"] for r in rows if r["loss_share"] is not None]
        deltas = [r["delta"] for r in rows]
        return {
            "group": label,
            "objects": len(rows),
            "delta_minus_one_exactly": sum(1 for d in deltas if d == -1),
            "delta_zero": sum(1 for d in deltas if d == 0),
            "penetrations_digitize": sum(r["pen_digitize"] for r in rows),
            "penetrations_rebuild": sum(r["pen_rebuild"] for r in rows),
            "worst_loss_share": round(min(losses), 6) if losses else None,
            "median_loss_share": round(statistics.median(losses), 6) if losses else None,
        }

    runs = [r for r in per_object if r["type_digitize"] == "RUNNING_SINGLE"]
    return {
        "fixture": name,
        "conditions": f"{params.get('fabric', 'cotton')} @ {params['hoop']}",
        "max_colors": params["colors"],
        "banded": False,
        "stream_digitize": len(dig.stitches),
        "stream_rebuild": len(reb.stitches),
        "stream_ratio": round(len(reb.stitches) / max(1, len(dig.stitches)), 6),
        "objects_digitize": len(dig.objects),
        "objects_rebuild": len(reb.objects),
        # An object set that changes is not a loss measurement at all — the
        # probe asserts equality before it looks at any percentage, and a
        # difference here invalidates every row below rather than widening it.
        "objects_only_in_digitize": sorted(set(a) - set(b)),
        "objects_only_in_rebuild": sorted(set(b) - set(a)),
        "type_changed": [r["sequence_order"] for r in per_object
                         if r["type_digitize"] != r["type_rebuild"]],
        "groups": [_slice(per_object, "all"), _slice(runs, "RUNNING_SINGLE")],
        "per_object": per_object,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fixture", action="append",
                    help="fixture name; repeatable. Default: A01_real_peacock_patch_photo")
    ap.add_argument("--all", action="store_true", help="the whole standing set")
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args()

    table = _audit_fixtures()
    if args.all:
        chosen = table
    else:
        want = args.fixture or ["A01_real_peacock_patch_photo"]
        known = {n for n, _p, _q in table}
        for w in want:
            if w not in known:
                raise SystemExit(f"unknown fixture {w!r}. Known: {', '.join(sorted(known))}")
        chosen = [row for row in table if row[0] in set(want)]

    docs = []
    for name, path, params in chosen:
        if not path.exists():
            raise SystemExit(f"missing fixture {path}")
        d = measure_one(name, path, params)
        docs.append(d)
        print(f"\n{d['fixture']}  [{d['conditions']}, {d['max_colors']} colours]  "
              f"UNBANDED OBSERVATION")
        print(f"  stream   {d['stream_digitize']:,} -> {d['stream_rebuild']:,}  "
              f"ratio {d['stream_ratio']:.4f}")
        print(f"  objects  {d['objects_digitize']} -> {d['objects_rebuild']}"
              f"{'' if not d['objects_only_in_digitize'] and not d['objects_only_in_rebuild'] else '  SET CHANGED'}")
        if d["type_changed"]:
            print(f"  TYPE CHANGED on {len(d['type_changed'])} objects: {d['type_changed'][:8]}")
        for g in d["groups"]:
            if not g["objects"]:
                continue
            print(f"  {g['group']:15s} {g['objects']:4d} obj  "
                  f"{g['penetrations_digitize']:6d} -> {g['penetrations_rebuild']:6d} pen  "
                  f"exactly -1: {g['delta_minus_one_exactly']:3d}  unchanged: {g['delta_zero']:4d}  "
                  f"worst {g['worst_loss_share']}")

    doc = {
        "produced_by": "scripts/measure_rebuild_fidelity.py",
        "code": code_provenance(),
        "toolchain": toolchain(),
        "rng_seed": RNG_SEED,
        "banded": False,
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
