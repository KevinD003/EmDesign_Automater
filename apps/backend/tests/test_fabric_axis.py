"""The fabric axis has to DISCRIMINATE, or it is worse than absent.

An axis whose numbers do not move with the fabric would look like coverage while
providing none — and the physical-units tranche (SZ1/SZ3/SZ4/UP2/UP3/UP4) is
about to be tuned against it. So these tests do not check that the sweep runs;
they check that it can tell fabrics apart, on the quantities each fabric
parameter is supposed to move.

Measured spread across denim (pull 0.15) to fleece (pull 0.50), which is the full
range the profiles define:

    05_wordmark_caps    satin    p90 step   3.8750 -> 4.5178
    01_flat_2color_logo fill     stitches   6,200 -> 4,913   (-21%)
    07_circular_badge   mixed    stitches  17,178 -> 14,160  (-17.6%)
                                 minutes    22.64 -> 18.78

That last row is why the axis was needed: every headline number in this series is
a COTTON number, and the same badge on fleece is 3.9 machine-minutes cheaper.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND / "scripts"))

from measure_fabric_axis import FABRICS, FIXTURES, sweep

from app.services.digitizer.constants import FABRIC_PROFILES


def test_the_axis_spans_the_whole_pull_range():
    """Sampling three fabrics clustered at 0.15-0.20 would show almost nothing.
    The profiles' own min and max must both be represented."""
    pulls = [FABRIC_PROFILES[f]["pull_mm"] for f in FABRICS]
    every = [p["pull_mm"] for p in FABRIC_PROFILES.values()]
    assert min(pulls) == min(every), "the axis misses the lowest-pull fabric"
    assert max(pulls) == max(every), "the axis misses the highest-pull fabric"
    assert len(set(pulls)) >= 5, f"only {len(set(pulls))} distinct pull values sampled"


def test_the_axis_covers_both_generators():
    """Pull compensation reaches satin columns and fills by DIFFERENT code paths.
    That asymmetry was UP1 itself — satin got half what fills got — so an axis
    that sampled only one of them could miss the next defect of that shape."""
    rows = sweep(fixtures=FIXTURES, fabrics=["cotton"])
    by_fixture = {r["fixture"]: r for r in rows}
    assert any(r["satin_objects"] > 0 for r in by_fixture.values()), "no satin sampled"
    assert any(r["satin_objects"] == 0 for r in by_fixture.values()), "no pure fill sampled"


def test_satin_column_width_tracks_pull_compensation():
    """The quantity UP1 moved, on the fixture that is all satin.

    Asserted as a MONOTONE relationship rather than an exact figure: the profiles
    change `satin_mm` alongside `pull_mm`, so the column pitch moves too and the
    width is not a pure function of pull. What must hold is that more pull gives a
    wider sewn column — if that ever inverts, pull compensation has stopped
    reaching the columns.
    """
    rows = sweep(fixtures=["05_wordmark_caps"], fabrics=FABRICS)
    rows.sort(key=lambda r: r["pull_mm"])
    widths = [r["p90_step_mm"] for r in rows]
    assert widths == sorted(widths), (
        f"sewn satin column width is not monotone in pull compensation: "
        f"{[(r['fabric'], r['pull_mm'], r['p90_step_mm']) for r in rows]}"
    )
    assert widths[-1] - widths[0] > 0.3, (
        f"only {widths[-1] - widths[0]:.4f}mm of column-width spread across the "
        f"whole pull range — the axis cannot see pull compensation at all"
    )


def test_fill_density_tracks_the_row_pitch():
    """`row_mm` runs 0.40 (denim/cotton) to 0.55 (jersey/fleece), so a fill sews
    measurably fewer stitches on a knit. Measured -21% on this fixture; asserted
    at a much weaker 5% so the test pins the DIRECTION and the existence of the
    effect, not a number that legitimate work will move."""
    rows = sweep(fixtures=["01_flat_2color_logo"], fabrics=FABRICS)
    by_row = {}
    for r in rows:
        by_row.setdefault(r["row_mm"], []).append(r["stitches"])
    finest = min(by_row)
    coarsest = max(by_row)
    assert coarsest > finest, "the sampled fabrics all share one row pitch"
    fine = max(by_row[finest])
    coarse = min(by_row[coarsest])
    assert coarse < fine * 0.95, (
        f"a {finest}mm row pitch sewed {fine} stitches and a {coarsest}mm pitch "
        f"{coarse} — under 5% apart, so the axis cannot see fill density"
    )


def test_p90_step_is_not_a_fabric_signal_for_fills():
    """Recorded so nobody reads the sweep's flat column as a defect.

    Fill rows are split at a fixed maximum stitch length, so the 90th percentile
    step sits ON that cap regardless of fabric — 3.9750 for every fabric on the
    fill fixture. It is a real property of the generator, not a broken
    measurement, and `median_step_mm` is the fabric-sensitive column for fills.
    """
    rows = sweep(fixtures=["01_flat_2color_logo"], fabrics=FABRICS)
    p90s = {r["p90_step_mm"] for r in rows}
    assert len(p90s) == 1, (
        f"p90 step is no longer pinned at the fill's max-step cap ({p90s}); if "
        f"this is intended, this test's premise needs rewriting rather than the "
        f"assertion loosening"
    )
    medians = {r["median_step_mm"] for r in rows}
    assert len(medians) > 1, "median step should still vary with the row pitch"


def test_the_profiles_are_read_not_restated():
    """A copy of the pull values here would drift from the engine's and the axis
    would report a fabric the pipeline no longer sews."""
    import inspect

    import measure_fabric_axis

    src = inspect.getsource(measure_fabric_axis)
    assert "FABRIC_PROFILES" in src, "the axis restates fabric parameters instead of reading them"
    for f in FABRICS:
        assert f in FABRIC_PROFILES, f"{f} is not a profile the engine knows"
