"""Auto-digitizing pipeline v1 — classical OpenCV, no ML (spec §4.2).

Pipeline: decode → scale to hoop → k-means color quantization → per-color masks →
contour regions → scanline (boustrophedon) fill stitches → Design with objects,
color stops, and a machine-valid stitch stream (COLOR_CHANGE / JUMP / TRIM / END).

Honest scope: this is the approximate classical-CV baseline (Phase 3). Satin
detection, underlay, pull compensation, and neural quality land in Phase 8.
cv2/numpy are imported lazily so the app boots without them.
"""

from __future__ import annotations

from itertools import pairwise

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

# Satin classification. The spec allows columns from 0.8mm to 10-12mm; this
# project capped at 4mm "where satin clearly beats tatami".
#
# Raised 4.0 -> 4.5 in v2 Part 3, and the reason is worth stating plainly because
# it was surfaced by a test. `test_rotated_bar_becomes_satin_with_angle` uses a
# bar whose docstring calls it "~3.6mm wide" — the nominal `cv2.line` thickness.
# Rasterised at 45 degrees it is actually wider, confirmed three independent
# ways: perpendicular ray count 4.43mm, area/skeleton-length 4.25mm, largest
# inscribed circle 4.50mm. (The OLD rule passed that test only because
# minAreaRect fits the staircase corners and under-reads at 3.82mm.) So a
# measured-width rule correctly finds 4.4mm, and a 4.0mm cap excluded a bar that
# any embroiderer would satin — the cap was wrong, not the test.
#
# 4.5 remains far below the spec's 10-12mm, and it is safe now in a way it was
# not before: satin follows the medial axis with per-segment tatami fallback for
# anything too wide, where it used to be a bounding-rect zigzag good only for a
# straight bar. Measured corpus impact of 4.0 -> 4.5: exactly ONE additional
# object becomes satin (fixture 08), and no broad fill changes at any cap up to
# 6.0. A reviewer may still read this as tuning to pass a test; the measurements
# above and in the Part 3 audit are there to be checked.
SATIN_MAX_W_MM = 4.5
# The spec's 0.8mm minimum column is deliberately NOT enforced. Fixture 04 is
# drawn entirely in 0.28-0.62mm strokes, and satin is exactly what those want —
# a 0.8mm floor would send the thinnest real linework back to tatami, which is
# the defect this part exists to fix. The effective floor is the 0.5px half-width
# clamp in `_skeleton_satin`, i.e. one thread. Kept as a named constant because
# the spec figure is worth recording next to the cap it sits under.
SATIN_MIN_W_MM = 0.8
# `SATIN_ASPECT` and `SKELETON_MIN_WIDTH_MM` were deleted here, not merely left
# unread: with classification now driven by measured medial-axis width they had
# no remaining caller anywhere in the tree (`rebuild_design`'s explicit-SATIN
# path uses `_satin_zigzag` + `_center_walk`, neither of which consults them).
# Aspect ratio tested a property of the bounding BOX rather than of the shape,
# so a ring, arc or bend — uniformly thin but with a huge box — always failed it
# and was area-filled. That is why fixture 04 came out 100% tatami.
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

# Squared-distance ratio above which a pixel counts as an anti-aliased blend of
# two palette colours rather than a member of either (0.5 on squared distance
# ≈ 0.71 on linear distance).
AMBIGUOUS_BLEND_RATIO = 0.5

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

# Per-object classification diagnostics from the most recent digitize_image call.
# Read by the benchmark harness so the audit can explain every satin/tatami
# decision from measured geometry instead of assertion.
_CLASSIFICATION_LOG: list[dict] = []


