"""Geometry and stream primitives — the lowest layer (R001 split)."""

from __future__ import annotations

from itertools import pairwise

from app.services.digitizer.constants import (
    _CLASSIFICATION_LOG,
    _MAX_WORK_PX,
    APPROX_EPS_MM,
    CHAIKIN_ITERS,
    COALESCE_REPAIR_PASSES,
    DT_WINDOW_PAD_PX,
    FABRIC_DEFAULT,
    FABRIC_PROFILES,
    HOLE_FRINGE_MIN_SHARE,
    HOLE_FRINGE_RING_MM,
    MITRE_MIN_STALLED,
    SMOOTH_MIN_POINTS,
    SPECK_KEEP_MM2,
    UNDERLAY_REPAIR_PASSES,
    ZIGZAG_RATIO,
)


def _fabric_profile(fabric_type: str) -> dict[str, float]:
    return FABRIC_PROFILES.get((fabric_type or "").strip().lower(), FABRIC_DEFAULT)


def _hole_covered_later(hole, labels, stitch_rank: dict, my_rank: int, shape,
                        mm_per_px: float, deferred=None) -> bool:
    """True when absorbing this fill hole cannot bury anything.

    Absorbing a hole means the fill sews over that area, so whatever the input
    shows there must either land ON TOP of the fill afterwards, or already
    extend beyond the hole so the fill merely overlaps its edge. Two safe cases:

    1. The hole's pixels belong to a cluster stitched AFTER this fill — the
       detail re-covers the area (fixture 02's letters in the green card).
    2. The hole is a FRINGE of a larger, earlier-stitched shape: the owning
       cluster continues past the hole boundary (checked in a ~1mm ring), so
       sewing over it is edge overlap — normal registration practice — not
       burial. This is fixture 07's antialias slivers hugging the star; keeping
       their knockout put one thread crossing per fill row around the star.

    Everything else keeps the knockout: an earlier-stitched detail WHOLLY inside
    the hole (07's HARBOR CLUB letters, navy before white) would be buried — the
    regression the first, unguarded version of this rule shipped for one bench
    run — and pixels owned by nobody are never re-covered at all.
    """
    import cv2
    import numpy as np

    m = np.zeros(shape, np.uint8)
    cv2.drawContours(m, [hole], -1, 255, thickness=cv2.FILLED)
    if deferred is not None and (m > 0).any() and float(deferred[m > 0].mean()) >= 0.5:
        return True  # the detail here was deferred behind this fill — it lands on top
    inside = labels[m > 0]
    inside = inside[inside >= 0]
    if inside.size == 0:
        return False
    dominant = int(np.bincount(inside).argmax())
    if stitch_rank.get(dominant, -1) > my_rank:
        return True
    r = max(1, round(HOLE_FRINGE_RING_MM / mm_per_px))
    ring = cv2.dilate(m, np.ones((2 * r + 1, 2 * r + 1), np.uint8)) & ~m
    ring_owned = float((labels[ring > 0] == dominant).mean()) if (ring > 0).any() else 0.0
    return ring_owned > HOLE_FRINGE_MIN_SHARE


def _open_preserving_detail(mask, mm_per_px: float):
    """3x3 opening that restores components the opening erased outright.

    The plain opening removed speckle but also deleted every stroke under ~2px
    wide as a unit: fixture 02's 'EST. 1974 - SUPPLY CO.' line vanished from the
    white mask, while the big NORTHFIELD letters kept the mask coarse enough to
    pass the open guard. Restoring only components that disappeared ENTIRELY
    keeps the anti-speckle effect (attached fuzz still erodes) while thin-but-
    real detail survives whole.
    """
    import cv2
    import numpy as np

    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stats, _c = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep_px = max(4, round(SPECK_KEEP_MM2 / (mm_per_px * mm_per_px)))
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < keep_px:
            continue
        comp = labels == i
        if not opened[comp].any():
            opened[comp] = 255
    return opened


