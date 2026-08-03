"""Colour planning: clustering, sketch-verify, texture, linework."""

from __future__ import annotations

from itertools import pairwise

from app.services.digitizer.constants import (
    AMBIGUOUS_BLEND_RATIO,
    AMBIGUOUS_MAX_CUT_SHARE,
    AMBIGUOUS_MIN_CENTRE_GAP,
    MERGE_DELTA,
    OUTLINE_BLACKHAT_DELTA,
    OUTLINE_BLACKHAT_MM,
    OUTLINE_MAX_HALF_MM,
    OUTLINE_MIN_MM,
    PALETTE_BIN,
    PALETTE_UNIFORM_TOL,
    SKETCH_EDGE_TOL_PX,
    SPECK_ABSORB_MAX_MM2,
    SPECK_ABSORB_RING_SHARE,
    SPLIT_DELTA_BGR,
    SPLIT_MAX_EXTRA,
    SPLIT_MIN_AREA_MM2,
    THIN_PALETTE_MIN_SHARE,
)
from app.services.digitizer.geometry import (
    _distance_transform,
    _merge_centers,
)
from app.services.digitizer.skeleton import (
    _axis_branches,
)


def _is_background(center_bgr, corners_bgr) -> bool:
    """v1 background test — kept only for the corner fallback path and tests.

    Superseded in v2 by ``segmentation.foreground_mask``: this compares COLOURS
    globally, so a design layer that happens to match the backdrop is deleted
    everywhere it appears. See the v1 baseline audit §5 root causes #1 and #2.
    """
    import numpy as np

    return bool(np.linalg.norm(center_bgr.astype(float) - corners_bgr.astype(float)) < 40.0)


def _split_bimodal_clusters(Z, fg_labels, centers, mm_per_px: float):
    """Split clusters whose members are two distinct colour modes.

    Returns (centers, fg_labels, n_splits); mutates fg_labels in place. Ranked
    by separation x size and capped, so only the strongest few gradient bands
    are recovered rather than shattering every shaded cluster.
    """
    import cv2
    import numpy as np

    min_px = SPLIT_MIN_AREA_MM2 / max(mm_per_px * mm_per_px, 1e-9)
    candidates = []
    for ci in range(len(centers)):
        idx = np.flatnonzero(fg_labels == ci)
        if len(idx) < 2 * min_px:
            continue
        members = Z[idx]
        cv2.setRNGSeed(20260728)  # deterministic sub-split
        _c, sub, _sub_cen = cv2.kmeans(
            members, 2, None,
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0), 3,
            cv2.KMEANS_PP_CENTERS,
        )
        sub = sub.reshape(-1)
        n0, n1 = int((sub == 0).sum()), int((sub == 1).sum())
        if min(n0, n1) < min_px:
            continue
        m0 = np.median(members[sub == 0], axis=0)
        m1 = np.median(members[sub == 1], axis=0)
        gap = float(np.linalg.norm(m0 - m1))
        if gap < SPLIT_DELTA_BGR:
            continue
        candidates.append((gap * min(n0, n1), ci, idx, sub, m0, m1))
    n_splits = 0
    centers = list(centers)
    for _score, ci, idx, sub, m0, m1 in sorted(candidates, reverse=True, key=lambda t: t[0]):
        if n_splits >= SPLIT_MAX_EXTRA:
            break
        centers[ci] = m0.astype(np.float32)
        fg_labels[idx[sub == 1]] = len(centers)
        centers.append(m1.astype(np.float32))
        n_splits += 1
    import numpy as _np
    return _np.array(centers, _np.float32), fg_labels, n_splits


