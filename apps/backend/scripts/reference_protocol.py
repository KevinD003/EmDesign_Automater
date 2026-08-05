"""A reference that can actually judge stitch direction (v2 Part 54, R004).

Part 53 established that the photographed panel cannot answer the satin question:
a structure tensor reports the dominant orientation IN ITS WINDOW, so on a column
narrower than that window the column's two edges dominate and it returns the
column's AXIS rather than the thread lying across it. At 0.186 mm/px a 1.5 mm
column is 8 px, and 77% of satin segments sit below the width where the reading
flips.

Part 53 then recommended "roughly 0.05 mm/px". **That was arithmetic, not a
measurement.** A capture spec nobody can reproduce is exactly how the next
reference ends up as unusable as this one, so the number is derived here instead.

HOW, and why not by simulation. The obvious route is a synthetic sew-out with
known thread direction, swept over resolution. That was built first and thrown
away: a synthetic periodic thread pattern near the sampling limit aliases to zero
3-tap gradient response (Sobel over [a, b, a] is 0), so it reported "edges" at
every width and every blur, and calibrating it back to reality needed two free
parameters fitted to one observation — which would fit anything.

What is used instead is the real panel and its own scaling law: **downsample the
reference, re-measure the width at which the reading flips from edges to thread,
and see how that width moves.** Real thread, real optics, real irregularity; the
only assumption is that the law extrapolates the way it interpolates, and the
sweep shows enough points to judge that.

    scripts/reference_protocol.py --selftest    # registration, against known truth
    scripts/reference_protocol.py --spec        # derive the capture spec
    scripts/reference_protocol.py --validate IMG --mm-per-px X

Nothing here touches the engine. It is a protocol, a registration tool and a
validity check, so the next photograph can be judged before three more parts are
scored against it.
"""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from measure_direction_field import angular_error_deg
from measure_stitch_direction import ORIENT_WINDOW, orientation_field

PANEL_MM_PER_PX = 0.186          # the reference we have, measured in Part 53
PANEL_WINDOW = ORIENT_WINDOW     # 9 px
# Satin column widths present in the panel, in mm. The crossover is looked for
# among these because they are what actually has to be judged.
WIDTH_EDGES_MM = tuple(round(0.4 + 0.2 * i, 2) for i in range(29))  # 0.4-6.0 mm, 0.2 mm steps


def crossover_width(rows, widths, *, min_n: int = 200) -> float | None:
    """The width ABOVE WHICH the reference consistently reads thread, not edges.

    "Reads thread" means it agrees with the direction actually sewn there more
    than with the perpendicular — the column's own axis. Below the crossover the
    reference is describing the outline and cannot judge any direction policy.

    Scanning upward for the FIRST bucket that reads thread was tried and is
    wrong: one noisy narrow bucket ends the scan and the crossover collapses to
    the bottom of the range, which is how an earlier version of this reported
    "0.4 mm, 100% usable" at a scale Part 53 had already measured as unusable.
    The property wanted is monotone, so it is checked from the top down: the
    crossover is the lowest width from which EVERY populated bucket above also
    reads thread.
    """
    verdicts = []
    for lo, hi in itertools.pairwise(widths):
        sel = [r for r in rows if lo <= r["width_mm"] < hi]
        if len(sel) < min_n:
            continue
        ref = np.array([r["ref"] for r in sel])
        sewn = np.array([r["sewn"] for r in sel])
        thread = (float(np.mean(angular_error_deg(sewn, ref)))
                  < float(np.mean(angular_error_deg(sewn + np.pi / 2, ref))))
        verdicts.append((lo, thread))
    if not verdicts:
        return None
    crossover = None
    for lo, thread in reversed(verdicts):
        if not thread:
            break
        crossover = lo
    return crossover


# ── the tooling: registering a close crop against the pipeline's geometry ─────


