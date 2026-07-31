"""v2 Part 22 — flat-graphic reclamation after the neural matte (segmentation).

Found by digitizing a NEW logo that had never been through the pipeline: a
wordmark placed under a mark came back with ZERO foreground pixels, so the
company name never reached the digitizer at all. U2-Net keeps the photographic
subject and discards what it reads as surrounding decoration — which is the
single most common logo layout there is.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services import segmentation


def _mark_with_wordmark() -> np.ndarray:
    """A filled mark with detached type below it, on a white ground."""
    img = np.full((900, 900, 3), 250, np.uint8)
    cv2.circle(img, (450, 400), 240, (86, 42, 24), -1)
    cv2.putText(img, "VERTEX", (250, 830), cv2.FONT_HERSHEY_DUPLEX, 3.2, (86, 42, 24), 8)
    return img


def _matte_that_keeps_only_the_mark(shape) -> np.ndarray:
    """Stand-in for U2-Net's output: the mark only, wordmark dropped."""
    mask = np.zeros(shape[:2], np.uint8)
    cv2.circle(mask, (450, 400), 240, 255, -1)
    return mask


def test_a_detached_wordmark_is_reclaimed():
    img = _mark_with_wordmark()
    matte = _matte_that_keeps_only_the_mark(img.shape)
    assert matte[780:860, 250:700].sum() == 0, "precondition: the matte drops the wordmark"

    out = segmentation._reclaim_ink(img, matte)
    assert out[780:860, 250:700].sum() > 0, "the wordmark must be reclaimed"


def test_the_mark_itself_is_untouched():
    img = _mark_with_wordmark()
    matte = _matte_that_keeps_only_the_mark(img.shape)
    out = segmentation._reclaim_ink(img, matte)
    assert (out[matte > 0] == 255).all(), "reclamation must never remove kept pixels"


def test_a_large_background_is_not_reclaimed():
    """Fixture 09's shape: a big non-substrate region the matte excluded on
    purpose. Reclaiming it turned that fixture from 1,747 into 9,319 stitches."""
    img = np.full((900, 900, 3), 250, np.uint8)
    img[:, :] = (200, 170, 90)                       # full-frame coloured ground
    cv2.circle(img, (450, 450), 200, (40, 40, 200), -1)
    matte = np.zeros(img.shape[:2], np.uint8)
    cv2.circle(matte, (450, 450), 200, 255, -1)

    out = segmentation._reclaim_ink(img, matte)
    corner = out[0:60, 0:60]
    assert corner.sum() == 0, "a frame-sized background must stay excluded"


def test_an_attached_fringe_is_not_reclaimed():
    """A component touching the kept mask is the matte's own tight edge, not a
    missed element; re-adding it only fattens shapes (measured: fixture 05 lost
    0.5 interior and gained 2.2 spill when attached fringe was reclaimed)."""
    img = np.full((400, 400, 3), 250, np.uint8)
    cv2.rectangle(img, (100, 100), (300, 300), (30, 30, 30), -1)
    matte = np.zeros(img.shape[:2], np.uint8)
    cv2.rectangle(matte, (104, 104), (296, 296), 255, -1)   # 4px tight all round

    out = segmentation._reclaim_ink(img, matte)
    assert int((out > 0).sum()) == int((matte > 0).sum()), "attached fringe must not be added"


@pytest.mark.parametrize("speck", [1, 2, 3])
def test_speckle_is_not_promoted(speck):
    img = np.full((900, 900, 3), 250, np.uint8)
    cv2.circle(img, (450, 450), 200, (30, 30, 30), -1)
    img[10:10 + speck, 10:10 + speck] = (20, 20, 20)       # isolated dust
    matte = np.zeros(img.shape[:2], np.uint8)
    cv2.circle(matte, (450, 450), 200, 255, -1)

    out = segmentation._reclaim_ink(img, matte)
    assert out[0:40, 0:40].sum() == 0, "dust must not become an object"
