"""Equivalence guard for the windowed `_uncovered_mask` (digitizer perf swarm).

The optimization crops the disc dilate to binary's bounding box; these cases pin
it to the previous full-canvas computation, which is replicated inline as the
oracle so a later edit to the production path cannot drift silently.
"""

import cv2
import numpy as np
import pytest

from app.services.digitizer import _uncovered_mask


def _uncovered_mask_reference(binary, skel, max_half_px: float):
    """The pre-optimization body, verbatim: full-canvas dilate then open."""
    # int() is not redundant here: round() on a numpy float returns a numpy float,
    # which cv2.getStructuringElement rejects. Kept verbatim from production.
    r = max(1, int(round(max_half_px)))  # noqa: RUF046
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    covered = cv2.dilate((skel > 0).astype(np.uint8), disc)
    mask = ((binary > 0) & (covered == 0)).astype(np.uint8) * 255
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def _thin(binary, iterations: int):
    """Skeleton stand-in that stays a subset of `binary`, as the caller's does."""
    return cv2.erode(binary, np.ones((3, 3), np.uint8), iterations=iterations)


def _blob_in_large_canvas():
    """Sparse case the window exists for: 60x60 of ink on a 600x600 canvas, r=20."""
    binary = np.zeros((600, 600), np.uint8)
    binary[270:330, 260:320] = 255
    skel = np.zeros_like(binary)
    skel[300, 275:305] = 255
    return binary, skel, 20.0, True


def _blob_touching_edge():
    """Both bbox ends clamp against the canvas, so the pad cannot be applied."""
    binary = np.zeros((160, 200), np.uint8)
    binary[0:40, 0:50] = 255
    binary[120:160, 170:200] = 255
    return binary, _thin(binary, 6), 2.0, True


def _empty():
    binary = np.zeros((80, 90), np.uint8)
    return binary, np.zeros_like(binary), 5.0, False


def _ring():
    binary = np.zeros((240, 240), np.uint8)
    cv2.circle(binary, (120, 120), 90, 255, thickness=14)
    return binary, _thin(binary, 5), 3.0, True


def _sliver_only():
    """One-px specks: the 3x3 open must erase them in both implementations."""
    binary = np.zeros((300, 300), np.uint8)
    binary[100, 100] = 255
    binary[250, 40] = 255
    return binary, np.zeros_like(binary), 3.0, False


CASES = {
    "blob_in_large_canvas": _blob_in_large_canvas,
    "blob_touching_edge": _blob_touching_edge,
    "empty": _empty,
    "ring": _ring,
    "sliver_only": _sliver_only,
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_windowed_matches_full_canvas(name: str) -> None:
    binary, skel, half, expect_nonempty = CASES[name]()
    expected = _uncovered_mask_reference(binary, skel, half)
    actual = _uncovered_mask(binary, skel, half)
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert np.array_equal(actual, expected), f"{name}: windowed output diverged"
    # Guards the guard: an accidentally all-zero oracle would match anything.
    assert bool(expected.any()) is expect_nonempty
