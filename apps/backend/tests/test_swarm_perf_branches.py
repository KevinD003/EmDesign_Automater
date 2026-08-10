"""Equivalence lock for the `_skeleton_branches` / `_prune_spurs` speedups.

Both functions were pure Python set/dict loops over skeleton pixels. The rewrite
moved neighbour discovery into `_skeleton_adjacency` (vectorised occupancy
gathers, windowed nonzero scan) and let `_prune_spurs` hand its window down.

Branch ORDER is stitch order: discovery feeds `_order_branches` and
`seen_edges`, and any difference in the emitted list — order, direction or
content — moves stitches. These tests therefore compare the full branch lists
for identity, not just their contents as a set.

The references below are the pre-optimization bodies copied verbatim, WITH ONE
DELIBERATE DEVIATION. Both the original and the shipped function iterated
`for node in nodes` over a SET, so discovery ran in tuple-hash order — stable
for a given CPython build, which is why this lock never caught it, but chosen by
hash rather than by geometry, and directly contrary to `_skeleton_adjacency`'s
own docstring ("the caller's set must be built from it IN THAT ORDER"). That was
fixed on its own merits alongside CTO 1b; the reference tracks the fix, keeping
raster order in the two containers that decide discovery sequence. Everything
else here is verbatim, because the neighbour-discovery rewrite is what the lock
is actually for and it remains independently re-implemented below.
"""

import numpy as np
import pytest

from app.services import digitizer as D

# ── references: the pre-optimization bodies, verbatim ────────────────────────


def _reference_branches(skel, min_len: int = 2):
    # `dict.fromkeys`, not a set comprehension — see the note on discovery order
    # in the module docstring. `np.nonzero` yields raster order and this keeps
    # it; everything else in this body is the pre-optimization code verbatim,
    # because what the lock exists to check is the neighbour-discovery rewrite.
    pts = dict.fromkeys((int(x), int(y)) for y, x in zip(*np.nonzero(skel)))
    if not pts:
        return []

    def neighbours(pt):
        x, y = pt
        out = [
            (x + dx, y + dy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (x + dx, y + dy) in pts
        ]
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            if (x + dx, y + dy) in pts and (x + dx, y) not in pts and (x, y + dy) not in pts:
                out.append((x + dx, y + dy))
        return out

    degree = {p: len(neighbours(p)) for p in pts}
    nodes = {p for p, d in degree.items() if d != 2}
    node_order = [p for p in pts if p in nodes]
    branches: list[list[tuple[int, int]]] = []
    seen_edges: set[frozenset] = set()

    def walk(start, first):
        path = [start, first]
        prev, cur = start, first
        while cur not in nodes:
            nxt = [n for n in neighbours(cur) if n != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
        return path

    for node in node_order:
        for nb in neighbours(node):
            edge = frozenset((node, nb))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            path = walk(node, nb)
            for a, b in zip(path, path[1:]):
                seen_edges.add(frozenset((a, b)))
            if len(path) >= min_len:
                branches.append(path)

    if not branches and pts:
        start = next(iter(pts))
        path, prev, cur = [start], None, start
        while True:
            nxt = [n for n in neighbours(cur) if n != prev]
            if not nxt or nxt[0] == start:
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
        if len(path) >= min_len:
            branches.append(path)
    return D._order_branches(branches)


def _reference_prune(skel, min_len_px: int, rounds: int = 4):
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
        for br in _reference_branches(out):
            if len(br) >= min_len_px:
                continue
            if br[0] in endpoints or br[-1] in endpoints:
                for x, y in (br[1:] if br[0] in endpoints else br[:-1]):
                    out[y, x] = 0
                removed = True
        if not removed:
            break
    return out


# ── skeleton fixtures ────────────────────────────────────────────────────────
# Built as filled masks and thinned, so the inputs are real Zhang-Suen output
# (staircases, L-corners, junction knots) rather than hand-drawn 1px lines.

CANVAS = 120  # px; leaves margin so shapes never touch the canvas edge
BLOB_SEED = 20260730  # fixed so the spiky blob is reproducible


def _mask_ring():
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS]
    r = np.hypot(yy - 60, xx - 60)
    m[(r >= 34) & (r <= 41)] = 255
    return m


def _mask_bare_loop():
    """A closed loop with NO endpoint — exercises the `next(iter(pts))` path."""
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    m[30:90, 30:38] = m[30:90, 82:90] = 255
    m[30:38, 30:90] = m[82:90, 30:90] = 255
    return m


def _mask_cross():
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS]
    m[(np.abs(yy - xx) <= 4) & (yy > 20) & (yy < 100)] = 255
    m[(np.abs(yy + xx - 120) <= 4) & (yy > 20) & (yy < 100)] = 255
    return m


def _mask_tee():
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    m[24:31, 20:100] = 255
    m[24:100, 58:65] = 255
    return m


def _mask_spiky_blob():
    """Disc with random hairs — the case `_prune_spurs` exists for."""
    rng = np.random.default_rng(BLOB_SEED)
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS]
    m[np.hypot(yy - 60, xx - 60) <= 22] = 255
    for ang in rng.random(14) * 2 * np.pi:
        length = 6 + rng.random() * 22
        for t in np.linspace(0, length, int(length) * 3 + 1):
            cy, cx = 60 + (22 + t) * np.sin(ang), 60 + (22 + t) * np.cos(ang)
            m[int(cy) - 1 : int(cy) + 2, int(cx) - 1 : int(cx) + 2] = 255
    return m


