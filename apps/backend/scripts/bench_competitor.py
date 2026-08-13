"""Competitor benchmark harness (v2 Part 64).

Compares STITCHIQ output against competitor embroidery output on matched
artwork, computing only what each source can honestly support:

- **STITCHIQ designs** carry objects, so the full object-level metric set is
  measured directly (provenance: stitchiq_generated).
- **Competitor machine files** (.dst/.pes/...) carry only a stitch stream.
  Stream metrics (stitches, trims, jumps, travel, colour stops) are exact;
  object-level facts are approximated by splitting the stream into blocks at
  TRIM/COLOR_CHANGE and *inferring* each block's stitch family from segment
  statistics (provenance: machine_file_inference — always labelled so).
- **Competitor renders/photos** support visual comparison only; every numeric
  competitor column is reported "unavailable", never guessed.

Outputs (docs/benchmarks/competitor-bench/):
  report.md            one table per case + summary + honesty notes
  cases/<id>.json      machine-readable metrics per case
  visual/<id>.png      artwork | STITCHIQ render [| competitor render] + crops

Rerun: .venv/bin/python scripts/bench_competitor.py   (from apps/backend)
Competitor-sourced inputs live in data/competitor/ (gitignored); a case whose
input is missing is skipped with a note in the report, not silently dropped.
"""

from __future__ import annotations

import json
import math
import sys
from itertools import pairwise
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from _viz import fit_width, hstack_pad, label_bar

from app.models.design import enum_str
from app.services.digitizer import digitize_image
from app.services.embroidery_io import read_embroidery
from app.services.stitch_render import render_design

FIXTURES = BACKEND_ROOT / "tests/fixtures/quality_bench"
COMPETITOR_DIR = BACKEND_ROOT / "data/competitor"
OUT_DIR = BACKEND_ROOT.parents[1] / "docs/benchmarks/competitor-bench"

SMALL_OBJECT_MM2 = 8.0  # Part 49's speck-vs-detail boundary, reused unchanged


# ── stream metrics: exact for ANY design, imported or generated ───────────────


def stream_metrics(design) -> dict:
    """Counts and travel measurable from the stitch stream alone (exact)."""
    counts = {"STITCH": 0, "JUMP": 0, "TRIM": 0, "COLOR_CHANGE": 0}
    travel = 0.0
    prev = None
    for s in design.stitches:
        cmd = str(getattr(s, "command", "")).upper()
        if cmd in counts:
            counts[cmd] += 1
        if cmd == "JUMP" and prev is not None:
            travel += math.dist(prev, (s.x, s.y))
        prev = (s.x, s.y)
    return {
        "stitch_count": counts["STITCH"],
        "trim_count": counts["TRIM"],
        "jump_count": counts["JUMP"],
        "jump_travel_mm": round(travel, 1),
        "color_stop_count": counts["COLOR_CHANGE"] + 1 if design.stitches else 0,
        "width_mm": round(float(design.width_mm), 1),
        "height_mm": round(float(design.height_mm), 1),
    }


# ── object metrics: STITCHIQ designs only (objects observed, not inferred) ────


