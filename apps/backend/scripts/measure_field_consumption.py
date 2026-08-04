"""Can a scanline fill consume the direction field? (v2 Part 51, R004-impl D2)

Part 50 built a direction field and scored it PER PIXEL against a photographed
sew-out: 33.91 deg, against 38.27 for the angles the engine assigns today. D2's
job was to make tatami fills consume it. This script measures the two things
that decide whether that is possible, and it exists because wiring the field in
without measuring them first produced a change that a CONSTANT ANGLE beat.

1. SEED MASK. The solver diffuses inward from a boundary, so which boundary it
   is seeded from is not a detail — it is most of the answer. Three seeds are
   ranked here, and they are 6.5 deg apart.

2. COLLAPSE COST. A scanline tatami fill lays parallel rows at ONE angle, so
   "consume the field" can only mean taking the field's mean orientation over
   the region. The gap between a field per pixel and the same field collapsed
   to one angle per region is what a straight-row generator cannot recover.

Controls are included and they are the point. A constant angle and a random
angle are scored on the same territory, because the panel has a dominant thread
direction: any policy a constant also achieves is not evidence the field is
being used.

    scripts/measure_field_consumption.py
    scripts/measure_field_consumption.py --image path/to/sewout.jpg --seeds 0

Scores are reported on three territories. The panel is 93.7% satin by area and
9.3% tatami, so a tatami-only change cannot move a whole-design number, and
reading one as if it could is how this part nearly shipped a null result.
"""

from __future__ import annotations

import argparse
import math
import statistics as st
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
from measure_stitch_direction import orientation_field

from app.services import direction_field as DF
from app.services.digitizer import digitize_image

DEFAULT_IMAGE = BACKEND / "tests/fixtures/reference_sewout.jpg"
HOOP = "360x350"
MAX_COLORS = 12
# Pinned so a rerun reproduces the digitize these numbers came from. Colour
# clustering is seeded; an unpinned run moves the region set and every score.
RNG_SEED = 20260728


def stitch_type_of(o) -> str:
    t = o.stitch_type
    return (t.value if hasattr(t, "value") else str(t)).lower()


def is_tatami(o) -> bool:
    t = stitch_type_of(o)
    return "tatami" in t or "fill" in t


def is_satin(o) -> bool:
    return "satin" in stitch_type_of(o)


def rasterise(design, h: int, w: int):
    """Per-object masks in SOURCE pixels, plus the territory masks.

    Design coordinates live in hoop space, not a 0-based box, so the mapping runs
    from the artwork's own extents to the frame. A bare multiply puts every
    region off-image and silently scores a blank mask.
    """
    pts = [p for o in design.objects for p in (o.contour or [])]
    ox, oy = min(p.x for p in pts), min(p.y for p in pts)
    ex, ey = max(p.x for p in pts), max(p.y for p in pts)
    sx, sy = w / max(ex - ox, 1e-6), h / max(ey - oy, 1e-6)

    def to_px(p):
        return [int(np.clip((p.x - ox) * sx, 0, w - 1)),
                int(np.clip((p.y - oy) * sy, 0, h - 1))]

    objs = [o for o in design.objects if o.contour]
    masks, per_stop = [], {}
    everything = np.zeros((h, w), np.uint8)
    tatami = np.zeros((h, w), np.uint8)
    satin = np.zeros((h, w), np.uint8)
    for o in objs:
        one = np.zeros((h, w), np.uint8)
        cv2.fillPoly(one, [np.array([to_px(p) for p in o.contour], np.int32)], 255)
        for hole in (o.holes or []):
            cv2.fillPoly(one, [np.array([to_px(p) for p in hole], np.int32)], 0)
        masks.append(one)
        everything = cv2.bitwise_or(everything, one)
        prev = per_stop.get(o.color_stop)
        per_stop[o.color_stop] = one.copy() if prev is None else cv2.bitwise_or(prev, one)
        if is_tatami(o):
            tatami = cv2.bitwise_or(tatami, one)
        elif is_satin(o):
            satin = cv2.bitwise_or(satin, one)
    return objs, masks, per_stop, everything, tatami, satin


def per_cluster_field(per_stop: dict, everything) -> DF.DirectionField:
    """Solve each colour cluster on its own mask and composite.

    Each cluster writes only inside its own mask so no cluster's flow leaks into
    another's territory. This is the seed a pipeline could actually use: cluster
    masks exist before any fill is generated, and the cost is bounded by the
    CLUSTER count rather than the contour count -- the multiplier behind the
    Part 48 and Part 49 blowups.
    """
    h, w = everything.shape[:2]
    c = np.zeros((h, w), np.float32)
    s = np.zeros((h, w), np.float32)
    for m in per_stop.values():
        f = DF.solve(m)
        sel = m > 0
        c[sel] = np.asarray(f.c, np.float32)[sel]
        s[sel] = np.asarray(f.s, np.float32)[sel]
    return DF.DirectionField(c=c, s=s, mask=everything)


