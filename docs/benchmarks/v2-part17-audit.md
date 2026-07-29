# v2 Part 17 Audit — granularity: fine geometry everywhere, made affordable

**Date:** 2026-07-29 · **Tag:** `v2-part17` · graded against [`v2-part16`](./v2-part16-summary.json)
**Strips:** [`07`](./v2-part17-fidelity-07.png) · [`08`](./v2-part17-fidelity-08.png)

The user's verdict on round three was "still not granular" — correct: contours, borders and fills
were traced on a 0.18mm/px staircase (640px source), and every stage inherited the chunk. The fix
is global fine-resolution processing, which Part 16 had REJECTED at 43.8s/fixture — so this round
is equal parts performance engineering and fidelity.

LINT-VERIFY: findings=14 files=apps/backend/app/services/digitizer.py apps/backend/tests/test_stitch_quality_metrics.py

## 1. Profile first: 44 of 62 seconds was the thinner running full-canvas

`_zhang_suen_thin` iterated whole-canvas array passes although a region occupies a fraction of it.
Cropping to the active bounding box (pasted back after) took the heaviest fixture at 2x from
**61.9s → 18.4s**; windowing the detail-deferral ring scan (the next profiler entry, 4.7s of
full-canvas dilates) and the rest landed the corpus at **39.5s total, worst fixture 13.4s** —
inside what competitor auto-digitizers take behind their spinners.

## 2. Then turn granularity on — and handle what it exposed

`_MIN_WORK_PX = 1200`: sources under it are cubic-upscaled (capped 2x) before segmentation, so all
geometry is traced fine. Three consequences found by the tests and fixed with measured values:

- **Phantom blend clusters**: cubic AA bands survived the 1px palette erosion and seeded 0.15mm
  "satin" slivers no needle could sew. The palette erosion now scales with the upscale factor, and
  a **sub-thread feature gate** (`MIN_FEATURE_W_MM = 0.25`) skips what remains. The first gate
  value (0.35) silently deleted ALL of fixture 04 — its real hairlines measure 0.30–0.33mm at fine
  resolution, not the 0.5mm the coarse grid had inflated them to; the constant carries both
  measured populations (phantoms 0.15 / real 0.30) so nobody re-tunes it blind.
- **Unbounded upscaling breaks tiny sources**: a 160px lettering render at 7.5x produced no
  stitchable shapes at all — capped at 2x and gated to sources ≥400px, below which the AA band is
  as large in mm as the smallest real features.
- **Resolution-dependent pins moved** (fixture 04's zigzag-object count 11→10, fixture 08's max
  penetrations/cell 7→9-10) — updated with provenance; every SAFETY number held.

## 3. Result

```
floor 0 · over-limit 0 · density flagged 0 · every 100/100 intact
stitch counts DOWN 5-15% on most fixtures (finer geometry overshoots less)
band: 03 +1.3, 05 +1.1, 08 +2.1 · spill: 04 −4.4, 06 −1.1, 10 −0.6
07's ring text "ESTABLISHED 1908" now partially legible; HARBOR CLUB crisper; rings tighter
pytest 171 WITH and 171 WITHOUT rembg · ruff 14 all pre-existing · secrets clean
```

## 4. What to attack

1. 07's 13.4s runtime is the ceiling now — the remaining hot spots are the disc-kernel dilates in
   `_uncovered_mask` and the boundary distance matrices.
2. The 2.5mm curved ring text is partially legible; full legibility needs the lettering engine.
3. `MIN_FEATURE_W_MM = 0.25` separates two measured populations 0.15/0.30 — thin margin; an
   adversarial probe with strokes at 0.2/0.25/0.3mm would pin the boundary properly.