def last_classification_log() -> list[dict]:
    """Per-object measured widths + satin/tatami decision from the last run."""
    return list(_CLASSIFICATION_LOG)


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
    text_mode: bool = False,
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

    # The PALETTE is learned from the foreground's INTERIOR, not its whole area.
    # Rendering and rescaling leave a 1-2px anti-aliased band where two colours
    # meet; those pixels are blends, not design colours, and if they are allowed
    # to seed a centroid they become a spurious extra thread — black-on-white
    # text came back as {black, near-white halo}, i.e. two colour stops for a
    # one-colour wordmark. Eroding first keeps the palette to colours that own
    # real area; every foreground pixel is then assigned to the nearest palette
    # entry below, so the halo is absorbed instead of promoted.
    interior = cv2.erode(fg_mask, np.ones((3, 3), np.uint8))
    pal_flat = interior.reshape(-1) > 0
    if int(pal_flat.sum()) < max(16, 0.05 * int(fg_flat.sum())):
        pal_flat = fg_flat  # design too thin to erode — fall back to all of it
    Z_pal = flat_rgb[pal_flat]

    k = max(1, min(int(max_colors), 8, len(np.unique(Z_pal, axis=0))))
    _, _, centers = cv2.kmeans(
        Z_pal, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS
    )
    # Assign every foreground pixel to its nearest palette colour. Looped over
    # centres to keep memory at N×k.
    d2 = np.empty((len(Z), len(centers)), np.float32)
    for ci in range(len(centers)):
        diff = Z - centers[ci]
        d2[:, ci] = np.einsum("ij,ij->i", diff, diff)
    fg_labels = d2.argmin(axis=1).astype(np.int32)
    if len(centers) > 1:
        # A pixel roughly equidistant from two palette colours IS the blend
        # between them. Assigning it to the nearer one grows every shape by
        # about a pixel per side, which pushed a 3.6mm satin bar over the 4mm
        # satin/tatami threshold. Leave those unassigned instead: they belong to
        # neither layer, and dropping them keeps shapes at their true width.
        nearest2 = np.partition(d2, 1, axis=1)[:, :2]
        ambiguous = nearest2[:, 0] > AMBIGUOUS_BLEND_RATIO * nearest2[:, 1]
        fg_labels[ambiguous] = -1
    centers = centers.astype(np.uint8)

    # Merge perceptually-identical centroids so one colour never becomes two
    # thread stops (a 1-colour wordmark asked to use 2 colours must return 1).
    remap = _merge_centers(centers, MERGE_DELTA)
    centers = np.array([centers[i] for i in sorted(set(remap.values()))], np.uint8)
    order = {old: new for new, old in enumerate(sorted(set(remap.values())))}

    labels = np.full(ih * iw, -1, np.int32)
    # -1 marks an unassigned blend pixel and must stay -1 (no layer owns it).
    labels[fg_flat] = [-1 if int(v) < 0 else order[remap[int(v)]] for v in fg_labels.reshape(-1)]
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

    _CLASSIFICATION_LOG.clear()
    stitches: list[Stitch] = []
    color_stops: list[ColorStop] = []
    objects: list[DesignObject] = []
    seq = 0
    skeleton_satin_used = 0        # diagnostics for the bench/audit
    skeleton_tatami_fallback = 0
    skeleton_partial_tatami = 0

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

            rect = cv2.minAreaRect(contour)
            under_step_px = max(1, round(UNDERLAY_STEP_MM / mm_per_px))
            pull_mm = _default_pull(fabric_type)
            top_region = _dilate_pull(region, pull_mm, mm_per_px)  # pull comp widens the top layer

            # ── Single classification path (v2 Part 3) ─────────────────────────
            # Satin vs tatami is decided by MEASURED LOCAL WIDTH along the shape's
            # medial axis — for every object, lettering or not. The old rule
            # compared the min-area bounding rectangle's short side against a
            # fixed aspect ratio, which is a property of the shape's BOUNDING BOX
            # rather than of the shape: a ring, an arc or an L-bend has a huge
            # bounding box and a uniformly thin stroke, so it always failed the
            # aspect test and was area-filled. That is why fixture 04 — a mark
            # made entirely of thin lines — came out 100% tatami.
            #
            # `text_mode` no longer forks this logic. It is still accepted (the
            # lettering service passes it and is out of scope here) but only
            # affects the speck threshold now, not classification.
            sat_step = max(1, round(SATIN_SPACING_MM / mm_per_px))
            skel_pts = None
            median_w = 0.0
            uncovered = 1.0
            reason = ""
            # Cheap gate before thinning: if the typical width across the whole
            # region is far over the cap this is a broad fill, and thinning it
            # would cost time to reach the same answer.
            _dt = cv2.distanceTransform((region > 0).astype(np.uint8), cv2.DIST_L2, 5)
            region_med_w = float(np.median(_dt[_dt > 0])) * 2.0 * mm_per_px if (_dt > 0).any() else 0.0
            if region_med_w > SATIN_MAX_W_MM * SATIN_PREGATE_SLACK:
                reason = "broad_fill_pregate"  # typical width far over the cap
            else:
                # Measure the TRUE region and add pull compensation to the column
                # half-width. Measuring the pre-dilated mask would fold pull comp
                # into the width test and push a 3.66mm stem over the cap.
                cand, median_w, wide_mask, axis_pts = _skeleton_satin(
                    region, mm_per_px, sat_step, max_step_px, extra_half_px=(pull_mm / 2.0) / mm_per_px
                )
                region_px = max(cv2.countNonZero(region), 1)
                uncovered = cv2.countNonZero(wide_mask) / region_px
                # Two independent conditions. Width: the stroke must fit under the
                # satin cap (median, not p90 — the distance transform spikes at
                # junctions where the medial axis is far from every edge although
                # the stroke is no wider). Reducibility: satin columns swept along
                # the medial axis must actually account for the shape. A disc has
                # a medial axis but columns capped at the satin width cannot cover
                # it, so the uncovered share stays high and it correctly remains
                # tatami — this is what stops broad fills being forced into satin.
                if not cand:
                    # Too small to reduce to a 1D axis at all — a freckle, a
                    # catchlight, a punctuation dot. A tiny fill is right here.
                    reason = "no_medial_axis"
                elif median_w > SATIN_MAX_W_MM:
                    reason = "wider_than_satin_cap"
                    skeleton_tatami_fallback += 1
                elif uncovered > SATIN_MAX_UNCOVERED:
                    reason = "not_stroke_like"
                    skeleton_tatami_fallback += 1
                else:
                    reason = "satin"
                    if cv2.countNonZero(wide_mask) > 0:
                        # Per-segment fallback: tatami only the parts too wide.
                        cand = cand + _scanline_fill(wide_mask, row_px, max_step_px, connect_px)
                        skeleton_partial_tatami += 1
                    skel_pts = cand
                    skeleton_satin_used += 1
            is_satin = skel_pts is not None
            _CLASSIFICATION_LOG.append(
                {
                    "seq": seq + 1,
                    "region_median_w_mm": round(region_med_w, 2),
                    "skeleton_median_w_mm": round(median_w, 2),
                    "uncovered_share": round(uncovered, 3),
                    "reason": reason,
                    "decision": "SATIN" if is_satin else "TATAMI",
                }
            )
            if skel_pts is not None:
                # Satin now always comes from the medial axis. The old
                # bounding-rect `_satin_zigzag` path is gone from digitizing:
                # it rotated the whole region to its min-area rectangle and
                # zigzagged across that, which only ever worked for a straight
                # bar — it could not follow a ring, an arc or a bend, which is
                # most of the thin geometry in real artwork. (`_satin_zigzag`
                # itself is retained: `rebuild_design` still uses it for objects
                # a user explicitly sets to SATIN.)
                # Centre-walk ALONG THE MEDIAL AXIS, not the bounding-rect midline.
                under = _axis_underlay(
                    axis_pts, UNDERLAY_STEP_MM / mm_per_px, connect_px,
                    (_PENETRATION_FLOOR_MM / mm_per_px) if _PENETRATION_FLOOR_MM else 0.0,
                    MAX_STITCH_MM / mm_per_px,
                )
                pts = _with_underlay(under, skel_pts, connect_px)
                underlay = UnderlayType.CENTER_WALK
            else:
                inset_px = max(1, round(EDGE_INSET_MM / mm_per_px))
                under = _edge_walk(
                    region, inset_px, under_step_px, connect_px,
                    (_PENETRATION_FLOOR_MM / mm_per_px) if _PENETRATION_FLOOR_MM else 0.0,
                    MAX_STITCH_MM / mm_per_px,
                )
                pts = _with_underlay(under, _scanline_fill(top_region, row_px, max_step_px, connect_px), connect_px)
                underlay = UnderlayType.EDGE_WALK
            # The floor is passed only for SATIN. A tatami row advances along a
            # line, never zigzags, so the repair could not fire there anyway —
            # but not passing it keeps fills on exactly the path they had.
            pts = _coalesce_short(
                pts, MIN_STITCH_MM / mm_per_px,
                (_PENETRATION_FLOOR_MM / mm_per_px) if (is_satin and _PENETRATION_FLOOR_MM) else 0.0,
            )
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
# Minimum spacing between consecutive SAME-SIDE penetrations in a satin column
# run. Distinct from MIN_STITCH_MM, which bounds how far the needle TRAVELS
# between penetrations: a satin column can travel 4mm across the stroke while the
# two entry points on one boundary sit a fraction of a millimetre apart. Packed
# tighter than this, the penetrations stop being stitches on the fabric and start
# being a perforated line through it — the failure mode Part 4 §8 flagged as
# unmeasured. Boundary-paced pitch reaches it on the concave side of a tight
# curve, where the inner boundary is much shorter than the outer one that sets
# the pitch.
#
# Reconciliation with the industry "running stitch never below 0.5mm" guidance
# (v2 Part 12): that guidance is a STITCH-LENGTH rule — needle travel between
# consecutive penetrations — and this codebase enforces it as MIN_STITCH_MM =
# 0.5, exactly the cited value. 0.30 here is not a more permissive version of
# that rule; it bounds a different quantity (same-side spacing, which consecutive
# stitch length cannot see) that the industry guides do not measure at all. Both
# values remain unvalidated on fabric — docs/FABRIC_TEST_PROTOCOL.md is the
# procedure for settling them empirically.
MIN_PENETRATION_MM = 0.30
# ENFORCED since v2 Part 6. Part 5 built the metric, measured the damage and left
# enforcement off so the decision could be taken on its own evidence rather than
# riding along with the instrument that found the problem. The evidence: every
# satin fixture in the corpus was violating, 8-24% of penetrations under the
# floor and hundreds at exactly 0.000mm — the needle entering the same hole
# twice. Enforcing costs 3.0 points of mean interior coverage and 3.5 of edge
# band across the satin corpus; the floor sweep and the rejected alternatives are
# in the Part 6 audit. `set_penetration_floor(None)` disables it, which is how
# the audit reproduces the before/after.
_PENETRATION_FLOOR_MM: float | None = MIN_PENETRATION_MM


