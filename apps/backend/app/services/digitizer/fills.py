"""Fill generators: scanline, contour, spiral, radial, and fill angle."""

from __future__ import annotations

from app.services.digitizer.constants import (
    _STAGGER_END_GUARD,
    FILL_ANGLE_DEFAULT_DEG,
    FILL_ANGLE_MIN_ELONGATION,
    FILL_STAGGER_ROWS,
    MIN_ARC_SAMPLES,
)
from app.services.digitizer.geometry import (
    _dist,
    _fg_window,
    _resample_closed,
    _subdivide_long,
    _warp_fit,
)


def _edge_avoiding_angle(region) -> float:
    """Fill angle for a region with no meaningful long axis (v2 Part 24).

    A flat 45 degrees is the industry default and is right for a disc, but it is
    wrong for a DIAMOND — the corpus has one — because 45 is exactly the
    direction the diamond's own edges run, and rows parallel to a dominant edge
    are the classic amateur tell: the last row runs alongside the boundary and
    any mismatch between the pitch and the remaining strip reads as a stripe.
    Rows PERPENDICULAR to a dominant edge are just as bad the other way, because
    then every row END lands on it and the ragged terminations line up.

    So the angle is chosen to sit as close to 45 degrees away from the region's
    strong edge directions as it can. Penalty per boundary segment is
    ``|cos(2 * (theta - edge))|``, which is 1 when the row is parallel OR
    perpendicular to that edge and 0 at exactly 45 degrees off, weighted by
    segment length so a long straight side outvotes a wobble in the outline.

    Falls back to FILL_ANGLE_DEFAULT_DEG when the boundary has no preferred
    direction at all — a circle, where the penalty is flat and every candidate
    ties, which is exactly the case 45 was the right default for.
    """
    import math

    import cv2

    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    # Length-weighted histogram of edge orientations, 5-degree bins, mod 180.
    #
    # A histogram and not a vector mean: the mean of a doubled-angle vector
    # cannot represent a BIMODAL boundary, and the case that matters is exactly
    # bimodal. A diamond's edges run at +45 and -45; doubled those are +90 and
    # -90, which cancel to zero, so a mean reports "no preferred direction" for
    # the one shape whose direction most needs avoiding. Measured: the vector
    # form returned 45.0 for the diamond, i.e. rows straight down its own edges.
    nbins = 36
    hist = [0.0] * nbins
    total = 0.0
    for c in contours:
        pts = c.reshape(-1, 2)
        if len(pts) < 8:
            continue
        # Chord over several pixels, not pixel-to-pixel: consecutive contour
        # pixels only ever step at multiples of 45 degrees, so a per-pixel
        # histogram reports every shape as axis-aligned-plus-diagonals.
        span = 5
        for i in range(0, len(pts), span):
            a, b = pts[i], pts[(i + span) % len(pts)]
            dx, dy = float(b[0] - a[0]), float(b[1] - a[1])
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            hist[int(math.degrees(math.atan2(dy, dx)) % 180.0 / (180.0 / nbins)) % nbins] += L
            total += L
    if total <= 0:
        return FILL_ANGLE_DEFAULT_DEG

    # |cos(2 * delta)| is 1 when the row is parallel OR perpendicular to an edge
    # and 0 at exactly 45 degrees off it, so minimising the weighted sum puts the
    # rows as far from every strong edge as the shape allows.
    centres = [(i + 0.5) * (180.0 / nbins) for i in range(nbins)]
    scored = []
    for deg in range(180):
        pen = sum(w * abs(math.cos(2.0 * math.radians(deg - e)))
                  for w, e in zip(hist, centres) if w)
        scored.append((pen / total, float(deg)))
    best, worst = min(scored)[0], max(scored)[0]
    # A flat landscape means the boundary has no preferred direction at all — a
    # disc — which is precisely the case the industry's flat 45 was right for.
    if worst - best < 0.05:
        return FILL_ANGLE_DEFAULT_DEG
    ang = min(scored, key=lambda s: (s[0], abs(s[1] - 45.0)))[1] % 180.0
    return round(ang - 180.0 if ang > 90.0 else ang, 1)


