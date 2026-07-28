# v2 Part 1 Audit — layer preservation · background separation · contour smoothing

**Date:** 2026-07-28 · **Tag:** `v2-part1` · graded against [`v1-baseline`](./v1-baseline-audit.md)
**Artifacts:** [`v2-part1-grid.png`](./v2-part1-grid.png) · [`v2-part1-summary.json`](./v2-part1-summary.json) · per-fixture PNG+JSON in [`v2-part1/`](./v2-part1/)

Scope of this re-grade: **background/edge, contour smoothness, and colour-layer fidelity only.**
Stitch-type appropriateness (satin vs tatami) is untouched here and remains at its v1 score of
1/5 across the board — that is Parts 2–3.

---

## 1. The headline: two "separate" root causes were one bug

The v1 audit listed background separation (#1) and colour-layer loss (#2) as distinct problems.
Diagnosing them showed they are the same rule failing in opposite directions. v1 decided
background by **colour identity** — any k-means cluster within ΔBGR < 40 of the average of the
four corner pixels was deleted *everywhere in the frame*:

| Fixture | Layer | Δ from corner average | v1 outcome |
|---|---|---|---|
| 02 | white lettering | **0.0** (identical to the page) | deleted → type survived only as unstitched holes |
| 08 | cream muzzle | **34.8** (just inside the cutoff) | deleted → muzzle and both eye-whites vanished |
| 07 | cream inner disc | **28.0** | deleted → 4 colours collapsed to 2 |
| 09 | tan / teal gradient | **53.0 / 50.8** (just outside) | **kept** → the backdrop was embroidered |

A threshold tweak cannot fix this: 02's white type is *exactly* the background colour, so no
colour-space rule can separate them. Background had to become a question of **where a pixel is**,
not **what colour it is**.

## 2. What changed

1. **`services/segmentation.py` (new).** Returns a foreground *mask*. Three tiers, each falling
   back cleanly: **rembg / U2-Net** (MIT, optional, lazily imported, result sanity-checked) →
   **border flood-fill** (region-grows inward with a local tolerance, so a smooth gradient backdrop
   is absorbed while an enclosed shape is not) → the **v1 corner heuristic** as a last resort.
   Measured on the corpus, rembg handled all ten; flood-fill alone would have failed 03 (0.6%
   foreground) and 09 (47.9%), which is why the learned tier leads.
2. **k-means now clusters foreground pixels only.** The background no longer consumes a cluster
   slot (v1's "+1 for background" fudge is gone) or drags the centroids, so the requested colour
   budget is spent on real design layers.
3. **Substrate rule.** A garment-coloured region is ink only if it passes **enclosure** (fully
   surrounded by ink — a catchlight inside a pupil passes, the aperture of a "G" opens onto the
   background and fails) **and** size caps (a ring's interior is enclosed but is the garment
   showing through). Enclosure is topological and carries the decision; the size caps are a guard.
4. **Contour smoothing.** Douglas-Peucker (`approxPolyDP`) then Chaikin corner-cutting, both
   skipped below 10 points and capped at 1% of perimeter, biased toward preservation per the brief.
5. **Conditional morphological opening.** v1 opened every mask with a 3×3 kernel, which erases
   ~2px strokes — this is what removed the "L" from HARBOR CLUB. Opening now runs only when the
   mask survives erosion.
6. **Speck threshold 4.0 → 2.0 mm²**, so the mascot's 2.6 mm² freckles survive.
7. **Sub-0.5 mm coalescing.** Needle penetrations closer than 0.5 mm are merged; they break thread
   and strike needles, and drop nothing (the following point is still stitched).
8. **`render_preview` stroke width** now scales with `px_per_mm × 0.4` instead of a hard-coded 2px
   (v1 audit §3).
9. **Harness metrics.** Density is now over **filled** area (v1's bounding-box version is kept
   alongside as `stitch_density_per_bbox_mm2` for comparability), plus `fill_row_pitch_mm`,
   `coverage_ratio` and `fill_rows_over_thread_width` measured **from stitch geometry, never from
   the rendered bitmap** — the v1 audit proved bitmap coverage grading unreliable.

## 3. Objective comparison — v1 vs v2-part1

Same fixtures, same digitize parameters, same pinned RNG. Nothing in `FIXTURE_PARAMS` changed, so
this is like-for-like.

| Fixture | colours ask / v1 / **v2** | jumps v1→v2 | <0.5 mm v1→**v2** | max stitch v1→v2 | stitches v1→v2 |
|---|---|---|---|---|---|
| 01 flat_2color_logo | 2 / 2 / **2** | 77→78 | 80→**0** | 8.72→9.15 | 1,699→1,579 |
| 02 logo_fine_text_3color | 3 / 2 / **3** ✅ | 140→164 | 236→**0** | 8.96→8.77 | 3,289→3,415 |
| 03 gradient_soft_subject | 4 / 3 / **4** ✅ | 278→514 | 321→**0** | 8.96→9.15 | 3,900→2,966 |
| 04 thin_line_outline | 2 / 1 / **1** | 187→287 | 309→**2** | 7.31→7.45 | 1,377→1,219 |
| 05 wordmark_caps | 2 / 1 / **2** | 173→186 | 292→**0** | 8.96→8.97 | 1,371→1,268 |
| 06 wordmark_script | 2 / 1 / **1** | 77→122 | 364→**0** | 8.59→8.78 | 1,094→794 |
| 07 circular_badge | 4 / 2 / **3** | 718→858 | 617→**0** | 8.96→9.15 | 4,083→5,234 |
| 08 mascot_detail | 5 / 3 / **5** ✅ | 303→374 | 288→**0** | 8.96→8.97 | 2,039→2,471 |
| 09 nonuniform_background | 4 / 4 / **2** | 78→**41** | 677→**0** | 8.96→8.77 | 5,816→**1,032** |
| 10 low_contrast_subject | 4 / 3 / **3** | 144→143 | 272→**0** | 8.96→8.97 | 2,612→2,345 |

| Metric | v1 | v2-part1 |
|---|---|---|
| Colour count matching the request | 2 / 10 | **5 / 10** |
| Sub-0.5 mm stitches (all fixtures) | 3,456 | **2** |
| Stitches over the 12.7 mm machine limit | 0 | **0** |
| Geometry-measured coverage ratio | — | **1.0 on all ten** |
| Jumps (all fixtures) | 2,175 | **2,767 — regression, see §5** |

## 4. The five acceptance questions, answered with evidence

**1. Does fixture 02's white text now stitch? — YES.**
Colour count 2 → 3; the new stop is `#f2f5f4` carrying **398 stitches**. In v1 the white layer had
Δ 0.0 from the page and was deleted entirely, leaving the type as unstitched negative space (so on
any non-white garment there was no type at all). It is now a real thread layer.

**2. Does fixture 08's cream muzzle now stitch? — YES.**
Colour count 3 → 5. New stops `#faf0e0` (**797 stitches**, the muzzle and eye-whites) and `#fefefe`
(**20 stitches**, the two catchlights). Visible in the output: the muzzle is filled, the eyes are
round with dark pupils rather than v1's flat rectangular bars, the five brow freckles are present,
and the whiskers are attached.

**3. Does fixture 07's "L" reappear? — YES.**
Side-by-side crop of the text band: v1 reads **"HARBOR C UB"**, v2 reads **"HARBOR CLUB"**. Cause
was the unconditional 3×3 morphological opening erasing the ~2px stem, now conditional. The cream
inner disc is also stitched behind the text (`#f7f4e8`, 1,904 stitches), where v1 left bare fabric.

**4. Does fixture 09 stop stitching its background? — YES, decisively.**
Stitch count **5,816 → 1,032**; colours 4 → 2; jumps 78 → 41; sub-0.5 mm stitches 677 → 0. The
output is now only the red diamond and its cream centre dot. This is the clearest single win in
Part 1.

**5. Does fixture 10's "LC" become legible? — NO, only marginally.**
This one is **not fixed**. Colour count is unchanged at 3, stitch count 2,612 → 2,345, and the
before/after crops show "LC" only slightly better defined. The subject is separated from the
backdrop correctly, but a subject 30 RGB units from its background still produces
near-indistinguishable thread colours, so the letters do not read at stitch-out. Reporting this as
a failure rather than dressing it up: low-contrast input needs contrast-aware palette selection,
which is not in Part 1's scope.

---
