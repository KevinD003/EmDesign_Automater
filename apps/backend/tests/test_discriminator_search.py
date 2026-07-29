"""Tests for scripts/discriminator_search.py (v2 Part 12, Part A item 1)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
for p in (str(BACKEND_ROOT), str(BACKEND_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import discriminator_search as DS


def test_both_real_violations_are_satin_realizable():
    """The anchor of the whole Part 11 argument: the two real fixture-07 triples
    are legitimate satin emissions AS THE SAME COORDINATES."""
    for _name, a, b, c in DS.REAL_REVERSALS:
        assert DS._violates(a, b, c)
        assert DS.satin_realizable(a, b, c)


def test_sampled_reversals_are_all_satin_realizable():
    rev = DS.sample_reversals(500, seed=1)
    assert rev, "the sampler must produce violating triples"
    assert all(DS.satin_realizable(*t) for t in rev)


def test_invariants_are_isometry_invariant():
    a, b, c = (1.0, 2.0), (3.0, 2.5), (1.1, 2.1)
    moved = [(x + 7.0, -y) for x, y in (a, b, c)]  # translate + reflect
    i1, i2 = DS._invariants(a, b, c), DS._invariants(*moved)
    assert all(abs(x - y) < 1e-12 for x, y in zip(i1, i2))


def test_balanced_accuracy_is_chance_on_identical_populations():
    pop = [0.1, 0.5, 0.9, 1.3]
    assert DS.best_threshold_accuracy(pop, list(pop)) == 0.5


def test_cli_runs_and_reports_the_constructive_result(capsys):
    assert DS.main(["--samples", "300"]) == 0
    out = capsys.readouterr().out
    assert "satin-realizable=True" in out
    assert "(100.0%)" in out
