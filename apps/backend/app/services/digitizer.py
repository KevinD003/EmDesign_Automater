"""Auto-digitizing pipeline v1 — classical OpenCV, no ML (spec §4.2).

Pipeline: decode → scale to hoop → k-means color quantization → per-color masks →
contour regions → scanline (boustrophedon) fill stitches → Design with objects,
color stops, and a machine-valid stitch stream (COLOR_CHANGE / JUMP / TRIM / END).

Honest scope: this is the approximate classical-CV baseline (Phase 3). Satin
detection, underlay, pull compensation, and neural quality land in Phase 8.
cv2/numpy are imported lazily so the app boots without them.
"""

from __future__ import annotations

from app.services import segmentation
from app.models.design import (
    ColorStop,
    ConnectMethod,
    Design,
    DesignObject,
    Point,
    Stitch,
    StitchType,
    UnderlayType,
)

# Tunables (mm unless noted) — see spec "Quick Reference" table.
ROW_SPACING_MM = 0.45     # fill row pitch — full-coverage tatami (0.6 left fabric showing through)
MAX_STITCH_MM = 6.0       # subdivide longer runs (machine safety << 12.7mm)
MIN_REGION_MM2 = 2.0      # drop specks smaller than this. v1 used 4.0, which
                          # deleted the mascot's 2.6mm² freckles and similar
                          # deliberate small detail (v1 audit §5). 2.0 keeps them
                          # while still discarding anti-aliasing specks; going to
                          # 1.0 adds objects without recovering further detail.
CONNECT_MM = 3.0          # row-to-row travel below this = stitch, else JUMP
DEFAULT_MAX_COLORS = 6

# Satin classification (spec: min column 0.8mm, max width 10-12mm; we cap at 4mm
# where satin clearly beats tatami, and require an elongated shape).
SATIN_MIN_W_MM = 0.8
SATIN_MAX_W_MM = 4.0
SATIN_ASPECT = 2.5
SATIN_SPACING_MM = 0.4    # zigzag pitch along the column

# Underlay (spec §4.6): edge-walk inside fills, center-walk under satin columns.
UNDERLAY_STEP_MM = 2.0    # running-stitch length
EDGE_INSET_MM = 0.6       # edge-walk offset inside the region edge

_MAX_WORK_PX = 1200.0     # cap working resolution (raise = more detail, slower)

# ── v2 Part 1: layer preservation + contour smoothing ────────────────────────
# Two clusters closer than this in BGR are the same thread in practice; merging
# them stops the engine emitting two colour stops (two thread changes) for what
# a human sees as one colour.
MERGE_DELTA = 18.0

# A cluster within this distance of the substrate (border) colour is the garment
# showing through, not ink. Deliberately much tighter than v1's global 40.0 —
# at 40 the cream muzzle of fixture 08 (Δ 34.8) was deleted as "background".
SUBSTRATE_DELTA = 12.0
# ...unless the region is small and fully enclosed by ink (catchlights, small
# highlights). Above this share of the foreground a substrate-coloured region is
# the garment showing through and must not be stitched.
#
# Measured separation: a letter's counter is ~18% of the design's foreground and
# fixture 04's ring interior 32-54%, while genuine enclosed detail (catchlights)
# is well under 1%. Note this is a HEURISTIC over a genuine ambiguity — a glyph
# counter and knocked-out type are the same shape geometrically, distinguishable
# only by scale. Fixture 02's knocked-out type is unaffected because it is not
# substrate-coloured (Δ 19.9 from the page white), so it never reaches this rule.
SUBSTRATE_ENCLOSED_MAX_AREA = 0.05
# ...and an absolute cap, which is the discriminator that actually works: a
# highlight/catchlight is a few mm², a glyph counter at legible text sizes is
# tens of mm². Measured: mascot catchlight ≈4mm², the counter of a 25mm "O" ≈90mm².
SUBSTRATE_MAX_MM2 = 8.0

