"""Auto-digitizing pipeline entry points: digitize_image, rebuild_design.

Pipeline: decode -> scale to hoop -> k-means color quantization -> per-color
masks -> contour regions -> scanline (boustrophedon) fill stitches -> Design
with objects, color stops, and a machine-valid stitch stream (COLOR_CHANGE /
JUMP / TRIM / END).

Honest scope: the stitch stage is classical CV; the segmentation stage in
front of it is a neural matte. cv2/numpy are imported lazily inside the
functions so the app boots without them.
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
from app.services import direction_field, segmentation
from app.services.digitizer import constants, staging
from app.services.digitizer.constants import (
    _CLASSIFICATION_LOG,
    _DROP_LOG,
    _MAX_WORK_PX,
    _MIN_WORK_PX,
    _UPSCALE_MIN_SRC_PX,
    CONNECT_MM,
    CONTOUR_FILL_MAX_BAND_RATIO,
    CONTOUR_FILL_MIN_MM2,
    CONTOUR_ROW_MAX_STEP_MM,
    DARK_CLOTH_LUM,
    DEFAULT_MAX_COLORS,
    DETAIL_DEFER_MAX_MM2,
    DETAIL_EMBED_SHARE,
    DIGITIZE_RNG_SEED,
    DROPPED_SHARE_WARN,
    FILL_BORDER_MIN_MM2,
    FILL_UNDERLAY_ANGLE_OFFSET_DEG,
    FILL_UNDERLAY_MIN_MM2,
    FILL_UNDERLAY_PITCH_MULT,
    FINE_DETAIL_SRC_PX_PER_MM,
    HOLE_KNOCKOUT_MIN_MM2,
    MAX_STITCH_MM,
    MIN_FEATURE_W_MM,
    MIN_REGION_MM2,
    MIN_STITCH_MM,
    OUTLINE_RUN_MM,
    PLAN_MAX_COLORS,
    SATIN_MAX_W_MM,
    SATIN_PREGATE_SLACK,
    SKETCH_MAX_RETRIES,
    SKETCH_MIN_COVERAGE,
    SUBSTRATE_DELTA,
    SUBSTRATE_ENCLOSED_MAX_MM2,
    SUBSTRATE_ENCLOSED_MAX_SHARE,
    TEXTURE_MS_COLOR,
    TEXTURE_MS_SPATIAL,
    TEXTURE_RETRY_MIN_CHUNK_MM2,
    TEXTURE_RETRY_MIN_GAIN,
    TEXTURE_RETRY_UNCOVERED,
    TEXTURE_SMOOTH_MIN,
    TRAVEL_STEP_MM,
    TRIM_MIN_GAP_MM,
)
from app.services.digitizer.fills import (
    _contour_fill,
    _fill_angle,
    _fill_angle_provenance,
    _fill_by_component,
)
from app.services.digitizer.generation import (
    spine_satin,
)
from app.services.digitizer.geometry import (
    _border_color,
    _decode_image_bgr,
    _decode_svg,
    _dilate_pull,
    _drop_floor_reversals,
    _fabric_profile,
    _hole_covered_later,
    _open_preserving_detail,
    _parse_hoop,
    _resample_open,
    _smooth_contour,
    _uncovered_chunk_mm2,
)
from app.services.digitizer.planning import (
    _band_ratio,
    _dark_linework,
    _interior_texture,
    _plan_palette,
    _sketch_from_labels,
    _verify_sketch,
)
from app.services.digitizer.provenance import (
    object_params_hash,
)
from app.services.digitizer.routing import (
    _coalesce_short,
    _lock_stream,
    _merge_adjacent_same_hex,
    _nearest_neighbour_order,
    _route_travel,
    coalesce_params,
    travel_route_pad_px,
)
from app.services.digitizer.satin import (
    _fill_border,
    _satin_axis_deg,
    fill_border_width_px,
)
from app.services.digitizer.underlay import (
    _edge_walk,
    _parallel_underlay,
    _satin_width_underlay,
    _with_underlay,
)

# Set by every digitize_image call: the PIXEL share of owned foreground that
# no emitted object covers. The element-level lost_share below deliberately
# ignores partial coverage (edge shaving is not loss), which is exactly why it
# cannot gate the Part 65 photographic rescue: a thread-textured photo webs
# the whole subject into ONE element that a single surviving fragment
# "covers" (the angelfish measured 0.9% by elements while most of its body
# was unsewn). The rescue reads this pixel share back after its recursive
# retry to decide whether the smoothed pass actually recovered artwork.
_LAST_UNCOVERED_PX: float = 0.0


def digitize_image(
    data: bytes,
    fabric_type: str = "cotton",
    hoop_size: str = "100x100",
    max_colors: int = DEFAULT_MAX_COLORS,
    min_region_mm2: float = MIN_REGION_MM2,
    text_mode: bool = False,
    _texture_smooth: bool | None = None,
) -> Design:
    """Convert an image into a stitch Design (classical CV baseline).

    ``_texture_smooth`` is internal: None means the Part 27 variance gate
    decides whether the photographic mean-shift runs; True forces it — used
    only by the Part 65 outcome-gated retry below, never by callers.
    """
    import math

    import cv2
    import numpy as np

    # DETERMINISM (CP1, 2026-08-10). The same upload MUST produce the same
    # design, and before this line it did not.
    #
    # `_palette_centers` calls `cv2.kmeans(..., KMEANS_PP_CENTERS)` with no
    # seed, so k-means++ draws from OpenCV's THREAD-LOCAL RNG. `routers/
    # digitize.py` declares its handler with a plain `def`, so FastAPI runs it
    # on the anyio threadpool, whose workers are reused — the RNG state carried
    # from one customer's request straight into the next. Four byte-identical
    # uploads on one worker returned 6/6/6/5 colour stops and
    # 8,694/8,755/8,673/8,486 stitches: four different products from one file.
    #
    # Why it was never caught: every bench script and test calls
    # `cv2.setRNGSeed(RNG_SEED)` BEFORE `digitize_image`, so the harness was
    # supplying the determinism the library owed. Production had no harness.
    # Seeding here moves that guarantee inside the library, where it belongs,
    # and makes the result independent of whatever ran on this thread before.
    #
    # The constant is the harness's own RNG_SEED. That is deliberate: callers
    # that already seed with it see byte-identical output, so this fix carries
    # no re-pin and no baseline churn — it only removes the variation nobody
    # wanted. A per-image seed was considered and rejected; the requirement is
    # that one image always gives one answer, and a fixed seed states that
    # plainly. `_split_bimodal_clusters` already seeds this way, which is why
    # the SUB-split was reproducible while the main palette was not.
    cv2.setRNGSeed(DIGITIZE_RNG_SEED)

    # Alpha-aware decode (CTO A15/N2) — rationale on _decode_image_bgr.
    img = _decode_image_bgr(data)
    svg_mask = None
    if img is None:
        decoded = _decode_svg(data)  # vector path (v2 Part 25)
        if decoded is None:
            raise ValueError("Could not decode image (expected SVG/PNG/JPEG/BMP/WebP)")
        img, svg_mask = decoded

    hoop_w, hoop_h = _parse_hoop(hoop_size)
    ih, iw = img.shape[:2]
    src_ih, src_iw = ih, iw                          # pre-rescale, for warnings
    # Texture is judged at SOURCE resolution: the granularity upscale's cubic
    # interpolation smooths it (measured on the peacock photo: 7.43 at source,
    # 5.86 after 2x — under the gate, so the smoothing silently never fired).
    is_textured = svg_mask is None and (
        _texture_smooth if _texture_smooth is not None
        else _interior_texture(img) >= TEXTURE_SMOOTH_MIN
    )
    mm_per_px = min(hoop_w / iw, hoop_h / ih) * 0.9  # 90% of hoop
    design_w_mm = iw * mm_per_px                     # physical width at this hoop
    # Work at a bounded resolution for speed; keep mm scale consistent.
    # Granularity floor (v2 Part 17): small sources are upscaled so contours,
    # borders and details are traced at fine geometry — a 640px logo in a 130mm
    # hoop otherwise carries a 0.18mm/px staircase into every downstream stage.
    # Affordable now that the thinner crops to its bounding box (62s -> 18s on
    # the heaviest fixture at 2x; typical fixtures are seconds).
    up_f = 1.0
    if _UPSCALE_MIN_SRC_PX <= max(iw, ih) < _MIN_WORK_PX:
        # Capped at 2x: beyond that, cubic AA bands grow wider than the palette
        # erosion can suppress even when scaled (a 160px lettering render at
        # 7.5x produced no stitchable shapes at all). 2x doubles geometric
        # granularity for the common 640px source; truly tiny sources should be
        # rendered bigger upstream, not inflated here.
        up_f = min(2.0, _MIN_WORK_PX / max(iw, ih))
        img = cv2.resize(img, (round(iw * up_f), round(ih * up_f)), interpolation=cv2.INTER_CUBIC)
        mm_per_px /= up_f
        ih, iw = img.shape[:2]
    if max(iw, ih) > _MAX_WORK_PX:
        f = _MAX_WORK_PX / max(iw, ih)
        img = cv2.resize(img, (int(iw * f), int(ih * f)), interpolation=cv2.INTER_AREA)
        mm_per_px /= f
        ih, iw = img.shape[:2]

    # Photographic input: posterize shading before quantization (v2 Part 27).
    # A photo — including a photographed sew-out, thread sheen and all — carries
    # per-region shading that k-means shatters into hundreds of speckle islands;
    # the peacock test photo produced a tail of navy shreds. Mean-shift merges
    # the shading while keeping edges. Gated on interior texture MEASURED AT
    # SOURCE resolution (see `is_textured` above), so flat artwork — the whole
    # bench corpus, 0.00-4.10 vs the 6.0 gate — takes the untouched path and
    # stays byte-identical. Applied here, at work resolution, where the
    # sp/sr parameters were calibrated.
    if is_textured:
        img = cv2.pyrMeanShiftFiltering(img, TEXTURE_MS_SPATIAL, TEXTURE_MS_COLOR)

    # ── Foreground/background separation (v2 Part 1) ──────────────────────────
    # Background is decided by WHERE a pixel is, not by what colour it is. The
    # v1 rule ("cluster colour within 40 of the corner average") deleted every
    # pixel of that colour anywhere in the frame, which is what removed fixture
    # 02's white type and fixture 08's cream muzzle while keeping fixture 09's
    # background. See services/segmentation.py.
    if svg_mask is not None:
        # Vector input carries its own EXACT foreground — no neural matte, no
        # substrate heuristics, none of the guesswork Parts 1/21/22 patched.
        fg_mask, seg_method = svg_mask, "svg-vector"
    else:
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
    # The palette-seeding erosion scales with the upscale factor (v2 Part 17):
    # cubic upscaling widens anti-alias bands to ~up_f pixels, and a 1px erosion
    # let them seed phantom clusters — a 2x-upscaled two-colour square grew four
    # 0.15mm 'satin' slivers in the blend colour, which no needle could sew.
    # ── Sketch-then-verify planning loop (v2 Part 33) ────────────────────────
    # A human digitizer sketches the outline first, checks it against the
    # artwork, and only fills once the structure agrees. `_plan` produces one
    # colour plan (the body below is the former inline quantization, moved, not
    # changed); the sketch it implies is verified against the source's own
    # edges, and a plan that failed to draw the artwork's lines is retried with
    # a larger colour budget. Flat corpus fixtures verify on the first attempt
    # by calibration, so their path — including RNG consumption — is identical.
    def _plan(k):
        return _plan_palette(
            k,
            img=img,
            fg_mask=fg_mask,
            fg_flat=fg_flat,
            flat_rgb=flat_rgb,
            Z=Z,
            ih=ih,
            iw=iw,
            up_f=up_f,
            is_textured=is_textured,
            mm_per_px=mm_per_px,
        )

    k_plan = min(int(max_colors), PLAN_MAX_COLORS)  # retries may exceed the cap
    labels, centers, n_shade_splits = _plan(k_plan)
    sketch = _sketch_from_labels(labels, fg_mask)
    sketch_cov, _sketch_prec = _verify_sketch(sketch, img, fg_mask)
    sketch_retries = 0
    while sketch_cov < SKETCH_MIN_COVERAGE and sketch_retries < SKETCH_MAX_RETRIES:
        sketch_retries += 1
        k_plan += 2
        labels2, centers2, splits2 = _plan(k_plan)
        cov2, _prec2 = _verify_sketch(_sketch_from_labels(labels2, fg_mask), img, fg_mask)
        if cov2 > sketch_cov:  # keep the better plan, whichever it is
            labels, centers, n_shade_splits = labels2, centers2, splits2
            sketch_cov = cov2

    substrate = _border_color(img)

    # Darkest-first stitching order (spec §4.2). Clusters emptied by halo
    # suppression are skipped so they never open a colour stop.
    clusters = [
        (int(c.astype(int).sum()), idx, c)
        for idx, c in enumerate(centers)
        if bool((labels == idx).any())
    ]
    clusters.sort(key=lambda t: t[0])

    # Fabric profile drives density/underlay/inset (v2 Part 13); cotton == the
    # old globals, so the all-cotton bench corpus is unchanged by construction.
    prof = _fabric_profile(fabric_type)
    row_px = max(1, round(prof["row_mm"] / mm_per_px))
    max_step_px = max(2, round(MAX_STITCH_MM / mm_per_px))
    # Fills subdivide on their own, tighter grid (CTO A6): tatami rows cap at
    # MAX_FILL_STITCH_MM, not the general run cap — see the constant's note.
    fill_step_px = max(2, round(constants.MAX_FILL_STITCH_MM / mm_per_px))
    min_area_px = max(0.0, float(min_region_mm2)) / (mm_per_px * mm_per_px)
    connect_px = CONNECT_MM / mm_per_px

    _CLASSIFICATION_LOG.clear()
    _DROP_LOG.clear()
    stitches: list[Stitch] = []
    color_stops: list[ColorStop] = []
    objects: list[DesignObject] = []
    seq = 0
    # CTO A6: successive ISOTROPIC fills alternate their fallback angle by 90
    # degrees so push/pull spreads across the design instead of accumulating
    # one way. Regions with a real long axis are exempt — the axis is a
    # property of the shape and wins (see _fill_angle_provenance).
    iso_fills = 0
    substrate_px = 0            # garment-coloured pixels deliberately left unstitched
    substrate_owned = np.zeros(fg_mask.shape, np.uint8)
    dropped_speck_count = 0     # regions under min_region_mm2 at THIS hoop size
    emitted_mask = np.zeros((ih, iw), np.uint8)  # px that became stitched objects
    skeleton_satin_used = 0        # diagnostics for the bench/audit
    skeleton_tatami_fallback = 0
    skeleton_partial_tatami = 0

    emitted_stop = 0  # actual color-stop count — only clusters that yield objects get one
    # Stitch rank per cluster: absorption of a fill hole is only safe when the
    # detail that sits in the hole is stitched AFTER this fill (v2 Part 14).
    stitch_rank = {cluster_idx: rank for rank, (_, cluster_idx, _c) in enumerate(clusters)}
    # ── Detail deferral (v2 Part 16) ─────────────────────────────────────────
    # A small dark component embedded in a LATER-stitched fill (fixture 08's
    # forehead dots and eye pupils, 07's HARBOR CLUB letters) used to stitch
    # first, forcing the fill to keep a knockout it cannot cross — the painted
    # miss-map showed red wedges around every such hole. Professional sequencing
    # stitches the background first and the detail ON TOP: those components are
    # deferred to a second pass after the main clusters, at the cost of extra
    # colour changes, and the fill absorbs their holes.
    deferred_mask = np.zeros((ih, iw), bool)
    deferred_items = []
    for rank, (_, ci_, center_) in enumerate(clusters[:-1]):
        later = np.isin(labels, [c2 for _, c2, _c in clusters[rank + 1:]])
        m8 = (labels == ci_).astype(np.uint8)
        ncc, lab_cc, stats, _cents = cv2.connectedComponentsWithStats(m8, connectivity=8)
        for k in range(1, ncc):
            if stats[k, cv2.CC_STAT_AREA] * mm_per_px * mm_per_px > DETAIL_DEFER_MAX_MM2:
                continue
            # Window to the component's bbox (v2 Part 17): the full-canvas dilate
            # here was the top profiler entry at 2x work resolution (4.7s/fixture).
            bx, by = stats[k, cv2.CC_STAT_LEFT], stats[k, cv2.CC_STAT_TOP]
            bw, bh = stats[k, cv2.CC_STAT_WIDTH], stats[k, cv2.CC_STAT_HEIGHT]
            wy0, wy1 = max(0, by - 3), min(ih, by + bh + 3)
            wx0, wx1 = max(0, bx - 3), min(iw, bx + bw + 3)
            comp_w = lab_cc[wy0:wy1, wx0:wx1] == k
            ring_w = cv2.dilate(comp_w.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~comp_w
            if ring_w.any() and float(later[wy0:wy1, wx0:wx1][ring_w].mean()) >= DETAIL_EMBED_SHARE:
                comp = np.zeros((ih, iw), bool)
                comp[wy0:wy1, wx0:wx1] = comp_w
                deferred_mask |= comp
                if not deferred_items or deferred_items[-1][0] != ci_:
                    deferred_items.append((ci_, center_, comp.copy()))
                else:  # one detail pass (one colour stop) per cluster, not per component
                    deferred_items[-1][2][:] |= comp
    work = [("main", ci_, c_, None) for _, ci_, c_ in clusters]
    work += [("detail", ci_, c_, comp) for ci_, c_, comp in deferred_items]

    # ── PASS A — collect every region before sewing any of them (v2 Part 52) ──
    # This loop decides WHICH regions exist; the loop after it decides how each
    # one is sewn. The split is not tidiness: the union of the design's object
    # contours is the seed that scored 32.34 deg in Part 51 against 38.84 for the
    # foreground silhouette, and in a single loop that union does not exist until
    # every object has already been sewn — so no generator could ever be handed
    # it. Nothing here emits a stitch, opens a colour stop or writes to either
    # diagnostic log; all of that stays in pass B, in its original order, so the
    # streams and the logs are byte-identical to before the split.
    plan = staging.DigitizePlan()
    seed_mask = np.zeros((ih, iw), np.uint8)
    for phase, cluster_idx, center, comp_mask in work:
        if phase == "main":
            mask = ((labels == cluster_idx) & ~deferred_mask).astype(np.uint8) * 255
        else:
            mask = comp_mask.astype(np.uint8) * 255
        # Opening removes speckle but also erases strokes ~2px wide (this is what
        # ate the "L" of HARBOR CLUB in fixture 07), so only open when the mask
        # is coarse enough to survive it.
        if cv2.countNonZero(cv2.erode(mask, np.ones((3, 3), np.uint8))) > 0.5 * cv2.countNonZero(mask):
            mask = _open_preserving_detail(mask, mm_per_px)
        # Textured input: solidify the ragged photographic boundary (v2 Part 29).
        # A photographed sew-out's colour regions have fuzzy thread-fringe edges;
        # a close at ~0.4mm heals the pinholes and gaps the fringe leaves, and
        # the following open sheds the fringe hairs themselves. Flat artwork
        # never takes this branch, so the corpus mask path is untouched.
        if is_textured and cv2.countNonZero(mask):
            kc = max(1, round(0.4 / mm_per_px))
            ko = max(1, round(0.3 / mm_per_px))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2 * kc + 1,) * 2, np.uint8))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2 * ko + 1,) * 2, np.uint8))
        # Substrate rule: a cluster the colour of the garment is only ink where it
        # forms a small enclosed element (knocked-out type, counters, catchlights).
        # A large expanse of it is the garment showing through a thin outline.
        #
        # SKIPPED for vector input (v2 Part 25): the rule exists because a raster
        # foreground is a GUESS and page-coloured regions inside the guess are
        # usually the page. An SVG's mask is declared, not guessed — a white
        # element on a white page is real artwork the file states explicitly,
        # and this rule was measured deleting exactly that (the white disc of
        # the white-on-white probe survived the mask and died here).
        if svg_mask is None and float(np.linalg.norm(center.astype(float) - substrate)) < SUBSTRATE_DELTA:
            # The garment is not a thread (v2 Part 41). A cluster the colour of
            # the cloth is the cloth showing between the design's elements, and
            # stitching it lays thread over bare fabric: measured on the black
            # neckline panel, 2,925 stitches (5.1% of all sewing) went into
            # near-black stops sitting 10.5 from the substrate — the gaps
            # BETWEEN petals, rendered as thread.
            #
            # This used to keep small enclosed regions as "knocked-out detail"
            # (a catchlight in a pupil, a counter). That is the wrong default
            # for embroidery: you do not stitch the background colour, you let
            # the cloth show. SVG input still keeps its declared elements — a
            # white shape on a white page is artwork the file states outright.
            if is_textured:
                substrate_px += int(cv2.countNonZero(mask))
                substrate_owned[mask > 0] = 255
                continue
            # ...but Part 41 applied that to FLAT ARTWORK too, and there the
            # substrate is the page, not a garment (v2 Part 45). On fixture 02 the
            # white wordmark sits inside a green card on a white page, so it
            # matched the substrate and the whole wordmark was deleted — 31
            # stitches and a colour stop, silently, with every metric improving
            # because coverage is scored against the objects that survive.
            #
            # Two signals were measured first and BOTH failed to separate the two
            # cases, which is why the rule keys on the input class instead:
            #
            #   feature                 fixture 02 (keep)   neckline panel (drop)
            #   enclosed by foreground        99.9%                92.8%
            #   blob half-width >= 0.3mm      85.9% of area        88.5% of area
            #
            # Texture does separate them, with room to spare: flat artwork scores
            # 0.00-4.10 on `_interior_texture` and a photograph of cloth 8.4-10.9,
            # against a 6.0 threshold. A photograph of a garment is cloth; a flat
            # export is a page, and a page-coloured island enclosed by artwork is
            # knocked-out design — type, counters, catchlights.
            #
            # So on flat art a substrate-coloured component is page when it is
            # CONTIGUOUS with the page, or when it is a large enclosed expanse.
            #
            # The size half of that test is not belt-and-braces; without it this
            # fix was measured filling fixture 04's ring with white thread — the
            # interior of an outline ring is enclosed by the ring and is still the
            # page. Measured share of the foreground per enclosed component:
            #
            #   fixture 02 wordmark   max  0.33%   -> keep (knocked-out type)
            #   fixture 06 script      one 7.36%   -> drop (counter of the script)
            #   fixture 04 ring       32.5%, 54.7% -> drop (the page inside a ring)
            #
            # 5% sits between them with 15x margin below and 6.5x above. It is the
            # threshold the pre-Part-41 rule used, restored — that rule was right
            # about flat artwork and wrong to be applied to photographs of cloth.
            outside = (fg_mask == 0).astype(np.uint8)
            reach = cv2.dilate(outside, np.ones((3, 3), np.uint8))
            fg_px = max(int(cv2.countNonZero(fg_mask)), 1)
            n_cc, cc_lab = cv2.connectedComponents(mask, connectivity=8)
            page = np.zeros_like(mask)
            for cc_i in range(1, n_cc):
                comp = cc_lab == cc_i
                comp_px = int(comp.sum())
                if (reach[comp].any()
                        or comp_px >= SUBSTRATE_ENCLOSED_MAX_SHARE * fg_px
                        or comp_px * mm_per_px * mm_per_px >= SUBSTRATE_ENCLOSED_MAX_MM2):
                    page[comp] = 255
            page_px = int(cv2.countNonZero(page))
            if page_px:
                substrate_px += page_px
                substrate_owned[page > 0] = 255
                mask = cv2.bitwise_and(mask, cv2.bitwise_not(page))
            if not cv2.countNonZero(mask):
                continue
        # RETR_CCOMP: 2-level hierarchy — top-level outlines + their interior holes
        # (letter counters, donuts). RETR_EXTERNAL would fill an 'o' solid.
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        hier = hierarchy[0] if hierarchy is not None else []

        # Raster order here, on purpose. The proximity ordering that actually
        # drives sewing needs to know where the previous object's last stitch
        # landed, which is generation state — so it stays in pass B and this pass
        # only establishes WHICH regions exist, never in what order they are sewn.
        tops = [i for i in range(len(contours)) if not (len(hier) and hier[i][3] != -1)]
        _cents = []
        for i in tops:
            m_ = cv2.moments(contours[i])
            _cents.append((m_["m10"] / m_["m00"], m_["m01"] / m_["m00"]) if m_["m00"] > 0
                          else tuple(contours[i][0][0].astype(float)))

        cplan = staging.ClusterPlan(phase=phase, cluster_idx=cluster_idx, center=center,
                                    mask=mask, tops=tops, centroids=_cents, regions=[])
        for ci in tops:
            contour = contours[ci]
            hole_contours = []
            if len(hier):
                child = hier[ci][2]
                while child != -1:
                    hole_contours.append(contours[child])
                    child = hier[child][0]
            # Area in PIXELS, not polygon area (v2 Part 36). `contourArea` uses
            # the shoelace formula over pixel CENTRES, so a 1px-wide stroke
            # encloses zero area however long it is, and a 2px stroke reads
            # about half its ink. The min-area filter then deleted thin artwork
            # outright: hairline linework, small lettering and a lattice
            # trellis each produced 15,641 contours of "area 0" and digitized
            # to ZERO objects. Counting the drawn pixels measures what the
            # filter has always meant — how much ink is here. For chunky shapes
            # the two agree, which is why the corpus streams are unchanged.
            probe = np.zeros_like(mask)
            cv2.drawContours(probe, [contour], -1, 255, thickness=cv2.FILLED)
            if hole_contours:
                cv2.drawContours(probe, hole_contours, -1, 0, thickness=cv2.FILLED)
            net_area = float(cv2.countNonZero(probe))
            if net_area < min_area_px:
                # Recorded, not logged. The drop log is written in pass B so its
                # entries keep their original order and the `seq` they are
                # numbered against; a speck decided here would otherwise land in
                # the log before any object had been sewn.
                cplan.regions.append(staging.RegionPlan(
                    top_index=ci, net_area_px=net_area, raw_contour=contour, dropped=True))
                continue
            cv2.drawContours(emitted_mask, [contour], -1, 255, thickness=cv2.FILLED)
            # Smooth the pixel staircase before it becomes stitches. Done here so
            # the stored contour (which drives rebuild) is smooth too, not just
            # this run's fill.
            smoothed = _smooth_contour(contour, mm_per_px)
            smoothed_holes = [_smooth_contour(h, mm_per_px) for h in hole_contours]
            # The seed, built from the region's own outline — the 32.34 deg seed
            # class, not the 38.84 deg foreground silhouette. Bounding-box work;
            # see `staging.add_to_seed` for why it must not be full-frame.
            staging.add_to_seed(seed_mask, smoothed, smoothed_holes)
            cplan.regions.append(staging.RegionPlan(
                top_index=ci, net_area_px=net_area, raw_contour=contour, dropped=False,
                contour=smoothed, holes=smoothed_holes))
        plan.clusters.append(cplan)

    # The field, solved ONCE for the design from the union of every object's own
    # outline. Part 51 measured the alternatives on the same panel: per colour
    # cluster 35.31 deg, foreground silhouette 38.84, this seed 32.34. Solving is
    # bounded by resolution rather than by contour count (Part 50 §6), so a
    # pathological input costs the same as a real one.
    plan.seed_mask = seed_mask
    plan.substrate_px = substrate_px
    plan.field = direction_field.solve(seed_mask) if cv2.countNonZero(seed_mask) else None
    staging.remember(plan)

    # ── PASS B — sew what pass A decided ─────────────────────────────────────
    # Nothing consumes `plan.field` yet, deliberately: Part 51 showed a straight
    # fill row can only take the field's regional mean and loses 45% of its value
    # doing so, and whether tatami or satin should consume it first is a
    # measurement, not a guess. This part makes the right field available; it does
    # not spend it. Stitch output is therefore unchanged.
    for cplan in plan.clusters:
        phase, cluster_idx, center = cplan.phase, cplan.cluster_idx, cplan.center
        mask = cplan.mask
        b, g, r = (int(v) for v in center)
        hexcol = f"#{r:02x}{g:02x}{b:02x}"
        this_stop = None  # opened lazily when this cluster's first real object appears
        stop_start = 0
        by_top = {rp.top_index: rp for rp in cplan.regions}
        # Sew this colour's regions in proximity order, not raster order (v2 Part
        # 48). `findContours` returns them bottom-up in scan order, so the needle
        # crossed the design between neighbours: measured on the panel, 29.36 m of
        # inter-object travel and a 30.03 mm median gap. Objects inside one colour
        # stop can be sewn in any order without adding a colour change, so this
        # costs nothing and is the only lever that matters — only 2.6% of trims
        # spanned under 3 mm, so converting short jumps would have touched 22 of
        # 844. Geometry is untouched; only the order and the joins between change.
        #
        # This stays in pass B because `_from` is where the LAST STITCH landed,
        # which does not exist until sewing has started.
        _from = (stitches[-1].x / mm_per_px, stitches[-1].y / mm_per_px) if stitches else None
        for ci in (cplan.tops[k] for k in _nearest_neighbour_order(cplan.centroids, _from)):
            rp = by_top.get(ci)
            if rp is None:
                continue
            if rp.dropped:
                dropped_speck_count += 1
                # Area, perimeter, and WHERE (v2 Part 49). The centroid was not
                # recorded before, so the only questions the log could answer were
                # "how much was dropped" and "how big" — never "was it structured".
                # Recovering an ornament that is filtered one bead at a time needs
                # the positions, and re-deriving them outside the pipeline is not
                # equivalent: the morphological open above removes single-pixel
                # noise, so a naive re-derivation on the raw cluster mask counts
                # 25,822 regions where the pipeline drops 768.
                # From the CONTOUR, not a filled probe. The first version took
                # moments over a full-size image once per dropped region — fine on
                # a design with a few hundred specks and catastrophic on noise,
                # where one colour holds tens of thousands. The fuzz suite caught
                # it: a 1500x1500 noise post went from ~16 s to over ten minutes.
                # Contour moments are O(points on the outline).
                _dm = cv2.moments(rp.raw_contour)
                if _dm["m00"]:
                    _dcx = _dm["m10"] / _dm["m00"] * mm_per_px
                    _dcy = _dm["m01"] / _dm["m00"] * mm_per_px
                else:
                    # Degenerate outline (collinear points) has zero area moment.
                    _pts = rp.raw_contour.reshape(-1, 2)
                    _dcx = float(_pts[:, 0].mean()) * mm_per_px
                    _dcy = float(_pts[:, 1].mean()) * mm_per_px
                _DROP_LOG.append((float(rp.net_area_px * mm_per_px * mm_per_px),
                                  float(cv2.arcLength(rp.raw_contour, True) * mm_per_px),
                                  float(_dcx), float(_dcy)))
                continue
            net_area = rp.net_area_px
            contour = rp.contour
            hole_contours = list(rp.holes)
            region = np.zeros_like(mask)
            cv2.drawContours(region, [contour], -1, 255, thickness=cv2.FILLED)
            for h in hole_contours:
                cv2.drawContours(region, [h], -1, 0, thickness=cv2.FILLED)

            rect = cv2.minAreaRect(contour)
            under_step_px = max(1, round(prof["under_mm"] / mm_per_px))
            pull_mm = prof["pull_mm"]
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
            sat_step = max(1, round(prof["satin_mm"] / mm_per_px))
            skel_pts = None
            median_w = 0.0
            uncovered = 1.0
            reason = ""
            # Cheap gate before thinning: if the typical width across the whole
            # region is far over the cap this is a broad fill, and thinning it
            # would cost time to reach the same answer.
            _dt = cv2.distanceTransform((region > 0).astype(np.uint8), cv2.DIST_L2, 5)
            region_med_w = float(np.median(_dt[_dt > 0])) * 2.0 * mm_per_px if (_dt > 0).any() else 0.0
            # Sub-thread features cannot be sewn — see MIN_FEATURE_W_MM's
            # measured grounding before touching the value.
            if 0.0 < region_med_w < MIN_FEATURE_W_MM:
                _CLASSIFICATION_LOG.append({
                    "seq": seq + 1, "region_median_w_mm": round(region_med_w, 2),
                    "skeleton_median_w_mm": 0.0, "uncovered_share": 1.0,
                    "reason": "sub_thread_feature", "decision": "SKIPPED",
                })
                continue
            if region_med_w > SATIN_MAX_W_MM * SATIN_PREGATE_SLACK:
                reason = "broad_fill_pregate"  # typical width far over the cap
            else:
                # The shared generation core (STEP 3c) — see `generation.py`.
                # This block and rebuild's were separate implementations of the
                # same sweep and drifted three times: pull compensation applied
                # twice, the remainder paced at the satin pitch instead of the
                # fill pitch, and the remainder's angle silently defaulted to 0.
                # `region` is UNDILATED on purpose; the core adds pull comp to
                # the column half-width itself.
                attempt = spine_satin(
                    region, mm_per_px=mm_per_px, spacing_px=sat_step,
                    max_step_px=max_step_px, fill_step_px=fill_step_px,
                    connect_px=connect_px, pull_mm=pull_mm,
                    stroke_mm=region_med_w, row_px=row_px,
                )
                median_w, uncovered = attempt.median_w_mm, attempt.uncovered_share
                axis_pts, reason = attempt.axis_pts, attempt.reason
                if attempt.viable:
                    skel_pts = attempt.points
                    skeleton_satin_used += 1
                    if attempt.remainder_tatami:
                        skeleton_partial_tatami += 1
                elif reason != "no_medial_axis":
                    # A freckle that has no axis at all is not a "fallback" —
                    # a tiny fill was always the right answer for it.
                    skeleton_tatami_fallback += 1
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
            fill_angle = 0.0  # satin carries its column angle instead; see below
            use_contour = False
            if skel_pts is not None:
                # Satin now always comes from the medial axis. The old
                # bounding-rect `_satin_zigzag` path is gone from digitizing:
                # it rotated the whole region to its min-area rectangle and
                # zigzagged across that, which only ever worked for a straight
                # bar — it could not follow a ring, an arc or a bend, which is
                # most of the thin geometry in real artwork. (`_satin_zigzag`
                # itself is retained: `rebuild_design` still uses it for objects
                # a user explicitly sets to SATIN.)
                # Underlay chosen by COLUMN WIDTH (v2 Part 24) instead of the
                # unconditional centre run every satin object got up to Part 23
                # — recipe in _satin_width_underlay.
                under, under_name = _satin_width_underlay(
                    region, axis_pts, median_w, prof, mm_per_px, under_step_px,
                    connect_px,
                    (constants._PENETRATION_FLOOR_MM / mm_per_px) if constants._PENETRATION_FLOOR_MM else 0.0,
                    MAX_STITCH_MM / mm_per_px,
                )
                underlay = UnderlayType(under_name)
                pts = _with_underlay(under, skel_pts, connect_px)
            else:
                # v2 Part 14: small holes are NOT knocked out of a fill. A hole
                # narrower than CONNECT_MM earns one thread crossing per fill row
                # (fixture 02's letters took one per row and read as mush), and a
                # small knockout saves no measurable thread while costing
                # registration. Standard digitizing practice: sew the fill solid
                # and stitch the small detail on top. Large holes (02's sun,
                # donut counters) keep the knockout.
                knockout_px2 = HOLE_KNOCKOUT_MIN_MM2 / (mm_per_px * mm_per_px)
                small_holes = [
                    hh for hh in hole_contours
                    if cv2.contourArea(hh) < knockout_px2
                    and _hole_covered_later(hh, labels, stitch_rank, stitch_rank[cluster_idx], mask.shape, mm_per_px, deferred_mask)
                ]
                if small_holes:
                    hole_contours = [hh for hh in hole_contours if cv2.contourArea(hh) >= knockout_px2]
                    cv2.drawContours(region, small_holes, -1, 255, thickness=cv2.FILLED)
                    top_region = _dilate_pull(region, pull_mm, mm_per_px)
                inset_px = max(1, round(prof["inset_mm"] / mm_per_px))
                under = _edge_walk(
                    region, inset_px, under_step_px, connect_px,
                    (constants._PENETRATION_FLOOR_MM / mm_per_px) if constants._PENETRATION_FLOOR_MM else 0.0,
                    MAX_STITCH_MM / mm_per_px,
                )
                # A band — a ring, a frame, a letter bowl — is the shape no
                # straight angle suits (v2 Part 24b). Requiring a hole as well as
                # the thickness ratio is the conservative call: an open arc (a
                # "C") would contour just as well, but a hole is unambiguous
                # evidence that the region wraps something, and a shape that
                # wraps nothing is the one at risk of a branching medial axis.
                use_contour = (
                    bool(hole_contours)
                    and net_area * mm_per_px * mm_per_px >= CONTOUR_FILL_MIN_MM2
                    and _band_ratio(top_region) <= CONTOUR_FILL_MAX_BAND_RATIO
                )
                if use_contour:
                    fill_angle = 0.0  # rows follow the outline; no single angle describes them
                    fill_pts = _contour_fill(
                        top_region, row_px,
                        max(1, min(max_step_px, round(CONTOUR_ROW_MAX_STEP_MM / mm_per_px))),
                        connect_px,
                    )
                else:
                    fill_pts = []
                if not fill_pts:
                    # v2 Part 24: rows follow the region's own long axis instead
                    # of the hard 0 degrees every fill got from Part 0 to Part 23.
                    use_contour = False
                    fill_angle, from_axis = _fill_angle_provenance(top_region)
                    if not from_axis:
                        # A6 alternation — free here: the edge-avoiding penalty
                        # has period 90, so the rotated angle dodges the same
                        # edges equally well.
                        if iso_fills % 2:
                            fill_angle = (fill_angle + 90.0) % 180.0
                            fill_angle = round(fill_angle - 180.0 if fill_angle > 90.0 else fill_angle, 1)
                        iso_fills += 1
                    fill_pts = _fill_by_component(top_region, row_px, fill_step_px, connect_px,
                                                  angle_deg=fill_angle)
                # Satin border on top of the fill (v2 Part 15) — the pro finish.
                # Area-gated: bordering specks doubles them for nothing.
                if net_area * mm_per_px * mm_per_px >= FILL_BORDER_MIN_MM2:
                    border_w = fill_border_width_px(mm_per_px)
                    fill_pts = fill_pts + _fill_border(
                        contour, hole_contours, border_w, sat_step, connect_px,
                        fill_pts[-1][:2] if fill_pts else None,
                        (constants._PENETRATION_FLOOR_MM / mm_per_px) if constants._PENETRATION_FLOOR_MM else 0.0,
                    )
                underlay = UnderlayType.EDGE_WALK
                # Edge run PLUS a low-density tatami layer across the top fill's
                # direction on anything big enough to sink (v2 Part 24). This is
                # the standard commercial recipe for a fill; up to Part 23 every
                # fill got the edge run alone.
                if net_area * mm_per_px * mm_per_px >= FILL_UNDERLAY_MIN_MM2:
                    # For a contour fill no single angle describes the top rows,
                    # so the underlay crosses the region's own axis instead —
                    # anything straight crosses concentric rows somewhere, and
                    # taking the axis keeps the choice from being arbitrary.
                    base_angle = _fill_angle(top_region) if use_contour else fill_angle
                    par = _parallel_underlay(
                        region, inset_px, max(1, round(row_px * FILL_UNDERLAY_PITCH_MULT)),
                        base_angle + FILL_UNDERLAY_ANGLE_OFFSET_DEG,
                        max_step_px, connect_px,
                        (constants._PENETRATION_FLOOR_MM / mm_per_px) if constants._PENETRATION_FLOOR_MM else 0.0,
                        MAX_STITCH_MM / mm_per_px,
                    )
                    if par:
                        under = _with_underlay(under, par, connect_px)
                        underlay = UnderlayType.PARALLEL
                pts = _with_underlay(under, fill_pts, connect_px)
            # The floor is passed only for SATIN. A tatami row advances along a
            # line, never zigzags, so the repair could not fire there anyway —
            # but not passing it keeps fills on exactly the path they had.
            #
            # Coalesce threshold for FILLS follows the row pitch (v2 Part 15):
            # adjacent fill rows connect with a stitch of one row pitch —
            # 0.45mm on cotton, INDUSTRY-STANDARD practice at 0.4-0.45mm — and
            # a 0.5mm minimum was deleting every row's first point. On straight
            # edges the replacement diagonal hugged the edge and hid it; on
            # fixture 02's sun the diagonals cut the arc and opened a visible
            # crescent, found by painting the emitted rows over the region.
            min_px, coalesce_floor_px = coalesce_params(
                mm_per_px, is_satin=is_satin,
                fill_row_px=None if is_satin else row_px,
            )
            pts = _coalesce_short(pts, min_px, coalesce_floor_px)
            # Floor BACKSTOP at the last transform (v2 Part 13). Every upstream
            # repair (_axis_underlay, _edge_walk, _restore_for_floor) runs before
            # coalescing, and coalescing can manufacture a fresh sub-floor
            # reversal out of clean inputs — Part 13's branch reordering exposed
            # exactly one (07 Satin 5, 0.277mm, at the underlay/top seam).
            # Enforcing here means no upstream reshuffle can leak a violation
            # into the stream again; on a clean object this is a no-op.
            if constants._PENETRATION_FLOOR_MM:  # unconditional since Part 15: fill borders zigzag too
                pts = _drop_floor_reversals(
                    pts, constants._PENETRATION_FLOOR_MM / mm_per_px, MAX_STITCH_MM / mm_per_px,
                )
            if len(pts) < 2:
                continue
            # Jumps that never leave this object's own region become hidden
            # travel runs (v2 Part 25) — see _route_travel. The floor backstop
            # then runs AGAIN, because two consecutive jumps converted to travel
            # form an out-and-back run whose turnaround is the same
            # needle-in-one-hole reversal the underlay dead-ends had in Part 11
            # (measured on fixture 04: travel out at x=45.11, back at 45.07,
            # 0.18mm apart at the turn). Same defect, same repair.
            # Border satin and pull comp land stitches up to the border
            # half-width OUTSIDE the region, so with the default 2px pad 77 of
            # the ring probe's 109 jump connections had "outside" endpoints
            # and were never routed — they shipped as trimmed jumps straight
            # across the counter (CTO review C2/A3). Shared with rebuild since
            # STEP 0 — see `travel_route_pad_px`.
            route_pad = travel_route_pad_px(pull_mm, mm_per_px)
            pts = _route_travel(pts, region, TRAVEL_STEP_MM / mm_per_px,
                                pad_px=route_pad,
                                min_pitch_px=MIN_STITCH_MM / mm_per_px)
            if constants._PENETRATION_FLOOR_MM:
                pts = _drop_floor_reversals(
                    pts, constants._PENETRATION_FLOOR_MM / mm_per_px, MAX_STITCH_MM / mm_per_px,
                )
            if this_stop is None:  # first real object → open a color stop (deferred COLOR_CHANGE)
                emitted_stop += 1
                this_stop = emitted_stop
                if emitted_stop > 1 and stitches:
                    stitches.append(Stitch(x=stitches[-1].x, y=stitches[-1].y, command="COLOR_CHANGE"))
                stop_start = len(stitches)
            obj_start = len(stitches)
            if stitches and stitches[-1].command != "COLOR_CHANGE":
                # Trim only when the connecting thread would be long enough to
                # matter (v2 Part 48). A trim costs roughly 2.5 s of machine time;
                # below TRIM_MIN_GAP_MM the machine carries a short thread to the
                # next region, which is what commercial digitizers do and what
                # every jump under this length already amounts to.
                gap = math.hypot(pts[0][0] * mm_per_px - stitches[-1].x,
                                 pts[0][1] * mm_per_px - stitches[-1].y)
                if gap >= TRIM_MIN_GAP_MM:
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
                    stitch_type=(
                        StitchType.SATIN if is_satin
                        else StitchType.CONTOUR_FILL if use_contour
                        else StitchType.TATAMI
                    ),
                    color_stop=this_stop,
                    density=1.0 / (prof["satin_mm"] if is_satin else prof["row_mm"]),
                    # Satin records the NORMALIZED walk axis, not raw rect[2]
                    # (CTO A5/C4): the raw angle is off by 90° whenever the
                    # generators' long-axis flip fired, so rebuild could not
                    # trust the stored value and recomputed minAreaRect —
                    # which made editing the angle a silent no-op.
                    stitch_angle=round(_satin_axis_deg(rect), 1) if is_satin else fill_angle,
                    underlay_type=underlay,
                    pull_compensation=round(pull_mm, 2),
                    entry_point=Point(x=pts[0][0] * mm_per_px, y=pts[0][1] * mm_per_px),
                    exit_point=Point(x=pts[-1][0] * mm_per_px, y=pts[-1][1] * mm_per_px),
                    connect_method=ConnectMethod.TRIM,
                    stitch_count=count,
                    contour=outline,
                    holes=hole_outlines,
                    # Provenance for the B1.5 pass-through: where this object's
                    # stitches are, and a fingerprint of the parameters that
                    # produced them. Filled in below, once the object exists to
                    # hash.
                    stitch_start=obj_start,
                )
            )
            objects[-1].params_hash = object_params_hash(objects[-1])

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

    # Dark-linework overlay (v2 Part 30): the drawn outlines a photograph
    # carries — leaf veins, petal boundaries, quill separations — recovered from
    # the image and sewn last, on top, in the palette's darkest thread. Textured
    # input only; flat artwork's dark lines are their own colour regions and
    # digitize as objects already.
    if is_textured and stitches:
        # "Dark linework" only exists when the artwork's lines are darker than
        # the cloth (v2 Part 41). On a dark garment nothing can be, so the
        # black-hat finds the GAPS BETWEEN elements and traces the garment
        # itself: measured on the black neckline panel, this pass alone emitted
        # 2,644 stitches of near-black thread over bare fabric, and simply
        # dropping the black colour stop only recoloured them to the next
        # darkest thread, which is worse — visible thread on bare cloth.
        substrate_lum = float(
            0.114 * substrate[0] + 0.587 * substrate[1] + 0.299 * substrate[2]
        )
        chains = (
            _dark_linework(img, fg_mask, mm_per_px)
            if substrate_lum >= DARK_CLOTH_LUM
            else []
        )
        if chains:
            def _lum(h: str) -> float:
                return 0.299 * int(h[1:3], 16) + 0.587 * int(h[3:5], 16) + 0.114 * int(h[5:7], 16)

            line_hex = min((s.hex for s in color_stops), key=_lum) if color_stops else "#202020"
            _lh = line_hex.lstrip("#")
            _line_bgr = np.array([int(_lh[4:6], 16), int(_lh[2:4], 16), int(_lh[0:2], 16)], np.float32)
            if float(np.linalg.norm(_line_bgr - substrate)) < SUBSTRATE_DELTA:
                # Drawing the garment's own colour onto the garment (v2 Part 41):
                # the darkest available thread IS the cloth here, so this pass
                # would trace the gaps between elements in invisible thread.
                chains = []
            emitted_stop += 1
            stitches.append(Stitch(x=stitches[-1].x, y=stitches[-1].y, command="COLOR_CHANGE"))
            stop_start = len(stitches)
            run_px = max(1.0, OUTLINE_RUN_MM / mm_per_px)
            for chain in chains:
                path = _resample_open(chain, run_px)
                if len(path) < 2:
                    continue
                if stitches[-1].command != "COLOR_CHANGE":
                    stitches.append(Stitch(x=stitches[-1].x, y=stitches[-1].y, command="TRIM"))
                stitches.append(Stitch(x=path[0][0] * mm_per_px, y=path[0][1] * mm_per_px, command="JUMP"))
                obj_start = len(stitches)
                for x, y in path:
                    stitches.append(Stitch(x=x * mm_per_px, y=y * mm_per_px, command="STITCH"))
                seq += 1
                objects.append(
                    DesignObject(
                        sequence_order=seq,
                        name=f"Line {seq} ({line_hex})",
                        stitch_type=StitchType.RUNNING_SINGLE,
                        color_stop=emitted_stop,
                        density=1.0 / OUTLINE_RUN_MM,
                        stitch_angle=0.0,
                        underlay_type=UnderlayType.NONE,
                        pull_compensation=0.0,
                        entry_point=Point(x=path[0][0] * mm_per_px, y=path[0][1] * mm_per_px),
                        exit_point=Point(x=path[-1][0] * mm_per_px, y=path[-1][1] * mm_per_px),
                        connect_method=ConnectMethod.TRIM,
                        stitch_count=len(stitches) - obj_start,
                        # The PATH, not an area: rebuild's RUNNING branch stitches
                        # along the stored contour rather than filling it.
                        contour=[Point(x=x * mm_per_px, y=y * mm_per_px) for x, y in path],
                    )
                )
            color_stops.append(
                ColorStop(
                    stop_number=emitted_stop,
                    thread_brand="Auto",
                    catalog_number="",
                    thread_name=f"Color {emitted_stop}",
                    hex=line_hex,
                    stitch_count=len(stitches) - stop_start,
                )
            )

    if stitches:
        last = stitches[-1]
        stitches.append(Stitch(x=last.x, y=last.y, command="END"))

    # Consecutive stops of one thread collapse into one mounting (v2 Part 25) —
    # BEFORE locking, so the deleted colour change never earns a tie pair.
    _merge_adjacent_same_hex(stitches, color_stops, objects)

    # Lock every thread end and trim every remaining long cross-fabric jump
    # (v2 Part 25). Runs on the assembled stream because cuts are created in
    # three places (object transition, colour change, END).
    stitches = _lock_stream(stitches)

    xs = [s.x for s in stitches if s.command == "STITCH"] or [0.0]
    ys = [s.y for s in stitches if s.command == "STITCH"] or [0.0]

    # ── Tell the user what was lost or altered (v2 Part 25) ──────────────────
    # Every branch below was a measured SILENT failure before this: a 40x40mm
    # hoop took the badge fixture from 21 objects to 4 and said nothing, and
    # max_colors=2 quietly returned 3 stops. The data was already collected
    # (_CLASSIFICATION_LOG, the speck counter); it just never left the function.
    user_warnings: list[str] = []
    # Two loss channels, two signals — because three simpler drafts were each
    # measured and rejected. A raw dropped-region count cries wolf (the badge
    # fixture at its intended hoop drops ~1,650 anti-aliasing specks totalling a
    # fraction of a percent); a contourArea share mis-scores thin linework
    # (fixture 04 read as "92% lost" because a hairline's polygon area is near
    # zero); and shape discriminators on the dropped specks separate nothing,
    # because at a small hoop EVERYTHING dropped is small. What actually happens
    # at a too-small hoop, measured on the badge (21 -> 5 objects by 70x70), is
    # that fine detail merges into neighbouring colour clusters during
    # quantization — the pixels survive, the elements don't — which no
    # post-hoc accounting of the filters can see.
    #
    # Signal 1 (exact, element-level): connected components of the OWNED
    # foreground that no emitted object touches AT ALL. Element-level and not
    # pixel-level, because a pixel accounting confounds real loss with edge
    # shaving — `_open_preserving_detail` and contour smoothing legitimately
    # shave the anti-aliased fringe of every shape, which read fixture 06's
    # script as "27% lost" when every stroke of it was emitted. An element that
    # is partially covered was digitized; an element with zero overlap is gone.
    # Owned means labels >= 0: blend pixels the halo suppression deliberately
    # leaves at -1 belong to no element.
    # Cloth left bare on purpose is not 'lost artwork' — excluding it keeps the
    # dropped-detail warning honest.
    owned = ((labels >= 0) & (substrate_owned == 0)).astype(np.uint8)
    n_own, own_lab, own_stats, _c = cv2.connectedComponentsWithStats(owned, connectivity=8)
    lost_px = 0
    covered = np.bincount(own_lab[emitted_mask > 0].reshape(-1), minlength=n_own)
    for k in range(1, n_own):
        if own_stats[k, cv2.CC_STAT_AREA] >= min_area_px and covered[k] == 0:
            lost_px += int(own_stats[k, cv2.CC_STAT_AREA])
    lost_share = lost_px / max(1, cv2.countNonZero(owned))
    # Photographic rescue (v2 Part 65). A low-resolution photo of a sew-out
    # can sit UNDER the Part 27 variance gate while its thread texture still
    # shatters colour areas into sub-thread webs at quantization — the
    # competitor angelfish photo lost most of its body this way while
    # measuring 1.86 against the 6.0 gate. No input-side metric separates
    # that photo from the flat-art corpus (which reaches 4.10), so the rescue
    # is gated on the OUTCOME — and on the PIXEL share of owned foreground no
    # object covers, not on the element-level lost_share above, which a webbed
    # photo defeats (one giant connected element, "covered" by any surviving
    # fragment). When the plain path leaves the gate's share of the artwork
    # unsewn, digitize once more with the mean-shift forced, and keep that
    # result only if it demonstrably recovers artwork.
    global _LAST_UNCOVERED_PX
    # Base: segmentation foreground minus deliberate substrate — NOT `owned`,
    # because the web damage this rescue exists to catch happens before
    # ownership (halo suppression leaves the shattered pixels at label -1, so
    # an owned-base ratio never sees them).
    art_base = ((fg_mask > 0) & (substrate_owned == 0)).astype(np.uint8)
    uncovered_px = 1.0 - cv2.countNonZero(
        cv2.bitwise_and(art_base, (emitted_mask > 0).astype(np.uint8))
    ) / max(1, cv2.countNonZero(art_base))
    _LAST_UNCOVERED_PX = uncovered_px
    if (svg_mask is None and not is_textured and _texture_smooth is None
            and uncovered_px >= TEXTURE_RETRY_UNCOVERED
            and _uncovered_chunk_mm2(art_base, emitted_mask, mm_per_px)
                >= TEXTURE_RETRY_MIN_CHUNK_MM2):
        # The recursive run clears and rewrites the module drop/classification
        # logs; snapshot them so a REJECTED retry leaves the caller's logs
        # describing the design actually returned (a kept retry's logs are the
        # child's own, which is correct for the design it returns).
        drop_snapshot = list(_DROP_LOG)
        cls_snapshot = list(_CLASSIFICATION_LOG)
        retry = digitize_image(data, fabric_type, hoop_size, max_colors,
                               min_region_mm2, text_mode, _texture_smooth=True)
        retry_unc = _LAST_UNCOVERED_PX  # set by the recursive call
        _LAST_UNCOVERED_PX = uncovered_px
        if retry_unc <= uncovered_px - TEXTURE_RETRY_MIN_GAIN:
            note = (
                f"Photographic texture: {uncovered_px:.0%} of the artwork could "
                "not be traced directly, so the photo was smoothed and "
                f"re-traced (now {retry_unc:.0%} untraced). For best results "
                "digitize from the original flat artwork rather than a photo."
            )
            return retry.model_copy(update={"warnings": [note, *retry.warnings]})
        _DROP_LOG[:] = drop_snapshot
        _CLASSIFICATION_LOG[:] = cls_snapshot
    if lost_share >= DROPPED_SHARE_WARN:
        user_warnings.append(
            f"About {lost_share:.0%} of the artwork is too small or too "
            "faint to sew at this size and was left out. A larger hoop keeps more detail."
        )
    # Signal 2 (heuristic, and labelled as such): source resolution vs physical
    # size. When many source pixels map to each millimetre, the artwork was
    # authored with detail this hoop cannot express — a 2px feature at 10px/mm
    # is 0.2mm, under the 40wt thread itself. This is the only available sensor
    # for the merge channel, which destroys elements before any filter runs.
    # Skipped for vector input: its raster resolution is chosen by US at render
    # time, so pixels-per-millimetre says nothing about the artwork's detail.
    src_px_per_mm = max(src_iw, src_ih) / max(design_w_mm, 1e-6)
    if svg_mask is None and src_px_per_mm >= FINE_DETAIL_SRC_PX_PER_MM:
        user_warnings.append(
            f"The image is {max(src_iw, src_ih)}px across but the design is only "
            f"{design_w_mm:.0f}mm wide — fine detail (small text, thin lines) may "
            "not survive at this size. Try a larger hoop, or simplify the artwork."
        )
    # A request past the planner's cap has been silently discarded since the
    # planner landed; Part 57 measured it inert (k=12 and k=8 byte-identical)
    # and Part 58 decided: keep the cap, say so. `k_plan` rather than the bare
    # cap in the message, because an outline-check retry can raise the plan.
    if int(max_colors) > PLAN_MAX_COLORS:
        user_warnings.append(
            f"Colour limit: {int(max_colors)} colours were requested, but colour "
            f"planning uses at most {PLAN_MAX_COLORS} — this design was planned "
            f"with {k_plan}. Values above {PLAN_MAX_COLORS} do not change the result."
        )
    distinct_hexes = len({s.hex for s in color_stops})
    if len(color_stops) > max_colors:
        user_warnings.append(
            f"Requested {max_colors} colours but the design uses {len(color_stops)} "
            f"colour stops ({distinct_hexes} distinct threads): detail stitched on top "
            "of a background fill opens a second stop of the same thread."
        )
    elif distinct_hexes < max_colors:
        user_warnings.append(
            f"Requested {max_colors} colours; the artwork only separated into "
            f"{distinct_hexes} distinguishable colour{'s' if distinct_hexes != 1 else ''}."
        )
    if n_shade_splits:
        user_warnings.append(
            f"{n_shade_splits} extra shade{'s' if n_shade_splits != 1 else ''} "
            "recovered from colour gradients in the photo (each is a real thread "
            "band the colour limit had merged away)."
        )
    # The outline check (v2 Part 33): sketch-then-verify. Quiet when the first
    # plan holds; when a re-plan fired, the user asked for fewer colours than
    # the artwork's structure needs, and that must be said rather than silently
    # overridden in either direction.
    if sketch_retries:
        user_warnings.append(
            f"Outline check: the first colour plan missed too many of the artwork's "
            f"lines and was re-drawn with {k_plan} colours "
            f"(structure now verified at {sketch_cov:.0%})."
        )
    elif sketch_cov < 0.9:
        user_warnings.append(
            f"Outline check: {sketch_cov:.0%} of the artwork's edges are captured "
            "by the colour plan — fine detail beyond that is below stitchable scale."
        )

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
        warnings=user_warnings,
        # The grid every generator above actually ran on, so a later rebuild
        # can reproduce it instead of guessing (CTO verdict STEP 3).
        source_mm_per_px=round(float(mm_per_px), 6),
    )
