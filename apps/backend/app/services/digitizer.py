"""Auto-digitizing pipeline v1 — classical OpenCV, no ML (spec §4.2).

Pipeline: decode → scale to hoop → k-means color quantization → per-color masks →
contour regions → scanline (boustrophedon) fill stitches → Design with objects,
color stops, and a machine-valid stitch stream (COLOR_CHANGE / JUMP / TRIM / END).

Honest scope: this is the approximate classical-CV baseline (Phase 3). Satin
detection, underlay, pull compensation, and neural quality land in Phase 8.
cv2/numpy are imported lazily so the app boots without them.
"""

from __future__ import annotations

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
from app.services import shape

# Tunables (mm unless noted) — see spec "Quick Reference" table.
# Fill row pitch. 0.6mm was sparse enough to leave fabric showing between rows with
# standard 40wt thread (~0.4mm laid width); 0.40mm is the industry-standard tatami
# density and is what makes a fill read as solid.
ROW_SPACING_MM = 0.40
MAX_STITCH_MM = 6.0       # subdivide longer runs (machine safety << 12.7mm)
MIN_REGION_MM2 = 4.0      # drop specks smaller than this
CONNECT_MM = 3.0          # row-to-row travel below this = stitch, else JUMP
DEFAULT_MAX_COLORS = 6

# Satin classification (spec: min column 0.8mm, max width 10-12mm). Width is measured
# from the DISTANCE TRANSFORM (services/shape.local_width), not a bounding box, so a
# curved swoosh or a ring is classified on its true stroke width. Length is derived as
# area/width, which is likewise curvature-invariant (a bounding box is not).
SATIN_MIN_W_MM = 0.8
SATIN_MAX_W_MM = 6.0      # above this, split-satin/tatami reads better than one column
SATIN_ASPECT = 2.5
SATIN_SPACING_MM = 0.4    # spacing between penetrations on the SAME rail (visible density)

# Tatami stagger (spec §4.3): consecutive rows must not put their needle penetrations
# on the same x, or the fill shows a straight "split line" down the shape. Fractions of
# one stitch length, cycled row to row — the classic 4-step brick pattern.
STAGGER_PATTERN = (0.0, 0.5, 0.25, 0.75)
FILL_STITCH_MM = 4.0      # nominal tatami stitch length (subdivision pitch within a row)
FILL_DEFAULT_ANGLE = 45.0  # blobby regions: 45° avoids aligning with the fabric weave
FILL_ELONGATION_MIN = 1.6  # above this, fill along the shape's own long axis instead

# Travel runs (spec §4.6): short hops between objects are stitched as a running stitch
# (hidden under later layers) instead of TRIM + JUMP. Trims are slow and leave tails.
TRAVEL_MAX_MM = 8.0
TRAVEL_STEP_MM = 2.0

# Underlay (spec §4.6): edge-walk inside fills, center-walk under satin columns.
UNDERLAY_STEP_MM = 2.0    # running-stitch length
EDGE_INSET_MM = 0.6       # edge-walk offset inside the region edge

_MAX_WORK_PX = 1200.0     # cap working resolution (raise = more detail, slower)

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
    """A cluster is background if it sits close to the average corner color."""
    import numpy as np

    return bool(np.linalg.norm(center_bgr.astype(float) - corners_bgr.astype(float)) < 40.0)


def _background_clusters(labels, centers_lab, n_clusters: int) -> set[int]:
    """Identify backdrop clusters from the image BORDER RING, not the four corners.

    The v1 rule compared each cluster to the average of the 4 corner pixels. One
    subject touching one corner poisons that average, the true backdrop stops matching,
    and the entire background is stitched as a solid object (measured on a subject-in-
    corner test: a 3038-stitch white block with 132 jumps). Border-ring occupancy is
    unaffected by a subject touching an edge.

    Guards:
    - if no cluster dominates the ring, the image is full-bleed (a photo, not artwork
      on a backdrop) and nothing is treated as background;
    - a cluster perceptually close to the dominant backdrop is also background, which
      catches patterned/striped backdrops.
    """
    import numpy as np

    h, w = labels.shape
    band = max(2, int(min(h, w) * 0.01))
    ring = np.concatenate([
        labels[:band, :].ravel(), labels[-band:, :].ravel(),
        labels[:, :band].ravel(), labels[:, -band:].ravel(),
    ])
    if ring.size == 0:
        return set()
    share = np.bincount(ring, minlength=n_clusters).astype(np.float64) / ring.size
    dominant = int(np.argmax(share))
    if share[dominant] < 0.45:
        return set()  # full-bleed image — no backdrop to remove
    bg = set()
    for c in range(n_clusters):
        if share[c] >= 0.35:
            bg.add(c)
        elif share[c] >= 0.08 and float(np.linalg.norm(centers_lab[c] - centers_lab[dominant])) < 25.0:
            bg.add(c)  # same backdrop, different shade (stripes, gradients, paper tone)
    return bg