# Contour smoothing. Douglas-Peucker tolerance in mm, then Chaikin corner-cutting.
# Both are capped for small contours so fine features are not smoothed away —
# the audit requires fixture 08's freckles/catchlights and fixture 07's "L" to survive.
APPROX_EPS_MM = 0.10
CHAIKIN_ITERS = 1
SMOOTH_MIN_POINTS = 10    # below this a contour is left alone entirely
# Chaikin corner-cutting SHRINKS a polygon, and adjacent colour layers are
# smoothed independently, so an aggressive setting pulls neighbouring layers
# apart and opens bare-fabric wedges between them. Measured on fixture 01's
# gold/blue join (white area in the join region): v1 27.5% · 2 iterations at
# 0.18mm 41.1% (a real regression, caught in adversarial review) · 1 iteration
# at 0.10mm 27.8%, i.e. parity with v1 while still removing the pixel staircase.
# Anything stronger trades layer registration for edge smoothness — not worth it.

# Pull compensation (spec §4.6): widen the top fill/satin to counter fabric pull that
# narrows stitching. Higher for stretchy fabrics. Applied as a dilation (per side, mm).
PULL_BY_FABRIC = {
    "cotton": 0.2, "denim": 0.15, "twill": 0.15, "poplin": 0.15, "canvas": 0.15,
    "polo/knit": 0.4, "knit": 0.4, "jersey": 0.45, "fleece": 0.5,
    "cap": 0.3, "towel": 0.5, "terry": 0.5,
}
PULL_DEFAULT_MM = 0.25


def _default_pull(fabric_type: str) -> float:
    return PULL_BY_FABRIC.get((fabric_type or "").strip().lower(), PULL_DEFAULT_MM)


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


def _is_background(center_bgr, corners_bgr) -> bool:
    """v1 background test — kept only for the corner fallback path and tests.

    Superseded in v2 by ``segmentation.foreground_mask``: this compares COLOURS
    globally, so a design layer that happens to match the backdrop is deleted
    everywhere it appears. See the v1 baseline audit §5 root causes #1 and #2.
    """
    import numpy as np

    return bool(np.linalg.norm(center_bgr.astype(float) - corners_bgr.astype(float)) < 40.0)


def _drop_large_substrate_regions(mask, design_area_px: float, mm_per_px: float = 0.0, fg_mask=None):
    """Decide which garment-coloured regions are actually ink.

    Two independent tests, both of which a region must pass:

    * **Enclosure** — the region must be completely surrounded by ink. A
      catchlight sits inside a dark pupil and passes; the aperture of a "G" or
      "C" opens onto the background and fails. This is the test that carries the
      decision, because it is topological rather than a tuned magnitude.
    * **Size** — a region fully enclosed by ink can still be the garment showing
      through a closed outline (fixture 04's ring interior is enclosed by its
      ring). Small in both relative and absolute terms keeps highlights while
      rejecting large enclosed fields.
    """
    import cv2
    import numpy as np

    n, labelled, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    px_area = (mm_per_px * mm_per_px) if mm_per_px > 0 else 0.0
    outside = None if fg_mask is None else (fg_mask == 0)
    kernel = np.ones((5, 5), np.uint8)
    keep = np.zeros_like(mask)
    for i in range(1, n):
        area_px = stats[i, cv2.CC_STAT_AREA]
        if area_px > SUBSTRATE_ENCLOSED_MAX_AREA * design_area_px:
            continue
        if px_area and area_px * px_area > SUBSTRATE_MAX_MM2:
            continue
        if outside is not None:
            comp = (labelled == i).astype(np.uint8)
            halo = cv2.dilate(comp, kernel) > 0
            if bool((halo & outside).any()):
                continue  # opens onto the background — an aperture, not a highlight
        keep[labelled == i] = 255
    return keep


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


