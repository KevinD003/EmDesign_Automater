"""The sixteen exist, and the six baselines are the bytes they were measured on.

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

  * **Presence.** All sixteen fixtures resolve to files that exist. Without
    this the suite can quietly shrink to ten and still report green, because a
    parametrised fixture that skips is not a failure.
  * **Identity.** The six baselines hash to the bytes they were measured on. The
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

from coverage_audit import A_TIER_PARAMS, CORPUS_DIR, CORPUS_EXTRA, fixtures

# Recorded from the tree that produced DET2's table (3e20a1f). If a rebuild of
# the corpus changes any of these, the numbers in DET2-COVERAGE and SH2-FINDINGS
# describe images that no longer exist and must be re-measured, not re-labelled.
#
# A01/A02 joined on 2026-08-22 with the promotion. The enumeration of 2026-08-21
# predicted this exact gap: the C-tier guard asserts against `CORPUS_EXTRA`
# alone, so two newly-cited real photographs would have entered the standing set
# UNPINNED — "which is precisely the argument that got the C-tier four pinned".
# Unlike the C-tier they are not generated, so they cannot silently regenerate;
# they can still be re-exported, re-compressed or cropped, and the tranche's
# tables would then describe images that no longer exist.
BASELINE_SHA256 = {
    "C05_gradient_field": "0b485f5b49b55b34593e24df6c6645889423b192758dc2da8e6badea0004fef1",
    "C11_many_colours": "5f28c0da66bb6599096ca63147adbc7593c068c833efb8ce68e600037df0336f",
    "C18_gradient_field": "130bab06c7a69969e1b8848b9caec1f7763b6faed17309d1b0c21dda477f7031",
    "C24_many_colours": "5effb8a85b574b868609fbf772ad29a14df658ff36b9562207a4928c9f8520a6",
    "A01_real_peacock_patch_photo":
        "1bc6dbc30feec3f558aa3d2fa98ec9f0e74b679cb2c546d550c015269f4f2c87",
    "A02_real_neckline_black":
        "351e5b145526ec7c10ea1c2d377b59e674bf6ce3eebf0d8a55fe86fc7db1e46c",
}


def test_the_named_baselines_are_the_ones_this_file_knows_about():
    """Guards the guard: if the corpus part of the standing set grows, this file
    must grow with it. It reads BOTH corpus tiers, because the version that read
    only `CORPUS_EXTRA` would have let the A-tier promotion through unpinned."""
    assert set(CORPUS_EXTRA) | set(A_TIER_PARAMS) == set(BASELINE_SHA256), (
        "coverage_audit's corpus tiers and BASELINE_SHA256 disagree. A new "
        "corpus baseline needs its hash pinned here and its filename un-ignored "
        "in .gitignore, or it will pass locally and error in CI."
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


def test_the_whole_standing_set_is_present():
    """The suite must not be able to shrink and still read green.

    Every harness that measures the standing set — coverage_audit, trace,
    visual_regression, test_stream_accounting — resolves it through
    `coverage_audit.fixtures()`. A parametrised case whose file is absent skips,
    and a skip is not a failure, so ten-of-sixteen coverage would report exactly
    as green as sixteen. This is the one place that says no.

    Deliberately NOT spelled "sixteen" in the name: the set has been ten, then
    fourteen, then sixteen, and the previous name went stale in the same commit
    that changed the count.
    """
    missing = [str(p) for _n, p, _params in fixtures() if not Path(p).exists()]
    assert not missing, (
        "fixtures missing from the working tree — the standing-set tables "
        "cannot be reproduced here:\n  " + "\n  ".join(missing)
    )


def test_the_standing_set_is_sixteen_in_three_declared_tiers():
    """The size is asserted somewhere, once, with its composition.

    Not to freeze it — it will change again — but so that a change to the set
    cannot be a silent side effect of editing one table. The count and the tier
    breakdown move together or the test says so.
    """
    from coverage_audit import CORPUS_PARAMS  # noqa: F401 — tier existence
    from run_quality_bench import FIXTURE_PARAMS

    rows = fixtures()
    assert len(rows) == 16, f"standing set is {len(rows)}, expected 16"
    names = [n for n, _p, _q in rows]
    assert len(set(names)) == 16, "a fixture is enumerated twice"
    assert sum(n in FIXTURE_PARAMS for n in names) == 10
    assert sum(n in CORPUS_EXTRA for n in names) == 4
    assert sum(n in A_TIER_PARAMS for n in names) == 2
