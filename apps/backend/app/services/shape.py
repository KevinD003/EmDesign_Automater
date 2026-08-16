"""Shape analysis primitives for digitizing quality (Phase 8.5).

The classical v1 digitizer classified satin columns with ``cv2.minAreaRect``, which
measures the bounding box of the WHOLE contour. For any shape that is not a straight
bar that is catastrophically wrong: a 3mm-wide curved swoosh reports a 42mm "width"
and is demoted to a tatami fill. Text, swooshes, rings and script lettering — the bulk
of real embroidery — therefore never became satin.

This module measures shapes the way a digitizer actually does:

- ``local_width`` — true stroke width from the distance transform (curve-invariant).
- ``geodesic_endpoints`` — the two ends of a column, measured THROUGH the shape
  (tree-diameter double-BFS), so an S-curve's ends are found correctly.
- ``column_rails`` — split a column outline into its two long sides ("rails"),
  handling both open columns (split at the geodesic ends) and closed rings
  (outer/inner contour), so satin can follow a curve instead of a straight axis.
- ``principal_angle`` — PCA long-axis angle, for per-region fill direction.

All functions take/return pixel-space data; mm conversion stays in the caller.
"""

from __future__ import annotations

from collections import deque

# Masks are downsampled to this before the O(pixels) BFS — keeps endpoint finding
# in the low milliseconds without meaningfully moving the endpoints.
_BFS_MAX_PX = 160


def local_width(region) -> tuple[float, float]:
    """Return ``(median_width_px, max_width_px)`` of a filled mask.

    Width is measured with the distance transform: for every interior pixel the
    distance to the nearest edge is half the local stroke width. Taking the median
    over the shape's *ridge* (the medial axis, approximated by the upper quantile of
    the distance field) gives a width that is invariant to curvature — unlike a
    bounding box.
    """
    import cv2
    import numpy as np

    dt = cv2.distanceTransform(region, cv2.DIST_L2, 5)
    vals = dt[dt > 0]
    if vals.size == 0:
        return 0.0, 0.0
    # The medial axis is where the distance field is locally maximal; the top decile
    # is a cheap, stable proxy that ignores the taper at the shape's edges.
    ridge = vals[vals >= np.quantile(vals, 0.90)]
    return float(np.median(ridge) * 2.0), float(vals.max() * 2.0)


def _bfs_far(mask, start: tuple[int, int]):
    """Farthest in-shape pixel from ``start`` by weighted geodesic distance.

    Diagonal steps cost sqrt(2), not 1. A plain 8-connected hop count undercounts any
    slanted path by up to 41%, which makes a diagonal-heavy shape (an S, a Z) look
    shorter — and therefore denser — than it is. Returns ``((y, x), distance)``.
    """
    import heapq
    import numpy as np

    h, w = mask.shape
    dist = np.full((h, w), np.inf, np.float64)
    sy, sx = start
    dist[sy, sx] = 0.0
    pq = [(0.0, sy, sx)]
    best, best_d = (sy, sx), 0.0
    steps = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
             (-1, -1, 1.4142135624), (-1, 1, 1.4142135624),
             (1, -1, 1.4142135624), (1, 1, 1.4142135624)]
    while pq:
        d, y, x = heapq.heappop(pq)
        if d > dist[y, x]:
            continue
        if d > best_d:
            best, best_d = (y, x), d
        for dy, dx, cost in steps:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and d + cost < dist[ny, nx]:
                dist[ny, nx] = d + cost
                heapq.heappush(pq, (d + cost, ny, nx))
    return best, best_d