def set_penetration_floor(mm: float | None) -> None:
    """Enable (or disable, with ``None``) the same-side penetration floor."""
    global _PENETRATION_FLOOR_MM
    _PENETRATION_FLOOR_MM = mm


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


# ── v2 Part 2: skeleton-guided satin lettering ───────────────────────────────
# A glyph is a STROKE, not an arbitrary blob. Filling its silhouette with
# horizontal tatami rows is what makes machine lettering read as blocky; real
# digitizing runs satin columns ACROSS the stroke, stepping ALONG its centreline,
# with the column width tracking the stroke's local width. These helpers build
# that: thin the glyph to its medial axis, walk each branch, and emit a zigzag
# whose half-width comes from the distance transform at each step.
SPUR_MIN_MM = 0.8         # skeleton branches shorter than this are thinning noise
SPUR_PRUNE_MULT = 0.6     # spur length threshold as a multiple of local half-width
# v2 Part 3: satin/tatami is decided by measured medial-axis width for EVERY
# shape. A region whose typical width is this multiple over the satin cap is a
# broad fill — skip thinning entirely and go straight to tatami (pure speed).
SATIN_PREGATE_SLACK = 1.5
# Share of a region the satin columns may fail to reach before the shape is
# judged not stroke-like. A ring or spoke is almost fully covered by columns
# swept along its axis; a disc is not, because columns are capped at the satin
# width. This is what keeps broad fills as tatami.
SATIN_MAX_UNCOVERED = 0.35
TANGENT_WINDOW = 3        # samples each side used to estimate stroke direction