def digitize_image(
    data: bytes,
    fabric_type: str = "cotton",
    hoop_size: str = "100x100",
    max_colors: int = DEFAULT_MAX_COLORS,
    min_region_mm2: float = MIN_REGION_MM2,
) -> Design:
    """Convert an image into a stitch Design (classical CV baseline)."""
    import cv2
    import numpy as np

    buf = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image (expected PNG/JPEG/BMP/WebP)")

    hoop_w, hoop_h = _parse_hoop(hoop_size)
    ih, iw = img.shape[:2]
    mm_per_px = min(hoop_w / iw, hoop_h / ih) * 0.9  # 90% of hoop
    # Work at a bounded resolution for speed; keep mm scale consistent.
    if max(iw, ih) > _MAX_WORK_PX:
        f = _MAX_WORK_PX / max(iw, ih)
        img = cv2.resize(img, (int(iw * f), int(ih * f)), interpolation=cv2.INTER_AREA)
        mm_per_px /= f
        ih, iw = img.shape[:2]

    # ── Foreground/background separation (v2 Part 1) ──────────────────────────
    # Background is decided by WHERE a pixel is, not by what colour it is. The
    # v1 rule ("cluster colour within 40 of the corner average") deleted every
    # pixel of that colour anywhere in the frame, which is what removed fixture
    # 02's white type and fixture 08's cream muzzle while keeping fixture 09's
    # background. See services/segmentation.py.
    fg_mask, seg_method = segmentation.foreground_mask(img, data)
    if fg_mask.shape[:2] != (ih, iw):
        fg_mask = cv2.resize(fg_mask, (iw, ih), interpolation=cv2.INTER_NEAREST)
    fg_flat = fg_mask.reshape(-1) > 0
    if not fg_flat.any():  # segmentation found nothing — treat everything as ink
        fg_flat = np.ones(ih * iw, bool)
        fg_mask = np.full((ih, iw), 255, np.uint8)

    # K-means over FOREGROUND pixels only. v1 clustered the whole image, so the
    # background stole a cluster slot (hence its "+1 for background" fudge) and
    # dominated the centroids; excluding it means the requested colour budget is
    # spent entirely on real design layers.
    flat_rgb = img.reshape(-1, 3).astype(np.float32)
    Z = flat_rgb[fg_flat]
    k = max(1, min(int(max_colors), 8, len(np.unique(Z, axis=0))))
    _, fg_labels, centers = cv2.kmeans(
        Z, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS
    )
    centers = centers.astype(np.uint8)

    # Merge perceptually-identical centroids so one colour never becomes two
    # thread stops (a 1-colour wordmark asked to use 2 colours must return 1).
    remap = _merge_centers(centers, MERGE_DELTA)
    centers = np.array([centers[i] for i in sorted(set(remap.values()))], np.uint8)
    order = {old: new for new, old in enumerate(sorted(set(remap.values())))}

    labels = np.full(ih * iw, -1, np.int32)
    labels[fg_flat] = [order[remap[int(v)]] for v in fg_labels.reshape(-1)]
    labels = labels.reshape(ih, iw)

    substrate = _border_color(img)
    design_area_px = float(max(int(fg_flat.sum()), 1))

    # Darkest-first stitching order (spec §4.2). Clusters emptied by halo
    # suppression are skipped so they never open a colour stop.
    clusters = [
        (int(c.astype(int).sum()), idx, c)
        for idx, c in enumerate(centers)
        if bool((labels == idx).any())
    ]
    clusters.sort(key=lambda t: t[0])

    row_px = max(1, round(ROW_SPACING_MM / mm_per_px))
    max_step_px = max(2, round(MAX_STITCH_MM / mm_per_px))
    min_area_px = max(0.0, float(min_region_mm2)) / (mm_per_px * mm_per_px)
    connect_px = CONNECT_MM / mm_per_px

    stitches: list[Stitch] = []
    color_stops: list[ColorStop] = []
    objects: list[DesignObject] = []
    seq = 0

    emitted_stop = 0  # actual color-stop count — only clusters that yield objects get one
    for _, cluster_idx, center in clusters:
        mask = (labels == cluster_idx).astype(np.uint8) * 255
        # Opening removes speckle but also erases strokes ~2px wide (this is what
        # ate the "L" of HARBOR CLUB in fixture 07), so only open when the mask
        # is coarse enough to survive it.
        if cv2.countNonZero(cv2.erode(mask, np.ones((3, 3), np.uint8))) > 0.5 * cv2.countNonZero(mask):
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        # Substrate rule: a cluster the colour of the garment is only ink where it
        # forms a small enclosed element (knocked-out type, counters, catchlights).
        # A large expanse of it is the garment showing through a thin outline.
        if float(np.linalg.norm(center.astype(float) - substrate)) < SUBSTRATE_DELTA:
            mask = _drop_large_substrate_regions(mask, design_area_px, mm_per_px, fg_mask)
        # RETR_CCOMP: 2-level hierarchy — top-level outlines + their interior holes
        # (letter counters, donuts). RETR_EXTERNAL would fill an 'o' solid.
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        hier = hierarchy[0] if hierarchy is not None else []
        b, g, r = (int(v) for v in center)
        hexcol = f"#{r:02x}{g:02x}{b:02x}"

        this_stop = None  # opened lazily when this cluster's first real object appears
        stop_start = 0
        for ci, contour in enumerate(contours):
            if len(hier) and hier[ci][3] != -1:
                continue  # a hole — handled with its parent
            hole_contours = []
            if len(hier):
                child = hier[ci][2]
                while child != -1:
                    hole_contours.append(contours[child])
                    child = hier[child][0]
            net_area = cv2.contourArea(contour) - sum(cv2.contourArea(h) for h in hole_contours)
            if net_area < min_area_px:
                continue
            # Smooth the pixel staircase before it becomes stitches. Done here so
            # the stored contour (which drives rebuild) is smooth too, not just
            # this run's fill.
            contour = _smooth_contour(contour, mm_per_px)
            hole_contours = [_smooth_contour(h, mm_per_px) for h in hole_contours]
            region = np.zeros_like(mask)
            cv2.drawContours(region, [contour], -1, 255, thickness=cv2.FILLED)
            for h in hole_contours:
                cv2.drawContours(region, [h], -1, 0, thickness=cv2.FILLED)

            # Narrow elongated region → satin column; otherwise tatami fill.
            rect = cv2.minAreaRect(contour)
            w_mm = min(rect[1]) * mm_per_px
            l_mm = max(rect[1]) * mm_per_px
            is_satin = SATIN_MIN_W_MM <= w_mm <= SATIN_MAX_W_MM and l_mm / max(w_mm, 0.01) >= SATIN_ASPECT
            under_step_px = max(1, round(UNDERLAY_STEP_MM / mm_per_px))
            pull_mm = _default_pull(fabric_type)
            top_region = _dilate_pull(region, pull_mm, mm_per_px)  # pull comp widens the top layer
            if is_satin:
                satin_step_px = max(1, round(SATIN_SPACING_MM / mm_per_px))
                under = _center_walk(region, rect, under_step_px, connect_px)  # underlay on the true shape
                pts = _with_underlay(under, _satin_zigzag(top_region, rect, satin_step_px, connect_px, max_step_px), connect_px)
                underlay = UnderlayType.CENTER_WALK
            else:
                inset_px = max(1, round(EDGE_INSET_MM / mm_per_px))
                under = _edge_walk(region, inset_px, under_step_px, connect_px)
                pts = _with_underlay(under, _scanline_fill(top_region, row_px, max_step_px, connect_px), connect_px)
                underlay = UnderlayType.EDGE_WALK
            pts = _coalesce_short(pts, MIN_STITCH_MM / mm_per_px)
            if len(pts) < 2:
                continue
            if this_stop is None:  # first real object → open a color stop (deferred COLOR_CHANGE)
                emitted_stop += 1
                this_stop = emitted_stop
                if emitted_stop > 1 and stitches:
                    stitches.append(Stitch(x=stitches[-1].x, y=stitches[-1].y, command="COLOR_CHANGE"))
                stop_start = len(stitches)
            obj_start = len(stitches)
            if stitches and stitches[-1].command != "COLOR_CHANGE":
                stitches.append(Stitch(x=stitches[-1].x, y=stitches[-1].y, command="TRIM"))
                stitches.append(Stitch(x=pts[0][0] * mm_per_px, y=pts[0][1] * mm_per_px, command="JUMP"))
            for (x, y, jump) in pts:
                stitches.append(
                    Stitch(x=x * mm_per_px, y=y * mm_per_px, command="JUMP" if jump else "STITCH")
                )
            seq += 1
            count = len(stitches) - obj_start
            outline = [
                Point(x=float(px_) * mm_per_px, y=float(py_) * mm_per_px)
                for px_, py_ in contour.reshape(-1, 2)
            ]
            hole_outlines = [
                [Point(x=float(px_) * mm_per_px, y=float(py_) * mm_per_px) for px_, py_ in h.reshape(-1, 2)]
                for h in hole_contours
            ] or None
            objects.append(
                DesignObject(
                    sequence_order=seq,
                    name=f"{'Satin' if is_satin else 'Fill'} {seq} ({hexcol})",
                    stitch_type=StitchType.SATIN if is_satin else StitchType.TATAMI,
                    color_stop=this_stop,
                    density=1.0 / (SATIN_SPACING_MM if is_satin else ROW_SPACING_MM),
                    stitch_angle=round(float(rect[2]), 1) if is_satin else 0.0,
                    underlay_type=underlay,
                    pull_compensation=round(pull_mm, 2),
                    entry_point=Point(x=pts[0][0] * mm_per_px, y=pts[0][1] * mm_per_px),
                    exit_point=Point(x=pts[-1][0] * mm_per_px, y=pts[-1][1] * mm_per_px),
                    connect_method=ConnectMethod.TRIM,
                    stitch_count=count,
                    contour=outline,
                    holes=hole_outlines,
                )
            )

        if this_stop is not None:  # cluster produced no stitchable objects → no phantom stop
            color_stops.append(
                ColorStop(
                    stop_number=this_stop,
                    thread_brand="Auto",
                    catalog_number="",
                    thread_name=f"Color {this_stop}",
                    hex=hexcol,
                    stitch_count=len(stitches) - stop_start,
                )
            )

    if stitches:
        last = stitches[-1]
        stitches.append(Stitch(x=last.x, y=last.y, command="END"))

    xs = [s.x for s in stitches if s.command == "STITCH"] or [0.0]
    ys = [s.y for s in stitches if s.command == "STITCH"] or [0.0]

    return Design(
        name="Digitized image",
        width_mm=round(max(xs) - min(xs), 2),
        height_mm=round(max(ys) - min(ys), 2),
        hoop_size=hoop_size,
        fabric_type=fabric_type,
        stitch_count=sum(1 for s in stitches if s.command == "STITCH"),
        color_stops=color_stops,
        objects=objects,
        stitches=stitches,
        status="digitized",
    )


