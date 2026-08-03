"""Column geometry: stations along an axis, the boundary they reach,
pacing, and the penetration floor."""

from __future__ import annotations

from itertools import pairwise

from app.services.digitizer.constants import (
    CAP_EXTRA_COLUMNS,
    CLOSED_LOOP_TOL_PX,
    FILL_STAGGER_ROWS,
    MIN_ARC_SAMPLES,
    MIN_STITCH_MM,
    SATIN_SPACING_MM,
    TANGENT_WINDOW,
)
from app.services.digitizer.geometry import (
    _dist,
    _fg_window,
    _mitre_stalled_side,
)
from app.services.digitizer.skeleton import (
    _extend_branch_ends,
    _nearest_axis,
)


def _march_to_edge(binary, x: float, y: float, nx: float, ny: float, limit: float) -> float:
    """Distance from (x, y) along (nx, ny) to the last pixel still inside the shape.

    The distance transform gives the radius of the largest inscribed circle,
    which is the distance to the NEAREST edge — not the distance to the edge in
    the direction the column actually runs. Using it symmetrically puts both
    column ends at that same radius, so on any stroke whose medial axis is not
    perfectly centred (most real glyphs, and every curve) one end falls short of
    the outline and the other overshoots it. That is the ragged edge measured in
    Part 2 (edge-band coverage 84.1% -> 78.1%). Marching to the actual boundary
    gives each side its own true half-width.
    """
    h, w = binary.shape[:2]
    travelled = 0.0
    last = 0.0
    while travelled <= limit:
        px, py = int(round(x + nx * travelled)), int(round(y + ny * travelled))
        if not (0 <= px < w and 0 <= py < h) or binary[py, px] == 0:
            break
        last = travelled
        travelled += 0.5
    return last


def _boundary_points(region):
    """Every boundary pixel of a region, outer contour and holes alike, as (N, 2).

    `CHAIN_APPROX_NONE` is deliberate: the corners a simplifying approximation
    drops are exactly the column endpoints this part exists to land on.
    """
    import cv2
    import numpy as np

    # Traced inside the foreground's own box with `offset` putting the points
    # back in canvas coordinates. Border following only ever visits foreground
    # and its 1 px rim, so a 1 px window margin cannot clip a contour or reorder
    # the components (the raster scan that orders them is translation-stable);
    # where the window clamps to the canvas edge it IS the full-canvas edge.
    win = _fg_window(region, 1)
    if win is None:
        return np.zeros((0, 2), dtype=np.float64)
    y0, y1, x0, x1 = win
    sub = np.ascontiguousarray((region[y0:y1, x0:x1] > 0).astype(np.uint8))
    contours, _ = cv2.findContours(sub, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE, offset=(x0, y0))
    arcs = [c.reshape(-1, 2).astype(np.float64) for c in contours if len(c) >= 2]
    return np.vstack(arcs) if arcs else np.zeros((0, 2), dtype=np.float64)


def _axis_frame(samples, dist=None):
    """Turn an axis polyline into (points, arc-length, unit tangents, radii).

    Tangents use the same ±`TANGENT_WINDOW` smoothing the ray-cast columns used,
    for the same reason: a ±1 estimate on a stair-stepped skeleton swings 45°.

    ``radii`` is the distance transform at each sample — the radius of the
    maximal inscribed disc there — which is what makes the boundary partition
    scale-aware (see `_nearest_axis`). Zero when no transform is supplied.
    """
    import numpy as np

    pts = np.asarray(samples, dtype=np.float64)
    lengths = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    idx = np.arange(len(pts))
    lo = np.maximum(idx - TANGENT_WINDOW, 0)
    hi = np.minimum(idx + TANGENT_WINDOW, len(pts) - 1)
    delta = pts[hi] - pts[lo]
    norm = np.linalg.norm(delta, axis=1)
    norm[norm < 1e-9] = 1.0
    if dist is None:
        radii = np.zeros(len(pts))
    else:
        radii = dist[pts[:, 1].astype(np.int64), pts[:, 0].astype(np.int64)].astype(np.float64)
    return pts, lengths, delta / norm[:, None], radii


