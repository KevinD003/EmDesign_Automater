"""Underlay generators and the walks they are built from."""

from __future__ import annotations

from app.services.digitizer.fills import (
    _fill_by_component,
)
from app.services.digitizer.geometry import (
    _dist,
    _distance_transform,
    _drop_floor_reversals,
    _resample_closed,
    _resample_open,
    _warp_fit,
)


def _run_along(poly_px, step_px: int, connect_px: float, first_jump: bool = True):
    """Running stitch around a closed polygon, resampled at ``step_px``. For appliqué
    placement / tackdown outlines. Returns [(x, y, is_jump)]."""
    pts_in = [(float(x), float(y)) for x, y in poly_px.reshape(-1, 2)]
    samples = _resample_closed(pts_in, max(1.0, float(step_px)))
    if len(samples) < 2:
        return []
    return [(samples[0][0], samples[0][1], first_jump)] + [(p[0], p[1], False) for p in samples[1:]]


def _manual_run(poly_px, step_px: int, passes: int = 1):
    """Running stitch ALONG an open drawn path, resampled at ``step_px``, ``passes`` times
    (single/double/triple; even passes retrace backward). Returns [(x, y, is_jump)]."""
    pts_in = [(float(x), float(y)) for x, y in poly_px.reshape(-1, 2)]
    base = _resample_open(pts_in, max(1.0, float(step_px)))
    if len(base) < 2:
        return []
    seq: list[tuple[float, float]] = []
    for i in range(max(1, passes)):
        seg = base if i % 2 == 0 else list(reversed(base))
        # Each pass ends where the next begins; drop that coincident junction point so
        # double/triple runs don't emit a zero-length stitch at the turnaround.
        seq += seg if i == 0 else seg[1:]
    return [(seq[0][0], seq[0][1], True)] + [(p[0], p[1], False) for p in seq[1:]]