def _scanline_fill(region, row_px: int, max_step_px: int, connect_px: float):
    """Boustrophedon scanline fill of a filled-contour mask.

    Returns [(x_px, y_px, is_jump)] — stitch points row by row, alternating
    direction; long runs subdivided; far row-to-row moves flagged as jumps.
    """
    import numpy as np

    pts: list[tuple[float, float, bool]] = []
    h = region.shape[0]
    left_to_right = True
    for y in range(0, h, row_px):
        cols = np.flatnonzero(region[y])
        if cols.size == 0:
            continue
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
            n = max(1, round(abs(b - a) / max_step_px))
            for i in range(1, n + 1):
                pts.append((a + (b - a) * i / n, float(y), False))
        left_to_right = not left_to_right
    return pts


MIN_STITCH_MM = 0.5  # below this a needle penetration risks thread break / needle strike


def _coalesce_short(pts, min_dist_px: float):
    """Drop needle penetrations closer together than ``min_dist_px``.

    Sub-0.5mm stitches break thread and damage needles, and they buy nothing —
    the shape is unchanged because the following point is still stitched. Jumps
    and the final point are always kept so the path and outline stay intact.
    """
    if not pts or min_dist_px <= 0:
        return pts
    out = [pts[0]]
    for p in pts[1:]:
        if p[2]:  # a jump defines the path; never coalesce it away
            out.append(p)
            continue
        if _dist(out[-1], p) < min_dist_px:
            continue
        out.append(p)
    if out[-1][:2] != pts[-1][:2]:
        out.append(pts[-1])
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
        for i in range(1, n + 1):
            p = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            pts.append((p[0], p[1], False))
            prev = p
        top = not top
    if pts:
        pts[0] = (pts[0][0], pts[0][1], True)  # enter the column with a jump
    return pts


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


