# v2 Part 3 Audit — measured-width satin/tatami classification for every shape

**Date:** 2026-07-28 · **Tag:** `v2-part3` · graded against [`v2-part2-5`](./v2-part2-5-summary.json)
**Grid:** [`v2-part3-grid.png`](./v2-part3-grid.png) · **Per-fixture:** [`v2-part3/`](./v2-part3/)

The skeleton + local-half-width machinery Parts 2/2.5 built for `text_mode` is now **the** classifier,
for lettering and artwork alike. The global aspect-ratio/bounding-rect threshold is gone.

---

## 1. Why the old rule could not work

```python
rect  = cv2.minAreaRect(contour)
w_mm  = min(rect[1]) * mm_per_px
l_mm  = max(rect[1]) * mm_per_px
is_satin = SATIN_MIN_W_MM <= w_mm <= SATIN_MAX_W_MM and l_mm / w_mm >= SATIN_ASPECT
```

Every term is a property of the **bounding box**, not of the shape. A ring, an arc, a horseshoe or an
L-bend is uniformly thin and obviously satin work, but its bounding box is square, so `l_mm / w_mm`
is ~1 and `min(rect[1])` is the box's short side rather than the stroke's width. Fixture 04 —
artwork consisting of *nothing but* thin lines — scored **0 of 11 objects** as satin.

## 2. The replacement

Per object, in order:

| Step | What it does | Constant |
|---|---|---|
| **Pre-gate** | Median distance-transform width over the whole region far above the cap → broad fill, skip thinning entirely (speed only; never flips a decision) | `SATIN_PREGATE_SLACK = 1.5` |
| **Medial axis** | Zhang-Suen thinning → pruned branches → satin columns across the stroke, stepping along it | — |
| **Width test** | Median local width must fit under the satin cap. Median, not p90: the distance transform spikes at junctions where the axis is genuinely far from every edge although the stroke is no wider | `SATIN_MAX_W_MM = 4.5` |
| **Reducibility test** | Columns swept along the axis must actually *account for* the shape. A disc has a medial axis, but capped-width columns cannot cover it, so its uncovered share stays high and it stays tatami | `SATIN_MAX_UNCOVERED = 0.35` |
| **Partial fallback** | Where a mostly-stroke shape has a wide patch, satin the stroke and tatami only that patch | — |

The reducibility test is what stops the obvious failure mode — "measured width is a stroke test, so
force everything through it and broad fills become satin." It is checked in §5.

Every decision is now logged per object (`last_classification_log()`), surfaced in the harness JSON as
`classification`, and every TATAMI verdict in this audit is quoted from it rather than asserted.

## 3. Stitch types — all 10 fixtures, before and after

| # | Fixture | v2-part2-5 | **v2-part3** | Change | Why |
|---|---|---|---|---|---|
| 01 | flat_2color_logo | TATAMI×2 | **TATAMI×2** | none | Both objects are broad fills (region width **8.43 / 6.97mm**) → `broad_fill_pregate`. **Correct: a disc and a triangle are not strokes.** |
| 02 | logo_fine_text_3color | TATAMI×15 SATIN×1 | **SATIN×12 TATAMI×4** | +11 satin | Twelve glyph strokes measure 1.02–2.19mm. The 4 remaining: two panels at 8.25/7.59mm (`broad_fill_pregate`) and two sub-pixel specks at 0.73/1.10mm (`no_medial_axis`). |
| 03 | gradient_soft_subject | TATAMI×4 | **SATIN×2 TATAMI×2** | +2 satin | Two quantisation annuli at 2.56/3.80mm are geometrically strokes. The other two: 5.74mm skeleton width (`wider_than_satin_cap`) and an 11.47mm core (`broad_fill_pregate`). |
| 04 | thin_line_outline | TATAMI×11 | **SATIN×11** | **+11 satin** | Widths **0.28–0.62mm**, uncovered share **0.00** on every object. This is the fixture the part was written for. |
| 05 | wordmark_caps | SATIN×6 | **SATIN×6** | none | Already satin via `text_mode`; now reaches the same verdict from geometry alone (2.92–3.66mm). |
| 06 | wordmark_script | SATIN×12 | **SATIN×12** | none | Same — 0.80–1.90mm. |
| 07 | circular_badge | TATAMI×18 | **SATIN×14 TATAMI×4** | +14 satin | Rings, arc type and star limbs at 0.51–3.80mm. The 4 remaining are genuinely wide: skeleton widths **8.04 / 5.56 / 8.04mm**, plus one 0.80mm speck with no axis. |
| 08 | mascot_detail | TATAMI×21 | **SATIN×12 TATAMI×9** | +12 satin | Ears, whiskers and outline at 0.73–4.09mm. The 9 remaining: **7 specks at 0.73mm** (`no_medial_axis` — see §7) and two blobs at 4.75/8.33mm. |
| 09 | nonuniform_background | TATAMI×2 | **TATAMI×2** | none | A diamond (7.17mm, `broad_fill_pregate`) and a dot (`no_medial_axis`). **Correct.** |
| 10 | low_contrast_subject | TATAMI×4 | **SATIN×2 TATAMI×2** | +2 satin | Two 2.12/2.56mm bands; the other two at 9.51mm and 7.16mm stay fills. |

