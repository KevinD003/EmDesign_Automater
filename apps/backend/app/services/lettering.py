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
import math
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


# Bounds response size on font-heavy systems (a full OS font dir can hold thousands).
_MAX_FONTS = 200
_FONT_EXTS = (".ttf", ".otf", ".ttc")  # formats PIL's FreeType loader accepts


def _font_files() -> list[str]:
    """Candidate font paths, in priority order (user dirs first so the cap favors them)."""
    files: list[str] = []
    # Repo fonts dir sits at <apps/backend>/fonts, two levels above this service file.
    repo_dir = os.path.join(os.path.dirname(__file__), "..", "..", "fonts")
    for root_dir in (os.environ.get("STITCHIQ_FONTS_DIR"), repo_dir):
        if not root_dir or not os.path.isdir(root_dir):  # both dirs may not exist
            continue
        for base, _dirs, names in os.walk(root_dir):
            files.extend(
                os.path.join(base, n) for n in names if n.lower().endswith(_FONT_EXTS)
            )
    files.extend(p for p in _FONT_CANDIDATES if os.path.isfile(p))
    for pattern in _FONT_GLOBS:
        files.extend(glob.glob(pattern, recursive=True))
    return files


def list_fonts() -> list[dict]:
    """Fonts usable for lettering: [{"name", "path"}, ...] sorted by display name."""
    from PIL import ImageFont

    seen: set[str] = set()
    fonts: list[dict] = []
    for path in _font_files():
        real = os.path.realpath(path)
        if real in seen or not os.path.isfile(real):
            continue
        seen.add(real)
        try:
            family, style = ImageFont.truetype(real, 12).getname()
        except OSError:  # present on disk but not a decodable font
            continue
        name = family if style in ("Regular", "Book") else f"{family} {style}"
        fonts.append({"name": name, "path": real})
        if len(fonts) >= _MAX_FONTS:
            break
    return sorted(fonts, key=lambda f: f["name"])


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

# Per-glyph rasterisation is cheap (one small bitmap per char), so arc mode renders
# at 3x the straight path's 160px to keep curve edges clean after per-glyph rotation.
_ARC_RENDER_FONT_PX = 480
# Glyph canvas = this multiple of the font size, squared: accents, descenders and
# side bearings all fit with the draw inset at 1x, so nothing can clip.
_GLYPH_CANVAS_MULT = 4
# Past this angular span the text laps around the bottom of the circle and the two
# ends collide; a full 360 deg would also make the crop meaningless.
_MAX_ARC_SPAN_DEG = 350.0

# Thread is ~0.4mm wide; below 4mm letter height, counters and strokes merge
# into unreadable stitching — reject rather than silently upsize.
_MIN_HEIGHT_MM = 4.0

# Baseline shapes the engine can lay text on; the router mirrors this as a Literal.
_BASELINES = ("straight", "arc")


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


def _load_font(path_or_none: str | None, size_px: int = _RENDER_FONT_PX):
    """Load a TrueType font at ``size_px``, or raise ValueError if it is undecodable."""
    from PIL import ImageFont

    try:
        return ImageFont.truetype(find_font(path_or_none), size=size_px)
    except OSError as exc:  # exists on disk but is not a decodable font
        raise ValueError(f"Cannot load font: {exc}") from exc


