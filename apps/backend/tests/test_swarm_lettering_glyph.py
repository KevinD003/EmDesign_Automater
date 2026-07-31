"""Per-glyph rendering primitive for the upcoming arc baseline (swarm: lettering)."""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from app.services.digitizer import digitize_image
from app.services.lettering import (
    _ARC_RENDER_FONT_PX,
    _load_font,
    _render_glyph,
    find_font,
    generate_lettering,
)

try:
    find_font()
    HAVE_FONT = True
except ValueError:
    HAVE_FONT = False

pytestmark = pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")


def _ink_height(ch: str, size_px: int) -> int:
    img, _adv, _off = _render_glyph(ch, _load_font(None, size_px))
    assert img is not None
    return img.height


def test_render_glyph_returns_cropped_ink_bitmap():
    img, advance, (off_x, off_y) = _render_glyph("H", _load_font(None, _ARC_RENDER_FONT_PX))
    assert img is not None
    assert img.mode == "L"
    assert img.width > 0 and img.height > 0
    assert img.getextrema()[1] == 255  # ink is full-white on a black field
    assert advance > 0
    assert isinstance(off_x, (int, float)) and isinstance(off_y, (int, float))


def test_arc_render_size_is_three_times_the_straight_path():
    assert _ARC_RENDER_FONT_PX == 3 * 160
    ratio = _ink_height("H", _ARC_RENDER_FONT_PX) / _ink_height("H", 160)
    assert 2.5 < ratio < 3.5


def test_whitespace_yields_no_image_but_still_advances():
    img, advance, offsets = _render_glyph(" ", _load_font(None, _ARC_RENDER_FONT_PX))
    assert img is None
    assert advance > 0
    assert offsets == (0, 0)


def test_offsets_and_size_match_an_independent_rendering():
    """Crop box and offsets must agree with the same glyph drawn at a known origin."""
    size = _ARC_RENDER_FONT_PX
    font = _load_font(None, size)
    img, advance, (off_x, off_y) = _render_glyph("H", font)

    origin = 1000  # arbitrary pen origin, far from any canvas edge
    canvas = Image.new("L", (2 * origin, 2 * origin), 0)
    draw = ImageDraw.Draw(canvas)
    draw.text((origin, origin), "H", font=font, fill=255)
    left, top, right, bottom = canvas.getbbox()

    assert img is not None
    assert img.size == (right - left, bottom - top)
    assert (off_x, off_y) == (left - origin, top - origin)
    # textbbox spans the advance, so it bounds the ink crop but is wider than it.
    tb = draw.textbbox((origin, origin), "H", font=font)
    assert img.height == tb[3] - tb[1]
    assert 0 < img.width <= advance
    assert advance == pytest.approx(tb[2] - tb[0], abs=1.0)


def test_glyph_helpers_do_not_change_the_straight_lettering_path():
    """generate_lettering('HI', 20) still matches the v1 composition + pipeline.

    Body mirrors tests/test_lettering.py::test_default_path_unchanged_by_tracking_feature
    so the baseline is recomputed here rather than hard-coded per environment.
    """
    from PIL import ImageFont

    from app.services import lettering as lt

    text, height_mm = "HI", 20.0
    font = ImageFont.truetype(lt.find_font(None), size=160)

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = max(right - left, 1), max(bottom - top, 1)
    margin = 12
    old = Image.new("RGB", (tw + 2 * margin, th + 2 * margin), "white")
    ImageDraw.Draw(old).text((margin - left, margin - top), text, font=font, fill="black")

    mm_per_px = height_mm / th
    iw, ih = old.size
    hoop = f"{max(iw * mm_per_px / 0.9, 1):.1f}x{max(ih * mm_per_px / 0.9, 1):.1f}"
    buf = io.BytesIO()
    old.save(buf, format="PNG")
    baseline = digitize_image(
        buf.getvalue(), "cotton", hoop, max_colors=2, min_region_mm2=0.5, text_mode=True
    )
    assert generate_lettering(text, height_mm).stitch_count == baseline.stitch_count


def test_load_font_rejects_an_undecodable_file(tmp_path):
    bogus = tmp_path / "broken.ttf"
    bogus.write_bytes(b"not a font")
    with pytest.raises(ValueError, match="Cannot load font"):
        _load_font(str(bogus), 160)
