"""Foreground/background separation for the digitizer (v2 Part 1).

Why this module exists
----------------------
v1 decided "background" by **colour identity**: any k-means cluster within
ΔBGR < 40 of the average of the four corner pixels was discarded *everywhere in
the image*. The v1 baseline audit traced two of its three worst root causes to
that single rule:

  * fixture 02 — the white lettering is literally the same colour as the page
    background (Δ = 0.0), so the whole white layer was deleted and the type
    survived only as unstitched negative space;
  * fixture 08 — the cream muzzle sits Δ = 34.8 from white, just under the
    cutoff, so the muzzle and both eye-whites vanished;
  * fixture 09 — the tan and teal bands of a gradient backdrop sit Δ = 53 and
    51, just *over* the cutoff, so the background was stitched as foreground.

The fix is conceptual, not a threshold tweak: background is a property of
**where a pixel is**, not of **what colour it is**. This module returns a
foreground *mask*. The same cream can then be background outside the subject
and a real thread layer inside it.

Three tiers, best first; each falls back cleanly so the app still runs with no
optional dependency and no network:

  1. ``rembg`` (U2-Net, MIT). Learned salient-object segmentation. Best on
     photographic and non-uniform-background input. Optional dependency,
     lazily imported, and its result is sanity-checked before use.
  2. Border flood-fill. Region-grows inward from the image border with a local
     colour tolerance, so a smooth gradient backdrop is absorbed while an
     enclosed shape is not. Pure OpenCV, offline, deterministic. This is the
     tier that recovers enclosed same-as-background layers (02, 07, 08).
  3. The v1 corner heuristic, kept only as a last resort so behaviour never
     regresses to "no segmentation at all".
"""

from __future__ import annotations

import os

# rembg's foreground must land inside this fraction of the frame to be believed.
# Outside it the model has almost certainly returned all-or-nothing, which is
# worse than the geometric fallback.
_REMBG_MIN_FG = 0.005
_REMBG_MAX_FG = 0.97
# U2-Net emits a soft saliency matte, and the 50% level of that ramp sits OUTSIDE
# the true object edge — thresholding at 128 fattened every shape by roughly
# 0.4mm per side, which silently pushed a 3.6mm satin bar over the 4mm
# satin/tatami boundary and reclassified it as a fill. Measured on that bar
# (true width 3.60mm): alpha>128 → 4.45mm · >192 → 4.14mm · >224 → 3.82mm.
# A conservative mask is also the right bias here: colour clustering inside the
# mask can recover a slightly under-included edge, but nothing trims an
# over-included one.
_REMBG_ALPHA = 224

# Border flood-fill tolerance, per channel, in 0-255 units. Loose enough to walk
# a smooth gradient or film grain, tight enough to stop at a real design edge
# (the low-contrast fixture's subject sits ~27 units from its backdrop).
_FLOOD_TOL = 12

_DISABLE_ENV = "STITCHIQ_DISABLE_REMBG"


def _rembg_mask(data: bytes):
    """U2-Net foreground mask, or None if unavailable/implausible."""
    if os.environ.get(_DISABLE_ENV):
        return None
    try:
        import io

        import numpy as np
        from PIL import Image
        from rembg import remove
    except Exception:  # noqa: BLE001 - optional dependency absent
        return None
    try:
        session = _rembg_session()
        if session is None:
            return None
        cut = remove(data, session=session)
        alpha = np.array(Image.open(io.BytesIO(cut)).convert("RGBA"))[:, :, 3]
    except Exception:  # noqa: BLE001 - model download/inference failure must not break digitizing
        return None
    mask = (alpha > _REMBG_ALPHA).astype("uint8") * 255
    frac = float((mask > 0).mean())
    if not (_REMBG_MIN_FG <= frac <= _REMBG_MAX_FG):
        return None  # implausible → let the geometric tier decide
    return mask


_SESSION = None
_SESSION_TRIED = False


