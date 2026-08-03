"""Stitch-order routing: travel, ties, trims, colour merging."""

from __future__ import annotations

from itertools import pairwise

from app.models.design import Stitch
from app.services.digitizer.constants import (
    MIN_PENETRATION_MM,
    TIE_ALONG_MM,
    TIE_LATERAL_MM,
    TRIM_JUMP_MM,
)
from app.services.digitizer.geometry import (
    _dist,
    _restore_for_floor,
)


def _merge_adjacent_same_hex(stitches, color_stops, objects) -> int:
    """Merge CONSECUTIVE colour stops that mount the same thread (v2 Part 25).

    Measured on the corpus: 5 of the 10 fixtures asked the operator to mount a
    thread they already had on the machine — fixture 04 opened two stops of one
    hex with nothing between them. Each merge deletes one COLOR_CHANGE (an
    operator re-thread) and replaces it with a TRIM.

    ADJACENT stops only, by design. Non-adjacent same-hex stops exist for
    layering (the deferred detail pass must sew AFTER the fills that cover its
    holes), and merging across an intervening colour would re-order the sewing.
    Adjacency preserves the stream order exactly, so it cannot break layering.

    Returns the number of stops merged away. Mutates all three arguments.
    """

    if len(color_stops) < 2:
        return 0
    cc_idx = [i for i, s in enumerate(stitches) if s.command == "COLOR_CHANGE"]
    remap: dict[int, int] = {}
    kept: list = []
    merged = 0
    for pos, stop in enumerate(color_stops):  # already in stop_number order
        if kept and stop.hex == kept[-1].hex:
            # The (pos-1)-th COLOR_CHANGE separated this stop from the previous
            # one; the thread does not change, so it becomes a plain TRIM.
            i = cc_idx[pos - 1]
            stitches[i] = Stitch(x=stitches[i].x, y=stitches[i].y, command="TRIM")
            if i + 1 < len(stitches) and stitches[i + 1].command == "STITCH":
                # A COLOR_CHANGE implied a repositioning the TRIM does not;
                # without a JUMP the first stitch of the next block would be
                # sewn as one long stitch from the trim position.
                stitches.insert(i + 1, Stitch(x=stitches[i + 1].x, y=stitches[i + 1].y, command="JUMP"))
                cc_idx = [j + 1 if j > i else j for j in cc_idx]
            kept[-1].stitch_count += stop.stitch_count
            remap[stop.stop_number] = kept[-1].stop_number
            merged += 1
            continue
        new_number = len(kept) + 1
        remap[stop.stop_number] = new_number
        stop.stop_number = new_number
        stop.thread_name = f"Color {new_number}"
        kept.append(stop)
    if merged:
        color_stops[:] = kept
        for o in objects:
            o.color_stop = remap.get(o.color_stop, o.color_stop)
    return merged


