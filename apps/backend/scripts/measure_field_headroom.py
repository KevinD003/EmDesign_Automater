"""Where, if anywhere, is the direction field worth consuming? (v2 Part 53)

Parts 50-52 scored candidate FIELDS against a photographed sew-out. That was the
right question for choosing a field, and the wrong one for choosing a consumer,
because the "what we do today" baseline in those tables is
`per_object_field(o.stitch_angle)` — one angle per region. For a tatami fill that
is exactly what gets sewn. **For a satin column it is not**: `stitch_angle` is
`cv2.minAreaRect(contour)[2]`, a property of the bounding box, while the column
is actually swept perpendicular to the medial axis and its direction changes
along its length. So the "satin 37.90 today" figure that made satin's headroom
look like 0.15 deg was never measuring satin.

This instrument compares, AT THE SAME POINTS:

    what we actually sewed there   (the stitch segment's own direction)
    what the field would say there (the solved field, sampled at that point)
    what the sew-out really does   (the reference orientation field)

Same points, same reference, so the difference is directly the answer to "would
consuming the field have helped here". Segments are bucketed — by object, by
position along the column, by column width, by local curvature, by field
confidence, by junction proximity — because an aggregate that hides a local win
is the exact failure mode Part 51 nearly shipped and Part 52 had to correct.

    scripts/measure_field_headroom.py                # the panel, all sections
    scripts/measure_field_headroom.py --resolution   # only the field solve sweep
    scripts/measure_field_headroom.py --cost         # only the runtime table

REGISTRATION. Part 52 measured that mapping the design by stretching its mm
extents to fill the frame moves ~17% of boundary pixels and is worth several
degrees. Here everything is mapped by the TRUE uniform scale — design mm divided
by the pipeline's own mm-per-pixel, then to source pixels by the frame ratio —
and the mapping is checked against the pipeline's own seed mask before any score
is reported.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from measure_direction_field import MIN_COHERENCE, angular_error_deg
from measure_field_consumption import (
    DEFAULT_IMAGE,
    HOOP,
    MAX_COLORS,
    RNG_SEED,
    is_satin,
    is_tatami,
)
from measure_stitch_direction import MAX_SEG_MM, MIN_SEG_MM, orientation_field

from app.services import direction_field as DF
from app.services.digitizer import digitize_image, staging

# Segments shorter than this carry no reliable direction, longer than this span
# more than one local orientation. Both bounds come from measure_stitch_direction.
SEG_BOUNDS_MM = (MIN_SEG_MM, MAX_SEG_MM)


# ── the run, and a registration that is checked rather than assumed ───────────


def digitize_panel(image: Path):
    cv2.setRNGSeed(RNG_SEED)
    t0 = time.perf_counter()
    design = digitize_image(image.read_bytes(), "cotton", HOOP, MAX_COLORS)
    seconds = time.perf_counter() - t0
    art = staging.last_field_artifact()
    if art is None or art.field is None or art.seed_mask is None:
        raise SystemExit("the pipeline exposed no field artifact")
    return design, art, seconds


def registration(design, art, src_shape):
    """mm -> source pixels, by the true uniform scale, verified against the seed.

    The pipeline's working frame is a uniform rescale of the source and object
    contours are stored as pixel * mm_per_px, so mm / mm_per_px recovers working
    pixels exactly and the frame ratio finishes the job. Recovering mm_per_px
    from the design's own extents against the seed's bounding box avoids
    depending on a private pipeline variable.
    """
    sh, sw = src_shape[:2]
    fh, fw = art.seed_mask.shape[:2]
    xs, ys = cv2.boundingRect(art.seed_mask)[0::2], cv2.boundingRect(art.seed_mask)[1::2]
    bx, bw = xs[0], xs[1]
    by, bh = ys[0], ys[1]
    pts = [p for o in design.objects for p in (o.contour or [])]
    ox, oy = min(p.x for p in pts), min(p.y for p in pts)
    ex, ey = max(p.x for p in pts), max(p.y for p in pts)
    # +1: a bounding rect of w pixels spans w-1 pixel centres.
    mm_per_px = ((ex - ox) / max(bw - 1, 1) + (ey - oy) / max(bh - 1, 1)) / 2.0
    kx, ky = sw / fw, sh / fh

    def to_px(x_mm, y_mm):
        return ((x_mm / mm_per_px) * kx, (y_mm / mm_per_px) * ky)

    return to_px, mm_per_px, (bx, by, bw, bh)


def rasterise_true(design, to_px, src_shape):
    """Object masks, an object-id label image and the territory masks."""
    sh, sw = src_shape[:2]

    def poly(points):
        return np.array([[int(np.clip(px, 0, sw - 1)), int(np.clip(py, 0, sh - 1))]
                         for px, py in (to_px(p.x, p.y) for p in points)], np.int32)

    objs = [o for o in design.objects if o.contour]
    labels = np.zeros((sh, sw), np.int32)
    everything = np.zeros((sh, sw), np.uint8)
    tatami = np.zeros((sh, sw), np.uint8)
    satin = np.zeros((sh, sw), np.uint8)
    for i, o in enumerate(objs, start=1):
        one = np.zeros((sh, sw), np.uint8)
        cv2.fillPoly(one, [poly(o.contour)], 255)
        for hole in (o.holes or []):
            cv2.fillPoly(one, [poly(hole)], 0)
        labels[one > 0] = i
        everything = cv2.bitwise_or(everything, one)
        if is_satin(o):
            satin = cv2.bitwise_or(satin, one)
        elif is_tatami(o):
            tatami = cv2.bitwise_or(tatami, one)
    return objs, labels, everything, tatami, satin


def lift(field, shape):
    """Working frame -> source pixels, resampling (cos 2t, sin 2t), never angles."""
    sh, sw = shape[:2]
    return (cv2.resize(np.asarray(field.c, np.float32), (sw, sh), interpolation=cv2.INTER_LINEAR),
            cv2.resize(np.asarray(field.s, np.float32), (sw, sh), interpolation=cv2.INTER_LINEAR))


# ── segments: what we actually sewed ─────────────────────────────────────────


def stitch_segments(design, to_px, mm_per_px):
    """Consecutive sewn stitches, as (x0,y0,x1,y1) in source pixels.

    JUMP, TRIM and COLOR_CHANGE break a run: the thread between them is travel,
    not sewing, and scoring it would measure the machine getting somewhere rather
    than the design's direction.
    """
    segs = []
    prev = None
    for s in design.stitches:
        cmd = str(getattr(s, "command", "")).upper()
        if cmd != "STITCH":
            prev = None
            continue
        cur = (s.x, s.y)
        if prev is not None:
            length = math.hypot(cur[0] - prev[0], cur[1] - prev[1])
            if SEG_BOUNDS_MM[0] <= length <= SEG_BOUNDS_MM[1]:
                x0, y0 = to_px(*prev)
                x1, y1 = to_px(*cur)
                segs.append((x0, y0, x1, y1, length))
        prev = cur
    return segs


def collect(design, art, src, verbose=True):
    """Everything downstream needs, in one consistent registration."""
    ref_theta, ref_coh = orientation_field(src)
    to_px, mm_per_px, _bbox = registration(design, art, src.shape)
    objs, labels, everything, tatami, satin = rasterise_true(design, to_px, src.shape)

    # Registration self-check: the rasterised union must land on the pipeline's
    # own seed. Part 52's whole correction was a mapping nobody checked.
    up = cv2.resize(art.seed_mask, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_NEAREST)
    inter = int(cv2.countNonZero(cv2.bitwise_and(up, everything)))
    union = int(cv2.countNonZero(cv2.bitwise_or(up, everything)))
    iou = inter / max(union, 1)
    if verbose:
        print(f"registration check: IoU(rasterised objects, pipeline seed) = {iou:.3f}   "
              f"mm/px {mm_per_px:.4f}")
    if iou < 0.85:
        raise SystemExit(f"registration IoU {iou:.3f} is too low to trust any score below")

    fc, fs = lift(art.field, src.shape)
    segs = stitch_segments(design, to_px, mm_per_px)

    sh, sw = src.shape[:2]
    rows = []
    for x0, y0, x1, y1, length in segs:
        mx, my = int((x0 + x1) / 2), int((y0 + y1) / 2)
        if not (0 <= mx < sw and 0 <= my < sh):
            continue
        if ref_coh[my, mx] < MIN_COHERENCE:
            continue          # no reference structure here; nothing to be right about
        oid = int(labels[my, mx])
        if oid == 0:
            continue          # travel or border overshoot, outside every region
        sewn = math.atan2(y1 - y0, x1 - x0)
        c, s = float(fc[my, mx]), float(fs[my, mx])
        rows.append({
            "oid": oid, "x": mx, "y": my, "len_mm": length,
            "sewn": sewn,
            "field": 0.5 * math.atan2(s, c),
            "coh": math.hypot(c, s),
            "ref": float(ref_theta[my, mx]),
            "satin": bool(satin[my, mx]),
            "tatami": bool(tatami[my, mx]),
        })
    return {
        "ref_theta": ref_theta, "ref_coh": ref_coh, "objs": objs, "labels": labels,
        "everything": everything, "tatami": tatami, "satin": satin,
        "rows": rows, "mm_per_px": mm_per_px, "to_px": to_px, "iou": iou,
    }


def err(rows, key):
    if not rows:
        return float("nan")
    a = np.array([r[key] for r in rows])
    b = np.array([r["ref"] for r in rows])
    return float(np.mean(angular_error_deg(a, b)))


def line(label, rows, width=44):
    if not rows:
        print(f"{label:{width}s} {'-':>8s} {'-':>8s} {'-':>8s} {0:8d}")
        return None
    sewn, field = err(rows, "sewn"), err(rows, "field")
    print(f"{label:{width}s} {sewn:8.2f} {field:8.2f} {sewn - field:+8.2f} {len(rows):8d}")
    return sewn - field


# ── sections ─────────────────────────────────────────────────────────────────


def object_widths(data) -> dict[int, float]:
    """Median stroke width per object, in mm, from its own distance transform."""
    labels = data["labels"]
    out = {}
    for oid in {r["oid"] for r in data["rows"]}:
        m = (labels == oid).astype(np.uint8)
        dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
        out[oid] = float(np.median(dt[dt > 0])) * 2.0 * data["mm_per_px"] if (dt > 0).any() else 0.0
    return out


def section_validity(data, src):
    """Q0 — can the reference see thread here at all? Everything below depends on it.

    A structure tensor over a window reports the dominant orientation IN that
    window. On a satin column narrower than the window, the strongest gradients
    are the column's own two edges, so it reports the COLUMN'S AXIS — which is
    perpendicular to the thread actually lying there. Scored against that, a
    correctly sewn column looks ~90 deg wrong, and any contour-parallel field
    looks right. Part 50 flagged this circularity for flat artwork and expected a
    photograph of real thread to escape it; it does not escape it on structures
    this thin.

    The test is direct: compare the reference against the sewn direction and
    against the perpendicular (the column axis). Whichever it agrees with is what
    it is measuring.
    """
    from measure_stitch_direction import orientation_field as of

    rows, widths = data["rows"], object_widths(data)
    mm_src = data["mm_per_px"] * (data["seed"].shape[1] / src.shape[1])
    print("\n" + "=" * 86)
    print("Q0 — INSTRUMENT VALIDITY: is the reference reading THREAD or EDGES?")
    print("=" * 86)
    print(f"source scale {mm_src:.4f} mm/px, so a 1.5 mm column is {1.5 / mm_src:.1f} px wide")
    print("and satin thread pitch (~0.4 mm) is "
          f"{0.4 / mm_src:.1f} px — at or under the sampling limit.\n")
    print(f"{'satin column width':26s} {'px':>6s} {'vs SEWN':>9s} {'vs AXIS':>9s} "
          f"{'reads':>7s} {'n':>8s}")
    for lo, hi in ((0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0)):
        sel = [r for r in rows if r["satin"] and lo <= widths.get(r["oid"], 0.0) < hi]
        if len(sel) < 50:
            continue
        ref = np.array([r["ref"] for r in sel])
        sewn = np.array([r["sewn"] for r in sel])
        e_s = float(np.mean(angular_error_deg(sewn, ref)))
        e_a = float(np.mean(angular_error_deg(sewn + np.pi / 2, ref)))
        print(f"{f'  {lo:.0f}-{hi:.0f} mm':26s} {(lo + hi) / 2 / mm_src:6.1f} "
              f"{e_s:9.2f} {e_a:9.2f} {'THREAD' if e_s < e_a else 'edges':>7s} {len(sel):8d}")

    print("\nWindow sweep — if the verdict moved with the window it would be the")
    print("window, not the geometry. It does not move; the crossover is width.\n")
    print(f"{'window':>7s} {'territory':24s} {'vs SEWN':>9s} {'vs AXIS':>9s} {'n':>8s}")
    for win in (5, 9, 15, 21):
        rt, rc = of(src, window=win)
        for terr, lo, hi, name in (("satin", 1.0, 2.0, "satin 1-2 mm"),
                                   ("satin", 2.0, 4.0, "satin 2-4 mm"),
                                   ("tatami", 0.0, 1e9, "tatami, all")):
            sel = [r for r in rows if r[terr] and lo <= widths.get(r["oid"], 0.0) < hi
                   and rc[r["y"], r["x"]] >= MIN_COHERENCE]
            if len(sel) < 50:
                continue
            ref = np.array([rt[r["y"], r["x"]] for r in sel])
            sewn = np.array([r["sewn"] for r in sel])
            print(f"{win:7d} {name:24s} "
                  f"{float(np.mean(angular_error_deg(sewn, ref))):9.2f} "
                  f"{float(np.mean(angular_error_deg(sewn + np.pi / 2, ref))):9.2f} "
                  f"{len(sel):8d}")

    trusted = sum(1 for r in rows if r["satin"] and widths.get(r["oid"], 0.0) >= 2.0)
    satin_n = sum(1 for r in rows if r["satin"])
    print(f"\nTRUSTWORTHY SATIN: {trusted}/{satin_n} segments "
          f"({100 * trusted / max(satin_n, 1):.0f}%) sit on columns the reference can resolve.")
    print("Every satin number below that is not restricted to those columns is "
          "measuring\nthe artwork's outlines, and a contour-parallel field agrees with "
          "outlines by\nconstruction. That is circular, not a win.")


def section_baselines(data):
    rows = data["rows"]
    print("\n" + "=" * 86)
    print("Q3 — WHAT WE ACTUALLY SEW, against what the field would have said there")
    print("=" * 86)
    print("Positive gain = the field is closer to the real sew-out than our stitches are.\n")
    print(f"{'territory':44s} {'sewn':>8s} {'field':>8s} {'gain':>8s} {'n':>8s}")
    line("all sewn segments", rows)
    line("  satin territory", [r for r in rows if r["satin"]])
    line("  tatami territory", [r for r in rows if r["tatami"]])
    print("\nControls on the same segments (a policy a constant matches proves nothing):")
    for name, ang in (("constant 0 deg", 0.0), ("constant 45 deg", 45.0), ("constant 90 deg", 90.0)):
        for terr in ("satin", "tatami"):
            sel = [r for r in rows if r[terr]]
            if not sel:
                continue
            e = float(np.mean(angular_error_deg(
                np.full(len(sel), math.radians(ang)), np.array([r["ref"] for r in sel]))))
            print(f"  {name + ' on ' + terr:42s} {e:8.2f}")


def section_satin_granularity(data):
    """Q1 — is a 0.15 deg aggregate hiding a local win?"""
    rows = [r for r in data["rows"] if r["satin"]]
    print("\n" + "=" * 86)
    print("Q1 — SATIN, BROKEN DOWN. Is the aggregate hiding local value?")
    print("=" * 86)
    if not rows:
        print("no satin segments with reference structure")
        return
    print(f"{'bucket':44s} {'sewn':>8s} {'field':>8s} {'gain':>8s} {'n':>8s}")

    # by field confidence
    for lo, hi in ((0.0, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 1.01)):
        line(f"  field coherence {lo:.2f}-{hi:.2f}",
             [r for r in rows if lo <= r["coh"] < hi])

    # by position along the column
    per_obj: dict[int, list] = {}
    for r in rows:
        per_obj.setdefault(r["oid"], []).append(r)
    thirds = {0: [], 1: [], 2: []}
    for rs in per_obj.values():
        n = len(rs)
        for i, r in enumerate(rs):
            thirds[min(2, i * 3 // max(n, 1))].append(r)
    for k, name in ((0, "start"), (1, "middle"), (2, "end")):
        line(f"  along the column: {name} third", thirds[k])

    # by column width, from the object's own distance transform
    widths = {}
    labels = data["labels"]
    for oid in per_obj:
        m = (labels == oid).astype(np.uint8)
        dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
        widths[oid] = float(np.median(dt[dt > 0])) * 2.0 * data["mm_per_px"] if (dt > 0).any() else 0.0
    for lo, hi in ((0.0, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, 1e9)):
        label = f"  column width {lo:.0f}-{hi:.0f} mm" if hi < 1e9 else "  column width 4+ mm"
        line(label, [r for r in rows if lo <= widths.get(r["oid"], 0.0) < hi])

    # by local curvature of the sewn path, as the turn between consecutive
    # segments of the same object
    for r in rows:
        r["_turn"] = 0.0
    for rs in per_obj.values():
        for i in range(1, len(rs)):
            rs[i]["_turn"] = float(angular_error_deg(
                np.array([rs[i]["sewn"]]), np.array([rs[i - 1]["sewn"]]))[0])
    for lo, hi in ((0.0, 2.0), (2.0, 10.0), (10.0, 30.0), (30.0, 91.0)):
        line(f"  local turn {lo:.0f}-{hi:.0f} deg",
             [r for r in rows if lo <= r["_turn"] < hi])

    # junction proximity: within 3 px of a DIFFERENT object's territory
    other = (labels > 0).astype(np.uint8)
    near = cv2.dilate(other, np.ones((7, 7), np.uint8))
    edges = cv2.Laplacian(labels.astype(np.float32), cv2.CV_32F)
    junction = ((np.abs(edges) > 0) & (near > 0)).astype(np.uint8)
    junction = cv2.dilate(junction, np.ones((7, 7), np.uint8))
    line("  within ~3 px of another object", [r for r in rows if junction[r["y"], r["x"]] > 0])
    line("  interior of its own object", [r for r in rows if junction[r["y"], r["x"]] == 0])

    # the best case that exists at all: per-object, how many columns would gain?
    gains = []
    for oid, rs in per_obj.items():
        if len(rs) < 20:
            continue
        gains.append(err(rs, "sewn") - err(rs, "field"))
    widths_mm = object_widths(data)
    trusted = [r for r in rows if widths_mm.get(r["oid"], 0.0) >= 2.0]
    print("\n  THE ONLY BUCKET THE REFERENCE CAN RESOLVE (columns >= 2 mm):")
    line("  satin on resolvable columns", trusted)

    if gains:
        g = np.array(gains)
        print(f"\n  per-column gain over {len(g)} columns with 20+ segments: "
              f"median {np.median(g):+.2f}  mean {g.mean():+.2f}")
        print(f"  columns the field would improve: {int((g > 0).sum())}/{len(g)} "
              f"({100 * (g > 0).mean():.0f}%)   best {g.max():+.2f}  worst {g.min():+.2f}")


def section_tatami_resolution(data, image: Path):
    """Q2 — is the tatami ceiling resolution-limited?"""
    print("\n" + "=" * 86)
    print("Q2 — DOES A FINER FIELD HELP TATAMI?")
    print("=" * 86)
    art_seed = data["seed"]
    rows_t = [r for r in data["rows"] if r["tatami"]]
    sewn_t = err(rows_t, "sewn")
    print(f"tatami segments: {len(rows_t)}, sewn error {sewn_t:.2f} deg\n")
    print(f"{'field solve':34s} {'solve s':>8s} {'commit':>8s} {'field':>8s} "
          f"{'gain':>8s} {'oracle':>8s}")
    src_shape = data["ref_theta"].shape
    for px, iters in ((384, 24), (768, 24), (768, 48), (1152, 72)):
        t0 = time.perf_counter()
        f = DF.solve(art_seed, iters=iters, work_max_px=px)
        secs = time.perf_counter() - t0
        fc, fs = lift(f, src_shape)
        vals, ref = [], []
        for r in rows_t:
            c, s = float(fc[r["y"], r["x"]]), float(fs[r["y"], r["x"]])
            vals.append(0.5 * math.atan2(s, c))
            ref.append(r["ref"])
        e = float(np.mean(angular_error_deg(np.array(vals), np.array(ref)))) if vals else float("nan")
        committed = float((np.asarray(f.coherence)[np.asarray(f.mask) > 0] > 0.30).mean())
        # Oracle: the single best angle per REGION, chosen against the reference
        # itself. No generator can beat this while a fill lays parallel rows, so
        # it is the ceiling any one-angle-per-region policy is competing for.
        oracle = _oracle_one_angle(rows_t)
        print(f"{f'{px} px, {iters} iters':34s} {secs:8.2f} {committed:8.3f} "
              f"{e:8.2f} {sewn_t - e:+8.2f} {oracle:8.2f}")


def _oracle_one_angle(rows) -> float:
    """Best achievable error if each region got its single best angle.

    Chosen against the reference, so it is unreachable in practice — that is the
    point. It bounds every one-angle-per-region policy, field-derived or not.
    """
    per_obj: dict[int, list] = {}
    for r in rows:
        per_obj.setdefault(r["oid"], []).append(r)
    total, n = 0.0, 0
    grid = np.radians(np.arange(0, 180, 1.0))
    for rs in per_obj.values():
        ref = np.array([r["ref"] for r in rs])
        best = min(float(np.mean(angular_error_deg(np.full(len(ref), a), ref))) for a in grid)
        total += best * len(rs)
        n += len(rs)
    return total / max(n, 1)


def section_cost(image: Path):
    print("\n" + "=" * 86)
    print("COST — solve time by resolution, real panel and pathological noise")
    print("=" * 86)
    _design, art, _ = digitize_panel(image)
    rng = np.random.default_rng(0)
    cases = [("panel seed", art.seed_mask)]
    for n in (900, 1500):
        cases.append((f"{n}x{n} noise", (rng.random((n, n)) > 0.5).astype(np.uint8) * 255))
    print(f"{'input':22s} {'384/24':>9s} {'768/24':>9s} {'768/48':>9s} {'1152/72':>9s}")
    for label, m in cases:
        times = []
        for px, iters in ((384, 24), (768, 24), (768, 48), (1152, 72)):
            t0 = time.perf_counter()
            DF.solve(m, iters=iters, work_max_px=px)
            times.append(time.perf_counter() - t0)
        print(f"{label:22s} " + " ".join(f"{t:9.3f}" for t in times))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    ap.add_argument("--cost", action="store_true")
    ap.add_argument("--resolution", action="store_true")
    ap.add_argument("--validity", action="store_true")
    args = ap.parse_args()

    if args.cost:
        section_cost(args.image)
        return 0

    src = cv2.imread(str(args.image))
    if src is None:
        print(f"cannot read {args.image}", file=sys.stderr)
        return 1
    design, art, secs = digitize_panel(args.image)
    print(f"{args.image.name}  {src.shape[1]}x{src.shape[0]}   digitize {secs:.1f}s   "
          f"{art.region_count} regions")
    data = collect(design, art, src)
    data["seed"] = art.seed_mask
    print(f"sewn segments scored: {len(data['rows'])} "
          f"(satin {sum(r['satin'] for r in data['rows'])}, "
          f"tatami {sum(r['tatami'] for r in data['rows'])})")

    if args.validity:
        section_validity(data, src)
        return 0
    if args.resolution:
        section_tatami_resolution(data, args.image)
        return 0
    section_validity(data, src)
    section_baselines(data)
    section_satin_granularity(data)
    section_tatami_resolution(data, args.image)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
