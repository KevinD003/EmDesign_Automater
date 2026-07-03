"""Lettering engine v1 (spec §4.10): text → stitches.

Renders the text with a system TrueType font (PIL) and feeds the bitmap through the
existing auto-digitizer, so lettering output gets contours + holes (letter counters),
underlay, and is object-editable/rebuildable like any digitized design.

Honest scope: v1 produces TATAMI-filled letters with edge-walk underlay. Per-stroke
satin lettering (the classic look) needs stroke decomposition — Phase 8 territory.
PIL is imported lazily.
"""

from __future__ import annotations

import glob
import io
import os

from app.models.design import Design
from app.services.digitizer import digitize_image

# Common TTF locations, in preference order (macOS, Linux, Windows).
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_FONT_GLOBS = [
    "/System/Library/Fonts/Supplemental/*.ttf",
    "/usr/share/fonts/**/*.ttf",
]


def find_font(preferred: str | None = None) -> str:
    """Locate a usable TrueType font file; raise if none is found."""
    candidates = ([preferred] if preferred else []) + _FONT_CANDIDATES
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    for pattern in _FONT_GLOBS:
        hits = sorted(glob.glob(pattern, recursive=True))
        if hits:
            return hits[0]
    raise ValueError("No TrueType font found on this system — supply a font path")


def generate_lettering(
    text: str,
    height_mm: float = 20.0,
    fabric_type: str = "cotton",
    font_path: str | None = None,
) -> Design:
    """Render ``text`` and digitize it into an embroidery Design."""
    from PIL import Image, ImageDraw, ImageFont

    text = (text or "").strip()
    if not text:
        raise ValueError("Text is empty")
    height_mm = max(5.0, min(float(height_mm), 100.0))

    font = ImageFont.truetype(find_font(font_path), size=160)

    # Measure, then render tightly cropped with a small margin.
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = max(right - left, 1), max(bottom - top, 1)
    margin = 12
    img = Image.new("RGB", (tw + 2 * margin, th + 2 * margin), "white")
    ImageDraw.Draw(img).text((margin - left, margin - top), text, font=font, fill="black")

    # Choose a hoop so the digitizer's 90%-of-hoop scaling yields the requested
    # physical letter height (text is th of ih pixels tall).
    iw, ih = img.size
    mm_per_px = height_mm / th
    hoop_w = iw * mm_per_px / 0.9
    hoop_h = ih * mm_per_px / 0.9
    hoop = f"{max(hoop_w, 1):.1f}x{max(hoop_h, 1):.1f}"

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    design = digitize_image(buf.getvalue(), fabric_type, hoop, max_colors=2)
    if design.stitch_count == 0 or not design.objects:
        raise ValueError(f"Text {text!r} produced no stitchable shapes (unsupported glyphs, or too small)")
    design.name = f'Text "{text}"'
    for stop in design.color_stops:
        stop.thread_name = "Lettering"
    return design
