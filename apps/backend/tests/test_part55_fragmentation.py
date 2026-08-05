"""Scoping instrument for R005 fragmentation (v2 Part 55).

Part 55 chose R005 over R008 as the next build target and measured what an
implementation would actually act on. Two things it found have to stay true of
the instrument itself, because both are easy to get quietly wrong:

* merging is only ever allowed **within one colour stop** — merging across stops
  would reorder colour changes and can put light thread under dark, which is the
  same reason Part 48 declined cross-colour trim ordering;
* proximity is between the **regions**, not their bounding boxes. A ring and the
  dot at its centre have overlapping boxes and are not adjacent, and an
  instrument that confused the two would report merge opportunities that do not
  exist.

No engine change in Part 55; this covers the measurement only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND_ROOT), str(BACKEND_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import measure_fragmentation as MF


def _labels_from(shapes, size=(200, 200)):
    """Paint each (draw_fn) as its own object id."""
    labels = np.zeros(size, np.int32)
    for i, draw in enumerate(shapes, start=1):
        one = np.zeros(size, np.uint8)
        draw(one)
        labels[one > 0] = i
    return labels


def test_regions_that_do_not_touch_are_not_neighbours_at_zero_gap():
    labels = _labels_from([
        lambda m: cv2.rectangle(m, (10, 10), (40, 40), 255, -1),
        lambda m: cv2.rectangle(m, (60, 10), (90, 40), 255, -1),
    ])
    assert MF.neighbours_within(labels, 2, 0) == set()


def test_regions_within_the_gap_become_neighbours():
    labels = _labels_from([
        lambda m: cv2.rectangle(m, (10, 10), (40, 40), 255, -1),
        lambda m: cv2.rectangle(m, (46, 10), (76, 40), 255, -1),
    ])
    # Filled rectangles include their corners, so x=41..45 is clear: five pixels
    # of separation. `gap_px` is a dilation RADIUS applied to one region only, so
    # it has to reach across the whole clear span and land on the other region —
    # radius 5 stops at x=45, radius 6 touches x=46.
    assert MF.neighbours_within(labels, 2, 5) == set()
    assert MF.neighbours_within(labels, 2, 6) == {(1, 2)}


def test_a_ring_and_the_dot_inside_it_are_adjacent_only_if_really_close():
    """Bounding boxes overlap completely here; the regions do not.

    An instrument that used boxes would call these neighbours at any gap and
    report a merge that a digitizer would never make.
    """
    labels = _labels_from([
        lambda m: (cv2.circle(m, (100, 100), 60, 255, -1),
                   cv2.circle(m, (100, 100), 40, 0, -1)),
        lambda m: cv2.circle(m, (100, 100), 8, 255, -1),
    ])
    assert MF.neighbours_within(labels, 2, 1) == set(), "hollow ring reported as touching its centre dot"
    # 40 - 8 = 32 px of clear space; only a gap that large should link them.
    assert MF.neighbours_within(labels, 2, 34) == {(1, 2)}


def test_grouping_is_transitive_through_a_chain():
    """Three regions in a line, each near the next, are one group."""
    uf = MF._Union(4)
    uf.join(1, 2)
    uf.join(2, 3)
    assert uf.find(1) == uf.find(3)


def test_union_find_keeps_separate_chains_apart():
    uf = MF._Union(5)
    uf.join(1, 2)
    uf.join(3, 4)
    assert uf.find(1) != uf.find(3)


def test_neighbour_search_is_bounded_by_region_area_not_frame_area():
    """The Parts 48/49 hazard, in the form it would take here.

    A full-frame dilate per object is multiplied by the OBJECT COUNT, which on a
    fragmented design is exactly the large number — 20 objects in a 25x larger
    frame would then cost ~500x.

    The bound asserted is LINEAR in frame area, not constant: one pass over the
    frame is needed to find the bounding boxes at all, and that pass legitimately
    grows with the frame. What must not grow is per-object full-frame work. This
    test failed when `np.where(labels == oid)` was doing exactly that.
    """
    import time

    def build(size):
        return _labels_from(
            [(lambda m, k=k: cv2.circle(m, (30 + 6 * k, 30 + 5 * k), 8, 255, -1))
             for k in range(20)],
            size=size,
        )

    small, big = build((400, 400)), build((2000, 2000))
    MF.neighbours_within(small, 20, 3)
    t0 = time.perf_counter(); MF.neighbours_within(small, 20, 3); t_small = time.perf_counter() - t0
    t0 = time.perf_counter(); MF.neighbours_within(big, 20, 3); t_big = time.perf_counter() - t0
    ratio = t_big / max(t_small, 1e-9)
    assert t_big < 40.0 * max(t_small, 1e-4), (
        f"25x the frame cost {ratio:.1f}x the time — that is faster than linear "
        "only if the per-object work is bbox-local, so this is the object-count "
        "multiplier coming back"
    )
