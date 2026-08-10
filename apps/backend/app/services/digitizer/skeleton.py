"""Medial axis: Zhang-Suen thinning and the branch graph over it."""

from __future__ import annotations

from app.services.digitizer.constants import (
    PROJECT_CHUNK,
    SKEL_DIAG,
    SKEL_ORTHO,
    SPUR_MIN_MM,
    SPUR_PRUNE_MULT,
    THIN_RING,
)
from app.services.digitizer.geometry import (
    _fg_window,
)


def _thin_state(full):
    """Crop, pad and index the foreground for one thinning run.

    Crop to the active bounding box (v2 Part 17): thinning iterated full-canvas
    array passes although a region typically occupies a small fraction of it —
    profiled at 44s of a 62s fixture at 2x work resolution. Only a foreground
    pixel can ever be removed, so the loop then carries PADDED FLAT INDICES of
    the live pixels instead of full-window masks; fixture 07's largest thinning
    input is 2.5% foreground of a 2400x2400 window. Parity keys off ABSOLUTE
    (y + x), so the crop origin MUST be added back — otherwise an odd-offset
    region thins differently from the same region uncropped.
    Returns ``(window, padded, idx, parity)``, or None for an empty mask.
    """
    import numpy as np

    win = _fg_window(full, 1)
    if win is None:
        return None
    y0, y1, x0, x1 = win
    # The 1 px border is never written — it IS the off-canvas background that
    # every neighbourhood read from a pixel on the crop edge has to see.
    padded = np.zeros((y1 - y0 + 2, x1 - x0 + 2), np.uint8)
    padded[1:-1, 1:-1] = full[y0:y1, x0:x1]
    idx = np.flatnonzero(padded)
    row, col = np.divmod(idx, padded.shape[1])
    # padded (row, col) is canvas (y0 + row - 1, x0 + col - 1); the -2 drops out.
    return win, padded, idx, ((row + col + y0 + x0) % 2).astype(np.uint8)


def _thin_terms(flat, idx, offsets):
    """Gather P2..P9 for the live pixels and apply Zhang-Suen's B/A test.

    ``B`` is the 8-neighbour count and ``A`` the number of 0→1 transitions round
    the ring; both fit in uint8. Every entry of ``idx`` is foreground by
    construction, so the scalar reference's ``img == 1`` term already holds.
    Returns ``(neighbours, keep)`` — ``neighbours`` is reused for the step test.
    """
    import numpy as np

    nb = [flat[idx + off] for off in offsets]
    b_count = nb[0] + nb[1] + nb[2] + nb[3] + nb[4] + nb[5] + nb[6] + nb[7]
    a_count = np.zeros(idx.size, np.uint8)
    for i in range(8):
        a_count += nb[i] < nb[(i + 1) % 8]
    return nb, (b_count >= 2) & (b_count <= 6) & (a_count == 1)


def _thin_step_ok(nb, step: int):
    """Zhang-Suen's per-step corner condition over the gathered neighbours.

    Step 0 is ``(P2&P4&P6) == 0 & (P4&P6&P8) == 0``; on 0/1 values that is
    ``(P4 & P6 & (P2|P8)) == 0``. Step 1 swaps the pairs. Identical result in
    four ops instead of seven — the removal schedule must match the scalar
    reference exactly, or downstream branch ordering shifts.
    """
    i, j, k, m = (2, 4, 0, 6) if step == 0 else (0, 6, 2, 4)
    return ((nb[k] | nb[m]) & nb[i] & nb[j]) == 0


