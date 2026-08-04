"""Deterministic picture of what a Design actually sews (v2 Part 44, R003).

Four parts in a row caught a real defect only by looking at a render — background
thread on black cloth (41), a flooded lattice (40), a split lobe (39), a lost
bead-chain (40) — and every one of those pictures came from a throwaway script in
a scratchpad. Nothing was committed, so nothing was repeatable.

This is the renderer those scripts should have been. It is a pure function of the
Design: same design in, byte-identical PNG out, on any machine with the same
OpenCV. That determinism is what makes a baseline comparison meaningful — a
render that wobbles between runs can only produce false alarms, and a harness
that cries wolf gets muted.

It draws the stitch STREAM, not the object contours, because the stream is what
the machine receives. A region whose contour is perfect but whose fill never got
emitted looks correct in a contour drawing and blank here, which is exactly the
class of defect this exists to catch.
"""

from __future__ import annotations

from app.models.design import Design

# 8 px/mm keeps a 130x180mm hoop under 1500px, which is small enough to commit as
# a baseline and large enough that a 0.4mm thread is three pixels wide.
PX_PER_MM = 8.0
THREAD_WIDTH_MM = 0.4       # 40wt, the same figure the coverage metrics use
MARGIN_PX = 12
FABRIC_BGR = (222, 228, 232)  # light neutral: dark threads read, pale ones still shift pixels
UNKNOWN_THREAD_BGR = (0, 0, 255)  # a stitch we could not colour is a bug, so make it loud


def _cmd(stitch) -> str:
    return stitch.command.value if hasattr(stitch.command, "value") else str(stitch.command)


def _hex_to_bgr(hex_str: str) -> tuple[int, int, int]:
    h = (hex_str or "").lstrip("#")
    if len(h) != 6:
        return UNKNOWN_THREAD_BGR
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return UNKNOWN_THREAD_BGR
    return (b, g, r)


def _segment(canvas, p0, p1, half_px: float, bgr) -> None:
    """One stitch as its swept band: a rectangle of width ``2*half_px`` plus caps.

    Deliberately not ``cv2.line(..., thickness)``. That call's covered width
    depends on the segment ANGLE — measured elsewhere in this repo at 5.00px
    perpendicular for an axis-aligned segment against 4.25px at 45 degrees, for
    the same nominal width — because it stamps a pen along a Bresenham walk. In a
    picture that bias makes diagonal fills look thinner than horizontal ones, and
    a baseline comparison would then flag an honest angle change as a coverage
    change. `measure_stitch_quality._thread_segment` avoids it the same way.
    """
    import cv2
    import numpy as np

    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    length = float(np.hypot(dx, dy))
    if length < 1e-9:
        cv2.circle(canvas, (round(x0), round(y0)), max(1, round(half_px)),
                   bgr, -1, cv2.LINE_AA)
        return
    nx, ny = -dy / length * half_px, dx / length * half_px
    quad = np.array([
        [x0 + nx, y0 + ny], [x1 + nx, y1 + ny],
        [x1 - nx, y1 - ny], [x0 - nx, y0 - ny],
    ], np.float32)
    cv2.fillConvexPoly(canvas, np.round(quad).astype(np.int32), bgr, cv2.LINE_AA)
    for px, py in (p0, p1):
        cv2.circle(canvas, (round(px), round(py)), max(1, round(half_px)),
                   bgr, -1, cv2.LINE_AA)


def render_design(design: Design, *, px_per_mm: float = PX_PER_MM,
                  thread_width_mm: float = THREAD_WIDTH_MM):
    """Render the sewn stream to a BGR image. Pure function of ``design``.

    Colour follows the stream's own COLOR_CHANGE commands rather than the objects'
    ``color_stop`` field, because that is how the machine resolves colour: whatever
    thread is on the needle when the stitch is made. If the two ever disagree, the
    picture shows what would actually be sewn.
    """
    import numpy as np

    stops = list(design.color_stops or [])
    xs = [s.x for s in design.stitches]
    ys = [s.y for s in design.stitches]
    if not xs:
        # An empty design is a real outcome (nine corpus designs still do it), so
        # render a blank swatch rather than raising — the diff should show it.
        return np.full((64, 64, 3), FABRIC_BGR, np.uint8)

    w = round((max(xs) - min(xs)) * px_per_mm) + 2 * MARGIN_PX
    h = round((max(ys) - min(ys)) * px_per_mm) + 2 * MARGIN_PX
    ox, oy = min(xs), min(ys)
    canvas = np.full((max(h, 1), max(w, 1), 3), FABRIC_BGR, np.uint8)

    half_px = thread_width_mm * px_per_mm / 2.0
    stop_idx = 0
    colour = _hex_to_bgr(stops[0].hex) if stops else UNKNOWN_THREAD_BGR
    prev = None
    for s in design.stitches:
        cmd = _cmd(s)
        if cmd == "COLOR_CHANGE":
            stop_idx += 1
            colour = _hex_to_bgr(stops[stop_idx].hex) if stop_idx < len(stops) else UNKNOWN_THREAD_BGR
            prev = None
            continue
        here = ((s.x - ox) * px_per_mm + MARGIN_PX, (s.y - oy) * px_per_mm + MARGIN_PX)
        if cmd == "STITCH":
            if prev is not None:
                _segment(canvas, prev, here, half_px, colour)
            prev = here
        elif cmd == "JUMP":
            # The needle travels without thread: move the pen, draw nothing.
            prev = here
        else:  # TRIM, STOP, END — the chain is broken
            prev = None
    return canvas


def encode_png(image) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("PNG encode failed")
    return buf.tobytes()
