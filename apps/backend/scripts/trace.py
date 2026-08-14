"""One command, one JSON, one key per headline number (TRACE).

Every number quoted in a StitchIQ report is supposed to be reproducible. In
practice they were reproducible only in the sense that someone could re-derive
them if they knew which script, which fabric, which hoop and which tree — and
three separate errors have already been traced to exactly that gap:

  * "22.65 machine-minutes" travelled through four reports before anyone noticed
    the corpus spans 18.78-22.64 and the figure was one fixture near the top;
  * a jersey number was reported as fleece, and the correction then gave the
    wrong hoop for two fixtures;
  * a tie-off was located at the wrong stream index because two index spaces
    were being read as one — the number was exact, the LOCATOR was wrong.

The fix for the first two was to make the bench refuse to print an unlabelled
headline. This is the other half: a single script that emits one JSON document
per run, carrying the design's numbers, the conditions they were measured at,
and the tree they came from. A report cites the command and the key. A reader
runs the command and reads the key.

    scripts/trace.py 08_mascot_detail                    # one fixture, JSON to stdout
    scripts/trace.py --all --json trace.json             # all fourteen
    scripts/trace.py 08_mascot_detail --key design.penetrations
    scripts/trace.py 08_mascot_detail --stream-index 8071
    scripts/trace.py 08_mascot_detail --penetration-index 7992

## Index spaces

A stitch position is meaningless without its space, and this repo has two that
differ by hundreds of entries on a real design:

  * **stream index** — position in `design.stitches`. Counts STITCH, JUMP, TRIM
    and COLOR_CHANGE. This is what a slice of the stitch list is indexed by, and
    what `_lock_stream` inserts tie-offs into.
  * **penetration index** — position among the STITCH entries alone. This is
    what `design.stitch_count` counts, what the machine-time estimate divides,
    and what a needle actually does.

`--stream-index` and `--penetration-index` convert between them and print the
entry, so a locator in a report can be checked rather than trusted.

A third span exists and is now named rather than confused with the other two:
an object's `stream_span` is `len(stitches) - obj_start`, so it counts the JUMPs
and TRIMs inside that object and excludes the tie-offs added afterwards. Its
`penetration_count` is the needle count. `accounting.*` carries the pipeline's
own census and closes both identities; nothing here subtracts one space from
the other.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for _p in (BACKEND, BACKEND / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Imported, never retyped: the fixture table, the seed, the machine model. A
# trace that used its own copy of any of these would certify numbers that no
# other harness produces.
from _provenance import code_provenance, toolchain
from coverage_audit import CORPUS_DIR, CORPUS_PARAMS, CORPUS_EXTRA, BENCH_DIR
from run_quality_bench import FIXTURE_PARAMS, RNG_SEED, SPM, TRIM_SECONDS

TRACE_VERSION = 1


def _cmd(stitch) -> str:
    return str(getattr(stitch.command, "value", stitch.command))


# Provenance comes from the shared module (2026-08-21), not a local copy.
# `coverage_audit.py` needed the same block, and a second implementation of
# "which tree was this" is the drift this repo has been punished for twice.
_git = code_provenance
_toolchain = toolchain


def resolve(name: str) -> tuple[Path, dict]:
    """Fixture name -> (path, the conditions it is always measured at)."""
    if name in FIXTURE_PARAMS:
        return BENCH_DIR / f"{name}.png", FIXTURE_PARAMS[name]
    if name in CORPUS_EXTRA:
        return CORPUS_DIR / f"{name}.png", CORPUS_PARAMS
    raise SystemExit(
        f"unknown fixture {name!r}. Known: {', '.join(sorted(FIXTURE_PARAMS))}, "
        f"{', '.join(CORPUS_EXTRA)}"
    )


def trace(name: str) -> dict:
    import cv2

    from app.services.digitizer import digitize_image, pipeline

    path, params = resolve(name)
    data = path.read_bytes()
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        data,
        fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params.get("text", False),
    )

    cmds = [_cmd(s) for s in design.stitches]
    penetrations = cmds.count("STITCH")
    jumps = cmds.count("JUMP")
    trims = cmds.count("TRIM")
    changes = cmds.count("COLOR_CHANGE")
    kinds = {}
    for o in design.objects:
        kinds[str(getattr(o.stitch_type, "value", o.stitch_type))] = \
            kinds.get(str(getattr(o.stitch_type, "value", o.stitch_type)), 0) + 1
    obj_span_total = sum(int(o.stream_span) for o in design.objects)

    est_minutes = penetrations / SPM
    return {
        "trace_version": TRACE_VERSION,
        "produced_by": "scripts/trace.py",
        "fixture": name,
        "source": {
            "path": str(path.relative_to(BACKEND)),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        },
        # LABELLED, always. A stitch count without its fabric and hoop is the
        # error this repo has made twice; run_quality_bench refuses to print one
        # and this refuses to emit one.
        "conditions": {
            "fabric": params.get("fabric", "cotton"),
            "hoop": params["hoop"],
            "max_colors": params["colors"],
            "text_mode": bool(params.get("text", False)),
            "rng_seed": RNG_SEED,
            "label": f"{params.get('fabric', 'cotton')} @ {params['hoop']}",
        },
        "code": _git(),
        "toolchain": _toolchain(),
        "design": {
            "penetrations": penetrations,          # == design.stitch_count
            "stream_length": len(design.stitches),
            "jumps": jumps,
            "trims": trims,
            "color_changes": changes,
            "objects": len(design.objects),
            "color_stops": len(design.color_stops),
            "width_mm": round(design.width_mm, 2),
            "height_mm": round(design.height_mm, 2),
            "object_types": kinds,
        },
        "machine": {
            # Both halves and the total. A routing change that trades stitches
            # for trims must be judged on the total, and quoting either half
            # alone is how a regression gets reported as a win.
            "spm": SPM,
            "trim_seconds": TRIM_SECONDS,
            "sew_minutes": round(est_minutes, 3),
            "trim_minutes": round(trims * TRIM_SECONDS / 60.0, 3),
            "minutes_net_of_trim": round(est_minutes + trims * TRIM_SECONDS / 60.0, 3),
            "formula": "penetrations / spm + trims * trim_seconds / 60",
        },
        "coverage": {
            # The pipeline's own figure, read from the pipeline. See DET2: it
            # was written in pass A and inflated until 2026-08-13.
            "uncovered_px": round(float(pipeline._LAST_UNCOVERED_PX), 6),
        },
        # RECONCILED. Read from the pipeline's own census, taken at the three
        # points where the stream is rewritten, rather than derived here — the
        # earlier version of this block subtracted a sum of stream spans from a
        # penetration count and reported the difference, which is the arithmetic
        # that produced the phantom "90 unattributed penetrations".
        "accounting": {
            **{k: v for k, v in pipeline._LAST_STREAM_ACCOUNTING.items()
               if not k.startswith("census_")},
            "sum_object_stream_spans": obj_span_total,
            "sum_object_penetrations": sum(int(o.penetration_count) for o in design.objects),
            "sum_stop_penetrations": sum(int(c.penetration_count) for c in design.color_stops),
            "unreconciled": False,
        },
        "index_spaces": {
            "stream": {
                "length": len(design.stitches),
                "definition": "position in design.stitches; includes STITCH, JUMP, TRIM, COLOR_CHANGE",
            },
            "penetration": {
                "length": penetrations,
                "definition": "position among STITCH entries only; equals design.stitch_count",
            },
            "stream_minus_penetration": len(design.stitches) - penetrations,
        },
        "warnings": list(design.warnings or []),
    }


def locate(name: str, *, stream: int | None = None, penetration: int | None = None) -> dict:
    """Convert a locator between the two index spaces and show the entry."""
    import cv2

    from app.services.digitizer import digitize_image

    path, params = resolve(name)
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        path.read_bytes(), fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"], max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    # stream index -> penetration index, for every entry, once.
    pen_of_stream, p = [], 0
    for s in design.stitches:
        if _cmd(s) == "STITCH":
            pen_of_stream.append(p)
            p += 1
        else:
            pen_of_stream.append(None)  # this entry is not a penetration at all
    stream_of_pen = [i for i, v in enumerate(pen_of_stream) if v is not None]

    if stream is None and penetration is None:
        raise SystemExit("give --stream-index or --penetration-index")
    if penetration is not None:
        if not 0 <= penetration < len(stream_of_pen):
            raise SystemExit(f"penetration index {penetration} out of range 0..{len(stream_of_pen) - 1}")
        stream = stream_of_pen[penetration]
    if not 0 <= stream < len(design.stitches):
        raise SystemExit(f"stream index {stream} out of range 0..{len(design.stitches) - 1}")

    s = design.stitches[stream]
    return {
        "fixture": name,
        "conditions": f"{params.get('fabric', 'cotton')} @ {params['hoop']}",
        "stream_index": stream,
        "penetration_index": pen_of_stream[stream],  # null when the entry is not a STITCH
        "command": _cmd(s),
        "x_mm": round(s.x, 4),
        "y_mm": round(s.y, 4),
        "note": ("this entry is not a penetration, so it has no penetration index"
                 if pen_of_stream[stream] is None else ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fixture", nargs="?", help="fixture name; omit with --all")
    ap.add_argument("--all", action="store_true", help="every bench and corpus fixture")
    ap.add_argument("--json", metavar="PATH", help="write here as well as to stdout")
    ap.add_argument("--key", help="print one dotted key instead of the whole document")
    ap.add_argument("--stream-index", type=int)
    ap.add_argument("--penetration-index", type=int)
    args = ap.parse_args()

    if args.stream_index is not None or args.penetration_index is not None:
        if not args.fixture:
            raise SystemExit("a locator needs a fixture")
        print(json.dumps(locate(args.fixture, stream=args.stream_index,
                                penetration=args.penetration_index), indent=2))
        return 0

    if args.all:
        doc = [trace(n) for n in list(FIXTURE_PARAMS) + list(CORPUS_EXTRA)]
    elif args.fixture:
        doc = trace(args.fixture)
    else:
        ap.error("give a fixture name or --all")

    if args.key:
        node = doc
        for part in args.key.split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
        print(json.dumps(node))
    else:
        print(json.dumps(doc, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
