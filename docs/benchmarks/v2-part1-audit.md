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
| 01 flat_2color_logo | 2 / 2 / **2** | 77→63 | 80→**0** | 8.72→8.73 | 1,699→1,648 |
| 02 logo_fine_text_3color | 3 / 2 / **3** ✅ | 140→167 | 236→**0** | 8.96→8.96 | 3,289→3,435 |
| 03 gradient_soft_subject | 4 / 3 / **4** ✅ | 278→513 | 321→**0** | 8.96→9.15 | 3,900→2,977 |
| 04 thin_line_outline | 2 / 1 / **1** | 187→286 | 309→**2** | 7.31→8.72 | 1,377→1,223 |
| 05 wordmark_caps | 2 / 1 / **2** ✅ | 173→186 | 292→**0** | 8.96→8.96 | 1,371→1,275 |
| 06 wordmark_script | 2 / 1 / **1** | 77→119 | 364→**0** | 8.59→8.96 | 1,094→799 |
| 07 circular_badge | 4 / 2 / **3** | 718→868 | 617→**0** | 8.96→9.32 | 4,083→5,275 |
| 08 mascot_detail | 5 / 3 / **5** ✅ | 303→385 | 288→**0** | 8.96→9.15 | 2,039→2,534 |
| 09 nonuniform_background | 4 / 4 / **2** | 78→41 | 677→**0** | 8.96→8.96 | 5,816→1,010 |
| 10 low_contrast_subject | 4 / 3 / **3** | 144→140 | 272→**0** | 8.96→8.97 | 2,612→2,342 |

| Metric | v1 | v2-part1 |
|---|---|---|
| Colour count matching the request | 2 / 10 | **5 / 10** |
| Sub-0.5 mm stitches (all fixtures) | 3,456 | **2** |
| Stitches over the 12.7 mm machine limit | 0 | **0** |
| Geometry-measured coverage ratio | — | **1.0 on all ten** |
| Jumps (all fixtures) | 2,175 | **2,768 — regression, see §6.2** |

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
## 5. Adversarial re-grade — and it is not flattering

Same method as Part 0: ten independent graders comparing v1 and v2 side by side, then ten
adversarial reviewers instructed to assume the improvement was overstated. Challenged scores stand.

> **Stamp:** these scores graded the build *before* the contour-smoothing correction in §6.1. The
> fixture-01 regression that drove its "regressed" verdict has since been measured back to parity;
> fixture 05's regression is real and stands. Re-running twenty agents to move one score would be
> disproportionate, so the numbers are reported as measured, with that caveat visible.

| Fixture | v1 bg / contour / colour | v2 bg / contour / colour | Verdict |
|---|:---:|:---:|---|
| 01 flat_2color_logo | 5 / 3 / 3 | 5 / 3 / 2 | regressed *(since fixed — §6.1)* |
| 02 logo_fine_text_3color | 3 / 2 / 2 | 3 / 3 / 3 | mixed |
| 03 gradient_soft_subject | 2 / 4 / 2 | 4 / 2 / 3 | mixed |
| 04 thin_line_outline | 4 / 2 / 5 | 4 / 3 / 4 | mixed |
| 05 wordmark_caps | 4 / 3 / 5 | 2 / 2 / 2 | **regressed** |
| 06 wordmark_script | 4 / 2 / 5 | 4 / 2 / 4 | mixed |
| 07 circular_badge | 4 / 3 / 2 | 3 / 2 / 3 | mixed |
| 08 mascot_detail | 3 / 2 / 2 | 3 / 2 / 3 | mixed |
| 09 nonuniform_background | 1 / 2 / 3 | **5** / 2 / 4 | **improved** |
| 10 low_contrast_subject | 3 / 2 / 3 | 3 / 3 / 3 | mixed |
| **Mean** | **3.3 / 2.5 / 3.2** | **3.6 / 2.4 / 3.1** | 1 improved · 7 mixed · 2 regressed |

**The honest reading: subjective quality is essentially flat.** Background/edge gains +0.3, contour
and colour each lose 0.1. That sits uncomfortably beside objective metrics that improved a lot
(colours matching request 2→5, sub-0.5 mm stitches 3,456→2, fixture 09 down 82% in stitch count).