def register_crop(crop, full):
    """Find where a close-up sits inside the full reference, as a similarity map.

    A macro photograph of one region is worth nothing until it can be placed in
    the same coordinate frame as the design, and Part 52 is the standing warning
    about mappings nobody checked. ORB + a partial-affine estimate recovers
    translation, rotation and scale; the caller composes it with the full frame's
    own registration.

    Returns (matrix 2x3 mapping CROP pixels -> FULL pixels, inlier count, scale).
    """
    g1 = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    g2 = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY) if full.ndim == 3 else full
    orb = cv2.ORB_create(nfeatures=8000)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8:
        return None, 0, float("nan")
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    raw = matcher.knnMatch(d1, d2, k=2)
    good = [m for m, n in (p for p in raw if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return None, len(good), float("nan")
    src = np.float32([k1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([k2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                             ransacReprojThreshold=3.0)
    if M is None:
        return None, 0, float("nan")
    scale = float(math.hypot(M[0, 0], M[1, 0]))
    return M, int(inliers.sum()) if inliers is not None else 0, scale


# ── sections ─────────────────────────────────────────────────────────────────


def _panel_rows():
    """Digitize the panel once and collect its sewn segments with column widths."""
    import measure_field_headroom as MFH

    src = cv2.imread(str(MFH.DEFAULT_IMAGE))
    design, art, _ = MFH.digitize_panel(MFH.DEFAULT_IMAGE)
    data = MFH.collect(design, art, src, verbose=False)
    widths = MFH.object_widths(data)
    rows = []
    for r in data["rows"]:
        if not r["satin"]:
            continue
        rows.append({"x": r["x"], "y": r["y"], "sewn": r["sewn"],
                     "width_mm": widths.get(r["oid"], 0.0)})
    return src, rows


def _rows_at_scale(src, rows, factor: float):
    """Re-read the reference at a coarser scale, sampling the same segments."""
    if factor >= 0.999:
        small = src
    else:
        small = cv2.resize(src, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
    theta, coh = orientation_field(small)
    h, w = small.shape[:2]
    out = []
    for r in rows:
        x = int(r["x"] * factor)
        y = int(r["y"] * factor)
        if not (0 <= x < w and 0 <= y < h) or coh[y, x] < 0.35:
            continue
        out.append({**r, "ref": float(theta[y, x])})
    return out


def selftest() -> bool:
    """Prove the registration tool against a transform we applied ourselves.

    A registration that is merely plausible is what Part 52 had to correct, so
    the check is against known truth: take a window of the panel, blow it up as a
    macro shot would, and require the tool to put it back where it came from.
    """
    ok = True
    print("SELF-TEST — crop registration against a known transform\n")
    full = cv2.imread(str(BACKEND / "tests/fixtures/reference_sewout.jpg"))
    if full is None:
        print("   reference image missing — cannot check")
        return False
    x, y, w, h = 200, 700, 300, 300
    for factor in (2.0, 3.0, 4.0):
        crop = cv2.resize(full[y:y + h, x:x + w], None, fx=factor, fy=factor,
                          interpolation=cv2.INTER_CUBIC)
        M, inl, scale = register_crop(crop, full)
        if M is None:
            print(f"   {factor:.0f}x: FAILED to register")
            ok = False
            continue
        got = M @ np.array([0.0, 0.0, 1.0])
        err = math.hypot(got[0] - x, got[1] - y)
        s_err = abs(scale - 1.0 / factor) * factor
        print(f"   {factor:.0f}x upscale: origin off by {err:5.1f} px, "
              f"scale off by {100 * s_err:4.1f}%, {inl} inliers")
        if err > 12.0 or s_err > 0.05:
            print("     not accurate enough to register a macro crop")
            ok = False
    print(f"\n   => registration {'VALID' if ok else 'INVALID'}")
    return ok


def spec() -> int:
    """Derive the capture spec from the panel's own downsample law."""
    print("\nCAPTURE SPEC, derived from the real reference\n")
    print("Downsample the panel, re-measure the column width at which the reading")
    print("flips from EDGES to THREAD, and read off how that width scales.\n")
    src, rows = _panel_rows()
    print(f"{'mm/px':>8s} {'frame':>12s} {'crossover':>11s} {'usable satin':>13s}")
    points = []
    for factor in (1.0, 0.85, 0.7, 0.55, 0.45, 0.35):
        scaled = _rows_at_scale(src, rows, factor)
        mm_px = PANEL_MM_PER_PX / factor
        cw = crossover_width(scaled, WIDTH_EDGES_MM)
        usable = (100.0 * sum(1 for r in scaled if cw is not None and r["width_mm"] >= cw)
                  / max(len(scaled), 1))
        h, w = (int(src.shape[0] * factor), int(src.shape[1] * factor))
        print(f"{mm_px:8.3f} {f'{w}x{h}':>12s} "
              f"{(f'{cw:.1f} mm' if cw else 'none'):>11s} {usable:12.0f}%")
        if cw:
            points.append((mm_px, cw))

    print()
    if len(points) >= 2:
        px = [cw / mm for mm, cw in points]
        print("crossover expressed in PIXELS: " + "  ".join(f"{v:.1f}" for v in px))
        # Deliberately NOT the mean. The ratio drifts across the sweep because two
        # limits are in play — the analysis window (fixed in pixels) binds at fine
        # scales, thread pitch (fixed in mm) binds at coarse ones — so a mean
        # back-predicts a crossover finer than the one directly measured at full
        # resolution. Extrapolating toward FINER capture uses the finest point
        # measured, which is both the relevant regime and the conservative choice.
        k = max(px[0], max(px))
        finest_mm, finest_cw = points[0]
        print(f"the finest scale measured ({finest_mm:.3f} mm/px) puts it at "
              f"{finest_cw:.1f} mm = {px[0]:.1f} px;")
        print(f"extrapolating on {k:.1f} px, the conservative end of the sweep.")
        target = 0.8
        need = target / k
        print(f"\nThe panel's narrowest satin is ~{target:.1f} mm (5th percentile 0.73 mm).")
        print(f"    capture at <= {need:.3f} mm/px  ({0.4 / need:.1f} px per 0.4 mm thread)")
        print(f"    that is {PANEL_MM_PER_PX / need:.1f}x the current panel's linear resolution")
        print(f"\nAt that scale a 360x350 mm hoop is ~{int(360 / need)}x{int(350 / need)} px,")
        print("which is not one frame from an ordinary camera. Shoot CLOSE CROPS of")
        print("individual regions and register each with `register_crop`; that is why")
        print("the registration tool exists and is self-tested above.")
        print("\nThis extrapolates BELOW the measured range, so treat it as a floor to")
        print("aim past, not a threshold to hit exactly — and re-run --spec on the new")
        print("photograph before scoring anything on it.")
    else:
        print("not enough crossover points to state a law — report the table only.")
    return 0


def validate(path: Path, mm_per_px: float | None) -> int:
    """Is a candidate reference resolving thread? Answer BEFORE scoring on it."""
    img = cv2.imread(str(path))
    if img is None:
        print(f"cannot read {path}", file=sys.stderr)
        return 1
    h, w = img.shape[:2]
    print(f"\n{path.name}  {w}x{h}")
    _theta, coh = orientation_field(img)
    print(f"oriented structure: {100 * float((coh >= 0.35).mean()):.1f}% of pixels "
          f"at coherence >= 0.35")
    if mm_per_px is None:
        print("\nno --mm-per-px given. Supply the scale to get a usability verdict;")
        print("without it this is texture, not millimetres.")
        return 0
    print(f"scale {mm_per_px:.4f} mm/px — a 0.4 mm thread is "
          f"{0.4 / mm_per_px:.1f} px, a 1.5 mm column is {1.5 / mm_per_px:.1f} px")
    print("\nTo turn this into a verdict the candidate must be digitized and its")
    print("sewn segments bucketed by column width, exactly as --spec does for the")
    print("panel: run `measure_field_headroom.py --image <this> --validity`.")
    print("A reference is usable for satin direction only when the crossover width")
    print("sits at or below the narrowest satin it must judge.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--spec", action="store_true")
    ap.add_argument("--validate", type=Path)
    ap.add_argument("--mm-per-px", type=float)
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest() else 1
    if args.validate:
        if not selftest():
            print("\nself-test failed — the verdict below would not mean anything",
                  file=sys.stderr)
            return 1
        return validate(args.validate, args.mm_per_px)
    if not selftest():
        print("\nself-test failed — the spec below would not mean anything", file=sys.stderr)
        return 1
    print()
    return spec()


if __name__ == "__main__":
    raise SystemExit(main())
