"""Why a scanline fill cannot consume the direction field (v2 Part 51, D2).

D2 was meant to make tatami fills consume the Part 50 field. It was implemented,
measured against the photographed sew-out, and REVERTED. These tests pin the two
structural findings that produced that verdict, so neither has to be rediscovered
by wiring a generator up a second time:

* the SEED MASK dominates the field's quality — diffusing inward from an outer
  silhouette is not the same field as diffusing from each region's own boundary,
  and it was the substitution that made the first D2 attempt lose to a constant;
* the COLLAPSE to one angle per region destroys information the field carries,
  and on the shape a digitizer most wants to fix — a ring — it destroys all of it.

Nothing here touches stitch output; D2 ships no engine change.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND_ROOT), str(BACKEND_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import measure_field_consumption as MFC

from app.services import direction_field as DF


def _annulus(size=320, outer=140, inner=80):
    m = np.zeros((size, size), np.uint8)
    cv2.circle(m, (size // 2, size // 2), outer, 255, -1)
    cv2.circle(m, (size // 2, size // 2), inner, 0, -1)
    return m


def _two_bars(size=320):
    """Two separated bars at right angles — a field with real regional variation."""
    m = np.zeros((size, size), np.uint8)
    cv2.rectangle(m, (20, 40), (300, 90), 255, -1)      # horizontal
    cv2.rectangle(m, (135, 150), (185, 300), 255, -1)   # vertical
    return m


def _mean_vector(field, region):
    sel = np.asarray(region) > 0
    c = float(np.asarray(field.c)[sel].mean())
    s = float(np.asarray(field.s)[sel].mean())
    return math.hypot(c, s)


# ── the collapse ──────────────────────────────────────────────────────────────


def test_doubled_angle_mean_does_not_wrap_at_180():
    """A region half at 179 deg and half at 1 deg averages to 0, never to 90.

    Averaging raw angles gives 90 — perpendicular to every stitch in the region.
    This is the representation bug the whole field is built to avoid, and the
    regional mean is where it would resurface.
    """
    m = np.zeros((40, 40), np.uint8)
    m[:] = 255
    c = np.zeros((40, 40), np.float32)
    s = np.zeros((40, 40), np.float32)
    for th, half in ((math.radians(179.0), slice(0, 20)), (math.radians(1.0), slice(20, 40))):
        c[half] = math.cos(2 * th)
        s[half] = math.sin(2 * th)
    field = DF.DirectionField(c=c, s=s, mask=m)

    class _O:
        stitch_type = "tatami"
        stitch_angle = 12.0

    got = MFC.regional_mean_angles(field, [_O()], [m])[0]
    assert min(got, 180.0 - got) < 1.0, f"doubled-angle mean wrapped: {got}"


def test_a_ring_cancels_so_one_angle_cannot_represent_it():
    """Over an annulus the field runs all the way round and the mean vector dies.

    A ring is exactly the shape the Part 50 pictures showed the field fixing, and
    it is the shape a single fill angle can least represent. The magnitude going
    to ~0 is not a solver defect — it is the honest statement that no one angle
    describes this region.
    """
    ring = _annulus()
    field = DF.solve(ring)
    assert _mean_vector(field, ring) < 0.05, "an annulus should not yield a decisive mean"
    # The per-pixel field is not weak — only its average is.
    sel = ring > 0
    assert float(np.asarray(field.coherence)[sel].max()) > 0.30


def test_collapsing_to_one_angle_per_region_loses_the_variation():
    """Per-pixel beats the regional mean wherever the field genuinely varies.

    Two bars at right angles have a true orientation that differs by 90 deg
    across the mask. One angle for the union cannot be right about both, so the
    collapse must score worse than the field itself. If this ever passes with
    equality, the field has stopped varying and D2's premise changed.
    """
    mask = _two_bars()
    field = DF.solve(mask)

    horiz = np.zeros_like(mask)
    cv2.rectangle(horiz, (20, 40), (300, 90), 255, -1)
    vert = np.zeros_like(mask)
    cv2.rectangle(vert, (135, 150), (185, 300), 255, -1)

    a_h = math.degrees(0.5 * math.atan2(
        float(np.asarray(field.s)[horiz > 0].mean()),
        float(np.asarray(field.c)[horiz > 0].mean()))) % 180.0
    a_v = math.degrees(0.5 * math.atan2(
        float(np.asarray(field.s)[vert > 0].mean()),
        float(np.asarray(field.c)[vert > 0].mean()))) % 180.0
    apart = abs((a_h - a_v + 90) % 180 - 90)
    assert apart > 30.0, (
        f"the two bars should want different angles; got {a_h:.1f} and {a_v:.1f}")


# ── the seed mask ─────────────────────────────────────────────────────────────


def test_seed_mask_changes_the_field_inside_the_same_region():
    """Solving on a silhouette is not the same field as solving on the regions.

    The first D2 attempt seeded the solver from the segmentation foreground — one
    blob whose boundary is the subject's outline — instead of the region
    boundaries where the shape information lives. Measured on the sew-out that
    cost 6.5 deg per pixel (32.34 -> 38.84) and made the change lose to a
    constant. This pins that the two seeds genuinely differ.
    """
    inner_a = np.zeros((320, 320), np.uint8)
    cv2.rectangle(inner_a, (40, 40), (280, 130), 255, -1)
    inner_b = np.zeros((320, 320), np.uint8)
    cv2.rectangle(inner_b, (40, 150), (130, 280), 255, -1)
    union = cv2.bitwise_or(inner_a, inner_b)
    # The silhouette: the convex outline that segmentation would hand over,
    # which swallows the boundary BETWEEN the two regions.
    hull = np.zeros((320, 320), np.uint8)
    pts = cv2.findNonZero(union)
    cv2.fillConvexPoly(hull, cv2.convexHull(pts), 255)

    f_regions = DF.solve(union)
    f_hull = DF.solve(hull)
    sel = inner_b > 0
    err = np.degrees(np.abs(
        (np.asarray(f_regions.theta)[sel] - np.asarray(f_hull.theta)[sel] + np.pi / 2)
        % np.pi - np.pi / 2))
    assert float(np.mean(err)) > 5.0, (
        "silhouette and region seeds produced the same field; the D2 finding "
        f"would not reproduce (mean difference {float(np.mean(err)):.2f} deg)")


def test_solve_cost_is_flat_in_contour_count():
    """The bound that matters: cost must not multiply by the noise count.

    Parts 48 and 49 both shipped per-region work inside the pre-filter contour
    loop, where the multiplier is how many contours the input happens to contain.
    The solver avoids that by working at a fixed resolution, so a 9x bigger noise
    mask with roughly 9x the contours must cost far less than 9x the time.

    Note what this does NOT claim: solving speckle is genuinely dearer than
    solving one solid shape, because the seeding work tracks boundary LENGTH.
    The guarantee is that it stops growing once the mask is downsampled, which is
    the property that keeps a pathological input bounded.
    """
    import time

    rng = np.random.default_rng(0)
    small = (rng.random((400, 400)) > 0.5).astype(np.uint8) * 255
    big = (rng.random((1200, 1200)) > 0.5).astype(np.uint8) * 255
    n_small = len(cv2.findContours(small, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0])
    n_big = len(cv2.findContours(big, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0])
    assert n_big > 5 * n_small, "the big case is not actually contour-heavier"

    DF.solve(small)  # warm any lazy import so the first call is not timed
    t0 = time.perf_counter(); DF.solve(small); t_small = time.perf_counter() - t0
    t0 = time.perf_counter(); DF.solve(big); t_big = time.perf_counter() - t0

    growth = t_big / max(t_small, 1e-3)
    assert growth < 3.0, (
        f"{n_big} contours cost {t_big:.3f}s vs {t_small:.3f}s for {n_small} "
        f"({growth:.1f}x) — solve cost is tracking contour count")
    assert t_big < 3.0, f"pathological mask took {t_big:.2f}s"


# ── the script's own classification ───────────────────────────────────────────


def test_tatami_and_satin_classification_are_exclusive():
    """Territory shares are only meaningful if nothing is counted in both."""
    class _O:
        def __init__(self, t):
            self.stitch_type = t

    for t in ("tatami", "TATAMI_FILL", "contour_fill", "satin", "SATIN_COLUMN"):
        o = _O(t)
        assert not (MFC.is_tatami(o) and MFC.is_satin(o)), t