def regional_mean_angles(field, objs, masks) -> dict[int, float]:
    """The one angle per tatami region a scanline fill could be handed.

    Doubled-angle mean, so mean(179, 1) is 0 and not 90. Degenerate regions --
    where the field cancels over the region and the magnitude is ~0 -- still
    return an angle here; whether that is wise is what the sweep measures, not
    something to decide by assertion.
    """
    out = {}
    fc, fs = np.asarray(field.c), np.asarray(field.s)
    for i, o in enumerate(objs):
        if not is_tatami(o):
            continue
        sel = masks[i] > 0
        if not sel.any():
            continue
        out[i] = math.degrees(0.5 * math.atan2(float(fs[sel].mean()),
                                               float(fc[sel].mean()))) % 180.0
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    ap.add_argument("--seeds", type=int, default=4, help="random-control trials")
    args = ap.parse_args()

    src = cv2.imread(str(args.image))
    if src is None:
        print(f"cannot read {args.image}", file=sys.stderr)
        return 1
    ref_theta, ref_coh = orientation_field(src)
    h, w = src.shape[:2]

    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(args.image.read_bytes(), "cotton", HOOP, MAX_COLORS)
    objs, masks, per_stop, everything, tatami, satin = rasterise(design, h, w)

    area = max(int((everything > 0).sum()), 1)
    print(f"{args.image.name}  {w}x{h}   {len(objs)} regions, "
          f"{len(per_stop)} colour stops, {sum(is_tatami(o) for o in objs)} tatami")
    print(f"area: tatami {100 * int((tatami > 0).sum()) / area:.1f}%   "
          f"satin {100 * int((satin > 0).sum()) / area:.1f}%\n")

    def report(label, fld):
        vals = [score_field(DF.DirectionField(c=fld.c, s=fld.s, mask=terr),
                            ref_theta, ref_coh)["mean_deg"]
                for terr in (everything, tatami, satin)]
        print(f"{label:46s} {vals[0]:8.2f} {vals[1]:8.2f} {vals[2]:8.2f}")
        return vals

    def as_regions(overrides):
        return DF.per_object_field(everything, [
            (m, math.radians(overrides.get(i, float(o.stitch_angle))))
            for i, (o, m) in enumerate(zip(objs, masks))])

    t0 = time.perf_counter()
    union = DF.solve(everything)
    t_union = time.perf_counter() - t0
    t0 = time.perf_counter()
    clustered = per_cluster_field(per_stop, everything)
    t_cluster = time.perf_counter() - t0

    print(f"{'PER-PIXEL — the ceiling a straight row cannot reach':46s} "
          f"{'WHOLE':>8s} {'TATAMI':>8s} {'SATIN':>8s}")
    report("  seed: union of every object contour", union)
    report("  seed: per colour cluster, composited", clustered)
    print(f"  solve cost: union {t_union:.2f}s (1)   "
          f"per-cluster {t_cluster:.2f}s ({len(per_stop)})")

    print(f"\n{'ONE ANGLE PER REGION — what a scanline fill can use':46s} "
          f"{'WHOLE':>8s} {'TATAMI':>8s} {'SATIN':>8s}")
    base = report("  current: the region's principal axis", as_regions({}))
    from_union = report("  field regional mean, union seed",
                        as_regions(regional_mean_angles(union, objs, masks)))
    report("  field regional mean, per-cluster seed",
           as_regions(regional_mean_angles(clustered, objs, masks)))

    tat_idx = [i for i, o in enumerate(objs) if is_tatami(o)]
    print(f"\n{'CONTROLS — a policy a constant matches proves nothing':46s} "
          f"{'WHOLE':>8s} {'TATAMI':>8s} {'SATIN':>8s}")
    for const in (0.0, 45.0, 90.0):
        report(f"  constant {const:.0f} deg on every tatami region",
               as_regions({i: const for i in tat_idx}))
    if args.seeds > 0:
        rng = np.random.default_rng(7)
        trials = [report(f"  random angle per region, seed {t}",
                         as_regions({i: float(rng.uniform(0, 180)) for i in tat_idx}))
                  for t in range(args.seeds)]
        print(f"{'  random, mean of ' + str(len(trials)):46s} "
              f"{st.mean(t[0] for t in trials):8.2f} {st.mean(t[1] for t in trials):8.2f} "
              f"{st.mean(t[2] for t in trials):8.2f}")

    ceiling = report("  (ceiling again, for the arithmetic below)", union)
    available = base[1] - ceiling[1]
    captured = base[1] - from_union[1]
    print(f"\nOn tatami territory: the field is worth {available:.2f} deg per pixel; "
          f"collapsing it\nto one angle per region captures {captured:.2f} deg of that "
          f"({100 * captured / max(available, 1e-9):.0f}%). "
          f"The rest\nis unreachable while fill rows are straight.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