def geodesic_endpoints(region) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """The two ends of a shape, measured *through* the shape (not across empty space).

    Double-BFS "tree diameter": the farthest point from any seed is one end; the
    farthest point from THAT is the other. Returns full-resolution ``(x, y)`` pairs,
    or None when the shape is too small / has no interior.
    """
    import cv2
    import numpy as np

    h, w = region.shape
    scale = min(1.0, _BFS_MAX_PX / max(h, w))
    small = (
        cv2.resize(region, (max(2, int(w * scale)), max(2, int(h * scale))), interpolation=cv2.INTER_NEAREST)
        if scale < 1.0
        else region
    )
    m = small > 0
    ys, xs = np.nonzero(m)
    if ys.size < 3:
        return None
    a, _ = _bfs_far(m, (int(ys[0]), int(xs[0])))
    b, d = _bfs_far(m, a)
    if d <= 1:
        return None
    inv = 1.0 / scale if scale < 1.0 else 1.0
    return (a[1] * inv, a[0] * inv), (b[1] * inv, b[0] * inv)


def _closest_index(contour_pts, pt) -> int:
    import numpy as np

    arr = np.asarray(contour_pts, np.float32)
    d = (arr[:, 0] - pt[0]) ** 2 + (arr[:, 1] - pt[1]) ** 2
    return int(np.argmin(d))


