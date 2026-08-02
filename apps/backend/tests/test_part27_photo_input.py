"""v2 Part 27 — photographed/textured input (the peacock patch test).

A photograph of a real sew-out exposed three defects, each pinned here:
the neural matte dropped the entire left branch (attached, thick, 5.9% of
frame — over the reclaim cap AND attached, so two rules rejected it); thread
sheen shattered solid colour areas into speckle islands; and the texture gate
initially measured at the wrong resolution, so the fix silently never ran.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services.digitizer import TEXTURE_SMOOTH_MIN, _interior_texture
from app.services.segmentation import _reclaim_ink


def test_flat_artwork_measures_untextured():
    """The corpus (flat fills) measures 0.00-4.10; the gate is 6.0. A synthetic
    flat two-colour image must sit far below it."""
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.circle(img, (150, 150), 100, (40, 40, 200), -1)
    cv2.rectangle(img, (20, 20), (90, 90), (30, 160, 30), -1)
    assert _interior_texture(img) < 1.0


def test_edge_heavy_linework_is_not_mistaken_for_texture():
    """The first metric confounded edges with texture: fixture 04's thin
    linework scored 99.2 — ranked more 'textured' than a photo of thread —
    because local stddev spikes at every edge. Interior-only sampling fixes the
    ranking; dense line art must stay below the gate."""
    img = np.full((400, 400, 3), 255, np.uint8)
    for i in range(20, 380, 12):
        cv2.line(img, (i, 20), (i, 380), (40, 40, 40), 2)
    assert _interior_texture(img) < TEXTURE_SMOOTH_MIN


def test_shaded_regions_measure_textured():
    """Per-region shading (thread sheen, photo lighting) is what the gate must
    catch: flat shapes filled with banded noise, edges intact."""
    rng = np.random.default_rng(7)
    img = np.full((300, 300, 3), 255, np.uint8)
    block = np.clip(90 + rng.normal(0, 22, (260, 260, 3)), 0, 255).astype(np.uint8)
    img[20:280, 20:280] = block
    assert _interior_texture(img) >= TEXTURE_SMOOTH_MIN


def _mask_scene():
    """A kept subject, plus one THICK attached element and one THIN attached
    fringe — the peacock's branch vs the matte's own edge."""
    img = np.full((400, 400, 3), 255, np.uint8)
    kept = np.zeros((400, 400), np.uint8)
    cv2.circle(img, (200, 200), 80, (60, 60, 160), -1)
    cv2.circle(kept, (200, 200), 80, 255, -1)
    # Thick attached element: a 24px-wide bar the subject touches (the branch).
    cv2.rectangle(img, (40, 188), (200, 212), (30, 90, 140), -1)
    # Thin attached fringe: a 2px ring hugging the kept mask's edge.
    cv2.circle(img, (200, 200), 83, (60, 60, 160), 2)
    return img, kept


def test_thick_attached_element_is_reclaimed():
    img, kept = _mask_scene()
    out = _reclaim_ink(img, kept)
    assert out[200, 60] == 255, "the branch (thick, attached) must be reclaimed"


def test_thin_attached_fringe_is_still_rejected():
    """Part 22 measured fringe reclamation costing fixture 05 -0.5 interior and
    +2.2 spill for no content. Thickness keeps that verdict."""
    img = np.full((400, 400, 3), 255, np.uint8)
    kept = np.zeros((400, 400), np.uint8)
    cv2.circle(img, (200, 200), 80, (60, 60, 160), -1)
    cv2.circle(kept, (200, 200), 80, 255, -1)
    cv2.circle(img, (200, 200), 84, (60, 60, 160), 2)  # fringe only
    out = _reclaim_ink(img, kept)
    ring = np.zeros_like(kept)
    cv2.circle(ring, (200, 200), 84, 255, 2)
    added = (out > 0) & (kept == 0) & (ring > 0)
    assert not added.any(), "a 2px matte-edge fringe must not be reclaimed"


def test_border_touching_background_is_still_rejected():
    """Fixture 09's photographic background components (6.94% and 9.19% of
    frame) both touch the border — that contact is what keeps them out now
    that the interior cap is 8%."""
    img = np.full((400, 400, 3), 255, np.uint8)
    kept = np.zeros((400, 400), np.uint8)
    cv2.circle(img, (200, 200), 60, (60, 60, 160), -1)
    cv2.circle(kept, (200, 200), 60, 255, -1)
    # A large dark region running off the frame edge: a background, not art.
    cv2.rectangle(img, (0, 0), (399, 40), (100, 60, 20), -1)
    out = _reclaim_ink(img, kept)
    assert out[20, 200] == 0, "border-touching expanse must stay background"


def test_detached_interior_element_over_two_percent_is_reclaimed():
    """The peacock's branch assembly was 5.9% of frame — over the old 2% cap —
    detached-from-nothing... and border-clear. Interior cap is now 8%."""
    img = np.full((400, 400, 3), 255, np.uint8)
    kept = np.zeros((400, 400), np.uint8)
    cv2.circle(img, (300, 300), 60, (60, 60, 160), -1)
    cv2.circle(kept, (300, 300), 60, 255, -1)
    cv2.rectangle(img, (40, 40), (160, 120), (30, 90, 140), -1)  # 9600px ≈ 6%
    out = _reclaim_ink(img, kept)
    assert out[80, 100] == 255


def test_inverted_matte_is_rejected_by_ink_recall():
    """v2 Part 32: on a neckline design on black, U2-Net kept the empty neck
    OPENING as the subject (ink recall 0.004) and the design digitized to ONE
    object. A matte covering under 20% of strong-ink pixels is not segmenting
    the artwork and must yield to the classical tiers. The gate's first draft
    (0.5) was itself caught by calibration: fixture 09's legitimate matte
    measures 0.407, and 0.5 would have caused the regression it guards against.
    """
    from app.services import segmentation as S

    img = np.zeros((400, 400, 3), np.uint8)          # black substrate
    cv2.circle(img, (100, 200), 60, (40, 160, 60), -1)
    cv2.circle(img, (300, 200), 60, (140, 60, 160), -1)
    cv2.rectangle(img, (80, 40), (320, 90), (60, 60, 200), -1)

    # Simulate the failure: a matte that keeps only an empty central region.
    bad = np.zeros((400, 400), np.uint8)
    cv2.rectangle(bad, (170, 120), (230, 300), 255, -1)  # covers no ink
    orig = S._rembg_mask
    S._rembg_mask = lambda data: bad
    try:
        mask, method = S.foreground_mask(img, b"fake")
        assert method != "rembg", "an inverted matte must not win the tier race"
        # The classical tier must recover the actual elements.
        assert mask[200, 100] > 0 and mask[200, 300] > 0
    finally:
        S._rembg_mask = orig
