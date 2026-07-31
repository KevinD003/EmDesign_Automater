"""Equivalence guard for the windowed skeleton-satin path (perf swarm, worker 3).

Every optimization here replaces a full-canvas array pass with the same
operation on the foreground's bounding box, pasted back. Each test replicates
the PRE-OPTIMIZATION body inline as an oracle and asserts bit equality, so the
speedup cannot silently move a stitch. The masks deliberately include the cases
the windowing reasoning depends on: content flush against the canvas edge (the
window clamps and the crop border IS the canvas border), an empty mask, a
one-pixel sliver, and a closed ring (whose skeleton has no endpoint at all).
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services import digitizer as D

# Big canvas, small content: the whole point is that the region occupies a small
# fraction of the canvas, which is what the production regions look like.
CANVAS = 360


def _canvas() -> np.ndarray:
    return np.zeros((CANVAS, CANVAS), np.uint8)


def _ring() -> np.ndarray:
    m = _canvas()
    cv2.circle(m, (120, 130), 46, 255, 4)
    return m


def _bar() -> np.ndarray:
    m = _canvas()
    cv2.line(m, (80, 200), (240, 96), 255, 5)
    return m


def _edge_touching() -> np.ndarray:
    """Foreground flush with x=0 and y=0 — forces every window to clamp."""
    m = _canvas()
    cv2.rectangle(m, (0, 0), (70, 4), 255, -1)
    cv2.rectangle(m, (0, 0), (4, 90), 255, -1)
    return m


def _corner_pair() -> np.ndarray:
    """Content in two opposite corners: the padded box covers the whole canvas."""
    m = _canvas()
    cv2.rectangle(m, (0, 0), (30, 3), 255, -1)
    cv2.rectangle(m, (CANVAS - 31, CANVAS - 4), (CANVAS - 1, CANVAS - 1), 255, -1)
    return m


def _sliver() -> np.ndarray:
    m = _canvas()
    m[181, 90:150] = 255
    m[100, 200] = 255
    return m


def _glyphish() -> np.ndarray:
    """Junctions and free ends, i.e. the shapes spur pruning exists for."""
    m = _canvas()
    cv2.line(m, (90, 90), (90, 210), 255, 5)
    cv2.line(m, (90, 150), (170, 150), 255, 5)
    cv2.line(m, (170, 150), (200, 100), 255, 5)
    cv2.circle(m, (240, 200), 30, 255, 5)
    return m


MASKS = {
    "ring": _ring,
    "bar": _bar,
    "edge_touching": _edge_touching,
    "corner_pair": _corner_pair,
    "sliver": _sliver,
    "glyphish": _glyphish,
    "empty": _canvas,
}


# ── pre-optimization bodies, kept verbatim as oracles ────────────────────────

def _oracle_thin(mask: np.ndarray) -> np.ndarray:
    full = (mask > 0).astype(np.uint8)
    ys, xs = np.nonzero(full)
    if ys.size == 0:
        return full
    y0, y1 = max(0, ys.min() - 1), min(full.shape[0], ys.max() + 2)
    x0, x1 = max(0, xs.min() - 1), min(full.shape[1], xs.max() + 2)
    img = full[y0:y1, x0:x1].copy()
    yy, xx = np.indices(img.shape)
    parity_mask = (yy + xx + y0 + x0) % 2
    while True:
        removed_any = False
        for step in (0, 1):
            for parity in (0, 1):
                p = np.pad(img, 1)
                P2, P3 = p[:-2, 1:-1], p[:-2, 2:]
                P4, P5 = p[1:-1, 2:], p[2:, 2:]
                P6, P7 = p[2:, 1:-1], p[2:, :-2]
                P8, P9 = p[1:-1, :-2], p[:-2, :-2]
                seq = [P2, P3, P4, P5, P6, P7, P8, P9, P2]
                B = P2 + P3 + P4 + P5 + P6 + P7 + P8 + P9
                A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
                if step == 0:
                    cond = (P2 * P4 * P6 == 0) & (P4 * P6 * P8 == 0)
                else:
                    cond = (P2 * P4 * P8 == 0) & (P2 * P6 * P8 == 0)
                remove = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & cond & (parity_mask == parity)
                if remove.any():
                    img[remove] = 0
                    removed_any = True
        if not removed_any:
            out = np.zeros_like(full)
            out[y0:y1, x0:x1] = img
            return out


def _oracle_prune(skel: np.ndarray, min_len_px: int, rounds: int = 4) -> np.ndarray:
    out = skel.copy()
    for _ in range(max(1, rounds)):
        p = np.pad(out, 1)
        deg = sum(
            p[dy : dy + out.shape[0], dx : dx + out.shape[1]]
            for dy in (0, 1, 2)
            for dx in (0, 1, 2)
            if not (dy == 1 and dx == 1)
        )
        endpoints = {(int(x), int(y)) for y, x in zip(*np.nonzero((out > 0) & (deg == 1)))}
        if not endpoints:
            break
        removed = False
        for br in D._skeleton_branches(out):
            if len(br) >= min_len_px:
                continue
            if br[0] in endpoints or br[-1] in endpoints:
                for x, y in (br[1:] if br[0] in endpoints else br[:-1]):
                    out[y, x] = 0
                removed = True
        if not removed:
            break
    return out


def _oracle_boundary(region: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours((region > 0).astype(np.uint8), cv2.RETR_CCOMP,
                                   cv2.CHAIN_APPROX_NONE)
    arcs = [c.reshape(-1, 2).astype(np.float64) for c in contours if len(c) >= 2]
    return np.vstack(arcs) if arcs else np.zeros((0, 2), dtype=np.float64)


def _oracle_axis_branches(binary: np.ndarray, dist: np.ndarray, mm_per_px: float):
    """`_axis_branches` with the full-canvas morphological close it used to run."""
    skel = D._zhang_suen_thin(cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)))
    median_half = float(np.median(dist[skel > 0])) if (skel > 0).any() else 0.0
    spur_px = max(round(D.SPUR_MIN_MM / mm_per_px), round(median_half * D.SPUR_PRUNE_MULT), 3)
    skel = D._prune_spurs(skel, spur_px)
    branches = [b for b in D._skeleton_branches(skel) if len(b) >= 3]
    return skel, branches or [b for b in D._skeleton_branches(skel) if len(b) >= 2]


def _oracle_hires(region, mm_per_px, sat_step, max_step_px, extra_half_px, stroke_px):
    """The full-canvas upscale `_skeleton_satin_hires` used before windowing."""
    f = 1
    if stroke_px > 0 and stroke_px < D.SMALL_STROKE_PX:
        f = min(D.SMALL_STROKE_MAX_SCALE, max(2, round(D.SMALL_STROKE_PX / stroke_px)))
    if f == 1:
        return D._skeleton_satin(region, mm_per_px, sat_step, max_step_px,
                                 extra_half_px=extra_half_px)
    big = cv2.resize(region, (region.shape[1] * f, region.shape[0] * f),
                     interpolation=cv2.INTER_CUBIC)
    big = (big > 127).astype(region.dtype) * 255
    cand, median_w, wide_mask, axis_pts = D._skeleton_satin(
        big, mm_per_px / f, sat_step * f, max_step_px * f, extra_half_px=extra_half_px * f,
    )
    cand = [(x / f, y / f, j) for x, y, j in cand]
    axis_pts = [(x / f, y / f, j) for x, y, j in axis_pts]
    wide_mask = cv2.resize(wide_mask, (region.shape[1], region.shape[0]),
                           interpolation=cv2.INTER_AREA)
    wide_mask = (wide_mask > 127).astype(region.dtype) * 255
    return cand, median_w, wide_mask, axis_pts


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(MASKS))
def test_distance_transform_matches_full_canvas(name: str) -> None:
    binary = (MASKS[name]() > 0).astype(np.uint8)
    expect = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    actual = D._distance_transform(binary)
    assert actual.dtype == expect.dtype and actual.shape == expect.shape
    assert np.array_equal(actual, expect)


@pytest.mark.parametrize("name", sorted(MASKS))
def test_thinning_matches_pre_optimization_body(name: str) -> None:
    mask = MASKS[name]()
    expect = _oracle_thin(mask)
    actual = D._zhang_suen_thin(mask)
    assert actual.dtype == expect.dtype and actual.shape == expect.shape
    assert np.array_equal(actual, expect)
    # A mask with content must thin to something, or equality is vacuous.
    assert bool(expect.any()) == bool(mask.any())


@pytest.mark.parametrize("name", sorted(MASKS))
def test_spur_pruning_matches_pre_optimization_body(name: str) -> None:
    skel = D._zhang_suen_thin(MASKS[name]())
    for min_len_px in (3, 9):
        expect = _oracle_prune(skel, min_len_px)
        assert np.array_equal(D._prune_spurs(skel, min_len_px), expect)


@pytest.mark.parametrize("name", sorted(MASKS))
def test_boundary_points_match_full_canvas(name: str) -> None:
    mask = MASKS[name]()
    expect = _oracle_boundary(mask)
    actual = D._boundary_points(mask)
    assert actual.shape == expect.shape
    assert np.array_equal(actual, expect)
    assert (len(expect) > 0) == bool(mask.any())


@pytest.mark.parametrize("name", sorted(MASKS))
def test_axis_branches_match_full_canvas_close(name: str) -> None:
    binary = (MASKS[name]() > 0).astype(np.uint8)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    skel, branches = D._axis_branches(binary, dist, 0.3)
    e_skel, e_branches = _oracle_axis_branches(binary, dist, 0.3)
    assert np.array_equal(skel, e_skel)
    assert branches == e_branches
    assert (len(e_branches) > 0) == bool(binary.any())


@pytest.mark.parametrize("name", sorted(MASKS))
def test_hires_satin_matches_full_canvas_upscale(name: str) -> None:
    region = MASKS[name]()
    # stroke_px below SMALL_STROKE_PX is what selects the hires path (f > 1).
    args = (region, 0.26, 4, 12, 1.5, 4.0)
    cand, med, mask, axis = D._skeleton_satin_hires(*args)
    e_cand, e_med, e_mask, e_axis = _oracle_hires(*args)
    assert mask.shape == e_mask.shape and mask.dtype == e_mask.dtype
    assert np.array_equal(mask, e_mask)
    assert cand == e_cand
    assert axis == e_axis
    assert med == e_med
    # Guard against a vacuously-empty comparison on the shapes that carry ink.
    if name in {"ring", "bar", "glyphish"}:
        assert len(e_cand) > 0


def test_hires_f1_path_is_untouched() -> None:
    """stroke_px >= SMALL_STROKE_PX must still go straight to `_skeleton_satin`."""
    region = _bar()
    args = (region, 0.26, 4, 12, 1.5, D.SMALL_STROKE_PX)
    got = D._skeleton_satin_hires(*args)
    expect = D._skeleton_satin(region, 0.26, 4, 12, extra_half_px=1.5)
    assert got[0] == expect[0] and got[1] == expect[1] and got[3] == expect[3]
    assert np.array_equal(got[2], expect[2])


def test_fg_window_clamps_and_reports_empty() -> None:
    m = _canvas()
    assert D._fg_window(m, 4) is None
    m[10:20, 30:40] = 255
    assert D._fg_window(m, 4) == (6, 24, 26, 44)
    assert D._fg_window(m, 0) == (10, 20, 30, 40)
    # Padding past the canvas clamps rather than wrapping or going negative.
    assert D._fg_window(m, 100) == (0, 120, 0, 140)
