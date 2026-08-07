"""Visual evidence for Stitch Flow (v2 Part 62).

For a fixture, digitize, pick the largest tatami object, and render the object
crop three ways: automatic angle, a flow line at +45°, and one at +90°. The
drawn line is overlaid in teal so the picture shows both the control and its
effect. Output: docs/benchmarks/part62-flow-<fixture>.png (side-by-side).

Run from apps/backend: .venv/bin/python scripts/visualize_flow_line.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.models.design import Point
from app.services.digitizer import digitize_image, rebuild_design
from app.services.stitch_render import MARGIN_PX, PX_PER_MM, render_design

OUT_DIR = BACKEND_ROOT.parents[1] / "docs" / "benchmarks"
FIXTURES = ["01_flat_2color_logo.png", "07_circular_badge.png"]
LABEL_H = 34


def _largest_tatami(design):
    best, best_area = None, -1.0
    for i, o in enumerate(design.objects):
        st = o.stitch_type.value if hasattr(o.stitch_type, "value") else o.stitch_type
        if st != "TATAMI" or not o.contour:
            continue
        xs = [p.x for p in o.contour]
        ys = [p.y for p in o.contour]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best, best_area = i, area
    return best


def _with_line(design, idx, line):
    objs = list(design.objects)
    objs[idx] = objs[idx].model_copy(update={"flow_line": line})
    return design.model_copy(update={"objects": objs})


def _crop(img, design, obj, pad_mm=2.0):
    xs = [s.x for s in design.stitches]
    ys = [s.y for s in design.stitches]
    ox, oy = min(xs), min(ys)
    cxs = [p.x for p in obj.contour]
    cys = [p.y for p in obj.contour]
    x0 = int((min(cxs) - pad_mm - ox) * PX_PER_MM) + MARGIN_PX
    x1 = int((max(cxs) + pad_mm - ox) * PX_PER_MM) + MARGIN_PX
    y0 = int((min(cys) - pad_mm - oy) * PX_PER_MM) + MARGIN_PX
    y1 = int((max(cys) + pad_mm - oy) * PX_PER_MM) + MARGIN_PX
    h, w = img.shape[:2]
    return img[max(0, y0):min(h, y1), max(0, x0):min(w, x1)].copy(), (ox, oy)


def _draw_line(crop, origin, obj, line, pad_mm=2.0):
    ox, oy = origin
    cxs = [p.x for p in obj.contour]
    cys = [p.y for p in obj.contour]
    bx = int((min(cxs) - pad_mm - ox) * PX_PER_MM) + MARGIN_PX
    by = int((min(cys) - pad_mm - oy) * PX_PER_MM) + MARGIN_PX
    pts = [(int((p.x - ox) * PX_PER_MM) + MARGIN_PX - bx,
            int((p.y - oy) * PX_PER_MM) + MARGIN_PX - by) for p in line]
    cv2.line(crop, pts[0], pts[1], (200, 180, 0), 3, cv2.LINE_AA)
    for p in pts:
        cv2.circle(crop, p, 6, (200, 180, 0), -1, cv2.LINE_AA)


def _label(img, text):
    bar = np.full((LABEL_H, img.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, text, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (230, 230, 230), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def main() -> None:
    for fx in FIXTURES:
        path = BACKEND_ROOT / "tests/fixtures/quality_bench" / fx
        cv2.setRNGSeed(1234)
        d = digitize_image(path.read_bytes(), "cotton", "100x100", 2)
        idx = _largest_tatami(d)
        if idx is None:
            print(f"{fx}: no tatami object, skipped")
            continue
        obj = d.objects[idx]
        cx = sum(p.x for p in obj.contour) / len(obj.contour)
        cy = sum(p.y for p in obj.contour) / len(obj.contour)

        base = rebuild_design(d)
        panels = []
        crop, origin = _crop(render_design(base), base, obj)
        panels.append(_label(crop, f"automatic ({obj.stitch_angle:.0f} deg)"))

        for delta in (45.0, 90.0):
            ang = (float(obj.stitch_angle) + delta) % 180.0
            a = math.radians(ang)
            line = [Point(x=cx - 6 * math.cos(a), y=cy - 6 * math.sin(a)),
                    Point(x=cx + 6 * math.cos(a), y=cy + 6 * math.sin(a))]
            flowed = rebuild_design(_with_line(d, idx, line))
            crop, origin = _crop(render_design(flowed), flowed, obj)
            _draw_line(crop, origin, obj, line)
            panels.append(_label(crop, f"flow line at {ang:.0f} deg"))

        hmax = max(p.shape[0] for p in panels)
        padded = [cv2.copyMakeBorder(p, 0, hmax - p.shape[0], 0, 8, cv2.BORDER_CONSTANT,
                                     value=(255, 255, 255)) for p in panels]
        out = np.hstack(padded)
        out_path = OUT_DIR / f"part62-flow-{fx.split('_')[0]}.png"
        cv2.imwrite(str(out_path), out)
        print(f"{fx}: object #{idx} ({obj.name}), wrote {out_path.name} {out.shape[1]}x{out.shape[0]}")


if __name__ == "__main__":
    main()
