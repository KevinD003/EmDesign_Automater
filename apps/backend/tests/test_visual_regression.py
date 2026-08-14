"""Committed visual regression for digitized output (v2 Part 44, R003).

Parts 39, 40 and 41 each found a defect that no metric flagged — a split lobe, a
flooded lattice, a lost bead-chain ornament, thread laid on bare cloth — and each
was found by looking at a picture produced by a script that was never committed.
So the check has never been repeatable, and the reviewer's P004 was right about
that even though it was wrong about the reason.

These tests close it. Ten bench fixtures are digitized at the bench's own pinned
configuration, rendered, and compared to committed baselines.

To accept an intended change:  scripts/visual_regression.py --update
To look at everything at once: scripts/visual_regression.py --contact-sheet
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

import visual_regression as VR  # noqa: E402

from app.services.stitch_render import render_design  # noqa: E402


@pytest.mark.parametrize("fixture", sorted(VR.FIXTURES))
def test_render_matches_its_baseline(fixture: str) -> None:
    actual, _design = VR.render_fixture(fixture)
    v = VR.compare(fixture, actual)
    why = v.get("reason") or f"SSIM {v.get('ssim')} < {VR.SSIM_GATE}"
    assert v["ok"], (
        f"{fixture}: {why}. "
        f"A diff strip (baseline | current | changed pixels in red) was written to "
        f"{v.get('diff')}. Look at it: if the change is intended, re-run "
        f"scripts/visual_regression.py --update and commit the new baselines."
    )


def test_the_renderer_is_deterministic() -> None:
    """The whole harness rests on this. Two renders of one design must be identical.

    Without it, a baseline comparison measures renderer noise and the gate has to
    be loosened until it stops catching anything.
    """
    _actual, design = VR.render_fixture("04_thin_line_outline")
    a, b = render_design(design), render_design(design)
    assert (a == b).all(), "render_design is not a pure function of the Design"


def test_the_gate_is_tight_enough_to_catch_a_real_change() -> None:
    """A harness that cannot fail is decoration.

    Turning the penetration floor off is a genuine pipeline change, and it must
    score below the gate. Measured across the ten fixtures it lands at SSIM
    0.909-0.993 — every one of which would PASS the 0.85 threshold a photo-
    comparison harness would use. That is why the gate here is 0.995: on a
    deterministic renderer, an unchanged pipeline scores exactly 1.000000, so
    anything less is a real difference and there is no noise to allow for.
    """
    from app.services.digitizer import MIN_PENETRATION_MM, set_penetration_floor

    try:
        set_penetration_floor(None)
        actual, _ = VR.render_fixture("07_circular_badge")
        v = VR.compare("07_circular_badge", actual, write_diff=False)
    finally:
        set_penetration_floor(MIN_PENETRATION_MM)

    assert not v["ok"], "disabling the penetration floor must fail the visual gate"
    assert v["ssim"] > 0.85, (
        "sanity check on the argument above: this change really does score above "
        "0.85, so a 0.85 gate would have let it through silently"
    )


def test_every_baseline_is_committed() -> None:
    """A missing baseline silently skips a fixture in the CLI; here it fails."""
    missing = [n for n in VR.FIXTURES if not (VR.BASELINE_DIR / f"{n}.png").exists()]
    assert not missing, f"no committed baseline for: {missing}"


def test_the_render_table_is_the_audit_table() -> None:
    """Pictures and numbers must describe the same run, so there is ONE table —
    now the larger one (CTO ruling 2026-08-22, Option A).

    This asserted `VR.FIXTURES is FIXTURE_PARAMS` — deliberately anti-drift,
    and correct as far as it went. What it pinned, though, was the render table
    to the BENCH TEN while the audit set is sixteen, so four fixtures that
    every numeric harness measures had no picture at all. C24 is the fixture
    the SH2 D1/D2 decision turns on; the noise-sewing defect was caught on 09
    only because 09 has a render.

    Identity (`is`) cannot be asserted any more because the table is built by a
    comprehension over `fixtures()`, so EQUALITY of names and params is
    asserted instead — and, separately, that path resolution comes from the
    same call rather than a second hard-coded directory.
    """
    from coverage_audit import fixtures

    audit = {name: params for name, _path, params in fixtures()}
    assert VR.FIXTURES == audit, "the render table drifted from the audit table"
    assert set(VR.FIXTURE_PATHS) == set(audit), "a fixture has params but no path"
    for name, path, _params in fixtures():
        assert VR.FIXTURE_PATHS[name] == path, (
            f"{name}: the render harness resolves a different file than the "
            f"audit does — path resolution must live in one place"
        )


def test_fixture_02_still_stitches_its_wordmark() -> None:
    """The white type on the green card must survive digitizing.

    Part 41 made a garment-coloured cluster never stitch on raster input, to stop
    thread being laid on bare cloth between a design's elements. On this fixture
    the white wordmark 'NORTHFIELD / EST. 1974 - SUPPLY CO.' sits inside a green
    card, and the page behind the card is also white — so the type reads as
    substrate and is dropped whole.

    Measured at c62bf33 (before Part 41): 4 colour stops including #fafafa with 31
    stitches, 7 objects, 6,221 stitches. Now: 3 stops, 6 objects, 6,185 stitches.
    The entire wordmark is gone, and no metric noticed because coverage is scored
    against the objects that WERE emitted.

    Fixed in Part 45: the substrate rule now keys on whether the input is a
    photograph of cloth or flat artwork on a page, and on flat art only drops
    substrate-coloured regions that reach the page or are too large to be
    knocked-out detail. See docs/benchmarks/v2-part45-audit.md.
    """
    _actual, design = VR.render_fixture("02_logo_fine_text_3color")
    hexes = {s.hex.lower() for s in design.color_stops}
    assert any(h not in ("#0f5a4b", "#f0c33c") for h in hexes), (
        f"the wordmark's thread colour is missing; stops are {sorted(hexes)}"
    )