Both are true, and the tension is the finding: **Part 1 fixed the specific named defects without
lifting overall perceived quality**, because what dominates a grader's eye — blocky tatami where
satin belongs, text that is present but not legible — is untouched by Part 1 and is exactly what
Parts 2–3 address. Fixture 02 is the clearest illustration: its white type genuinely stitches now
(verified below), yet it still reads "EORTEFIELD" rather than "NORTHFIELD" because a 6mm cap-height
word rendered as tatami cannot resolve. The layer was the Part-1 bug; the legibility is a Part-2 bug.

### Two reviewer findings that were wrong, and why

**"Fixture 02's white text is not actually stitched."** Wrong, but for an instructive reason.
`render_preview` draws on a near-white background, so white thread is invisible — the reviewer
could see a white band and reasonably concluded nothing was there. Re-plotting **stop 3 alone on a
mid-grey ground** shows 398 white stitches forming the wordmark in the correct position. The
reviewer's *observation* was accurate; the inference was not.

This exposes a third rendering defect in the same family as the v1 stroke-width bug: **the
customer-facing preview cannot depict white or light thread at all.** Logged for a later part.

**"Coverage claims 1.0 while the render shows unfilled wedges."** The reviewer is **right**, and
this is a genuine flaw in the metric I added. `coverage_ratio` compares fill-row pitch to thread
width — it detects *rows too far apart*, not *regions never filled*. It cannot see a bare wedge
between two layers. It should not be used as a pass/fail gate, and §6.1 exists only because a human
looked at the picture. A void-detecting metric (rasterise contours, compare to stitched area) is
needed before coverage can gate anything.

## 6. Regressions and honest limitations

### 6.1 A regression this audit caught, and I fixed
Adversarial review found that fixture 01's gold triangle had eroded away from the blue disc,
opening a bare-fabric wedge. Verified and traced: **Chaikin corner-cutting shrinks a polygon**, and
adjacent colour layers are smoothed independently, so they pull apart. Measured white area in the
gold/blue join region: **v1 27.5% · v2 at 2 iterations/0.18mm 41.1% · v2 at 1 iteration/0.10mm
27.8%.** Settings reduced to 1 iteration at 0.10 mm — parity with v1, staircase still removed.
Fixture 01's jumps also improved as a side effect (77 → 63).

### 6.2 Jump count regressed on 7 of 10 — not fixed
Totals 2,175 → 2,768. This violates the brief's "no regression" line and I am not going to explain
it away. Evidenced cause: v2 stitches content v1 deleted (objects 76 → 97; fixture 07 gained a
1,904-stitch cream disc that v1 dropped entirely), and the only fixture where v2 *removes* content
improved (09: 78 → 41). Normalised per 1,000 stitches, 07 and 08 improve while 03, 04 and 06 still
regress. The real fix is decomposing annular regions into monotone chunks before scanline filling,
so a row does not repeatedly cross a hole — that is a fill-pattern change, which the brief reserves
for Parts 2–4. `POST /api/optimize/path` already reduces travel on demand.

### 6.3 Fixture 05 gained a spurious colour — not fixed
"SUMMIT" is one ink colour; v2 returns two, the second a light halo at Δ21.4 from white — too far
from the page to trip the substrate rule, too close to be a real layer. I attempted an
"anti-aliasing halo has no interior" suppressor; it broke three tests without fixing this case, and
I **reverted it rather than tune thresholds until the fixtures looked right**. Recorded as open.

### 6.4 Other honest notes
- **Fixture 10 is not fixed** (see §4, question 5). Low-contrast input needs contrast-aware palette
  selection.
- **Fixture 02's small second line** ("EST. 1974 · SUPPLY CO.") still produces no stitches at all.
- **rembg costs runtime**: fixture 01 went 0.10 s → 2.58 s. Total bench 2.2 s → ~7 s. It also
  bought nothing measurable on clean white-background fixtures, where flood-fill agreed with it.
  A cheap "is the background already uniform?" pre-check would skip the model in those cases.
- **The corpus is ten synthetic fixtures.** Thresholds tuned against them risk overfitting; the
  substrate rule in particular is a heuristic over a genuine ambiguity (a glyph counter and
  knocked-out type are the same shape, separable only by scale and enclosure).
- **Nothing has been stitched on a real machine.** All claims are geometry and renders.

## 7. Reproducing

```bash
cd apps/backend && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -r requirements-features.txt     # optional: enables the rembg tier
python -m pytest tests -q                    # 88 passed
python scripts/run_quality_bench.py --tag v2-part1
```
Without rembg installed the pipeline still runs, falling back to border flood-fill; fixtures 03 and
09 will be materially worse, which is itself worth measuring.
