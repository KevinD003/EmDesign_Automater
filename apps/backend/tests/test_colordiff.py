"""CIEDE2000 is verified BEFORE anything depends on it (CTO ruling 2026-08-25).

The substrate gate is about to stop being a Euclidean BGR constant and start
being a perceptual threshold. That makes the colour-difference formula
load-bearing on 5.80 machine-minutes per garment, and a hand-written
implementation of a formula with two well-known traps — the undefined mean hue
at zero chroma, and the wrap of the h' difference — is exactly the kind of thing
this repository refuses to build a headline on unverified.

THE VERIFICATION CHAIN, STATED HONESTLY. `ciede2000` here is checked against
`skimage.color.deltaE_ciede2000`, which is itself checked against Sharma, Wu &
Dalal's published pairs upstream. That is one step removed from a first-hand
Sharma verification and is not described as one. Four of Sharma's pairs are also
asserted directly, including the two that catch the traps.

skimage is NOT a runtime dependency — nothing in requirements*.txt names it, and
`colordiff` deliberately does not import it (see its docstring). It is present
transitively here, so the cross-check runs when it can and skips when it cannot.
The direct Sharma pairs always run, so this file is never vacuous.
"""

from __future__ import annotations

import math

import pytest

from app.services.digitizer.colordiff import (
    bgr_ciede2000,
    ciede2000,
    srgb_to_lab,
)

# Sharma, Wu & Dalal (2005) test data — four pairs chosen for what they catch,
# not at random:
#   #1  ordinary blue pair, the everyday case
#   #4  a pair the formula must return exactly 1.0000 for
#   #7  ZERO CHROMA on one side: the h-bar convention trap
#   #9  opposite hues at low chroma: the h' wrap and R_T rotation trap
SHARMA = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
]


@pytest.mark.parametrize(("lab1", "lab2", "expected"), SHARMA)
def test_sharma_published_pairs(lab1, lab2, expected):
    assert ciede2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize(("lab1", "lab2", "expected"), SHARMA)
def test_the_formula_is_symmetric(lab1, lab2, expected):
    """dE(a,b) == dE(b,a). Asserted, not assumed — an asymmetric implementation
    would make the gate depend on which colour was called the substrate."""
    assert ciede2000(lab2, lab1) == pytest.approx(ciede2000(lab1, lab2), abs=1e-9)


def test_identical_colours_are_zero():
    for lab in [(0.0, 0.0, 0.0), (50.0, 12.0, -30.0), (100.0, 0.0, 0.0)]:
        assert ciede2000(lab, lab) == pytest.approx(0.0, abs=1e-12)


def test_the_conversion_reproduces_the_number_the_substrate_argument_rests_on():
    """sRGB(8,8,8) -> L* ~= 2.19, i.e. under the ~2.3 JND against pure black.

    This single value is why the substrate gate changes: BGR calls the same pair
    13.856. The tolerance is loose on purpose — OpenCV's float32 path gives
    2.185 and this exact-arithmetic path gives 2.193, and that 0.008 spread is
    recorded in `colordiff`'s docstring rather than hidden by a tight bound.
    """
    L, a, b = srgb_to_lab((8, 8, 8))
    assert L == pytest.approx(2.19, abs=0.01)
    assert a == pytest.approx(0.0, abs=1e-6) and b == pytest.approx(0.0, abs=1e-6)
    assert bgr_ciede2000((8, 8, 8), (0, 0, 0)) < 2.3


def test_a_grey_pair_is_nearer_than_euclid_says():
    """The mechanism in one assertion: BGR over-states difference near black."""
    euclid = math.sqrt(3 * 8.0 ** 2)
    assert euclid == pytest.approx(13.856, abs=1e-3)
    assert bgr_ciede2000((8, 8, 8), (0, 0, 0)) < euclid / 5.0


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_agrees_with_skimage_across_random_lab_pairs(seed):
    """Cross-check against an independently maintained implementation.

    Random over the whole Lab gamut rather than near the gate: an error in the
    hue-rotation term shows up in saturated colours, which is precisely the
    region dE76 could not speak to and the region the survey's null result is
    weakest in.
    """
    np = pytest.importorskip("numpy")
    color = pytest.importorskip(
        "skimage.color",
        reason="scikit-image is not a runtime dependency; the Sharma pairs above "
               "still run, so this file is never vacuous",
    )
    rng = np.random.default_rng(seed)
    a = np.column_stack([rng.uniform(0, 100, 400),
                         rng.uniform(-128, 127, 400),
                         rng.uniform(-128, 127, 400)])
    b = np.column_stack([rng.uniform(0, 100, 400),
                         rng.uniform(-128, 127, 400),
                         rng.uniform(-128, 127, 400)])
    ref = color.deltaE_ciede2000(a, b)
    worst = 0.0
    for i in range(len(a)):
        got = ciede2000(tuple(a[i]), tuple(b[i]))
        worst = max(worst, abs(got - float(ref[i])))
    assert worst < 1e-6, f"worst disagreement with skimage: {worst}"