def last_classification_log() -> list[dict]:
    """Per-object measured widths + satin/tatami decision from the last run."""
    return list(_CLASSIFICATION_LOG)


def _default_pull(fabric_type: str) -> float:
    return _fabric_profile(fabric_type)["pull_mm"]


def _dilate_pull(region, pull_mm: float, mm_per_px: float):
    """Widen a region mask by ``pull_mm`` per side (pull compensation)."""
    import cv2
    import numpy as np

    px = round(max(0.0, pull_mm) / mm_per_px)
    if px <= 0:
        return region
    return cv2.dilate(region, np.ones((2 * px + 1, 2 * px + 1), np.uint8))


def _parse_hoop(hoop_size: str) -> tuple[float, float]:
    try:
        w, h = hoop_size.lower().replace("mm", "").split("x")
        return max(float(w), 10.0), max(float(h), 10.0)
    except Exception:  # noqa: BLE001 - bad input → default hoop
        return 100.0, 100.0


def _border_color(img):
    """Median colour of the image border = the substrate/garment colour."""
    import numpy as np

    edges = np.concatenate([img[0, :], img[-1, :], img[:, 0], img[:, -1]], axis=0)
    return np.median(edges.astype(np.float32), axis=0)


def _merge_centers(centers, delta: float) -> dict[int, int]:
    """Map each centroid index to a representative, merging ones within ``delta``.

    Prevents emitting two colour stops for what a human reads as one colour —
    e.g. a single-colour wordmark digitized with a 2-colour budget.
    """
    import numpy as np

    rep: dict[int, int] = {}
    for i, c in enumerate(centers):
        for j in sorted(rep.values()):
            if float(np.linalg.norm(c.astype(float) - centers[j].astype(float))) < delta:
                rep[i] = j
                break
        else:
            rep[i] = i
    return rep


def _chaikin_closed(pts, iterations: int):
    """Chaikin corner-cutting on a closed polygon — turns the pixel staircase
    left by findContours into a smooth outline. Each pass replaces every vertex
    with two points at 1/4 and 3/4 along its edges."""
    import numpy as np

    out = np.asarray(pts, np.float32)
    for _ in range(max(0, iterations)):
        if len(out) < 4:
            break
        nxt = np.roll(out, -1, axis=0)
        out = np.stack([out * 0.75 + nxt * 0.25, out * 0.25 + nxt * 0.75], axis=1).reshape(-1, 2)
    return out


def _smooth_contour(contour, mm_per_px: float):
    """Douglas-Peucker simplify + Chaikin smooth, biased toward PRESERVATION.

    Small contours are returned untouched: the v1 audit requires the mascot's
    freckles/catchlights and the badge's "L" to survive, and simplification is
    exactly what removes features that small. The epsilon is also capped at a
    fraction of the perimeter so a short outline is never collapsed.
    """
    import cv2
    import numpy as np

    pts = contour.reshape(-1, 2)
    if len(pts) < SMOOTH_MIN_POINTS:
        return contour  # too few points to be a staircase; leave it alone
    peri = cv2.arcLength(contour, True)
    eps = min(APPROX_EPS_MM / max(mm_per_px, 1e-6), peri * 0.01)
    approx = cv2.approxPolyDP(contour, eps, True)
    if len(approx) < 4:
        return contour  # simplification degenerated — keep the original
    smoothed = _chaikin_closed(approx.reshape(-1, 2), CHAIKIN_ITERS)
    return np.round(smoothed).astype(np.int32).reshape(-1, 1, 2)


