"""Draw the direction field so it can be looked at (v2 Part 50, R004-impl D1).

D1's deliverable is a picture, not a number. The field is consumed by nothing, so
the only way to judge whether it is worth taking to D2 is to put it beside the
artwork and see whether the flow is what a digitizer would have chosen.

    scripts/visualise_direction_field.py                  # all ten bench fixtures
    scripts/visualise_direction_field.py --only 07_circular_badge
    scripts/visualise_direction_field.py --image path.jpg --hoop 360x350 --colors 12

Each panel is source | current per-object angles | solved field, so the
comparison is visible rather than asserted.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
for p in (BACKEND, BACKEND / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.services import direction_field as DF
from app.services.digitizer import digitize_image

OUT_DIR = REPO / "docs" / "benchmarks" / "v2-part50-field"

STEP_PX = 18          # quiver spacing
ARROW_LEN = 13        # half-length of each stroke
BG = (250, 250, 248)


def _regions_and_mask(design, shape):
    """Rasterise the design's objects into (mask, [(region, angle_rad)])."""
    h, w = shape
    pts = [p for o in design.objects for p in (o.contour or [])]
    if not pts:
        return None, []
    ox, oy = min(p.x for p in pts), min(p.y for p in pts)
    ex, ey = max(p.x for p in pts), max(p.y for p in pts)
    sx, sy = w / max(ex - ox, 1e-6), h / max(ey - oy, 1e-6)

    def to_px(p):
        return [int(np.clip((p.x - ox) * sx, 0, w - 1)),
                int(np.clip((p.y - oy) * sy, 0, h - 1))]

    mask = np.zeros((h, w), np.uint8)
    regions = []
    for o in design.objects:
        if not o.contour:
            continue
        one = np.zeros((h, w), np.uint8)
        cv2.fillPoly(one, [np.array([to_px(p) for p in o.contour], np.int32)], 255)
        for hole in (o.holes or []):
            cv2.fillPoly(one, [np.array([to_px(p) for p in hole], np.int32)], 0)
        mask = cv2.bitwise_or(mask, one)
        regions.append((one, math.radians(float(o.stitch_angle))))
    return mask, regions


def draw_field(field, title: str, base=None):
    """Quiver over the mask. Colour encodes confidence, so a washed-out area reads
    as 'the field is unsure here' rather than silently looking as good as the rest."""
    h, w = field.mask.shape[:2]
    canvas = np.full((h, w, 3), BG, np.uint8) if base is None else base.copy()
    canvas[field.mask == 0] = BG
    theta = field.theta
    conf = field.coherence
    for y in range(STEP_PX, h - STEP_PX, STEP_PX):
        for x in range(STEP_PX, w - STEP_PX, STEP_PX):
            if not field.mask[y, x]:
                continue
            cval = float(conf[y, x])
            if cval < 0.02:
                continue
            a = float(theta[y, x])
            dx, dy = ARROW_LEN * math.cos(a), ARROW_LEN * math.sin(a)
            shade = int(30 + (1.0 - min(cval, 1.0)) * 170)
            cv2.line(canvas, (int(x - dx), int(y - dy)), (int(x + dx), int(y + dy)),
                     (shade, shade, 220 - shade // 2), 2, cv2.LINE_AA)
    cv2.rectangle(canvas, (0, 0), (w - 1, h - 1), (200, 200, 200), 1)
    cv2.putText(canvas, title, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1, cv2.LINE_AA)
    return canvas


def panel_for(name: str, src, design, out_path: Path) -> dict:
    h, w = src.shape[:2]
    mask, regions = _regions_and_mask(design, (h, w))
    if mask is None or not regions:
        return {"name": name, "skipped": "no regions with contours"}

    t0 = time.perf_counter()
    solved = DF.solve(mask)
    solve_s = time.perf_counter() - t0
    per_obj = DF.per_object_field(mask, regions)

    left = src.copy()
    cv2.putText(left, f"{name}  ({len(regions)} regions)", (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(left, f"{name}  ({len(regions)} regions)", (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1, cv2.LINE_AA)
    strip = np.hstack([
        left,
        draw_field(per_obj, "current: one angle per region"),
        draw_field(solved, f"solved field  ({solve_s * 1000:.0f} ms)"),
    ])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scale = min(1.0, 1800 / strip.shape[1])
    if scale < 1.0:
        strip = cv2.resize(strip, (int(strip.shape[1] * scale), int(strip.shape[0] * scale)),
                           interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out_path), strip)
    return {"name": name, "regions": len(regions), "solve_s": round(solve_s, 3),
            "mask_px": int((mask > 0).sum()), "out": str(out_path)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--image", help="score an arbitrary image instead of the bench")
    ap.add_argument("--hoop", default="130x180")
    ap.add_argument("--colors", type=int, default=6)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    out_dir = Path(args.out)

    if args.image:
        src = cv2.imread(args.image)
        if src is None:
            raise SystemExit(f"could not read {args.image}")
        cv2.setRNGSeed(20260728)
        design = digitize_image(Path(args.image).read_bytes(), "cotton", args.hoop, args.colors)
        stem = Path(args.image).stem
        print(panel_for(stem, src, design, out_dir / f"{stem}.png"))
        return 0

    import visual_regression as VR

    names = [args.only] if args.only else sorted(VR.FIXTURES)
    rows = []
    for name in names:
        src = cv2.imread(str(VR.FIXTURE_DIR / f"{name}.png"))
        design = VR.render_fixture(name)[1]
        r = panel_for(name, src, design, out_dir / f"{name}.png")
        rows.append(r)
        if "skipped" in r:
            print(f"  {name:26s} skipped: {r['skipped']}")
        else:
            print(f"  {name:26s} {r['regions']:4d} regions  "
                  f"{r['mask_px']:8d} px  solve {r['solve_s'] * 1000:6.1f} ms")
    ok = [r for r in rows if "solve_s" in r]
    if ok:
        print(f"\nsolve time: min {min(r['solve_s'] for r in ok) * 1000:.1f} ms  "
              f"max {max(r['solve_s'] for r in ok) * 1000:.1f} ms")
    print(f"panels -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