def _sketch_from_labels(labels, fg_mask):
    """The plan's rough sketch: every boundary between differently-planned
    regions, plus the design's outer outline. uint8 0/255."""
    import cv2
    import numpy as np

    lab = labels.astype(np.int32)
    edge = np.zeros(lab.shape, bool)
    edge[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edge[1:, :] |= lab[1:, :] != lab[:-1, :]
    edge &= fg_mask > 0
    outline = cv2.morphologyEx(fg_mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    return ((edge | outline).astype(np.uint8)) * 255


def _verify_sketch(sketch, img, fg_mask):
    """(edge_coverage, stroke_precision) of the sketch against the source.

    Coverage: share of the source's own strong edges that lie within
    SKETCH_EDGE_TOL_PX of a sketch stroke — "did the plan draw every line the
    artwork has?". Precision: share of sketch strokes lying near a true edge —
    "did the plan invent lines?". Both in [0, 1].
    """
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    near = cv2.dilate(fg_mask, np.ones((7, 7), np.uint8)) > 0
    true_edges = (cv2.Canny(gray, 50, 120) > 0) & near
    n_true = int(true_edges.sum())
    n_sketch = int((sketch > 0).sum())
    if n_true < 32 or n_sketch < 32:
        return 1.0, 1.0  # nothing to verify against — a blank plan is not a failure
    k = np.ones((2 * SKETCH_EDGE_TOL_PX + 1,) * 2, np.uint8)
    sketch_zone = cv2.dilate(sketch, k) > 0
    edge_zone = cv2.dilate(true_edges.astype(np.uint8) * 255, k) > 0
    coverage = float((true_edges & sketch_zone).sum()) / n_true
    precision = float(((sketch > 0) & edge_zone).sum()) / n_sketch
    return coverage, precision


def _absorb_specks(labels, mm_per_px: float):
    """Relabel sub-speck colour components to the cluster that surrounds them.

    Operates on the quantized label map, so the fix happens before objects,
    holes, or deferral ever exist: the surrounding fill simply grows over the
    speck, no knockout, no extra object, no trim.
    """
    import cv2
    import numpy as np

    out = labels.copy()
    max_px = SPECK_ABSORB_MAX_MM2 / max(mm_per_px * mm_per_px, 1e-9)
    k3 = np.ones((3, 3), np.uint8)
    ih, iw = out.shape
    for c in np.unique(out):
        if c < 0:
            continue
        n, lab, st, _cents = cv2.connectedComponentsWithStats((out == c).astype(np.uint8), 8)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] > max_px:
                continue
            x, y, w, h = (st[i, k] for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                             cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
            wy0, wy1 = max(0, y - 2), min(ih, y + h + 2)
            wx0, wx1 = max(0, x - 2), min(iw, x + w + 2)
            comp = lab[wy0:wy1, wx0:wx1] == i
            ring = cv2.dilate(comp.astype(np.uint8), k3).astype(bool) & ~comp
            ring_vals = out[wy0:wy1, wx0:wx1][ring]
            ring_vals = ring_vals[(ring_vals >= 0) & (ring_vals != c)]
            if ring_vals.size == 0:
                continue
            vals, counts = np.unique(ring_vals, return_counts=True)
            # Share is judged over OWNED OTHER-cluster ring pixels: a speck at
            # a region's outer edge has background (-1) in its ring, and
            # counting background as a dissenting vote left visible flecks at
            # every leaf edge on the peacock while interior flecks absorbed.
            # Same-cluster ring pixels cannot occur (the component is maximal).
            if counts.max() >= SPECK_ABSORB_RING_SHARE * int(ring_vals.size):
                out[wy0:wy1, wx0:wx1][comp] = vals[counts.argmax()]
    return out


def _dark_linework(img, fg_mask, mm_per_px: float):
    """Thin dark drawn lines in a textured image, as ordered px polylines."""
    import math

    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = max(3, 2 * round(OUTLINE_BLACKHAT_MM / mm_per_px) + 1)
    bh = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    near_fg = cv2.dilate(fg_mask, np.ones((5, 5), np.uint8)) > 0
    lines = ((bh > OUTLINE_BLACKHAT_DELTA) & near_fg).astype(np.uint8)
    if cv2.countNonZero(lines) == 0:
        return []
    # Blobs are regions wearing a dark colour, not drawing; a LINE is thin by
    # definition, so anything past the half-width cap is cut before thinning.
    dist = cv2.distanceTransform(lines, cv2.DIST_L2, 3)
    lines[dist > max(2.0, OUTLINE_MAX_HALF_MM / mm_per_px)] = 0
    lines = cv2.morphologyEx(lines, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if cv2.countNonZero(lines) == 0:
        return []
    _skel, branches = _axis_branches(lines, _distance_transform(lines), mm_per_px)
    min_len = OUTLINE_MIN_MM / mm_per_px
    out = []
    for b in branches:
        if len(b) < 2:
            continue
        if sum(math.dist(p, q) for p, q in pairwise(b)) >= min_len:
            out.append([(float(x), float(y)) for x, y in b])
    # Nearest-first chaining keeps the travel between lines short.
    ordered = []
    cur = (0.0, 0.0)
    while out:
        i = min(range(len(out)), key=lambda j: min(
            (out[j][0][0] - cur[0]) ** 2 + (out[j][0][1] - cur[1]) ** 2,
            (out[j][-1][0] - cur[0]) ** 2 + (out[j][-1][1] - cur[1]) ** 2))
        chain = out.pop(i)
        if ((chain[-1][0] - cur[0]) ** 2 + (chain[-1][1] - cur[1]) ** 2 <
                (chain[0][0] - cur[0]) ** 2 + (chain[0][1] - cur[1]) ** 2):
            chain.reverse()
        ordered.append(chain)
        cur = chain[-1]
    return ordered


def _interior_texture(img) -> float:
    """Median local luminance stddev in region INTERIORS, away from edges.

    The gate for photographic/textured input (v2 Part 27). Interiors only,
    because a naive whole-foreground measure confounds texture with EDGES —
    fixture 04's thin linework scored 99.2 (it is all edge) while a photographed
    embroidery patch scored 34.7, ranking flat art as more "textured" than a
    photo of thread. Sampling ≥3px clear of Canny edges fixes the ranking:
    corpus fixtures measure 0.00–4.10 (fixture 09's photographic background is
    the max) and the embroidery photo 7.43.
    """
    import cv2
    import numpy as np

    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mu = cv2.blur(g, (5, 5))
    sd = np.sqrt(np.maximum(cv2.blur(g * g, (5, 5)) - mu * mu, 0))
    sub = np.array([img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]], np.float32).mean(axis=0)
    fg = (np.linalg.norm(img.astype(np.float32) - sub, axis=2) >= 40).astype(np.uint8)
    edges = cv2.Canny(g.astype(np.uint8), 60, 140)
    interior = cv2.erode(fg, np.ones((5, 5), np.uint8)) & (cv2.dilate(edges, np.ones((5, 5), np.uint8)) == 0)
    n = int(interior.sum())
    # A very dense texture can shred the interior sample to nothing; 500 samples
    # keeps the median stable, below that the gate abstains (known limitation).
    return float(np.median(sd[interior > 0])) if n >= 500 else 0.0


def _band_ratio(region) -> float:
    """How thick a region is relative to its own extent: ``2 * peak_dist / sqrt(area)``.

    Near 0 for a band (a ring, a frame, a letter bowl) and above 1 for a disc,
    because a band's thickness does not grow when you make the band longer. Used
    to tell "this is a stroke too wide to satin" from "this is a blob", which is
    the difference between contour rows flowing and contour rows tearing.
    """
    import math

    import cv2
    import numpy as np

    m = (region > 0).astype(np.uint8)
    area = int(m.sum())
    if area <= 0:
        return 0.0
    peak = float(cv2.distanceTransform(m, cv2.DIST_L2, 5).max())
    return 2.0 * peak / math.sqrt(area)
def _plan_palette(
    k: int,
    *,
    img,
    fg_mask,
    fg_flat,
    flat_rgb,
    Z,
    ih,
    iw,
    up_f,
    is_textured,
    mm_per_px,
):
    """One k-means colour plan over the foreground, as a label image.

    Extracted verbatim from `digitize_image`, where it was a closure over the
    ten values now passed explicitly (R001). It reads all ten and assigns none,
    which is what made the extraction safe; the stream locks prove it.
    """
    import cv2
    import numpy as np

    ek = max(1, round(up_f))
    interior = cv2.erode(fg_mask, np.ones((2 * ek + 1, 2 * ek + 1), np.uint8))
    pal_flat = interior.reshape(-1) > 0
    if int(pal_flat.sum()) < max(16, 0.05 * int(fg_flat.sum())):
        pal_flat = fg_flat  # design too thin to erode — fall back to all of it
    Z_pal = flat_rgb[pal_flat]
    # ...but a colour that exists ONLY in thin strokes is erased by that
    # erosion and never enters the palette at all (v2 Part 36). Measured on
    # a lattice trellis: the erosion kept the white diamonds and removed
    # every line, so k-means saw three shades of white, the ink was never a
    # cluster, and the design digitized to ZERO objects. The same hole
    # applies to any outline-only colour — linework, stems, text strokes.
    #
    # Recovered by looking for colour MODES the eroded sample missed. A
    # real ink is a sharp peak in the histogram (many pixels at nearly one
    # value); an anti-aliasing blend is smeared along the gradient between
    # two inks and never peaks. Requiring a local maximum is what keeps
    # this from re-admitting the halos the erosion exists to exclude.
    if pal_flat is not fg_flat:
        # Only locally UNIFORM pixels may seed a recovered colour: a
        # stroke's core is flat, while the blend band our own cubic upscale
        # creates along its edge is a gradient. Without this the lattice's
        # halo seeded four more "inks" spanning white->cyan, and the line
        # shattered across them just as badly as before.
        med = cv2.medianBlur(img, 3)
        uniform = (
            np.abs(img.astype(np.int16) - med.astype(np.int16)).max(axis=2)
            <= PALETTE_UNIFORM_TOL
        ).reshape(-1)
        core_flat = fg_flat & uniform
        if int(core_flat.sum()) < 64:
            core_flat = fg_flat
        fg_rgb = flat_rgb[core_flat]
        bins = (fg_rgb // PALETTE_BIN).astype(np.int32)
        keys = (bins[:, 0] << 12) | (bins[:, 1] << 6) | bins[:, 2]
        pbins = (Z_pal // PALETTE_BIN).astype(np.int32)
        seen = set(
            np.unique((pbins[:, 0] << 12) | (pbins[:, 1] << 6) | pbins[:, 2]).tolist()
        )
        uk, cnt = np.unique(keys, return_counts=True)
        mass = dict(zip(uk.tolist(), cnt.tolist()))
        floor = max(64, THIN_PALETTE_MIN_SHARE * len(keys))
        recover = []
        for key, n in mass.items():
            if key in seen or n < floor:
                continue
            b, g, r = (key >> 12) & 63, (key >> 6) & 63, key & 63
            peak = True
            for db in (-1, 0, 1):
                for dg in (-1, 0, 1):
                    for dr in (-1, 0, 1):
                        if db == dg == dr == 0:
                            continue
                        nb = ((b + db) << 12) | ((g + dg) << 6) | (r + dr)
                        if mass.get(nb, 0) > n:
                            peak = False
            if peak:
                recover.append(key)
        if recover:
            Z_pal = np.vstack([Z_pal, fg_rgb[np.isin(keys, recover)]])

    k = max(1, min(int(k), 12, len(np.unique(Z_pal, axis=0))))  # 12: retry headroom past the base cap of 8
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
    # Collapse duplicate palette centres (v2 Part 36). k-means always
    # returns k centres even when the artwork holds fewer real colours, so
    # asking a 2-colour image for 8 puts the spare centres INSIDE the
    # anti-aliasing gradient between the two. Those centres then claim the
    # halo, and every stroke shatters: a lattice trellis' 48,877px of line
    # became 15,641 fragments averaging 3px, all under the speck filter, and
    # the design digitized to zero objects. Merging centres closer than one
    # thread's worth of colour re-forms the strokes. Non-degenerate palettes
    # have no such pairs, so the corpus is untouched.
    if len(centers) > 1:
        cf = centers.astype(np.float32)
        counts = np.bincount(fg_labels, minlength=len(cf))
        # Greedy merge into the DOMINANT centre, never transitively. A
        # union-find over "closer than the gap" chains white -> halo ->
        # halo -> ink across an anti-aliasing gradient and collapses the
        # whole image into one cluster (measured: it did exactly that on
        # the lattice). Anchoring every merge to an already-kept, larger
        # centre keeps two real colours apart no matter how finely the
        # blend between them is sampled.
        remap = np.full(len(cf), -1, np.int32)
        kept: list[int] = []
        for i in np.argsort(-counts):
            target = next(
                (
                    k
                    for k in kept
                    if float(np.linalg.norm(cf[i] - cf[k])) < AMBIGUOUS_MIN_CENTRE_GAP
                ),
                None,
            )
            if target is None:
                remap[i] = len(kept)
                kept.append(int(i))
            else:
                remap[i] = remap[target]
        if len(kept) < len(cf):
            centers = np.array([cf[k] for k in kept], dtype=centers.dtype)
            fg_labels = remap[fg_labels]
            d2 = np.empty((len(Z), len(centers)), np.float32)
            for ci in range(len(centers)):
                diff = Z - centers[ci]
                d2[:, ci] = np.einsum("ij,ij->i", diff, diff)
            fg_labels = d2.argmin(axis=1).astype(np.int32)
    # The ambiguous-blend cut is SKIPPED for textured input (v2 Part 31): on
    # flat artwork a pixel equidistant from two palette colours is an
    # anti-aliasing halo, but on a photograph it is a real transition thread —
    # and the cut was measured swallowing the peacock's entire teal band before
    # gradient recovery could see it (the teal half showed up in the split scan
    # only when the cut was off: #507164, 3,221px, gap 49.8 from its brown
    # parent cluster).
    if len(centers) > 1 and not is_textured:
        # A pixel roughly equidistant from two palette colours IS the blend
        # between them. Assigning it to the nearer one grows every shape by
        # about a pixel per side, which pushed a 3.6mm satin bar over the 4mm
        # satin/tatami threshold. Leave those unassigned instead: they belong to
        # neither layer, and dropping them keeps shapes at their true width.
        #
        # ...but ONLY when the two nearest centres are actually different
        # colours (v2 Part 36). k-means always returns k centres even when
        # the artwork holds fewer distinct colours, so a 2-colour image
        # asked for 8 gets DUPLICATE centres. Every ink pixel is then
        # equidistant from two identical centres, the ratio test calls it a
        # blend, and the ink is discarded: measured on a lattice trellis,
        # 57,532px of line — the entire design — went unassigned and the
        # digitize returned ZERO objects. A pixel between two centres of
        # the same colour is not a blend of two threads; it is solidly that
        # colour. Requiring a real gap leaves non-degenerate palettes (every
        # corpus fixture) bit-identical.
        order2 = np.argpartition(d2, 1, axis=1)[:, :2]
        nearest2 = np.take_along_axis(d2, order2, axis=1)
        gap = np.linalg.norm(
            centers[order2[:, 0]].astype(np.float32)
            - centers[order2[:, 1]].astype(np.float32),
            axis=1,
        )
        ambiguous = (nearest2[:, 0] > AMBIGUOUS_BLEND_RATIO * nearest2[:, 1]) & (
            gap >= AMBIGUOUS_MIN_CENTRE_GAP
        )
        # A shape that is MOSTLY boundary cannot afford to lose its
        # boundary (v2 Part 36). Dropping the blend ring costs a chunky
        # shape a pixel per side — the whole point — but on a thin stroke
        # the ring IS the stroke: on a lattice trellis the cut removed
        # 57,318 of 95,227 line pixels (60%) and severed what was left into
        # 521 islands of ~73px, every one under the 2mm² speck floor, so
        # the design digitized to ZERO objects (measured: with the cut
        # disabled the same image yields 12 objects). So the cut is applied
        # per cluster and skipped where it would take more than
        # AMBIGUOUS_MAX_CUT_SHARE of that cluster's ink. Chunky artwork is
        # a few percent boundary and never trips it.
        for c in range(len(centers)):
            in_c = fg_labels == c
            n_c = int(in_c.sum())
            if n_c and int((ambiguous & in_c).sum()) > AMBIGUOUS_MAX_CUT_SHARE * n_c:
                ambiguous &= ~in_c
        fg_labels[ambiguous] = -1
    # Gradient-band recovery (v2 Part 31, textured input only): clusters that
    # merged two real thread colours under the k cap split back apart. Runs
    # BEFORE the median recentre so both halves get their own true median.
    n_shade_splits = 0
    if is_textured:
        centers, fg_labels, n_shade_splits = _split_bimodal_clusters(Z, fg_labels, centers, mm_per_px)
    # Truer thread colours (v2 Part 16): the k-means centroid averages every
    # member pixel INCLUDING anti-aliased blends, muddying flat-art colours.
    # The per-channel median of the cluster's members is robust to the blend
    # tail and lands on the ink the artwork actually used.
    for ci in range(len(centers)):
        member = Z[fg_labels == ci]
        if len(member) > 8:
            centers[ci] = np.median(member, axis=0)
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

    # Textured input: absorb colour specks into their surroundings (v2 Part 29).
    # Even after mean-shift, a photographed sew-out leaves confetti — measured
    # on the peacock: 52 of 128 objects were under 40 stitches, each one a trim,
    # a lock, and a fleck of the wrong colour inside another region's fill. A
    # component smaller than a few thread widths whose ring is solidly one other
    # cluster IS that cluster, misassigned by shading. Runs before the deferral
    # scan so deferral sees the cleaned map. Flat artwork never reaches this.
    if is_textured:
        labels = _absorb_specks(labels, mm_per_px)
        # Seam fill (v2 Part 29): on flat artwork, blend pixels (-1) are
        # anti-aliasing halos and deliberately belong to no cluster. On a
        # photograph they are the BOUNDARIES between abutting regions — leaving
        # them unowned put a white pinhole seam wherever navy met green on the
        # peacock's tail, everywhere, which no real sew-out has. Each unowned
        # foreground pixel joins its nearest cluster; regions then abut exactly,
        # and the per-object pull compensation overlaps them as usual.
        seam = (labels < 0) & (fg_mask > 0)
        if seam.any():
            _dist_t, nearest = cv2.distanceTransformWithLabels(
                (labels < 0).astype(np.uint8), cv2.DIST_L2, 5,
                labelType=cv2.DIST_LABEL_PIXEL,
            )
            owned_flat = np.flatnonzero(labels.reshape(-1) >= 0)
            # nearest[] indexes pixels where labels>=0 by their DIST_LABEL_PIXEL id,
            # which enumerates the ZERO pixels of the source mask in scan order.
            lut = labels.reshape(-1)[owned_flat]
            labels[seam] = lut[nearest[seam] - 1]

    return labels, centers, n_shade_splits
