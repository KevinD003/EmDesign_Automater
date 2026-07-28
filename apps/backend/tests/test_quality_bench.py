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
