"""Digitizer quality benchmark harness (Part 0).

Runs the digitize pipeline over every fixture in
``tests/fixtures/quality_bench/`` and emits, under ``docs/benchmarks/<tag>/``:

  * ``<tag>/<fixture>-output.png`` — the stitch render, via the app's OWN preview
    renderer (``services.package.render_preview``), i.e. what a customer sees
    in the production package. The harness deliberately does not draw stitches
    its own way; grading a private renderer would grade the wrong thing.
  * ``<tag>/<fixture>.json``       — per-fixture metrics + warnings/errors
  * ``<tag>-summary.json``         — every fixture in one file, plus totals
  * ``<tag>-grid.png``             — labeled input→output contact grid

This is **measurement infrastructure**. It imports the pipeline and must never
modify it: every future improvement is graded by re-running this exact script
with a new ``--tag`` and diffing the numbers against ``v1-baseline``.

Usage
-----
    python scripts/run_quality_bench.py                  # tag: v1-baseline
    python scripts/run_quality_bench.py --tag v2-part1   # after a pipeline change

Determinism: k-means seeds itself from OpenCV's global RNG, so the harness pins
that seed before each fixture. Same input + same pipeline ⇒ same numbers, which
is what makes a before/after diff meaningful rather than noise.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

FIXTURE_DIR = BACKEND_ROOT / "tests" / "fixtures" / "quality_bench"
BENCH_DIR = REPO_ROOT / "docs" / "benchmarks"

RNG_SEED = 20260728
SPM = 800.0  # machine speed used for the time estimate (matches package.build_summary)
MACHINE_MAX_STITCH_MM = 12.7  # hard machine limit; anything longer is a defect

# Per-fixture digitize parameters. Kept in the harness (not guessed per run) so a
# re-run after a pipeline change compares like with like. ``colors`` is chosen to
# match the artwork's real palette, which is the fair setting for each case.
FIXTURE_PARAMS: dict[str, dict] = {
    "01_flat_2color_logo": {"colors": 2, "hoop": "100x100", "fabric": "cotton"},
    "02_logo_fine_text_3color": {"colors": 3, "hoop": "130x180", "fabric": "cotton"},
    "03_gradient_soft_subject": {"colors": 4, "hoop": "130x180", "fabric": "cotton"},
    "04_thin_line_outline": {"colors": 2, "hoop": "100x100", "fabric": "cotton"},
    # 05/06 are pure wordmarks, so they are digitized as LETTERING (text=True),
    # the same path `generate_lettering` uses. Declared here rather than inferred
    # so the setting is visible in the diff and in every summary JSON.
    # 02 and 07 contain text inside a mixed design and stay text=False: isolating
    # the type within a logo needs per-object stroke detection, which is Part 3.
    "05_wordmark_caps": {"colors": 2, "hoop": "130x180", "fabric": "cotton", "text": True},
    "06_wordmark_script": {"colors": 2, "hoop": "130x180", "fabric": "cotton", "text": True},
    "07_circular_badge": {"colors": 4, "hoop": "130x180", "fabric": "cotton"},
    "08_mascot_detail": {"colors": 5, "hoop": "130x180", "fabric": "cotton"},
    "09_nonuniform_background": {"colors": 4, "hoop": "130x180", "fabric": "cotton"},
    "10_low_contrast_subject": {"colors": 4, "hoop": "130x180", "fabric": "cotton"},
}
DEFAULT_PARAMS = {"colors": 4, "hoop": "130x180", "fabric": "cotton"}


@dataclass
class FixtureResult:
    """Everything the audit needs about one fixture, in one JSON-able record."""

    fixture: str
    params: dict
    ok: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    runtime_s: float = 0.0

    stitch_count: int = 0
    color_count: int = 0
    object_count: int = 0
    stitch_types: dict[str, int] = field(default_factory=dict)
    objects_with_holes: int = 0

    width_mm: float = 0.0
    height_mm: float = 0.0
    est_minutes: float = 0.0

    jump_count: int = 0
    trim_count: int = 0
    color_changes: int = 0

    max_stitch_mm: float = 0.0
    mean_stitch_mm: float = 0.0
    stitches_over_machine_limit: int = 0
    stitches_under_0_5mm: int = 0

    # Density over the FILLED area (sum of object contour areas minus holes), not
    # the bounding box. The bounding-box version read artificially low for any
    # design with empty space and invited the misreading corrected in v1 audit §3.
    stitch_density_per_mm2: float = 0.0
    filled_area_mm2: float = 0.0
    stitch_density_per_bbox_mm2: float = 0.0  # v1's definition, kept for comparability

    # Coverage straight from stitch geometry — the audit proved bitmap-based
    # coverage grading is unreliable, so this never looks at the rendered PNG.
    fill_row_pitch_mm: float = 0.0
    fill_rows_over_thread_width: int = 0
    coverage_ratio: float = 0.0

    segmentation_method: str | None = None
    satin_share: float = 0.0        # SATIN objects / all objects
    output_png: str | None = None


def _rel(path: Path) -> str:
    """Repo-relative path when possible, absolute otherwise (tests write to tmp)."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _cmd(stitch) -> str:
    c = stitch.command
    return c.value if hasattr(c, "value") else str(c)


