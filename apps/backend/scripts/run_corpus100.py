"""Digitize the 100-design corpus and measure every one (v2 Part 36).

Runs in a process pool (the digitizer is CPU-bound and releases nothing), and
records per design: wall time, object/stitch/colour counts, penetration-floor
violations, over-machine-limit stitches, density flags, interior coverage,
trims/jumps, emitted warnings, and any exception with its traceback.

Usage:  .venv/bin/python scripts/run_corpus100.py [--workers 3] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

CORPUS = BACKEND / "tests" / "fixtures" / "corpus100"

# Hoop chosen per design so size is never the thing being measured: a large
# format for the real panels, a standard one for everything else.
BIG = {"A01_real_peacock_patch_photo", "A02_real_neckline_black", "A03_real_neckline_panel"}


def _gap(a, b) -> float:
    import math

    return math.hypot(b.x - a.x, b.y - a.y)


def _one(name: str) -> dict:
    from measure_stitch_quality import measure

    from app.services.digitizer import MIN_PENETRATION_MM, ROW_SPACING_MM, digitize_image

    path = CORPUS / f"{name}.png"
    hoop = "360x350" if name in BIG or name.startswith("B") else "180x130"
    row = {"name": name, "hoop": hoop}
    try:
        t0 = time.time()
        design = digitize_image(path.read_bytes(), "cotton", hoop, 12)
        row["seconds"] = round(time.time() - t0, 2)
        cmds = [getattr(s.command, "value", str(s.command)) for s in design.stitches]
        # An EMPTY design is a product failure, not a harness error: measuring
        # it divides by zero. Record it as data so the report can rank it.
        if cmds.count("STITCH") == 0:
            row.update(
                ok=True, empty=True, objects=len(design.objects), stitches=0,
                jumps=0, trims=0, colors=len(design.color_stops),
                width_mm=round(design.width_mm, 1), height_mm=round(design.height_mm, 1),
                interior=0.0, floor_violations=0, over_limit=0, density_flags=0,
                warnings=list(design.warnings or []),
            )
            return row
        m = measure(design, ROW_SPACING_MM, MIN_PENETRATION_MM)
        row.update(
            objects=len(design.objects),
            stitches=cmds.count("STITCH"),
            jumps=cmds.count("JUMP"),
            trims=cmds.count("TRIM"),
            colors=len(design.color_stops),
            width_mm=round(design.width_mm, 1),
            height_mm=round(design.height_mm, 1),
            empty=False,
            interior=round(m["coverage"].get("interior_pct") or -1.0, 2),
            floor_violations=int(m["penetration"].get("below_floor", -1)),
            # Only SEWN pairs are bounded by the machine's reach: a jump or a
            # post-trim move is legitimately long (the needle travels with the
            # thread cut). Counting those read 285-865 "violations" on clean
            # designs — an instrument error, not a defect.
            over_limit=sum(
                1
                for i in range(1, len(design.stitches))
                if cmds[i] == "STITCH" and cmds[i - 1] == "STITCH"
                and _gap(design.stitches[i - 1], design.stitches[i]) > 12.7
            ),
            density_flags=int(m["density"].get("flagged_cells", -1)),
            warnings=list(design.warnings or []),
            ok=True,
        )
    except Exception as exc:  # noqa: BLE001 - the whole point is to catch these
        row.update(ok=False, error=f"{type(exc).__name__}: {exc}",
                   traceback=traceback.format_exc()[-1200:])
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--json", type=Path, default=BACKEND / "scripts" / "corpus100.json")
    ap.add_argument("--only", help="substring filter")
    args = ap.parse_args()

    meta = json.loads((CORPUS / "corpus.json").read_text())
    names = [m["name"] for m in meta if not args.only or args.only in m["name"]]
    tier = {m["name"]: m["tier"] for m in meta}
    cls = {m["name"]: m["class"] for m in meta}

    rows = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(_one, n): n for n in names}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            r["tier"] = tier[r["name"]]
            r["class"] = cls[r["name"]]
            rows.append(r)
            flag = "ok " if r.get("ok") else "ERR"
            print(f"[{i:3d}/{len(names)}] {flag} {r['name']}", flush=True)

    rows.sort(key=lambda r: r["name"])
    args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    bad = [r for r in rows if not r.get("ok")]
    print(f"\ndone in {time.time() - t0:.0f}s — {len(rows)} designs, {len(bad)} errors")
    print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
