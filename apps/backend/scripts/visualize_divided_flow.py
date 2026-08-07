"""Visual evidence for divided Stitch Flow (v2 Part 63).

Three curved shapes where one straight direction is visibly inadequate —
a crescent, a bent leaf (chevron band) and a bowl (half annulus) — each
digitized for real and rendered three ways:

  automatic angle | Part 62 single line | Part 63 divide + one line per side

Direction lines are drawn in teal, the divide in orange, so every panel shows
the control together with its effect. Output:
docs/benchmarks/part63-divided-<shape>.png

Run from apps/backend: .venv/bin/python scripts/visualize_divided_flow.py
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
LABEL_H = 34
# A mid-tone ink: dark enough to classify as foreground, light enough that the
# rendered thread rows leave visible texture in every panel.
INK = (60, 120, 200)


def _crescent() -> np.ndarray:
    img = np.full((900, 900, 3), 255, np.uint8)
    cv2.circle(img, (450, 420), 300, INK, -1, cv2.LINE_AA)
    cv2.circle(img, (450, 250), 270, (255, 255, 255), -1, cv2.LINE_AA)
    return img


def _bent_leaf() -> np.ndarray:
    img = np.full((900, 900, 3), 255, np.uint8)
    pts = np.array([[170, 680], [450, 260], [730, 680]], np.int32)
    cv2.polylines(img, [pts], False, INK, 150, cv2.LINE_AA)
    return img


def _bowl() -> np.ndarray:
    img = np.full((900, 900, 3), 255, np.uint8)
    cv2.circle(img, (450, 380), 320, INK, -1, cv2.LINE_AA)
    cv2.circle(img, (450, 380), 175, (255, 255, 255), -1, cv2.LINE_AA)
    img[:380] = 255  # keep the bottom half: a bowl with both arms pointing up
    return img


# Each shape: divide through the object (bbox fractions), and one direction
# line per side, placed at a bbox fraction with an angle chosen so rows run
# ACROSS the local band — what one global angle cannot do on both halves.
SHAPES = [
    ("crescent", _crescent,
     ((0.5, -0.1), (0.5, 1.1)),                       # vertical divide
     [((0.22, 0.45), 40.0), ((0.78, 0.45), 140.0)]),  # across each horn
    ("bent-leaf", _bent_leaf,
     ((0.5, -0.1), (0.5, 1.1)),                       # vertical divide at the bend
     [((0.25, 0.60), 37.0), ((0.75, 0.60), 143.0)]),  # across each limb
    ("bowl", _bowl,
     ((-0.1, 0.35), (1.1, 0.35)),                     # horizontal divide below the arms
     [((0.10, 0.15), 0.0), ((0.50, 0.85), 90.0)]),    # across the arms / across the base
]


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


def _with(design, idx, **fields):
    objs = list(design.objects)
    objs[idx] = objs[idx].model_copy(update=fields)
    return design.model_copy(update={"objects": objs})


def _bbox(obj):
    xs = [p.x for p in obj.contour]
    ys = [p.y for p in obj.contour]
    return min(xs), min(ys), max(xs), max(ys)


def _at(obj, fx: float, fy: float) -> tuple[float, float]:
    x0, y0, x1, y1 = _bbox(obj)
    return x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)


def _dir_line(obj, frac, ang_deg: float, half_mm: float = 6.0):
    cx, cy = _at(obj, *frac)
    a = math.radians(ang_deg)
    return [Point(x=cx - half_mm * math.cos(a), y=cy - half_mm * math.sin(a)),
            Point(x=cx + half_mm * math.cos(a), y=cy + half_mm * math.sin(a))]


def _render(design):
    # Slightly thinner than physical thread so row direction stays visible even
    # at axis-aligned angles, where full-width rows tile into a solid block.
    return render_design(design, thread_width_mm=0.28)


def _crop(img, design, obj, pad_mm=2.0):
    xs = [s.x for s in design.stitches]
    ys = [s.y for s in design.stitches]
    ox, oy = min(xs), min(ys)
    x0, y0, x1, y1 = _bbox(obj)
    px = lambda v, o: int((v - o) * PX_PER_MM) + MARGIN_PX
    h, w = img.shape[:2]
    crop = img[max(0, px(y0 - pad_mm, oy)):min(h, px(y1 + pad_mm, oy)),
               max(0, px(x0 - pad_mm, ox)):min(w, px(x1 + pad_mm, ox))].copy()
    return crop, (ox, oy, max(0, px(x0 - pad_mm, ox)), max(0, px(y0 - pad_mm, oy)))


def _draw_seg(crop, origin, seg, bgr):
    ox, oy, bx, by = origin
    pts = [(int((p.x - ox) * PX_PER_MM) + MARGIN_PX - bx,
            int((p.y - oy) * PX_PER_MM) + MARGIN_PX - by) for p in seg]
    cv2.line(crop, pts[0], pts[1], bgr, 3, cv2.LINE_AA)
    for p in pts:
        cv2.circle(crop, p, 6, bgr, -1, cv2.LINE_AA)


def _label(img, text):
    bar = np.full((LABEL_H, img.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, text, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (230, 230, 230), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def main() -> None:
    for name, maker, divide_frac, line_specs in SHAPES:
        ok, buf = cv2.imencode(".png", maker())
        assert ok
        cv2.setRNGSeed(1234)
        d = digitize_image(buf.tobytes(), "cotton", "100x100", 2)
        idx = _largest_tatami(d)
        if idx is None:
            print(f"{name}: no tatami object, skipped")
            continue
        obj = d.objects[idx]

        divide = [Point(x=_at(obj, *divide_frac[0])[0], y=_at(obj, *divide_frac[0])[1]),
                  Point(x=_at(obj, *divide_frac[1])[0], y=_at(obj, *divide_frac[1])[1])]
        line_a = _dir_line(obj, *line_specs[0])
        line_b = _dir_line(obj, *line_specs[1])

        panels = []
        base = rebuild_design(d)
        crop, origin = _crop(_render(base), base, obj)
        auto_deg = float(obj.stitch_angle) % 180.0
        if auto_deg >= 179.75:  # -0.001 folds to 179.999; show the 0 it means
            auto_deg = 0.0
        panels.append(_label(crop, f"automatic ({auto_deg:.0f} deg)"))

        single = rebuild_design(_with(d, idx, flow_line=line_a))
        crop, origin = _crop(_render(single), single, obj)
        _draw_seg(crop, origin, line_a, (200, 180, 0))
        panels.append(_label(crop, f"one line ({line_specs[0][1]:.0f} deg)"))

        divided = rebuild_design(_with(d, idx, flow_divide=divide,
                                       flow_line=line_a, flow_line_b=line_b))
        crop, origin = _crop(_render(divided), divided, obj)
        _draw_seg(crop, origin, divide, (0, 138, 224))
        _draw_seg(crop, origin, line_a, (200, 180, 0))
        _draw_seg(crop, origin, line_b, (200, 180, 0))
        panels.append(_label(
            crop, f"divided ({line_specs[0][1]:.0f} / {line_specs[1][1]:.0f} deg)"))

        hmax = max(p.shape[0] for p in panels)
        padded = [cv2.copyMakeBorder(p, 0, hmax - p.shape[0], 0, 8, cv2.BORDER_CONSTANT,
                                     value=(255, 255, 255)) for p in panels]
        out = np.hstack(padded)
        out_path = OUT_DIR / f"part63-divided-{name}.png"
        cv2.imwrite(str(out_path), out)
        print(f"{name}: object #{idx}, wrote {out_path.name} {out.shape[1]}x{out.shape[0]}")


if __name__ == "__main__":
    main()
