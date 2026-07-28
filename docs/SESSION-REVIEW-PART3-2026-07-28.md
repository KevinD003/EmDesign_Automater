# STITCHIQ v2 — Part 3 Work Report for Independent Review

**Date:** 2026-07-28 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part3-audit.md`](./benchmarks/v2-part3-audit.md) ·
**Grid:** [`docs/benchmarks/v2-part3-grid.png`](./benchmarks/v2-part3-grid.png)

> **Brief:** generalise the skeleton + local-half-width machinery built for `text_mode` in Parts 2/2.5
> into the default satin/tatami path for **all** shapes, replacing the global aspect-ratio /
> bounding-rect threshold. Don't touch background separation, colour/layer logic, or the Part 2.5
> renderer. Two files only.
>
> §4 and §5 are the parts most worth arguing with.

---

## 1. The old rule was measuring the bounding box, not the shape

```python
rect = cv2.minAreaRect(contour)
is_satin = (SATIN_MIN_W_MM <= min(rect[1]) * mm_per_px <= SATIN_MAX_W_MM
            and max(rect[1]) / min(rect[1]) >= SATIN_ASPECT)
```

A ring, an arc, a horseshoe: uniformly thin, unmistakably satin work, square bounding box. Aspect
ratio ≈ 1 → fails. **Fixture 04, which is nothing but thin lines, scored 0 of 11 objects as satin.**

Now: thin the region to its medial axis, measure the local width along it, and require two things —
the width fits under the satin cap, **and** columns swept along the axis actually account for the
shape (`uncovered ≤ 0.35`). The second test is what stops the obvious failure mode of "measure width,
force everything through it, watch broad fills become satin": a disc *has* a medial axis, but
capped-width columns cannot cover it.

Every decision is logged per object and lands in the harness JSON, so every claim below is quoted from
the run rather than asserted.

## 2. Result — all ten fixtures

| # | Fixture | before | **after** | reason for what stayed TATAMI |
|---|---|---|---|---|
| 01 | flat_2color_logo | TATAMI×2 | **TATAMI×2** | 8.43 / 6.97mm — broad fills. Control, unchanged. |
| 02 | logo_fine_text | T×15 S×1 | **S×12 T×4** | 2 panels 8.25/7.59mm · 2 specks 0.73/1.10mm |
| 03 | gradient_soft | TATAMI×4 | **S×2 T×2** | 5.74mm over cap · 11.47mm core |
| 04 | thin_line_outline | TATAMI×11 | **SATIN×11** | — (widths 0.28–0.62mm, uncovered 0.00) |
| 05 | wordmark_caps | SATIN×6 | **SATIN×6** | — (same verdict, now from geometry not `text_mode`) |
| 06 | wordmark_script | SATIN×12 | **SATIN×12** | — |
| 07 | circular_badge | TATAMI×18 | **S×14 T×4** | 8.04 / 5.56 / 8.04mm · one 0.80mm speck |
| 08 | mascot_detail | TATAMI×21 | **S×12 T×9** | 7 specks at 0.73mm · 4.75 / 8.33mm blobs |
| 09 | nonuniform_bg | TATAMI×2 | **TATAMI×2** | 7.17mm diamond · dot. Control, unchanged. |
| 10 | low_contrast | TATAMI×4 | **S×2 T×2** | 9.51mm · 7.16mm |

**19/96 → 71/96 objects satin.** All three mandated outcomes hold: 04 flips entirely, 07/08 get
partial satin measured under the cap, and neither broad-fill control moves by one object.

**Nothing over the 12.7mm machine limit on any fixture. Corpus jumps 2,613 → 2,046** — below even the
v1 baseline's 2,175, for the first time in this v2 sequence.

**Colour/background, checked field by field rather than assumed:** 02/07/08/09 keep identical
`color_count`, `segmentation_method`, `objects_with_holes` and `filled_area_mm2` **to the decimal**,
and dumping the colour stops and per-object colour assignments from both builds and diffing them gives
`IDENTICAL`. Same pixels, same layers; only the stitching changed. One field does move —
`coverage_ratio` 1.0 → 0.0 on 02/07/08 — and it is not a colour field: it comes from
`fill_row_geometry`, which by design reports nothing for majority-satin designs (Part 1 added that
guard because satin's consecutive points run *across* the column and gave a physically impossible
0.018mm "row pitch"). Those three fixtures became majority-satin. 09 stays 1.0 because it stays
all-tatami.

## 3. Two regressions I introduced, and the intermediate numbers

**(a) 82mm stitches.** Generalising satin to rings broke `_center_walk` — it walks the midline of the
min-area **bounding rectangle**, which for a ring is a diameter straight through the hole. Replacing
it with a medial-axis walk was right; my decimation was not. I wrote it as a **list-index stride**
while consecutive axis samples are one satin column (~0.4mm) apart, so the underlay pitch became
`stride × 0.4mm` and was unbounded across a branch boundary. Six fixtures over the limit, worst
stitch **82.22mm**.

I first tried to fix it by threading per-branch jump flags through the pipeline. That still left six
fixtures over the limit, so I **abandoned that approach** rather than keep tuning it: the flags were
the fragile part. `_axis_underlay` now decimates by **distance** and derives jump flags from the
travelled gap exactly as `_center_walk` did — a discontinuity becomes a JUMP no matter what the branch
bookkeeping upstream does.

**(b) Fixture 04's rings came out dashed.** Found by opening the grid image, not by a metric — every
number was green. `_skeleton_branches` counted raw 8-neighbours, so every L-corner of a thinned
staircase (i.e. every curve at 1px) read as a junction: **617 "branches" from 1,288 skeleton pixels**,
most of length 2. Satin over 2-pixel fragments is noise. Suppressing diagonal edges already served by
a shared 4-neighbour — the standard connectivity rule — takes that ring to **1 branch**.

| | dashed | **fixed** | tatami baseline |
|---|---|---|---|
| 04 edge band | 89.3% | **96.7%** | 99.6% |
| 04 jumps | 192 | **29** | 285 |

This one is worth dwelling on: the dashed ring passed the width test, the coverage test and the
machine-limit test. Only the picture showed it.

## 4. The finding worth arguing with: edge-band coverage fell on every fixture that flipped

Re-grading all ten from stitch geometry (interior = outline eroded 0.6mm; spill = thread outside the
outline):

| Fixture | interior b→a | **edge band b→a** | spill b→a |
|---|---|---|---|
| 01 control | 98.7 → 98.7 | 94.6 → 94.6 | 2.1 → 2.1 |
| 09 control | 99.0 → 99.0 | 93.3 → 93.3 | 3.9 → 3.9 |
| 03 | 97.9 → 96.9 | 94.8 → **87.3** | 10.4 → **7.9** |
| 04 | — (no interior) | 99.6 → **96.7** | 54.0 → **46.6** |
| 05 | 96.3 → 95.5 | 85.5 → 82.2 | 12.6 → **11.2** |
| 08 | 98.6 → 97.8 | 95.8 → 92.3 | 5.4 → **4.2** |

Edge band **down** on every fixture that changed — 03 by 7.5 points. Spill **down** on all of them
too. This is Part 2.5 §4's trade-off confirmed corpus-wide rather than on two fixtures: tatami earns
part of its edge-band number by overshooting the outline.

I am reporting both because either alone misleads. The fair challenge is that spill is a second metric
that happens to favour my change — the mitigating fact is that it was introduced in Part 2.5, before
this part's classification work existed, not selected afterwards.

Also note **fixture 04 has no interior at any erosion** (0.28–0.62mm strokes), and its 46.6% spill is a
unit artifact, not furriness: 0.3mm of shape traced with 0.4mm thread must spill. Tatami spilled more.

## 5. The satin cap moved 4.0 → 4.5mm — a test surfaced it, and I changed the code, not the test

`test_rotated_bar_becomes_satin_with_angle` uses a bar its docstring calls "~3.6mm wide" (the nominal
`cv2.line` thickness). Rasterised at 45° it isn't. Three independent measurements:

| Method | Width |
|---|---|
| Perpendicular ray count | **4.43mm** |
| Area ÷ skeleton length | **4.25mm** |
| Largest inscribed circle × 2 | **4.50mm** |
| *(old rule's `minAreaRect` short side)* | *3.82mm* |

The old rule passed only because `minAreaRect` under-reads a diagonal staircase. Sensitivity, measured:

```
cap=4.0mm -> 70 satin objects      cap=5.0mm -> 72
cap=4.5mm -> 71  (shipped)         cap=6.0mm -> 74
```

**One object** separates 4.0 from 4.5, and **no broad fill changes at any cap up to 6.0mm**. 4.5
remains far under the spec's own 10–12mm ceiling. I could not edit the test — out of scope — so state
the counter-reading plainly: this can be read as moving a threshold to make a test pass. The three
measurements and the sensitivity table are the evidence against that reading.

## 6. Dead code removed rather than left misleading

`SATIN_ASPECT` and `SKELETON_MIN_WIDTH_MM` lost their last callers. I initially wrote a comment
claiming `SATIN_ASPECT` was "retained for `rebuild_design`'s explicit-SATIN path" — **that was wrong**;
that path uses `_satin_zigzag` + `_center_walk`, neither of which consults it. Both constants are
deleted. `SATIN_MIN_W_MM` is kept but deliberately **not enforced**: fixture 04's 0.28mm strokes are
exactly what must become satin, so a 0.8mm floor would reintroduce the defect. The effective floor is
the one-thread half-width clamp.

## 7. Still wrong

1. Nine objects (7 on fixture 08) hit `no_medial_axis` at 0.73mm — freckles and catchlights too small
   to thin. They get a tiny tatami fill; a bean or run stitch is the craft answer and doesn't exist here.
2. Fixture 03's annuli are the weakest satin call in the corpus — geometrically strokes, but only
   because a gradient was quantised into bands. The classifier can't see that, and arguably shouldn't.
3. Runtime 7.6s → 12.8s for ten designs. Thinning isn't free; the pre-gate already skips it for broad
   fills (17.5s → 10.2s when tightened 2.0 → 1.5, classifications byte-identical under the pinned RNG).
4. Edge-band coverage still trails tatami wherever satin took over (§4). Edge-defined satin —
   pairing boundary contours and generating columns between corresponding points — remains the fix,
   and remains larger than one part.

## 8. Verification

```
pytest — WITH rembg:     90 passed, 1 warning in 19.00s
pytest — WITHOUT rembg:  90 passed, 1 warning in 6.01s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Scope held: `git diff` touches `app/services/digitizer.py` and `scripts/run_quality_bench.py` only.
`segmentation.py`, colour/layer logic and the Part 2.5 renderer in `package.py` are untouched.

## 9. What to attack

1. `SATIN_MAX_UNCOVERED = 0.35` is load-bearing — it alone keeps broad fills as fills. What shape is
   60% coverable by capped columns and yet should still be a fill?
2. The cap change (§5). Is a fixture whose own docstring mis-stated its width sufficient grounds?
3. Deleting `SATIN_ASPECT` removes the only elongation signal. Is there a shape that is thin by
   measured width and still not satin work?
4. §4's edge-band losses are real. Is spill a fair rebuttal, or should a 7.5-point loss on fixture 03
   have blocked the satin call there outright?
5. §3(b) — a visibly broken output passed every automated check in the harness. What else is the
   metric set blind to?
