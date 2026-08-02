"""v2 Part 34 — the PARTIAL matte (full-bleed neckline panel).

Part 32 gated the matte on a hard ink-recall floor (0.2), calibrated against a
total failure (0.004). A full-bleed panel then produced a matte at recall
0.203 — one point above the floor — keeping an arbitrary diagonal fragment and
digitizing a quarter of the design. No fixed floor can split 0.203 (failure)
from 0.407 (fixture 09's legitimate matte), so the decision is comparative:
a matte missing over half the ink loses to a flood tier that explains >=95% of
it with a sane foreground fraction. Fixture 09 keeps its matte because flood
recall there is only 0.656 — flood cannot explain its ink.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services import segmentation as S


def _panel():
    """Full-bleed artwork on black: elements spread over the whole frame."""
    img = np.zeros((400, 400, 3), np.uint8)
    for cx, cy in [(60, 60), (340, 60), (60, 340), (340, 340), (200, 200)]:
        cv2.circle(img, (cx, cy), 45, (40, 160, 60), -1)
    for y in range(60, 340, 40):
        cv2.line(img, (100, y), (300, y), (60, 200, 220), 8)
    return img


def test_partial_matte_loses_to_flood_that_explains_the_ink():
    """A matte keeping ~one corner of a full-bleed panel (recall just above the
    0.2 floor) must be overruled by the flood tier, which recovers everything."""
    img = _panel()
    bad = np.zeros((400, 400), np.uint8)
    cv2.rectangle(bad, (0, 200), (200, 399), 255, -1)  # bottom-left corner only

    orig = S._rembg_mask
    S._rembg_mask = lambda data: bad
    try:
        mask, method = S.foreground_mask(img, b"fake")
        assert method == "floodfill", "a partial matte must lose the comparison"
        assert mask[60, 340] > 0, "the top-right element must be recovered"
        assert mask[60, 60] > 0 and mask[200, 200] > 0
    finally:
        S._rembg_mask = orig


def test_low_recall_matte_survives_when_flood_cannot_explain_the_ink():
    """Fixture 09's shape of evidence: matte recall under 0.5, but the flood
    tier explains well under 95% of the ink (non-uniform substrate defeats a
    border flood). The matte must be kept — this is the case that killed the
    'just raise the floor' fix."""
    img = _panel()
    # Non-uniform substrate: a bright gradient band floods poorly.
    for x in range(400):
        img[:, x][(img[:, x] == 0).all(axis=1)] = (x // 2, x // 3, x // 2)

    kept = np.zeros((400, 400), np.uint8)
    cv2.rectangle(kept, (0, 0), (399, 180), 255, -1)  # under half the ink

    orig = S._rembg_mask
    S._rembg_mask = lambda data: kept
    try:
        _mask, method = S.foreground_mask(img, b"fake")
        assert method == "rembg", "flood explains too little ink to overrule"
    finally:
        S._rembg_mask = orig