def _assign_boundary(bpts, frames):
    """Assign every boundary point to one axis branch, with a side and a parameter.

    THIS IS THE CORRESPONDENCE SOLUTION, and the junction problem is solved by
    what it does NOT try to do: it never attempts to split the region's contour
    into two global left/right arcs. At a junction — where three strokes meet and
    the contour weaves between them — no such global split exists. Instead each
    boundary point is assigned to its NEAREST axis branch, so every branch sees
    only the boundary that belongs to it; the contour is partitioned by the
    skeleton's own topology rather than by any assumption about the shape.

    Within a branch a point gets:
      * ``t`` — arc length along that branch, refined by projecting onto the
        local tangent, so the parameter runs continuously past a branch end
        instead of piling up on the last sample (this is what makes caps work);
      * ``side`` — the sign of the cross product with the tangent, i.e. which of
        the stroke's two boundaries it lies on.

    Two points with the same ``t`` and opposite ``side`` ARE corresponding points
    on the two boundaries. Returns ``[(t, side, point), ...]`` per branch.
    """
    import numpy as np

    if len(bpts) == 0 or not frames:
        return [[] for _ in frames]
    owner, local, nearest = _nearest_axis(bpts, frames)

    out = []
    for b, frame in enumerate(frames):
        pts, lengths, tan, _radii = frame
        sel = np.flatnonzero(owner[nearest] == b)
        if len(sel) == 0:
            out.append([])
            continue
        j = local[nearest[sel]]
        rel = bpts[sel] - pts[j]
        cross = tan[j][:, 0] * rel[:, 1] - tan[j][:, 1] * rel[:, 0]
        out.append({
            "t": lengths[j] + (rel * tan[j]).sum(-1),   # arc length, tangentially refined
            "side": np.sign(cross),
            "off": np.abs(cross),                       # perpendicular reach from the axis
            "pt": bpts[sel],
        })
    return out


def _extreme_per_station(arc, grid, period: float | None):
    """One boundary point per column station: the one reaching FARTHEST out.

    A stroke's boundary carries many pixels per column pitch, and several of them
    share a parameter — around a corner, dozens do. Interpolating across those
    ties averages the endpoint INWARD, which measured as a 1.4-2.1 point coverage
    loss when this part first ran. Keeping the outermost point per station makes
    the column reach the boundary it is supposed to define.
    """
    import numpy as np

    t, off, pt = arc["t"], arc["off"], arc["pt"]
    lo, pitch = grid[0], (grid[1] - grid[0])
    tt = lo + np.mod(t - lo, period) if period else t
    station = np.clip(((tt - lo) / pitch).astype(np.int64), 0, len(grid) - 1)
    order = np.lexsort((off, station))               # within a station, offset ascending
    ordered = station[order]
    last = np.flatnonzero(np.append(np.diff(ordered) != 0, True))
    keep = order[last]                               # => the max-offset point per station
    return tt[keep], pt[keep]


def _arc_at(t_src, p_src, t_query, period: float | None):
    """Sample a boundary arc at arbitrary parameters — the pairing step.

    Corresponding points are defined by EQUAL ``t`` on the two arcs, so both are
    reparametrised onto the same query grid. Open strokes clamp at the arc ends
    (a query past the last boundary point yields that point, which is the cap
    tip); rings wrap by `period`, which is the whole of the ring special case —
    a closed loop is just an arc with no ends to clamp against.
    """
    import numpy as np

    order = np.argsort(t_src)
    ts, ps = t_src[order], p_src[order]
    if period and period > 0:                        # ring: repeat one turn each way
        ts = np.concatenate([ts - period, ts, ts + period])
        ps = np.vstack([ps, ps, ps])
    x = np.interp(t_query, ts, ps[:, 0])
    y = np.interp(t_query, ts, ps[:, 1])
    return np.stack([x, y], axis=1)


def _column_grid(sides, period: float | None, pitch: float, free_ends=(True, True)):
    """The parameter stations columns are laid at — where terminals and rings differ.

    A ring has no terminals, so the grid covers exactly one turn and stops one
    pitch short of closing; the last column then sits beside the first.

    A FREE stroke end runs PAST the terminal by `CAP_EXTRA_COLUMNS`. Beyond the
    tip both boundary arcs clamp to their own end point, so the pair converges
    onto the cap and the terminal is stitched rather than left a half-width short.

    A JUNCTION end gets no such padding, and that distinction is the point of
    v2 Part 7. At a free end the outline really does wrap around the tip, so
    converging the two arcs there is correct. At an interior vertex — an 'M'
    apex, a 'U' bowl join, a 'T' crossing — the axis ends inside the shape and
    the outline does NOT converge; it carries on around the corner. Padding
    there fabricates a fan of columns onto a point that is not a cap. Before the
    penetration floor those coincident columns overlapped and painted the corner
    in; with the floor on they are dropped and the corner shows as a wedge-shaped
    hole. Measured on fixture 05: the fans in the 'M' apexes and the 'U' join are
    exactly these, not the boundary mis-assignment Part 6 §4 assumed.
    """
    import numpy as np

    if period:
        return np.arange(0.0, period, pitch) if period >= pitch * 2 else None
    pad = CAP_EXTRA_COLUMNS * pitch
    lo = min(s["t"].min() for s in sides) - (pad if free_ends[0] else 0.0)
    hi = max(s["t"].max() for s in sides) + (pad if free_ends[1] else 0.0)
    return np.arange(lo, hi + 1e-9, pitch)


