"""Pre-digitizing image preparation (v2 Part 36) — the "Photoshop step".

Competitors (Hatch's image-prep, Wilcom's bitmap tools) all ship a raster
editor in front of digitizing, and for a real reason: the digitizer's colour
plan is only as good as the artwork it is handed. A JPEG shot on a phone, a
scan with a grey cast, or a logo with a busy background all digitize badly no
matter how good the stitch engine is — and every one of those is fixed by
crop / straighten / levels / posterize BEFORE quantization.

Every operation is a pure function of (image, params) so the whole chain is
deterministic and testable, and the ops compose in a fixed, documented order
(geometry first, then tone, then colour, then structure) — otherwise the same
slider values produce different results depending on click order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

# Guard rails: the editor runs server-side on user uploads, so every size is
# bounded before any allocation.
MAX_SIDE_PX = 4096
MIN_SIDE_PX = 8


@dataclass
class EditParams:
    """One full edit state. Defaults are all no-ops."""

    # geometry
    crop: tuple[float, float, float, float] | None = None  # x,y,w,h as 0..1
    rotate_deg: float = 0.0
    flip_h: bool = False
    flip_v: bool = False
    scale: float = 1.0
    # tone
    brightness: float = 0.0        # -1..1
    contrast: float = 0.0          # -1..1
    auto_levels: bool = False
    gamma: float = 1.0             # 0.2..3
    # colour
    saturation: float = 0.0        # -1..1 (-1 = greyscale)
    hue_shift: int = 0             # degrees
    # structure
    sharpen: float = 0.0           # 0..1
    denoise: float = 0.0           # 0..1
    posterize: int = 0             # 0 = off, else 2..32 levels
    remove_background: bool = False
    threshold_bw: bool = False
    extra: dict = field(default_factory=dict)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _geometry(img, p: EditParams):
    h, w = img.shape[:2]
    if p.crop:
        x, y, cw, ch = (_clamp01(v) for v in p.crop)
        x0, y0 = int(x * w), int(y * h)
        x1 = min(w, max(x0 + MIN_SIDE_PX, int((x + cw) * w)))
        y1 = min(h, max(y0 + MIN_SIDE_PX, int((y + ch) * h)))
        img = img[y0:y1, x0:x1]
    if p.flip_h:
        img = cv2.flip(img, 1)
    if p.flip_v:
        img = cv2.flip(img, 0)
    if abs(p.rotate_deg) > 1e-6:
        h, w = img.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), p.rotate_deg, 1.0)
        # Grow the canvas so rotation never crops the artwork off (a
        # straighten that silently eats a corner is worse than no straighten).
        cos, sin = abs(m[0, 0]), abs(m[0, 1])
        nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
        m[0, 2] += nw / 2 - w / 2
        m[1, 2] += nh / 2 - h / 2
        corner = tuple(int(v) for v in img[0, 0])
        img = cv2.warpAffine(img, m, (nw, nh), borderValue=corner)
    if abs(p.scale - 1.0) > 1e-3:
        s = max(0.05, min(4.0, p.scale))
        h, w = img.shape[:2]
        nw = int(max(MIN_SIDE_PX, min(MAX_SIDE_PX, w * s)))
        nh = int(max(MIN_SIDE_PX, min(MAX_SIDE_PX, h * s)))
        interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
        img = cv2.resize(img, (nw, nh), interpolation=interp)
    return img


def _tone(img, p: EditParams):
    if p.auto_levels:
        # Per-channel 1%-99% stretch: fixes scans and phone shots with a cast
        # without the hue shift a global stretch would introduce.
        out = np.empty_like(img)
        for c in range(3):
            ch = img[:, :, c]
            lo, hi = np.percentile(ch, (1.0, 99.0))
            if hi - lo < 1e-3:
                out[:, :, c] = ch
            else:
                out[:, :, c] = np.clip((ch.astype(np.float32) - lo) * 255.0 / (hi - lo), 0, 255)
        img = out
    if abs(p.brightness) > 1e-6 or abs(p.contrast) > 1e-6:
        a = 1.0 + max(-0.95, min(1.0, p.contrast))
        b = max(-1.0, min(1.0, p.brightness)) * 127.0
        img = cv2.convertScaleAbs(img, alpha=a, beta=b)
    if abs(p.gamma - 1.0) > 1e-3:
        g = max(0.2, min(3.0, p.gamma))
        lut = np.array([((i / 255.0) ** (1.0 / g)) * 255 for i in range(256)], np.uint8)
        img = cv2.LUT(img, lut)
    return img


def _colour(img, p: EditParams):
    if abs(p.saturation) > 1e-6 or p.hue_shift:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        if p.hue_shift:
            hsv[..., 0] = (hsv[..., 0] + (p.hue_shift / 2.0)) % 180.0
        if abs(p.saturation) > 1e-6:
            hsv[..., 1] *= 1.0 + max(-1.0, min(2.0, p.saturation))
        img = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
    return img


def _structure(img, p: EditParams):
    if p.denoise > 1e-6:
        d = int(3 + round(_clamp01(p.denoise) * 8)) | 1
        img = cv2.bilateralFilter(img, d, 40 + 60 * _clamp01(p.denoise), 12)
    if p.sharpen > 1e-6:
        amount = _clamp01(p.sharpen)
        blur = cv2.GaussianBlur(img, (0, 0), 1.6)
        img = cv2.addWeighted(img, 1 + amount, blur, -amount, 0)
    if p.posterize and p.posterize >= 2:
        n = max(2, min(32, int(p.posterize)))
        step = 255.0 / (n - 1)
        img = np.clip(np.round(img.astype(np.float32) / step) * step, 0, 255).astype(np.uint8)
    if p.threshold_bw:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    return img


def _remove_background(img):
    """Flatten the background to white using the app's own segmentation.

    Reuses ``segmentation.foreground_mask`` on purpose: the editor's idea of
    "background" must be the SAME one the digitizer will use, or the preview
    lies about what will be stitched.
    """
    from app.services.segmentation import foreground_mask

    ok, buf = cv2.imencode(".png", img)
    mask, _ = foreground_mask(img, buf.tobytes() if ok else None)
    out = img.copy()
    out[mask == 0] = (255, 255, 255)
    return out


def apply_edits(img, p: EditParams):
    """Apply the full chain in the documented order and return a new image."""
    if img is None or img.size == 0:
        raise ValueError("empty image")
    img = _geometry(img, p)
    img = _tone(img, p)
    img = _colour(img, p)
    if p.remove_background:
        img = _remove_background(img)
    img = _structure(img, p)
    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE_PX:
        s = MAX_SIDE_PX / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img


def suggest(img) -> dict:
    """Measured auto-prep advice — the "what should I fix?" button.

    Each suggestion states the measurement behind it so the user can disagree
    with a number rather than with an opinion.
    """
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lo, hi = np.percentile(g, (1.0, 99.0))
    contrast_span = float(hi - lo)
    lap = float(cv2.Laplacian(g, cv2.CV_64F).var())
    sat = float(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1].mean())
    colours = len(np.unique(img.reshape(-1, 3) // 16, axis=0))
    tips = []
    params = EditParams()
    if contrast_span < 160:
        tips.append(
            f"Low contrast (tonal span {contrast_span:.0f}/255) — auto-levels will "
            "separate the colours before they are quantized."
        )
        params.auto_levels = True
    if lap < 60:
        tips.append(
            f"Soft edges (detail variance {lap:.0f}) — a little sharpening helps the "
            "outline pass find real boundaries."
        )
        params.sharpen = 0.35
    if lap > 900:
        tips.append(
            f"Very noisy (detail variance {lap:.0f}) — denoise first, or the noise "
            "becomes stitch objects."
        )
        params.denoise = 0.5
    if sat < 40:
        tips.append(
            f"Nearly greyscale (mean saturation {sat:.0f}/255) — expect few thread "
            "colours; boost saturation if the original artwork had more."
        )
    if colours > 2500:
        tips.append(
            f"{colours} distinct colour cells — posterize to flatten photographic "
            "shading into stitchable blocks."
        )
        params.posterize = 8
    return {
        "measurements": {
            "contrastSpan": round(contrast_span, 1),
            "detailVariance": round(lap, 1),
            "meanSaturation": round(sat, 1),
            "colourCells": colours,
        },
        "tips": tips,
        "suggested": {
            "autoLevels": params.auto_levels,
            "sharpen": params.sharpen,
            "denoise": params.denoise,
            "posterize": params.posterize,
        },
    }