def _spiral_fill(region, row_px: int, max_step_px: int, connect_px: float):
    """Archimedean spiral fill (v2 Part 26). [(x_px, y_px, is_jump)].

    ONE continuous path from the centre outward, turns spaced ``row_px`` apart —
    which means a disc gets ZERO interior row-ends: the classic "curved fill
    effect" the desktop suites sell, and the strongest possible answer to the
    ragged-row-end problem for round shapes. The centre is the distance
    transform's peak (the point deepest inside the region), not the bbox centre,
    so an off-centre blob spirals around its own body.

    Points outside the region are clipped: the walk marks a jump when it leaves
    and re-enters, so a non-circular region gets spiral arcs clipped to its own
    outline — downstream travel routing then decides what those hops become.
    """
    import math

    import cv2
    import numpy as np

    m = (region > 0).astype(np.uint8)
    if cv2.countNonZero(m) == 0:
        return []
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    _mn, _mx, _mnl, (cx, cy) = cv2.minMaxLoc(dist)
    h, w = m.shape
    # Far corner distance bounds the spiral's outer radius.
    r_max = max(math.hypot(px - cx, py - cy) for px in (0, w) for py in (0, h))
    pitch = max(1.0, float(row_px))
    b = pitch / (2.0 * math.pi)  # r = b * theta

    pts: list[tuple[float, float, bool]] = []
    theta = 0.0
    was_inside = False
    while b * theta <= r_max:
        r = b * theta
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        iy, ix = round(y), round(x)
        inside = 0 <= iy < h and 0 <= ix < w and m[iy, ix] > 0
        if inside:
            pts.append((float(x), float(y), not was_inside and bool(pts)))
        was_inside = inside
        # Advance by ~a third of the pitch of ARC length, so the polyline hugs
        # the curve near the centre and stays bounded far out; clamp keeps the
        # very first steps (r ~ 0) from spinning forever.
        theta += min(0.8, max(0.05, (pitch / 3.0) / max(r, pitch / 3.0)))
    return _subdivide_long(pts, max_step_px)


def _radial_fill(region, row_px: int, max_step_px: int, connect_px: float):
    """Radial (sunburst) fill (v2 Part 26). [(x_px, y_px, is_jump)].

    Spokes through the distance-transform peak, angle-stepped so the RIM spacing
    equals the row pitch. The classic radial problem is the centre: spokes that
    all reach it stack penetrations into one hole. Staggering solves it — every
    second spoke stops at half radius, every fourth at three-quarters — the same
    trick sunburst engravings use, and the density metric is the referee.

    Spokes alternate direction (out on one, back on the next via the rim) so
    consecutive spokes connect at their shared end instead of jumping.
    """
    import math

    import cv2
    import numpy as np

    m = (region > 0).astype(np.uint8)
    if cv2.countNonZero(m) == 0:
        return []
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    _mn, _mx, _mnl, (cx, cy) = cv2.minMaxLoc(dist)
    h, w = m.shape
    ys, xs = np.nonzero(m)
    r_max = float(np.hypot(xs - cx, ys - cy).max())
    pitch = max(1.0, float(row_px))
    n_spokes = max(8, round(2.0 * math.pi * r_max / pitch))

    def clip_ray(angle: float, r_inner: float):
        """Points of the ray from r_inner to the region edge, inside only."""
        out = []
        steps = int(r_max - r_inner) + 1
        for s in range(steps + 1):
            r = r_inner + s
            x, y = cx + r * math.cos(angle), cy + r * math.sin(angle)
            iy, ix = round(y), round(x)
            if 0 <= iy < h and 0 <= ix < w and m[iy, ix] > 0:
                out.append((float(x), float(y)))
            elif out:
                break  # left the region: this spoke ends here
        return out

    pts: list[tuple[float, float, bool]] = []
    for i in range(n_spokes):
        angle = 2.0 * math.pi * i / n_spokes
        # Stagger: deepest spokes stop at 2 pitches out, not at the centre —
        # the first version sent every 4th spoke to r=0 and the density metric
        # counted 59 penetrations in ONE cell there, an order of magnitude past
        # the flag level. No spoke may touch the hub.
        r_inner = max(2.0 * pitch, (0.08, 0.5, 0.25, 0.5)[i % 4] * r_max)
        ray = clip_ray(angle, r_inner)
        if len(ray) < 2:
            continue
        if i % 2 == 1:
            ray.reverse()  # in on odd spokes: consecutive spokes share the rim
        first = not pts or _dist(pts[-1], ray[0]) > connect_px
        pts.append((ray[0][0], ray[0][1], first))
        pts.append((ray[-1][0], ray[-1][1], False))
    # The keep-out leaves a bare hub ~2 pitches across; a short spiral covers it
    # in the same curved idiom, one continuous path, no stacked holes.
    hub = np.zeros_like(m)
    cv2.circle(hub, (int(cx), int(cy)), int(2.5 * pitch), 255, -1)
    hub = cv2.bitwise_and(hub, m * 255)
    centre = _spiral_fill(hub, row_px, max_step_px, connect_px)
    if centre:
        x, y, _f = centre[0]
        centre[0] = (x, y, bool(pts) and _dist(pts[-1], (x, y)) > connect_px)
    return _subdivide_long(pts + centre, max_step_px)