def _run_along(poly_px, step_px: int, connect_px: float, first_jump: bool = True):
    """Running stitch around a closed polygon, resampled at ``step_px``. For appliqué
    placement / tackdown outlines. Returns [(x, y, is_jump)]."""
    pts_in = [(float(x), float(y)) for x, y in poly_px.reshape(-1, 2)]
    samples = _resample_closed(pts_in, max(1.0, float(step_px)))
    if len(samples) < 2:
        return []
    return [(samples[0][0], samples[0][1], first_jump)] + [(p[0], p[1], False) for p in samples[1:]]


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


def _satin_border(poly_px, width_px: float, step_px: int, connect_px: float):
    """Satin border along a closed contour (appliqué edge cover): resample the outline,
    then at each sample emit ±half-width points along the local normal, alternating to
    zig-zag across the edge. Returns [(x, y, is_jump)]."""
    pts_in = [(float(x), float(y)) for x, y in poly_px.reshape(-1, 2)]
    if len(pts_in) < 3:
        return []
    samples = _resample_closed(pts_in, max(1.0, float(step_px)))
    if len(samples) < 3:
        return []
    half = width_px / 2.0
    out: list[tuple[float, float, bool]] = []
    top = True
    n = len(samples)
    for i, p in enumerate(samples):
        nxt = samples[(i + 1) % n]
        dx, dy = nxt[0] - p[0], nxt[1] - p[1]
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / length, dx / length  # unit normal
        a = (p[0] + nx * half, p[1] + ny * half)
        b = (p[0] - nx * half, p[1] - ny * half)
        pair = (a, b) if top else (b, a)
        for j, q in enumerate(pair):
            out.append((float(q[0]), float(q[1]), i == 0 and j == 0))
        top = not top
    return out


