"""Perceptual colour difference: CIEDE2000, and the sRGB->Lab conversion it reads.

WHY THIS EXISTS. The substrate rule asks "is this colour cluster the garment?"
and answered it with Euclidean distance in BGR. That is not a perceptual
quantity, and the cost was measured: A02 sews 4,638 penetrations — 5.80
machine-minutes per garment at 800 spm — in near-black thread on black cloth,
because `#080808` is 13.856 from pure black in BGR against a 12.0 gate while
being, to a human, the same colour.

THE ARGUMENT LEADS WITH INVARIANCE, NOT WITH THE JND (CTO ruling 2026-08-24,
which rated this the stronger of the two forms):

    A PERCEPTUAL METRIC IS INVARIANT TO THE PIPELINE'S OWN PREPROCESSING; A BGR
    CONSTANT IS NOT, AND NOTHING WARNED WHEN THE PREPROCESSING LANDED.

Measured by ablation: with the textured path's mean-shift filter disabled A02's
darkest cluster reads BGR 8.2 and is deleted; with it enabled, 13.3 and sewn.
The verdict flipped because of OUR smoothing, not because the garment changed.
Across the same ablation dE76 moves 1.67 -> 2.05 and dE2000 stays under the JND
on both sides. The threshold argument — a JND is derived where 12.0 was fitted
— is true and secondary.

## Why hand-written rather than imported

`scikit-image` ships a `deltaE_ciede2000` and IS importable in this environment,
but it is a transitive dependency (nothing in requirements*.txt asks for it) and
this repository has already declined to add it for one function — see
`visual_regression.ssim`, twenty lines rather than a large dependency every
installer pays for. Shipping pipeline behaviour on a package the requirements do
not name would be worse than either choice made deliberately.

So the formula is implemented here and VERIFIED AGAINST skimage in
`tests/test_colordiff.py`, which skips when skimage is absent. State the chain
honestly: this implementation is checked against an implementation that is
itself checked against Sharma, Wu & Dalal's published pairs upstream — plus four
of those pairs asserted directly here. It is not a first-hand Sharma
verification and is not described as one.

## The conversion is part of the contract

A dE means nothing without the Lab it was computed from. `srgb_to_lab` uses the
sRGB transfer function and the D65 white point, matching OpenCV's
`COLOR_BGR2Lab` on float32 input; both give L* = 2.185 for sRGB(8,8,8) where the
CIE formula by hand gives 2.193. That 0.008 is immaterial inside the 5.2-wide
plateau the corpus shows, and it is recorded rather than resolved because a
verification depends on knowing which conversion fed it.
"""

from __future__ import annotations

import math

# D65, 2-degree observer — the white point sRGB is defined against.
_XN, _YN, _ZN = 0.95047, 1.00000, 1.08883


def _linearize(c: float) -> float:
    """sRGB transfer function, inverse. `c` in 0-1."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _f(t: float) -> float:
    return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (841.0 / 108.0) * t + 4.0 / 29.0


def srgb_to_lab(rgb) -> tuple[float, float, float]:
    """sRGB (0-255, R G B order) -> CIE L*a*b*, D65. L* in 0-100."""
    r, g, b = (_linearize(max(0.0, min(255.0, float(v))) / 255.0) for v in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / _XN
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / _YN
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / _ZN
    fx, fy, fz = _f(x), _f(y), _f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def bgr_to_lab(bgr) -> tuple[float, float, float]:
    """The pipeline's own channel order (OpenCV BGR) -> Lab."""
    return srgb_to_lab((bgr[2], bgr[1], bgr[0]))


def ciede2000(lab1, lab2) -> float:
    """CIEDE2000 colour difference between two CIE L*a*b* triples.

    Sharma, Wu & Dalal (2005), with the two details implementations usually get
    wrong and which the verification test exists to catch:

      * the mean hue h-bar is undefined when either chroma is zero, and the
        convention is to take the sum rather than average toward an arbitrary
        angle — the `C1p * C2p == 0` guards below;
      * the h' difference wraps at 180 degrees in BOTH directions, and the
        sign matters for the R_T rotation term.

    kL = kC = kH = 1 (reference conditions). Symmetric by construction; the
    test asserts that rather than assuming it.
    """
    L1, a1, b1 = (float(v) for v in lab1)
    L2, a2, b2 = (float(v) for v in lab2)

    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = 0.5 * (C1 + C2)
    Cbar7 = Cbar ** 7
    G = 0.5 * (1.0 - math.sqrt(Cbar7 / (Cbar7 + 25.0 ** 7))) if Cbar > 0 else 0.5
    a1p, a2p = (1.0 + G) * a1, (1.0 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = 0.0 if (a1p == 0.0 and b1 == 0.0) else math.degrees(math.atan2(b1, a1p)) % 360.0
    h2p = 0.0 if (a2p == 0.0 and b2 == 0.0) else math.degrees(math.atan2(b2, a2p)) % 360.0

    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0.0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180.0:
        dhp = h2p - h1p
    elif h2p - h1p > 180.0:
        dhp = h2p - h1p - 360.0
    else:
        dhp = h2p - h1p + 360.0
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)

    Lbarp = 0.5 * (L1 + L2)
    Cbarp = 0.5 * (C1p + C2p)
    if C1p * C2p == 0.0:
        hbarp = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hbarp = 0.5 * (h1p + h2p)
    elif h1p + h2p < 360.0:
        hbarp = 0.5 * (h1p + h2p + 360.0)
    else:
        hbarp = 0.5 * (h1p + h2p - 360.0)

    T = (1.0
         - 0.17 * math.cos(math.radians(hbarp - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * hbarp))
         + 0.32 * math.cos(math.radians(3.0 * hbarp + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * hbarp - 63.0)))
    dtheta = 30.0 * math.exp(-(((hbarp - 275.0) / 25.0) ** 2))
    Cbarp7 = Cbarp ** 7
    R_C = 2.0 * math.sqrt(Cbarp7 / (Cbarp7 + 25.0 ** 7)) if Cbarp > 0 else 0.0
    S_L = 1.0 + (0.015 * (Lbarp - 50.0) ** 2) / math.sqrt(20.0 + (Lbarp - 50.0) ** 2)
    S_C = 1.0 + 0.045 * Cbarp
    S_H = 1.0 + 0.015 * Cbarp * T
    R_T = -math.sin(math.radians(2.0 * dtheta)) * R_C

    return math.sqrt(
        (dLp / S_L) ** 2
        + (dCp / S_C) ** 2
        + (dHp / S_H) ** 2
        + R_T * (dCp / S_C) * (dHp / S_H)
    )


def bgr_ciede2000(bgr1, bgr2) -> float:
    """dE2000 between two colours given in the pipeline's BGR 0-255 floats."""
    return ciede2000(bgr_to_lab(bgr1), bgr_to_lab(bgr2))