def _zhang_suen_thin(mask):
    """Zhang-Suen thinning → 1px medial axis. Pure NumPy.

    Deliberately NOT ``skimage.morphology.skeletonize``: scikit-image is not in
    ``requirements.txt`` or ``requirements-dev.txt`` (it only appears when the
    optional rembg extra is installed), and ``cv2.ximgproc`` is absent from
    opencv-python-headless. Depending on either would make lettering behave
    differently on CI than locally — the exact environment-dependence that Part
    1's review caught.
    """
    import numpy as np

    full = (mask > 0).astype(np.uint8)
    state = _thin_state(full)
    if state is None:
        return full
    (y0, y1, x0, x1), padded, idx, par = state
    pw = padded.shape[1]
    flat = padded.reshape(-1)
    offsets = tuple(dy * pw + dx for dy, dx in THIN_RING)
    stale = True
    while True:
        removed_any = False
        for step in (0, 1):
            # Checkerboard split (v2 Part 16): the textbook simultaneous update
            # deletes BOTH sides of an even-width ridge in one sub-iteration —
            # a 2px line satisfies the conditions on both rows at once and
            # vanishes entirely, which collapsed a 2x-upscaled bar to a single
            # skeleton pixel. Removing one pixel parity at a time re-checks the
            # neighbourhood between halves, so a ridge always keeps its centre.
            cand = None
            for parity in (0, 1):
                # Only the pixel values feed the terms, so a sub-pass that
                # removed nothing leaves them valid for the next one — and the
                # LAST pass of every thinning removes nothing by definition.
                if stale:
                    nb, keep = _thin_terms(flat, idx, offsets)
                    stale, cand = False, None
                if cand is None:
                    cand = keep & _thin_step_ok(nb, step)
                sel = cand & (par == parity)
                if sel.any():
                    flat[idx[sel]] = 0
                    idx, par = idx[~sel], par[~sel]
                    cand, stale, removed_any = None, True, True
        if not removed_any:
            out = np.zeros_like(full)
            out[y0:y1, x0:x1] = padded[1:-1, 1:-1]
            return out


def _prune_spurs(skel, min_len_px: int, rounds: int = 4):
    """Delete short dead-end branches from a skeleton.

    Thinning a glyph whose outline carries any noise sprouts hairs: measured on
    "SUMMIT", the letter S produced 82 branches from 179 skeleton pixels. Each
    hair would start its own satin run with its own jump, which is what made the
    first attempt look like scattered dashes rather than columns. A branch that
    dead-ends and is shorter than a stroke width is thinning noise, not a stroke.
    """
    import numpy as np

    out = skel.copy()
    for _ in range(max(1, rounds)):
        # The degree count reads 8-neighbours, so a 1 px window round the live
        # pixels holds every read; zero-padding the window edge reproduces the
        # full-canvas np.pad, and no pixel outside the window can be an endpoint
        # because none is set. Skeletons are sparse — counting degrees over the
        # whole canvas costs eight full-size adds per round for nothing.
        win = _fg_window(out, 1)
        if win is None:
            break
        y0, y1, x0, x1 = win
        sub, hw, ww = np.pad(out[y0:y1, x0:x1], 1), y1 - y0, x1 - x0
        deg = sum(
            sub[dy : dy + hw, dx : dx + ww]
            for dy in (0, 1, 2)
            for dx in (0, 1, 2)
            if not (dy == 1 and dx == 1)
        )
        ends = np.nonzero((out[y0:y1, x0:x1] > 0) & (deg == 1))
        endpoints = {(int(x) + x0, int(y) + y0) for y, x in zip(*ends)}
        if not endpoints:
            break
        removed = False
        # `win` is the tight box grown by 1, so it still holds every set pixel:
        # reusing it saves a second full-canvas scan per round. Coordinates stay
        # ABSOLUTE — translating them would reorder branch discovery (set-hash
        # order) and with it the surviving pixel of a two-endpoint branch.
        for br in _skeleton_branches(out, win=win):
            if len(br) >= min_len_px:
                continue
            if br[0] in endpoints or br[-1] in endpoints:
                # keep the junction pixel so the surviving strokes stay connected
                for x, y in (br[1:] if br[0] in endpoints else br[:-1]):
                    out[y, x] = 0
                removed = True
        if not removed:
            break
    return out


