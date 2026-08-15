"""THE floor() TEST, run rather than named (CTO ruling 2026-08-24).

A01's rebuild loses exactly one penetration on 20 of its 36 RUNNING_SINGLE
objects and none on 15. The hypothesis was a resampling floor() flip. This tests
it against the two candidate mechanisms visible in the code, and reports which
one the data supports:

  H1  STEP MISMATCH. digitize resamples at a FLOAT pixel step
      (`run_px = OUTLINE_RUN_MM / mm_per_px`); rebuild rounds it to an INTEGER
      (`max(1, round(pitch_mm / mm_per_px))`). Different step -> different
      floor(L/step).

  H2  PATH QUANTISATION. rebuild rebuilds the polyline through
      `to_px` = `int((p.x - minx) * px_per_mm) + pad`, i.e. TRUNCATION to whole
      pixels, so the stored mm path is shortened before it is resampled at all.

Discriminator: for each object compute the stored path length and the fractional
part of length/step. Under a pure floor() flip, objects that keep their count
should have a fractional part near 0 or near 1 and those that lose one should
sit in between — and if the two groups do NOT separate on that statistic, the
flip is not the whole story.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for _p in (BACKEND, BACKEND / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

CORPUS = BACKEND / "tests" / "fixtures" / "corpus100"


def main() -> None:
    import cv2
    from coverage_audit import A_TIER_PARAMS
    from run_quality_bench import RNG_SEED

    from app.services.digitizer import digitize_image
    from app.services.digitizer.constants import MAX_STITCH_MM, MIN_STITCH_MM, RUN_PITCH_MM
    from app.services.digitizer.rebuild import rebuild_design

    params = A_TIER_PARAMS["A01_real_peacock_patch_photo"]
    cv2.setRNGSeed(RNG_SEED)
    dig = digitize_image((CORPUS / "A01_real_peacock_patch_photo.png").read_bytes(),
                         fabric_type=params["fabric"], hoop_size=params["hoop"],
                         max_colors=params["colors"])
    reb = rebuild_design(dig.model_copy(deep=True), force=True)

    # Reproduce rebuild's own scale exactly as rebuild derives it.
    xs = [p.x for o in dig.objects for p in (o.contour or [])]
    ys = [p.y for o in dig.objects for p in (o.contour or [])]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    w_mm, h_mm = maxx - minx, maxy - miny
    stored = dig.source_mm_per_px
    px_per_mm = (min(1.0 / float(stored), 2000.0 / max(w_mm, h_mm)) if stored and stored > 0
                 else min(10.0, 2000.0 / max(w_mm, h_mm)))
    mm_per_px = 1.0 / px_per_mm
    pad = 2

    rb = {o.sequence_order: o for o in reb.objects}
    rows = []
    for o in dig.objects:
        if str(getattr(o.stitch_type, "value", o.stitch_type)) != "RUNNING_SINGLE":
            continue
        r = rb.get(o.sequence_order)
        if r is None:
            continue
        run_d = float(o.density or 0.0)
        pitch_mm = (min(max(1.0 / run_d, MIN_STITCH_MM), MAX_STITCH_MM)
                    if run_d > 0 else RUN_PITCH_MM)
        step_px_int = max(1, round(pitch_mm / mm_per_px))

        mm_pts = [(p.x, p.y) for p in (o.contour or [])]
        len_mm = sum(math.dist(mm_pts[i - 1], mm_pts[i]) for i in range(1, len(mm_pts)))
        # The exact polyline rebuild resamples: TRUNCATED to whole pixels.
        px_pts = [(int((x - minx) * px_per_mm) + pad, int((y - miny) * px_per_mm) + pad)
                  for x, y in mm_pts]
        dedup = [px_pts[0]]
        for p in px_pts[1:]:
            if p != dedup[-1]:
                dedup.append(p)
        len_px_quant = sum(math.dist(dedup[i - 1], dedup[i]) for i in range(1, len(dedup)))
        len_px_exact = len_mm / mm_per_px

        frac_exact = (len_px_exact / step_px_int) % 1.0
        frac_quant = (len_px_quant / step_px_int) % 1.0
        rows.append({
            "seq": o.sequence_order,
            "pen_digitize": int(o.penetration_count or 0),
            "pen_rebuild": int(r.penetration_count or 0),
            "delta": int(r.penetration_count or 0) - int(o.penetration_count or 0),
            "contour_points": len(mm_pts),
            "len_mm": round(len_mm, 4),
            "pitch_mm": round(pitch_mm, 4),
            "step_px_int": step_px_int,
            "step_px_float": round(pitch_mm / mm_per_px, 4),
            "len_px_exact": round(len_px_exact, 3),
            "len_px_quantised": round(len_px_quant, 3),
            "px_lost_to_truncation": round(len_px_exact - len_px_quant, 3),
            "frac_exact": round(frac_exact, 4),
            "frac_quantised": round(frac_quant, 4),
            "predicted_pts_exact": int(len_px_exact // step_px_int) + 2,
            "predicted_pts_quantised": int(len_px_quant // step_px_int) + 2,
        })

    lost = [r for r in rows if r["delta"] == -1]
    kept = [r for r in rows if r["delta"] == 0]
    other = [r for r in rows if r["delta"] not in (0, -1)]
    print(f"mm_per_px(rebuild) = {mm_per_px:.6f}   source_mm_per_px = {stored}")
    print(f"{len(rows)} run objects: {len(kept)} kept, {len(lost)} lost 1, {len(other)} other\n")
    print(f"{'seq':>5s} {'d':>3s} {'pen':>7s} {'len_mm':>9s} {'stepf':>7s} {'stepi':>5s} "
          f"{'lenpx':>9s} {'quant':>9s} {'trunc':>7s} {'fracE':>7s} {'fracQ':>7s} "
          f"{'predE':>5s} {'predQ':>5s}")
    for r in sorted(rows, key=lambda r: (r["delta"], r["seq"])):
        print(f"{r['seq']:5d} {r['delta']:3d} {r['pen_digitize']:3d}->{r['pen_rebuild']:<3d} "
              f"{r['len_mm']:9.3f} {r['step_px_float']:7.3f} {r['step_px_int']:5d} "
              f"{r['len_px_exact']:9.2f} {r['len_px_quantised']:9.2f} "
              f"{r['px_lost_to_truncation']:7.2f} {r['frac_exact']:7.3f} "
              f"{r['frac_quantised']:7.3f} {r['predicted_pts_exact']:5d} "
              f"{r['predicted_pts_quantised']:5d}")

    def _sep(key: str) -> str:
        a = sorted(r[key] for r in kept)
        b = sorted(r[key] for r in lost)
        if not a or not b:
            return "n/a"
        return (f"kept [{a[0]:.3f}, {a[-1]:.3f}]  lost [{b[0]:.3f}, {b[-1]:.3f}]  "
                f"{'SEPARATES' if a[-1] < b[0] or b[-1] < a[0] else 'OVERLAPS'}")

    print(f"\nfrac_exact      {_sep('frac_exact')}")
    print(f"frac_quantised  {_sep('frac_quantised')}")
    print(f"truncation px   {_sep('px_lost_to_truncation')}")
    ok_e = sum(1 for r in rows if r["predicted_pts_exact"] == r["pen_rebuild"])
    ok_q = sum(1 for r in rows if r["predicted_pts_quantised"] == r["pen_rebuild"])
    print("\nprediction accuracy vs actual rebuild count:")
    print(f"  H1 (exact length, integer step)     {ok_e}/{len(rows)}")
    print(f"  H2 (truncated length, integer step) {ok_q}/{len(rows)}")
    Path(sys.argv[1] if len(sys.argv) > 1 else "run_roundtrip.json").write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    main()