def _rembg_session():
    """Cache the ONNX session — construction downloads/loads a ~176MB model."""
    global _SESSION, _SESSION_TRIED
    if _SESSION_TRIED:
        return _SESSION
    _SESSION_TRIED = True
    try:
        from rembg import new_session

        _SESSION = new_session("u2net", sess_options=_deterministic_session_options())
    except Exception:  # noqa: BLE001 - no network / no model cache
        _SESSION = None
    return _SESSION


def _deterministic_session_options():
    """ONNX pinned to one thread and sequential execution, or None if unavailable.

    REPRODUCIBLE INFERENCE, ON PURPOSE. Every one of the ten bench fixtures takes
    the rembg path — measured, not assumed — so the learned segmentation decides
    the foreground for the whole corpus, and CP1 already established that a
    customer re-running one upload must get one product. Left at ONNX's defaults,
    the matte is computed with multi-threaded reductions whose ORDER is not
    guaranteed, so bit-identical output is a property of the machine's load
    rather than of the code.

    It was NOT observed to vary: nine digitizes of one fixture — three on an idle
    box, six during a concurrent full test suite, all in separate processes —
    produced one stitch hash. This pins the guarantee anyway, because "did not
    vary on this box today" is not the same claim as "cannot vary".

    MEASURED FREE. Pinning changes nothing about the answer, only its
    reproducibility: the foreground masks for 03, 01 and 08 are byte-identical
    with and without it (hashes 022849c6…, ea356a5c…, a99c9226…). Had they
    differed this would have been a stream-altering change needing a full re-pin,
    which is why it was measured before being adopted rather than after.

    Returns None when onnxruntime cannot be imported, so the caller falls back to
    rembg's own default rather than losing segmentation entirely.
    """
    try:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return opts
    except Exception:  # noqa: BLE001 - fall back to rembg's default session
        return None


def _flood_mask(img):
    """Foreground = whatever the background flood-fill could not reach.

    Region-grows from every border pixel with a per-channel tolerance. A smooth
    gradient backdrop is connected and slowly varying, so it is absorbed; a
    shape enclosed by the subject is not reachable from the border and stays
    foreground even when it is the exact colour of the backdrop.
    """
    import cv2
    import numpy as np

    h, w = img.shape[:2]
    # cv2.floodFill needs a mask 2px larger than the image.
    filled = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    lo = up = (_FLOOD_TOL,) * 3
    work = img.copy()

    step = max(1, min(h, w) // 64)  # seed along the border, not every pixel
    seeds = (
        [(x, 0) for x in range(0, w, step)]
        + [(x, h - 1) for x in range(0, w, step)]
        + [(0, y) for y in range(0, h, step)]
        + [(w - 1, y) for y in range(0, h, step)]
    )
    for sx, sy in seeds:
        if filled[sy + 1, sx + 1]:
            continue  # already absorbed by an earlier seed
        cv2.floodFill(work, filled, (sx, sy), 0, lo, up, flags)

    background = filled[1:-1, 1:-1] > 0
    fg = (~background).astype(np.uint8) * 255
    # Close pinholes (anti-aliased edges leave speckle) without eating detail.
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return fg


def _corner_mask(img):
    """v1 behaviour, kept as the final fallback: colour-distance from the
    average corner pixel. Global and location-blind — see the module docstring
    for why this is last, not first."""
    import numpy as np

    corners = np.array(
        [img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]], dtype=np.float32
    ).mean(axis=0)
    dist = np.linalg.norm(img.astype(np.float32) - corners, axis=2)
    return (dist >= 40.0).astype(np.uint8) * 255