def _decode_svg(data: bytes):
    """Decode an SVG into ``(bgr_image, exact_foreground_mask)`` — or None if
    the bytes are not SVG (v2 Part 25).

    THE point of vector input, and why this returns a mask as well as pixels:
    every raster upload forces the pipeline to GUESS the foreground (U2-Net,
    `_reclaim_ink`, halo suppression — Parts 1, 21, 22 all exist because that
    guess goes wrong), whereas a vector file states it. The mask is recovered
    exactly by rendering the artwork twice, once on white and once on black:
    an opaque artwork pixel is identical in both renders, a background or
    semi-transparent pixel differs. That includes WHITE artwork on a white
    page — the case every substrate-colour heuristic gets wrong by definition.

    Rendered at `_MAX_WORK_PX` on the long side so the working-resolution
    rescale is a no-op and the mask never has to be resampled.
    """
    head = data[:2048].lstrip()
    if not (head.startswith((b"<?xml", b"<svg")) or b"<svg" in head[:1024]):
        return None
    import io

    import cv2
    import numpy as np
    from reportlab.graphics import renderPM
    from svglib.svglib import svg2rlg

    try:
        drawing = svg2rlg(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - svglib raises arbitrary types on bad XML; None -> caller's 415
        return None
    if drawing is None or drawing.width <= 0 or drawing.height <= 0:
        return None
    f = _MAX_WORK_PX / max(drawing.width, drawing.height)
    drawing.scale(f, f)
    drawing.width *= f
    drawing.height *= f
    white = np.array(renderPM.drawToPIL(drawing, bg=0xFFFFFF).convert("RGB"))
    black = np.array(renderPM.drawToPIL(drawing, bg=0x000000).convert("RGB"))
    diff = np.abs(white.astype(np.int16) - black.astype(np.int16)).max(axis=2)
    # < 8 rather than == 0: renderPM dithers the last bit of anti-aliased
    # coverage, so a fully opaque pixel can differ by a count or two.
    mask = (diff < 8).astype(np.uint8) * 255
    return cv2.cvtColor(white, cv2.COLOR_RGB2BGR), mask


def _subdivide_long(pts, max_step_px: int):
    """Split any stitched segment longer than the machine step; jumps pass through."""
    import math

    out: list[tuple[float, float, bool]] = []
    for prev, cur in pairwise([None, *pts]):
        if prev is None or cur[2]:
            out.append(cur)
            continue
        L = math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        k = max(1, math.ceil(L / max(max_step_px, 1)))
        for j in range(1, k + 1):
            out.append((prev[0] + (cur[0] - prev[0]) * j / k,
                        prev[1] + (cur[1] - prev[1]) * j / k, False))
    return out


def _restore_for_floor(out, dropped, floor_px: float):
    """Put back only the coalesced points whose absence breaks the penetration floor.

    A satin path alternates sides, so after a drop the points either side of a
    survivor can become same-side neighbours closer than the floor. Restoring ANY
    point that was dropped between them restores the alternation and fixes it, so
    the repair is minimal by construction: one short stitch back per violation,
    rather than the blanket protection v2 Part 9 used.

    The triple test mirrors the one the metric uses — a real satin pair zigzags,
    with the same-side gap shorter than either crossing — so a running-stitch
    underlay cannot trigger a spurious restore.
    """
    for _ in range(COALESCE_REPAIR_PASSES):
        repaired = False
        for i in range(1, len(out) - 1):
            a, b, c = out[i - 1], out[i], out[i + 1]
            gap = _dist(a, c)
            if gap >= floor_px or gap >= ZIGZAG_RATIO * min(_dist(a, b), _dist(b, c)):
                continue
            for k in (i - 1, i):
                if dropped[k]:
                    out.insert(k + 1, dropped[k].pop(0))
                    dropped.insert(k + 1, [])
                    repaired = True
                    break
            if repaired:
                break
        if not repaired:
            break
    return out


def _dist(p, q) -> float:
    return float(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5)


def _warp_fit(region, center, angle_deg: float):
    """Rotate a mask into a destination sized to hold the rotated content (NO cropping —
    a tall-thin shape rotated to horizontal would otherwise be clipped by the original
    width). Returns (rotated, inverse_affine); the inverse maps rotated px → original px."""
    import cv2

    M = cv2.getRotationMatrix2D((float(center[0]), float(center[1])), float(angle_deg), 1.0)
    h, w = region.shape
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw = int(h * sin + w * cos) + 1
    nh = int(h * cos + w * sin) + 1
    M[0, 2] += (nw - w) / 2.0
    M[1, 2] += (nh - h) / 2.0
    rot = cv2.warpAffine(region, M, (nw, nh))
    return rot, cv2.invertAffineTransform(M)


def _mitre_one_side(end, other, mid, floor_px: float, min_len_px: float) -> int:
    """Move one boundary's stalled ends onto the axis. Modifies `end` in place.

    NO joined-apex vs butt-joint gate, and the reason is measured (v2 Part 9 audit
    §3): both produce the SAME medial-axis topology — two arms plus a short apex
    spur — so the obvious "one branch versus two branches meeting" discriminator
    does not exist. A gate built on it measured inert and was removed.
    """
    import numpy as np

    original = end.copy()
    stalled = np.hypot(*(np.diff(end, axis=0).T)) < floor_px
    touched: list[int] = []
    run = 0
    for i in range(1, len(end)):
        # Only inside a RUN of stalled stations. A sharp vertex stalls one
        # boundary for several columns in a row; a straight stroke only throws
        # isolated short steps, and mitring those moved an end off its own outline
        # for nothing — measured as fresh dashes of missed edge band along every
        # arm of the letter probe.
        run = run + 1 if stalled[i - 1] else 0
        if run < MITRE_MIN_STALLED:
            continue
        # The AXIS must itself be advancing. Past a terminal the grid runs into the
        # cap padding, where `mid` is clamped to the axis end point and consecutive
        # stations share one coordinate — mitring there stamps ends into one hole.
        if float(np.hypot(*(mid[i] - mid[i - 1]))) < floor_px:
            continue
        if float(np.hypot(*(mid[i] - end[i - 1]))) < floor_px:
            continue          # the axis is no better here; leave it to the floor
        # Keep both adjacent path steps above the minimum stitch length. The path
        # is A0 B0 A1 B1…, so a mitred `a[i]` is reached from `b[i-1]` and left
        # towards `b[i]`. This is necessary but NOT sufficient — see
        # `_coalesce_short`, which is where the remaining interaction lives.
        if float(np.hypot(*(mid[i] - other[i]))) < min_len_px:
            continue
        if i > 0 and float(np.hypot(*(mid[i] - other[i - 1]))) < min_len_px:
            continue
        end[i] = mid[i]
        touched.append(i)
    return _revert_bad_mitres(end, original, touched, floor_px)


def _revert_bad_mitres(end, original, touched, floor_px: float) -> int:
    """Undo any mitre that made its own neighbourhood worse. Returns the net moved.

    `stalled` is computed once in `_mitre_one_side` and goes stale as points move,
    so a mitred end can end up crowding a column further along that was fine.
    """
    import numpy as np

    moved = len(touched)
    for i in touched:
        prv = float(np.hypot(*(end[i] - end[i - 1])))
        nxt = float(np.hypot(*(end[i] - end[i + 1]))) if i + 1 < len(end) else floor_px
        if min(prv, nxt) < floor_px:
            end[i] = original[i]
            moved -= 1
    return moved


def _mitre_stalled_side(a, b, mid, floor_px: float, min_len_px: float) -> int:
    """Walk stalled column ends back onto the medial axis — a satin mitre (v2 Part 8).

    At a sharp vertex the two boundaries are in direct conflict: the OUTER arc
    sweeps right around the corner and needs a column every pitch to cover it,
    while every one of those columns wants its INNER end on the reflex point, so
    the inner penetrations pile into a spot far tighter than the floor allows.
    Dropping the offending columns (what `_enforce_floor` does) opens the outer
    fan and leaves the apex bare; keeping them violates the floor.

    A hand digitizer resolves this with a mitre: the inner ends are laid along the
    corner's BISECTOR instead of into its point. The medial axis IS that bisector,
    by definition, and it advances station to station even where the boundary does
    not. Returns how many ends were moved.
    """
    return _mitre_one_side(a, b, mid, floor_px, min_len_px) + \
        _mitre_one_side(b, a, mid, floor_px, min_len_px)


def _distance_transform(binary):
    """`cv2.distanceTransform` (DIST_L2, mask 5) computed on the foreground box.

    Exact, not an approximation. The transform is 0 at every background pixel,
    so the untouched remainder of the canvas already holds its final value. For
    a foreground pixel sitting ``e`` px inside the tight box there is a
    background pixel at ``e + 1``, while anything the window cut away is at
    least ``e + DT_WINDOW_PAD_PX`` away, so the shortest chamfer path never
    leaves the window. Where the window clamps it is the real canvas edge.
    """
    import cv2
    import numpy as np

    out = np.zeros(binary.shape[:2], np.float32)
    win = _fg_window(binary, DT_WINDOW_PAD_PX)
    if win is None:
        return out
    y0, y1, x0, x1 = win
    out[y0:y1, x0:x1] = cv2.distanceTransform(
        np.ascontiguousarray(binary[y0:y1, x0:x1]), cv2.DIST_L2, 5)
    return out


def _fg_window(mask, pad: int):
    """Nonzero bounding box of ``mask`` grown by ``pad`` px, clamped to the canvas.

    Returns ``(y0, y1, x0, x1)`` as half-open slice bounds, or None when ``mask``
    is empty. Substituting the window for the full canvas is exact ONLY for an
    operator that is local with a reach of at most ``pad`` px AND returns 0 on
    all-zero input; every caller states the reach it relies on. Two axis
    reductions rather than np.nonzero, which materialises an index pair per set
    pixel just to take four extremes.
    """
    import numpy as np

    fg = mask > 0
    rows = np.flatnonzero(fg.any(axis=1))
    if rows.size == 0:
        return None
    cols = np.flatnonzero(fg.any(axis=0))
    h, w = mask.shape[:2]
    return (max(0, int(rows[0]) - pad), min(h, int(rows[-1]) + pad + 1),
            max(0, int(cols[0]) - pad), min(w, int(cols[-1]) + pad + 1))


def _uncovered_mask(binary, skel, max_half_px: float):
    """Everything satin could not reach — the caller's per-segment tatami fallback.

    Discs of the clamped half-width swept along the skeleton approximate the band
    the columns cover closely enough; the remainder is what needs tatami.
    """
    import cv2
    import numpy as np

    r = max(1, int(round(max_half_px)))
    fg = binary > 0
    rows = np.flatnonzero(fg.any(axis=1))
    out = np.zeros(fg.shape, np.uint8)
    if rows.size == 0:
        return out
    cols = np.flatnonzero(fg.any(axis=0))
    # Windowing is exact, not an approximation: the result is 0 wherever binary is
    # 0, so only binary's bbox can carry output; skel is a subset of binary, so the
    # r-radius dilate reaches at most r px beyond that bbox and the 3x3 open one px
    # further. A pad of r+2 therefore leaves every in-bbox pixel with the identical
    # neighbourhood it has on the full canvas, and the border ring the morphology
    # sees is all-zero either way (or the real canvas edge, once clamped).
    h, w = fg.shape[:2]
    y0, y1 = max(0, int(rows[0]) - r - 2), min(h, int(rows[-1]) + r + 3)
    x0, x1 = max(0, int(cols[0]) - r - 2), min(w, int(cols[-1]) + r + 3)
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    covered = cv2.dilate((skel[y0:y1, x0:x1] > 0).astype(np.uint8), disc)
    mask = (fg[y0:y1, x0:x1] & (covered == 0)).astype(np.uint8) * 255
    # Ignore slivers — a thin uncovered rim is the anti-aliased edge, not a region.
    out[y0:y1, x0:x1] = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return out


def _resample_closed(poly: list[tuple[float, float]], step: float) -> list[tuple[float, float]]:
    """Arc-length resample of a closed polygon: points spaced ~``step`` along the
    perimeter (INTERPOLATED, not just vertices — CHAIN_APPROX_SIMPLE gives corners only,
    so straight edges must be filled in)."""
    if len(poly) < 2:
        return list(poly)
    closed = list(poly) + [poly[0]]
    out = [closed[0]]
    since = 0.0
    for i in range(1, len(closed)):
        p0, p1 = closed[i - 1], closed[i]
        seg = _dist(p0, p1)
        if seg < 1e-9:
            continue
        pos = 0.0
        while since + (seg - pos) >= step:
            pos += step - since
            t = pos / seg
            out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
            since = 0.0
        since += seg - pos
    return out


def _resample_open(poly: list[tuple[float, float]], step: float) -> list[tuple[float, float]]:
    """Arc-length resample of an OPEN polyline (path), points spaced ~``step``. Unlike
    ``_resample_closed`` it does not wrap back to the start. Used for hand-drawn runs."""
    if len(poly) < 2:
        return list(poly)
    out = [poly[0]]
    since = 0.0
    for i in range(1, len(poly)):
        p0, p1 = poly[i - 1], poly[i]
        seg = _dist(p0, p1)
        if seg < 1e-9:
            continue
        pos = 0.0
        while since + (seg - pos) >= step:
            pos += step - since
            t = pos / seg
            out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
            since = 0.0
        since += seg - pos
    if out[-1] != poly[-1]:
        out.append(poly[-1])
    return out


def _drop_floor_reversals(pts, floor_px: float, max_px: float):
    """Drop one point of a running-stitch reversal that lands a same-side pair
    under the penetration floor (v2 Part 11; side choice made adaptive in 12).

    Where a medial-axis branch dead-ends, the underlay walks out to the tip and
    back down the SAME line, so the points either side of the turnaround coincide:
    ``... 57.0, 59.2, 61.4(tip), 59.2, 57.0 ...`` puts two penetrations 0.0mm
    apart. Locally that triple is indistinguishable from a satin column whose
    pitch has collapsed — same shape, same test — so the metric counts it, and it
    was the last floor violation left in the corpus after Part 10.

    The repair mirrors Part 10's: touch only what actually violates. One point of
    the coincident pair is removed, which restores the spacing while leaving the
    thread on the same line; the merged stitch must stay within ``MAX_STITCH_MM``
    or the point is kept and the violation reported honestly rather than traded
    for a long stitch. Triples containing a jump are skipped — a jump breaks the
    run, so the metric never sees them and the flag has to survive.
    """
    if floor_px <= 0.0 or len(pts) < 3:
        return pts
    out = list(pts)
    for _ in range(UNDERLAY_REPAIR_PASSES):
        dropped = False
        for i in range(1, len(out) - 1):
            a, b, c = out[i - 1], out[i], out[i + 1]
            if a[2] or b[2] or c[2]:
                continue
            gap = _dist(a, c)
            if gap >= floor_px or gap >= ZIGZAG_RATIO * min(_dist(a, b), _dist(b, c)):
                continue
            # Drop whichever side leaves the SMALLER merged stitch (v2 Part 12):
            # Part 11's fixed return-preference creates the longer merged span in
            # 49.5% of measured asymmetric turnarounds (Part 12 audit §2). Ties
            # keep the return side, preserving Part 11's output byte-for-byte.
            cand = []
            for k in (i + 1, i - 1):
                nxt = out[k + 1] if k + 1 < len(out) else None
                prv = out[k - 1] if k > 0 else None
                if nxt is not None and nxt[2]:
                    continue          # would swallow a jump
                merged = _dist(prv, nxt) if prv is not None and nxt is not None else 0.0
                if merged > max_px:
                    continue          # would exceed the machine-safe stitch length
                cand.append((merged, k))
            if cand:
                del out[min(cand, key=lambda mk: mk[0])[1]]
                dropped = True
                break
        if not dropped:
            break
    return out

def _flow_line_angle(flow_line, fallback_deg: float) -> float:
    """Fill angle from a user's Stitch Flow line, or the fallback (v2 Part 62).

    The line lives in design mm with y down — the same orientation as the image
    space `_scanline_angled` works in, so degrees(atan2(dy, dx)) needs no flip.
    Folded to [0, 180): rows have no head or tail. A degenerate line (fewer than
    two points, or both points coincident) falls back rather than inventing an
    angle from noise.
    """
    import math

    if not flow_line or len(flow_line) < 2:
        return fallback_deg
    a, b = flow_line[0], flow_line[-1]
    dx, dy = float(b.x) - float(a.x), float(b.y) - float(a.y)
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return fallback_deg
    return math.degrees(math.atan2(dy, dx)) % 180.0


def _flow_divide_valid(flow_divide) -> bool:
    """A divide line is usable when its endpoints are two distinct points.

    Same degeneracy rule as `_flow_line_angle`: a missing, single-point or
    zero-length divide means "no divide", never a guessed one (v2 Part 63).
    """
    if not flow_divide or len(flow_divide) < 2:
        return False
    a, b = flow_divide[0], flow_divide[-1]
    return abs(float(b.x) - float(a.x)) > 1e-9 or abs(float(b.y) - float(a.y)) > 1e-9


def _flow_side(flow_divide, x: float, y: float) -> float:
    """Signed side of (x, y) relative to the divide line's endpoints.

    Sign of the cross product (b-a) x (p-a). The mm->px transform used at
    rebuild is a positive uniform scale plus translation, so this sign matches
    the pixel-space half-plane split in `_split_mask_by_line` (v2 Part 63).
    """
    a, b = flow_divide[0], flow_divide[-1]
    return (float(b.x) - float(a.x)) * (y - float(a.y)) - (
        float(b.y) - float(a.y)
    ) * (x - float(a.x))


def _flow_side_angles(flow_divide, flow_line, flow_line_b, fallback_deg: float):
    """Per-side fill angles (positive side, negative side) of a valid divide.

    Each candidate direction line claims the side its MIDPOINT lies on; first
    claim wins (`flow_line` is considered before `flow_line_b`), and a side no
    line claims sews at the fallback — the object's automatic angle. A line
    whose midpoint sits exactly on the divide claims nothing: that placement is
    ambiguous and silence beats a coin flip (v2 Part 63).
    """
    angles = [fallback_deg, fallback_deg]
    claimed = [False, False]
    for line in (flow_line, flow_line_b):
        if not line or len(line) < 2:
            continue
        a, b = line[0], line[-1]
        mx = (float(a.x) + float(b.x)) / 2.0
        my = (float(a.y) + float(b.y)) / 2.0
        s = _flow_side(flow_divide, mx, my)
        if s == 0.0:
            continue
        i = 0 if s > 0 else 1
        if not claimed[i]:
            angles[i] = _flow_line_angle(line, fallback_deg)
            claimed[i] = True
    return angles[0], angles[1]


def _split_mask_by_line(mask, a_px, b_px):
    """Split a region mask into the two half-planes of a divide line.

    Pixels exactly on the line land on the positive side, so the two returned
    masks partition the region — no gap, no overlap (v2 Part 63).
    """
    import numpy as np

    h, w = mask.shape
    ys, xs = np.ogrid[0:h, 0:w]
    cross = (b_px[0] - a_px[0]) * (ys - a_px[1]) - (b_px[1] - a_px[1]) * (xs - a_px[0])
    inside = mask > 0
    pos = (inside & (cross >= 0)).astype(np.uint8) * 255
    neg = (inside & (cross < 0)).astype(np.uint8) * 255
    return pos, neg
