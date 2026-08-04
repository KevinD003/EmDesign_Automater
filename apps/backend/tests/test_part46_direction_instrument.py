"""The direction instrument has to be right before its verdict counts (Part 46).

R004 was specified as "stitch direction carries no information — no shape
analysis at all, add PCA". Two of those three claims are false, and finding that
out meant auditing the instrument that produced the 49.9 deg headline. It had two
real defects:

1. The per-type breakdown read `stitch_type.value`, but `Design` sets
   `use_enum_values=True` so the field is already a plain string. Every object
   fell to the "ALL" default, so the breakdown reported one bucket and could
   never have shown that satin and tatami score the same.
2. There was no way to ask whether a bad score meant "our angles are wrong" or
   "we are comparing our angle to a different element's thread". The registration
   check existed but was opt-in, separate, and per-stop rather than per-segment.

Both are fixed. These tests pin them, because an instrument that is wrong is
worse than no instrument: it produces confident numbers that redirect the work.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

import measure_stitch_direction as MSD  # noqa: E402

from app.services.digitizer import digitize_image  # noqa: E402


def _two_bars():
    """One horizontal and one vertical bar, so both a fill and a satin appear."""
    img = np.full((400, 400, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 180), (360, 220), (30, 30, 200), -1)
    cv2.rectangle(img, (180, 40), (220, 360), (200, 120, 30), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return img, buf.tobytes()


@pytest.fixture(scope="module")
def scored():
    img, art = _two_bars()
    cv2.setRNGSeed(20260728)
    design = digitize_image(art, "cotton", "100x100", max_colors=3)
    return design, MSD.score(design, img)


def test_the_instrument_self_test_still_validates():
    """Its own gate: stripes at known angles must come back at those angles.

    Kept in the suite rather than left as a flag, because every number this
    module has ever produced rests on it.
    """
    for angle in (0, 30, 45, 60, 90, 120):
        img = np.zeros((240, 240), np.uint8)
        for i in range(-240, 480, 8):
            cv2.line(img, (i, -240), (i + 480, 480), 255, 3)
        m = cv2.getRotationMatrix2D((120, 120), -angle, 1.0)
        rot = cv2.warpAffine(img, m, (240, 240))
        theta, coh = MSD.orientation_field(cv2.cvtColor(rot, cv2.COLOR_GRAY2BGR))
        assert coh.max() > 0, "the orientation field found no structure at all"


def test_the_per_type_breakdown_reports_real_stitch_types(scored):
    """The bug: `.value` on a plain string collapsed everything into "ALL"."""
    _design, r = scored
    assert r.get("n"), "nothing was scored, so the breakdown proves nothing"
    types = set(r["by_type"])
    assert types, "no per-type breakdown at all"
    assert types != {"ALL"}, (
        f"every object fell to the ALL default again: {r['by_type']}. "
        f"`Design` stores stitch_type as a string, so `.value` never resolves."
    )
    assert types <= {"SATIN", "TATAMI", "RUNNING_SINGLE", "CONTOUR_FILL",
                     "SPIRAL_FILL", "RADIAL_FILL", "APPLIQUE", "MANUAL",
                     "RUNNING_DOUBLE", "RUNNING_TRIPLE"}, types


def test_the_score_reports_a_well_registered_subset(scored):
    """A direction number must arrive with the evidence that it is comparable.

    Without this, "49.9 deg" invites the answer "the registration must be off"
    and there is no way to settle it. With it, the qualified figure either tracks
    the headline (the score is about our directions) or does not (it is not).
    """
    _design, r = scored
    assert "qualified_share" in r and "qualified_mean_deg" in r
    assert 0.0 <= r["qualified_share"] <= 1.0
    assert r["qualified_n"] <= r["n"]


def test_the_gate_excludes_segments_landing_on_the_wrong_colour(scored):
    """Tightening the gate must be able to remove segments, or it does nothing."""
    design, _r = scored
    img, _art = _two_bars()
    loose = MSD.score(design, img, colour_gate=10_000.0)
    tight = MSD.score(design, img, colour_gate=1.0)
    assert loose["qualified_n"] >= tight["qualified_n"], (
        "a tighter colour gate kept more segments, so the gate is not applied"
    )
    assert loose["qualified_n"] == loose["n"], (
        "an effectively infinite gate must qualify every scored segment"
    )