def _pace_by_boundary(tl, pl, tr, pr, grid, period: float | None, pitch: float, floor_px: float = 0.0):
    """Re-space the columns so the FASTER boundary advances one pitch between them.

    Pitch measured along the axis is wrong wherever the two boundaries advance at
    different rates — the outside of any curve, and every junction, where one arc
    sweeps around a fillet while the other barely moves. The columns spread apart
    on the fast side and leave a fan of wedge-shaped gaps; measured on fixtures
    05/07/08 as a 0.6-1.3 point INTERIOR coverage loss. Oversample the parameter,
    then keep a column only once either side has moved a full pitch.

    ``floor_px`` bounds only the TAIL column here (v2 Part 7). Part 5 also gated
    every column on ``min(moved_a, moved_b) >= floor_px``, requiring the slow side
    to advance too. That is right on a curve and catastrophic at a junction: where
    one arc STALLS, the minimum never reaches the floor, so the branch emits no
    columns at all over that stretch — the wedge-shaped holes at fixture 05's 'M'
    apexes and 'U' join. Only 5.5% of that fixture's columns were being dropped by
    `_enforce_floor`; the rest of the hole was columns never generated. The safety
    guarantee is unaffected: `_enforce_floor` still applies the floor to the final
    endpoints, which is what the metric actually measures.
    """
    import numpy as np

    fine = np.arange(grid[0], grid[-1] + 1e-9, pitch / 4.0)
    a_all, b_all = _arc_at(tl, pl, fine, period), _arc_at(tr, pr, fine, period)
    keep = [0]
    for i in range(1, len(fine)):
        last = keep[-1]
        moved_a = float(np.hypot(*(a_all[i] - a_all[last])))
        moved_b = float(np.hypot(*(b_all[i] - b_all[last])))
        if max(moved_a, moved_b) >= pitch:
            keep.append(i)
    if keep[-1] != len(fine) - 1:
        tail = len(fine) - 1
        moved = min(float(np.hypot(*(a_all[tail] - a_all[keep[-1]]))),
                    float(np.hypot(*(b_all[tail] - b_all[keep[-1]]))))
        if moved >= floor_px:      # never close the run with a floor violation
            keep.append(tail)
    return fine[keep], a_all[keep], b_all[keep]


def _min_stitch_px(pitch_px: float) -> float:
    """MIN_STITCH_MM in the caller's pixels, derived from the satin pitch.

    Avoids re-deriving mm_per_px inside the column geometry, where it is not
    otherwise needed, and keeps the ratio explicit rather than a bare number.
    """
    return pitch_px * (MIN_STITCH_MM / SATIN_SPACING_MM)


def _enforce_floor(pairs, floor_px: float, closed: bool):
    """Drop columns whose penetrations would land closer than ``floor_px`` on either side.

    Applied to the FINAL endpoints, after clamping and pull compensation. Pacing
    alone is not enough: pull comp moves each end outward from the axis after the
    pacing decision, which on the concave side of a ring pulls it to a smaller
    radius and shrinks the spacing again. Enforcing before the clamp left 86-91%
    of violations fixed but not all of them; enforcing here is what the metric
    actually measures.
    """
    if floor_px <= 0.0 or len(pairs) < 2:
        return pairs
    # A violating column is DROPPED. Two cleverer strategies were implemented and
    # measured first, because deleting a whole crossing to fix one boundary looks
    # wasteful — and both lost. At a 0.30mm floor across the satin corpus:
    #
    #   strategy                    residual violations   mean interior   mean edge band
    #   drop the column (shipped)                     3           95.84            94.28
    #   slide the end along its boundary            245           96.60            95.33
    #   retract the end along its column             44           96.61            95.34
    #
    # Both buy about half a point of coverage and give up the guarantee, which is
    # the entire point of a safety floor. They fail for the same reason in two
    # forms: moving a penetration instead of removing it only relocates the
    # crowding. Sliding forward shortens the gap to whatever comes next. Retraction
    # shortens the COLUMN, and a column under the 0.5mm minimum stitch length gets
    # a point removed by `_coalesce_short` further down the pipeline, which breaks
    # the strict A-B-A-B alternation and creates fresh same-side adjacencies. A
    # strict second pass does not rescue either (measured 59 and 45), because by
    # then the damage is downstream of this function.
    kept = [pairs[0]]
    for a, b in pairs[1:]:
        pa, pb = kept[-1]
        if min(_dist(pa, a), _dist(pb, b)) >= floor_px:
            kept.append((a, b))
    # A ring closes on itself, so the last column must also clear the first.
    while closed and len(kept) > 2:
        pa, pb = kept[-1]
        qa, qb = kept[0]
        if min(_dist(pa, qa), _dist(pb, qb)) >= floor_px:
            break
        kept.pop()
    return kept


