"""Digitizer quality benchmark — run this to tell whether a change actually helped.

    python tools/make_corpus.py        # writes tools/corpus/ + tools/gt/ (once)
    python tools/bench_digitizer.py    # prints the metric table

Fidelity is measured by rasterizing the emitted stitch stream as thread strokes and
comparing the covered area against an EXACT ground-truth artwork mask (written by
make_corpus.py from the same drawing commands, so there is no heuristic in the ground
truth). Both are cropped to their bounding box first, so IoU measures shape fidelity
rather than placement.

What each column means:
  IoU_%        overlap of stitched area with the artwork — the headline "does it look
               like my picture" number
  coverage_%   how much of the artwork got stitched (low = missing/dropped detail)
  spill_%      how much stitching landed OUTSIDE the artwork (high = stray stitches)
  satin_objs   elements stitched as satin columns — text/outlines/swooshes SHOULD be
               satin; a design that is all TATAMI is the classic bad auto-digitize
  jumps/travel machine health: trims, thread tails, run time
  pct_lt_0.5   sub-0.5mm stitches; note a dense fill legitimately turns by one row
               pitch at the end of every row, so a nonzero value here is expected
"""
import os
import sys
import time
import math
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import cv2
import numpy as np

from app.services import digitizer
from app.services import optimizer

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")
THREAD_MM = 0.4  # rendered thread width


def gt_mask(path, canvas_shape):
    """Exact ground-truth artwork mask, cropped to its bbox and resized to the canvas.
    Cropping removes translation/scale differences so IoU measures SHAPE fidelity."""
    g = os.path.join(os.path.dirname(__file__), "gt", os.path.splitext(os.path.basename(path))[0] + ".png")
    m = cv2.imread(g, cv2.IMREAD_GRAYSCALE)
    if m is None:
        return None
    ys, xs = np.nonzero(m > 127)
    if len(xs) == 0:
        return None
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ch, cw = canvas_shape
    return cv2.resize(m, (cw, ch), interpolation=cv2.INTER_AREA)


