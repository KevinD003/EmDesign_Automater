# v2 Part 16 Audit — the fidelity loop, round three: text, sequencing, colour

**Date:** 2026-07-29 · **Tag:** `v2-part16` · graded against [`v2-part15`](./v2-part15-summary.json)
**Strips:** [`02`](./v2-part16-fidelity-02.png) · [`07`](./v2-part16-fidelity-07.png) · [`08`](./v2-part16-fidelity-08.png)

The user's three named problems — text not visible, shapes imperfect, colours off, white gaps —
each got a mechanism found and fixed. **07's HARBOR CLUB went from invisible (Part 14) to outlined
(Part 15) to fully legible navy satin (this part).** Fixture 08's face now carries its nose, smile,
whiskers, dots and pupils on a solid head.

LINT-VERIFY: findings=14 files=apps/backend/app/services/digitizer.py apps/backend/scripts/measure_stitch_quality.py apps/backend/tests/test_fidelity.py apps/backend/tests/test_stitch_quality_metrics.py apps/backend/tests/test_lettering.py

## 1. Small text — resolution, and a latent thinning bug the fix exposed

A 640px source in a 130mm hoop puts a 4mm letter at ~20px with 2-4px strokes; no medial-axis
machinery can column that. A GLOBAL work-resolution raise was tried first and **rejected on
measurement: 43.8s per fixture** for gains only small strokes need. Shipped instead:
`_skeleton_satin_hires` — regions whose typical stroke is under `SMALL_STROKE_PX = 8` are thinned
and columned at up to 3x resolution, points scaled back. Only small objects pay (corpus total 47s,
worst fixture 13s).

The upscale exposed a **latent bug present since Part 2**: the vectorised Zhang-Suen thinner
deletes BOTH sides of an even-width ridge in one simultaneous sub-iteration — a 2x-upscaled bar
collapsed to a **single skeleton pixel** (measured: f=1 → 139px, f=2 → 1px, f=3 → 447px, all
interpolations). Fixed with the standard checkerboard split: one pixel parity removed at a time, so
a ridge always keeps its centre. This changed skeletons corpus-wide by design (fixture 04 gained a
previously-empty object into the zigzag count; two pinned tests updated with provenance).

## 2. White gaps — professional sequencing (detail-on-top), not more repair

The painted miss-map of fixture 08 showed red wedges around every small dark detail: darkest-first
order stitches the dots/pupils/whiskers FIRST, so the head fill must keep uncrossable knockouts
around all of them. Part 14's burial guard was right to refuse absorption — the SEQUENCE was wrong.
Now a component under `DETAIL_DEFER_MAX_MM2 = 60` whose surrounding ring is ≥60% later-stitched
cluster is **deferred to a detail pass after the main clusters**: the fill sews solid beneath
(absorption guard extended to trust deferral), the detail lands on top. One detail pass per cluster
— a first version opened a colour stop per component (19 stops on fixture 08, caught on render) and
was grouped before commit; 08 ships at 5 stops, 07 at 4. The burial guard still protects
non-deferrable (large) earlier details, and both directions are pinned as tests.

## 3. Colour — median, not mean

The k-means centroid averages every member pixel including anti-aliased blends, muddying flat-art
colours. Cluster representatives are now the per-channel **median** of members — robust to the
blend tail, landing on the ink the artwork used.

## 4. Corpus — held where it must, moved where intended

```
floor violations 0 · over-limit 0 · density flagged 0 · all Part 15 100/100 scores intact
02: letters re-classified under hires (stitch stream changed, coverage identical)
07: 13,036 → 12,174 st, spill 6.2 → 5.4, HARBOR CLUB legible — classification changed BY DESIGN
08: 6,470 → 5,555 st, spill 4.0 → 3.2, face details on top
05 gives back 2.0 interior / 1.7 band (hires satin re-columned the wordmark) — reported, next loop's target
06 spill 20.9 → 25.0 (hires satin on script strokes reaches further) — reported
colour changes +1 on 02/07/10 (the detail pass) · runtimes up: worst fixture 13.3s, corpus 47.2s
pytest 171 WITH and 171 WITHOUT rembg · vitest untouched · ruff 14 all pre-existing · secrets clean
```

## 5. What to attack

1. 05/06's give-back: the hires path re-columns strokes that were already healthy at 1x. Gate it
   harder (only when 1x produced a degenerate skeleton)?
2. 07's top ring text (white-on-navy, ~2.5mm, curved) is the last illegible text — it is at the
   physical limit; a lettering engine with per-glyph columns is the real answer (competitor gap #1).
3. Runtime: 13s worst-case is tolerable, not good. The hires thinning is the hot spot.
4. The deferral threshold (60mm²) and embed share (0.6) are geometry-grounded guesses; adversarial
   shapes (a detail ON a boundary) should probe them.