def _contour_fill(region, row_px: int, max_step_px: int, connect_px: float, start=None):
    """Fill whose rows FOLLOW the outline rather than crossing it (v2 Part 24b).

    Returns [(x_px, y_px, is_jump)]. This is the "curved fill" the desktop suites
    sell as contour / parallel fill, and the shape it exists for is a ring: no
    straight angle is right for an annulus, because a straight row crosses the
    band at 90 degrees at two points and runs along it at two others, so the
    ragged row-ends bunch on the inside of the curve and the fill reads as a
    stack of chords rather than a band.

    Rows are ISO-DISTANCE curves of the region's own distance transform, spaced
    ``row_px`` apart in that distance — and distance-to-boundary is measured
    perpendicular to the boundary by definition, so the perpendicular spacing
    between neighbouring rows is exactly the row pitch everywhere, including
    where the band bends. Offsetting the outline polygon instead would need
    self-intersection cleanup at every concave turn; the distance transform gets
    that for free because a pinched region simply splits into two components at
    the level where it pinches.
    """
    import cv2
    import numpy as np

    dist = cv2.distanceTransform((region > 0).astype(np.uint8), cv2.DIST_L2, 5)
    peak = float(dist.max())
    if peak <= 0.0:
        return []
    # One pixel tighter than the nominal row pitch, and the pixel is the point.
    # A scanline fill's rows are exact: row y and row y+row_px are row_px apart by
    # construction. A contour row is the boundary of `dist >= level`, and `dist`
    # lives on the pixel grid, so each extracted row sits within +/-0.5px of its
    # true iso-distance curve — which means two neighbouring rows can end up a
    # full pixel FURTHER apart than nominal, and that pixel is wider than the
    # 0.05mm of slack a 0.45mm pitch leaves against 0.4mm thread.
    #
    # Measured: at the nominal pitch, fixture 03 scored 98.4 interior and fixture
    # 07 98.0, against 99.4 / 98.9 for the straight fill they replaced. One pixel
    # tighter, both reach 99.4 / 99.0 — i.e. equal and slightly better. Multipliers
    # of 0.9, 0.8 and 0.7 all produced byte-identical output because they round to
    # the same integer pixel, which is the tell that the defect was quantisation
    # and not density.
    step = max(1.0, float(row_px) - 1.0)
    # Start half a pitch in, so the first row sits a half-pitch from the edge
    # exactly as a scanline fill's first row does, and run past the peak so the
    # ridge down the middle of the band is covered rather than left as a seam.
    levels = list(np.arange(step / 2.0, peak + step, step))

    out: list[tuple[float, float, bool]] = []
    cur = (float(start[0]), float(start[1])) if start else None
    for level in levels:
        band = (dist >= level).astype(np.uint8) * 255
        if cv2.countNonZero(band) == 0:
            continue
        loops, _h = cv2.findContours(band, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        polys = []
        for loop in loops:
            pts = [(float(x), float(y)) for x, y in loop.reshape(-1, 2)]
            if len(pts) < MIN_ARC_SAMPLES:
                continue
            polys.append(_resample_closed(pts, max(1.0, float(max_step_px))))
        # Nearest-first within a level, so a level that has split into several
        # islands does not hop back and forth between them.
        while polys:
            if cur is None:
                idx = 0
            else:
                idx = min(range(len(polys)),
                          key=lambda i: min(_dist(cur, p) for p in polys[i]))
            poly = polys.pop(idx)
            if cur is not None:
                # Enter the loop at its closest point and walk from there, so the
                # step in from the previous row is one pitch rather than a trip
                # back to an arbitrary contour origin.
                s = min(range(len(poly)), key=lambda i: _dist(cur, poly[i]))
                poly = poly[s:] + poly[:s]
            poly = poly + [poly[0]]  # close the loop
            first = cur is None or _dist(cur, poly[0]) > connect_px
            out.append((poly[0][0], poly[0][1], first))
            for p in poly[1:]:
                out.append((p[0], p[1], False))
            cur = (poly[-1][0], poly[-1][1])
    return out


def _fill_angle(region) -> float:
    """`_fill_angle_provenance` without the provenance — see there."""
    return _fill_angle_provenance(region)[0]


def _fill_angle_provenance(region) -> tuple[float, bool]:
    """Fill direction for a region, plus whether it came from a real long axis.

    The bool is what CTO A6's alternation keys on: an angle derived from the
    region's own long axis is a property of the shape and must be obeyed, while
    the isotropic fallback is an arbitrary (if edge-aware) choice — successive
    isotropic fills may rotate it 90 degrees to spread push/pull, and can do so
    for free because `_edge_avoiding_angle`'s penalty |cos(2(theta-edge))| has
    period 90: the rotated angle avoids exactly the same edges exactly as well.

    Returns the orientation of the principal (major) axis when the shape is
    elongated enough for that axis to be meaningful, else FILL_ANGLE_DEFAULT_DEG.
    The value is in the same convention `_scanline_angled` takes: measured on
    image axes (y down), mod 180, and emitted stitches run in that direction —
    verified by measuring the length-weighted direction of the points the filler
    actually returns, not by reasoning about `getRotationMatrix2D`'s sign.

    The axis comes from central image moments, which weigh every foreground
    pixel, rather than from `minAreaRect`, which is decided by the few extreme
    points on the hull: a plus sign, a ring and a star all have a square hull and
    would get an arbitrary rect angle, while their moment axis correctly reports
    them as isotropic and hands them the 45-degree default.
    """
    import math

    import cv2

    m = cv2.moments(region, binaryImage=True)
    if m["m00"] <= 0:
        return FILL_ANGLE_DEFAULT_DEG, False
    mu20 = m["mu20"] / m["m00"]
    mu02 = m["mu02"] / m["m00"]
    mu11 = m["mu11"] / m["m00"]
    # Eigenvalues of [[mu20, mu11], [mu11, mu02]]; both are >= 0 for a real
    # covariance, and the discriminant cannot go negative, so no clamping games.
    half = (mu20 + mu02) / 2.0
    disc = math.sqrt(max(0.0, ((mu20 - mu02) / 2.0) ** 2 + mu11 * mu11))
    lam_hi, lam_lo = half + disc, half - disc
    if lam_lo <= 1e-9 or math.sqrt(lam_hi / lam_lo) < FILL_ANGLE_MIN_ELONGATION:
        return _edge_avoiding_angle(region), False
    ang = math.degrees(0.5 * math.atan2(2.0 * mu11, mu20 - mu02)) % 180.0
    # Fold to (-90, 90]. A fill direction is an axis, not a heading — 175 and -5
    # lay the same rows — and the folded form keeps `_scanline_angled`'s
    # near-horizontal short-circuit reachable for a shape that measures 179.8.
    return round(ang - 180.0 if ang > 90.0 else ang, 1), True


def _fill_by_component(region, row_px: int, max_step_px: int, connect_px: float, start=None,
                       angle_deg: float = 0.0):
    """Scanline-fill each connected component separately, nearest-first (v2 Part 13).

    A scattered mask — the too-wide remainder of a satin object is the real case
    — used to be serpentined as ONE region, so every row hopped between every
    fragment: measured 435 of fixture 07's 979 jumps came from exactly this.
    Filling fragment-by-fragment turns per-row hops into one transition per
    fragment. `start` (px) seeds the ordering at the caller's current needle
    position; single-component masks take the old path unchanged.

    `angle_deg` is the object's fill direction (v2 Part 24). It is applied to
    every component of the object rather than recomputed per fragment: the
    multi-component case is the too-wide REMAINDER of one satin stroke, and
    letting each shard pick its own axis would fan a single stroke into a dozen
    directions. Angle per OBJECT is what the desktop suites expose, too.
    """
    import cv2
    import numpy as np

    n, labels, _stats, cents = cv2.connectedComponentsWithStats(region, connectivity=8)
    if n <= 2:
        return _scanline_angled(region, angle_deg, row_px, max_step_px, connect_px)
    remaining = list(range(1, n))
    cur = (float(start[0]), float(start[1])) if start else (0.0, 0.0)
    out: list[tuple[float, float, bool]] = []
    while remaining:
        idx = min(remaining, key=lambda i: (cents[i][0] - cur[0]) ** 2 + (cents[i][1] - cur[1]) ** 2)
        remaining.remove(idx)
        cur = (float(cents[idx][0]), float(cents[idx][1]))
        pts = _scanline_angled((labels == idx).astype(np.uint8) * 255, angle_deg,
                               row_px, max_step_px, connect_px)
        if not pts:
            continue
        if out:
            x, y, _ = pts[0]
            pts[0] = (x, y, _dist(out[-1], (x, y)) > connect_px)
        out.extend(pts)
    return out


def _scanline_fill(region, row_px: int, max_step_px: int, connect_px: float):
    """Boustrophedon scanline fill of a filled-contour mask.

    Returns [(x_px, y_px, is_jump)] — stitch points row by row, alternating
    direction; long runs subdivided on a STAGGERED grid; far row-to-row moves
    flagged as jumps.

    Interior penetrations sit on an absolute grid offset by the row's place in
    the FILL_STAGGER_ROWS cycle — measured from the segment's absolute left end,
    not its travel start, so the stagger diagonal runs one way across the whole
    fill instead of herringboning with the serpentine direction.
    """
    import math

    import numpy as np

    pts: list[tuple[float, float, bool]] = []
    h = region.shape[0]
    left_to_right = True
    row_idx = 0
    step = max(1.0, float(max_step_px))
    guard = _STAGGER_END_GUARD * step
    for y in range(0, h, row_px):
        cols = np.flatnonzero(region[y])
        if cols.size == 0:
            continue
        phase = (row_idx % FILL_STAGGER_ROWS) / FILL_STAGGER_ROWS
        row_idx += 1
        # Split the row into contiguous runs (handles concave shapes/holes).
        splits = np.flatnonzero(np.diff(cols) > 1)
        runs = np.split(cols, splits + 1)
        segs = [(int(rn[0]), int(rn[-1])) for rn in runs if rn.size >= 2]
        if not segs:
            continue
        segs.sort(key=lambda s: s[0], reverse=not left_to_right)
        for x0, x1 in segs:
            a, b = (x0, x1) if left_to_right else (x1, x0)
            first = not pts or _dist(pts[-1], (a, y)) > connect_px
            pts.append((float(a), float(y), first))
            lo, hi = (a, b) if a < b else (b, a)
            inner = []
            s = lo + phase * step
            while s < hi:
                if lo + guard <= s <= hi - guard:
                    inner.append(s)
                s += step
            if a > b:
                inner.reverse()
            # ceil() end-gap repair (CTO A6/C8): the stagger grid + end guard
            # leaves the span from a row end to its nearest kept penetration
            # unbounded by `step` — worst case step*(1+2*guard), measured
            # 15.9mm on a 75mm fill at the 12.7mm machine cap, i.e. OVER the
            # cap. Any over-step gap in [a, inner..., b] is subdivided into
            # ceil(gap/step) parts, each <= step. The split points carry the
            # row's own stagger PHASE (fractions (k+phase)/n, all parts still
            # <= gap/n): unstaggered equal splits put the two legs of an
            # out-and-back row pair — a thin tongue nearly parallel to the
            # rows — needle-into-needle, measured 0.146mm same-side pairs on
            # fixture 07's Fill 2, and `_drop_floor_reversals` cannot repair a
            # retrace whose merged stitch would exceed the machine cap.
            row = [float(a), *(float(s) for s in inner), float(b)]
            filled: list[float] = [row[0]]
            for nxt in row[1:]:
                gap = abs(nxt - filled[-1])
                if gap > step:
                    n = math.ceil(gap / step)
                    base, d = filled[-1], nxt - filled[-1]
                    ks = [k + phase for k in range(n)] if phase > 1e-9 else range(1, n)
                    filled.extend(base + d * k_ / n for k_ in ks)
                filled.append(nxt)
            for s in filled[1:]:
                pts.append((float(s), float(y), False))
        left_to_right = not left_to_right
    return pts


def _scanline_angled(region, angle_deg: float, row_px: int, max_step_px: int, connect_px: float):
    """Scanline fill at an arbitrary angle: rotate the mask so rows are horizontal,
    fill, then map points back through the inverse rotation.

    THE ROTATION IS ABOUT THE REGION'S OWN CROP, NOT THE CANVAS (CTO verdict
    STEP 3). It used to be `_warp_fit(region, (w/2, h/2), ...)` — the centre of
    whatever canvas the region happened to be sitting on — and `_warp_fit` then
    offsets the fitted output by `(nw - w)/2`, which depends on the canvas
    dimensions too. Both terms leak the canvas into the row grid, so the SAME
    shape at the SAME angle got a different fill depending on where else objects
    sat around it. Measured on a 120x80 rectangle at 30 degrees:

        canvas 300x300 vs 300x420, region unmoved   every stitch up to 0.83px off
        region translated +100px, canvas unchanged  up to 35.16px off

    35px is a different row phase entirely — the fill was not a property of the
    object at all. digitize rasters at ~18px/mm on the image and rebuild at
    10px/mm on the bounding box of every object, so the two paths never agreed
    on the grid; and moving one object re-phased its neighbours, which would
    have made B2's move/scale/rotate silently restitch things the user did not
    touch.

    Cropping to the region's own foreground window makes the fitted size, the
    rotation centre and hence the row phase depend on nothing but the region's
    own pixels. `_skeleton_satin_hires` already worked this way.
    """
    if abs(angle_deg) < 0.5:
        return _scanline_fill(region, row_px, max_step_px, connect_px)
    win = _fg_window(region, 1)
    if win is None:
        return []
    y0, y1, x0, x1 = win
    crop = region[y0:y1, x0:x1]
    ch, cw = crop.shape
    rot, Minv = _warp_fit(crop, (cw / 2.0, ch / 2.0), angle_deg)
    out = []
    for x, y, jump in _scanline_fill(rot, row_px, max_step_px, connect_px):
        X = Minv[0, 0] * x + Minv[0, 1] * y + Minv[0, 2] + x0
        Y = Minv[1, 0] * x + Minv[1, 1] * y + Minv[1, 2] + y0
        out.append((float(X), float(Y), jump))
    return out