def _render_glyph(ch: str, font) -> tuple:
    """Rasterise one character → ``(image, advance_px, (offset_x, offset_y))``.

    ``image`` is an 'L' bitmap, ink 255 on black 0, cropped tight to the ink;
    ``advance_px`` is the pen advance measured before cropping; the offsets are the
    ink bbox left/top of ``ch`` drawn at the pen origin (0, 0), so a caller pastes at
    ``(pen_x + offset_x, pen_y + offset_y)``. Whitespace/inkless chars yield
    ``(None, advance_px, (0, 0))`` — advance the pen without pasting.
    """
    from PIL import Image, ImageDraw

    size = int(getattr(font, "size", _ARC_RENDER_FONT_PX))
    inset = size  # draw origin; leaves >=1 font size of slack on every side
    span = size * _GLYPH_CANVAS_MULT
    canvas = Image.new("L", (span, span), 0)
    draw = ImageDraw.Draw(canvas)
    advance = float(draw.textlength(ch, font=font))
    draw.text((inset, inset), ch, font=font, fill=255)
    # Crop to the ink, NOT to textbbox: textbbox spans the advance width, so it would
    # bake side bearings into the bitmap and skew the per-glyph rotation centre.
    box = canvas.getbbox()
    if box is None:  # whitespace, or a glyph the font renders empty
        return None, advance, (0, 0)
    return canvas.crop(box), advance, (box[0] - inset, box[1] - inset)


def _arc_layout(text: str, font, spacing_px: float, radius_px: float) -> list[tuple]:
    """Per-character ``(char, mid_angle_rad, advance_px)`` along an upward arc.

    Angles are measured from the top of the circle, positive clockwise (to the
    right). Each character owns a slot of ``advance + spacing`` and the slots are
    laid out symmetrically about the vertical, with the tracking gap split evenly
    so the ink itself stays centred.
    """
    from PIL import Image, ImageDraw

    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    advances = [float(probe.textlength(ch, font=font)) for ch in text]
    gap = spacing_px / radius_px
    span = sum(a / radius_px + gap for a in advances)
    if math.degrees(span) > _MAX_ARC_SPAN_DEG:
        raise ValueError("arc radius too small for this text — increase radius or shorten text")
    out: list[tuple] = []
    angle = -span / 2.0 + gap / 2.0  # pen angle of the first glyph
    for ch, advance in zip(text, advances):
        arc = advance / radius_px
        out.append((ch, angle + arc / 2.0, advance))
        angle += arc + gap
    return out


def _rotated_point(src_size, dst_size, point, theta: float) -> tuple[float, float]:
    """Where ``point`` lands after ``Image.rotate(-degrees(theta), expand=True)``.

    PIL rotates about the source centre and re-centres the expanded canvas, so the
    same rotation about the two centres reproduces the mapping (to within PIL's
    sub-pixel rounding of the expanded size).
    """
    a = -theta  # PIL's angle runs counter-clockwise; theta runs clockwise
    ca, sa = math.cos(a), math.sin(a)
    vx = point[0] - src_size[0] / 2.0
    vy = point[1] - src_size[1] / 2.0
    return (vx * ca + vy * sa + dst_size[0] / 2.0, -vx * sa + vy * ca + dst_size[1] / 2.0)


def _paste_arc(placed: list[tuple], th: int):
    """Union the rotated glyphs onto one canvas → (white-bg RGB image, ``th``)."""
    from PIL import Image, ImageOps

    if not placed:
        raise ValueError("Text rendered no ink")
    x0 = min(x for _g, x, _y in placed)
    y0 = min(y for _g, _x, y in placed)
    w = math.ceil(max(x + g.width for g, x, _y in placed) - x0) + 1
    h = math.ceil(max(y + g.height for g, _x, y in placed) - y0) + 1
    canvas = Image.new("L", (max(w, 1), max(h, 1)), 0)
    for glyph, x, y in placed:
        # Glyph is its own mask: overlapping neighbours union instead of blanking.
        canvas.paste(glyph, (round(x - x0), round(y - y0)), glyph)
    box = canvas.getbbox()
    if box is None:
        raise ValueError("Text rendered no ink")
    m = _TEXT_MARGIN_PX
    ink = ImageOps.invert(canvas.crop(box)).convert("RGB")
    img = Image.new("RGB", (ink.width + 2 * m, ink.height + 2 * m), "white")
    img.paste(ink, (m, m))
    return img, th


