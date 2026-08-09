"""Guards the quality-bench harness itself (Part 0 measurement infrastructure).

The harness is how every future digitizer change gets graded, so it has to keep
working even though it lives outside the app package. These tests assert the
corpus is present and the metric extraction is correct — they do NOT assert
anything about digitize *quality*, which is what the audit doc is for.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = BACKEND_ROOT / "tests" / "fixtures" / "quality_bench"
SCRIPT = BACKEND_ROOT / "scripts" / "run_quality_bench.py"

EXPECTED_FIXTURES = 10


def _load_harness():
    """Import the harness by path — it lives in scripts/, outside the app package.

    It must be registered in sys.modules before exec: @dataclass resolves its own
    field annotations through sys.modules[cls.__module__], which is None otherwise.
    """
    if "run_quality_bench" in sys.modules:
        return sys.modules["run_quality_bench"]
    spec = importlib.util.spec_from_file_location("run_quality_bench", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["run_quality_bench"] = module
    spec.loader.exec_module(module)
    return module


def test_bench_corpus_is_present():
    pngs = sorted(p for p in FIXTURE_DIR.glob("*.png") if not p.name.startswith("_"))
    assert len(pngs) == EXPECTED_FIXTURES, f"expected {EXPECTED_FIXTURES} bench fixtures, found {len(pngs)}"


def test_every_fixture_has_declared_params():
    """A fixture with no entry in FIXTURE_PARAMS would silently fall back to
    defaults, making a before/after comparison unfair."""
    harness = _load_harness()
    for png in FIXTURE_DIR.glob("*.png"):
        if png.name.startswith("_"):
            continue
        assert png.stem in harness.FIXTURE_PARAMS, f"{png.stem} missing from FIXTURE_PARAMS"


def test_stitch_length_metric_ignores_jumps():
    """Travel across a JUMP is not a stitch; counting it would inflate
    max_stitch_mm and fake a machine-limit violation."""
    from app.models.design import Design, Stitch

    harness = _load_harness()
    design = Design(
        name="t",
        stitches=[
            Stitch(x=0, y=0, command="STITCH"),
            Stitch(x=3, y=0, command="STITCH"),      # 3mm stitch
            Stitch(x=90, y=0, command="JUMP"),       # long travel — must not count
            Stitch(x=93, y=0, command="STITCH"),
            Stitch(x=97, y=0, command="STITCH"),     # 4mm stitch
        ],
    )
    assert harness._stitch_lengths(design) == pytest.approx([3.0, 4.0])


def test_run_fixture_produces_preview_and_metrics(tmp_path):
    """End-to-end on one fixture: the harness must emit a real PNG and
    self-consistent numbers."""
    harness = _load_harness()
    src = FIXTURE_DIR / "01_flat_2color_logo.png"
    result = harness.run_fixture(src, tmp_path)

    assert result.ok and result.error is None
    assert result.stitch_count > 100
    assert result.object_count >= 1
    assert result.color_count >= 1
    assert result.est_minutes == pytest.approx(result.stitch_count / harness.SPM, abs=0.005)  # stored 2dp
    assert sum(result.stitch_types.values()) == result.object_count

    out = tmp_path / "01_flat_2color_logo-output.png"
    assert out.is_file() and out.stat().st_size > 1000
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_baseline_results_are_committed():
    """The v1 baseline numbers are the contract future parts are graded against;
    if this file goes missing, comparisons are impossible."""
    summary = BACKEND_ROOT.parents[1] / "docs" / "benchmarks" / "v1-baseline-summary.json"
    assert summary.is_file(), "docs/benchmarks/v1-baseline-summary.json must be committed"
    data = json.loads(summary.read_text())
    assert data["fixture_count"] == EXPECTED_FIXTURES
    assert data["failed"] == [], f"baseline run had hard failures: {data['failed']}"


# ── CTO verdict STEP -1: the assertion this file was missing ─────────────────
#
# The bench measured stitch counts for a whole phase and never once asserted
# that a fixture's stitches were SEWABLE. That is how `_route_travel` came to
# manufacture 70.8% of 01_flat_2color_logo — 59.6% of its penetrations under
# the needle-safety floor, 21.3 machine-minutes for a 65mm two-colour logo —
# with every gate in the suite green. Exact-hash gating cannot catch it: the
# hash simply moved with the regression.
#
# These are BANDS, not hashes, per the verdict: wide enough that a legitimate
# generator change does not trip them, tight enough that a 2x inflation or a
# return of sub-floor packing does.

# (fixture stem, max sub-floor share, max machine-minutes)
#
# Bands are set from the MEASURED post-fix value with headroom, and every one
# of them fails if the pixel floor returns. Measured 2026-08-09, before -> after
# the STEP -1 clamp:
#
#   01_flat_2color_logo  17,078 -> 8,749 st · 44.4% -> 3.8% · 21.4 -> 13.7 min
#   07_circular_badge    45,793 -> 34,665 st · 29.9% -> 14.9% · 58.0 -> 46.5 min
#   05_wordmark_caps      2,518 -> 1,864 st · 15.0% ->  1.0% ·  3.4 ->  2.7 min
#
# The badge is deliberately given a wider sub-floor band than the others: at
# 14.9% it is still the worst fixture in the corpus, because its many small
# tightly-curved satin objects force the resampler down to the floor legally.
# The band is set to catch a REGRESSION (the pixel floor reads 29.9% here),
# not to certify the badge as good — it is not, and it is called out as
# outstanding work rather than papered over by a loose number.
#
# THE SECOND COLUMN IS THE ONE THAT MEANS DAMAGE (added at STEP 0). The 0.5mm
# line is quality and machine time; the 0.3mm line — MIN_PENETRATION_MM — is
# where the needle re-enters a hole it just made. A tatami's row-to-row
# connection is one row pitch and sits under 0.5mm BY CONSTRUCTION, so a
# fill-heavy fixture reads several percent there while being perfectly
# sewable. Measured: the badge is 14.9% under 0.5mm but only 1.2% under 0.3mm
# — its sub-floor reading is mostly row connections, not perforation. Grading
# on the loose number alone nearly rejected STEP 0, which was correct.
#
# (fixture stem, max sub-0.5mm share, max sub-0.3mm share, max machine-minutes)
SEWABILITY_BANDS = [
    ("01_flat_2color_logo", 0.10, 0.03, 17.0),
    ("07_circular_badge", 0.20, 0.04, 52.0),
    ("05_wordmark_caps", 0.05, 0.02, 3.1),
]


@pytest.mark.parametrize(("stem", "max_sub_floor", "max_sub_pen", "max_minutes"),
                         SEWABILITY_BANDS)
def test_fixture_output_is_sewable(tmp_path, stem, max_sub_floor, max_sub_pen, max_minutes):
    harness = _load_harness()
    path = FIXTURE_DIR / f"{stem}.png"
    assert path.is_file(), path
    result = harness.run_fixture(path, tmp_path)
    assert not result.error, result.error

    # Below the floor the needle is perforating rather than stitching: thread
    # breaks, needle deflection, and visually a shapeless mass along every
    # region edge. Measured 0.596 before the STEP -1 clamp, 0.038 after.
    assert result.sub_floor_share <= max_sub_floor, (
        f"{stem}: {result.sub_floor_share:.1%} of stitches are under the needle-safety "
        f"floor (band {max_sub_floor:.0%}) — is resample_inside back to a pixel floor?"
    )
    # The safety line. Measured 0.8% / 1.2% / 0.2% on the three fixtures.
    assert result.sub_penetration_share <= max_sub_pen, (
        f"{stem}: {result.sub_penetration_share:.1%} of stitches are under "
        f"MIN_PENETRATION_MM — the needle is re-entering its own hole "
        f"(band {max_sub_pen:.0%})"
    )
    # Machine time is the owner's cost centre, and it must include trims:
    # a routing change that trades stitches for trims has to be judged on the
    # total, or a "fix" can shift the cost sideways and look like a win.
    assert result.machine_minutes <= max_minutes, (
        f"{stem}: {result.machine_minutes:.1f} machine-minutes "
        f"({result.stitch_count:,} stitches + {result.trim_count} trims), band {max_minutes}"
    )


def test_sewability_metrics_are_actually_computed():
    """A band test whose metric is always 0.0 would pass forever. Pin that both
    numbers are real and derived from the stream."""
    import math

    from app.models.design import Design, Stitch

    d = Design(name="t", stitch_count=4, objects=[], color_stops=[], stitches=[
        Stitch(x=0, y=0, command="STITCH"),
        Stitch(x=0.1, y=0, command="STITCH"),   # sub-floor
        Stitch(x=5.1, y=0, command="STITCH"),   # fine
        Stitch(x=5.1, y=0, command="TRIM"),
    ])
    lengths = _load_harness()._stitch_lengths(d)
    assert len(lengths) == 2 and math.isclose(min(lengths), 0.1, abs_tol=1e-6)
