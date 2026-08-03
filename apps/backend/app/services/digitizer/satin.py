"""Satin generators built on the column geometry, plus borders."""

from __future__ import annotations

from app.services.digitizer import constants
from app.services.digitizer.columns import (
    _assign_boundary,
    _axis_frame,
    _axis_samples,
    _boundary_points,
    _column_ends,
    _emit_columns,
    _enforce_floor,
    _raycast_columns,
)
from app.services.digitizer.constants import (
    FILL_STAGGER_ROWS,
    HIRES_CROP_PAD_PX,
    SATIN_MAX_W_MM,
    SMALL_STROKE_MAX_SCALE,
    SMALL_STROKE_PX,
)
from app.services.digitizer.geometry import (
    _dist,
    _distance_transform,
    _fg_window,
    _resample_closed,
    _uncovered_mask,
    _warp_fit,
)
from app.services.digitizer.skeleton import (
    _axis_branches,
    _free_ends,
)


def _satin_zigzag(region, rect, step_px: int, connect_px: float, max_step_px: int = 1_000_000):
    """Satin column for a narrow elongated region.

    Rotates the mask so the region's long axis is horizontal, walks columns at
    ``step_px``, emits alternating top/bottom edge points (the zigzag), then maps
    the points back through the inverse rotation. Cross-width zigs longer than
    ``max_step_px`` are subdivided so no stitch exceeds the machine limit — this
    keeps even a mis-classified wide column machine-valid. Returns [(x, y, is_jump)].
    """
    import numpy as np

    (cx, cy), (rw, rh), ang = rect
    if rw < rh:  # normalize: long axis → horizontal
        ang += 90.0
    rot, Minv = _warp_fit(region, (cx, cy), ang)
    _, w = rot.shape

    def inv(px_: float, py_: float) -> tuple[float, float]:
        return (
            float(Minv[0, 0] * px_ + Minv[0, 1] * py_ + Minv[0, 2]),
            float(Minv[1, 0] * px_ + Minv[1, 1] * py_ + Minv[1, 2]),
        )

    pts: list[tuple[float, float, bool]] = []
    prev: tuple[float, float] | None = None
    top = True
    for x in range(0, w, step_px):
        rows = np.flatnonzero(rot[:, x])
        if rows.size < 2:
            continue
        y0, y1 = int(rows[0]), int(rows[-1])
        (ax, ay), (bx, by) = ((x, y0), (x, y1)) if top else ((x, y1), (x, y0))
        a = inv(ax, ay)
        b = inv(bx, by)
        jump = prev is not None and _dist(prev, a) > connect_px
        pts.append((a[0], a[1], jump))
        prev = a
        n = max(1, int(np.ceil(_dist(a, b) / max_step_px)))
        if n > 1:
            # Staggered splits, same reason as `_emit_columns` (v2 Part 28):
            # this is the path a USER-forced wide satin takes through rebuild,
            # and aligned split points there perforate a line down the column.
            phase = ((x // max(1, step_px)) % FILL_STAGGER_ROWS) / FILL_STAGGER_ROWS
            guard = 0.3 / n
            for i in range(n):
                f = (i + phase) / n
                if guard <= f <= 1.0 - guard:
                    p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
                    pts.append((p[0], p[1], False))
        pts.append((b[0], b[1], False))
        prev = b
        top = not top
    if pts:
        pts[0] = (pts[0][0], pts[0][1], True)  # enter the column with a jump
    return pts


def _satin_columns(region, binary, dist, skel, used, step: int, max_step_px: int, max_half_px: float,
                   extra_px: float, floor_px: float = 0.0):
    """Lay every branch's columns between corresponding points on its two boundaries."""
    pts: list[tuple[float, float, bool]] = []
    prev_end: tuple[float, float] | None = None
    frames = [_axis_frame(s, dist) for s in used]
    assigned = _assign_boundary(_boundary_points(region), frames)
    last_pair = None
    for frame, samples, owned in zip(frames, used, assigned):
        pairs = _column_ends(frame, owned, float(step), max_half_px, extra_px, floor_px,
                             _free_ends(skel, samples))
        if not pairs:
            # Boundary too sparse to pair (a two-pixel stub, a region whose
            # contour the thinning did not survive). Fall back to the Part 2.5
            # ray-cast column for THIS branch only, so an edge case can never
            # delete a stroke from the design or empty out a satin object.
            # The fallback paces off axis samples, so it needs the same floor.
            pairs = _enforce_floor(_raycast_columns(binary, samples, max_half_px, extra_px), floor_px, False)
        # Trim the SEAM only. Branches are emitted back to back unless far enough
        # apart to earn a JUMP, so the first column of a branch can land in the
        # last one's holes. Trimming from the front cannot disturb a ring's wrap
        # guarantee, which only widens when a leading column goes.
        while floor_px > 0.0 and pairs and last_pair is not None and min(
            _dist(last_pair[0], pairs[0][0]), _dist(last_pair[1], pairs[0][1])
        ) < floor_px:
            pairs = pairs[1:]
        if not pairs:
            continue
        last_pair = pairs[-1]
        emitted, prev_end = _emit_columns(pairs, max_step_px, prev_end, float(step))
        pts.extend(emitted)
    if pts:
        pts[0] = (pts[0][0], pts[0][1], True)
    return pts


def _skeleton_satin_hires(region, mm_per_px, sat_step, max_step_px, extra_half_px,
                          stroke_px: float):
    """Run `_skeleton_satin` at scaled-up resolution for thin-stroke regions.

    The scale factor targets SMALL_STROKE_PX of resolution across the typical
    stroke; outputs are scaled back so callers stay in working pixels. Cubic
    upscale then threshold, so the mask edge is smoothed rather than a magnified
    staircase.
    """
    import cv2
    import numpy as np

    f = 1
    if stroke_px > 0 and stroke_px < SMALL_STROKE_PX:
        f = min(SMALL_STROKE_MAX_SCALE, max(2, round(SMALL_STROKE_PX / stroke_px)))
    if f == 1:
        return _skeleton_satin(region, mm_per_px, sat_step, max_step_px,
                               extra_half_px=extra_half_px)
    # Upscale only the region's own box, then paste into the full-size canvas —
    # the COORDINATE FRAME must stay absolute (see `_skeleton_branches`: a closed
    # loop starts at an arbitrary set element, so translating the input reorders
    # every column and changes the stitch stream). Exact because INTER_CUBIC
    # reads 4x4 and the window carries >= HIRES_CROP_PAD_PX zero px on every
    # side it did not clamp to the canvas edge, where the crop border IS the
    # canvas border and replicates identically; outside the window the cubic
    # samples see only zeros, which is what `big` is pre-filled with.
    win = _fg_window(region, HIRES_CROP_PAD_PX)
    big = np.zeros((region.shape[0] * f, region.shape[1] * f), region.dtype)
    if win is not None:
        y0, y1, x0, x1 = win
        up = cv2.resize(region[y0:y1, x0:x1], ((x1 - x0) * f, (y1 - y0) * f),
                        interpolation=cv2.INTER_CUBIC)
        big[y0 * f:y1 * f, x0 * f:x1 * f] = (up > 127).astype(region.dtype) * 255
    cand, median_w, wide_mask, axis_pts = _skeleton_satin(
        big, mm_per_px / f, sat_step * f, max_step_px * f,
        extra_half_px=extra_half_px * f,
    )
    cand = [(x / f, y / f, j) for x, y, j in cand]
    axis_pts = [(x / f, y / f, j) for x, y, j in axis_pts]
    wide_mask = cv2.resize(wide_mask, (region.shape[1], region.shape[0]),
                           interpolation=cv2.INTER_AREA)
    wide_mask = (wide_mask > 127).astype(region.dtype) * 255
    return cand, median_w, wide_mask, axis_pts


def _skeleton_satin(region, mm_per_px: float, spacing_px: int, max_step_px: int, extra_half_px: float = 0.0):
    """Satin columns that follow a stroke, bounded by the stroke's own outline.

    Thins the region to its medial axis to find the strokes and their topology,
    then lays each column between CORRESPONDING points on the two boundary arcs
    that belong to that branch (v2 Part 4). Column ends are therefore boundary
    points by construction — they cannot fall short of the outline or overshoot
    it, which is what a centreline offset by a measured half-width could not
    guarantee. Width still varies along the stroke, as script faces need.

    Returns ``(points, median_width_mm, wide_mask, axis_points)``. Where the
    stroke is wider than satin can span, the column is clamped to the satin limit
    and the unreachable remainder comes back as ``wide_mask`` for the caller to
    tatami — the per-segment fallback, rather than dropping the whole glyph.
    """
    import cv2
    import numpy as np

    binary = (region > 0).astype(np.uint8)
    empty = np.zeros_like(binary)
    if cv2.countNonZero(binary) == 0:
        return [], 0.0, empty, []
    dist = _distance_transform(binary)
    skel, branches = _axis_branches(binary, dist, mm_per_px)
    if not branches:
        return [], 0.0, empty, []

    step = max(1, int(spacing_px))
    # Half-width is clamped to the satin limit. At a corner or a letter junction
    # ('M' vertex, 'U' bowl join) the distance transform spikes — the medial axis
    # there is genuinely far from every edge — even though the STROKE is no
    # wider. Unclamped, those samples throw a single stitch clear across the
    # glyph. Measured on "SUMMIT": stems are 3.66mm median but the 90th
    # percentile hits 7.32mm purely from junctions.
    max_half_px = (SATIN_MAX_W_MM / 2.0) / max(mm_per_px, 1e-6)

    used, widths, centre_track = _axis_samples(branches, dist, binary, step, mm_per_px)
    floor_px = (constants._PENETRATION_FLOOR_MM / max(mm_per_px, 1e-6)) if constants._PENETRATION_FLOOR_MM else 0.0
    pts = _satin_columns(region, binary, dist, skel, used, step, max_step_px, max_half_px,
                         extra_half_px, floor_px)
    # Report the MEDIAN stroke width, not the share of samples over the limit:
    # junction spikes make the mean and the over-limit share useless as a
    # "is this a stroke or a blob?" test.
    median_w = float(np.median(widths)) if widths else 0.0
    # Centreline for the underlay, in the same order the columns were laid.
    # `_center_walk` cannot be used once satin covers curved shapes: it walks the
    # midline of the min-area BOUNDING RECT, which for a ring is a diameter
    # straight across the hole, so every ring picked up a bogus line through it.
    # The third element keeps the tuple shape `_axis_underlay` consumes; that
    # function derives its own jump flags from the travelled distance rather than
    # trusting a flag set here, because branch bookkeeping is exactly what went
    # wrong first (see `_axis_underlay`).
    axis_pts = [(float(x), float(y), False) for (x, y) in centre_track]

    return pts, median_w, _uncovered_mask(binary, skel, max_half_px), axis_pts


def _satin_border(poly_px, width_px: float, step_px: int, connect_px: float,
                  floor_px: float = 0.0):
    """Satin border along a closed contour: resample the outline, then at each
    sample emit ±half-width points along the local normal, zig-zagging across
    the edge. Returns [(x, y, is_jump)].

    STRICT alternation — every path step is a full crossing (A0 B0 A1 B1), the
    Part 4 lesson; the old per-station side swap put two same-side penetrations
    one pitch apart back-to-back and _coalesce_short deleted them.

    The penetration floor is enforced AT GENERATION (v2 Part 15): on a
    pixel-staircase contour the local normal swings step to step, so same-side
    points of adjacent stations can land fractions of a millimetre apart —
    fixture 07's ring borders emitted 830 sub-floor pairs before this gate. A
    station is skipped until BOTH sides have advanced ``floor_px`` from the
    last emitted station — the same both-boundaries rule Part 5 built for
    columns; downstream repair could never fix 830 without mangling the border.
    """
    pts_in = [(float(x), float(y)) for x, y in poly_px.reshape(-1, 2)]
    if len(pts_in) < 3:
        return []
    samples = _resample_closed(pts_in, max(1.0, float(step_px)))
    if len(samples) < 3:
        return []
    half = width_px / 2.0
    out: list[tuple[float, float, bool]] = []
    n = len(samples)
    prev_a = prev_b = None
    for i, p in enumerate(samples):
        nxt = samples[(i + 1) % n]
        dx, dy = nxt[0] - p[0], nxt[1] - p[1]
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / length, dx / length  # unit normal
        a = (p[0] + nx * half, p[1] + ny * half)
        b = (p[0] - nx * half, p[1] - ny * half)
        if prev_a is not None and floor_px > 0.0 and (
            _dist(a, prev_a) < floor_px or _dist(b, prev_b) < floor_px
        ):
            continue
        out.append((a[0], a[1], not out))
        out.append((b[0], b[1], False))
        prev_a, prev_b = a, b
    return out


def _fill_border(contour, hole_contours, width_px: float, step_px: int,
                 connect_px: float, last_pt, floor_px: float = 0.0):
    """Satin border around a fill's outline and its kept holes (v2 Part 15).

    The finish every professional digitizer applies to a filled logo shape: row
    ends land where they land, and a narrow satin runs the contour on top to
    give the edge a single crisp line — this is most of the visual difference
    between "rows of thread" and "proper embroidery". Centered on the contour,
    so half the width covers the fill's ragged ends and half reaches the true
    artwork edge the segmentation traced. Holes get the same treatment (fixture
    02's sun rim). Returns [(x, y, is_jump)], entering from ``last_pt``.
    """
    out: list[tuple[float, float, bool]] = []
    for poly in [contour, *hole_contours]:
        seg = _satin_border(poly, width_px, step_px, connect_px, floor_px)
        if not seg:
            continue
        prev = out[-1][:2] if out else last_pt
        x, y, _ = seg[0]
        seg[0] = (x, y, prev is not None and _dist(prev, (x, y)) > connect_px)
        out.extend(seg)
    return out
