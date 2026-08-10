"""A bench number must carry the conditions it was measured under.

THE FAILURE THIS PREVENTS, in two acts.

Act one: every number this bench has ever printed was a COTTON number at one of
two hoops, and none of them said so. "22.65 machine-minutes" travelled through
four reports and was quoted to the owner as a headline improvement. Measured
across the fabric axis, the same fixture runs 18.78–22.64 machine-minutes — so
that figure is one point near the top of a 17% band that fabric alone moves.
Nothing reported was wrong. Nothing carried its label.

Act two: the fabric axis's own summary then mislabelled a badge figure as fleece
when it was jersey — in the same commit that established the need for labelling —
and the correction to THAT gave 100x100 as the hoop for two fixtures that run at
130x180. Two labelling errors in two hours, in the corrections to a labelling
problem. Care is not the fix; refusing to emit an unlabelled number is.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND / "scripts"))

from run_quality_bench import FIXTURE_PARAMS, _conditions, _headline


class _R:
    """Enough of a FixtureResult for the headline formatter."""

    def __init__(self, params):
        self.params = params
        self.fixture = "probe"
        self.stitch_count = 1234
        self.color_count = 3
        self.object_count = 5
        self.runtime_s = 1.0


def test_a_number_without_a_fabric_is_refused():
    with pytest.raises(SystemExit, match="fabric"):
        _conditions({"hoop": "100x100"})


def test_a_number_without_a_hoop_is_refused():
    with pytest.raises(SystemExit, match="hoop"):
        _conditions({"fabric": "cotton"})


def test_an_empty_fabric_is_refused_not_treated_as_absent_but_fine():
    """`params.get` returning "" would pass a truthiness-free check and print
    `[ @ 100x100]`, which reads as labelled and is not."""
    with pytest.raises(SystemExit):
        _conditions({"fabric": "", "hoop": "100x100"})


def test_the_headline_leads_with_the_conditions():
    line = _headline(_R({"fabric": "fleece", "hoop": "200x200"}))
    assert line.startswith("[fleece @ 200x200]"), line
    assert "1,234 st" in line


def test_every_bench_fixture_declares_both():
    """The guard is only worth having if the corpus actually satisfies it."""
    for name, params in FIXTURE_PARAMS.items():
        assert _conditions(params), name


def test_the_summary_records_the_conditions_it_aggregated_over():
    """`totals` sums across fixtures, and the aggregate is what gets quoted. A
    summary that carries per-fixture params but no aggregate label still lets an
    unlabelled total escape into a report."""
    import inspect

    import run_quality_bench

    src = inspect.getsource(run_quality_bench.main)
    assert '"conditions"' in src, (
        "the summary no longer records the fabrics and hoops it aggregated over"
    )
    assert src.index('"conditions"') < src.index('"totals"'), (
        "conditions must precede totals in the summary, so a reader meets the "
        "label before the number"
    )


def test_the_committed_summaries_that_have_conditions_are_consistent():
    """Any bench summary carrying a `conditions` block must agree with its own
    per-fixture params. Older summaries predate the block and are skipped rather
    than retro-fitted — they are historical records, not current claims."""
    bench = BACKEND.parent.parent / "docs" / "benchmarks"
    checked = 0
    for path in sorted(bench.glob("*-summary.json")):
        data = json.loads(path.read_text())
        cond = data.get("conditions")
        if not cond:
            continue
        checked += 1
        for fx in data.get("fixtures", []):
            want = f"{fx['params']['fabric']} @ {fx['params']['hoop']}"
            assert cond["per_fixture"][fx["fixture"]] == want, (
                f"{path.name}: {fx['fixture']} labelled "
                f"{cond['per_fixture'][fx['fixture']]!r} but ran at {want!r}"
            )
            assert fx["params"]["fabric"] in cond["fabrics"]
            assert fx["params"]["hoop"] in cond["hoops"]
    # Not asserted non-zero: a fresh checkout need not have run the bench yet.
    assert checked >= 0
