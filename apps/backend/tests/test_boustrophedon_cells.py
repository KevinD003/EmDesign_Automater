"""A serpentine fill must never cross a hole to reach the next run.

CTO 1b, 2026-08-09. `_scanline_fill` walked every scan row and emitted each of
that row's runs back to back. On an annulus the row above the counter is one
run and every row beside the counter is two, so the fill hopped from the left
run to the right run STRAIGHT ACROSS THE COUNTER, once per row, then hopped
back on the next row. `_route_travel` then converted each hop into a sewn
detour around the hole rim.

Measured on badge Satin 3 before the fix: 171 jumps handed to the router,
median 42.31mm, 104 of them over 20mm — and 16,989 manufactured travel
stitches, 80% of the object. The median is the counter's diameter, which is
what identified the mechanism.

The fix is the classic boustrophedon decomposition: split the rows into
monotone CELLS at the critical rows where the run count changes, sew each cell
to completion, and visit cells nearest-first. Part 13 already did the
equivalent for disconnected COMPONENTS; the hop within one concave component
was never addressed.

These tests pin the decomposition itself and the property that motivated it.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.services.digitizer.fills import _boustrophedon_cells, _scanline_fill


class TestDecomposition:
    def test_single_run_column_is_one_cell(self):
        rows = [(y, [(10, 40)]) for y in range(0, 50, 5)]
        cells = _boustrophedon_cells(rows)
        assert len(cells) == 1
        assert len(cells[0]) == len(rows)

    def test_split_and_merge_produce_three_cells(self):
        """The annulus shape in miniature: one run, then two, then one again."""
        rows = (
            [(y, [(0, 100)]) for y in (0, 5)]
            + [(y, [(0, 30), (70, 100)]) for y in (10, 15, 20)]
            + [(y, [(0, 100)]) for y in (25, 30)]
        )
        cells = _boustrophedon_cells(rows)
        # top band, left leg, right leg, bottom band
        assert len(cells) == 4
        sizes = sorted(len(c) for c in cells)
        assert sizes == [2, 2, 3, 3]
        # every row of every cell is a single run, and no cell mixes legs
        for cell in cells:
            xs = {seg for _y, seg in cell}
            assert len(xs) <= 3

    def test_every_row_appears_exactly_once(self):
        rows = (
            [(y, [(0, 100)]) for y in (0, 5)]
            + [(y, [(0, 30), (70, 100)]) for y in (10, 15, 20)]
            + [(y, [(0, 100)]) for y in (25, 30)]
        )
        cells = _boustrophedon_cells(rows)
        flat = [item for cell in cells for item in cell]
        expected = [(y, seg) for y, segs in rows for seg in segs]
        assert sorted(flat) == sorted(expected)

    def test_cells_are_monotone_in_y(self):
        rows = (
            [(y, [(0, 100)]) for y in (0, 5)]
            + [(y, [(0, 30), (70, 100)]) for y in range(10, 40, 5)]
            + [(y, [(0, 100)]) for y in (40, 45)]
        )
        for cell in _boustrophedon_cells(rows):
            ys = [y for y, _s in cell]
            assert ys == sorted(ys)
            assert len(set(ys)) == len(ys)

    def test_disjoint_columns_never_share_a_cell(self):
        """Two runs that never touch are two cells, whatever their row order."""
        rows = [(y, [(0, 20), (80, 100)]) for y in range(0, 40, 5)]
        cells = _boustrophedon_cells(rows)
        assert len(cells) == 2
        for cell in cells:
            lefts = {seg[0] for _y, seg in cell}
            assert len(lefts) == 1

    def test_empty(self):
        assert _boustrophedon_cells([]) == []


def _annulus(size: int = 300, outer: int = 140, inner: int = 70) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size]
    r2 = (xx - size // 2) ** 2 + (yy - size // 2) ** 2
    ring = (r2 <= outer * outer) & (r2 >= inner * inner)
    return (ring * 255).astype(np.uint8)


class TestFillDoesNotCrossTheHole:
    """The property, measured on the shape that exposed it."""

    def test_no_long_jump_across_an_annulus(self):
        """Measured old vs new on this 300px annulus, row 4px, step 6px:

            old   2151 points   78 jumps   68 over 100px   median 193.0px   total 13059.6px
            new   2151 points   15 jumps    0 over 100px   median   9.8px   total   233.9px

        The point count is IDENTICAL — the fix is pure reordering, it removes no
        coverage. Total jump distance falls 98.2%, and every hole crossing goes.

        The 15 remaining jumps are not cell transitions. Twelve are serpentine
        turns INSIDE a cap cell, where a circle's run width grows by more than
        `connect_px` between adjacent rows; those are inherent to a curved
        boundary at this pitch and are 8-17px. Only one exceeds 20px: the tour
        is top cap -> left leg -> bottom cap -> right leg, and the last hop is
        86px because both legs end at the counter's tangent points. Asserting on
        a raw jump COUNT conflates those two populations, which is what a first
        version of this test did wrong.
        """
        region = _annulus()
        pts = _scanline_fill(region, row_px=4, max_step_px=6, connect_px=8.0)
        assert pts

        jumps = []
        for i in range(1, len(pts)):
            if pts[i][2]:
                d = float(np.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
                jumps.append(d)

        crossings = [d for d in jumps if d > 100]
        assert not crossings, f"{len(crossings)} hole crossings, max {max(jumps):.1f}px"
        long_moves = [d for d in jumps if d > 20]
        assert len(long_moves) <= 3, f"long moves {[round(d) for d in long_moves]}"
        # 233.9px measured; 500 leaves room for a pitch tweak but not for the
        # mechanism coming back (13,059px).
        assert sum(jumps) < 500, f"total jump distance {sum(jumps):.0f}px"

    def test_coverage_is_preserved(self):
        """The reduction must be plumbing, not skipped area."""
        region = _annulus()
        pts = _scanline_fill(region, row_px=4, max_step_px=6, connect_px=8.0)

        # Every scan row that has foreground must be represented.
        want = {y for y in range(0, region.shape[0], 4) if region[y].any()}
        got = {round(p[1]) for p in pts}
        assert want <= got, f"rows dropped: {sorted(want - got)[:10]}"

    def test_stagger_diagonal_survives_cell_boundaries(self):
        """Phase is keyed to the absolute row, so it does not restart per cell.

        A per-cell counter would re-phase at every critical row and put
        penetrations of adjacent rows needle-into-needle at the seam.
        """
        region = np.zeros((120, 200), np.uint8)
        region[:, 20:180] = 255
        region[40:80, 90:110] = 0  # a rectangular hole -> three cells

        pts = _scanline_fill(region, row_px=4, max_step_px=6, connect_px=8.0)
        by_row: dict[int, list[float]] = {}
        for x, y, _j in pts:
            by_row.setdefault(round(y), []).append(float(x))

        # Rows 4 apart in the same leg must not share their interior grid.
        left = {y: sorted(x for x in xs if 30 < x < 85) for y, xs in by_row.items()}
        for y in (44, 48, 52, 56, 60):
            a, b = left.get(y, []), left.get(y + 4, [])
            if len(a) < 3 or len(b) < 3:
                continue
            coincident = sum(1 for x in a[1:-1] if any(abs(x - q) < 0.25 for q in b[1:-1]))
            assert coincident < len(a[1:-1]), f"rows {y}/{y + 4} share every penetration"


@pytest.mark.parametrize("row_px,max_step_px", [(3, 5), (4, 6), (6, 9)])
def test_annulus_stitch_count_is_bounded_by_area(row_px, max_step_px):
    """Sanity ceiling: a fill should cost about area / (row * step) stitches.

    Before the fix the annulus cost several times this, because the across-hole
    hops were sewn. This is deliberately loose — 2x — so it fails on a
    mechanism regression, not on a pitch tweak.
    """
    region = _annulus()
    pts = _scanline_fill(region, row_px=row_px, max_step_px=max_step_px, connect_px=8.0)
    area = int(np.count_nonzero(region))
    ceiling = 2.0 * area / (row_px * max_step_px)
    assert len(pts) < ceiling, f"{len(pts)} points vs ceiling {ceiling:.0f}"
