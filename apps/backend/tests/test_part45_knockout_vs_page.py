"""Knocked-out artwork is not the page (v2 Part 45, R011).

Part 41 made a substrate-coloured cluster never stitch on raster input, which was
right for the case it was measured on — a photograph of a black garment, where
the cloth showing between the design's elements was being sewn in black thread.

It was applied to flat artwork too, and there the "substrate" is the page. On the
bench's fixture 02 the white wordmark sits inside a green card on a white page, so
it matched and the whole wordmark was deleted: 31 stitches and a colour stop, with
every coverage metric improving because coverage is scored against the objects
that survive.

The rule now keys on the input class, and these tests pin all three behaviours it
has to get right at once. They are the both-sides check whose absence let the
original defect through.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.digitizer.colordiff import bgr_ciede2000
from app.services.digitizer import (
    SUBSTRATE_DE2000,
    SUBSTRATE_ENCLOSED_MAX_MM2,
    SUBSTRATE_ENCLOSED_MAX_SHARE,
    _border_color,
    _interior_texture,
    digitize_image,
)

RNG_SEED = 20260728


def _png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _digitize(img, colors: int, hoop: str = "130x180"):
    cv2.setRNGSeed(RNG_SEED)
    return digitize_image(_png(img), "cotton", hoop, max_colors=colors)


def _card_with_knocked_out_type():
    """Small white bars knocked out of a solid card, on a white page — artwork.

    Sized like real type rather than one big slab: each bar is a few mm2 at the
    hoop this is digitized to, which is the side of the threshold knocked-out type
    actually falls on. One large slab would be dropped, correctly.
    """
    img = np.full((600, 600, 3), 255, np.uint8)
    cv2.rectangle(img, (90, 140), (510, 460), (75, 90, 15), -1)  # solid card
    for i in range(6):
        x = 150 + i * 55
        cv2.rectangle(img, (x, 290), (x + 34, 340), (255, 255, 255), -1)
    return img


def _ring_on_a_page():
    """An outline ring on a white page — the interior is page, not artwork."""
    img = np.full((600, 600, 3), 255, np.uint8)
    cv2.circle(img, (300, 300), 220, (55, 35, 25), 26)
    return img


def _cloth_photo():
    """The real black neckline panel — the photograph Part 41 was measured on.

    A synthetic stand-in was tried and rejected: `_interior_texture` samples only
    pixels far from the corner substrate, so generated noise on black scores 0.0
    and would have read as flat artwork. The committed corpus image is the honest
    fixture for the case this rule exists to protect.
    """
    path = (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "corpus100"
            / "A02_real_neckline_black.png")
    return cv2.imread(str(path))


def _stop_hexes(design) -> set[str]:
    return {s.hex.lower() for s in design.color_stops}


def _closest_stop_to(design, bgr) -> float:
    """Smallest PERCEPTUAL distance from any colour stop to a BGR colour.

    Euclidean BGR until 2026-08-26, when the substrate gate itself became
    CIEDE2000. Four assertions in this file compare against the gate's constant,
    and a comparison in one space against a threshold in another is meaningless
    — so the space moved with the gate.

    THE LIMIT OF EVERY ASSERTION BELOW, stated once here: a test that reads the
    same constant as the gate can catch the gate being BYPASSED, never the gate
    being WRONG. Both sides move together by construction. `test_part41`'s
    docstring records what that cost — it passed on A02 while A02 sewed 4,638
    stitches of black on black — and the assertion that does NOT share a gate
    constant lives in `tests/test_substrate_gate.py`.
    """
    out = []
    for s in design.color_stops:
        h = s.hex.lstrip("#")
        out.append(bgr_ciede2000(
            (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)), bgr))
    return min(out) if out else float("inf")


def test_flat_art_keeps_type_knocked_out_of_a_solid_shape():
    """The Part 41 regression, in miniature: this bar must be stitched."""
    design = _digitize(_card_with_knocked_out_type(), 3, hoop="40x40")
    assert _closest_stop_to(design, (255, 255, 255)) < SUBSTRATE_DE2000, (
        f"the knocked-out bar lost its thread colour; stops are {_stop_hexes(design)}"
    )


def test_flat_art_does_not_stitch_the_page_inside_an_outline_ring():
    """The counter-case that a naive enclosure test gets wrong.

    An early version of this fix kept every enclosed substrate-coloured region and
    filled fixture 04's ring with 176 white stitches on white fabric. Enclosure
    alone is not the discriminator; size is what separates a knockout from a page.
    """
    design = _digitize(_ring_on_a_page(), 2, hoop="100x100")
    assert _closest_stop_to(design, (255, 255, 255)) >= SUBSTRATE_DE2000, (
        f"the page inside the ring was stitched; stops are {_stop_hexes(design)}"
    )


def test_a_photograph_of_cloth_still_never_stitches_the_cloth():
    """Part 41's guarantee, which this change must not weaken.

    The instruction behind it — "we never do the thread for background, it's a
    black cloth" — applies to every enclosed region on a garment photo, including
    the gaps between elements that look exactly like knocked-out detail.
    """
    art = _cloth_photo()
    assert _interior_texture(art) >= 6.0, "this fixture must read as a photograph"
    design = _digitize(art, 6)
    substrate = _border_color(art)
    assert _closest_stop_to(design, substrate) >= SUBSTRATE_DE2000, (
        f"cloth-coloured thread on a garment photo; stops are {_stop_hexes(design)}"
    )
    assert design.stitch_count > 0, "the design itself must still sew"


def test_the_thresholds_separate_the_measured_cases_with_margin():
    """The numbers the rule rests on, so a future edit cannot quietly narrow them.

    Measured per enclosed substrate-coloured component:
      fixture 02 wordmark glyphs  max 17.6 mm2, max 0.33% of foreground -> keep
      fixture 04 ring hub             97.6 mm2,          2.1%           -> drop
      fixture 04 ring interiors                     32.5% / 54.7%       -> drop
    """
    assert SUBSTRATE_ENCLOSED_MAX_MM2 > 17.6 * 2, "too tight above the wordmark glyphs"
    assert SUBSTRATE_ENCLOSED_MAX_MM2 < 97.6 / 2, "too loose below fixture 04's hub"
    assert SUBSTRATE_ENCLOSED_MAX_SHARE > 0.0033 * 10, "too tight above the wordmark"
    assert SUBSTRATE_ENCLOSED_MAX_SHARE < 0.325 / 2, "too loose below the ring interior"


@pytest.mark.parametrize("fixture,colors,hoop,must_keep", [
    ("02_logo_fine_text_3color", 3, "130x180", True),
    ("04_thin_line_outline", 2, "100x100", False),
])
def test_the_real_bench_fixtures_land_on_the_right_side(fixture, colors, hoop, must_keep):
    """Same two cases on the actual artwork, not a synthetic stand-in."""
    art = (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "quality_bench"
           / f"{fixture}.png").read_bytes()
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(art, "cotton", hoop, max_colors=colors)
    near_white = _closest_stop_to(design, (255, 255, 255)) < SUBSTRATE_DE2000
    assert near_white is must_keep, (
        f"{fixture}: expected page-coloured thread present={must_keep}, "
        f"got stops {_stop_hexes(design)}"
    )