**Totals: 19/96 → 71/96 objects satin.** The three brief-mandated outcomes all hold: 04 flips
entirely (0→11), 07 and 08 get partial satin measured under the cap, and neither broad-fill control
(01, 09) moves by a single object.

## 4. Machine limits, travel and colour — the things that must not regress

| Fixture | max stitch (b→a) | over 12.7mm | jumps (b→a) | colours (b→a) |
|---|---|---|---|---|
| 01 | 8.86 → 8.86 | 0 → **0** | 63 → 63 | 2 → 2 |
| 02 | 8.96 → 8.96 | 0 → **0** | 171 → 188 | 3 → 3 |
| 03 | 9.15 → 9.15 | 0 → **0** | 452 → **121** | 4 → 4 |
| 04 | 8.58 → **2.59** | 0 → **0** | 285 → **29** | 1 → 1 |
| 05 | 4.32 → 4.80 | 0 → **0** | 93 → **44** | 1 → 1 |
| 06 | 4.39 → 4.73 | 0 → **0** | 107 → **52** | 1 → 1 |
| 07 | 9.15 → 8.96 | 0 → **0** | 866 → 981 | 3 → 3 |
| 08 | 8.97 → 8.78 | 0 → **0** | 385 → 386 | 5 → 5 |
| 09 | 8.97 → 8.97 | 0 → **0** | 41 → 41 | 2 → 2 |
| 10 | 8.97 → 8.78 | 0 → **0** | 150 → **141** | 3 → 3 |

**Zero stitches over the 12.7mm machine limit on all ten.** Corpus jumps **2,613 → 2,046** — below
even the v1 baseline's 2,175, and the first time in this v2 sequence that has been true.

**Colour and background, checked directly rather than assumed.** For 02/07/08/09, comparing the two
builds' outputs field by field:

```
                          color_count  segmentation  objects_with_holes  filled_area_mm2
02_logo_fine_text_3color     3 -> 3      rembg->rembg      4 -> 4           5234.2 -> 5234.2
07_circular_badge            3 -> 3      rembg->rembg     10 -> 10          6772.3 -> 6772.3
08_mascot_detail             5 -> 5      rembg->rembg      5 -> 5           3020.6 -> 3020.6
09_nonuniform_background     2 -> 2      rembg->rembg      1 -> 1           1664.6 -> 1664.6

colour stops + per-object colour assignment, dumped from both builds and diffed:  IDENTICAL
  02  #0f5a4b #eec23d #eff2f2      07  #122854 #d6a42d #f7f3e7
  08  #30221e #de6c26 #d68084 #faf0e0 #ffffff        09  #eb3c46 #fcf6e6
```

`filled_area_mm2` identical to the decimal is the strongest available statement that segmentation and
layer assignment are untouched: the same pixels are in the same layers; only how they are stitched
changed.

**One field does move, and it is not a colour field.** `coverage_ratio` goes 1.0 → 0.0 on 02/07/08.
It is derived from `fill_row_geometry`, which by design returns 0.0 for majority-satin designs (added
in Part 1 because a satin run's consecutive points are *across* the column, giving a physically
impossible 0.018mm "row pitch"). Those three fixtures became majority-satin, so the fill-row metric
correctly declines to report. 09 stays 1.0 because it stays all-tatami.