def _skeleton_adjacency(skel, win=None):
    """Raster-order skeleton points plus their 8-neighbours, redundant diagonals cut.

    A thinned staircase — which is what any curve or circle becomes at 1px — is
    full of L-corners: a pixel touching both an orthogonal neighbour and the
    diagonal beyond it. Counted naively that corner has three neighbours and
    reads as a junction, so a plain ring shattered into hundreds of two-pixel
    'branches' (fixture 04's outer ring: 1,288 skeleton pixels -> 617 branches,
    most of length 2). Satin over fragments that short is noise: the tangent is
    quantised to 45 degrees, the columns scatter, and short columns get
    coalesced away — the ring came out visibly dashed. A diagonal edge is
    therefore dropped when the two pixels are already joined through a shared
    4-neighbour, which is the standard connectivity rule and is symmetric from
    either end. A genuine junction ('A', 'K', a spoke meeting a rim) has no such
    shortcut and still reads as a junction.

    Returns ``(pts, nbrs)``: ``pts`` in raster order (the caller's set must be
    built from it IN THAT ORDER — set iteration order decides branch discovery
    order, hence stitch order) and ``nbrs`` mapping each point to its neighbour
    list. Coordinates are ABSOLUTE: only the nonzero scan is windowed, because
    np.nonzero over a 2400x2400 canvas holding ~6k skeleton pixels costs more
    than everything else here put together. Neighbour lists reuse the tuple
    objects in ``pts`` rather than building new ones. ``win`` may supply an
    already-known window; ANY rectangle containing every set pixel works, since
    only the scan is windowed, so a caller that grew the box for its own reads
    can hand that one over instead of paying a second full-canvas scan.
    """
    import numpy as np

    if win is None:
        win = _fg_window(skel, 0)
    if win is None:
        return [], {}
    y0, y1, x0, x1 = win
    # 1 px border of background so every neighbour read of a window-edge pixel
    # lands in it; the tight box holds every set pixel, so that border is real.
    occ = np.zeros((y1 - y0 + 2, x1 - x0 + 2), np.int32)
    occ[1:-1, 1:-1] = skel[y0:y1, x0:x1] > 0
    ry, rx = np.nonzero(occ[1:-1, 1:-1])
    stride = occ.shape[1]
    base = (ry + 1) * stride + (rx + 1)
    occ.reshape(-1)[base] = np.arange(base.size) + 1  # 1-based; 0 == background
    flat = occ.reshape(-1)
    orth = [flat[base + dy * stride + dx] for dx, dy in SKEL_ORTHO]
    # SKEL_ORTHO index of the two 4-neighbours shared with each diagonal.
    diag = [flat[base + dy * stride + dx] * (orth[i] == 0) * (orth[j] == 0)
            for (dx, dy), i, j in zip(SKEL_DIAG, (0, 0, 1, 1), (2, 3, 2, 3))]
    pts = list(zip((rx + x0).tolist(), (ry + y0).tolist()))
    nbrs: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for pt, *cells in zip(pts, *(c.tolist() for c in orth + diag)):
        nbrs[pt] = [pts[c - 1] for c in cells if c]
    return pts, nbrs


