"""Score our stitch DIRECTIONS against a real sew-out photograph (v2 Part 38).

The quality bench measures whether thread covers the shape. It cannot see the
defect that makes auto-digitized work read as "not quite right": in embroidery
SHAPE IS CARRIED BY DIRECTION, and a fill laid at the wrong angle covers its
region perfectly while looking nothing like the real thing.

A photographed sew-out shows which way every thread runs, so that is measurable.
The structure tensor recovers the local thread direction; this compares ours to
it, length-weighted, folded mod 180 (a stitch has no head or tail).

    .venv/bin/python scripts/measure_stitch_direction.py photo.jpg --hoop 360x350
    .venv/bin/python scripts/measure_stitch_direction.py --self-test

Read the numbers with these anchors:
  0 deg   perfect agreement with the real sew-out
  45 deg  no better than a coin flip
  and ALWAYS run --self-test first: this instrument has been wrong before.

Known limits, so nobody over-reads a run:
  * Registration is a linear map from the design's stitch bounding box to the
    source frame. It is only as good as the digitizer's own framing; validate
    it with --check-registration, which reports how close the source colour at
    each stitch is to the thread laid there (per COLOUR STOP, since single
    pixels are noisy under photographic shading).
  * Where we stitch something the source has no thread for (a knocked-out gap
    filled as if it were ink), the comparison is meaningless for those points
    and shows up as a large per-stop colour distance.
"""

from __future__ import annotations

import argparse
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

ORIENT_WINDOW = 9
MIN_COHERENCE = 0.5
MIN_SEG_MM = 0.3
MAX_SEG_MM = 6.0