THREAD_WIDTH_MM = 0.4  # 40wt embroidery thread, the global standard


def _polygon_area(points) -> float:
    """Shoelace area of a closed polygon of Points, in mm²."""
    if len(points) < 3:
        return 0.0
    total = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        total += p.x * q.y - q.x * p.y
    return abs(total) / 2.0


def filled_area_mm2(design) -> float:
    """Area the design actually covers: object contours minus their holes."""
    total = 0.0
    for o in design.objects:
        if not o.contour:
            continue
        total += _polygon_area(o.contour) - sum(_polygon_area(h) for h in (o.holes or []))
    return max(total, 0.0)


def fill_row_geometry(design) -> tuple[float, int]:
    """Median vertical pitch between adjacent fill rows (mm), and how many gaps
    exceed one thread width.

    Measured from stitch coordinates, never from the render. A pitch at or below
    the thread width means the rows touch or overlap — full coverage.
    """
    import statistics

    ys = sorted({round(s.y, 3) for s in design.stitches if _cmd(s) == "STITCH"})
    gaps = [b - a for a, b in zip(ys, ys[1:]) if b - a > 1e-6]
    if not gaps:
        return 0.0, 0
    return round(statistics.median(gaps), 3), sum(1 for g in gaps if g > THREAD_WIDTH_MM)


def _stitch_lengths(design) -> list[float]:
    """Needle-to-needle travel for consecutive STITCH commands (mm)."""
    out: list[float] = []
    prev = None
    for s in design.stitches:
        if _cmd(s) == "STITCH":
            if prev is not None:
                out.append(math.dist((prev.x, prev.y), (s.x, s.y)))
            prev = s
        else:
            prev = None  # a jump/trim/color-change breaks the run
    return out