def object_metrics(design) -> dict | None:
    """Object-level facts read directly from Design.objects (STITCHIQ side)."""
    if not design.objects:
        return None
    types: dict[str, int] = {}
    holes = 0
    with_holes = 0
    small = 0
    angles = set()
    per_object = []
    for o in design.objects:
        st = enum_str(o.stitch_type)
        types[st] = types.get(st, 0) + 1
        if o.holes:
            with_holes += 1
            holes += len(o.holes)
        if o.contour:
            xs = [p.x for p in o.contour]
            ys = [p.y for p in o.contour]
            if (max(xs) - min(xs)) * (max(ys) - min(ys)) < SMALL_OBJECT_MM2:
                small += 1
        angles.add(round(float(o.stitch_angle), 1))
        per_object.append(o.penetration_count)
    per_object.sort()
    return {
        "object_count": len(design.objects),
        "stitch_type_distribution": dict(sorted(types.items())),
        "objects_with_holes": with_holes,
        "hole_count": holes,
        "small_objects_lt_8mm2": small,
        "distinct_angles": len(angles),
        "median_stitches_per_object": per_object[len(per_object) // 2],
    }


# ── block inference: the honest object proxy for machine files ────────────────


def split_blocks(design) -> list[list[tuple[float, float]]]:
    """Split the stream into sewing blocks at TRIM / COLOR_CHANGE boundaries.

    A block is the machine-file stand-in for an object: the run of STITCH
    points between thread cuts. JUMPs inside a block do not split it (fills
    legitimately jump across holes); they simply are not stitch points.
    """
    blocks: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for s in design.stitches:
        cmd = str(getattr(s, "command", "")).upper()
        if cmd in ("TRIM", "COLOR_CHANGE", "END"):
            if len(cur) >= 2:
                blocks.append(cur)
            cur = []
        elif cmd == "STITCH":
            cur.append((s.x, s.y))
    if len(cur) >= 2:
        blocks.append(cur)
    return blocks


def block_features(block: list[tuple[float, float]]) -> dict:
    """Segment statistics a stitch family can be inferred from."""
    segs = []
    for a, b in pairwise(block):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length > 1e-6:
            segs.append((dx, dy, length))
    if not segs:
        return {"n": len(block), "median_len": 0.0, "reversal_rate": 0.0,
                "density": 0.0, "coverage": 0.0, "bbox_mm2": 0.0, "angle_deg": None}
    lens = sorted(s[2] for s in segs)
    median_len = lens[len(lens) // 2]
    total_len = sum(lens)
    reversals = 0
    for (ax, ay, _), (bx, by, _) in pairwise(segs):
        if ax * bx + ay * by < 0:
            reversals += 1
    xs = [p[0] for p in block]
    ys = [p[1] for p in block]
    w = max(max(xs) - min(xs), 0.1)
    h = max(max(ys) - min(ys), 0.1)
    # dominant orientation, doubled-angle mean weighted by length
    c = s2 = 0.0
    for dx, dy, length in segs:
        th = math.atan2(dy, dx)
        c += math.cos(2 * th) * length
        s2 += math.sin(2 * th) * length
    return {
        "n": len(block),
        "median_len": round(median_len, 2),
        "reversal_rate": round(reversals / max(len(segs) - 1, 1), 3),
        "density": round(len(block) / (w * h), 3),  # penetrations per mm² of bbox
        # thread length relative to the bbox diagonal: a run traverses its
        # bbox (~1-3x), a fill blankets it (tens of x) — bbox-thinness-proof
        "coverage": round(total_len / math.hypot(w, h), 2),
        "bbox_mm2": round(w * h, 1),
        "angle_deg": round(math.degrees(0.5 * math.atan2(s2, c)) % 180.0, 1),
    }


def infer_block_type(feat: dict) -> str:
    """Infer run / satin / fill from segment statistics. ALWAYS an inference.

    Calibrated against STITCHIQ's own generators round-tripped through DST
    (where the true type is known) — see test_part64_benchmark.py. Measured
    there: a satin bar reverses direction on nearly every stitch; a run's
    thread length is ~1-3x its bbox diagonal (2.7 for a perimeter walk, 1.0
    for a straight line) while a fill's is ~50x. The run/fill boundary sits at
    coverage 6 — twice the highest run measured, an eighth of the fill — and
    is immune to the thin-bbox trap that makes per-area density lie on
    straight runs.
    """
    if feat["n"] < 4:
        return "unknown"
    if feat["reversal_rate"] >= 0.6 and feat["median_len"] >= 0.8:
        return "satin"
    if feat["coverage"] > 6.0:
        return "fill"
    if feat["reversal_rate"] < 0.4:
        return "run"
    return "unknown"


def block_metrics(design) -> dict:
    """Object-PROXY metrics for a stitch-only design. Provenance: inferred."""
    blocks = split_blocks(design)
    feats = [block_features(b) for b in blocks]
    dist: dict[str, int] = {}
    for f in feats:
        t = infer_block_type(f)
        dist[t] = dist.get(t, 0) + 1
    return {
        "provenance": "machine_file_inference",
        "block_count": len(blocks),
        "inferred_type_distribution": dict(sorted(dist.items())),
        "block_features": feats,
    }


# ── visual pack ───────────────────────────────────────────────────────────────


def side_by_side(panels: list[tuple[str, np.ndarray]], width: int = 420) -> np.ndarray:
    return hstack_pad([label_bar(fit_width(img, width), text, height=30)
                       for text, img in panels], gap=6)


def crops_row(panels: list[tuple[str, np.ndarray]], frac_box: tuple[float, float, float, float],
              width: int = 420) -> np.ndarray:
    """The same fractional box cut from every panel, for like-for-like crops."""
    fx0, fy0, fx1, fy1 = frac_box
    out = []
    for text, img in panels:
        h, w = img.shape[:2]
        crop = img[int(fy0 * h):max(int(fy1 * h), int(fy0 * h) + 1),
                   int(fx0 * w):max(int(fx1 * w), int(fx0 * w) + 1)]
        out.append((f"{text} (crop)", crop))
    return side_by_side(out, width)


# ── the benchmark cases ───────────────────────────────────────────────────────
# kind:
#   fixture      artwork in-repo; STITCHIQ measured fully; no competitor data
#   machine_file competitor stitch file; stream exact + blocks inferred;
#                no artwork, so no matched STITCHIQ side
#   render_only  competitor render/photo as artwork; STITCHIQ digitizes it;
#                competitor numbers unavailable, comparison is visual

CASES = [
    {"id": "01-flat-logo", "kind": "fixture", "artwork": FIXTURES / "01_flat_2color_logo.png",
     "colors": 2, "crop": (0.30, 0.25, 0.70, 0.65)},
    {"id": "05-lettering", "kind": "fixture", "artwork": FIXTURES / "05_wordmark_caps.png",
     "colors": 2, "crop": (0.05, 0.30, 0.55, 0.70)},
    {"id": "07-badge", "kind": "fixture", "artwork": FIXTURES / "07_circular_badge.png",
     "colors": 3, "crop": (0.30, 0.25, 0.75, 0.70)},
    {"id": "03-photo-derived", "kind": "fixture", "artwork": FIXTURES / "03_gradient_soft_subject.png",
     "colors": 4, "crop": (0.25, 0.20, 0.75, 0.70)},
    {"id": "08-small-detail", "kind": "fixture", "artwork": FIXTURES / "08_mascot_detail.png",
     "colors": 4, "crop": (0.30, 0.30, 0.70, 0.70)},
    {"id": "sample-dst", "kind": "machine_file",
     "file": BACKEND_ROOT / "tests/fixtures/sample.dst"},
    {"id": "sample-pes", "kind": "machine_file",
     "file": BACKEND_ROOT / "tests/fixtures/sample.pes"},
    {"id": "angelfish-royal-present", "kind": "render_only",
     "artwork": COMPETITOR_DIR / "angelfish.jpg", "colors": 4,
     "note": "Competitor render (royal-present.ru marketing photo, watermarked). "
             "No stitch file: numeric competitor columns are unavailable.",
     "crop": (0.35, 0.25, 0.80, 0.60)},
]


def run_case(case: dict, out_dir: Path | None = None) -> dict:
    result = {"id": case["id"], "kind": case["kind"], "stitchiq": None,
              "competitor": None, "notes": []}
    visual_panels: list[tuple[str, np.ndarray]] = []

    if case["kind"] in ("fixture", "render_only"):
        art_path = case["artwork"]
        if not art_path.exists():
            result["notes"].append(f"SKIPPED: artwork missing ({art_path.name})")
            return result
        art = cv2.imread(str(art_path))
        cv2.setRNGSeed(1234)
        d = digitize_image(art_path.read_bytes(), "cotton", "100x100", case["colors"])
        result["stitchiq"] = {"provenance": "stitchiq_generated",
                              **stream_metrics(d), **(object_metrics(d) or {})}
        label = "competitor render" if case["kind"] == "render_only" else "source artwork"
        visual_panels.append((label, art))
        visual_panels.append(("STITCHIQ", render_design(d)))
        if case["kind"] == "render_only":
            result["competitor"] = {"provenance": "render_only",
                                    "numeric_metrics": "unavailable"}
            result["notes"].append(case.get("note", ""))

    elif case["kind"] == "machine_file":
        fp = case["file"]
        if not fp.exists():
            result["notes"].append(f"SKIPPED: file missing ({fp.name})")
            return result
        d = read_embroidery(fp.read_bytes(), fp.suffix.lstrip("."))
        bm = block_metrics(d)
        bm.pop("block_features")  # per-block detail goes to JSON consumers who ask
        result["competitor"] = {**stream_metrics(d), **bm}
        result["notes"].append("No source artwork for this file: no matched "
                               "STITCHIQ side exists. Stream metrics exact; "
                               "types inferred from segment statistics.")
        visual_panels.append((f"competitor ({fp.name})", render_design(d)))

    if visual_panels:
        vis = side_by_side(visual_panels)
        if "crop" in case:
            vis = np.vstack([vis, np.full((6, vis.shape[1], 3), 255, np.uint8),
                             crops_row(visual_panels, case["crop"])])
        out = (out_dir or OUT_DIR) / "visual" / f"{case['id']}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), vis)
        result["visual"] = str(out.relative_to((out_dir or OUT_DIR).parents[1]))
    return result


# ── report ────────────────────────────────────────────────────────────────────

METRIC_ROWS = [
    ("object count", "object_count", "block_count (inferred)"),
    ("stitch count", "stitch_count", "stitch_count"),
    ("trim count", "trim_count", "trim_count"),
    ("jump travel mm", "jump_travel_mm", "jump_travel_mm"),
    ("color stops", "color_stop_count", "color_stop_count"),
    ("stitch types", "stitch_type_distribution", "inferred_type_distribution"),
    ("objects with holes", "objects_with_holes", None),
    ("small objects <8mm2", "small_objects_lt_8mm2", None),
    ("distinct angles", "distinct_angles", None),
]


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, dict):
        return ", ".join(f"{k} {n}" for k, n in v.items()) or "—"
    return str(v)


def case_table(r: dict) -> str:
    lines = [f"### {r['id']}  ({r['kind']})", "",
             "| metric | STITCHIQ | competitor |", "|---|---|---|"]
    sq, cp = r.get("stitchiq"), r.get("competitor")
    for label, sq_key, cp_key in METRIC_ROWS:
        sv = sq.get(sq_key) if sq else None
        ck = cp_key.split(" ")[0] if cp_key else None
        cv_ = cp.get(ck) if (cp and ck) else None
        if cp and cv_ is None and ck is not None and cp.get("numeric_metrics") == "unavailable":
            cv_ = "unavailable (render only)"
        lines.append(f"| {label} | {_fmt(sv)} | {_fmt(cv_)} |")
    for n in r.get("notes", []):
        if n:
            lines.append(f"\n> {n}")
    if r.get("visual"):
        lines.append(f"\nVisual: `{r['visual']}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "cases").mkdir(exist_ok=True)
    results = []
    for case in CASES:
        print(f"running {case['id']} ...", flush=True)
        r = run_case(case)
        results.append(r)
        (OUT_DIR / "cases" / f"{case['id']}.json").write_text(json.dumps(r, indent=1))

    lines = [
        "# Competitor benchmark (v2 Part 64)", "",
        "Regenerate with `scripts/bench_competitor.py`. Every number is either",
        "measured exactly from a stream, read from STITCHIQ objects, or marked",
        "inferred/unavailable — nothing in between.", "",
        "## Summary",
        "",
        "| case | kind | SQ objects | SQ stitches | SQ trims | competitor stitches | competitor trims |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        sq, cp = r.get("stitchiq") or {}, r.get("competitor") or {}
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            r["id"], r["kind"], _fmt(sq.get("object_count")), _fmt(sq.get("stitch_count")),
            _fmt(sq.get("trim_count")), _fmt(cp.get("stitch_count")), _fmt(cp.get("trim_count"))))
    lines += [
        "",
        "## Comparison framing",
        "",
        "Four verdicts exist: better / worse / different-but-not-clearly-worse /",
        "not measurable. With the competitor data held today, **every numeric",
        "cross-comparison is 'not measurable from the files available'**:",
        "the five fixture cases have no competitor output for their artwork, the",
        "two foreign machine files have no artwork (and are trivial test",
        "patterns — most blocks under 4 stitches), and the render-only case has",
        "no competitor stitch file. The one comparison the current population",
        "supports is *visual*, on the render-only case, and any better/worse",
        "verdict drawn from it is human judgement over the visual pack — it is",
        "recorded in the Part 64 audit as such, not asserted here as a metric.",
        "",
        "What would upgrade this to numeric verdicts, in order of value:",
        "native competitor design files (objects + properties) for matched",
        "artwork; else competitor machine files exported for artwork we can also",
        "digitize (stream + inferred-block comparisons on matched ground).",
        "",
    ]
    for r in results:
        lines.append(case_table(r))
    (OUT_DIR / "report.md").write_text("\n".join(lines))
    print(f"wrote {OUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