def _decode(data: bytes):
    """Decode to ``(bgr, alpha_mask_or_None)``.

    ``IMREAD_COLOR`` silently DISCARDS the alpha channel, which destroys the most
    common real upload: a logo on a transparent background. A dark logo then becomes
    indistinguishable from the (also-black) transparent area and the whole canvas
    digitizes as one blob. Decoding UNCHANGED and keeping alpha as an explicit
    foreground mask fixes that outright.
    """
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Could not decode image (expected PNG/JPEG/BMP/WebP)")
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), None
    if img.shape[2] == 4:
        alpha = img[..., 3]
        bgr = img[..., :3].copy()
        # Composite over white so semi-transparent edges quantize toward the artwork
        # colour rather than toward black.
        a = (alpha.astype(np.float32) / 255.0)[..., None]
        bgr = (bgr.astype(np.float32) * a + 255.0 * (1.0 - a)).astype(np.uint8)
        return bgr, (alpha > 127).astype(np.uint8) * 255
    return img[..., :3].copy(), None


def _quantize(img, k: int, fg_mask):
    """K-means colour quantization in CIE L*a*b*, over foreground pixels only.

    Two corrections over the v1 BGR clustering:
    - **L*a*b***: Euclidean distance in Lab approximates *perceived* colour difference,
      so clusters split where a human sees a different colour. In BGR the same distance
      means different things in different parts of the cube, which mangles skin tones,
      greens and shadows.
    - **Foreground-only**: fitting over background pixels wastes cluster budget on the
      backdrop — a 6-colour logo on white would spend a centre describing the white.

    Returns ``(labels_hw, centers_bgr)``.
    """
    import cv2
    import numpy as np

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    h, w = lab.shape[:2]
    flat = lab.reshape(-1, 3).astype(np.float32)
    sel = (fg_mask.reshape(-1) > 0) if fg_mask is not None else np.ones(h * w, bool)
    if sel.sum() < k:
        sel = np.ones(h * w, bool)
    sample = flat[sel]
    k = max(1, min(k, int(sel.sum())))
    _, lbl, centers = cv2.kmeans(
        sample, k, None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 5, cv2.KMEANS_PP_CENTERS,
    )
    # Assign every pixel (including background) to its nearest centre so the label map
    # stays whole-image; background pixels get masked out by the caller.
    d = ((flat[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    labels = np.argmin(d, axis=1).reshape(h, w)

    counts = np.bincount(labels.reshape(-1)[sel], minlength=len(centers)).astype(np.float64)
    centers, labels = _merge_near_clusters(centers, labels, counts)
    centers_bgr = cv2.cvtColor(centers.astype(np.uint8)[None, ...], cv2.COLOR_LAB2BGR)[0]
    return labels, centers_bgr, centers


# Two Lab colours closer than this read as the SAME thread — no thread chart resolves
# finer, and no embroiderer would load a second needle for it.
DELTA_E_MERGE = 12.0


def _merge_near_clusters(centers, labels, counts):
    """Merge clusters that are perceptually identical (Lab ΔE < ``DELTA_E_MERGE``).

    Anti-aliased artwork has a fringe of intermediate colours along every edge, and
    k-means happily spends real cluster budget describing it — on a 2-colour logo, 4 of
    6 centres went to fringe bands of 41-608 px. Those bands fall under the minimum
    region area and get dropped, so the pixels they stole are simply never stitched
    (measured: 95%→78% coverage). Merging by ΔE returns them to their parent colour.
    """
    import numpy as np

    n = len(centers)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = np.argsort(-counts)  # merge small clusters into large ones
    for a_i in range(n):
        for b_i in range(a_i + 1, n):
            a, b = int(order[a_i]), int(order[b_i])
            if find(a) == find(b):
                continue
            if float(np.linalg.norm(centers[a] - centers[b])) < DELTA_E_MERGE:
                parent[find(b)] = find(a)

    roots = sorted({find(i) for i in range(n)})
    remap = {r: i for i, r in enumerate(roots)}
    lut = np.array([remap[find(i)] for i in range(n)], np.int32)

    new_centers = np.zeros((len(roots), 3), np.float32)
    for r in roots:
        members = [i for i in range(n) if find(i) == r]
        w = counts[members]
        tot = w.sum()
        new_centers[remap[r]] = (
            (centers[members] * w[:, None]).sum(axis=0) / tot if tot > 0 else centers[members].mean(axis=0)
        )
    return new_centers, lut[labels]


def _prefilter(img):
    """Edge-preserving smoothing before quantization.

    Photos and re-saved JPEGs carry noise and ringing that k-means turns into thousands
    of speckle regions (each one an object, a trim and two jumps). A bilateral filter
    flattens those while keeping the hard colour edges that become stitch boundaries.
    """
    import cv2

    return cv2.bilateralFilter(img, d=7, sigmaColor=45, sigmaSpace=7)


def _segment_inside(mask, a, b, samples: int = 24) -> bool:
    """True when the straight segment a→b stays inside ``mask`` (both in pixel space)."""
    h, w = mask.shape[:2]
    for i in range(samples + 1):
        t = i / samples
        x = int(round(a[0] + (b[0] - a[0]) * t))
        y = int(round(a[1] + (b[1] - a[1]) * t))
        if not (0 <= x < w and 0 <= y < h) or mask[y, x] == 0:
            return False
    return True


def _subdivide(pts, max_step_px: float):
    """Split any segment longer than ``max_step_px`` so no stitch exceeds the machine limit."""
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    for prev, cur in zip(pts, pts[1:]):
        d = _dist(prev, cur)
        n = max(1, int(-(-d // max_step_px)))  # ceil
        for i in range(1, n + 1):
            out.append((prev[0] + (cur[0] - prev[0]) * i / n, prev[1] + (cur[1] - prev[1]) * i / n))
    return out


def _center_walk_rails(rail_a, rail_b, step_px: float):
    """Center-walk underlay for a rail-defined satin column.

    ``_center_walk`` rotates the region and takes the mid-row of each column, which is
    only correct for a straight bar. On a RING it returns the midpoint between the top
    and bottom arcs — i.e. a straight chord across the middle of the circle, stitched
    as a visible line that is not in the artwork. Halfway between the two rails is the
    column's true midline for any curvature. Returns [(x, y, is_jump)].
    """
    mids = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in zip(rail_a, rail_b)]
    if len(mids) < 2:
        return []
    out = [mids[0]]
    acc = 0.0
    for prev, cur in zip(mids, mids[1:]):
        acc += _dist(prev, cur)
        if acc >= step_px:
            out.append(cur)
            acc = 0.0
    if out[-1] != mids[-1]:
        out.append(mids[-1])
    if len(out) < 2:
        return []
    return [(out[0][0], out[0][1], True)] + [(p[0], p[1], False) for p in out[1:]]


def _satin_from_rails(rail_a, rail_b, max_step_px: float, pull_px: float = 0.0):
    """True satin zigzag across a column defined by its two rails.

    At each station the needle alternates rails, so every stitch crosses the column —
    and because the rails follow the outline, the column follows curvature (an S-stroke
    or a ring stitches correctly, which a single-angle rotation cannot do).

    ``pull_px`` extends each crossing outward at BOTH ends: pull compensation belongs
    across the column's width only, never along its length (an isotropic dilation also
    lengthens the column, smearing its ends).
    """
    raw: list[tuple[float, float]] = []
    for i, (a, b) in enumerate(zip(rail_a, rail_b)):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = (dx * dx + dy * dy) ** 0.5
        if L < 1e-9:
            continue
        ux, uy = dx / L, dy / L
        A = (a[0] - ux * pull_px, a[1] - uy * pull_px)
        B = (b[0] + ux * pull_px, b[1] + uy * pull_px)
        raw.append(A if i % 2 == 0 else B)
    if len(raw) < 2:
        return []
    pts = _subdivide(raw, max_step_px)
    return [(pts[0][0], pts[0][1], True)] + [(p[0], p[1], False) for p in pts[1:]]


def digitize_image(
    data: bytes,
    fabric_type: str = "cotton",
    hoop_size: str = "100x100",
    max_colors: int = DEFAULT_MAX_COLORS,
) -> Design:
    """Convert an image into a stitch Design (classical CV baseline)."""
    import cv2
    import numpy as np

    img, alpha_fg = _decode(data)

    hoop_w, hoop_h = _parse_hoop(hoop_size)
    ih, iw = img.shape[:2]
    mm_per_px = min(hoop_w / iw, hoop_h / ih) * 0.9  # 90% of hoop
    # Work at a bounded resolution for speed; keep mm scale consistent.
    if max(iw, ih) > _MAX_WORK_PX:
        f = _MAX_WORK_PX / max(iw, ih)
        img = cv2.resize(img, (int(iw * f), int(ih * f)), interpolation=cv2.INTER_AREA)
        if alpha_fg is not None:
            alpha_fg = cv2.resize(alpha_fg, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        mm_per_px /= f
        ih, iw = img.shape[:2]

    img = _prefilter(img)

    if alpha_fg is not None:
        # Alpha is authoritative: quantize the visible artwork only, spend the whole
        # colour budget on it, and skip backdrop detection entirely.
        fg_mask = alpha_fg
        k = max(1, min(int(max_colors), 8))
        labels, centers, _lab = _quantize(img, k, fg_mask)
        clusters = [(int(c.astype(int).sum()), idx, c) for idx, c in enumerate(centers)]
    else:
        # Quantize over ALL pixels, with extra budget so the backdrop (and its shades)
        # get their own clusters. The backdrop must be REPRESENTED in the label map for
        # the border-ring rule to identify it — fitting over a guessed foreground makes
        # every background pixel fall into an artwork cluster, and the whole image is
        # then either kept or dropped together.
        k = max(2, min(int(max_colors) + 2, 10))
        labels, centers, centers_lab = _quantize(img, k, None)
        bg = _background_clusters(labels, centers_lab, len(centers))
        keep = [i for i in range(len(centers)) if i not in bg]
        clusters = [(int(centers[i].astype(int).sum()), i, centers[i]) for i in keep]
        fg_mask = np.isin(labels, keep).astype(np.uint8) * 255
    # Darkest-first stitching order (spec §4.2).
    clusters.sort(key=lambda t: t[0])
    if not clusters:  # image was all "background" — keep the darkest cluster anyway
        darkest = min(range(len(centers)), key=lambda i: int(centers[i].astype(int).sum()))
        clusters = [(0, darkest, centers[darkest])]

    row_px = max(1, round(ROW_SPACING_MM / mm_per_px))
    max_step_px = max(2, round(MAX_STITCH_MM / mm_per_px))
    min_area_px = MIN_REGION_MM2 / (mm_per_px * mm_per_px)
    connect_px = CONNECT_MM / mm_per_px

    stitches: list[Stitch] = []
    color_stops: list[ColorStop] = []
    objects: list[DesignObject] = []
    seq = 0

    emitted_stop = 0  # actual color-stop count — only clusters that yield objects get one
    for _, cluster_idx, center in clusters:
        mask = (labels == cluster_idx).astype(np.uint8) * 255
        mask = cv2.bitwise_and(mask, fg_mask)  # never stitch the background
        # OPEN clears speckle, CLOSE fills the pinholes that quantization punches into
        # otherwise-solid areas (each pinhole would otherwise become a spurious hole).
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
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
            region = np.zeros_like(mask)
            cv2.drawContours(region, [contour], -1, 255, thickness=cv2.FILLED)
            for h in hole_contours:
                cv2.drawContours(region, [h], -1, 0, thickness=cv2.FILLED)

            # --- Satin vs fill, decided on TRUE stroke width (not a bounding box) ---
            rect = cv2.minAreaRect(contour)
            med_w_px, _ = shape.local_width(region)
            w_mm = med_w_px * mm_per_px
            # Length from area/width is curvature-invariant, so an S-stroke or a ring
            # measures its real run length rather than its bounding diagonal.
            len_mm = (net_area * mm_per_px * mm_per_px) / max(w_mm, 0.01)
            is_satin = (
                SATIN_MIN_W_MM <= w_mm <= SATIN_MAX_W_MM
                and len_mm / max(w_mm, 0.01) >= SATIN_ASPECT
            )
            under_step_px = max(1, round(UNDERLAY_STEP_MM / mm_per_px))
            pull_mm = _default_pull(fabric_type)
            rails = None
            if is_satin:
                # One station per half-spacing: alternating rails puts penetrations on
                # each side SATIN_SPACING_MM apart, which is the density the user sees.
                station_px = max(1.0, (SATIN_SPACING_MM / 2.0) / mm_per_px)
                stations = int(min(4000, max(4, round(len_mm / mm_per_px / station_px))))
                # Reject branching shapes (a cross, a star, the letters H/K/X): their
                # rails are not the two sides of one column, so zigzagging between them
                # lays stitches straight across the artwork.
                rails = (
                    shape.column_rails(region, stations)
                    if shape.is_single_column(region, med_w_px)
                    else None
                )
                is_satin = rails is not None

            fill_angle = 0.0
            if is_satin:
                pull_px = (pull_mm / 2.0) / mm_per_px
                under = _center_walk_rails(rails[0], rails[1], under_step_px)
                pts = _with_underlay(
                    under, _satin_from_rails(rails[0], rails[1], max_step_px, pull_px), connect_px
                )
                underlay = UnderlayType.CENTER_WALK
            else:
                top_region = _dilate_pull(region, pull_mm, mm_per_px)  # pull comp widens the top layer
                # Aim the fill along the shape; blobby regions get 45° so rows never run
                # parallel to the fabric weave (a flat, banded look).
                ang, elong = shape.principal_angle(region)
                fill_angle = ang if elong >= FILL_ELONGATION_MIN else FILL_DEFAULT_ANGLE
                inset_px = max(1, round(EDGE_INSET_MM / mm_per_px))
                under = _edge_walk(region, inset_px, under_step_px, connect_px)
                fill_step_px = max(2, round(FILL_STITCH_MM / mm_per_px))
                pts = _with_underlay(
                    under,
                    _scanline_angled(top_region, fill_angle, row_px, fill_step_px, connect_px),
                    connect_px,
                )
                underlay = UnderlayType.EDGE_WALK
            if len(pts) < 2:
                continue
            if this_stop is None:  # first real object → open a color stop (deferred COLOR_CHANGE)
                emitted_stop += 1
                this_stop = emitted_stop
                if emitted_stop > 1 and stitches:
                    stitches.append(Stitch(x=stitches[-1].x, y=stitches[-1].y, command="COLOR_CHANGE"))
                stop_start = len(stitches)
            obj_start = len(stitches)
            connect = ConnectMethod.TRIM
            if stitches and stitches[-1].command != "COLOR_CHANGE":
                ex, ey = pts[0][0] * mm_per_px, pts[0][1] * mm_per_px
                last = stitches[-1]
                gap = _dist((last.x, last.y), (ex, ey))
                # A travel run is only invisible if it stays ON this colour's own
                # artwork, where surrounding stitching hides it. Crossing bare fabric
                # (between two strokes of a line drawing, say) would show as a stray
                # thread that is not in the customer's image, so that must be a trim.
                covered = _segment_inside(
                    mask, (last.x / mm_per_px, last.y / mm_per_px), (pts[0][0], pts[0][1])
                )
                if gap <= TRAVEL_MAX_MM and covered:
                    # Short hop → walk there with running stitches (hidden by later
                    # layers) instead of TRIM + JUMP. Trims are slow and leave tails.
                    n = max(1, int(-(-gap // TRAVEL_STEP_MM)))
                    for i in range(1, n + 1):
                        stitches.append(Stitch(
                            x=last.x + (ex - last.x) * i / n,
                            y=last.y + (ey - last.y) * i / n,
                            command="STITCH",
                        ))
                    connect = ConnectMethod.TRAVEL_RUN
                else:
                    stitches.append(Stitch(x=last.x, y=last.y, command="TRIM"))
                    stitches.append(Stitch(x=ex, y=ey, command="JUMP"))
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
                    stitch_angle=round(float(rect[2]), 1) if is_satin else round(fill_angle, 1),
                    underlay_type=underlay,
                    pull_compensation=round(pull_mm, 2),
                    entry_point=Point(x=pts[0][0] * mm_per_px, y=pts[0][1] * mm_per_px),
                    exit_point=Point(x=pts[-1][0] * mm_per_px, y=pts[-1][1] * mm_per_px),
                    connect_method=connect,
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
    """Boustrophedon scanline fill with cell decomposition.

    Returns [(x_px, y_px, is_jump)]. Rows are grouped into *cells* that each carry a
    single run per row, so a cell is stitched start-to-finish without interruption.
    """
    import numpy as np

    h = region.shape[0]

    # --- 1. rows -> runs -------------------------------------------------------
    rows: list[list[tuple[int, int]]] = []
    ys: list[int] = []
    for y in range(0, h, row_px):
        cols = np.flatnonzero(region[y])
        ys.append(y)
        if cols.size == 0:
            rows.append([])
            continue
        splits = np.flatnonzero(np.diff(cols) > 1)
        runs = np.split(cols, splits + 1)
        rows.append([(int(rn[0]), int(rn[-1])) for rn in runs if rn.size >= 2])

    # --- 2. boustrophedon cell decomposition ----------------------------------
    # A shape with a hole (a ring, the counter of an 'o') puts TWO runs on each row.
    # Serpentining straight through them jumps across the hole on EVERY row - measured
    # at 107-130 jumps and >3m of travel on one 90mm ring logo. Splitting the region
    # into cells that each carry one run per row removes those jumps outright: only the
    # (few) cell-to-cell transitions can become jumps.
    cell_of: dict[tuple[int, int], int] = {}
    next_cell = 0
    prev_ri = -1
    for ri, segs in enumerate(rows):
        if not segs:
            prev_ri = -1  # a gap in the shape always breaks the cell chain
            continue
        prev_segs = rows[prev_ri] if prev_ri >= 0 else []
        for si, s in enumerate(segs):
            over = [pj for pj, ps in enumerate(prev_segs) if not (s[1] < ps[0] or s[0] > ps[1])]
            if len(over) == 1:
                ps = prev_segs[over[0]]
                back = [sj for sj, ss in enumerate(segs) if not (ss[1] < ps[0] or ss[0] > ps[1])]
                if len(back) == 1:  # 1-to-1 continuation -> same cell
                    cell_of[(ri, si)] = cell_of[(prev_ri, over[0])]
                    continue
            cell_of[(ri, si)] = next_cell  # a split, a merge, or a fresh start
            next_cell += 1
        prev_ri = ri

    cells: dict[int, list[tuple[int, int]]] = {}
    for key, c in cell_of.items():
        cells.setdefault(c, []).append(key)

    # --- 3. serpentine each cell, chaining cells nearest-first ----------------
    pts: list[tuple[float, float, bool]] = []
    pending = {c: sorted(v) for c, v in cells.items()}
    cur: tuple[float, float] | None = None
    row_i = 0
    while pending:
        if cur is None:
            cid = min(pending, key=lambda c: (pending[c][0][0], rows[pending[c][0][0]][pending[c][0][1]][0]))
        else:  # enter the cell whose start is closest to where the needle already is
            def _entry(c, _cur=cur):
                ri, si = pending[c][0]
                x0, x1 = rows[ri][si]
                return min(_dist(_cur, (x0, ys[ri])), _dist(_cur, (x1, ys[ri])))
            cid = min(pending, key=_entry)
        members = pending.pop(cid)

        left_to_right = True
        if cur is not None:
            ri, si = members[0]
            x0, x1 = rows[ri][si]
            left_to_right = _dist(cur, (x0, ys[ri])) <= _dist(cur, (x1, ys[ri]))

        for ri, si in members:
            x0, x1 = rows[ri][si]
            y = ys[ri]
            a, b = (x0, x1) if left_to_right else (x1, x0)
            jump = bool(pts) and _dist(pts[-1], (a, y)) > connect_px
            # A run only a few pixels long (the very tip of a circle, a taper) would
            # emit two penetrations a fraction of a millimetre apart, which shreds
            # thread. One penetration covers it.
            if abs(b - a) < max(1.0, max_step_px * 0.08):
                pts.append((float((a + b) / 2.0), float(y), jump if pts else True))
                cur = ((a + b) / 2.0, float(y))
                left_to_right = not left_to_right
                row_i += 1
                continue
            pts.append((float(a), float(y), jump if pts else True))
            # Brick-stagger the interior penetrations: without this every row breaks on
            # the same x and the fill shows a straight split line (spec 4.3).
            phase = STAGGER_PATTERN[row_i % len(STAGGER_PATTERN)]
            span = b - a
            step = max_step_px if span >= 0 else -max_step_px
            sgn = 1.0 if span >= 0 else -1.0
            t = a + phase * step
            # Drop any penetration landing within a third of a step of either row end -
            # those become sub-0.5mm stitches, which shred thread and wear needles.
            while (t - b) * sgn < -abs(step) / 3.0:
                if abs(t - a) > abs(step) / 3.0:
                    pts.append((float(t), float(y), False))
                t += step
            pts.append((float(b), float(y), False))
            cur = (float(b), float(y))
            left_to_right = not left_to_right
            row_i += 1
    return pts


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
