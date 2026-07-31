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

        _SESSION = new_session("u2net")
    except Exception:  # noqa: BLE001 - no network / no model cache
        _SESSION = None
    return _SESSION


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
    out = mask.copy()
    for i in range(1, n):
        if not (min_area <= stats[i, cv2.CC_STAT_AREA] <= max_area):
            continue
        comp = labels == i
        if near[comp].any():
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
