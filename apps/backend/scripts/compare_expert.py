"""Our output against an expert's machine file, at the granularities both have.

    python scripts/compare_expert.py                    # every real job pair
    python scripts/compare_expert.py --only <job-name>
    python scripts/compare_expert.py --self-test        # no real artwork needed

WHY NOT PER-OBJECT. The first specification for this harness asked for per-object
stitch-type agreement. That measurement cannot exist: a DST carries no object
metadata at all, and a PES carries colour blocks and nothing else. There is no
expert-side object to agree with, so the comparison is built at the two
granularities that are genuinely present on both sides —

    design level    stitch count, colour count, machine-minutes net of trim,
                    trims, jumps, bounding box, and our own coverage metric run
                    over the EXPERT's stream as well as ours;
    block level     per-colour-block stitch count, extent and thread colour,
                    matched nearest-colour first and then by spatial overlap.

— plus a rendered side-by-side and a difference image, because the first useful
signal from real artwork will be visual and not numeric. A colour block is a run
of stitching between colour changes: it is what the machine executes and what
every format records, so both sides have it by construction.

NOTHING HERE IS TUNED. There are no thresholds and no pass/fail. It reports
differences; deciding which of them are defects needs the real pairs, and they
have not arrived.

METRIC PROVENANCE. `TRIM_SECONDS`, `STITCH_PER_MIN` and `coverage_metrics` are
IMPORTED from the bench and the quality measurement rather than restated. A
number here has to be comparable with every other number in this series, and
re-deriving a formula by hand is exactly how this project once reported a result
3.3x wrong.
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
from measure_stitch_quality import _cmd, coverage_metrics
from real_jobs import RealJobError, load_jobs
from run_quality_bench import RNG_SEED, TRIM_SECONDS

from app.services.digitizer import digitize_image
from app.services.embroidery_io import read_embroidery
from app.services.stitch_render import render_design

OUT_DIR = BACKEND.parent.parent / "docs" / "benchmarks" / "real-jobs"

# Sewing speed. Imported would be better; `run_quality_bench` derives est_minutes
# inline rather than exposing a constant, so it is restated ONCE here with the
# source named, and `test_compare_expert.py` asserts the two agree on a fixture.
STITCH_PER_MIN = 800.0

RENDER_PX_PER_MM = 8.0


# ── the two granularities both sides have ───────────────────────────────────


def _blocks(design) -> list[dict]:
    """Colour blocks: runs of stitching between colour changes.

    This is what the machine executes and what every format records, so it is
    directly comparable between our Design and one read back from a DST. Built
    from the STREAM rather than from `design.objects`, because the expert side
    has no objects.
    """
    stops = list(design.color_stops or [])
    out: list[dict] = []
    cur: list[tuple[float, float]] = []

    def close():
        if not cur:
            return
        xs = [p[0] for p in cur]
        ys = [p[1] for p in cur]
        i = len(out)
        out.append({
            "index": i,
            "stitches": len(cur),
            "x_mm": round(min(xs), 2),
            "y_mm": round(min(ys), 2),
            "w_mm": round(max(xs) - min(xs), 2),
            "h_mm": round(max(ys) - min(ys), 2),
            "hex": (stops[i].hex if i < len(stops) else None),
        })
        cur.clear()

    for s in design.stitches:
        c = _cmd(s)
        if c == "STITCH":
            cur.append((float(s.x), float(s.y)))
        elif c in ("COLOR_CHANGE", "END"):
            close()
    close()
    return [b for b in out if b["stitches"]]


def _design_metrics(design) -> dict:
    """Everything both sides can answer, in the units the rest of the series uses."""
    pts, lengths = [], []
    trims = jumps = 0
    prev = None
    for s in design.stitches:
        c = _cmd(s)
        if c == "STITCH":
            p = (float(s.x), float(s.y))
            if prev is not None:
                lengths.append(float(np.hypot(p[0] - prev[0], p[1] - prev[1])))
            pts.append(p)
            prev = p
        elif c == "TRIM":
            trims += 1
            prev = None
        elif c == "JUMP":
            jumps += 1
            prev = None
        elif c == "COLOR_CHANGE":
            prev = None

    n = len(pts)
    est_min = n / STITCH_PER_MIN
    xs = [p[0] for p in pts] or [0.0]
    ys = [p[1] for p in pts] or [0.0]
    blocks = _blocks(design)
    return {
        "stitches": n,
        "colour_blocks": len(blocks),
        "distinct_threads": len({b["hex"] for b in blocks if b["hex"]}),
        "trims": trims,
        "jumps": jumps,
        # The headline the whole series is graded on: sewing time plus the
        # machine stop each trim costs. A change that trades stitches for trims
        # must be judged on the total.
        "machine_minutes": round(est_min + trims * TRIM_SECONDS / 60.0, 2),
        "est_minutes": round(est_min, 2),
        "width_mm": round(max(xs) - min(xs), 2),
        "height_mm": round(max(ys) - min(ys), 2),
        "mean_stitch_mm": round(float(np.mean(lengths)), 3) if lengths else 0.0,
        "max_stitch_mm": round(float(max(lengths)), 2) if lengths else 0.0,
    }


def _match_blocks(ours: list[dict], theirs: list[dict]) -> dict:
    """Pair colour blocks by nearest colour, then resolve by spatial overlap.

    Greedy over colour distance because thread colour is the stronger signal —
    an expert and we may split one colour across a different number of blocks,
    but a navy block is not going to be matched to a gold one. Overlap breaks
    ties between blocks of the SAME colour, which is the common case.

    Unmatched blocks on either side are REPORTED, not dropped: "the expert used
    three blocks of navy where we used one" is exactly the kind of difference
    this harness exists to surface.
    """
    def rgb(b):
        h = (b["hex"] or "#000000").lstrip("#")
        return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)

    def iou(a, b):
        ax2, ay2 = a["x_mm"] + a["w_mm"], a["y_mm"] + a["h_mm"]
        bx2, by2 = b["x_mm"] + b["w_mm"], b["y_mm"] + b["h_mm"]
        ix = max(0.0, min(ax2, bx2) - max(a["x_mm"], b["x_mm"]))
        iy = max(0.0, min(ay2, by2) - max(a["y_mm"], b["y_mm"]))
        inter = ix * iy
        union = a["w_mm"] * a["h_mm"] + b["w_mm"] * b["h_mm"] - inter
        return inter / union if union > 0 else 0.0

    cand = []
    for i, o in enumerate(ours):
        for j, t in enumerate(theirs):
            cand.append((float(np.linalg.norm(rgb(o) - rgb(t))), -iou(o, t), i, j))
    cand.sort()

    used_o: set[int] = set()
    used_t: set[int] = set()
    pairs = []
    for dist, neg_iou, i, j in cand:
        if i in used_o or j in used_t:
            continue
        used_o.add(i)
        used_t.add(j)
        o, t = ours[i], theirs[j]
        pairs.append({
            "ours_index": i,
            "expert_index": j,
            "colour_distance": round(dist, 1),
            "bbox_iou": round(-neg_iou, 3),
            "ours_hex": o["hex"],
            "expert_hex": t["hex"],
            "ours_stitches": o["stitches"],
            "expert_stitches": t["stitches"],
            "stitch_delta": o["stitches"] - t["stitches"],
            "ours_extent_mm": [o["w_mm"], o["h_mm"]],
            "expert_extent_mm": [t["w_mm"], t["h_mm"]],
        })
    pairs.sort(key=lambda p: p["expert_index"])
    return {
        "matched": pairs,
        "ours_unmatched": [ours[i]["index"] for i in range(len(ours)) if i not in used_o],
        "expert_unmatched": [theirs[j]["index"] for j in range(len(theirs)) if j not in used_t],
    }


# ── the visual half ─────────────────────────────────────────────────────────


def _render_pair(ours, theirs, path: Path) -> dict:
    """Side-by-side plus a difference image, aligned by CONTENT.

    Two things here are easy to get wrong, and both were wrong in a draft:

    1. INK IS NOT "DARKER THAN WHITE". The canvas is `FABRIC_BGR`
       (222, 228, 232) — every channel under 250 — so a `< 250` test calls the
       whole canvas ink and the difference image comes out uniformly "both".
       Ink is "differs from the fabric colour", which is what the renderer draws.

    2. ALIGNMENT IS BY CONTENT, NOT BY ABSOLUTE COORDINATE, and the reverse was
       tried first. Putting both designs in a shared mm frame is the obvious
       move and it is wrong here: a DST stores coordinates relative to its own
       origin, and where an expert placed the design in the hoop is a property of
       their file, not of the stitching. Registering on absolute mm made a pure
       7mm translation read as 23.6% disagreement — the whole outline lit up
       twice, which is a picture of nothing. The two bounding boxes are centred
       on each other instead, so the difference shows shape and coverage, which
       is what is actually comparable.

       The cost of that choice, stated because it is real: a placement or
       hoop-position difference is INVISIBLE in this image. It is visible in the
       design-level `width_mm`/`height_mm` deltas, which is where it belongs.

    Imported `FABRIC_BGR` and `MARGIN_PX` rather than restating them: they are
    the renderer's own numbers and a copy here could drift from what it draws.
    """
    from app.services.stitch_render import FABRIC_BGR, MARGIN_PX

    ra = render_design(ours, px_per_mm=RENDER_PX_PER_MM)
    rb = render_design(theirs, px_per_mm=RENDER_PX_PER_MM)
    h = max(ra.shape[0], rb.shape[0])
    w = max(ra.shape[1], rb.shape[1])

    def centred(img):
        out = np.full((h, w, 3), FABRIC_BGR, np.uint8)
        dy = (h - img.shape[0]) // 2
        dx = (w - img.shape[1]) // 2
        out[dy:dy + img.shape[0], dx:dx + img.shape[1]] = img
        return out

    a, b = centred(ra), centred(rb)
    fabric = np.array(FABRIC_BGR, np.int16)
    ink_a = (np.abs(a.astype(np.int16) - fabric) > 6).any(axis=2)
    ink_b = (np.abs(b.astype(np.int16) - fabric) > 6).any(axis=2)

    # Grey where both stitched, so agreement recedes and disagreement is what the
    # eye lands on. Red = ours only, blue = the expert's only.
    diff = np.full((h, w, 3), 255, np.uint8)
    diff[ink_a & ink_b] = (205, 205, 205)
    diff[ink_a & ~ink_b] = (60, 60, 220)
    diff[~ink_a & ink_b] = (220, 120, 40)

    gap = np.full((h, MARGIN_PX, 3), 255, np.uint8)
    sheet = np.hstack([a, gap, b, gap, diff])
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), sheet)
    return {
        "sheet": str(path),
        "ours_only_px": int((ink_a & ~ink_b).sum()),
        "expert_only_px": int((~ink_a & ink_b).sum()),
        "both_px": int((ink_a & ink_b).sum()),
        "aligned_by": "bounding-box centre (absolute mm is not comparable across formats)",
        "layout": "ours | expert | difference (red=ours only, blue=expert only)",
    }


# ── one job ─────────────────────────────────────────────────────────────────


def compare(ours, theirs, name: str, *, render_to: Path | None = None) -> dict:
    om, tm = _design_metrics(ours), _design_metrics(theirs)
    delta = {}
    for k in om:
        if isinstance(om[k], (int, float)) and isinstance(tm[k], (int, float)):
            d = round(om[k] - tm[k], 3)
            pct = (round(100.0 * d / tm[k], 1) if tm[k] else None)
            delta[k] = {"ours": om[k], "expert": tm[k], "delta": d, "pct": pct}

    res = {
        "job": name,
        "design": delta,
        "blocks": _match_blocks(_blocks(ours), _blocks(theirs)),
        # Our own coverage measure, run over the EXPERT's stream too. It was
        # built to grade our stitching; pointing it at a professional's file is
        # the only way to learn what it reads on work that is known to be good.
        "coverage": {"ours": coverage_metrics(ours), "expert": coverage_metrics(theirs)},
    }
    if render_to is not None:
        res["render"] = _render_pair(ours, theirs, render_to)
    return res


def _print(res: dict) -> None:
    print(f"\n=== {res['job']} ===")
    print(f"{'metric':18s} {'ours':>12s} {'expert':>12s} {'delta':>10s} {'pct':>8s}")
    for k, v in res["design"].items():
        pct = "-" if v["pct"] is None else f"{v['pct']:+.1f}%"
        print(f"{k:18s} {v['ours']:>12} {v['expert']:>12} {v['delta']:>10} {pct:>8s}")

    b = res["blocks"]
    print(f"\ncolour blocks: {len(b['matched'])} matched, "
          f"{len(b['ours_unmatched'])} ours unmatched, "
          f"{len(b['expert_unmatched'])} expert unmatched")
    if b["matched"]:
        print(f"  {'exp#':>4s} {'ours':>7s} {'expert':>7s} {'delta':>7s} "
              f"{'dcolour':>8s} {'iou':>6s}  hex ours/expert")
        for p in b["matched"]:
            print(f"  {p['expert_index']:4d} {p['ours_stitches']:7d} "
                  f"{p['expert_stitches']:7d} {p['stitch_delta']:+7d} "
                  f"{p['colour_distance']:8.1f} {p['bbox_iou']:6.3f}  "
                  f"{p['ours_hex']}/{p['expert_hex']}")
    if "render" in res:
        r = res["render"]
        print(f"\n  {r['sheet']}")
        print(f"  ours-only {r['ours_only_px']:,}px  expert-only {r['expert_only_px']:,}px  "
              f"both {r['both_px']:,}px")


# ── self-test: prove the instrument works before the material arrives ───────


def _self_test() -> int:
    """No real artwork required, and that is the point.

    A harness that has never been run cannot be trusted the day the first real
    pair lands. Two checks: comparing a design with ITSELF must report zero
    everywhere (any non-zero is a bug in the harness, not a finding), and
    comparing it with a deliberately perturbed copy must report the perturbation.
    """
    fixture = BACKEND / "tests" / "fixtures" / "quality_bench" / "07_circular_badge.png"
    cv2.setRNGSeed(RNG_SEED)
    d = digitize_image(fixture.read_bytes(), "cotton", "100x100", 6)

    same = compare(d, d, "self (identity)")
    bad = [k for k, v in same["design"].items() if v["delta"] != 0]
    if bad:
        print(f"IDENTITY FAILED — non-zero delta on {bad}")
        return 1
    m = same["blocks"]
    if m["ours_unmatched"] or m["expert_unmatched"]:
        print(f"IDENTITY FAILED — unmatched blocks: {m}")
        return 1
    if any(p["stitch_delta"] != 0 or p["colour_distance"] != 0 for p in m["matched"]):
        print("IDENTITY FAILED — a block did not match itself")
        return 1
    print(f"identity: {len(m['matched'])} blocks, all deltas zero  OK")

    # Drop the last colour block. The harness must SEE it: one fewer block, an
    # unmatched expert block, and fewer stitches.
    keep = d.model_copy(deep=True)
    cut = _blocks(d)[-1]["stitches"]
    kept = []
    seen = 0
    limit = len(_blocks(d)) - 1
    for s in d.stitches:
        if _cmd(s) == "COLOR_CHANGE":
            seen += 1
            if seen >= limit:
                break
        kept.append(s)
    keep.stitches = kept
    keep.color_stops = list(d.color_stops)[:limit]

    perturbed = compare(keep, d, "self (one block removed)")
    if perturbed["design"]["stitches"]["delta"] >= 0:
        print("PERTURBATION MISSED — removing a block did not reduce the count")
        return 1
    if not perturbed["blocks"]["expert_unmatched"]:
        print("PERTURBATION MISSED — the removed block was not reported unmatched")
        return 1
    print(f"perturbation: stitches {perturbed['design']['stitches']['delta']:+d} "
          f"(block held {cut}), "
          f"{len(perturbed['blocks']['expert_unmatched'])} expert block(s) unmatched  OK")

    sheet = OUT_DIR / "self-test.png"
    r = _render_pair(keep, d, sheet)
    if r["expert_only_px"] <= 0:
        print("RENDER FAILED — the removed block is not visible in the difference")
        return 1
    print(f"render: {sheet}  expert-only {r['expert_only_px']:,}px  OK")
    print("\nharness verified on synthetic pairs; no real artwork was used or tuned against")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="a single job by directory name")
    ap.add_argument("--self-test", action="store_true",
                    help="verify the harness itself; needs no real artwork")
    ap.add_argument("--json", type=Path, help="write the full result here")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    try:
        jobs = load_jobs()
    except RealJobError as exc:
        print(f"invalid job: {exc}")
        return 1
    if args.only:
        jobs = [j for j in jobs if j.name == args.only]
    if not jobs:
        print("no real job pairs to compare. `python scripts/real_jobs.py` says what "
              "is expected where; `--self-test` verifies the harness without them.")
        return 0

    results = []
    for j in jobs:
        p = j.params
        cv2.setRNGSeed(RNG_SEED)
        ours = digitize_image(j.artwork.read_bytes(), p["fabric"], p["hoop"],
                              int(p["colors"]), text_mode=bool(p.get("text", False)))
        theirs = read_embroidery(j.expert.read_bytes(), j.expert.suffix.lstrip("."))
        res = compare(ours, theirs, j.name, render_to=OUT_DIR / f"{j.name}.png")
        res["tier"] = j.tier
        _print(res)
        results.append(res)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