def _edge_walk(region, inset_px: int, step_px: int, connect_px: float):
    """Edge-walk underlay: a running stitch along the region outline, inset inside
    the edge (spec §4.6). Returns [(x_px, y_px, is_jump)]."""
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
    return pts


def _center_walk(region, rect, step_px: int, connect_px: float):
    """Center-walk underlay for a satin column: a running stitch down the column's
    long-axis midline (spec §4.6). Returns [(x_px, y_px, is_jump)]."""
    import cv2
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


def _with_underlay(under, top, connect_px: float):
    """Prepend underlay points to the top stitching; the transition becomes a plain
    stitch when the two are close, otherwise a jump."""
    if not under:
        return top
    if top:
        x, y, _ = top[0]
        top = [(x, y, _dist(under[-1], (x, y)) > connect_px)] + top[1:]
    return under + top


def _scanline_angled(region, angle_deg: float, row_px: int, max_step_px: int, connect_px: float):
    """Scanline fill at an arbitrary angle: rotate the mask so rows are horizontal,
    fill, then map points back through the inverse rotation."""
    import cv2
    import numpy as np

    if abs(angle_deg) < 0.5:
        return _scanline_fill(region, row_px, max_step_px, connect_px)
    h, w = region.shape
    rot, Minv = _warp_fit(region, (w / 2.0, h / 2.0), angle_deg)
    out = []
    for x, y, jump in _scanline_fill(rot, row_px, max_step_px, connect_px):
        X = Minv[0, 0] * x + Minv[0, 1] * y + Minv[0, 2]
        Y = Minv[1, 0] * x + Minv[1, 1] * y + Minv[1, 2]
        out.append((float(X), float(Y), jump))
    return out