# A component U2-Net dropped is reclaimed when it is at least this far (in BGR
# distance) from the substrate colour — i.e. unmistakably ink rather than a
# shadow or a compression artefact. Same threshold family as _corner_mask's 40.
#
# ── SETTLED 2026-08-27: THERE IS NO AXIS. Queued for a perceptual metric. ─────
#
# 60.0 does not express a fixed perceptual criterion, and the reason is stronger
# than "it varies by garment". Held at a FIXED 60-BGR distance, dE2000 varies
# 2.77x-3.46x purely from the DIRECTION of the step, at every luminance from 0.7
# to 255. The between-substrate spread of the medians is only 1.4x.
#
# TWO WRONG ANSWERS WERE PROPOSED BEFORE THAT ONE, and both are recorded because
# each looked like the finding at the time:
#
#   * saturation — extrapolated from the substrate gate's BGR/dE ratios (6.34
#     near black, 4.58 near white, ~2.0 saturated), predicting coloured garments
#     as the strict end at roughly threefold. The MAGNITUDE was right, the axis
#     was not.
#   * luminance — my own reading of the field survey, which found dE 7.4 at luma
#     255 rising to 20.4 at luma 12 and called it monotone in garment tone. It is
#     not: those field values sit at different points WITHIN each substrate's own
#     range (7.4-11.0 against that substrate's minimum of 7.27; 19.5 against its
#     median of 18.95), so the trend describes which artwork each fixture happens
#     to carry, not the garment. A survey of real pixels cannot separate the two;
#     only a controlled sweep at fixed distance can, and it was the CTO's.
#
# WHY THIS COMPLETES THE CASE WITHOUT NEW MATERIAL. If direction alone moves the
# criterion 3x at a single substrate, then ONE FIXTURE DEMONSTRATES IT and no
# comparison between garments is needed. The argument is the same invariance
# argument that carried SUBSTRATE_DELTA to CIEDE2000: a Euclidean-BGR constant
# cannot express a perceptual criterion anywhere in the space.
#
# CONSEQUENCE, and note the SIGN: this is the opposite error from the substrate
# gate. That one sewed invisible thread; this one DISCARDS VISIBLE ARTWORK the
# matte already dropped, on whichever side of the space the step happens to run.
#
# NOT MOVED HERE, deliberately — not in the same tranche as the legibility
# metric. What the intake ask (corpus_real/README.md §2c, tone-on-tone artwork
# on a dark garment) still buys is the narrower question of CONSEQUENCE: whether
# the current constant produces a WRONG VERDICT on real artwork. That is no
# longer a blocker on the change, only on knowing what the change is worth.
_INK_DELTA = 60.0
# ...and at least this share of the frame, so JPEG speckle and stray pixels are
# not promoted into objects. 0.02% of a 900x900 frame is ~160px: far below a
# 8mm letter, far above noise.
_INK_MIN_AREA_FRAC = 0.0002
# ...and NO MORE than this share, which is what separates a missed detail from a
# missed background. Measured on the case that motivated the rule and on the two
# fixtures that must not regress:
#   wordmark under a logo mark   0.29% / 0.14% / 0.12% of frame
#   fixture 09 photographic bg   9.19% / 6.94%
#   fixture 03 gradient bg      11.21%
# 2% sits ~7x above the largest real detail and ~3.5x below the smallest true
# background. Rationale: U2-Net reliably finds LARGE salient regions, so a large
# area it excluded was excluded on purpose; only small pieces are its blind spot.
_INK_MAX_AREA_FRAC = 0.02
# A larger cap for components that do NOT touch the frame border (v2 Part 27).
# The 2% cap was calibrated against photographic backgrounds — but measured,
# every one of those touches the border (fixture 09's two candidates, 6.94% and
# 9.19%, both do; fixture 03's gradient likewise), because a background by
# nature runs to the frame edge. A dropped ARTWORK element floats free: the
# peacock patch's entire left branch-with-flowers came back as one detached
# 5.90% component, border-clear, and the 2% cap silently deleted it — the
# Part 22 class of loss at a bigger size. Border contact is the principled
# discriminator; the raised cap only applies when it is absent.
_INK_MAX_AREA_FRAC_INTERIOR = 0.08
# An ATTACHED missed component is normally the matte's own edge being a pixel
# tight (Part 22 measured reclaiming that fringe: fixture 05 lost 0.5 interior
# and gained 2.2 spill for nothing). But "attached" also describes a real
# element the subject touches — the peacock patch's branch, which the bird
# STANDS ON, came back as a 13k-px attached component and was refused. A matte
# edge fringe is inherently THIN (1–2px); a real element has body. Attached
# components at least this thick (max inscribed radius, px) are reclaimable.
_ATTACHED_MIN_THICK_PX = 4.0
# The rembg matte must cover at least this share of strong-ink pixels to be
# trusted (v2 Part 32) — below it, the matte has found something other than the
# artwork. Calibrated against every fixture, not hoped about:
#   corpus recalls: 0.407 (fixture 09 — its photographic backdrop counts as
#   "ink" by colour distance, so a low-but-real recall is CORRECT there),
#   0.709 (fixture 03), 0.92-1.00 (the other eight).
#   the failure this gate exists for: 0.004 — the neckline design on black,
#   where U2-Net kept the empty neck OPENING as the subject and discarded
#   every flower.
# 0.2 sits far under the legitimate minimum and 50x above the failure. A first
# draft used 0.5 and the calibration run itself caught it kicking fixture 09
# off the rembg tier — the gate would have caused the regression it guards
# against.
_MATTE_MIN_INK_RECALL = 0.2
# v2 Part 34 — the PARTIAL matte. A full-bleed neckline panel produced a matte
# with ink recall 0.203: one point above the floor, yet keeping an arbitrary
# diagonal fragment (11.5% of frame against 40.6% ink). A fixed floor cannot
# split 0.203 (failure) from 0.407 (fixture 09, legitimate) with any safety, so
# the decision is comparative instead: when the matte misses over half the ink
# AND the classical flood tier explains nearly all of it with a sane foreground
# fraction, the flood tier is the better hypothesis and wins. Calibration
# (matte recall / flood ink recall): failures 0.203/1.000 and 0.004/0.998 both
# reroute; fixture 09 at 0.407/0.656 keeps its matte because flood CANNOT
# explain its ink (margin 0.294 on that side, 0.297 on the failure side); every
# other input has matte recall >= 0.709 and never reaches the comparison.
_MATTE_COMPARE_RECALL = 0.5   # below this, the matte must beat the flood tier
_FLOOD_EXPLAINS_INK = 0.95    # flood recall needed to overrule the matte
# A reclaim candidate within this many pixels of the kept mask counts as that
# mask's own edge, not a separate missed element.
_ATTACHED_GAP_PX = 3