def _column_ends(frame, assigned, spacing_px: float, max_half_px: float, extra_px: float,
                 floor_px: float = 0.0, free_ends=(True, True)):
    """Column endpoint pairs for one branch, taken from its two boundary arcs.

    Returns ``[((x0, y0), (x1, y1)), ...]``, or ``[]`` when the branch's boundary
    is too sparse to pair — the caller then falls back to ray-cast columns for
    that branch, so this can never remove a stroke from the design.
    """
    import numpy as np

    pts, lengths = frame[0], frame[1]
    if not assigned:
        return []
    closed = len(pts) > 2 and float(np.hypot(*(pts[0] - pts[-1]))) <= CLOSED_LOOP_TOL_PX
    sides = [{k: v[assigned["side"] == sign] for k, v in assigned.items()} for sign in (1.0, -1.0)]
    if any(len(s["t"]) < MIN_ARC_SAMPLES for s in sides):
        return []

    period = float(lengths[-1]) if closed else None
    pitch = max(spacing_px, 1e-3)
    grid = _column_grid(sides, period, pitch, free_ends)
    if grid is None or len(grid) < 2:
        return []

    tl, pl = _extreme_per_station(sides[0], grid, period)
    tr, pr = _extreme_per_station(sides[1], grid, period)
    # Restricting the dropped slow-side gate to closed loops was tried, to spare the
    # ring probe's edge band. It changed nothing measurable: after
    # `_extend_branch_ends` pushes samples past the skeleton, almost no annulus
    # still closes within CLOSED_LOOP_TOL_PX, so `closed` was false for both the
    # probe rings and fixture 03. Removed rather than left as a no-op.
    grid, a, b = _pace_by_boundary(tl, pl, tr, pr, grid, period, pitch, floor_px)
    # Clamp to the satin cap about the axis, exactly as the ray-cast columns did:
    # at a junction the two boundaries are genuinely far apart, and an unclamped
    # column there throws one stitch clear across the glyph.
    mid = np.stack([np.interp(grid % period if period else grid, lengths, pts[:, 0]),
                    np.interp(grid % period if period else grid, lengths, pts[:, 1])], axis=1)
    for end in (a, b):
        v = end - mid
        d = np.linalg.norm(v, axis=1)
        d[d < 1e-9] = 1.0
        over = d > max_half_px
        end[over] = mid[over] + v[over] / d[over, None] * max_half_px
        grow = (d + extra_px) / d                    # pull compensation, outward
        end[~over] = mid[~over] + v[~over] * grow[~over, None]
    if floor_px > 0.0:
        _mitre_stalled_side(a, b, mid, floor_px, _min_stitch_px(pitch))
    pairs = [((float(p[0]), float(p[1])), (float(q[0]), float(q[1]))) for p, q in zip(a, b)]
    return _enforce_floor(pairs, floor_px, closed)


def _raycast_columns(binary, samples, max_half_px: float, extra_px: float):
    """Part 2.5's column placement, kept as the per-branch fallback.

    Each end ray-marches outward from the axis along the column direction. That
    is an approximation of the boundary — good, but aimed by a tangent estimated
    from a stair-stepped skeleton — which is why Part 4 pairs real boundary
    points instead. Retained because a branch whose boundary cannot be paired
    (a two-pixel stub) must still stitch.
    """
    out = []
    for i, (x, y) in enumerate(samples):
        lo = max(i - TANGENT_WINDOW, 0)
        hi = min(i + TANGENT_WINDOW, len(samples) - 1)
        tx, ty = samples[hi][0] - samples[lo][0], samples[hi][1] - samples[lo][1]
        norm = (tx * tx + ty * ty) ** 0.5 or 1.0
        nx, ny = -ty / norm, tx / norm               # unit normal to the stroke
        up = _march_to_edge(binary, x, y, nx, ny, max_half_px + 1.0)
        dn = _march_to_edge(binary, x, y, -nx, -ny, max_half_px + 1.0)
        up = max(min(up, max_half_px), 0.5) + extra_px
        dn = max(min(dn, max_half_px), 0.5) + extra_px
        out.append(((x + nx * up, y + ny * up), (x - nx * dn, y - ny * dn)))
    return out