## 5. Re-grading stitch-type appropriateness from stitch geometry

Same methodology as Part 2.5, applied to all ten: rasterise the actual stitch path at 0.4mm thread,
rasterise the object outlines, then measure **interior** (outline eroded 0.6mm), **edge band**
(outline minus interior) and **spill** (thread area falling outside the outline).

| # | Fixture | interior b→a | edge band b→a | spill b→a |
|---|---|---|---|---|
| 01 | flat_2color_logo | 98.7 → 98.7 | 94.6 → 94.6 | 2.1 → 2.1 |
| 02 | logo_fine_text | 99.0 → 99.0 | 96.8 → **96.9** | 3.7 → 3.7 |
| 03 | gradient_soft | 97.9 → 96.9 | 94.8 → **87.3** | 10.4 → **7.9** |
| 04 | thin_line_outline | — (no interior) | 99.6 → **96.7** | 54.0 → **46.6** |
| 05 | wordmark_caps | 96.3 → 95.5 | 85.5 → 82.2 | 12.6 → **11.2** |
| 06 | wordmark_script | 98.2 → 98.2 | 91.4 → **91.8** | 25.8 → **23.0** |
| 07 | circular_badge | 98.1 → 97.5 | 96.3 → 95.0 | 5.7 → **4.9** |
| 08 | mascot_detail | 98.6 → 97.8 | 95.8 → 92.3 | 5.4 → **4.2** |
| 09 | nonuniform_bg | 99.0 → 99.0 | 93.3 → 93.3 | 3.9 → 3.9 |
| 10 | low_contrast | 98.6 → 98.6 | 94.9 → 94.4 | 3.0 → 3.0 |

**01 and 09 are bit-stable controls** — identical on all three measures, which is the check that the
harness is measuring what it claims.

**04 has no interior at any erosion**: at 0.28–0.62mm, the entire shape *is* edge band. Its 46.6%
spill is likewise not a defect but a unit problem — a 0.3mm shape traced with 0.4mm thread cannot
avoid spilling; the tatami baseline spilled *more* (54.0%).

**The honest counterweight: edge-band coverage went DOWN on the fixtures that changed** — 03 by 7.5
points, 08 by 3.5, 04 by 2.9, 05 by 3.3. This is the same trade-off measured in Part 2.5 §4, now
confirmed across the whole corpus rather than two fixtures: **tatami buys edge-band coverage by
overshooting the outline**, and spill fell on every one of those same fixtures. A reviewer is
entitled to call this metric-shopping; both numbers are above, and neither was chosen after the fact —
spill was introduced in Part 2.5 before this part's classification changes existed.

## 6. The satin cap moved 4.0 → 4.5mm, and it was a test that surfaced it

`test_rotated_bar_becomes_satin_with_angle` builds a bar its docstring calls "~3.6mm wide" — the
nominal `cv2.line` thickness. Rasterised at 45° it is not 3.6mm. Measured three independent ways:

| Method | Width |
|---|---|
| Perpendicular ray count across the bar | **4.43mm** |
| Area ÷ skeleton length | **4.25mm** |
| Largest inscribed circle × 2 (distance transform) | **4.50mm** |
| *(old rule's `minAreaRect` short side, for contrast)* | *3.82mm* |

The old rule passed that test only because `minAreaRect` fits the staircase corners and **under-reads**
a diagonal. A measured-width rule correctly reports ~4.4mm, so a 4.0mm cap excluded a bar any
embroiderer would satin. **The cap was wrong, not the test.**

Corpus sensitivity, measured rather than argued:

```
cap=4.0mm  71 -> 70 satin objects   (08 loses one)
cap=4.5mm  71 satin objects          <- shipped
cap=5.0mm  72 satin objects          (08 gains one)
cap=6.0mm  74 satin objects          (03 +1, 07 +1, 08 +1)
```

**Exactly one object** separates 4.0 from 4.5, and **no broad fill changes at any cap up to 6.0mm** —
fixtures 01 and 09 stay 0/2 satin throughout. 4.5mm remains far below the spec's own 10–12mm ceiling,
and it is safer now than it was before: satin follows the medial axis with per-segment tatami fallback
for anything too wide, where previously it was a bounding-rect zigzag good only for a straight bar.

A reviewer may still read this as tuning to pass a test. The three measurements above and the
sensitivity table are the evidence; both are reproducible from the fixture.

## 7. Defects this part introduced and then fixed — with the intermediate numbers

Two regressions appeared during the work. Both are recorded because the intermediate states are the
interesting part, not the final one.

**(a) Underlay travel exceeded the machine limit — 82mm stitches.** Generalising satin to rings broke
`_center_walk`, which walks the midline of the min-area **bounding rectangle**: for a ring that is a
diameter straight through the hole. Replacing it with a medial-axis walk was correct, but the
decimation was written as a **list-index stride** while consecutive axis samples are one satin column
(~0.4mm) apart — so the underlay pitch became `stride × 0.4mm`, and across a branch boundary it was
unbounded. Result: 6 fixtures over the limit, worst stitch **82.22mm**. Fixed by decimating by
**distance** and deriving jump flags from the travelled gap the way `_center_walk` did, so a
discontinuity becomes a JUMP regardless of branch bookkeeping (`_axis_underlay`). An attempt to fix it
by carrying per-branch flags through the pipeline was tried first and **abandoned** — it left 6
fixtures over the limit — because the flags are the fragile part.

**(b) Rings came out visibly dashed.** Caught by opening the grid, not by a metric. `_skeleton_branches`
counted 8-neighbours directly, so every L-corner of a thinned staircase — which is what any curve
becomes at 1px — read as a junction: fixture 04's outer ring shattered into **617 "branches" from
1,288 skeleton pixels**, most of length 2. Satin over 2-pixel fragments is noise (the tangent
quantises to 45°, columns scatter, short columns get coalesced away). Suppressing diagonal edges that
are already served by a shared 4-neighbour — the standard connectivity rule, symmetric from either
end — takes that ring to **1 branch**, and a real junction still reads as one.

| | dashed | **fixed** | tatami baseline |
|---|---|---|---|
| 04 edge band | 89.3% | **96.7%** | 99.6% |
| 04 jumps | 192 | **29** | 285 |
| 04 max stitch | 2.46mm | 2.59mm | 8.58mm |

## 8. What is still wrong

1. **Seven objects on fixture 08 and two elsewhere return `no_medial_axis` at 0.73mm** — freckles and
   catchlights too small to thin. They get a tiny tatami fill. A bean or run stitch would be the
   craft-correct answer; neither exists on this path.
2. **03's annuli are the weakest satin call in the corpus** (edge band 94.8 → 87.3). They *are*
   strokes geometrically, but they are strokes only because a gradient got quantised into bands — the
   classifier cannot see that distinction, and arguably should not.
3. **Runtime 7.6s → 12.8s for ten designs.** Thinning is not free. The pre-gate already skips it for
   broad fills (measured 17.5s → 10.2s when tightened from 2.0 to 1.5, with byte-identical
   classifications under the pinned RNG); the rest is real work.
4. **Edge-band coverage remains below tatami on every fixture that flipped.** §5. The remedy is
   edge-defined satin — pairing the two boundary contours and generating columns between
   *corresponding* points — which is still the larger piece of work described in Part 2.5 §5.

## 9. Verification

```
pytest — WITH rembg:     90 passed, 1 warning in 19.00s
pytest — WITHOUT rembg:  90 passed, 1 warning in 6.01s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Scope: `app/services/digitizer.py` and `scripts/run_quality_bench.py` only. Background separation
(`segmentation.py`), colour/layer logic, and the Part 2.5 renderer (`package.py`) are untouched — the
`git diff` covers two files.

## 10. What to attack

1. `SATIN_MAX_UNCOVERED = 0.35` is the load-bearing constant: it alone stops broad fills becoming
   satin. What shape is 60% coverable by capped columns and *should* still be a fill?
2. The 4.0 → 4.5mm cap change (§6). Is a fixture whose true width was mis-stated in its own docstring
   sufficient grounds, given the alternative reading is that I moved a threshold to pass a test?
3. Deleting `SATIN_ASPECT` removes the only shape-elongation signal. Is there a case where a shape is
   thin by measured width and yet *not* satin work?
4. §5's edge-band losses are real. Is spill a fair rebuttal, or is a 7.5-point edge-band loss on
   fixture 03 simply a regression that should have blocked the satin call there?
