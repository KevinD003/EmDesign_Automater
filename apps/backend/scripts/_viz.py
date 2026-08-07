"""Shared visualization helpers for evidence scripts (v2 Part 66).

Three scripts (visualize_flow_line, visualize_divided_flow, bench_competitor)
each carried their own label bar, panel stacking, object cropping and
largest-tatami finder. This is the one copy; the scripts import from here.
Import path: scripts run from apps/backend and tests add scripts/ to
sys.path via conftest, so a bare `import _viz` works in both.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.models.design import enum_str
from app.services.stitch_render import MARGIN_PX, PX_PER_MM

LABEL_H = 34
TEAL = (200, 180, 0)     # direction lines
ORANGE = (0, 138, 224)   # divide lines


def label_bar(img: np.ndarray, text: str, height: int = LABEL_H) -> np.ndarray:
    """The image with a dark caption bar stacked on top."""
    bar = np.full((height, img.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, text, (8, height - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (230, 230, 230), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def fit_width(img: np.ndarray, width: int) -> np.ndarray:
    h, w = img.shape[:2]
    return cv2.resize(img, (width, max(1, round(h * width / w))),
                      interpolation=cv2.INTER_AREA)


def hstack_pad(panels: list[np.ndarray], gap: int = 8) -> np.ndarray:
    """Stack panels of unequal height side by side, white-padded."""
    hmax = max(p.shape[0] for p in panels)
    padded = [cv2.copyMakeBorder(p, 0, hmax - p.shape[0], 0, gap,
                                 cv2.BORDER_CONSTANT, value=(255, 255, 255))
              for p in panels]
    return np.hstack(padded)


def largest_tatami(design) -> int | None:
    """Index of the largest TATAMI object with a contour, by bbox area."""
    best, best_area = None, -1.0
    for i, o in enumerate(design.objects):
        if enum_str(o.stitch_type) != "TATAMI" or not o.contour:
            continue
        xs = [p.x for p in o.contour]
        ys = [p.y for p in o.contour]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best, best_area = i, area
    return best


def crop_to_object(img: np.ndarray, design, obj, pad_mm: float = 2.0):
    """Crop a render to an object's bbox (+pad). Returns (crop, origin).

    ``origin`` = (ox_mm, oy_mm, bx_px, by_px), everything draw_segment needs
    to place design-mm points inside the crop.
    """
    xs = [s.x for s in design.stitches]
    ys = [s.y for s in design.stitches]
    ox, oy = min(xs), min(ys)
    cxs = [p.x for p in obj.contour]
    cys = [p.y for p in obj.contour]

    def px(v: float, o: float) -> int:
        return int((v - o) * PX_PER_MM) + MARGIN_PX

    h, w = img.shape[:2]
    x0 = max(0, px(min(cxs) - pad_mm, ox))
    y0 = max(0, px(min(cys) - pad_mm, oy))
    x1 = min(w, px(max(cxs) + pad_mm, ox))
    y1 = min(h, px(max(cys) + pad_mm, oy))
    return img[y0:y1, x0:x1].copy(), (ox, oy, x0, y0)


def draw_segment(crop: np.ndarray, origin, seg, bgr=TEAL) -> None:
    """Overlay a two-point design-mm segment (line + endpoint dots) on a crop."""
    ox, oy, bx, by = origin
    pts = [(int((p.x - ox) * PX_PER_MM) + MARGIN_PX - bx,
            int((p.y - oy) * PX_PER_MM) + MARGIN_PX - by) for p in seg]
    cv2.line(crop, pts[0], pts[-1], bgr, 3, cv2.LINE_AA)
    for p in pts:
        cv2.circle(crop, p, 6, bgr, -1, cv2.LINE_AA)
