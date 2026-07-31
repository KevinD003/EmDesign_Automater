"""Equivalence guard for the vectorized `_zhang_suen_thin` (v2 swarm, perf 4).

The pre-optimization body is copied in verbatim as `_reference_thin` and every
case asserts exact array equality. Thinning's *removal schedule* — which pixel
leaves in which (step, parity) sub-iteration — is the contract, not just the
final pixel set: `_skeleton_branches` walks the skeleton from a set-iteration
start, so a single displaced pixel reorders every satin column downstream.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services import digitizer as D

# ── reference: the implementation as it stood before vectorization ───────────

def _reference_neighbours(img):
    p = np.pad(img, 1)
    # P2..P9, clockwise from north.
    P2, P3 = p[:-2, 1:-1], p[:-2, 2:]
    P4, P5 = p[1:-1, 2:], p[2:, 2:]
    P6, P7 = p[2:, 1:-1], p[2:, :-2]
    P8, P9 = p[1:-1, :-2], p[:-2, :-2]
    seq = (P2, P3, P4, P5, P6, P7, P8, P9, P2)
    B = P2 + P3 + P4 + P5 + P6 + P7 + P8 + P9
    A = sum((seq[i] ^ 1) & seq[i + 1] for i in range(8))
    return (P2, P4, P6, P8), B, A


def _reference_thin(mask):
    full = (mask > 0).astype(np.uint8)
    win = D._fg_window(full, 1)
    if win is None:
        return full
    y0, y1, x0, x1 = win
    img = full[y0:y1, x0:x1].copy()
    yy, xx = np.indices(img.shape)
    parity_mask = (yy + xx + y0 + x0) % 2
    par = (parity_mask == 0, parity_mask == 1)
    keep = None
    while True:
        removed_any = False
        for step in (0, 1):
            cond = None
            for parity in (0, 1):
                if keep is None:
                    (P2, P4, P6, P8), B, A = _reference_neighbours(img)
                    keep = (img == 1) & (B >= 2) & (B <= 6) & (A == 1)
                    cond = None
                if cond is None:
                    cond = (((P2 & P4 & P6) == 0) & ((P4 & P6 & P8) == 0) if step == 0
                            else ((P2 & P4 & P8) == 0) & ((P2 & P6 & P8) == 0))
                remove = keep & cond & par[parity]
                if remove.any():
                    img[remove] = 0
                    keep, removed_any = None, True
        if not removed_any:
            out = np.zeros_like(full)
            out[y0:y1, x0:x1] = img
            return out


# ── fixtures ─────────────────────────────────────────────────────────────────

BAR_HALF_W = 1          # 2 px total width — the even-width ridge the parity split exists for
NOISE_SEED = 20260730   # fixed so the removal-order coupling case is reproducible


def _bar():
    """A 2 px wide bar. Simultaneous update deletes both of its rows at once."""
    m = np.zeros((40, 60), np.uint8)
    m[18:18 + 2 * BAR_HALF_W, 6:54] = 255
    return m


def _disc():
    m = np.zeros((70, 70), np.uint8)
    cv2.circle(m, (35, 35), 24, 255, -1)
    return m


def _ring():
    m = np.zeros((80, 80), np.uint8)
    cv2.circle(m, (40, 40), 30, 255, 7)
    return m


def _lshape():
    m = np.zeros((60, 60), np.uint8)
    m[10:50, 10:16] = 255
    m[44:50, 10:52] = 255
    return m


def _noise():
    rng = np.random.default_rng(NOISE_SEED)
    return (rng.random((64, 64)) > 0.35).astype(np.uint8) * 255


def _empty():
    return np.zeros((32, 32), np.uint8)


def _offset_bar():
    """Same bar shifted one px — parity keys off absolute (y + x), not the crop."""
    m = np.zeros((40, 60), np.uint8)
    m[19:19 + 2 * BAR_HALF_W, 7:55] = 255
    return m


def _full_canvas():
    """Foreground on all four canvas edges — the window clamps with no margin."""
    return np.full((48, 52), 255, np.uint8)


MASKS = {
    "full_canvas": _full_canvas,
    "bar": _bar,
    "offset_bar": _offset_bar,
    "disc": _disc,
    "ring": _ring,
    "lshape": _lshape,
    "noise": _noise,
    "empty": _empty,
}


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(MASKS))
def test_thinning_matches_pre_vectorization_reference(name: str) -> None:
    mask = MASKS[name]()
    expect = _reference_thin(mask)
    actual = D._zhang_suen_thin(mask)
    assert actual.dtype == expect.dtype and actual.shape == expect.shape
    assert np.array_equal(actual, expect)
    # A mask with content must thin to something, or the equality is vacuous.
    assert bool(expect.any()) == bool(mask.any())


def test_even_width_bar_keeps_a_single_centre_line() -> None:
    """Guards the property the checkerboard split was added for."""
    skel = _reference_thin(_bar())
    assert D._zhang_suen_thin(_bar()).sum() == skel.sum() > 10


@pytest.mark.parametrize("shift", [0, 1, 2, 3])
def test_thinning_matches_reference_under_translation(shift: int) -> None:
    """Parity is absolute, so odd shifts thin differently — both sides must agree."""
    base = _lshape()
    mask = np.zeros((base.shape[0] + 4, base.shape[1] + 4), np.uint8)
    mask[shift:shift + base.shape[0], shift:shift + base.shape[1]] = base
    assert np.array_equal(D._zhang_suen_thin(mask), _reference_thin(mask))


NEIGHBOURHOODS = 256   # all 8-neighbour on/off patterns, one per bit of the index


@pytest.mark.parametrize("step", [0, 1])
def test_folded_step_condition_matches_the_two_triple_form(step: int) -> None:
    """The 4-op fold must agree on every one of the 256 neighbourhoods."""
    codes = np.arange(NEIGHBOURHOODS)
    nb = [((codes >> i) & 1).astype(np.uint8) for i in range(8)]
    P2, P4, P6, P8 = nb[0], nb[2], nb[4], nb[6]
    expect = ((((P2 & P4 & P6) == 0) & ((P4 & P6 & P8) == 0)) if step == 0
              else (((P2 & P4 & P8) == 0) & ((P2 & P6 & P8) == 0)))
    assert np.array_equal(D._thin_step_ok(nb, step), expect)


def test_ring_order_is_clockwise_from_north() -> None:
    """A counts transitions round THIS cycle; a reordering changes the schedule."""
    assert D.THIN_RING == ((-1, 0), (-1, 1), (0, 1), (1, 1),
                           (1, 0), (1, -1), (0, -1), (-1, -1))