def run_fixture(path: Path, out_dir: Path) -> FixtureResult:
    import cv2

    from app.services.digitizer import digitize_image
    from app.services.package import render_preview

    params = FIXTURE_PARAMS.get(path.stem, DEFAULT_PARAMS)
    res = FixtureResult(fixture=path.stem, params=dict(params))

    cv2.setRNGSeed(RNG_SEED)  # pin k-means init so re-runs are comparable
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            design = digitize_image(
                path.read_bytes(),
                fabric_type=params["fabric"],
                hoop_size=params["hoop"],
                max_colors=params["colors"],
                text_mode=bool(params.get("text", False)),
            )
        except Exception as exc:  # noqa: BLE001 - a crash is a finding, not a stop
            res.runtime_s = round(time.perf_counter() - started, 3)
            res.error = f"{type(exc).__name__}: {exc}"
            res.warnings = [str(w.message) for w in caught]
            traceback.print_exc()
            return res
        res.runtime_s = round(time.perf_counter() - started, 3)
        res.warnings = [str(w.message) for w in caught]

    res.ok = True
    res.stitch_count = design.stitch_count
    res.color_count = len(design.color_stops)
    res.object_count = len(design.objects)
    res.objects_with_holes = sum(1 for o in design.objects if o.holes)
    for o in design.objects:
        key = o.stitch_type.value if hasattr(o.stitch_type, "value") else str(o.stitch_type)
        res.stitch_types[key] = res.stitch_types.get(key, 0) + 1
    res.satin_share = round(res.stitch_types.get("SATIN", 0) / max(res.object_count, 1), 3)

    res.width_mm, res.height_mm = design.width_mm, design.height_mm
    res.est_minutes = round(design.stitch_count / SPM, 2)

    res.jump_count = sum(1 for s in design.stitches if _cmd(s) == "JUMP")
    res.trim_count = sum(1 for s in design.stitches if _cmd(s) == "TRIM")
    res.color_changes = sum(1 for s in design.stitches if _cmd(s) == "COLOR_CHANGE")

    lengths = _stitch_lengths(design)
    if lengths:
        res.max_stitch_mm = round(max(lengths), 2)
        res.mean_stitch_mm = round(sum(lengths) / len(lengths), 3)
        res.stitches_over_machine_limit = sum(1 for d in lengths if d > MACHINE_MAX_STITCH_MM)
        res.stitches_under_0_5mm = sum(1 for d in lengths if d < 0.5)
    bbox = max(design.width_mm * design.height_mm, 1.0)
    res.stitch_density_per_bbox_mm2 = round(design.stitch_count / bbox, 2)
    res.filled_area_mm2 = round(filled_area_mm2(design), 1)
    res.stitch_density_per_mm2 = round(design.stitch_count / max(res.filled_area_mm2, 1.0), 2)

    pitch, over = fill_row_geometry(design)
    res.fill_row_pitch_mm = pitch
    res.fill_rows_over_thread_width = over
    res.coverage_ratio = round(min(1.0, THREAD_WIDTH_MM / pitch), 3) if pitch else 0.0

    # Record which segmentation tier handled this fixture (rembg / floodfill /
    # corner). Recomputed here rather than threaded through the Design model, so
    # the data model stays untouched by the harness.
    try:
        import cv2
        import numpy as np

        from app.services import segmentation

        raw = path.read_bytes()
        bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        res.segmentation_method = segmentation.foreground_mask(bgr, raw)[1]
    except Exception:  # noqa: BLE001 - diagnostic only
        res.segmentation_method = None

    out_png = out_dir / f"{path.stem}-output.png"
    out_png.write_bytes(render_preview(design))
    res.output_png = _rel(out_png)
    return res


