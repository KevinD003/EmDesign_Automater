"""v2 Part 36 — thin-stroke artwork must not digitize to nothing.

Found by running a 100-design corpus: twelve designs produced ZERO stitches,
all of them thin-stroke classes (lattice trellis, hairline linework, small
lettering). Three separate defects stacked, each pinned below.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services.digitizer import digitize_image


def _png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _lattice(width_px: int = 6, size: int = 520, bg=(255, 255, 255), line=(60, 200, 220)):
    img = np.full((size, size, 3), bg, np.uint8)
    for d in range(-size, size, 120):
        cv2.line(img, (d, 0), (d + size, size), line, width_px)
        cv2.line(img, (d + size, 0), (d, size), line, width_px)
    return img


def _stitch_count(design) -> int:
    return sum(
        1 for s in design.stitches if getattr(s.command, "value", s.command) == "STITCH"
    )


def test_lattice_trellis_produces_stitches():
    """The headline failure: a lattice of ~1.5mm lines digitized to ZERO
    objects. Three causes stacked — duplicate k-means centres on a 2-colour
    image, a blend cut that removed 60% of the line pixels, and a speck filter
    measuring polygon area (0 for a thin stroke) instead of ink."""
    design = digitize_image(_png(_lattice()), "cotton", "180x130", 12)
    assert _stitch_count(design) > 0, "a stitchable lattice must not vanish"
    assert design.objects, "and it must produce real objects"


def test_two_colour_image_does_not_shatter_into_confetti():
    """A 2-colour image asked for 12 colours must not have spare centres land
    inside the anti-aliasing gradient: that shattered a 48,877px mask into
    15,641 fragments averaging 3px, every one under the speck floor."""
    design = digitize_image(_png(_lattice(width_px=14)), "cotton", "180x130", 12)
    assert _stitch_count(design) > 0
    # Only one real ink colour exists, so the plan must not invent many.
    assert len({c.hex for c in design.color_stops}) <= 3


def test_thick_artwork_is_unaffected_by_the_thin_stroke_relief():
    """The blend cut still applies where a shape can afford it — a chunky
    two-colour graphic keeps working exactly as before."""
    img = np.full((400, 400, 3), 255, np.uint8)
    cv2.circle(img, (200, 200), 150, (40, 40, 200), -1)
    cv2.rectangle(img, (60, 60), (150, 150), (30, 160, 30), -1)
    design = digitize_image(_png(img), "cotton", "100x100", 6)
    assert _stitch_count(design) > 500
    assert len(design.objects) >= 2


def test_genuinely_unstitchable_hairlines_still_warn_rather_than_pretend():
    """Honest limit: 1px lines at this size are ~0.16mm — under the thread
    itself. The right behaviour is not to invent stitches but to SAY so."""
    img = np.full((520, 520, 3), 255, np.uint8)
    for x in range(20, 500, 9):
        cv2.line(img, (x, 20), (x + 40, 500), (40, 40, 40), 1)
    design = digitize_image(_png(img), "cotton", "180x130", 12)
    if _stitch_count(design) == 0:
        assert design.warnings, "an empty result must always be explained"
        assert any("left out" in w or "detail" in w for w in design.warnings)