def _route_travel(pts, region, step_px: float, dilate_px: int = 2):
    """Replace needle-up jumps whose path stays inside the object's own region
    with running stitches at TRAVEL_STEP_MM (v2 Part 25).

    This is the industry alternative to trimming every long move: a travel run
    inside the region is covered (or at worst bordered) by the object's own
    stitching, costs no trim, and leaves no thread trail. Jumps that leave the
    region are returned untouched for `_lock_stream` to judge.

    The region is dilated a couple of pixels before testing because
    boundary-paced satin ends sit ON the boundary, and a move between two
    branch tips legitimately hugs the edge.
    """
    import math

    import cv2
    import numpy as np

    if len(pts) < 2 or region is None:
        return pts
    mask = cv2.dilate(region, np.ones((2 * dilate_px + 1,) * 2, np.uint8)) > 0
    h, w = mask.shape

    def inside(ax, ay, bx, by, length):
        n = max(2, int(length))  # ~1px sampling
        for t in range(n + 1):
            x = ax + (bx - ax) * t / n
            y = ay + (by - ay) * t / n
            iy, ix = round(y), round(x)
            if not (0 <= iy < h and 0 <= ix < w) or not mask[iy, ix]:
                return False
        return True

    # Boundary polylines for the detour fallback, computed lazily: a jump whose
    # straight line leaves the region (a fill row hopping ACROSS a hole) can
    # usually travel AROUND the obstruction along the region's own edge, where
    # the border satin later covers the run. Without this, a plain donut
    # produced 72 trims — one per hole-crossing row connection — versus the
    # single trim the shape needs.
    boundary: list | None = None

    def get_boundary():
        nonlocal boundary
        if boundary is None:
            k = np.ones((3, 3), np.uint8)
            shrunk = cv2.erode(mask.astype(np.uint8) * 255, k)
            cs, _ = cv2.findContours(shrunk, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
            boundary = [c.reshape(-1, 2).astype(np.float64) for c in cs if len(c) >= 8]
        return boundary

    def detour(ax, ay, bx, by):
        """Points routing a->b along one boundary loop, or None."""
        best = None
        for poly in get_boundary():
            d_a = np.hypot(poly[:, 0] - ax, poly[:, 1] - ay)
            d_b = np.hypot(poly[:, 0] - bx, poly[:, 1] - by)
            ia, ib = int(d_a.argmin()), int(d_b.argmin())
            cost = float(d_a[ia] + d_b[ib])
            if best is None or cost < best[0]:
                best = (cost, poly, ia, ib)
        if best is None:
            return None
        _cost, poly, ia, ib = best
        n = len(poly)
        fwd = (ib - ia) % n
        idxs = ([(ia + s) % n for s in range(fwd + 1)] if fwd <= n - fwd
                else [(ia - s) % n for s in range((n - fwd) + 1)])
        path = [(float(poly[i][0]), float(poly[i][1])) for i in idxs]
        # Resample to the travel pitch; the raw contour is one point per pixel.
        keep = [path[0]]
        acc = 0.0
        for p, q in pairwise(path):
            acc += math.hypot(q[0] - p[0], q[1] - p[1])
            if acc >= step_px:
                keep.append(q)
                acc = 0.0
        keep.append(path[-1])
        return keep

    out = [pts[0]]
    for prev, cur in pairwise(pts):
        if not cur[2]:
            out.append(cur)
            continue
        ax, ay = float(prev[0]), float(prev[1])
        bx, by = float(cur[0]), float(cur[1])
        length = math.hypot(bx - ax, by - ay)
        if length <= 1e-6:
            out.append(cur)
            continue
        if inside(ax, ay, bx, by, length):
            k = max(1, round(length / max(step_px, 1.0)))
            for j in range(1, k):
                out.append((ax + (bx - ax) * j / k, ay + (by - ay) * j / k, False))
            out.append((bx, by, False))
            continue
        via = detour(ax, ay, bx, by)
        if via is not None and all(
            inside(p[0], p[1], q[0], q[1], math.hypot(q[0] - p[0], q[1] - p[1]))
            for p, q in pairwise([(ax, ay), *via, (bx, by)])
        ):
            for p in via:
                out.append((p[0], p[1], False))
            out.append((bx, by, False))
        else:
            out.append(cur)  # genuinely cross-fabric: left for _lock_stream
    return out


def _tie_triangle(x: float, y: float, dx: float, dy: float,
                  along: float = TIE_ALONG_MM) -> list[tuple[float, float]]:
    """Three lock penetrations anchored at (x, y), oriented along unit (dx, dy):
    out along the path, offset to the side, back to the anchor. `along` is the
    out-leg length — `_lock_stream.tie` grows it past nearby penetrations so the
    lock cannot land within the floor of the stitching it secures."""
    import math

    n = math.hypot(dx, dy)
    dx, dy = (dx / n, dy / n) if n > 1e-9 else (1.0, 0.0)
    px, py = -dy, dx
    return [
        (x + along * dx, y + along * dy),
        (x + 0.5 * along * dx + TIE_LATERAL_MM * px,
         y + 0.5 * along * dy + TIE_LATERAL_MM * py),
        (x, y),
    ]


def _lock_stream(stitches: list) -> list:
    """Post-pass over a finished stitch stream: lock every thread end.

    - Before each TRIM / COLOR_CHANGE / END that follows stitching: a tie-off.
    - At the first stitch of each new run after a cut: a tie-in.
    - A JUMP longer than TRIM_JUMP_MM with no preceding TRIM: gains a tie-off
      and a TRIM, so the machine cuts instead of dragging thread.

    Runs on the assembled stream rather than inside the emission loop because
    cuts are created in three places (object transition, colour change, END)
    and a single pass cannot miss one of them. Per-object `stitch_count` values
    are computed before this pass, so they deliberately exclude lock stitches —
    they describe the object's own stitching, not its plumbing.
    """
    import math


    out: list = []

    def last_stitch_dir():
        """Direction of the most recent stitched segment in `out`, or None."""
        pts = [s for s in out if s.command == "STITCH"]
        if len(pts) < 2:
            return None
        a, b = pts[-2], pts[-1]
        return (b.x - a.x, b.y - a.y)

    def tie(x, y, d, neighbours=()):
        """Append lock penetrations at (x, y) along unit-ish (d), keeping every
        new penetration at least MIN_PENETRATION_MM clear of `neighbours`.

        Two search axes, both earned by measurement. A fixed 0.7mm back-step
        produced 92 floor violations: on a 0.4mm-pitch satin end it lands 0.3mm
        from the previous penetration. Growing the leg alone still failed on
        fixture 03, because a satin end's back-direction points STRAIGHT ALONG
        the zig line — every previous hole lies on that line, so no length
        escapes it (measured: the leg grew to 1.6mm and still landed 0.05mm
        from an old hole). Rotating the lock off the line is what works; length
        growth remains as the second axis.
        """
        best = None
        for rot in (0.0, 0.6, -0.6, 1.2, -1.2):  # radians; ±35° and ±70°
            c, s_ = math.cos(rot), math.sin(rot)
            rd = (d[0] * c - d[1] * s_, d[0] * s_ + d[1] * c)
            for along in (TIE_ALONG_MM, TIE_ALONG_MM + 0.3, TIE_ALONG_MM + 0.6):
                pts = _tie_triangle(x, y, rd[0], rd[1], along)
                worst = min((math.hypot(px - nx, py - ny)
                             for px, py in pts for nx, ny in neighbours), default=1e9)
                if best is None or worst > best[0]:
                    best = (worst, pts)
                if worst >= MIN_PENETRATION_MM + 0.1:
                    for tx, ty in pts:
                        out.append(Stitch(x=tx, y=ty, command="STITCH"))
                    return
        # No candidate cleared the margin (dense ground everywhere): take the
        # best available rather than skipping the lock — an unlocked end
        # unravels, while a tight lock in dense stitching is exactly where
        # extra penetrations matter least.
        for tx, ty in best[1]:
            out.append(Stitch(x=tx, y=ty, command="STITCH"))

    def recent_penetrations(n=3):
        pts = [s for s in out if s.command == "STITCH"]
        return [(p.x, p.y) for p in pts[-n:]]

    pending_tie_in = False
    for i, s in enumerate(stitches):
        if s.command in ("TRIM", "COLOR_CHANGE", "END"):
            # Tie-off runs BACKWARD along the just-stitched path, so the lock
            # lies on ground that is already covered — forward would overshoot
            # 0.7mm past the object's edge onto bare fabric.
            d = last_stitch_dir()
            if d is not None and out and out[-1].command == "STITCH":
                anchor = out[-1]
                tie(anchor.x, anchor.y, (-d[0], -d[1]), recent_penetrations()[:-1])
            out.append(s)
            if s.command != "END":
                pending_tie_in = True
            continue
        if s.command == "JUMP":
            prev = out[-1] if out else None
            if (prev is not None and prev.command == "STITCH"
                    and math.hypot(s.x - prev.x, s.y - prev.y) > TRIM_JUMP_MM):
                d = last_stitch_dir()
                if d is not None:
                    tie(prev.x, prev.y, (-d[0], -d[1]), recent_penetrations()[:-1])
                out.append(Stitch(x=out[-1].x, y=out[-1].y, command="TRIM"))
                pending_tie_in = True
            out.append(s)
            continue
        # STITCH
        if pending_tie_in:
            # Tie in TOWARD the next move so the lock lies under the coming
            # stitching. Direction from this landing to the next point.
            nxt = next((t for t in stitches[i + 1:] if t.command == "STITCH"), None)
            d = (nxt.x - s.x, nxt.y - s.y) if nxt is not None else (1.0, 0.0)
            out.append(Stitch(x=s.x, y=s.y, command="STITCH"))
            tie(s.x, s.y, d, [(nxt.x, nxt.y)] if nxt is not None else ())
            pending_tie_in = False
            continue
        out.append(s)
    return out


def _coalesce_short(pts, min_dist_px: float, floor_px: float = 0.0):
    """Drop needle penetrations closer together than ``min_dist_px``.

    Sub-0.5mm stitches break thread and damage needles, and they buy nothing —
    the shape is unchanged because the following point is still stitched. Jumps
    and the final point are always kept so the path and outline stay intact.

    ``floor_px`` enables TARGETED repair (v2 Part 10). Coalescing changes which
    points survive a satin path, and that shift can break the strict A-B-A-B
    alternation `_enforce_floor` relies on, leaving two same-side penetrations
    closer than the floor. v2 Part 9 fixed that by protecting every mitred
    endpoint from being dropped at all, which cost 27 extra sub-0.5mm stitches
    corpus-wide. Here the drops happen first and only the specific points whose
    removal actually produced a violation are put back, so the short-stitch cost
    is paid once per real violation instead of once per mitre.
    """
    if not pts or min_dist_px <= 0:
        return pts
    out = [pts[0]]
    dropped: list[list] = [[]]          # dropped[k]: points removed just after out[k]
    for p in pts[1:]:
        if p[2] or _dist(out[-1], p) >= min_dist_px:
            out.append(p)               # a jump defines the path; never coalesce it away
            dropped.append([])
        else:
            dropped[-1].append(p)
    if out[-1][:2] != pts[-1][:2]:
        out.append(pts[-1])
        dropped.append([])
    return _restore_for_floor(out, dropped, floor_px) if floor_px > 0.0 else out
