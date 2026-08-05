"""How much of the fragmentation is actually mergeable? (v2 Part 55, R005 scoping)

R005 has been open since Part 46 as "median 19 stitches per object". That is a
symptom, not a target: a design of 771 objects is only a defect if those objects
*should* have been fewer. Petals of a flower are legitimately separate; three
fragments of one stroke that morphology cut apart are not.

So this measures the thing an implementation would actually act on: **within a
single colour stop, how many objects sit close enough to another object that a
digitizer would have treated them as one region** — and what merging them would
cost and save.

    scripts/measure_fragmentation.py                 # panel + bench
    scripts/measure_fragmentation.py --only 07_circular_badge

Two rules that are not negotiable and shape every number here:

* **Only within a colour stop.** Merging across stops would reorder colour
  changes and can put light thread under dark. Part 48 declined the same thing
  for trims and it is declined here.
* **Proximity is measured between the regions themselves**, not their bounding
  boxes. A ring and the dot at its centre have overlapping boxes and are not
  adjacent.

Cost is bounded bounding-box-locally, per Parts 48/49: the work per object is
proportional to that object's own area, never to the frame.
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.digitizer import digitize_image, staging

PANEL = BACKEND / "tests/fixtures/reference_sewout.jpg"
GAPS_MM = (0.0, 0.4, 0.8, 1.5, 3.0)


class _Union:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def neighbours_within(labels: np.ndarray, n_obj: int, gap_px: int):
    """Pairs of object ids whose regions come within `gap_px`.

    `gap_px` is a dilation RADIUS applied to one region at a time, so it must
    reach across the whole clear span to land on its neighbour — regions with
    `gap_px - 1` clear pixels between them are linked.

    Dilation is done inside each object's own bounding box, expanded by the gap.
    A full-frame dilate per object is the Part 48/49 trap — the multiplier there
    is the object count, which on a fragmented design is exactly what is large.
    """
    h, w = labels.shape
    k = np.ones((2 * gap_px + 1, 2 * gap_px + 1), np.uint8) if gap_px > 0 else None
    pairs: set[tuple[int, int]] = set()
    # Bounding boxes in ONE pass over the frame. Doing `np.where(labels == oid)`
    # per object is a full-frame scan multiplied by the object count — the exact
    # Parts 48/49 shape, and on a fragmented design the object count is the large
    # number. A test pins this; it failed when the per-object version was here.
    boxes: dict[int, tuple[int, int, int, int]] = {}
    ys_all, xs_all = np.nonzero(labels)
    if len(ys_all):
        ids = labels[ys_all, xs_all]
        order = np.argsort(ids, kind="stable")
        ids, xs_s, ys_s = ids[order], xs_all[order], ys_all[order]
        starts = np.searchsorted(ids, np.unique(ids))
        bounds = list(starts) + [len(ids)]
        for idx, oid in enumerate(np.unique(ids)):
            lo, hi = bounds[idx], bounds[idx + 1]
            boxes[int(oid)] = (int(xs_s[lo:hi].min()), int(xs_s[lo:hi].max()),
                               int(ys_s[lo:hi].min()), int(ys_s[lo:hi].max()))
    for oid, (x0, x1, y0, y1) in boxes.items():
        gx0, gx1 = max(0, x0 - gap_px - 1), min(w, x1 + gap_px + 2)
        gy0, gy1 = max(0, y0 - gap_px - 1), min(h, y1 + gap_px + 2)
        sub = labels[gy0:gy1, gx0:gx1]
        mine = (sub == oid).astype(np.uint8)
        grown = cv2.dilate(mine, k) if k is not None else mine
        touching = np.unique(sub[(grown > 0) & (sub != oid) & (sub > 0)])
        for other in touching:
            a, b = int(min(oid, other)), int(max(oid, other))
            pairs.add((a, b))
    return pairs


def analyse(design, art, label: str):
    objs = [o for o in design.objects if o.contour]
    if not objs:
        print(f"{label}: no objects")
        return None
    counts = [o.stitch_count for o in objs]
    h, w = art.seed_mask.shape[:2]
    # mm per working pixel, from the design's own extents against the seed bbox.
    pts = [p for o in objs for p in o.contour]
    ox, oy = min(p.x for p in pts), min(p.y for p in pts)
    ex, ey = max(p.x for p in pts), max(p.y for p in pts)
    _bx, _by, bw, bh = cv2.boundingRect(art.seed_mask)
    mm_per_px = ((ex - ox) / max(bw - 1, 1) + (ey - oy) / max(bh - 1, 1)) / 2.0

    labels = np.zeros((h, w), np.int32)
    stops = {}
    for i, o in enumerate(objs, start=1):
        poly = np.array([[int(np.clip(p.x / mm_per_px, 0, w - 1)),
                          int(np.clip(p.y / mm_per_px, 0, h - 1))] for p in o.contour], np.int32)
        one = np.zeros((h, w), np.uint8)
        cv2.fillPoly(one, [poly], 255)
        labels[one > 0] = i
        stops[i] = o.color_stop

    print(f"\n{label}")
    print(f"  {len(objs)} objects across {len(set(stops.values()))} colour stops, "
          f"{len(design.stitches)} stitches")
    print(f"  stitches/object: median {st.median(counts)}  "
          f"p25 {int(np.percentile(counts, 25))}  p75 {int(np.percentile(counts, 75))}  "
          f"max {max(counts)}")
    tiny = sum(1 for c in counts if c <= 25)
    print(f"  objects of 25 stitches or fewer: {tiny} ({100 * tiny / len(objs):.0f}%)")

    print(f"  {'gap':>6s} {'groups':>8s} {'merged away':>12s} {'largest group':>14s}")
    rows = []
    for gap_mm in GAPS_MM:
        gap_px = round(gap_mm / mm_per_px)
        pairs = neighbours_within(labels, len(objs), gap_px)
        uf = _Union(len(objs) + 1)
        for a, b in pairs:
            if stops[a] == stops[b]:      # same colour stop only
                uf.join(a, b)
        groups: dict[int, int] = {}
        for i in range(1, len(objs) + 1):
            groups[uf.find(i)] = groups.get(uf.find(i), 0) + 1
        n_groups = len(groups)
        print(f"  {gap_mm:5.1f}mm {n_groups:8d} {len(objs) - n_groups:12d} "
              f"{max(groups.values()):14d}")
        rows.append((gap_mm, n_groups, len(objs) - n_groups, max(groups.values())))
    return {"label": label, "objects": len(objs), "counts": counts, "rows": rows,
            "stitches": len(design.stitches)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()

    import visual_regression as VR

    results = []
    if not args.only or args.only == "panel":
        cv2.setRNGSeed(20260728)
        design = digitize_image(PANEL.read_bytes(), "cotton", "360x350", 12)
        results.append(analyse(design, staging.last_field_artifact(), "reference panel"))

    if args.only == "panel":
        names = []
    else:
        names = [args.only] if args.only else sorted(VR.FIXTURES)
    for name in names:
        params = VR.FIXTURES[name]
        cv2.setRNGSeed(VR.RNG_SEED)
        design = digitize_image((VR.FIXTURE_DIR / f"{name}.png").read_bytes(),
                                fabric_type=params.get("fabric", "cotton"),
                                hoop_size=params["hoop"], max_colors=params["colors"],
                                text_mode=params.get("text", False))
        results.append(analyse(design, staging.last_field_artifact(), name))

    results = [r for r in results if r]
    if len(results) > 1:
        print("\n" + "=" * 70)
        print("ACROSS EVERYTHING")
        tot_obj = sum(r["objects"] for r in results)
        print(f"  {tot_obj} objects over {len(results)} designs")
        for i, gap_mm in enumerate(GAPS_MM):
            merged = sum(r["rows"][i][2] for r in results)
            print(f"  at {gap_mm:.1f} mm: {merged} objects merge away "
                  f"({100 * merged / tot_obj:.0f}% of all objects)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
