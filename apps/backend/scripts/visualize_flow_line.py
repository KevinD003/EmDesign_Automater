"""Visual evidence for Stitch Flow (v2 Part 62; helpers shared since Part 66).

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

BACKEND_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND_ROOT), str(BACKEND_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _viz import crop_to_object, draw_segment, hstack_pad, label_bar, largest_tatami

from app.models.design import Point
from app.services.digitizer import digitize_image, rebuild_design
from app.services.stitch_render import render_design

OUT_DIR = BACKEND_ROOT.parents[1] / "docs" / "benchmarks"
FIXTURES = ["01_flat_2color_logo.png", "07_circular_badge.png"]


def _with_line(design, idx, line):
    objs = list(design.objects)
    objs[idx] = objs[idx].model_copy(update={"flow_line": line})
    return design.model_copy(update={"objects": objs})


def main() -> None:
    for fx in FIXTURES:
        path = BACKEND_ROOT / "tests/fixtures/quality_bench" / fx
        cv2.setRNGSeed(1234)
        d = digitize_image(path.read_bytes(), "cotton", "100x100", 2)
        idx = largest_tatami(d)
        if idx is None:
            print(f"{fx}: no tatami object, skipped")
            continue
        obj = d.objects[idx]
        cx = sum(p.x for p in obj.contour) / len(obj.contour)
        cy = sum(p.y for p in obj.contour) / len(obj.contour)

        base = rebuild_design(d)
        crop, _origin = crop_to_object(render_design(base), base, obj)
        panels = [label_bar(crop, f"automatic ({obj.stitch_angle:.0f} deg)")]

        for delta in (45.0, 90.0):
            ang = (float(obj.stitch_angle) + delta) % 180.0
            a = math.radians(ang)
            line = [Point(x=cx - 6 * math.cos(a), y=cy - 6 * math.sin(a)),
                    Point(x=cx + 6 * math.cos(a), y=cy + 6 * math.sin(a))]
            flowed = rebuild_design(_with_line(d, idx, line))
            crop, origin = crop_to_object(render_design(flowed), flowed, obj)
            draw_segment(crop, origin, line)
            panels.append(label_bar(crop, f"flow line at {ang:.0f} deg"))

        out = hstack_pad(panels)
        out_path = OUT_DIR / f"part62-flow-{fx.split('_')[0]}.png"
        cv2.imwrite(str(out_path), out)
        print(f"{fx}: object #{idx} ({obj.name}), wrote {out_path.name} "
              f"{out.shape[1]}x{out.shape[0]}")


if __name__ == "__main__":
    main()