def _skeleton_branches(skel, min_len: int = 2, win=None):
    """Split a 1px skeleton into ordered polylines between endpoints/junctions.

    Returns a list of [(x, y), ...] paths. Junction pixels are shared, so the
    branches of a glyph like 'A' or 'K' meet rather than leaving a gap. ``win``
    is passed straight to `_skeleton_adjacency` and only saves a scan.
    """
    pt_list, neighbours = _skeleton_adjacency(skel, win)
    if not pt_list:
        return []
    # `dict.fromkeys`, not `set`. The comment here used to read "raster insertion
    # order — see `_skeleton_adjacency`", which a `set` does not have: it was
    # asserting the very property the container destroyed. `_skeleton_adjacency`
    # is explicit that "the caller's set must be built from it IN THAT ORDER —
    # set iteration order decides branch discovery order, hence stitch order",
    # and both this container and `nodes` below were plain sets, so discovery ran
    # in tuple-hash order. That is stable for a given CPython build and so never
    # showed up as flakiness, but it is not a property to rely on, and it means
    # branch cuts are chosen by hash rather than by geometry. `_order_branches`
    # (Part 13) sorts the RESULT by adjacency — measured, that leaves total
    # inter-branch travel unchanged at 0.0% — so this is a determinism fix on its
    # own merits, not a travel one, and it is deliberately not part of 1b.
    pts = dict.fromkeys(pt_list)  # raster order, O(1) membership

    degree = {p: len(neighbours[p]) for p in pts}
    nodes = {p for p, d in degree.items() if d != 2}  # endpoints + junctions
    node_order = [p for p in pts if p in nodes]  # walk them top-left first
    branches: list[list[tuple[int, int]]] = []
    seen_edges: set[frozenset] = set()

    def walk(start, first):
        path = [start, first]
        prev, cur = start, first
        while cur not in nodes:
            nxt = [n for n in neighbours[cur] if n != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
        return path

    for node in node_order:
        for nb in neighbours[node]:
            edge = frozenset((node, nb))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            path = walk(node, nb)
            for a, b in zip(path, path[1:]):
                seen_edges.add(frozenset((a, b)))
            if len(path) >= min_len:
                branches.append(path)

    if not branches and pts:  # a closed loop (e.g. 'O') has no endpoint at all
        start = next(iter(pts))
        path, prev, cur = [start], None, start
        while True:
            nxt = [n for n in neighbours[cur] if n != prev]
            if not nxt or nxt[0] == start:
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
        if len(path) >= min_len:
            branches.append(path)
    return _order_branches(branches)


def _order_branches(branches):
    """Chain branches by nearest endpoint, reversing where that shortens travel.

    v2 Part 13. Branches were emitted in `for node in nodes` SET order —
    spatially arbitrary, so consecutive branches could sit at opposite ends of a
    glyph and every transition earned a jump. Measured on fixture 07, branch
    starts contributed 122 of 979 jumps and underlay branch breaks another 61.
    Greedy nearest-endpoint is O(n^2) on ~tens of branches per object; the
    start is the branch endpoint nearest the top-left for determinism.
    """
    if len(branches) < 2:
        return branches
    remaining = list(branches)
    cur = min(remaining, key=lambda b: min(b[0][0] + b[0][1], b[-1][0] + b[-1][1]))
    remaining.remove(cur)
    if cur[-1][0] + cur[-1][1] < cur[0][0] + cur[0][1]:
        cur = cur[::-1]
    ordered = [cur]
    while remaining:
        ex, ey = ordered[-1][-1]

        def d2(p, ex=ex, ey=ey):
            return (p[0] - ex) ** 2 + (p[1] - ey) ** 2

        nxt = min(remaining, key=lambda b: min(d2(b[0]), d2(b[-1])))
        remaining.remove(nxt)
        ordered.append(nxt[::-1] if d2(nxt[-1]) < d2(nxt[0]) else nxt)
    return ordered


def _extend_branch_ends(samples, dist, binary, step: int):
    """Extrapolate a skeleton branch past both ends, out to the stroke's cap.

    The medial axis of a bar stops half a width short of its end, so satin driven
    straight off the skeleton leaves every stroke terminal unstitched. Points are
    only added while they stay inside the glyph, so this cannot spill outside the
    shape or run past a junction into open space.
    """
    h, w = binary.shape[:2]

    def march(anchor, toward):
        ax, ay = anchor
        dx, dy = ax - toward[0], ay - toward[1]
        norm = (dx * dx + dy * dy) ** 0.5
        if norm < 1e-6:
            return []
        dx, dy = dx / norm, dy / norm
        reach = float(dist[int(ay), int(ax)])  # local half-width = cap depth
        out = []
        travelled = float(step)
        while travelled <= reach:
            nx, ny = int(round(ax + dx * travelled)), int(round(ay + dy * travelled))
            if not (0 <= nx < w and 0 <= ny < h) or binary[ny, nx] == 0:
                break
            out.append((nx, ny))
            travelled += step
        return out

    head = march(samples[0], samples[min(1, len(samples) - 1)])
    tail = march(samples[-1], samples[max(-2, -len(samples))])
    return list(reversed(head)) + list(samples) + tail


def _nearest_axis(bpts, frames):
    """Owning axis sample for each boundary point, as (branch id, sample id, flat index).

    NOT nearest by raw distance (v2 Part 7). Raw distance is a Voronoi split, and
    a Voronoi split is wrong wherever two branches differ in thickness: where a
    6px hairline meets a 34px stem, a stem boundary pixel is 17px from the stem
    axis but only ~17px from the hairline axis too, so a tall run of the STEM's
    boundary gets handed to the HAIRLINE. Those pixels then all project to nearly
    one station on the hairline's short axis — the stall Part 6 §4 exposed once
    the penetration floor stopped the surplus columns from papering over it.

    The medial axis already defines the right answer. A boundary point p lies at
    exactly the local radius r(a) from the axis point a whose maximal inscribed
    disc touches it, and strictly further from every other axis point. So minimise
    ``|p - a| - r(a)``: it is ~0 for the branch p actually bounds and positive for
    any other, at any thickness ratio. Worked example in the Part 7 audit.

    Chunked because the full boundary x axis distance matrix runs to hundreds of
    megabytes on a large ring.
    """
    import numpy as np

    axis_all = np.vstack([f[0] for f in frames])
    radii_all = np.concatenate([f[3] for f in frames])
    owner = np.concatenate([np.full(len(f[0]), i, dtype=np.int64) for i, f in enumerate(frames)])
    local = np.concatenate([np.arange(len(f[0]), dtype=np.int64) for f in frames])
    nearest = np.empty(len(bpts), dtype=np.int64)
    for i in range(0, len(bpts), PROJECT_CHUNK):
        diff = bpts[i:i + PROJECT_CHUNK, None, :] - axis_all[None, :, :]
        gap = np.sqrt((diff * diff).sum(-1)) - radii_all[None, :]
        nearest[i:i + PROJECT_CHUNK] = np.argmin(gap, axis=1)
    return owner, local, nearest


def _free_ends(skel, samples) -> tuple[bool, bool]:
    """Is each end of this branch a FREE stroke end, or an interior junction?

    A skeleton pixel with two or fewer 8-neighbours is the end of a line; three or
    more means other strokes continue through it. `_extend_branch_ends` has
    already pushed the samples past the original endpoint toward the cap, so the
    test walks back to the last sample that is actually on the skeleton.
    """
    import numpy as np

    if skel is None or len(samples) < 2:
        return True, True
    h, w = skel.shape[:2]

    def on_skel(pt):
        x, y = round(pt[0]), round(pt[1])
        return 0 <= x < w and 0 <= y < h and skel[y, x] > 0

    def free(order):
        for pt in order:
            if not on_skel(pt):
                continue
            x, y = round(pt[0]), round(pt[1])
            patch = skel[max(y - 1, 0):y + 2, max(x - 1, 0):x + 2]
            return int(np.count_nonzero(patch)) - 1 <= 2
        return True

    return free(samples), free(samples[::-1])


def _axis_branches(binary, dist, mm_per_px: float):
    """Thin a region to its medial axis and split it into ordered branches."""
    import cv2
    import numpy as np

    # Close pinholes and soften the outline before thinning — boundary noise is
    # what sprouts skeleton hairs, and it is cheaper to remove it here than to
    # prune the consequences.
    # Windowed: a 3x3 close reaches 2 px and cannot set a pixel outside
    # dilate(binary), i.e. 1 px past the tight box, so a 3 px margin computes
    # every possibly-nonzero output from in-window data and the rest stays 0.
    smooth = np.zeros_like(binary)
    win = _fg_window(binary, 3)
    if win is not None:
        y0, y1, x0, x1 = win
        smooth[y0:y1, x0:x1] = cv2.morphologyEx(
            np.ascontiguousarray(binary[y0:y1, x0:x1]), cv2.MORPH_CLOSE,
            np.ones((3, 3), np.uint8))
    skel = _zhang_suen_thin(smooth)
    # Prune spurs shorter than a typical stroke width; that is the scale at which
    # a dead-end branch is noise rather than a real stroke ending.
    median_half = float(np.median(dist[skel > 0])) if (skel > 0).any() else 0.0
    spur_px = max(int(round(SPUR_MIN_MM / mm_per_px)), int(round(median_half * SPUR_PRUNE_MULT)), 3)
    skel = _prune_spurs(skel, spur_px)
    branches = [b for b in _skeleton_branches(skel) if len(b) >= 3]
    return skel, branches or [b for b in _skeleton_branches(skel) if len(b) >= 2]