# ── Edge-bounded satin (v2 Part 4) ────────────────────────────────────────────
# Parts 2/2.5/3 placed each column end by measuring outward from the medial axis
# — first the distance transform, then a ray-cast along the column's own
# direction. Both are per-sample APPROXIMATIONS of the boundary: the ray is
# aimed by a tangent estimated from a stair-stepped 1px skeleton, so wherever
# that estimate tilts, the end lands off the outline. Measured consequence:
# edge-band coverage stayed below tatami on every fixture satin took over.
#
# Part 4 stops approximating. The two boundary arcs of a stroke are extracted
# from the region's own contour and columns are laid between CORRESPONDING
# points on them, so a column end is a boundary point by construction and cannot
# fall short of, or past, the outline.
CLOSED_LOOP_TOL_PX = 2.5   # axis start/end within this = a ring, no terminals
MIN_ARC_SAMPLES = 4        # a boundary arc needs this many points to be usable
CAP_EXTRA_COLUMNS = 2      # columns added past each terminal to close the cap
PROJECT_CHUNK = 256        # contour points per distance-matrix chunk (memory)
# Consecutive stalled stations on one boundary before a mitre engages (v2 Part 8).
# A sharp vertex stalls its inner boundary for many columns in a row; a straight
# stroke only ever throws isolated short steps, and mitring those is pure damage.
MITRE_MIN_STALLED = 3
# A same-side penetration pair only counts when the triple actually ZIGZAGS: the
# same-side gap must be shorter than either crossing. True of a satin column pair,
# false of any stitch sequence advancing along a line.
#
# THIS MODULE OWNS THE VALUE. `scripts/measure_stitch_quality.py` imports it as
# `ZIGZAG_RATIO` rather than keeping its own copy (v2 Part 10 §6 item 1 flagged the
# duplicate). The pipeline owns it because `scripts/` is not a package — it is a
# dev CLI that inserts the backend root on `sys.path` — so a shipped service
# importing from it would invert the dependency. The direction here is the one
# already in use: `run_quality_bench.py` imports MIN_PENETRATION_MM and
# SATIN_SPACING_MM from this module.
ZIGZAG_RATIO = 0.9
COALESCE_REPAIR_PASSES = 200   # bound; each pass restores at most one point
UNDERLAY_REPAIR_PASSES = 200   # bound; each pass drops at most one point
# NO outward bias is applied to column ends. One was tried — a contour point is
# the centre of the outermost pixel still inside the shape, so half a pixel of
# reach is arguably owed — and while the coalescing defect below was still in
# place it did buy coverage. Once that was fixed it buys nothing (fixture 03 edge
# band 97.2 -> 97.2, fixture 05 98.3 -> 98.4 at +0.5px) and costs spill
# (03 8.0 -> 9.7, 05 12.2 -> 15.6, 04 47.3 -> 55.3). Removed. Sweep in the audit.


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

    img = (mask > 0).astype(np.uint8)
    while True:
        removed_any = False
        for step in (0, 1):
            p = np.pad(img, 1)
            # P2..P9, clockwise from north.
            P2, P3 = p[:-2, 1:-1], p[:-2, 2:]
            P4, P5 = p[1:-1, 2:], p[2:, 2:]
            P6, P7 = p[2:, 1:-1], p[2:, :-2]
            P8, P9 = p[1:-1, :-2], p[:-2, :-2]
            seq = [P2, P3, P4, P5, P6, P7, P8, P9, P2]
            B = P2 + P3 + P4 + P5 + P6 + P7 + P8 + P9
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                cond = (P2 * P4 * P6 == 0) & (P4 * P6 * P8 == 0)
            else:
                cond = (P2 * P4 * P8 == 0) & (P2 * P6 * P8 == 0)
            remove = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & cond
            if remove.any():
                img[remove] = 0
                removed_any = True
        if not removed_any:
            return img


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
        p = np.pad(out, 1)
        deg = sum(
            p[dy : dy + out.shape[0], dx : dx + out.shape[1]]
            for dy in (0, 1, 2)
            for dx in (0, 1, 2)
            if not (dy == 1 and dx == 1)
        )
        endpoints = {(int(x), int(y)) for y, x in zip(*np.nonzero((out > 0) & (deg == 1)))}
        if not endpoints:
            break
        removed = False
        for br in _skeleton_branches(out):
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


