"""Arc-baseline composition (`_compose_arc_image`) — Lettering engine v1.

Composition only: wiring arc mode into ``generate_lettering`` is a separate step,
so these tests drive the private helper directly with a font loaded at the arc
render size.
"""

from __future__ import annotations

import pytest

from app.services import lettering as lt
from app.services.lettering import find_font

try:
    find_font()
    HAVE_FONT = True
except ValueError:
    HAVE_FONT = False

pytestmark = pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")

_HEIGHT_MM = 20.0


def _arc_font():
    from PIL import ImageFont

    return ImageFont.truetype(find_font(None), size=lt._ARC_RENDER_FONT_PX)


def _straight_font():
    from PIL import ImageFont

    return ImageFont.truetype(find_font(None), size=lt._RENDER_FONT_PX)


def _ink_height(img) -> int:
    """Ink extent of a white-bg RGB composition (the margin is not ink)."""
    return img.height - 2 * lt._TEXT_MARGIN_PX


def test_arc_image_has_ink_and_is_wider_than_tall():
    from PIL import ImageOps

    img, ref_h = lt._compose_arc_image("CURVED", _arc_font(), 0.0, _HEIGHT_MM, 40.0)
    assert ImageOps.invert(img.convert("L")).getbbox() is not None, "arc image is blank"
    assert img.width > img.height, (img.size,)
    assert ref_h > 0


def test_arc_reference_height_is_the_straight_ink_height():
    """ref_ink_height_px must be the straight `th`, so mm scaling matches straight mode."""
    font = _arc_font()
    _straight, straight_th = lt._compose_text_image("CURVED", font, 0.0, _HEIGHT_MM)
    _arc, arc_ref = lt._compose_arc_image("CURVED", font, 0.0, _HEIGHT_MM, 40.0)
    assert arc_ref == straight_th


def test_arc_is_taller_than_the_straight_composition():
    arc, _ref = lt._compose_arc_image("CURVED", _arc_font(), 0.0, _HEIGHT_MM, 40.0)
    straight, _th = lt._compose_text_image("CURVED", _straight_font(), 0.0, _HEIGHT_MM)
    assert arc.height > straight.height
    # Same-font comparison: bending must add vertical extent on its own, not just
    # because arc mode rasterises at a larger font size.
    same_font, _th2 = lt._compose_text_image("CURVED", _arc_font(), 0.0, _HEIGHT_MM)
    assert arc.height > same_font.height * 2


def test_radius_below_letter_height_rejected():
    with pytest.raises(ValueError, match="at least the letter height"):
        lt._compose_arc_image("CURVED", _arc_font(), 0.0, _HEIGHT_MM, 10.0)


def test_text_too_long_for_radius_rejected():
    with pytest.raises(ValueError, match="too small"):
        lt._compose_arc_image("ABCDEFGHIJKLMNOP", _arc_font(), 0.0, _HEIGHT_MM, 25.0)


def test_letter_spacing_widens_the_arc():
    font = _arc_font()
    tight, _a = lt._compose_arc_image("ARC", font, 0.0, _HEIGHT_MM, 100.0)
    loose, _b = lt._compose_arc_image("ARC", font, 3.0, _HEIGHT_MM, 100.0)
    assert loose.width > tight.width


def test_huge_radius_degenerates_toward_straight():
    font = _arc_font()
    arc, _ref = lt._compose_arc_image("CURVED", font, 0.0, _HEIGHT_MM, 5000.0)
    straight, _th = lt._compose_text_image("CURVED", font, 0.0, _HEIGHT_MM)
    ratio = _ink_height(arc) / _ink_height(straight)
    assert 0.85 <= ratio <= 1.15, ratio


def test_whitespace_advances_without_drawing():
    """A space must widen the arc but add no ink of its own."""
    font = _arc_font()
    joined, _a = lt._compose_arc_image("AB", font, 0.0, _HEIGHT_MM, 100.0)
    spaced, _b = lt._compose_arc_image("A B", font, 0.0, _HEIGHT_MM, 100.0)
    assert spaced.width > joined.width
