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
            return mask, "rembg"

    try:
        mask = _flood_mask(img)
        frac = float((mask > 0).mean())
        if _REMBG_MIN_FG <= frac <= _REMBG_MAX_FG:
            return mask, "floodfill"
    except Exception:  # noqa: BLE001 - never let segmentation break digitizing
        pass

    return _corner_mask(img), "corner"


__all__ = ["foreground_mask"]