def _mask_hairy_bar():
    """Short stubs on a thick bar — spurs `_prune_spurs` must actually delete."""
    rng = np.random.default_rng(BLOB_SEED + 1)
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    m[54:67, 15:105] = 255
    for x in rng.choice(np.arange(20, 100), 12, replace=False):
        h = int(3 + rng.random() * 7)
        m[67 : 67 + h, x : x + 3] = 255
        m[54 - h : 54, x : x + 3] = 255
    return m


def _mask_noise():
    """Random blobs: isolated fragments, two-endpoint branches, dense junctions."""
    rng = np.random.default_rng(BLOB_SEED + 2)
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    m[10:110, 10:110] = (rng.random((100, 100)) < 0.42) * 255
    return m


def _mask_offset_bar():
    """Odd origin: catches anything that silently re-frames the coordinates."""
    m = np.zeros((CANVAS, CANVAS), np.uint8)
    m[17:24, 13:97] = 255
    m[17:70, 61:68] = 255
    return m


MASKS = {
    "ring": _mask_ring,
    "bare_loop": _mask_bare_loop,
    "cross": _mask_cross,
    "tee": _mask_tee,
    "spiky_blob": _mask_spiky_blob,
    "offset_bar": _mask_offset_bar,
}

MIN_LENS = (3, 8, 20)  # below / around / above the spur lengths in the blob


def _skeleton(name: str):
    skel = D._zhang_suen_thin(MASKS[name]())
    assert skel.any(), f"{name} thinned to nothing — the comparison would be vacuous"
    return skel


# ── tests ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(MASKS))
def test_branches_match_pre_optimization_body(name: str) -> None:
    skel = _skeleton(name)
    expect = _reference_branches(skel)
    actual = D._skeleton_branches(skel)
    assert expect, f"{name} produced no branches — equality would be vacuous"
    assert actual == expect  # same order, same direction, same points


@pytest.mark.parametrize("name", sorted(MASKS))
def test_branches_match_for_higher_min_len(name: str) -> None:
    skel = _skeleton(name)
    for min_len in (2, 3, 6):
        assert D._skeleton_branches(skel, min_len) == _reference_branches(skel, min_len)


@pytest.mark.parametrize("name", sorted(MASKS))
def test_prune_matches_pre_optimization_body(name: str) -> None:
    skel = _skeleton(name)
    for min_len_px in MIN_LENS:
        expect = _reference_prune(skel, min_len_px)
        actual = D._prune_spurs(skel, min_len_px)
        assert actual.dtype == expect.dtype and actual.shape == expect.shape
        assert np.array_equal(actual, expect)
    # The spiky blob must actually lose pixels, or the oracle proves nothing.
    if name == "spiky_blob":
        assert D._prune_spurs(skel, 20).sum() < skel.sum()


@pytest.mark.parametrize("name", sorted(MASKS))
def test_prune_matches_for_other_round_counts(name: str) -> None:
    skel = _skeleton(name)
    for rounds in (1, 2, 8):
        assert np.array_equal(D._prune_spurs(skel, 8, rounds), _reference_prune(skel, 8, rounds))


@pytest.mark.parametrize("name", sorted(MASKS))
def test_supplied_window_matches_computed_window(name: str) -> None:
    """`_prune_spurs` hands down a box grown by 1; any superset must be equal."""
    skel = _skeleton(name)
    for pad in (0, 1, 5):
        win = D._fg_window(skel, pad)
        assert D._skeleton_branches(skel, win=win) == _reference_branches(skel)


def test_empty_skeleton_yields_no_branches() -> None:
    empty = np.zeros((CANVAS, CANVAS), np.uint8)
    assert D._skeleton_branches(empty) == []
    assert D._skeleton_adjacency(empty) == ([], {})
    assert np.array_equal(D._prune_spurs(empty, 8), empty)


def test_adjacency_offset_order_is_the_documented_one() -> None:
    """`walk` follows nxt[0]; the offset order is what picks it."""
    assert D.SKEL_ORTHO == ((1, 0), (-1, 0), (0, 1), (0, -1))
    assert D.SKEL_DIAG == ((1, 1), (1, -1), (-1, 1), (-1, -1))


@pytest.mark.parametrize("name", sorted(MASKS))
def test_adjacency_lists_match_the_reference_rule(name: str) -> None:
    """Per-point neighbour lists, in order, against the original set arithmetic."""
    skel = _skeleton(name)
    pts, nbrs = D._skeleton_adjacency(skel)
    pt_set = set(pts)
    assert len(pts) == int((skel > 0).sum()) == len(pt_set)
    # Raster order: the caller's `set(pts)` insertion order decides branch order.
    assert pts == [(int(x), int(y)) for y, x in zip(*np.nonzero(skel))]
    for x, y in pts:
        expect = [
            (x + dx, y + dy) for dx, dy in D.SKEL_ORTHO if (x + dx, y + dy) in pt_set
        ]
        for dx, dy in D.SKEL_DIAG:
            if (x + dx, y + dy) in pt_set and (x + dx, y) not in pt_set and (x, y + dy) not in pt_set:
                expect.append((x + dx, y + dy))
        assert nbrs[(x, y)] == expect


@pytest.mark.parametrize("name", sorted(MASKS))
def test_adjacency_is_symmetric(name: str) -> None:
    """The redundant-diagonal rule must read the same from either end."""
    _, nbrs = D._skeleton_adjacency(_skeleton(name))
    for pt, ns in nbrs.items():
        for n in ns:
            assert pt in nbrs[n]
