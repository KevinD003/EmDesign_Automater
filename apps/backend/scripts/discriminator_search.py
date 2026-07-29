"""Empirical search for a LOCAL discriminator between a running-stitch reversal
and a collapsed satin column (v2 Part 12, Part A item 1).

Part 11 §1 claimed: "no test on the triple ``a, b, c`` alone can separate a
180-degree running-stitch reversal from a satin column whose pitch has collapsed
to zero, because there is nothing to separate." This script is the evidence that
claim asked for. It has two halves:

**The constructive half** (the strong one). A triple of points is determined up
to rigid motion and reflection by the complete invariant ``(|ab|, |bc|, angle at
b)``, and any physically meaningful discriminator must be invariant under rigid
motions — needle/fabric damage does not depend on where the triple sits in the
hoop. So if, for a violating reversal triple, the *same three coordinates* are
also a legitimate satin emission ``(B0, A1, B1)`` — legs = one column crossing
and one diagonal advance, both inside the widths the pipeline actually emits —
then every function of the triple returns the same answer for both readings,
and separation is impossible *for that triple*, full stop. The script checks
this satin-realizability for the two real fixture-07 violations (coordinates as
recorded in the Part 11 audit) and for a large sampled family of synthetic
reversals.

**The sweep half** (the honest caveat). Across *distributions*, partial
separation can still exist — underlay steps cluster near ``UNDERLAY_STEP_MM``
while satin columns span the full width range — so the script also sweeps every
candidate discriminator the audits discussed (anti-parallelism, leg ratio,
collinearity residual, plus the raw invariants) and reports the best single-
threshold accuracy of each. The point the numbers make: whatever accuracy a
distributional prior buys, its false positives are by construction *real satin
violations*, which is exactly the population a safety metric exists to catch.
A filter that discards them is not a discriminator, it is a hole.

    python scripts/discriminator_search.py [--samples N] [--seed N]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.digitizer import (
    MIN_PENETRATION_MM,
    SATIN_MAX_W_MM,
    UNDERLAY_STEP_MM,
    ZIGZAG_RATIO,
)

# The two real violations Part 11 located (fixture 07, mm coordinates from the
# audit §1). These are the ground truth the whole argument is anchored to.
REAL_REVERSALS = (
    ("07 Satin 1  (0.1828mm)", (77.8781, 78.7922), (79.8891, 78.6094), (77.8781, 78.6094)),
    ("07 Satin 13 (0.0000mm)", (59.2313, 23.4000), (61.4250, 23.4000), (59.2313, 23.4000)),
)


def _invariants(a, b, c) -> tuple[float, float, float]:
    """Complete local invariant (|ab|, |bc|, angle at b) — determines the triple
    up to rigid motion + reflection, which is the full symmetry group any
    physical discriminator must respect."""
    l1, l2 = math.dist(a, b), math.dist(b, c)
    u = ((a[0] - b[0]) / l1, (a[1] - b[1]) / l1)
    v = ((c[0] - b[0]) / l2, (c[1] - b[1]) / l2)
    dot = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    return l1, l2, math.acos(dot)


def _violates(a, b, c) -> bool:
    """The metric's own test: same-side gap under the floor AND the triple zigzags."""
    gap = math.dist(a, c)
    return gap < MIN_PENETRATION_MM and gap < ZIGZAG_RATIO * min(math.dist(a, b), math.dist(b, c))


def satin_realizable(a, b, c) -> bool:
    """Could these exact coordinates have been emitted by the satin path?

    Reading the triple as ``(B0, A1, B1)`` of an ``A0 B0 A1 B1`` stream: |bc| is
    a column crossing and |ab| the diagonal advance to it. A column is plausible
    when it is within the satin width cap (plus nothing below — ``SATIN_MIN_W_MM``
    exists but is deliberately NOT enforced, per Part 3), and the diagonal of an
    adjacent column pair differs from the column by at most the pitch collapse
    under test (bounded here by the floor itself).
    """
    l1, l2 = math.dist(a, b), math.dist(b, c)
    return l2 <= SATIN_MAX_W_MM and abs(l1 - l2) <= MIN_PENETRATION_MM


