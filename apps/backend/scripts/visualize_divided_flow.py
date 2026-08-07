"""Visual evidence for divided Stitch Flow (v2 Part 63; helpers shared Part 66).

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
for _p in (str(BACKEND_ROOT), str(BACKEND_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _viz import ORANGE, crop_to_object, draw_segment, hstack_pad, label_bar, largest_tatami

from app.models.design import Point
from app.services.digitizer import digitize_image, rebuild_design
from app.services.stitch_render import render_design

OUT_DIR = BACKEND_ROOT.parents[1] / "docs" / "benchmarks"
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


def main() -> None:
    for name, maker, divide_frac, line_specs in SHAPES:
        ok, buf = cv2.imencode(".png", maker())
        assert ok
        cv2.setRNGSeed(1234)
        d = digitize_image(buf.tobytes(), "cotton", "100x100", 2)
        idx = largest_tatami(d)
        if idx is None:
            print(f"{name}: no tatami object, skipped")
            continue
        obj = d.objects[idx]

        divide = [Point(x=_at(obj, *divide_frac[0])[0], y=_at(obj, *divide_frac[0])[1]),
                  Point(x=_at(obj, *divide_frac[1])[0], y=_at(obj, *divide_frac[1])[1])]
        line_a = _dir_line(obj, *line_specs[0])
        line_b = _dir_line(obj, *line_specs[1])

        base = rebuild_design(d)
        crop, _origin = crop_to_object(_render(base), base, obj)
        auto_deg = float(obj.stitch_angle) % 180.0
        if auto_deg >= 179.75:  # -0.001 folds to 179.999; show the 0 it means
            auto_deg = 0.0
        panels = [label_bar(crop, f"automatic ({auto_deg:.0f} deg)")]

        single = rebuild_design(_with(d, idx, flow_line=line_a))
        crop, origin = crop_to_object(_render(single), single, obj)
        draw_segment(crop, origin, line_a)
        panels.append(label_bar(crop, f"one line ({line_specs[0][1]:.0f} deg)"))

        divided = rebuild_design(_with(d, idx, flow_divide=divide,
                                       flow_line=line_a, flow_line_b=line_b))
        crop, origin = crop_to_object(_render(divided), divided, obj)
        draw_segment(crop, origin, divide, ORANGE)
        draw_segment(crop, origin, line_a)
        draw_segment(crop, origin, line_b)
        panels.append(label_bar(
            crop, f"divided ({line_specs[0][1]:.0f} / {line_specs[1][1]:.0f} deg)"))

        out = hstack_pad(panels)
        out_path = OUT_DIR / f"part63-divided-{name}.png"
        cv2.imwrite(str(out_path), out)
        print(f"{name}: object #{idx}, wrote {out_path.name} {out.shape[1]}x{out.shape[0]}")


if __name__ == "__main__":
    main()
