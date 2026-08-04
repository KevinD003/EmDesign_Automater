"""A direction field over the foreground (v2 Part 50, R004-impl D1).

**Nothing consumes this yet.** D1 exists so the approach can be looked at before
any stitch generator depends on it, which is the cheapest point to abandon it.

Why a field at all. `_fill_angle` gives each region one angle from its own
principal axis, and Part 46 measured that approach at its ceiling: 49.9 deg
against a real sew-out, flat across object size, the same for satin and tatami,
and unmoved by restricting the comparison to well-registered segments. The reason
is structural — colour clustering cuts one visual element into several regions,
and each then picks an axis knowing nothing about its neighbours. A petal split
into five colour patches gets five unrelated directions. A field is defined over
the whole foreground, so neighbours share a flow by construction.

The representation is the **doubled angle**. A stitch direction has no head or
tail, so theta and theta+pi are the same thing and averaging them naively gives
nonsense: mean(179 deg, 1 deg) is 90 deg, exactly wrong. Doubling maps both to the
same point on the circle, so (cos 2t, sin 2t) can be averaged, blurred and
diffused like any vector, then halved back at the end. Everything below operates
on that pair, never on the angle.

The solver is deliberately the cheapest thing that could work: seed the field on
the foreground boundary with the boundary's own tangent, then diffuse inward by
repeated blur-and-reseed, which is Laplace with Dirichlet edges by another name.
That produces contour-parallel flow — thread that follows the shape's outline,
which is what a digitizer does for a petal or a leaf. It is a first
approximation, not a claim about what the final field should be.
"""

from __future__ import annotations

from dataclasses import dataclass

# Iterations of blur-and-reseed. The field is smooth well before this on the
# fixtures measured; the cap is what keeps cost predictable on a pathological
# mask rather than a tuned quality knob.
DIFFUSE_ITERS = 24
DIFFUSE_KERNEL = 9

# The mask is worked at this longest side and the result scaled back. A field is
# smooth by construction, so solving it at full resolution buys nothing and costs
# quadratically — the panel's mask is over 1000px and its field is unchanged at
# 384. This is the bound that keeps a noise input from becoming a solver problem.
WORK_MAX_PX = 384


@dataclass(frozen=True)
class DirectionField:
    """Orientation per pixel over a mask, in the doubled-angle representation.

    ``c`` and ``s`` are cos(2t) and sin(2t) at the mask's own resolution.
    ``theta`` unwraps them to radians mod pi, image axes, y down — the same
    convention `measure_stitch_direction.orientation_field` returns, so the two
    are directly comparable.
    """

    c: object
    s: object
    mask: object

    @property
    def theta(self):
        import numpy as np

        return 0.5 * np.arctan2(self.s, self.c)

    @property
    def coherence(self):
        """Magnitude of the doubled-angle vector: 1 where the flow agrees, 0 where it cancels."""
        import numpy as np

        return np.sqrt(self.c * self.c + self.s * self.s)

    def sample(self, xs, ys):
        """Angle (radians, mod pi) at integer pixel coordinates, clamped to the mask."""
        import numpy as np

        h, w = self.mask.shape[:2]
        xi = np.clip(np.asarray(xs, int), 0, w - 1)
        yi = np.clip(np.asarray(ys, int), 0, h - 1)
        return 0.5 * np.arctan2(self.s[yi, xi], self.c[yi, xi])