def build_grid(results: list[FixtureResult], out_dir: Path, tag: str) -> Path:
    """Labeled contact grid: each cell is one fixture's input beside its output."""
    from PIL import Image, ImageDraw, ImageFont

    THUMB, PAD, HEAD, FOOT = 260, 14, 26, 34
    CELL_W, CELL_H = THUMB * 2 + PAD * 3, THUMB + HEAD + FOOT + PAD
    COLS = 2
    rows = math.ceil(len(results) / COLS)

    def font(sz: int):
        for p in (
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ):
            if Path(p).is_file():
                return ImageFont.truetype(p, sz)
        return ImageFont.load_default()

    f_title, f_small = font(15), font(12)
    W, H = CELL_W * COLS, CELL_H * rows + 54
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 14), f"STITCHIQ digitizer bench — {tag}   (left: input art · right: stitch output)", font=font(19), fill=(15, 20, 35))

    for i, r in enumerate(results):
        ox, oy = (i % COLS) * CELL_W, 54 + (i // COLS) * CELL_H
        d.rectangle((ox + 4, oy + 2, ox + CELL_W - 6, oy + CELL_H - 6), outline=(210, 214, 222))
        d.text((ox + PAD, oy + 6), r.fixture, font=f_title, fill=(15, 20, 35))

        for j, src in enumerate((FIXTURE_DIR / f"{r.fixture}.png", REPO_ROOT / (r.output_png or ""))):
            box = (ox + PAD + j * (THUMB + PAD), oy + HEAD)
            if src.is_file():
                im = Image.open(src).convert("RGB")
                im.thumbnail((THUMB, THUMB))
                canvas = Image.new("RGB", (THUMB, THUMB), (244, 245, 248))
                canvas.paste(im, ((THUMB - im.width) // 2, (THUMB - im.height) // 2))
                sheet.paste(canvas, box)
            else:
                d.rectangle((*box, box[0] + THUMB, box[1] + THUMB), fill=(252, 232, 232))
                d.text((box[0] + 12, box[1] + THUMB // 2), "FAILED", font=f_title, fill=(170, 30, 30))

        if r.ok:
            types = " ".join(f"{k[:6]}×{v}" for k, v in sorted(r.stitch_types.items()))
            line1 = f"{r.stitch_count:,} st · {r.color_count} colors · {r.object_count} objects · {r.width_mm:.0f}×{r.height_mm:.0f}mm · {r.est_minutes:.1f} min"
            line2 = f"{types or 'no objects'} · {r.jump_count} jumps · max stitch {r.max_stitch_mm:.1f}mm"
            fill2 = (170, 30, 30) if r.stitches_over_machine_limit else (90, 96, 110)
        else:
            line1, line2, fill2 = f"ERROR: {(r.error or '')[:70]}", "", (170, 30, 30)
        d.text((ox + PAD, oy + HEAD + THUMB + 5), line1, font=f_small, fill=(60, 66, 80))
        d.text((ox + PAD, oy + HEAD + THUMB + 19), line2, font=f_small, fill=fill2)

    path = BENCH_DIR / f"{tag}-grid.png"  # headline artifact sits at the top level
    sheet.save(path)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default="v1-baseline", help="output name/folder under docs/benchmarks (default: v1-baseline)")
    ap.add_argument("--only", default=None, help="run a single fixture by stem, e.g. 08_mascot_detail")
    args = ap.parse_args()

    fixtures = sorted(p for p in FIXTURE_DIR.glob("*.png") if not p.name.startswith("_"))
    if args.only:
        fixtures = [p for p in fixtures if p.stem == args.only]
    if not fixtures:
        print(f"no fixtures found in {FIXTURE_DIR} — run tests/fixtures/quality_bench/_generate_fixtures.py", file=sys.stderr)
        return 1

    out_dir = BENCH_DIR / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[FixtureResult] = []
    for path in fixtures:
        print(f"▸ {path.stem} … ", end="", flush=True)
        r = run_fixture(path, out_dir)
        results.append(r)
        print(
            f"ERROR {r.error}" if not r.ok
            else f"{r.stitch_count:,} st · {r.color_count} colors · {r.object_count} obj · {r.runtime_s}s"
        )
        (out_dir / f"{r.fixture}.json").write_text(json.dumps(asdict(r), indent=2) + "\n")

    grid = build_grid(results, out_dir, args.tag)
    ok = [r for r in results if r.ok]
    summary = {
        "tag": args.tag,
        "rng_seed": RNG_SEED,
        "fixture_count": len(results),
        "failed": [r.fixture for r in results if not r.ok],
        "totals": {
            "stitches": sum(r.stitch_count for r in ok),
            "objects": sum(r.object_count for r in ok),
            "fixtures_with_over_limit_stitches": sum(1 for r in ok if r.stitches_over_machine_limit),
            "fixtures_with_warnings": sum(1 for r in ok if r.warnings),
            "runtime_s": round(sum(r.runtime_s for r in results), 2),
        },
        "fixtures": [asdict(r) for r in results],
    }
    summary_path = BENCH_DIR / f"{args.tag}-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"\ngrid    → {_rel(grid)}")
    print(f"summary → {_rel(summary_path)}")
    if summary["failed"]:
        print(f"FAILED  → {', '.join(summary['failed'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