def _edge_walk(region, inset_px: int, step_px: int, connect_px: float,
               floor_px: float = 0.0, max_px: float = 0.0):
    """Edge-walk underlay: a running stitch along the region outline, inset inside
    the edge (spec §4.6). Returns [(x_px, y_px, is_jump)].

    The reversal repair applies here too (v2 Part 12): where erosion leaves a
    hairline spike, the contour walks out the spike and back along the adjacent
    pixel row — the same out-and-back geometry as a medial-axis branch tip, and
    the same needle-in-the-same-hole result. No corpus fixture currently
    produces one, but "does not violate on this corpus" is not "cannot violate";
    the adversarial spike test pins the case. (``_center_walk`` is deliberately
    NOT wired: its emitted points advance monotonically in rotated-x by
    ``step_px`` per point, the un-rotation is an isometry, so any same-side pair
    is at least ``2 * step_px`` apart — ~13x the floor. A property test pins
    that impossibility instead.)"""
    import cv2
    import numpy as np

    k = max(1, inset_px)
    eroded = cv2.erode(region, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    if cv2.countNonZero(eroded) == 0:
        eroded = region  # region too thin to inset — walk the raw edge
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    pts: list[tuple[float, float, bool]] = []
    for c in contours:
        poly = [(float(x), float(y)) for x, y in c.reshape(-1, 2)]
        if len(poly) < 3:
            continue
        poly.append(poly[0])  # close the loop
        acc = 0.0
        for i, p in enumerate(poly):
            if i == 0:
                jump = bool(pts) and _dist(pts[-1], p) > connect_px
                pts.append((p[0], p[1], jump if pts else True))
                continue
            acc += _dist(poly[i - 1], p)
            if acc >= step_px:
                pts.append((p[0], p[1], False))
                acc = 0.0
        if pts and pts[-1][:2] != poly[-1]:
            pts.append((poly[-1][0], poly[-1][1], False))
    return _drop_floor_reversals(pts, floor_px, max_px)


def _center_walk(region, rect, step_px: int, connect_px: float):
    """Center-walk underlay for a satin column: a running stitch down the column's
    long-axis midline (spec §4.6). Returns [(x_px, y_px, is_jump)]."""
    import numpy as np

    (cx, cy), (rw, rh), ang = rect
    if rw < rh:
        ang += 90.0
    rot, Minv = _warp_fit(region, (cx, cy), ang)
    h, w = rot.shape

    pts: list[tuple[float, float, bool]] = []
    for x in range(0, w, max(1, step_px)):
        rows = np.flatnonzero(rot[:, x])
        if rows.size == 0:
            continue
        mid = float(rows[0] + rows[-1]) / 2.0
        X = Minv[0, 0] * x + Minv[0, 1] * mid + Minv[0, 2]
        Y = Minv[1, 0] * x + Minv[1, 1] * mid + Minv[1, 2]
        jump = bool(pts) and _dist(pts[-1], (X, Y)) > connect_px
        pts.append((float(X), float(Y), jump if pts else True))
    return pts


def _zigzag_underlay(region, axis_pts, step_px: float, inset_px: float, connect_px: float,
                     floor_px: float = 0.0, max_px: float = 0.0):
    """Zigzag underlay along a medial axis (v2 Part 24). [(x_px, y_px, is_jump)].

    Walks the axis at ``step_px`` and throws the needle alternately to either
    side, turning ``inset_px`` short of the boundary. Half-width comes from the
    distance transform at each axis sample, which is the true local half-width of
    the stroke, so the lattice follows a stroke that narrows or curves instead of
    assuming a constant bar — the same reason satin itself moved off `minAreaRect`
    in Part 4.

    Two passes are laid, the second offset by half a step and walked back, which
    is what makes it a DOUBLE zigzag: a single zigzag supports the two edges but
    leaves the centre of a wide column unscaffolded, and coming back on the
    opposite phase costs no extra travel because the return trip has to happen
    anyway to reach the top stitching's start.
    """
    import math

    import numpy as np

    if len(axis_pts) < 2:
        return []
    dist = _distance_transform((region > 0).astype(np.uint8))
    h, w = region.shape

    def pass_(pts, phase: float):
        # (x, y, starts_a_new_run) — the cross-column throw is the STITCH, so it
        # must never be flagged as a jump however long it is. Only a break in the
        # axis itself (end of one branch, start of the next) starts a new run.
        out: list[tuple[float, float, bool]] = []
        acc = phase
        side = 1
        broke = True
        for i in range(len(pts)):
            x, y = float(pts[i][0]), float(pts[i][1])
            if i:
                d = _dist(pts[i - 1][:2], (x, y))
                if d > connect_px:
                    acc, broke = phase, True
                else:
                    acc += d
            if i and acc < step_px:
                continue
            acc = 0.0
            # Local tangent from the neighbours; the normal is its perpendicular.
            j0, j1 = max(0, i - 1), min(len(pts) - 1, i + 1)
            tx = float(pts[j1][0]) - float(pts[j0][0])
            ty = float(pts[j1][1]) - float(pts[j0][1])
            n = math.hypot(tx, ty)
            if n < 1e-9:
                continue
            nx, ny = -ty / n, tx / n
            iy, ix = round(y), round(x)
            if not (0 <= iy < h and 0 <= ix < w):
                continue
            reach = max(1.0, float(dist[iy, ix]) - inset_px)
            px, py = x + side * nx * reach, y + side * ny * reach
            if out and not broke and max_px > 0:
                # Subdivide a throw longer than the machine limit. A column
                # inside SATIN_MAX_W_MM cannot reach 12.7mm, but the underlay
                # also has to cover the advance along the axis when a branch
                # curves sharply, and an unbounded stitch is a machine fault
                # rather than a quality opinion.
                gap = _dist(out[-1], (px, py))
                if gap > max_px:
                    ax, ay = out[-1][0], out[-1][1]
                    steps = int(gap // max_px) + 1
                    for s in range(1, steps):
                        out.append((ax + (px - ax) * s / steps,
                                    ay + (py - ay) * s / steps, False))
            out.append((px, py, broke))
            broke = False
            side = -side
        return out

    first = pass_(axis_pts, 0.0)
    second = pass_(list(reversed(axis_pts)), step_px / 2.0)
    pts = first + second
    if first and second:
        x, y, _f = second[0]
        pts[len(first)] = (x, y, _dist(first[-1], (x, y)) > connect_px)
    return _drop_floor_reversals(pts, floor_px, max_px)


def _parallel_underlay(region, inset_px: int, row_px: int, angle_deg: float,
                       max_step_px: int, connect_px: float,
                       floor_px: float = 0.0, max_px: float = 0.0):
    """Low-density tatami underlay under a fill (v2 Part 24). [(x, y, is_jump)].

    An open scanline layer inside the eroded region, crossing the top fill's
    direction. Inset by the same amount as the edge walk so the underlay cannot
    surface outside the top layer at the boundary.
    """
    import cv2
    import numpy as np

    k = max(1, inset_px)
    eroded = cv2.erode(region, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    if cv2.countNonZero(eroded) == 0:
        return []
    pts = _fill_by_component(eroded, max(1, row_px), max_step_px, connect_px,
                             angle_deg=angle_deg)
    return _drop_floor_reversals(pts, floor_px, max_px)


def _axis_underlay(axis_pts, step_px: float, connect_px: float,
                   floor_px: float = 0.0, max_px: float = 0.0):
    """Running-stitch underlay along a medial axis. Returns [(x_px, y_px, is_jump)].

    Decimation is by DISTANCE, not by list index. Consecutive axis samples are one
    satin column apart (~0.4mm), so an index stride of `step_px` spaced the underlay
    `step_px x spacing_px` apart — 4mm on the bench fixtures — and was unbounded
    across a branch boundary, where it produced stitches of 16mm and worse against
    a 12.7mm machine limit. Jump flags are derived from the travelled gap exactly as
    `_center_walk` does, so a discontinuity becomes a JUMP rather than a long stitch
    no matter how the branch bookkeeping upstream turns out.
    """
    out: list[tuple[float, float, bool]] = []
    last: tuple[float, float] | None = None
    for i, (x, y, _flag) in enumerate(axis_pts):
        if last is None:
            out.append((float(x), float(y), True))
            last = (float(x), float(y))
            continue
        # A break in the axis (end of one branch, start of the next): close out the
        # previous branch first so its tail keeps its underlay, then travel.
        if _dist(axis_pts[i - 1], (x, y)) > connect_px:
            px, py = float(axis_pts[i - 1][0]), float(axis_pts[i - 1][1])
            if _dist(last, (px, py)) > 1e-6:
                out.append((px, py, _dist(last, (px, py)) > connect_px))
            out.append((float(x), float(y), True))
            last = (float(x), float(y))
            continue
        gap = _dist(last, (x, y))
        if gap >= step_px:
            out.append((float(x), float(y), gap > connect_px))
            last = (float(x), float(y))
    return _drop_floor_reversals(out, floor_px, max_px)


def _with_underlay(under, top, connect_px: float):
    """Prepend underlay points to the top stitching; the transition becomes a plain
    stitch when the two are close, otherwise a jump."""
    if not under:
        return top
    if top:
        x, y, _ = top[0]
        top = [(x, y, _dist(under[-1], (x, y)) > connect_px)] + top[1:]
    return under + top


def _rebuild_underlay(st: str, ut: str, mask, rect, stitch_angle: float,
                      spacing_px: int, under_step_px: int, connect_px: float,
                      max_step_px: int, mm_per_px: float, floor_px: float,
                      max_px: float, edge_inset_px: int, zigzag_pitch_px: float,
                      zigzag_inset_px: float, parallel_pitch_mult: float,
                      parallel_angle_offset_deg: float):
    """Underlay for a rebuilt object: the SELECTED type dispatched to its real
    generator (CTO A5/C5). Returns [(x, y, is_jump)] or [] for none.

    Before this, any non-NONE choice silently collapsed to center-walk (satin)
    / edge-walk (fills), so the dropdown was mostly fake. Runs/manual/appliqué
    take no underlay. A stored value digitize never assigns to the family (a
    legacy save from the old free-for-all dropdown) keeps the old collapse so
    no design errors out on load.
    """
    if not ut or ut == "NONE":
        return []
    if st == "SATIN":
        if ut == "DOUBLE_ZIGZAG":
            # Zigzag lattice along the column midline — same generator and
            # pitch recipe as digitize's wide-satin path.
            axis = _center_walk(mask, rect, under_step_px, connect_px)
            return _zigzag_underlay(
                mask, axis, zigzag_pitch_px, zigzag_inset_px, connect_px,
                floor_px, max_px,
            ) or _center_walk(mask, rect, under_step_px, connect_px)
        if ut == "EDGE_WALK":
            return _edge_walk(mask, edge_inset_px, under_step_px, connect_px,
                              floor_px, max_px)
        # CENTER_WALK, plus legacy PARALLEL/CONTOUR saves
        return _center_walk(mask, rect, under_step_px, connect_px)
    if st in ("TATAMI", "CONTOUR_FILL", "SPIRAL_FILL", "RADIAL_FILL"):
        under = _edge_walk(mask, edge_inset_px, under_step_px, connect_px,
                           floor_px, max_px)
        if ut == "PARALLEL":
            # Edge run PLUS the low-density crossing tatami layer — digitize's
            # PARALLEL recipe (v2 Part 24), previously unreachable from an edit.
            par = _parallel_underlay(
                mask, edge_inset_px,
                max(1, round(spacing_px * parallel_pitch_mult)),
                stitch_angle + parallel_angle_offset_deg,
                max_step_px, connect_px, floor_px, max_px,
            )
            if par:
                under = _with_underlay(under, par, connect_px)
        return under
    return []
