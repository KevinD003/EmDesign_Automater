# Surface metric 1, built — and the prediction it was built to test, half refuted

**Ruling of 2026-08-27 executed.** Base → Head **`fd5aa5a..7da8644`**, on `main`.
CI **31927482610** (#134): both jobs `completed`, **`conclusion: success`**, from the API.

Local lanes on that exact tree: `pytest -q` **1445 passed**, 2 skipped, 2 deselected,
3 xfailed, exit 0 (18:17); `STITCHIQ_NO_REBUILD_PASSTHROUGH=1` **1439 passed**, 8 skipped,
2 deselected, 3 xfailed, exit 0 (17:29).

---

## 0. LEAD WITH THE REFUTATIONS

**R1 — the falsifiable prediction is HALF refuted, and the half that fails is the useful
half.** 05 separates cleanly; **07's arc text does not.** Its letters read 0.34–0.57 mm,
indistinguishable from clean fixtures, while all of 07's deviation sits in one object — the
1067-column ring. The ruling said that would mean the metric measures the wrong thing. The
narrower reading is §2b: arc text fails by **fragmentation**, and a letter emitted as two
pieces has two clean edges. Boundary deviation is structurally blind to it, which is the
spec's own claim now demonstrated rather than asserted.

**R2 — two defects in my own instrument, both caught by numbers being impossible rather than
merely surprising.** The first run reported **226 mm of deviation on a 90 mm design** (a
hi-res space collision); the second reported ring *width* as raggedness (holes not counted as
boundaries). Both in §3.

**R3 — the `_INK_DELTA` magnitude I predicted is right and the AXIS is wrong.** I extrapolated
from the substrate gate's BGR/dE ratios that saturated or coloured garments would be the strict
end, roughly threefold. Measured: the spread is **2.77×** — magnitude correct — but it is
monotone in **luminance**, running the other way. **The darker the garment, the more perceptual
difference this rule demands before it will rescue dropped artwork.**

**R4 — my own "the corpus has no mid-tones" framing was too coarse.** 09 sits at luma 162 and
C18 at 195; that is *why* the trend was measurable. What is missing is narrower and is stated
as such in §4.

---

## 1. Metric 1 — boundary deviation, across the sixteen

    scripts/measure_surface.py --json out.json
    scripts/measure_surface.py --objects 07_circular_badge
    keys: fixtures[].summary.{median_roughness_mm,worst_roughness_mm,worst_object_seq}

**Reported in mm and thread widths (40wt ≈ 0.4 mm). NO BAND**, deliberately — this repository
has twice shipped a constant fitted to the corpus that named it.

| fixture | satin objs | median | worst | thr | max\|d\| | worst obj |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **05_wordmark_caps** | 6 | **1.3987** | 1.7080 | 4.27 | 1.9334 | seq 5 |
| 10_low_contrast_subject | 2 | 0.8925 | 1.6087 | 4.02 | 1.7278 | seq 4 |
| 06_wordmark_script | 7 | 0.8550 | 1.1619 | 2.90 | 1.2684 | seq 6 |
| 02_logo_fine_text_3color | 10 | 0.6712 | 0.9034 | 2.26 | 0.6770 | seq 3 |
| 03_gradient_soft_subject | 2 | 0.6711 | 1.2290 | 3.07 | 1.4039 | seq 1 |
| 07_circular_badge | 17 | 0.3705 | **2.6577** | 6.64 | 3.5048 | seq 3 |
| A02_real_neckline_black | 169 | 0.2653 | 1.9120 | 4.78 | 1.8946 | seq 45 |
| 08_mascot_detail | 11 | 0.1727 | **4.3921** | 10.98 | 6.4372 | seq 2 |
| A01_real_peacock_patch_photo | 66 | 0.1266 | 1.7865 | 4.47 | 2.5952 | seq 1 |
| C24_many_colours | 7 | 0.1132 | 0.4583 | 1.15 | 0.4441 | seq 8 |
| 04_thin_line_outline | 10 | **0.0331** | 0.0892 | 0.22 | 0.3375 | seq 1 |

01, 09, C05, C11, C18 carry no satin objects and are reported as unmeasured rather than as
zero — `boundary_deviation` returns `None` so "clean" and "not measured" cannot be conflated.

**Median and worst answer different questions and the table shows why.** 08 has the *third
best* median and the *worst* single object; 05 has the worst median and a tight worst. A design
whose defect is localised (07, 08) is invisible in a median over 17 objects; a design whose
defect is everywhere (05) is invisible in a max. Both columns are load-bearing.

## 2. The prediction, tested

### 2a. 05 — borne out, and the offset/roughness split earns its keep

05 is the **worst median in the corpus**: 1.3987 mm, **3.50 thread widths**, against 04's
0.0331. And its offsets are textbook:

| seq | cols | roughness | offset a | offset b | asymmetry |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 95 | 1.7080 | **+0.1993** | **+0.1998** | **0.0005** |
| 6 | 101 | 1.5818 | +0.1992 | +0.2022 | 0.0030 |
| 3 | 142 | 1.4367 | +0.1993 | +0.1998 | 0.0005 |

**05 is perfectly calibrated and rough.** Pull compensation is applied, both sides, to four
decimal places — which is a free confirmation of UP1's per-side fix — and the edge still
wanders 3.5 threads. A metric reporting raw distance would have read that +0.2 as the finding
and missed the wander entirely. This is the case the split was built for, and the fixture I
flagged visually four tranches ago for irregular column ends is the one it names.

### 2b. 07's arc text — NOT borne out, and the diagnosis is narrow

| seq | cols | roughness | offset a | offset b | what it is |
| ---: | ---: | ---: | ---: | ---: | --- |
| 3 | 1067 | 2.6577 | −0.7424 | −1.0684 | the navy ring |
| 14 | 19 | 0.5683 | +0.2333 | +0.2477 | an arc-text letter |
| 19 | 17 | 0.5283 | +0.1297 | +0.2254 | a letter |
| 17 | 26 | 0.5150 | +0.1319 | +0.1998 | a letter |
| 4 | 769 | 0.3528 | +0.1512 | +0.2409 | the gold ring |

The letters read **0.34–0.57 mm with clean positive offsets** — below 02, 03, 06 and 10, all of
which I would call visually fine. The metric cannot see 07's degradation.

**Why, precisely:** 07's arc text is degraded by *fragmentation* — letters broken into pieces
or missing outright. Boundary deviation measures how well an **emitted** edge tracks **its own**
contour. A letter that came out as two fragments contributes two objects, each with a clean
edge; a letter that was never emitted contributes nothing to measure. The defect is in the
object *set*, not in any object's surface.

The spec anticipated exactly this — *"legibility gates structure, boundary deviation gates
edges; neither substitutes for the other"* — and this is the first empirical demonstration.
**So the prediction did not falsify the metric; it identified which metric the defect needs.**
That makes Metric 2 the load-bearing half rather than the second half.

## 3. Two defects in the instrument, and how they surfaced

**A space collision — 226 mm on a 90 mm design.** `_column_ends` runs inside
`_skeleton_satin_hires`, in **hi-res** pixels. `cand` and `axis_pts` are divided by `f` on the
way out; my edge log was not. Fixed at the same site as the other two rescales, so a future
change to `f` cannot rescale two of three. Caught in one glance because the number was
physically impossible rather than merely large — which is the argument for reporting in mm
rather than in pixels.

**Holes are boundaries too.** On an annulus every column has one end on the **hole**, and the
first version measured it against the outer contour — reporting the ring's *width* as
deviation. It showed itself because **the three worst objects in the whole corpus were exactly
the three with holes**:

| object | before | after |
| --- | ---: | ---: |
| 08 seq 2 (knocked-out head) | 15.4635 | **4.3921** |
| 07 seq 3 (navy ring) | 6.7789 | **2.6577** |
| 07 seq 4 (gold ring) | 3.7205 | 0.3528 |

Both were the instrument measuring the wrong distance, not the pipeline sewing badly. Recorded
in `_signed_distances`' docstring with the numbers, because a corrected instrument that does
not say what it used to report invites the same mistake next time.

**`pipeline.py` stayed at exactly 1500 and the space was paid for structurally** — the
classification-log dict moved to `accounting.log_classification` — rather than by comment-golf
for a fourth tranche. A structural constraint should be met structurally.

## 4. `_INK_DELTA` — the ratio survey (measured), the decision test (blocked)

    scripts/measure_ink_delta.py --json out.json

`_reclaim_missed_ink` rescues artwork the matte dropped when it sits ≥ **60.0** in Euclidean
BGR from the garment. Sampling the real pixels within ±5 of that boundary on all sixteen:

| substrate luma | fixtures | dE2000 at the 60.0 boundary |
| ---: | --- | ---: |
| 255 | 02, 05, 06, 07 | **7.4 – 11.0** |
| 219 | 03 | 8.6 |
| 195 | C18 | 12.3 |
| 162 | 09 | 20.1 |
| 12 | C24 | 20.4 |
| 0.7 | A02 | **19.5** |

**2.77× spread in what "unmistakably ink" means** — and monotone in luminance, not saturation
(R3). The substrate gate's ratios do not transfer because they were measured at *small*
distances near black where L\* is steep; 60 BGR from black lands well up the L\* curve while
60 BGR from white barely moves it. **A ratio is a local property, and carrying it across a
distance is the same class of error as carrying a constant across a space.**

**Direction matters: this is the opposite error from the substrate gate.** That one sewed
invisible thread. This one would **discard visible artwork**, on dark garments.

**The blocked half, narrowed.** Not "the corpus has no mid-tones" — 09 and C18 sit between,
which is how the trend was measurable. What is missing is **artwork close to its own garment's
tone on a dark substrate**: A02 and C24 are dark but carry high-contrast florals, so nothing
in them is near enough for a dE-20 threshold to discard. Whether the spread produces a **wrong
verdict** is unanswerable on this corpus, and is said rather than inferred.

**`_INK_DELTA` is NOT moved**, as ruled.

## 5. Third intake ask (§2c)

**A mid-tone or dark garment with tone-on-tone artwork** — a royal-blue polo with navy
lettering, a heather-grey tee with grey embroidery, a tan cap with cream thread.

The first ask justified by **two independent measurements**: it answers whether `_INK_DELTA`'s
2.77× spread produces a wrong verdict, **and** it is the class the phantom `COLOR_CHANGE`
needs, since a truly dark garment is excluded one guard earlier by `DARK_CLOTH_LUM = 60.0`.
One job unblocks two queued items.

## 6. What is NOT done

| item | state |
| --- | --- |
| **Surface Metric 2 — legibility** | **not built** — and §2b makes it the load-bearing half |
| a band or gate on boundary deviation | **deliberately absent** |
| fills' boundary points | **not instrumented** — only satin objects are measured; a fill's scanline–edge intersections are equally explicit at generation but were not hooked |
| `_INK_DELTA`'s decision test | **blocked on §5** |
| aligning the two run emitters | **named, not written** |
| rebuild census, TEXTURE_RETRY's second question, SH2 | **queued** |

## 7. Standing

Nothing has been sewn. Three named intake asks, each earned by a measurement — a flat-lit scan
under `TEXTURE_SMOOTH_MIN` 6.0, light-garment artwork with a near-white element, and a mid-tone
or dark garment with tone-on-tone artwork. The spec is still empty and still the highest-value
input on the board.