def source_fg_mask(path, canvas_shape):
    """Non-background mask of the SOURCE image, CROPPED TO ITS FOREGROUND BBOX and
    resized to the rendered canvas. Cropping to the bbox removes any translation/scale
    mismatch between source and design frames, so IoU measures SHAPE fidelity only."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 3 and img.shape[2] == 4:
        fg = (img[..., 3] > 127).astype(np.uint8) * 255
    else:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        # Ground truth backdrop = MEDIAN colour of the border ring (robust to a subject
        # touching an edge, unlike a corner average).
        b = max(2, int(min(img.shape[:2]) * 0.02))
        ring = np.concatenate([img[:b, :].reshape(-1, 3), img[-b:, :].reshape(-1, 3),
                               img[:, :b].reshape(-1, 3), img[:, -b:].reshape(-1, 3)])
        bg = np.median(ring.astype(np.float32), axis=0)
        d = np.linalg.norm(img.astype(np.float32) - bg, axis=2)
        fg = (d > 40).astype(np.uint8) * 255
    ys, xs = np.nonzero(fg)
    if len(xs) == 0:
        return None
    fg = fg[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ch, cw = canvas_shape
    return cv2.resize(fg, (cw, ch), interpolation=cv2.INTER_AREA)


def render_stitches(design, px_per_mm):
    """Rasterize the stitch stream (STITCH runs only) into a coverage mask."""
    st = [s for s in design.stitches]
    xs = [s.x for s in st if s.command == "STITCH"]
    ys = [s.y for s in st if s.command == "STITCH"]
    if not xs:
        return None, (0, 0), (0, 0)
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    W, H = max(maxx - minx, 0.1), max(maxy - miny, 0.1)
    cw, ch = max(1, int(W * px_per_mm)), max(1, int(H * px_per_mm))
    canvas = np.zeros((ch, cw), np.uint8)
    t = max(1, int(round(THREAD_MM * px_per_mm)))
    prev = None
    for s in st:
        if s.command == "STITCH" and prev is not None and prev.command in ("STITCH",):
            p = (int((prev.x - minx) * px_per_mm), int((prev.y - miny) * px_per_mm))
            q = (int((s.x - minx) * px_per_mm), int((s.y - miny) * px_per_mm))
            cv2.line(canvas, p, q, 255, t)
        prev = s
    return canvas, (W, H), (minx, miny)


def stitch_stats(design):
    """Machine-health stats straight off the stream."""
    st = design.stitches
    lens = []
    prev = None
    for s in st:
        if prev is not None and s.command == "STITCH" and prev.command == "STITCH":
            lens.append(math.hypot(s.x - prev.x, s.y - prev.y))
        prev = s
    lens = np.array(lens) if lens else np.array([0.0])
    m = optimizer.path_metrics(design)
    return {
        "stitches": design.stitch_count,
        "objects": len(design.objects),
        "colors": len(design.color_stops),
        "satin_objs": sum(1 for o in design.objects if str(getattr(o.stitch_type, "value", o.stitch_type)) == "SATIN"),
        "trims": m.trims,
        "jumps": m.jump_count,
        "travel_mm": m.travel_mm,
        "len_mean": round(float(lens.mean()), 2),
        "len_max": round(float(lens.max()), 2),
        "pct_gt_12.7": round(float((lens > 12.7).mean() * 100), 2),
        "pct_lt_0.5": round(float(((lens > 0) & (lens < 0.5)).mean() * 100), 2),
    }


def run(path, **kw):
    data = open(path, "rb").read()
    t0 = time.time()
    d = digitizer.digitize_image(data, **kw)
    dt = time.time() - t0

    px_per_mm = 8.0
    rendered, (W, H), _ = render_stitches(d, px_per_mm)
    row = {"file": os.path.basename(path), "sec": round(dt, 2), "w_mm": d.width_mm, "h_mm": d.height_mm}
    row.update(stitch_stats(d))

    src = gt_mask(path, rendered.shape[:2]) if rendered is not None else None
    if rendered is not None and src is not None:
        a = (src > 127)
        b = (rendered > 127)
        inter = np.logical_and(a, b).sum()
        union = np.logical_or(a, b).sum() or 1
        row["IoU_%"] = round(inter / union * 100, 1)
        row["coverage_%"] = round(inter / max(a.sum(), 1) * 100, 1)   # of the artwork, how much got stitched
        row["spill_%"] = round(np.logical_and(b, ~a).sum() / max(b.sum(), 1) * 100, 1)  # stitched outside artwork
    try:
        q = optimizer.analyze_quality(d)
        row["quality"] = f"{q.grade}/{q.score}"
    except Exception as e:
        row["quality"] = f"err:{e}"
    return row


if __name__ == "__main__":
    files = sorted(os.listdir(CORPUS))
    rows = []
    for f in files:
        p = os.path.join(CORPUS, f)
        try:
            rows.append(run(p, fabric_type="cotton", hoop_size="100x100", max_colors=6))
        except Exception as e:
            rows.append({"file": f, "ERROR": f"{type(e).__name__}: {e}"})
    cols = ["file", "sec", "IoU_%", "coverage_%", "spill_%", "stitches", "objects", "colors",
            "satin_objs", "trims", "jumps", "travel_mm", "len_max", "pct_gt_12.7", "pct_lt_0.5", "quality"]
    print("\n" + " | ".join(c.ljust(11) for c in cols))
    print("-" * 150)
    for r in rows:
        if "ERROR" in r:
            print(r["file"].ljust(11), "->", r["ERROR"])
            continue
        print(" | ".join(str(r.get(c, "")).ljust(11) for c in cols))
    json.dump(rows, open(os.path.join(os.path.dirname(__file__), "baseline.json"), "w"), indent=1)
