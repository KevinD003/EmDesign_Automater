"""The fourteen exist, and the four baselines are the bytes they were measured on.

CI run 31658769064 was red on `main` while the local suite read green:

    1 failed, 1304 passed, 4 skipped, 2 deselected, 3 xfailed, 16 errors
    ERROR tests/test_stream_accounting.py::...[C24_many_colours]
          FileNotFoundError: .../corpus100/C24_many_colours.png

`.gitignore` excluded `corpus100/C*.png` as generated output, CI has no
generation step, and the four C-tier images the DET2 table cites by name
therefore existed only on a machine where `build_corpus100.py` had been run.
The local `1322 passed` was measured under a condition it did not state — which
is the exact failure the tranche that reported it was built to prevent. It
applies to "the suite passed" as much as to a stitch count.

Two separate things are pinned here, and they fail for different reasons:

  * **Presence.** All fourteen fixtures resolve to files that exist. Without
    this the suite can quietly shrink to ten and still report green, because a
    parametrised fixture that skips is not a failure.
  * **Identity.** The four baselines hash to the bytes SH2 measured. The
    gitignore's stated reason — "generated, regenerated with a fixed seed" — is
    right for a corpus and wrong for a baseline. C24 carries the 12.53 % figure
    the whole SH2 D1/D2 decision rests on. A baseline that regenerates is not a
    baseline; a regenerated image that differs must be caught, not silently
    accepted as the new reference.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from coverage_audit import CORPUS_DIR, CORPUS_EXTRA, fixtures

# Recorded from the tree that produced DET2's table (3e20a1f). If a rebuild of
# the corpus changes any of these, the numbers in DET2-COVERAGE and SH2-FINDINGS
# describe images that no longer exist and must be re-measured, not re-labelled.
BASELINE_SHA256 = {
    "C05_gradient_field": "0b485f5b49b55b34593e24df6c6645889423b192758dc2da8e6badea0004fef1",
    "C11_many_colours": "5f28c0da66bb6599096ca63147adbc7593c068c833efb8ce68e600037df0336f",
    "C18_gradient_field": "130bab06c7a69969e1b8848b9caec1f7763b6faed17309d1b0c21dda477f7031",
    "C24_many_colours": "5effb8a85b574b868609fbf772ad29a14df658ff36b9562207a4928c9f8520a6",
}


def test_the_four_named_baselines_are_the_ones_this_file_knows_about():
    """Guards the guard: if `CORPUS_EXTRA` grows, this file must grow with it."""
    assert set(CORPUS_EXTRA) == set(BASELINE_SHA256), (
        "coverage_audit.CORPUS_EXTRA and BASELINE_SHA256 disagree. A fifth "
        "baseline needs its hash pinned here and its filename un-ignored in "
        ".gitignore, or it will pass locally and error in CI."
    )


@pytest.mark.parametrize("name", sorted(BASELINE_SHA256))
def test_a_baseline_is_tracked_and_unchanged(name: str):
    path = CORPUS_DIR / f"{name}.png"
    assert path.exists(), (
        f"{path} is missing. It is a committed baseline, not generated output — "
        f"check the .gitignore exception for it survived."
    )
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    assert got == BASELINE_SHA256[name], (
        f"{name} is not the image DET2 and SH2 were measured on.\n"
        f"  expected {BASELINE_SHA256[name]}\n  got      {got}\n"
        f"If the corpus generator changed deliberately, re-measure the tables in "
        f"docs/DET2-COVERAGE-2026-08-13.md and docs/SH2-FINDINGS-2026-08-10.md "
        f"and update this hash in the same commit. Do not update the hash alone."
    )


def test_all_fourteen_fixtures_are_present():
    """The suite must not be able to shrink to ten and still read green.

    Every harness that measures "the fourteen" — coverage_audit, trace,
    test_stream_accounting — resolves them through `coverage_audit.fixtures()`.
    A parametrised case whose file is absent skips, and a skip is not a failure,
    so ten-of-fourteen coverage would report exactly as green as fourteen. This
    is the one place that says no.
    """
    missing = [str(p) for _n, p, _params in fixtures() if not Path(p).exists()]
    assert not missing, (
        "fixtures missing from the working tree — the fourteen-fixture tables "
        "cannot be reproduced here:\n  " + "\n  ".join(missing)
    )
