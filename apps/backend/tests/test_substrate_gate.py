"""The substrate gate is perceptual, and the superseded constant stays retired.

Shipped 2026-08-25. The rule that decides "this colour cluster IS the garment"
compared colours with Euclidean distance in BGR, which is not a perceptual
quantity. Measured cost on A02, the black neckline panel: 4,638 penetrations —
5.80 machine-minutes per garment at 800 spm — sewn in near-black thread on black
cloth, because `#080808` is 13.856 from pure black in BGR against a 12.0 gate.

Two things are pinned here and they fail for different reasons.

  * **The metric is perceptual and its threshold is derived.** `SUBSTRATE_DE2000`
    is 2.0 — "perceptible at a glance", the level that matches what the rule
    ASKS (would a customer see thread on cloth?) rather than CIEDE2000's unit
    JND, which is a trained observer under controlled viewing. Measured, the JND
    fails twice: A02 reads 1.263 so 1.0 does not fix it, and fixture 02's page
    reads 1.092 so 1.0 would newly KEEP 15,893 px of page as artwork.

  * **The retired constant stays retired.** `SUBSTRATE_DELTA` is still defined so
    the metric survey can print a before-column, and a retired constant that
    quietly stays wired is how two thresholds come to disagree. Nothing in
    `app/` may compare against it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.digitizer.colordiff import bgr_ciede2000
from app.services.digitizer.constants import SUBSTRATE_DE2000, SUBSTRATE_DELTA

APP = Path(__file__).resolve().parents[1] / "app"


def test_the_superseded_bgr_constant_is_not_compared_against_anywhere():
    """Guards the retirement. `SUBSTRATE_DELTA` may be DEFINED and EXPORTED, but
    a comparison against it would mean two gates are live at once."""
    offenders = []
    for py in APP.rglob("*.py"):
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if "SUBSTRATE_DELTA" not in code:
                continue
            # A definition, an import or an __all__ entry is fine; a comparison
            # is not.
            if re.search(r"[<>]=?\s*SUBSTRATE_DELTA|SUBSTRATE_DELTA\s*[<>]=?", code):
                offenders.append(f"{py.relative_to(APP)}:{n}: {line.strip()}")
    assert not offenders, (
        "SUBSTRATE_DELTA is the SUPERSEDED Euclidean-BGR gate and is kept only so "
        "scripts/measure_substrate_metric.py can report a before-column. A live "
        "comparison against it means two substrate thresholds disagree:\n  "
        + "\n  ".join(offenders)
    )


def test_the_defect_that_motivated_the_change_is_gated_in_now():
    """A02's `#080808` against pure black: the 5.80-machine-minute cluster."""
    assert bgr_ciede2000((8, 8, 8), (0, 0, 0)) < SUBSTRATE_DE2000


def test_the_unit_jnd_would_NOT_have_fixed_it():
    """Recorded as a test because both the CTO and I reasoned from the JND and
    the corpus refuted it. If someone later "simplifies" the threshold to 1.0,
    this says what that costs."""
    assert bgr_ciede2000((8, 8, 8), (0, 0, 0)) > 1.0


def test_a_page_that_is_nearly_white_is_still_the_page():
    """Fixture 02's `#fafafa` against white — 1.092, so the unit JND would have
    newly KEPT it and sewn 15,893 px of page as artwork. At 2.0 it is correctly
    still substrate. This is the near-white regression the change must not
    introduce while fixing the near-black one."""
    assert bgr_ciede2000((250, 250, 250), (255, 255, 255)) < SUBSTRATE_DE2000


def test_real_cream_artwork_on_a_near_white_page_survives():
    """Fixture 07's `#f8f4e8` reads dE2000 5.986 — real artwork, and the far
    edge of the plateau the threshold sits in. If a future threshold rises past
    this, the badge's cream loses its thread."""
    assert bgr_ciede2000((232, 244, 248), (255, 255, 255)) > SUBSTRATE_DE2000


