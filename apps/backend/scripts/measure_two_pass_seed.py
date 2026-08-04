"""Is the field the pipeline now solves the best seed class? (v2 Part 52)

Part 51's finding was that the SEED MASK is most of the direction field's
quality, and that the seed a one-pass pipeline could reach — the segmentation
foreground silhouette — was the worst of the three. Part 52 restructures
`digitize_image` into a collection pass and a generation pass so the best seed,
the union of every object's own outline, exists before any generator runs.

This checks that claim against a real run rather than against the code that was
just written. It takes the seed the pipeline actually built
(`staging.last_field_artifact()`), rebuilds the two rival seeds from the same
run, and scores all three against the photographed sew-out.

ONE REGISTRATION FOR ALL THREE, and that is the point of this script rather than
an implementation detail. Part 51 solved the union and per-cluster seeds on masks
rasterised from the design's mm extents STRETCHED to fill the source frame, while
the silhouette came from the pipeline's own working frame. The design's bounding
box does not quite fill that frame — 98.9% x 99.2% here — so the two mappings
differ by about a 1% scale and a 6 px shift, which moves ~17% of all boundary
pixels on artwork this fine. Measured, that mixed registration was worth 4.15 deg
of the 6.50 deg spread Part 51 attributed entirely to the seed. The ranking
survived; the magnitude did not. So every candidate here is solved in the
pipeline's own frame and lifted once, by the same transform.

    scripts/measure_two_pass_seed.py
    scripts/measure_two_pass_seed.py --image path/to/sewout.jpg
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from measure_direction_field import score_field
from measure_field_consumption import (
    DEFAULT_IMAGE,
    HOOP,
    MAX_COLORS,
    RNG_SEED,
    rasterise,
)
from measure_stitch_direction import orientation_field

from app.services import direction_field as DF
from app.services.digitizer import digitize_image, staging
from app.services.digitizer import pipeline as PL


def run(image: Path):
    """Digitize once, keeping the plan and the foreground mask for comparison."""
    grab: dict = {}
    real_sketch = PL._sketch_from_labels
    real_remember = staging.remember

    def sketch_spy(labels, fg_mask):
        grab.setdefault("fg", fg_mask.copy())
        return real_sketch(labels, fg_mask)

    def remember_spy(plan):
        grab["plan"] = plan
        return real_remember(plan)

    PL._sketch_from_labels = sketch_spy
    PL.staging.remember = remember_spy
    try:
        cv2.setRNGSeed(RNG_SEED)
        t0 = time.perf_counter()
        design = digitize_image(image.read_bytes(), "cotton", HOOP, MAX_COLORS)
        grab["seconds"] = time.perf_counter() - t0
    finally:
        PL._sketch_from_labels = real_sketch
        PL.staging.remember = real_remember
    return design, grab


def per_cluster_seed_field(plan):
    """Rival seed: each colour cluster solved on its own regions, composited."""
    h, w = plan.seed_mask.shape[:2]
    c = np.zeros((h, w), np.float32)
    s = np.zeros((h, w), np.float32)
    for cl in plan.clusters:
        cm = np.zeros((h, w), np.uint8)
        for rp in cl.regions:
            if not rp.dropped:
                staging.add_to_seed(cm, rp.contour, rp.holes)
        if not cv2.countNonZero(cm):
            continue
        f = DF.solve(cm)
        sel = cm > 0
        c[sel] = np.asarray(f.c, np.float32)[sel]
        s[sel] = np.asarray(f.s, np.float32)[sel]
    return DF.DirectionField(c=c, s=s, mask=plan.seed_mask)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    args = ap.parse_args()

    src = cv2.imread(str(args.image))
    if src is None:
        print(f"cannot read {args.image}", file=sys.stderr)
        return 1
    ref_theta, ref_coh = orientation_field(src)
    h, w = src.shape[:2]

    design, grab = run(args.image)
    plan = grab.get("plan")
    art = staging.last_field_artifact()
    if plan is None or art is None or art.field is None:
        print("the pipeline exposed no field artifact", file=sys.stderr)
        return 1

    _objs, _masks, _per_stop, everything, tatami, satin = rasterise(design, h, w)
    fh, fw = plan.seed_mask.shape[:2]
    print(f"{args.image.name}  {w}x{h}   digitize {grab['seconds']:.1f}s")
    print(f"pass A: {art.cluster_count} clusters, {art.region_count} regions, "
          f"seed {art.seed_px} px in a {fw}x{fh} frame")
    print(f"pass B: {len(design.objects)} objects, {len(design.stitches)} stitches\n")

    def lift(field):
        """Working frame -> source pixels, resampling (cos 2t, sin 2t).

        Never the angle itself: resampled across the 180 deg wrap it averages to
        nonsense. Same transform for every candidate, so the comparison is fair
        whatever the transform's own error is.
        """
        return (cv2.resize(np.asarray(field.c, np.float32), (w, h), interpolation=cv2.INTER_LINEAR),
                cv2.resize(np.asarray(field.s, np.float32), (w, h), interpolation=cv2.INTER_LINEAR))

    def report(label, field):
        c, s = lift(field)
        vals = [score_field(DF.DirectionField(c=c, s=s, mask=terr), ref_theta, ref_coh)["mean_deg"]
                for terr in (everything, tatami, satin)]
        print(f"{label:46s} {vals[0]:8.2f} {vals[1]:8.2f} {vals[2]:8.2f}")
        return vals

    print(f"{'seed, all solved in the pipeline frame':46s} "
          f"{'WHOLE':>8s} {'TATAMI':>8s} {'SATIN':>8s}")
    union = report("  union of object contours  <- pass A ships this", art.field)
    cluster = report("  per colour cluster, composited", per_cluster_seed_field(plan))
    fg = grab.get("fg")
    silhouette = report("  segmentation foreground silhouette", DF.solve(fg)) if fg is not None else None

    print()
    rivals = [r for r in (cluster, silhouette) if r is not None]
    if rivals and all(union[1] < r[1] for r in rivals) and all(union[0] < r[0] for r in rivals):
        best = min(r[1] for r in rivals)
        print(f"PASS — the pipeline's seed wins on every territory; nearest rival is "
              f"{best - union[1]:.2f} deg behind on tatami.")
        return 0
    print("FAIL — the pipeline is not handing downstream the best available seed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
