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


def _unsupported_glyphs(text: str, font) -> list[str]:
    """Characters the font renders as its .notdef "tofu" box (or not at all).

    PIL gives no cmap access, so compare each character's rendering against the
    rendering of a permanently-unassigned codepoint (U+0378): identical bitmaps
    mean the font substituted .notdef — the character has no real glyph and would
    digitize into a garbage rectangle of stitches.
    """
    from PIL import Image, ImageDraw

    def render(s: str) -> bytes:
        img = Image.new("L", (300, 300), 0)
        ImageDraw.Draw(img).text((30, 30), s, font=font, fill=255)
        return img.tobytes()

    try:
        notdef = render("\u0378")  # unassigned codepoint → guaranteed .notdef
    except Exception:  # noqa: BLE001 - detection is best-effort; never block rendering
        return []
    bad: list[str] = []
    for ch in dict.fromkeys(text):
        if ch.isspace():
            continue
        try:
            if render(ch) == notdef:
                bad.append(ch)
        except Exception:  # noqa: BLE001 - a char PIL cannot render at all
            bad.append(ch)
    return bad


# Text is rasterised at this PIL font size; the resulting ink height (px) maps onto
# height_mm, so px-per-mm for spacing conversion is (ink_px_height / height_mm).
_RENDER_FONT_PX = 160
_TEXT_MARGIN_PX = 12  # white border around the rendered text bitmap


def _compose_text_image(text: str, font, letter_spacing_mm: float, height_mm: float):
    """Rasterise ``text`` → (white-bg RGB image, ink pixel height).

    ``letter_spacing_mm == 0`` runs the original single-draw path unchanged
    (the font's own kerning applies); non-zero tracking draws per character.
    """
    from PIL import Image, ImageDraw

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = max(right - left, 1), max(bottom - top, 1)
    m = _TEXT_MARGIN_PX
    if letter_spacing_mm == 0:
        # Measure, then render tightly cropped with a small margin.
        img = Image.new("RGB", (tw + 2 * m, th + 2 * m), "white")
        ImageDraw.Draw(img).text((m - left, m - top), text, font=font, fill="black")
        return img, th
    # Tracking mm→px uses the same scale that later maps the render back to mm
    # (ink is th px tall and will sew at height_mm).
    return _compose_tracked(text, font, letter_spacing_mm * th / height_mm, (left, top), th)


def _compose_tracked(text: str, font, spacing_px: float, origin: tuple[int, int], th: int):
    """Per-character draw: each glyph advances by its ``textlength`` + ``spacing_px``.

    Drawn oversized on a dark 'L' canvas, cropped to ink, then re-margined — so
    negative tracking (glyphs pulled together, possibly overlapping) cannot clip.
    """
    from PIL import Image, ImageDraw, ImageOps

    left, top = origin
    m = _TEXT_MARGIN_PX
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    advances = [probe.textlength(ch, font=font) for ch in text]
    offsets: list[float] = []
    x = 0.0
    for adv in advances:
        offsets.append(x)
        x += adv + spacing_px
    shift = max(0.0, -min(offsets))  # keep negative-tracked glyphs on-canvas
    # th of slack past the last offset covers any right-side-bearing overshoot.
    w = int(4 * m - left + shift + max(offsets) + max(advances) + th)
    canvas = Image.new("L", (max(w, 1), th + 4 * m), 0)
    draw = ImageDraw.Draw(canvas)
    for ch, off in zip(text, offsets):
        draw.text((2 * m - left + shift + off, 2 * m - top), ch, font=font, fill=255)
    box = canvas.getbbox()
    if box is None:
        raise ValueError(f"Text {text!r} rendered no ink")
    ink = ImageOps.invert(canvas.crop(box)).convert("RGB")
    img = Image.new("RGB", (ink.width + 2 * m, ink.height + 2 * m), "white")
    img.paste(ink, (m, m))
    return img, max(box[3] - box[1], 1)


def generate_lettering(
    text: str,
    height_mm: float = 20.0,
    fabric_type: str = "cotton",
    font_path: str | None = None,
    letter_spacing_mm: float = 0.0,
) -> Design:
    """Render ``text`` and digitize it into an embroidery Design.

    ``letter_spacing_mm`` adds (negative: removes) tracking between characters;
    0 keeps the classic single-draw rendering with the font's native kerning.
    """
    from PIL import ImageFont

    text = (text or "").strip()
    if not text:
        raise ValueError("Text is empty")
    height_mm = max(5.0, min(float(height_mm), 100.0))

    try:
        font = ImageFont.truetype(find_font(font_path), size=_RENDER_FONT_PX)
    except OSError as exc:  # exists on disk but is not a decodable font
        raise ValueError(f"Cannot load font: {exc}") from exc
    bad = _unsupported_glyphs(text, font)
    if bad:
        raise ValueError(
            f"Unsupported characters for lettering: {' '.join(bad)!r} — the font has no glyphs for them"
        )

    img, th = _compose_text_image(text, font, letter_spacing_mm, height_mm)
    design = _digitize_text_image(img, th, text, height_mm, fabric_type)
    design.name = f'Text "{text}"'
    for stop in design.color_stops:
        stop.thread_name = "Lettering"
    return design


def _digitize_text_image(img, th: int, text: str, height_mm: float, fabric_type: str) -> Design:
    """Digitize the rendered bitmap at the scale that sews ``th`` px as ``height_mm``."""
    # Choose a hoop so the digitizer's 90%-of-hoop scaling yields the requested
    # physical letter height (text is th of ih pixels tall).
    iw, ih = img.size
    mm_per_px = height_mm / th
    hoop_w = iw * mm_per_px / 0.9
    hoop_h = ih * mm_per_px / 0.9
    hoop = f"{max(hoop_w, 1):.1f}x{max(hoop_h, 1):.1f}"

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    # Letters carry meaningful sub-4mm² details (the dot on 'i'/'j', accents,
    # punctuation) that the image digitizer's speck filter would drop — keep them.
    # text_mode routes each glyph through skeleton-guided satin: columns run
    # ACROSS the stroke, stepping along its medial axis, with the column width
    # following the local stroke width. Filling a glyph's silhouette with
    # horizontal tatami rows is what made machine lettering read as blocky.
    design = digitize_image(
        buf.getvalue(), fabric_type, hoop, max_colors=2, min_region_mm2=0.5, text_mode=True
    )
    if design.stitch_count == 0 or not design.objects:
        raise ValueError(f"Text {text!r} produced no stitchable shapes (unsupported glyphs, or too small)")
    return design