@pytest.mark.parametrize("threshold", [1.30, 2.0, 3.0, 4.0, 5.9])
def test_the_plateau_makes_the_exact_threshold_inconsequential(threshold):
    """Every value in [1.263, 5.986) gives identical verdicts on the corpus's
    near-gate clusters. The number is not fitted; it is a point in a 4.7-wide
    gap, and this shows the gap is real rather than asserted. The sweep starts
    just ABOVE 1.263 because the plateau is half-open at that end: at exactly
    1.263 the strict `<` leaves A02 on the wrong side, which is the boundary
    condition rather than a counter-example."""
    black = bgr_ciede2000((8, 8, 8), (0, 0, 0))          # 1.263, must be substrate
    page = bgr_ciede2000((250, 250, 250), (255, 255, 255))  # 1.092, must be substrate
    cream = bgr_ciede2000((232, 244, 248), (255, 255, 255))  # 5.986, must be artwork
    assert black < threshold, "A02's near-black must be substrate at every plateau point"
    assert page < threshold, "the page must stay substrate at every plateau point"
    assert cream > threshold, "07's cream must stay artwork at every plateau point"


def test_the_two_constants_are_not_confusable():
    """One is a BGR distance, one is a dE. Both are floats near a small number,
    which is exactly how a unit error ships."""
    assert SUBSTRATE_DELTA == 12.0 and SUBSTRATE_DE2000 == 2.0


# ── The assertion that shares NO constant with the gate ──────────────────────
#
# Everything above compares against `SUBSTRATE_DE2000`, and so does every
# assertion in test_part41 and test_part45. That family can catch the gate being
# BYPASSED and can never catch the gate being WRONG, because both sides move
# together by construction. It is not a hypothetical limit: test_part41 is the
# regression test for "no thread in the garment colour" and it PASSED on A02
# while A02 sewed 4,638 stitches of black on black, because 13.856 >= 12.0.
#
# So this one names no gate constant. Its threshold is 3.0 dE2000, justified
# independently below and deliberately LOOSER than the live gate, so that
# raising `SUBSTRATE_DE2000` toward it does not silently satisfy this too.

#: Two colours this far apart in CIEDE2000 are "clearly different" — well past
#: perceptible-at-a-glance. Justified by the render examined on 2026-08-22: A02's
#: black-on-black regions were INVISIBLE in the sew-out preview, and the nearest
#: real artwork in the whole corpus (07's cream, 5.986) sits at twice this. Any
#: stop closer than this to the cloth is thread the customer cannot see.
INVISIBLE_ON_CLOTH_DE2000 = 3.0


def test_a02_sews_nothing_in_its_garment_colour():
    """THE ASSERTION THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT.

    No gate constant appears here. It states the product requirement directly —
    a real photograph of a black garment must not come back with stitches in a
    thread the customer cannot distinguish from the cloth — and it is measured
    on penetrations, not on cluster distances, because penetrations are what
    cost machine time.

    Before the fix this read 4,638 penetrations, 21.0 % of the design, 5.80
    machine-minutes per garment. VERIFIED TO BITE rather than assumed to: re-run
    with `SUBSTRATE_DE2000` forced to 1.0 -- the unit JND both the CTO and I
    first reasoned toward -- it fails with exactly those 4,638 penetrations. So
    it catches the original defect AND the threshold choice that would have
    shipped it, which is more than the gate-constant family can do. It is the fixture's own conditions from
    `A_TIER_PARAMS`, so a change to the promoted parameters moves the test with
    the corpus rather than leaving it measuring something else.
    """
    import cv2

    from app.services.digitizer import digitize_image
    from coverage_audit import A_TIER_PARAMS, CORPUS_DIR
    from run_quality_bench import RNG_SEED

    name = "A02_real_neckline_black"
    src = CORPUS_DIR / f"{name}.png"
    if not src.exists():                       # skip, never error — CI has no generator
        pytest.skip(f"{src} is missing; test_corpus_baseline_fixtures asserts its presence")
    params = A_TIER_PARAMS[name]
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        src.read_bytes(), fabric_type=params["fabric"],
        hoop_size=params["hoop"], max_colors=params["colors"],
    )
    # The garment, inferred exactly as the pipeline infers it: this fixture's
    # border is pure black. Stated as a literal rather than re-running
    # `_border_color`, so the test does not share THAT machinery either.
    substrate = (0, 0, 0)
    invisible = [
        (s.hex, int(s.penetration_count))
        for s in design.color_stops
        if bgr_ciede2000(
            (int(s.hex.lstrip("#")[4:6], 16), int(s.hex.lstrip("#")[2:4], 16),
             int(s.hex.lstrip("#")[0:2], 16)), substrate) < INVISIBLE_ON_CLOTH_DE2000
    ]
    wasted = sum(p for _h, p in invisible)
    assert wasted == 0, (
        f"{wasted} penetrations ({wasted / 800.0:.2f} machine-minutes at 800 spm) "
        f"are sewn in thread indistinguishable from the garment: {invisible}"
    )