def _emit_columns(pairs, max_step_px: int, prev_end, spacing_px: float):
    """Zigzag the endpoint pairs into stitch points: A0 B0 A1 B1 ... — every step a crossing.

    The obvious alternative — emit both ends of each column and flip which side
    leads — puts two penetrations one PITCH apart on the same boundary, back to
    back in the path. At a 0.4mm satin pitch that is a 0.4mm stitch, under the
    0.5mm minimum, so `_coalesce_short` correctly deletes it. The effect was to
    halve the needle penetrations along BOTH boundaries — 0.8mm apart under 0.4mm
    thread — which is the dotted rim of uncovered edge band this part started out
    trying to explain. Strict alternation makes every path step a full crossing,
    so nothing is short enough to be coalesced away and each boundary keeps a
    penetration every pitch.
    """
    import numpy as np

    seq = [end for pair in pairs for end in pair]
    if not seq:
        return [], prev_end
    first_jump = prev_end is None or _dist(prev_end, seq[0]) > spacing_px * 4
    out: list[tuple[float, float, bool]] = [(seq[0][0], seq[0][1], first_jump)]
    for k, (p0, p1) in enumerate(pairwise(seq)):
        n = max(1, int(np.ceil(_dist(p0, p1) / max(max_step_px, 1))))
        if n > 1:
            # STAGGERED split points (v2 Part 28). Even subdivision put every
            # crossing's split penetration at the same fractions, so on a column
            # wider than the machine step the splits of successive crossings
            # lined up ~0.15mm apart down the column centre — measured on an
            # 8mm straight bar as 383 same-side floor violations, a perforation
            # line where the fabric would tear. Same defect as unstaggered fill
            # rows, same cure: the split grid shifts by a quarter step per
            # crossing (the concept Ink/Stitch documents as staggering split
            # satin stitches; implementation our own). Adjacent crossings'
            # splits now sit ~max_step/4 apart — an order of magnitude over
            # the floor. Ends are guarded by 0.3 of a step so a split never
            # lands nearly-in the boundary penetration's hole.
            phase = (k % FILL_STAGGER_ROWS) / FILL_STAGGER_ROWS
            guard = 0.3 / n
            for i in range(n):
                f = (i + phase) / n
                if guard <= f <= 1.0 - guard:
                    out.append((p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f, False))
        out.append((p1[0], p1[1], False))
    return out, seq[-1]


def _axis_samples(branches, dist, binary, step: int, mm_per_px: float):
    """Decimate each branch to column stations and take the classification widths.

    Kept as its own pass, separate from column generation, so that Part 4's change
    to HOW columns are drawn provably cannot move WHICH objects are satin: the
    widths fed to the classifier come from here and touch nothing downstream.

    WIDTH FOR CLASSIFICATION is the distance transform, never the column length.
    A column follows a direction estimated from a stair-stepped skeleton, so on a
    diagonal it tilts off the true perpendicular and over-reads by 1/cos(error) —
    measured on a 3.6mm diagonal bar, the ray-cast said 4.05mm, enough to
    misclassify a textbook satin shape. Returns ``(samples, widths, centres)``.
    """
    used, widths, centres = [], [], []
    for branch in branches:
        samples = branch[::step] or [branch[0]]
        if samples[-1] != branch[-1]:
            samples.append(branch[-1])
        if len(samples) < 2:
            continue
        # A medial axis stops roughly half a stroke-width short of the stroke's
        # END — the skeleton of a bar does not reach its cap. Left uncorrected,
        # every terminal loses a half-width of coverage, which measured as a
        # 13-17 point coverage deficit against tatami. Extrapolate each end along
        # its tangent, keeping only points still inside the glyph.
        samples = _extend_branch_ends(samples, dist, binary, step)
        used.append(samples)
        for x, y in samples:
            widths.append(float(dist[int(y), int(x)]) * 2.0 * mm_per_px)
            centres.append((float(x), float(y)))
    return used, widths, centres
