"""v2 Part 29 — textured-input cleanup: speck absorption and seam fill.

All gated on `is_textured`, so flat artwork (the whole bench corpus) never
reaches these paths — the stream-lock suite is the proof. Each test pins a
defect measured on the photographed peacock patch.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np

from app.services.digitizer import _absorb_specks


def test_surrounded_speck_joins_its_surroundings():
    """52 of the peacock's 128 objects were sub-40-stitch colour flecks inside
    other regions' fills — each one a trim, a lock, and visual confetti."""
    lab = np.zeros((60, 60), np.int32)
    lab[20:24, 20:24] = 1  # a ~0.4mm^2 fleck of cluster 1 inside cluster 0
    out = _absorb_specks(lab, 0.15)
    assert (out == 1).sum() == 0
    assert out[21, 21] == 0


def test_speck_between_two_regions_keeps_its_vote():
    """Absorption requires one DOMINANT neighbour: a small region wedged
    between two clusters is a real boundary feature, not noise."""
    lab = np.zeros((60, 60), np.int32)
    lab[:, 30:] = 2
    lab[28:32, 28:32] = 1  # straddles the 0|2 boundary
    out = _absorb_specks(lab, 0.15)
    assert (out == 1).sum() > 0, "a boundary-straddling element must survive"


def test_element_bigger_than_the_cap_survives():
    lab = np.zeros((80, 80), np.int32)
    lab[20:60, 20:60] = 1  # 40x40 px = 36mm^2 at 0.15mm/px — far over 3mm^2
    out = _absorb_specks(lab, 0.15)
    assert (out == 1).sum() == 40 * 40


def test_edge_speck_with_background_ring_still_absorbs():
    """The share is judged over OWNED ring pixels: a fleck at a leaf's outer
    edge has background (-1) in its ring, and counting background as a
    dissenting vote left visible flecks at every leaf edge."""
    lab = np.full((60, 60), -1, np.int32)
    lab[10:50, 10:50] = 0          # a leaf
    lab[10:13, 20:24] = 1          # fleck ON the leaf's edge; ring above is -1
    out = _absorb_specks(lab, 0.15)
    assert (out == 1).sum() == 0


def test_dark_linework_recovers_drawn_lines():
    """v2 Part 30: thin dark lines between colour fields — the outlines and
    veins a hand-digitized patch draws in stem stitch — do not survive
    quantization (a 0.5mm line quantizes into its neighbours). The black-hat
    pass recovers them from the image itself."""
    from app.services.digitizer import _dark_linework

    img = np.full((300, 300, 3), 255, np.uint8)
    import cv2
    cv2.rectangle(img, (40, 40), (260, 260), (120, 200, 120), -1)   # a leaf-green field
    cv2.line(img, (60, 150), (240, 150), (40, 40, 40), 3)           # a drawn dark vein
    cv2.line(img, (150, 60), (150, 240), (40, 40, 40), 3)
    fg = np.full((300, 300), 255, np.uint8)
    chains = _dark_linework(img, fg, 0.2)
    assert chains, "the drawn lines were not recovered"
    total = sum(
        sum(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5 for p, q in pairwise(c))
        for c in chains
    )
    assert total > 250, f"recovered only {total:.0f}px of ~360px of drawn line"


def test_dark_linework_ignores_dark_regions():
    """A dark REGION is a colour field, not drawing — the half-width cap must
    keep the tracer out of it (no spurious spine down a navy fill)."""
    import cv2

    from app.services.digitizer import _dark_linework

    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.rectangle(img, (60, 60), (240, 240), (90, 60, 30), -1)      # big navy block
    fg = np.full((300, 300), 255, np.uint8)
    chains = _dark_linework(img, fg, 0.2)
    inside = sum(
        1 for c in chains for x, y in c if 80 < x < 220 and 80 < y < 220
    )
    assert inside == 0, "the tracer drew a spine through a solid dark region"