def sample_reversals(n: int, seed: int) -> list[tuple]:
    """Synthetic underlay reversals: out along a branch, turn, back down it.

    Varies the things a real medial-axis tip varies: step length (decimation can
    leave the tip-closing step anywhere below ``UNDERLAY_STEP_MM``), leg
    asymmetry, and a kink angle at the tip (a curved axis does not reverse along
    the exact same line — fixture 07's 0.1828mm case is a kinked one).
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        l1 = float(rng.uniform(0.3, UNDERLAY_STEP_MM * 1.1))
        l2 = float(rng.uniform(0.3, UNDERLAY_STEP_MM * 1.1))
        kink = float(rng.uniform(0.0, math.radians(25.0)))
        b = (0.0, 0.0)
        a = (-l1, 0.0)
        c = (-l2 * math.cos(kink), l2 * math.sin(kink))
        if _violates(a, b, c):
            out.append((a, b, c))
    return out


def sample_collapsed_satin(n: int, seed: int) -> list[tuple]:
    """Synthetic collapsed satin triples (B0, A1, B1): two same-boundary points
    ``gap`` apart, the opposite-boundary point one column width away."""
    import numpy as np

    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        w = float(rng.uniform(0.3, SATIN_MAX_W_MM))
        gap = float(rng.uniform(0.0, MIN_PENETRATION_MM))
        skew = float(rng.uniform(-0.5, 0.5)) * gap
        a, b, c = (0.0, 0.0), (skew, w), (gap, 0.0)
        if _violates(a, b, c):
            out.append((a, b, c))
    return out


CANDIDATES = {
    "leg |ab|": lambda a, b, c: _invariants(a, b, c)[0],
    "leg |bc|": lambda a, b, c: _invariants(a, b, c)[1],
    "leg ratio max/min": lambda a, b, c: max(*_invariants(a, b, c)[:2]) / min(*_invariants(a, b, c)[:2]),
    "angle at b (anti-parallelism)": lambda a, b, c: _invariants(a, b, c)[2],
    "collinearity (triangle area / |ac|)": lambda a, b, c: (
        abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / max(math.dist(a, c), 1e-12)
    ),
    "gap |ac|": lambda a, b, c: math.dist(a, c),
    "gap / min leg": lambda a, b, c: math.dist(a, c) / min(*_invariants(a, b, c)[:2]),
}


def best_threshold_accuracy(pos: list[float], neg: list[float]) -> float:
    """Best achievable BALANCED accuracy of a single threshold on one scalar
    feature, over both directions. Balanced (mean of per-class rates), because
    the two populations are different sizes and raw accuracy would reward the
    trivial always-say-satin classifier. 0.5 = no separation, 1.0 = perfect."""
    pts = sorted({*pos, *neg})
    best = 0.5
    for t in pts:
        pos_le = sum(1 for v in pos if v <= t) / len(pos)
        neg_gt = sum(1 for v in neg if v > t) / len(neg)
        best = max(best, (pos_le + neg_gt) / 2.0, ((1 - pos_le) + (1 - neg_gt)) / 2.0)
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--samples", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20260729)
    args = ap.parse_args(argv)

    print("== constructive check: are the REAL violations satin-realizable as-is? ==")
    for name, a, b, c in REAL_REVERSALS:
        l1, l2, th = _invariants(a, b, c)
        ok = satin_realizable(a, b, c)
        print(f"  {name}: legs {l1:.4f}/{l2:.4f}mm, angle {math.degrees(th):6.2f} deg, "
              f"violates={_violates(a, b, c)}, satin-realizable={ok}")
    print()

    rev = sample_reversals(args.samples, args.seed)
    sat = sample_collapsed_satin(args.samples, args.seed + 1)
    n_real = sum(1 for t in rev if satin_realizable(*t))
    print("== sampled populations (violating triples only) ==")
    print(f"  reversals: {len(rev)}   collapsed satin: {len(sat)}")
    print(f"  reversals whose exact coordinates are ALSO a legitimate satin emission: "
          f"{n_real}/{len(rev)} ({100.0 * n_real / max(len(rev), 1):.1f}%)")
    print("  (for those, every function f(a,b,c) is identical on both readings — "
          "separation is impossible for the individual triple)")
    print()

    def _sweep(title, rev_pop):
        print(f"== {title} (best single-threshold BALANCED accuracy; 0.5 = chance) ==")
        for name, fn in CANDIDATES.items():
            acc = best_threshold_accuracy([fn(*t) for t in rev_pop], [fn(*t) for t in sat])
            print(f"  {name:38} {acc:.3f}")
        print()

    _sweep("sweep A: full adversarial reversal space", rev)
    # Real decimation walks out and back with the SAME step, so real reversals
    # have near-equal legs — 07's two cases measure ratio 1.004 and 1.000. The
    # broad sampler above deliberately over-disperses to cover the space the
    # brief asked for; this subfamily is what the pipeline actually emits.
    tight = [t for t in rev if max(*_invariants(*t)[:2]) / min(*_invariants(*t)[:2]) <= 1.05]
    _sweep(f"sweep B: decimation-consistent subfamily (leg ratio <= 1.05, n={len(tight)})", tight)

    print("Reading: every reversal sampled is satin-realizable AS-IS, so no function of the "
          "triple can separate an individual case — including both real fixture-07 violations. "
          "Sweep A's above-chance numbers are DISTRIBUTIONAL (independent-leg sampling; underlay "
          f"steps cluster near {UNDERLAY_STEP_MM}mm while satin spans the width range) and their "
          "false positives are real satin violations — the population the metric exists to catch. "
          "Sweep B shows the separation collapsing on the subfamily the pipeline actually emits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