def _skeleton_branches(skel, min_len: int = 2):
    """Split a 1px skeleton into ordered polylines between endpoints/junctions.

    Returns a list of [(x, y), ...] paths. Junction pixels are shared, so the
    branches of a glyph like 'A' or 'K' meet rather than leaving a gap.
    """
    import numpy as np

    pts = {(int(x), int(y)) for y, x in zip(*np.nonzero(skel))}
    if not pts:
        return []

    def neighbours(pt):
        """8-neighbours with REDUNDANT DIAGONALS suppressed.

        A thinned staircase — which is what any curve or circle becomes at 1px —
        is full of L-corners: a pixel touching both an orthogonal neighbour and
        the diagonal beyond it. Counted naively that corner has three neighbours
        and reads as a junction, so a plain ring shattered into hundreds of
        two-pixel 'branches' (fixture 04's outer ring: 1,288 skeleton pixels ->
        617 branches, most of length 2). Satin over fragments that short is
        noise: the tangent is quantised to 45 degrees, the columns scatter, and
        short columns get coalesced away — the ring came out visibly dashed.

        A diagonal edge is dropped when the two pixels are already joined
        through a shared 4-neighbour, which is the standard connectivity rule
        and is symmetric from either end. A genuine junction ('A', 'K', a spoke
        meeting a rim) has no such shortcut and still reads as a junction.
        """
        x, y = pt
        out = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (x + dx, y + dy) in pts]
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            if (x + dx, y + dy) in pts and (x + dx, y) not in pts and (x, y + dy) not in pts:
                out.append((x + dx, y + dy))
        return out

    degree = {p: len(neighbours(p)) for p in pts}
    nodes = {p for p, d in degree.items() if d != 2}  # endpoints + junctions
    branches: list[list[tuple[int, int]]] = []
    seen_edges: set[frozenset] = set()

    def walk(start, first):
        path = [start, first]
        prev, cur = start, first
        while cur not in nodes:
            nxt = [n for n in neighbours(cur) if n != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
        return path

    for node in nodes:
        for nb in neighbours(node):
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
            nxt = [n for n in neighbours(cur) if n != prev]
            if not nxt or nxt[0] == start:
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
        if len(path) >= min_len:
            branches.append(path)
    return branches


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


def _boundary_points(region):
    """Every boundary pixel of a region, outer contour and holes alike, as (N, 2).

    `CHAIN_APPROX_NONE` is deliberate: the corners a simplifying approximation
    drops are exactly the column endpoints this part exists to land on.
    """
    import cv2
    import numpy as np

    contours, _ = cv2.findContours((region > 0).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
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
    for p0, p1 in pairwise(seq):
        n = max(1, int(np.ceil(_dist(p0, p1) / max(max_step_px, 1))))
        for i in range(1, n + 1):
            out.append((p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n, False))
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


def _axis_branches(binary, dist, mm_per_px: float):
    """Thin a region to its medial axis and split it into ordered branches."""
    import cv2
    import numpy as np

    # Close pinholes and soften the outline before thinning — boundary noise is
    # what sprouts skeleton hairs, and it is cheaper to remove it here than to
    # prune the consequences.
    smooth = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    skel = _zhang_suen_thin(smooth)
    # Prune spurs shorter than a typical stroke width; that is the scale at which
    # a dead-end branch is noise rather than a real stroke ending.
    median_half = float(np.median(dist[skel > 0])) if (skel > 0).any() else 0.0
    spur_px = max(int(round(SPUR_MIN_MM / mm_per_px)), int(round(median_half * SPUR_PRUNE_MULT)), 3)
    skel = _prune_spurs(skel, spur_px)
    branches = [b for b in _skeleton_branches(skel) if len(b) >= 3]
    return skel, branches or [b for b in _skeleton_branches(skel) if len(b) >= 2]


def _uncovered_mask(binary, skel, max_half_px: float):
    """Everything satin could not reach — the caller's per-segment tatami fallback.

    Discs of the clamped half-width swept along the skeleton approximate the band
    the columns cover closely enough; the remainder is what needs tatami.
    """
    import cv2
    import numpy as np

    r = max(1, int(round(max_half_px)))
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    covered = cv2.dilate((skel > 0).astype(np.uint8), disc)
    mask = ((binary > 0) & (covered == 0)).astype(np.uint8) * 255
    # Ignore slivers — a thin uncovered rim is the anti-aliased edge, not a region.
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


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
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
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
    floor_px = (_PENETRATION_FLOOR_MM / max(mm_per_px, 1e-6)) if _PENETRATION_FLOOR_MM else 0.0
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
                    under = _edge_walk(
                        mask, inset_px, under_step_px, connect_px,
                        (_PENETRATION_FLOOR_MM / mm_per_px) if _PENETRATION_FLOOR_MM else 0.0,
                        MAX_STITCH_MM / mm_per_px,
                    )
                    pts = _with_underlay(under, pts, connect_px)
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