def rebuild_design(design: Design) -> Design:
    """Regenerate the whole stitch stream from object contours + parameters.

    Every object must carry a ``contour`` (only digitized designs do). Objects are
    re-filled with their CURRENT stitch_type / density / stitch_angle, so editing a
    parameter and rebuilding applies the edit. Raises ValueError if not regenerable.
    """
    import cv2
    import numpy as np

    objs = sorted(design.objects, key=lambda o: o.sequence_order)
    if not objs:
        raise ValueError("Design has no objects to rebuild (imported stitch files are not regenerable)")
    if any(not o.contour for o in objs):
        raise ValueError("Some objects have no contour — design is not regenerable")

    xs = [p.x for o in objs for p in o.contour]
    ys = [p.y for o in objs for p in o.contour]
    minx, miny = min(xs), min(ys)
    w_mm = max(max(xs) - minx, 1.0)
    h_mm = max(max(ys) - miny, 1.0)
    px_per_mm = min(4.0, 800.0 / max(w_mm, h_mm))  # ≤800px canvas
    mm_per_px = 1.0 / px_per_mm
    pad = 2
    cw, ch = int(w_mm * px_per_mm) + 2 * pad, int(h_mm * px_per_mm) + 2 * pad

    def to_px(p: Point) -> tuple[int, int]:
        return (int((p.x - minx) * px_per_mm) + pad, int((p.y - miny) * px_per_mm) + pad)

    def to_mm(x: float, y: float) -> tuple[float, float]:
        return ((x - pad) * mm_per_px + minx, (y - pad) * mm_per_px + miny)

    max_step_px = max(2, round(MAX_STITCH_MM / mm_per_px))
    connect_px = CONNECT_MM / mm_per_px

    stitches: list[Stitch] = []
    new_objects: list[DesignObject] = []
    stop_counts: dict[int, int] = {}

    ordered_stops = sorted(design.color_stops, key=lambda c: c.stop_number)
    for stop_i, stop in enumerate(ordered_stops):
        if stop_i > 0 and stitches:
            prev = stitches[-1]
            stitches.append(Stitch(x=prev.x, y=prev.y, command="COLOR_CHANGE"))
        stop_start = len(stitches)

        for o in (ob for ob in objs if ob.color_stop == stop.stop_number):
            mask = np.zeros((ch, cw), np.uint8)
            poly = np.array([to_px(p) for p in o.contour], np.int32)
            cv2.fillPoly(mask, [poly], 255)
            for hole in o.holes or []:
                cv2.fillPoly(mask, [np.array([to_px(p) for p in hole], np.int32)], 0)

            st = o.stitch_type.value if hasattr(o.stitch_type, "value") else o.stitch_type
            ut = o.underlay_type.value if hasattr(o.underlay_type, "value") else o.underlay_type
            spacing_mm = 1.0 / max(float(o.density) or 1.0, 0.2)
            spacing_px = max(1, round(spacing_mm / mm_per_px))
            under_step_px = max(1, round(UNDERLAY_STEP_MM / mm_per_px))
            top = _dilate_pull(mask, float(o.pull_compensation or 0.0), mm_per_px)  # honor edited pull comp
            if st == "APPLIQUE":
                # placement outline → tackdown → satin edge cover (spec §4.3)
                run_step = max(2, round(2.0 / mm_per_px))
                border_px = max(2, round(2.0 / mm_per_px))  # 2mm satin border
                sat_step = max(1, round(SATIN_SPACING_MM / mm_per_px))
                pts = (
                    _run_along(poly, run_step, connect_px, True)
                    + _run_along(poly, run_step, connect_px, False)
                    + _satin_border(poly, border_px, sat_step, connect_px)
                )
            elif st == "SATIN":
                rect = cv2.minAreaRect(poly)
                pts = _satin_zigzag(top, rect, spacing_px, connect_px, max_step_px)
                if ut and ut != "NONE":  # any non-NONE underlay → center-walk for satin
                    pts = _with_underlay(_center_walk(mask, rect, under_step_px, connect_px), pts, connect_px)
            elif st in ("RUNNING_SINGLE", "RUNNING_DOUBLE", "RUNNING_TRIPLE", "BACKSTITCH", "REDWORK", "MANUAL"):
                # Running stitch ALONG the drawn path (open polyline), not an area fill.
                passes = {"RUNNING_DOUBLE": 2, "BACKSTITCH": 2, "RUNNING_TRIPLE": 3}.get(st, 1)
                pts = _manual_run(poly, max_step_px, passes)
            else:
                pts = _scanline_angled(top, float(o.stitch_angle), spacing_px, max_step_px, connect_px)
                if ut and ut != "NONE":  # any non-NONE underlay → edge-walk for fills
                    inset_px = max(1, round(EDGE_INSET_MM / mm_per_px))
                    pts = _with_underlay(_edge_walk(mask, inset_px, under_step_px, connect_px), pts, connect_px)
            pts = _coalesce_short(pts, MIN_STITCH_MM / mm_per_px)
            if len(pts) < 2:
                continue

            if stitches and stitches[-1].command != "COLOR_CHANGE":
                last = stitches[-1]
                stitches.append(Stitch(x=last.x, y=last.y, command="TRIM"))
                ex, ey = to_mm(pts[0][0], pts[0][1])
                stitches.append(Stitch(x=ex, y=ey, command="JUMP"))
            obj_start = len(stitches)
            for x, y, jump in pts:
                mx, my = to_mm(x, y)
                stitches.append(Stitch(x=mx, y=my, command="JUMP" if jump else "STITCH"))

            entry = to_mm(pts[0][0], pts[0][1])
            exit_ = to_mm(pts[-1][0], pts[-1][1])
            new_objects.append(
                o.model_copy(
                    update={
                        "stitch_count": len(stitches) - obj_start,
                        "entry_point": Point(x=entry[0], y=entry[1]),
                        "exit_point": Point(x=exit_[0], y=exit_[1]),
                    }
                )
            )
        stop_counts[stop.stop_number] = len(stitches) - stop_start

    if stitches:
        last = stitches[-1]
        stitches.append(Stitch(x=last.x, y=last.y, command="END"))

    sxs = [s.x for s in stitches if s.command == "STITCH"] or [0.0]
    sys_ = [s.y for s in stitches if s.command == "STITCH"] or [0.0]
    new_stops = [
        c.model_copy(update={"stitch_count": stop_counts.get(c.stop_number, 0)}) for c in ordered_stops
    ]
    return design.model_copy(
        update={
            "stitches": stitches,
            "objects": new_objects,
            "color_stops": new_stops,
            "stitch_count": sum(1 for s in stitches if s.command == "STITCH"),
            "width_mm": round(max(sxs) - min(sxs), 2),
            "height_mm": round(max(sys_) - min(sys_), 2),
        }
    )
