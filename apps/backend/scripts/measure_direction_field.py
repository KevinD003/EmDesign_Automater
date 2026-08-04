"""Rank candidate direction fields against a reference (v2 Part 50, R004-impl D0).

`measure_stitch_direction.py` answers one question: how far are OUR STITCHES from
a photographed sew-out. That produced the 49.9 deg figure and it was enough to
prove per-region angles are at their ceiling (Part 46). It is not enough to steer
engine work, because it can only score a design that has already been stitched.

This scores a FIELD directly against a reference orientation field, so two
candidates can be compared on the same artwork before either is wired into a
generator. Concretely it can rank:

    * the current per-object angles, expressed as a field
    * a solved field
    * a constant angle, the trivial baseline anything must beat

and it reports structure, not one scalar — by fixture, by region, and in spatial
buckets — because a single number cannot say WHERE a field is wrong.

    scripts/measure_direction_field.py --self-test
    scripts/measure_direction_field.py            # all ten bench fixtures

No target is written down here on purpose. `docs/PROMPT-direction-field.md` says
to set one from what the instrument shows is achievable; a threshold picked in
advance is the habit these audits keep catching.
"""

from __future__ import annotations

import argparse
import math
import statistics as st
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND / "scripts"))

from measure_stitch_direction import orientation_field

from app.services import direction_field as DF

# A reference pixel only carries information where the source actually has
# oriented structure. Flat interior has no direction to be right or wrong about,
# and scoring it would dilute every candidate toward the same number.
MIN_COHERENCE = 0.35


def angular_error_deg(a, b):
    """|a - b| folded to [0, 90]. Orientation has no head or tail."""
    return np.degrees(np.abs((a - b + np.pi / 2) % np.pi - np.pi / 2))


def score_field(field: DF.DirectionField, ref_theta, ref_coh, *,
                min_coherence: float = MIN_COHERENCE, buckets: int = 3) -> dict:
    """Compare a candidate field to a reference orientation field.

    Returns the aggregate, the qualified subset, and a spatial breakdown. The
    qualified subset is the Part 46 idea carried forward: a bad score has to be
    able to say whether it is the field that is wrong or the comparison, and here
    that means reporting how much of the mask carried enough reference structure
    to be worth scoring at all.
    """
    mask = field.mask > 0
    usable = mask & (ref_coh >= min_coherence)
    if not usable.any():
        return {"n": 0, "mean_deg": float("nan"), "qualified_share": 0.0}

    err = angular_error_deg(field.theta, ref_theta)
    # UNIFORM weights, deliberately. The first version weighted by the candidate's
    # own confidence, which is 1.0 everywhere for a per-object field and well
    # under that for a diffused one — so the diffused field was scored mostly
    # where it happened to be sure, and the comparison flattered it. A candidate
    # does not get to choose which pixels it is judged on.
    sel = usable
    e = err[sel]
    ww = np.ones_like(e)
    h, wd = mask.shape[:2]
    grid = {}
    for by in range(buckets):
        for bx in range(buckets):
            y0, y1 = by * h // buckets, (by + 1) * h // buckets
            x0, x1 = bx * wd // buckets, (bx + 1) * wd // buckets
            sub = sel[y0:y1, x0:x1]
            if sub.sum() < 50:
                continue
            grid[f"{by},{bx}"] = round(float(np.mean(err[y0:y1, x0:x1][sub])), 2)
    return {
        "n": int(sel.sum()),
        "mean_deg": round(float(np.average(e, weights=ww)), 2),
        "median_deg": round(float(np.median(e)), 2),
        "within_15_pct": round(100.0 * float((e < 15).mean()), 1),
        "within_30_pct": round(100.0 * float((e < 30).mean()), 1),
        # What fraction of the design carried reference structure at all. Low here
        # means "this artwork cannot answer the question", not "the field is bad".
        "qualified_share": round(float(usable.sum()) / max(int(mask.sum()), 1), 3),
        # How much of the mask this candidate is actually confident about. Not a
        # weight — reported alongside so a field that only commits near edges
        # cannot look decisive by staying quiet everywhere else.
        "committed_share": round(float((field.coherence[mask] > 0.30).mean()), 3),
        "by_cell": grid,
    }


# ── self-tests ────────────────────────────────────────────────────────────────


def _radial_stripes(size=400):
    """Spokes from the centre: the true orientation at (x,y) is atan2(dy,dx)."""
    img = np.zeros((size, size, 3), np.uint8)
    cx = cy = size // 2
    for deg in range(0, 360, 6):
        a = math.radians(deg)
        cv2.line(img, (cx, cy),
                 (int(cx + size * math.cos(a)), int(cy + size * math.sin(a))),
                 (220, 220, 220), 2)
    yy, xx = np.mgrid[0:size, 0:size]
    truth = np.arctan2(yy - cy, xx - cx)
    return img, truth


def _concentric_rings(size=400, step=8):
    """Rings: the true orientation is the tangent, atan2(dy,dx) + 90 deg."""
    img = np.zeros((size, size, 3), np.uint8)
    cx = cy = size // 2
    for r in range(step, size, step):
        cv2.circle(img, (cx, cy), r, (220, 220, 220), 2)
    yy, xx = np.mgrid[0:size, 0:size]
    truth = np.arctan2(yy - cy, xx - cx) + np.pi / 2
    return img, truth