def _boundary_tangents(mask):
    """(c, s, seed) — doubled-angle tangent along the mask's own outline.

    The tangent comes from the contour polyline rather than an image gradient:
    a gradient at a hard mask edge is the NORMAL, and using it would give a field
    at right angles to the shape everywhere, which is the kind of sign error this
    repo has been caught by before.
    """
    import cv2
    import numpy as np

    c = np.zeros(mask.shape, np.float32)
    s = np.zeros(mask.shape, np.float32)
    seed = np.zeros(mask.shape, np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    h, w = mask.shape[:2]
    for cnt in contours:
        pts = cnt.reshape(-1, 2)
        if len(pts) < 5:
            continue
        # Central difference along the closed polyline, over a few points so a
        # single-pixel staircase does not dominate the tangent.
        step = max(2, len(pts) // 128)
        nxt = np.roll(pts, -step, axis=0)
        prv = np.roll(pts, step, axis=0)
        d = (nxt - prv).astype(np.float32)
        n = np.hypot(d[:, 0], d[:, 1])
        keep = n > 1e-6
        if not keep.any():
            continue
        ang = np.arctan2(d[keep, 1], d[keep, 0])
        xs = np.clip(pts[keep, 0], 0, w - 1)
        ys = np.clip(pts[keep, 1], 0, h - 1)
        c[ys, xs] = np.cos(2 * ang)
        s[ys, xs] = np.sin(2 * ang)
        seed[ys, xs] = 255
    return c, s, seed


def solve(mask, *, iters: int = DIFFUSE_ITERS, work_max_px: int = WORK_MAX_PX) -> DirectionField:
    """Diffuse the boundary tangent inward to a smooth field over ``mask``.

    Cost is bounded by construction: the mask is worked at ``work_max_px`` on its
    longest side, so the per-iteration cost is fixed no matter how large or how
    noisy the input is. That bound is deliberate — Parts 48 and 49 both shipped a
    per-region cost inside the pre-filter contour loop, where the multiplier is
    the noise count rather than the design count, and both were caught only by the
    fuzz suite. A field solved on a downscaled mask cannot repeat that.
    """
    import cv2
    import numpy as np

    full = (np.asarray(mask) > 0).astype(np.uint8) * 255
    fh, fw = full.shape[:2]
    scale = min(1.0, work_max_px / max(fh, fw, 1))
    if scale < 1.0:
        small = cv2.resize(full, (max(1, int(fw * scale)), max(1, int(fh * scale))),
                           interpolation=cv2.INTER_NEAREST)
    else:
        small = full

    c, s, seed = _boundary_tangents(small)
    inside = small > 0
    if not inside.any() or not (seed > 0).any():
        zeros = np.zeros(full.shape, np.float32)
        return DirectionField(c=zeros, s=zeros.copy(), mask=full)

    k = (DIFFUSE_KERNEL, DIFFUSE_KERNEL)
    seeded = seed > 0
    seed_c, seed_s = c.copy(), s.copy()
    for _ in range(iters):
        c = cv2.GaussianBlur(c, k, 0)
        s = cv2.GaussianBlur(s, k, 0)
        # Dirichlet: the outline keeps its own tangent every step, so the flow is
        # pulled toward the shape rather than washing out to a constant.
        c[seeded] = seed_c[seeded]
        s[seeded] = seed_s[seeded]
        c[~inside] = 0.0
        s[~inside] = 0.0

    # Normalise so coherence reads as agreement, not as blur magnitude.
    mag = np.sqrt(c * c + s * s)
    ok = mag > 1e-6
    cn, sn = np.zeros_like(c), np.zeros_like(s)
    cn[ok] = c[ok] / mag[ok]
    sn[ok] = s[ok] / mag[ok]
    # Keep the pre-normalisation magnitude as the confidence signal.
    conf = np.clip(mag / (mag.max() + 1e-9), 0.0, 1.0)
    cn *= conf
    sn *= conf

    if scale < 1.0:
        cn = cv2.resize(cn, (fw, fh), interpolation=cv2.INTER_LINEAR)
        sn = cv2.resize(sn, (fw, fh), interpolation=cv2.INTER_LINEAR)
    cn[full == 0] = 0.0
    sn[full == 0] = 0.0
    return DirectionField(c=cn, s=sn, mask=full)


def per_object_field(mask, regions) -> DirectionField:
    """The CURRENT behaviour expressed as a field, so the two can be scored alike.

    ``regions`` is an iterable of (region_mask, angle_radians). Every pixel of a
    region carries that region's single angle. This is what `_fill_angle` amounts
    to, written in the same representation as `solve()` so the instrument can rank
    them against each other on the same artwork rather than comparing a number
    from one pipeline against a number from another.
    """
    import numpy as np

    full = (np.asarray(mask) > 0).astype(np.uint8) * 255
    c = np.zeros(full.shape, np.float32)
    s = np.zeros(full.shape, np.float32)
    for region, angle in regions:
        sel = np.asarray(region) > 0
        c[sel] = float(np.cos(2 * angle))
        s[sel] = float(np.sin(2 * angle))
    c[full == 0] = 0.0
    s[full == 0] = 0.0
    return DirectionField(c=c, s=s, mask=full)


def constant_field(mask, angle_rad: float) -> DirectionField:
    """One angle everywhere — the trivial baseline any candidate must beat."""
    import numpy as np

    full = (np.asarray(mask) > 0).astype(np.uint8) * 255
    c = np.full(full.shape, float(np.cos(2 * angle_rad)), np.float32)
    s = np.full(full.shape, float(np.sin(2 * angle_rad)), np.float32)
    c[full == 0] = 0.0
    s[full == 0] = 0.0
    return DirectionField(c=c, s=s, mask=full)