def _resample(poly, n: int):
    """Resample a polyline to exactly ``n`` arc-length-even points."""
    import numpy as np

    p = np.asarray(poly, np.float64)
    if len(p) < 2 or n < 2:
        return [tuple(v) for v in p]
    seg = np.hypot(*(p[1:] - p[:-1]).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total <= 1e-9:
        return [tuple(p[0])] * n
    targets = np.linspace(0.0, total, n)
    xs = np.interp(targets, cum, p[:, 0])
    ys = np.interp(targets, cum, p[:, 1])
    return list(zip(xs.tolist(), ys.tolist()))


def column_rails(region, stations: int):
    """Split an elongated region into its two long sides, resampled to ``stations`` points.

    Returns ``(rail_a, rail_b)`` running in the SAME direction end-to-end, so
    ``zip(rail_a, rail_b)`` yields opposing pairs across the column — which is exactly
    what a satin zigzag needs, and it follows curvature for free.

    Two topologies are handled:
    - **Ring** (region has an interior hole, e.g. a circular outline or the letter O):
      the rails are the outer and inner contours.
    - **Open column** (a bar, swoosh, or S-stroke): the outline is cut at the two
      geodesic endpoints, giving the two sides.
    """
    import cv2
    import numpy as np

    contours, hierarchy = cv2.findContours(region, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    hier = hierarchy[0] if hierarchy is not None else []
    outer_i = max(range(len(contours)), key=lambda i: cv2.contourArea(contours[i]))
    outer = [(float(x), float(y)) for x, y in contours[outer_i].reshape(-1, 2)]
    if len(outer) < 8:
        return None

    holes = [
        i for i in range(len(contours))
        if len(hier) and hier[i][3] == outer_i and cv2.contourArea(contours[i]) > 0.05 * cv2.contourArea(contours[outer_i])
    ]

    if holes:  # ---- ring: outer rail + inner rail ----
        inner_i = max(holes, key=lambda i: cv2.contourArea(contours[i]))
        inner = [(float(x), float(y)) for x, y in contours[inner_i].reshape(-1, 2)]
        if len(inner) < 8:
            return None
        a = _resample(outer + [outer[0]], stations)
        b = _resample(inner + [inner[0]], stations)
        # findContours returns outer CCW and holes CW (or vice versa); reverse the
        # inner rail so both run the same way round, then rotate it so the rails start
        # opposite each other — otherwise every crossing would slice across the ring.
        b = list(reversed(b))
        a0 = np.asarray(a[0])
        k = int(np.argmin([((np.asarray(p) - a0) ** 2).sum() for p in b]))
        b = b[k:] + b[:k]
        return a, b

    # ---- open column: cut the outline at the two geodesic ends ----
    ends = geodesic_endpoints(region)
    if ends is None:
        return None
    i = _closest_index(outer, ends[0])
    j = _closest_index(outer, ends[1])
    if i == j:
        return None
    if i > j:
        i, j = j, i
    side1 = outer[i:j + 1]
    side2 = outer[j:] + outer[:i + 1]
    if len(side1) < 3 or len(side2) < 3:
        return None
    a = _resample(side1, stations)
    b = _resample(list(reversed(side2)), stations)  # reversed → runs alongside `a`
    return a, b


def principal_angle(region) -> tuple[float, float]:
    """PCA long-axis ``(angle_degrees, elongation)`` of a filled mask.

    Used to aim a tatami fill along the shape instead of always stitching horizontally.
    """
    import numpy as np

    ys, xs = np.nonzero(region)
    if xs.size < 8:
        return 0.0, 1.0
    pts = np.stack([xs, ys]).astype(np.float64)
    pts -= pts.mean(axis=1, keepdims=True)
    cov = np.cov(pts)
    vals, vecs = np.linalg.eigh(cov)
    major = vecs[:, int(np.argmax(vals))]
    angle = float(np.degrees(np.arctan2(major[1], major[0])))
    lo, hi = float(min(vals)), float(max(vals))
    elong = float((hi / lo) ** 0.5) if lo > 1e-9 else 999.0
    return angle, elong


def geodesic_length(region) -> float:
    """Longest in-shape path length in full-resolution pixels (0.0 if unmeasurable)."""
    import cv2
    import numpy as np

    h, w = region.shape
    scale = min(1.0, _BFS_MAX_PX / max(h, w))
    small = (
        cv2.resize(region, (max(2, int(w * scale)), max(2, int(h * scale))), interpolation=cv2.INTER_NEAREST)
        if scale < 1.0
        else region
    )
    m = small > 0
    ys, xs = np.nonzero(m)
    if ys.size < 3:
        return 0.0
    a, _ = _bfs_far(m, (int(ys[0]), int(xs[0])))
    _, d = _bfs_far(m, a)
    return float(d) * (1.0 / scale if scale < 1.0 else 1.0)


def is_single_column(region, width_px: float, max_ratio: float = 1.45) -> bool:
    """True when a region is ONE satin column rather than a branching shape.

    Rail-pairing assumes a shape with exactly two ends and two long sides. A BRANCHING
    shape — a cross, a star, the letters T/H/K/X — has more than two ends, so cutting
    its outline at the two geodesic extremes leaves rails that wrap around the extra
    branch. Zigzagging between those rails throws stitches straight across the artwork
    (a visible diagonal that is not in the customer's image).

    The test is conservation of area: a genuine column of length L and width w covers
    about L*w. Every extra branch adds area that its longest path does not account for,
    so the ratio climbs. This separates true curved columns (an S, a C, a J — which a
    crossing-width test wrongly rejects because of their tight end curvature) from
    genuinely branching ones.
    """
    import cv2
    import numpy as np

    if width_px <= 0:
        return False

    # A CLOSED band (a ring, the letter O) has no ends at all, so its longest in-shape
    # path is only HALF its loop — using that as the length doubles the ratio and
    # rejects every ring. Measure a closed band by its medial loop instead: the mean of
    # the outer and inner contour perimeters. A shape that has a hole AND branches
    # (the letter A) still fails, because its legs add area the loop cannot account for.
    contours, hierarchy = cv2.findContours(region, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return False
    hier = hierarchy[0] if hierarchy is not None else []
    outer_i = max(range(len(contours)), key=lambda i: cv2.contourArea(contours[i]))
    holes = [
        i for i in range(len(contours))
        if len(hier) and hier[i][3] == outer_i
        and cv2.contourArea(contours[i]) > 0.05 * cv2.contourArea(contours[outer_i])
    ]
    if holes:
        inner_i = max(holes, key=lambda i: cv2.contourArea(contours[i]))
        length = (
            cv2.arcLength(contours[outer_i], True) + cv2.arcLength(contours[inner_i], True)
        ) / 2.0
    else:
        length = geodesic_length(region)
    if length <= 0:
        return False
    area = float(np.count_nonzero(region))
    predicted = length * width_px
    if predicted <= 0:
        return False
    return (area / predicted) <= max_ratio