def self_test() -> bool:
    """Stripes, then two nontrivial fields where the truth varies per pixel.

    The stripe test only proves the instrument can read a constant orientation.
    A field that varies smoothly is the case this part exists for, so it has to
    be in the self-test — otherwise the instrument could be right about the easy
    case and wrong about the one that matters.
    """
    ok = True
    print("instrument self-test")

    for true_deg in (0, 30, 45, 60, 90, 120):
        img = np.zeros((300, 300, 3), np.uint8)
        a = math.radians(true_deg)
        for k in range(-400, 400, 6):
            ox, oy = -k * math.sin(a), k * math.cos(a)
            cv2.line(img,
                     (int(150 + ox - 500 * math.cos(a)), int(150 + oy - 500 * math.sin(a))),
                     (int(150 + ox + 500 * math.cos(a)), int(150 + oy + 500 * math.sin(a))),
                     (220, 220, 220), 2)
        theta, _ = orientation_field(img)
        est = math.degrees(float(np.median(theta[100:200, 100:200]))) % 180
        err = abs((est - true_deg + 90) % 180 - 90)
        ok &= err <= 3.0
        print(f"  {'ok ' if err <= 3.0 else 'FAIL'} stripes {true_deg:3d} deg "
              f"-> {est:6.1f} (err {err:.1f})")

    for name, gen, tol in (("radial spokes", _radial_stripes, 8.0),
                           ("concentric rings", _concentric_rings, 8.0)):
        img, truth = gen()
        theta, coh = orientation_field(img)
        # Skip the singular centre, where every direction meets and no method can
        # be right, and score only where the source has real structure.
        yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
        r = np.hypot(xx - img.shape[1] / 2, yy - img.shape[0] / 2)
        sel = (coh >= MIN_COHERENCE) & (r > 40) & (r < img.shape[0] / 2 - 10)
        err = float(np.median(angular_error_deg(theta[sel], truth[sel])))
        ok &= err <= tol
        print(f"  {'ok ' if err <= tol else 'FAIL'} {name:17s} median error {err:5.2f} deg "
              f"(tolerance {tol})")

    print(f"  => instrument {'VALID' if ok else 'INVALID'}")
    return ok


# ── running over the bench ────────────────────────────────────────────────────


def candidates_for(name: str):
    """Build the reference and every candidate field for one bench fixture."""
    import visual_regression as VR

    params = VR.FIXTURES[name]
    src = cv2.imread(str(VR.FIXTURE_DIR / f"{name}.png"))
    ref_theta, ref_coh = orientation_field(src)

    cv2.setRNGSeed(VR.RNG_SEED)
    design = VR.render_fixture(name)[1]

    h, w = src.shape[:2]
    # Design coordinates live in HOOP space, not a 0-based box, so the mapping is
    # from the artwork's own extents to the frame — not a bare multiply. Getting
    # this wrong puts every region off-image and scores a blank mask.
    pts_all = [p for o in design.objects for p in (o.contour or [])]
    if not pts_all:
        return None
    ox, oy = min(p.x for p in pts_all), min(p.y for p in pts_all)
    ex, ey = max(p.x for p in pts_all), max(p.y for p in pts_all)
    sx = w / max(ex - ox, 1e-6)
    sy = h / max(ey - oy, 1e-6)

    def to_px(p):
        return [int(np.clip((p.x - ox) * sx, 0, w - 1)),
                int(np.clip((p.y - oy) * sy, 0, h - 1))]

    mask = np.zeros((h, w), np.uint8)
    regions = []
    for o in design.objects:
        if not o.contour:
            continue
        poly = np.array([to_px(p) for p in o.contour], np.int32)
        one = np.zeros((h, w), np.uint8)
        cv2.fillPoly(one, [poly], 255)
        for hole in (o.holes or []):
            cv2.fillPoly(one, [np.array([to_px(p) for p in hole], np.int32)], 0)
        mask = cv2.bitwise_or(mask, one)
        regions.append((one, math.radians(float(o.stitch_angle))))

    if not regions:
        return None
    return {
        "name": name, "params": params, "mask": mask,
        "ref_theta": ref_theta, "ref_coh": ref_coh,
        "per_object": DF.per_object_field(mask, regions),
        "solved": DF.solve(mask),
        "constant45": DF.constant_field(mask, math.radians(45.0)),
        "n_objects": len(regions),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()

    if not self_test():
        print("\nself-test failed — no score below would mean anything", file=sys.stderr)
        return 1
    if args.self_test:
        return 0

    import visual_regression as VR

    names = [args.only] if args.only else sorted(VR.FIXTURES)
    print(f"\n{'fixture':26s} {'objs':>5s} {'qual':>6s} "
          f"{'per-object':>11s} {'solved':>9s} {'const 45':>9s}   winner")
    rows = []
    for name in names:
        c = candidates_for(name)
        if c is None:
            print(f"{name:26s}  (no regions)")
            continue
        scores = {k: score_field(c[k], c["ref_theta"], c["ref_coh"])
                  for k in ("per_object", "solved", "constant45")}
        if not scores["per_object"].get("n"):
            print(f"{name:26s}  (no reference structure under the design)")
            continue
        best = min(scores, key=lambda k: scores[k]["mean_deg"])
        print(f"{name:26s} {c['n_objects']:5d} "
              f"{scores['per_object']['qualified_share']:6.2f} "
              f"{scores['per_object']['mean_deg']:11.2f} "
              f"{scores['solved']['mean_deg']:9.2f} "
              f"{scores['constant45']['mean_deg']:9.2f}   {best}")
        rows.append((name, scores))

    if rows:
        print()
        for key in ("per_object", "solved", "constant45"):
            vals = [s[key]["mean_deg"] for _n, s in rows]
            print(f"  {key:12s} mean over fixtures {st.mean(vals):6.2f} deg   "
                  f"median {st.median(vals):6.2f}")
        wins = {}
        for _n, s in rows:
            wins[min(s, key=lambda k: s[k]["mean_deg"])] = \
                wins.get(min(s, key=lambda k: s[k]["mean_deg"]), 0) + 1
        print(f"  fixtures won: {wins}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