def orientation_field(img, window: int = ORIENT_WINDOW):
    """(theta, coherence): local thread direction, image axes, y down, mod pi."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    k = (window, window)
    jxx = cv2.GaussianBlur(gx * gx, k, 0)
    jyy = cv2.GaussianBlur(gy * gy, k, 0)
    jxy = cv2.GaussianBlur(gx * gy, k, 0)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-6)
    return theta, coh


def self_test() -> bool:
    """Stripes at known angles. If this fails, no run below means anything."""
    ok = True
    for true_deg in (0, 30, 45, 60, 90, 120):
        img = np.zeros((300, 300, 3), np.uint8)
        a = math.radians(true_deg)
        for k in range(-400, 400, 6):
            ox, oy = -k * math.sin(a), k * math.cos(a)
            p1 = (int(150 + ox - 500 * math.cos(a)), int(150 + oy - 500 * math.sin(a)))
            p2 = (int(150 + ox + 500 * math.cos(a)), int(150 + oy + 500 * math.sin(a)))
            cv2.line(img, p1, p2, (220, 220, 220), 2)
        theta, _ = orientation_field(img)
        est = math.degrees(float(np.median(theta[100:200, 100:200]))) % 180
        err = abs((est - true_deg + 90) % 180 - 90)
        flag = "ok " if err <= 3.0 else "FAIL"
        ok &= err <= 3.0
        print(f"  {flag} stripes at {true_deg:3d} deg -> measured {est:6.1f} (error {err:.1f})")
    return ok


def _cmd(s) -> str:
    return str(getattr(s.command, "value", s.command))


def _mapper(design, shape):
    sh, sw = shape
    pts = [(s.x, s.y) for s in design.stitches if _cmd(s) == "STITCH"]
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)

    def to_px(x, y):
        return (
            int((x - minx) / max(maxx - minx, 1e-9) * (sw - 1)),
            int((y - miny) / max(maxy - miny, 1e-9) * (sh - 1)),
        )

    return to_px


def check_registration(design, src) -> float:
    """Per-stop colour agreement. Small distances => the mapping is aligned."""
    sh, sw = src.shape[:2]
    to_px = _mapper(design, (sh, sw))

    def hexbgr(h):
        h = h.lstrip("#")
        return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)

    stops = [hexbgr(c.hex) for c in design.color_stops]
    samples = defaultdict(list)
    ci = 0
    for s in design.stitches:
        c = _cmd(s)
        if c == "COLOR_CHANGE":
            ci = min(ci + 1, len(stops) - 1)
            continue
        if c != "STITCH":
            continue
        px, py = to_px(s.x, s.y)
        if 0 <= px < sw and 0 <= py < sh:
            samples[ci].append(src[py, px].astype(np.float32))
    dists = []
    print("  stop  our thread   source median at our stitches   distance    n")
    for ci_, arr in sorted(samples.items()):
        if len(arr) < 200:
            continue
        med = np.median(np.stack(arr), axis=0)
        d = float(np.linalg.norm(med - stops[ci_]))
        dists.append(d)
        print(f"   {ci_:3d}  {design.color_stops[ci_].hex}   "
              f"({med[2]:5.0f},{med[1]:5.0f},{med[0]:5.0f})                 {d:7.1f}  {len(arr):6d}")
    mean = st.mean(dists) if dists else float("nan")
    print(f"  mean per-stop colour distance = {mean:.1f}  "
          f"(large => stitches land where the source has different/no thread)")
    return mean


def score(design, src) -> dict:
    theta, coh = orientation_field(src)
    sh, sw = src.shape[:2]
    to_px = _mapper(design, (sh, sw))
    per_type: dict[str, list[float]] = defaultdict(list)
    errs: list[float] = []
    weights: list[float] = []

    try:
        from measure_stitch_quality import _object_slices
        slices = list(_object_slices(design))
    except Exception:  # noqa: BLE001 - typing only affects the breakdown
        slices = [(None, list(design.stitches))]

    for obj, seg in slices:
        ty = str(getattr(getattr(obj, "stitch_type", None), "value", "ALL"))
        prev = None
        for s in seg:
            if _cmd(s) != "STITCH":
                prev = None
                continue
            if prev is not None:
                dx, dy = s.x - prev.x, s.y - prev.y
                length = math.hypot(dx, dy)
                if MIN_SEG_MM < length < MAX_SEG_MM:
                    px, py = to_px((prev.x + s.x) / 2, (prev.y + s.y) / 2)
                    if 0 <= px < sw and 0 <= py < sh and coh[py, px] > MIN_COHERENCE:
                        e = math.degrees(
                            abs((math.atan2(dy, dx) - float(theta[py, px]) + math.pi / 2)
                                % math.pi - math.pi / 2)
                        )
                        errs.append(e)
                        weights.append(length)
                        per_type[ty].append(e)
            prev = s

    if not errs:
        return {"n": 0}
    return {
        "n": len(errs),
        "mean_deg": sum(e * w for e, w in zip(errs, weights)) / sum(weights),
        "median_deg": st.median(errs),
        "within_15_pct": 100 * sum(1 for e in errs if e < 15) / len(errs),
        "within_30_pct": 100 * sum(1 for e in errs if e < 30) / len(errs),
        "by_type": {k: (len(v), st.mean(v)) for k, v in per_type.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", nargs="?", help="photograph of the real sew-out")
    ap.add_argument("--hoop", default="360x350")
    ap.add_argument("--colors", type=int, default=12)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--check-registration", action="store_true")
    args = ap.parse_args()

    if args.self_test or not args.photo:
        print("instrument self-test (stripes at known angles):")
        ok = self_test()
        print("  => instrument VALID" if ok else "  => instrument BROKEN — do not trust runs")
        if not args.photo:
            return

    print("\ninstrument self-test:")
    if not self_test():
        print("  => BROKEN; aborting")
        return

    from app.services.digitizer import digitize_image

    src = cv2.imread(args.photo)
    if src is None:
        raise SystemExit(f"could not read {args.photo}")
    design = digitize_image(Path(args.photo).read_bytes(), "cotton", args.hoop, args.colors)

    if args.check_registration:
        print("\nregistration check:")
        check_registration(design, src)

    r = score(design, src)
    if not r.get("n"):
        print("\nno comparable segments found")
        return
    print(f"\nstitch-direction fidelity  ({r['n']} segments; 0 = matches the "
          f"sew-out, 45 = coin flip)")
    print(f"  mean |error|   {r['mean_deg']:.1f} deg   (length-weighted)")
    print(f"  median         {r['median_deg']:.1f} deg")
    print(f"  within 15 deg  {r['within_15_pct']:.1f}%")
    print(f"  within 30 deg  {r['within_30_pct']:.1f}%")
    for ty, (n, m) in sorted(r["by_type"].items(), key=lambda kv: -kv[1][0]):
        print(f"    {ty:16s} n={n:6d} mean={m:5.1f}")


if __name__ == "__main__":
    main()