def _compose_arc_image(
    text: str, font, letter_spacing_mm: float, height_mm: float, radius_mm: float
):
    """Bend ``text`` along an upward (rainbow) arc → (white-bg RGB image, ref ink height).

    The second element is the STRAIGHT ink height of the whole string, i.e. the same
    measure the straight path hands ``_digitize_text_image`` as ``th`` — so letter
    height, not the arc's total vertical extent, is what maps onto ``height_mm``.
    """
    from PIL import Image, ImageDraw

    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    _left, top, _right, bottom = probe.textbbox((0, 0), text, font=font)
    th = max(bottom - top, 1)
    if float(radius_mm) < float(height_mm):
        raise ValueError("arc radius must be at least the letter height")
    px_per_mm = th / float(height_mm)
    radius_px = float(radius_mm) * px_per_mm
    ascent = font.getmetrics()[0]  # default anchor "la" puts the baseline here

    placed: list[tuple] = []
    for ch, theta, advance in _arc_layout(text, font, letter_spacing_mm * px_per_mm, radius_px):
        glyph, _advance, (off_x, off_y) = _render_glyph(ch, font)
        if glyph is None:  # whitespace: the slot advances, nothing is drawn
            continue
        rot = glyph.rotate(-math.degrees(theta), expand=True, resample=Image.BICUBIC)
        anchor = _rotated_point(glyph.size, rot.size, (advance / 2.0 - off_x, ascent - off_y), theta)
        # Circle centre sits radius_px BELOW the top of the arc, so the text bends up.
        placed.append(
            (
                rot,
                radius_px * math.sin(theta) - anchor[0],
                radius_px * (1.0 - math.cos(theta)) - anchor[1],
            )
        )
    return _paste_arc(placed, th)


def _compose(
    text: str,
    font,
    baseline: str,
    letter_spacing_mm: float,
    height_mm: float,
    arc_radius_mm: float | None,
):
    """Rasterise ``text`` on ``baseline`` → (white-bg RGB image, reference ink height px)."""
    if baseline == "arc":
        return _compose_arc_image(text, font, letter_spacing_mm, height_mm, float(arc_radius_mm))
    return _compose_text_image(text, font, letter_spacing_mm, height_mm)


def generate_lettering(
    text: str,
    height_mm: float = 20.0,
    fabric_type: str = "cotton",
    font_path: str | None = None,
    letter_spacing_mm: float = 0.0,
    baseline: str = "straight",
    arc_radius_mm: float | None = None,
) -> Design:
    """Render ``text`` and digitize it into an embroidery Design.

    ``letter_spacing_mm`` adds (negative: removes) tracking between characters;
    0 keeps the classic single-draw rendering with the font's native kerning.
    ``baseline='arc'`` bends the text upward (rainbow) along a circle of
    ``arc_radius_mm``, which is required in that mode and must be >= ``height_mm``.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Text is empty")
    if baseline not in _BASELINES:
        raise ValueError(f"Unknown baseline {baseline!r} — expected one of {', '.join(_BASELINES)}")
    if baseline == "arc" and arc_radius_mm is None:
        raise ValueError("arc baseline requires arc_radius_mm")
    if float(height_mm) < _MIN_HEIGHT_MM:
        raise ValueError("text below 4mm cannot be embroidered legibly")
    height_mm = min(float(height_mm), 100.0)

    # Glyph coverage is size-independent, so probe at the straight render size: the
    # detector's fixed 300px canvas would clip glyphs at the arc path's 3x size.
    font = _load_font(font_path)
    bad = _unsupported_glyphs(text, font)
    if bad:
        raise ValueError(
            f"Unsupported characters for lettering: {' '.join(bad)!r} — the font has no glyphs for them"
        )
    if baseline == "arc":
        font = _load_font(font_path, _ARC_RENDER_FONT_PX)

    img, th = _compose(text, font, baseline, letter_spacing_mm, height_mm, arc_radius_mm)
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