def _reclaim_ink(img, mask):
    """Add back flat-graphic regions the neural matte discarded (v2 Part 22).

    U2-Net is trained to find the photographic SUBJECT, so on a logo it keeps
    the mark and silently deletes everything it reads as surrounding decoration
    — measured on a new emblem: the wordmark under the mark came back with
    **zero** foreground pixels, so the company name simply never reached the
    digitizer. That is the single most common logo layout there is.

    Reclaiming is deliberately conservative: only connected components that are
    strongly non-substrate in colour AND big enough to sew are restored, so a
    genuine photographic background (fixture 09) stays out. Returns a new mask;
    the input is not modified.
    """
    import cv2
    import numpy as np

    substrate = np.array(
        [img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]], dtype=np.float32
    ).mean(axis=0)
    ink = (np.linalg.norm(img.astype(np.float32) - substrate, axis=2) >= _INK_DELTA)
    missed = (ink & (mask == 0)).astype(np.uint8)
    if not missed.any():
        return mask
    n, labels, stats, _c = cv2.connectedComponentsWithStats(missed, connectivity=8)
    frame = img.shape[0] * img.shape[1]
    min_area = max(16, int(_INK_MIN_AREA_FRAC * frame))
    max_area = int(_INK_MAX_AREA_FRAC * frame)
    # Only components DETACHED from what the matte already kept are reclaimed.
    # A wholly-missed element (the wordmark below a mark) sits well clear of the
    # subject; a component touching the existing mask is the matte's own edge
    # being a pixel tight, and re-adding it just fattens shapes and adds spill
    # (measured: reclaiming attached fringe cost fixture 05 -0.5 interior and
    # +2.2 spill for no recovered content).
    near = cv2.dilate(mask, np.ones((2 * _ATTACHED_GAP_PX + 1,) * 2, np.uint8))
    ih, iw = img.shape[:2]
    max_area_interior = int(_INK_MAX_AREA_FRAC_INTERIOR * frame)
    out = mask.copy()
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        x, y, w, h = (stats[i, k] for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                            cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        touches_border = x == 0 or y == 0 or x + w >= iw or y + h >= ih
        cap = max_area if touches_border else max_area_interior
        if not (min_area <= area <= cap):
            continue
        comp = labels == i
        if near[comp].any():
            # Attached: reclaim only if the component has real body — a matte
            # edge fringe never does.
            comp_u8 = comp.astype(np.uint8)
            thickness = float(cv2.distanceTransform(comp_u8, cv2.DIST_L2, 5).max())
            if thickness < _ATTACHED_MIN_THICK_PX:
                continue
        out[comp] = 255
    return out


def foreground_mask(img, data: bytes | None = None) -> tuple[object, str]:
    """Return ``(mask, method)``: uint8 mask (255 = foreground) + which tier won.

    ``img`` is BGR at working resolution; ``data`` is the original encoded bytes
    (rembg wants an encoded image). The mask is always returned at ``img``'s
    resolution.
    """
    import cv2

    h, w = img.shape[:2]
    if data is not None:
        mask = _rembg_mask(data)
        if mask is not None:
            if mask.shape[:2] != (h, w):
                mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
            # Matte plausibility gate (v2 Part 32). U2-Net finds the
            # PHOTOGRAPHIC SUBJECT, and on a neckline design on black it decided
            # the subject was the empty neck OPENING — it kept 15.6% of the
            # frame, almost none of it ink, and discarded every flower.
            # `_reclaim_ink` could not repair that: the missed embroidery was
            # one 35%-of-frame border-touching component, which both area caps
            # correctly refuse. So the matte itself is audited against the ink
            # evidence: if it covers less than half of the strongly-non-substrate
            # pixels, it is not segmenting THIS kind of image, and the classical
            # tiers (built exactly for uniform-substrate artwork) take over.
            import numpy as np

            substrate = np.array(
                [img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]], dtype=np.float32
            ).mean(axis=0)
            ink = np.linalg.norm(img.astype(np.float32) - substrate, axis=2) >= _INK_DELTA
            n_ink = int(ink.sum())
            matte_ok = n_ink < 64 or (
                (ink & (mask > 0)).sum() >= _MATTE_MIN_INK_RECALL * n_ink
            )
            if matte_ok and n_ink >= 64:
                # Partial-matte comparison (v2 Part 34): a matte that misses
                # over half the ink only survives if the flood tier cannot
                # explain that ink either — see the calibration note above.
                recall = (ink & (mask > 0)).sum() / n_ink
                if recall < _MATTE_COMPARE_RECALL:
                    try:
                        flood = _flood_mask(img)
                        frac = float((flood > 0).mean())
                        if (
                            _REMBG_MIN_FG <= frac <= _REMBG_MAX_FG
                            and (ink & (flood > 0)).sum() >= _FLOOD_EXPLAINS_INK * n_ink
                        ):
                            return flood, "floodfill"
                    except Exception:  # noqa: BLE001, S110 - comparison is best-effort
                        pass
            if matte_ok:
                return _reclaim_ink(img, mask), "rembg"

    try:
        mask = _flood_mask(img)
        frac = float((mask > 0).mean())
        if _REMBG_MIN_FG <= frac <= _REMBG_MAX_FG:
            return mask, "floodfill"
    except Exception:  # noqa: BLE001 - never let segmentation break digitizing
        pass

    return _corner_mask(img), "corner"


__all__ = ["foreground_mask"]
