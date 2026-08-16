# Output quality: what competitors do, what our code must change, and in what order

**This document is about the picture, not the instruments.** Nine tranches have made the
measurements trustworthy. The rendered output has not visibly moved in that time, and this plan
says what to change so that it does.

It opens with a refuted hypothesis of my own, because that is what the first attempt produced and
suppressing it would waste the next person's day.

---

## 0. THE REFUTATION THAT OPENS THIS PLAN

**Hypothesis:** 05_wordmark_caps' 1.3987 mm median edge deviation is variance injected by
`columns._extreme_per_station`, which keeps the FARTHEST boundary sample per column station. A
maximum over pixel-quantised samples is an extreme-value statistic whose variance rises with how
many samples land in the bin — dozens at a corner, a handful on a straight. It fit the measured
signature exactly: pull compensation perfect to four decimals, edge wandering 3.5 thread widths.

**Test:** damp the reach magnitude along the column axis over one thread width of arc, keeping
the maximum's reach and the axis's direction. Implemented, measured with
`scripts/measure_surface.py` across the standing sixteen.

**Result — REFUTED. Every measured fixture got worse:**

| fixture | before | after |
| --- | ---: | ---: |
| 02_logo_fine_text_3color | 0.6712 | 0.6758 |
| 03_gradient_soft_subject | 0.6711 | 0.6764 |
| 04_thin_line_outline | **0.0331** | **0.0600** |
| 05_wordmark_caps | **1.3987** | **1.4173** |
| 06_wordmark_script | 0.8550 | 0.9186 |
| 07_circular_badge | 0.3705 | 0.4320 |
| 08_mascot_detail | 0.1727 | 0.2292 |

Not one improved. The change was reverted; no code from it is in the tree.

### What the refutation eliminates, which is the useful part

1. **Estimator variance is not the cause.** Damping it moved the edge AWAY from the stored
   contour, so the emitted edge was already tracking something more faithfully than a smoothed
   version of itself.
2. **Pixel quantisation is not the cause, by arithmetic.** 05 is 640x640 at
   `mm_per_px = 0.1828`. One pixel is 0.18 mm; re-rasterisation can contribute at most about
   ±0.09 mm. The measured roughness is 1.13-1.71 mm — **6 to 9 pixels, 12-19x more than the
   entire quantisation budget.**
3. **A generation-vs-storage boundary mismatch is not the cause.** `pipeline.py:754-757`
   rasterises the generation region from `rp.contour`, the same smoothed contour the object
   stores. Both sides share one shape.

### What it leaves, and where the next session should start

Per-object, one fixture, same pull compensation throughout:

| seq | columns | roughness | offset a | offset b |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 42 | **0.2073 mm** | +0.1996 | +0.1998 |
| 1 | 71 | 1.3607 | +0.2000 | +0.2000 |
| 5 | 95 | 1.7080 | +0.1993 | +0.1998 |
| 6 | 101 | 1.5818 | +0.1992 | +0.2022 |
| 4 | 135 | 1.1320 | +0.1998 | +0.1998 |
| 3 | 142 | 1.4367 | +0.1993 | +0.1998 |

**Compensation is identical to four decimals on all six. One letter is 8x cleaner than the
others.** So the defect is per-object and shape-dependent, and it is not any global property of
the estimator, the scale, or the compensation.

The next candidates, in the order they should be tested — each by **varying one thing on
purpose**, not by reading a correlation across fixtures:

* **Corners and curvature extremes.** seq 2 is the simplest glyph in the word. Test: bin the
  per-station deviation by local contour curvature and see whether the tail is corners.
* **Cap and branch-end extension.** `_extend_branch_ends` pushes samples past the skeleton, and
  a wordmark is mostly stroke ends. Test: exclude the first and last N stations per branch and
  re-measure.
* **Branch handover at junctions.** `M`, `S` and `U` have junctions; `I` does not. Test: measure
  deviation as a function of distance to the nearest junction.

One of those three should carry most of the 9 pixels. If none does, the metric itself needs
re-reading before more code is written.

---

## 1. WHAT COMPETITORS ACTUALLY DO DIFFERENTLY

The honest summary is not "better algorithms". It is **one structural difference with four
consequences**.

> Professional packages digitise from an EDITABLE VECTOR OBJECT MODEL, authored or corrected by
> a person. We infer objects from pixels. Every visible quality gap descends from that.

### 1a. Shapes are curves, not traced rasters

Wilcom, Hatch and Ink/Stitch place stitches against Bezier outlines. A column end is the analytic
intersection of a normal with a curve, so the edge is smooth **by construction** — there is no
staircase to remove because there was never a staircase.

We trace a raster mask with `CHAIN_APPROX_NONE` (every boundary pixel, deliberately — the
docstring explains that simplification drops exactly the corners columns must land on), smooth
with Douglas-Peucker plus one Chaikin pass, then **round back to `int32`**
(`geometry.py:219`) and re-rasterise to a binary mask before the generators ever see it.

**Our gap:** no curve ever exists in the pipeline. `docs/CTO-VERDICT-2026-08-09.md` measured
contours turning 11,445-18,937 degrees.

### 1b. Letters come from designed alphabets, not from tracing

Every professional package ships hand-digitised alphabets: each glyph is a satin object a human
designed, with its own underlay, its own pull compensation, and a size range the designer
approved. **Nobody traces letters from pixels**, because at 5-6 mm cap height the trace is noise.

**Our gap:** `lettering.py` converts TrueType outlines via PIL FreeType — better than tracing,
but still an outline conversion rather than a designed glyph. And artwork-embedded text (07's
"HARBOR CLUB") goes through the ordinary raster path and fragments.

### 1c. Fills follow the form

Contour fills that run parallel to a shape's boundary, and turning tatami whose angle varies
along the shape, are standard. They are what makes embroidery catch light like embroidery rather
than like printed vinyl.

**Our state is better than it looks:** `CONTOUR_FILL` IS auto-selected at digitize
(`pipeline.py:940-941, 1088-1089`) behind two gates, and `SPIRAL_FILL` / `RADIAL_FILL` exist with
generators in `rebuild.py:366-372`. So this is **not a missing feature — it is a gating
question**, and gating questions are measurable.

### 1d. A person makes the artistic calls

Stitch direction per object, which detail to keep, what to simplify, where to split a colour.
Auto-digitising is a starting point in every one of these products; the human finishes it. That
is precisely why the "photo or logo to finished design, no human" row is amber for every software
column in the benchmark — **nobody has solved it, which is why the prize is worth chasing.**

---

## 2. THE PLAN, IN PRIORITY ORDER

Each item states the measured baseline it must move, so the next session cannot ship a change
that feels better and measures worse — which is exactly what §0 did.

### P1 — Finish the boundary diagnosis (blocks the curve work)

Baseline: 05 median **1.3987 mm** (3.50 thread widths); 04 median 0.0331; corpus worst object
08 seq 2 at 4.3921.

Run the three tests in §0. Report which carries the deviation. **No code change until one does** —
§0 is the cost of skipping that step.

### P2 — Sub-pixel contours end to end

Two defects, both real, both cheap, and both currently invisible because §1a's staircase
dominates:

* `geometry.py:219` rounds the Chaikin output back to `int32`, discarding the sub-pixel
  precision the smoothing just computed.
* `pipeline.py:757` re-rasterises that contour to a binary mask, so `_boundary_points` recovers
  a pixel staircase regardless of how smooth the contour was.

Carry float contours through to the generators and sample the boundary analytically. This is the
prerequisite for a curve primitive, and it is worth doing even if P1 shows corners dominate.

### P3 — A real curve primitive

Fit cubic Beziers to the simplified contour, splitting at detected corners so sharp features are
not rounded away, and place column ends by intersecting the axis normal with the fitted curve.
This is §1a, and it is the single largest visible-quality item on the board.

Measure: boundary deviation on all sixteen, and the corpus turning-degrees figure from
`CTO-VERDICT-2026-08-09`.

### P4 — Legibility, and the fragmentation it exposes

Surface Metric 2, already specced and still unbuilt. §2b of `SURFACE-METRICS-2026-08-27` showed
boundary deviation is **structurally blind** to 07's arc text, because a letter emitted as two
fragments has two clean edges. Legibility is the metric that sees it.

Then the fix it points at: a component-merge pass that rejoins same-colour fragments within a
thread width before generation, so a letter is one object rather than three.

### P5 — Measure the vector path against the raster path

`geometry._decode_svg` already exists and recovers an EXACT foreground mask by rendering twice,
on white and on black. **Nobody has ever measured how much better SVG input is.**

If the gap is large, it is simultaneously a product answer ("send vector art where you have it")
and a way to isolate how much of the quality gap is inference error rather than generation error.
Cheapest high-information experiment on this list.

### P6 — Contour-fill gating

Measure how often `CONTOUR_FILL` fires across the sixteen and what the two gates
(`CONTOUR_FILL_MIN_MM2`, `CONTOUR_FILL_MAX_BAND_RATIO`) reject. If it almost never fires, the
"flat, directionless fills" finding is a threshold question with a cheap answer, not a missing
feature.

### P7 — Alphabets

Out of scope for a code change: hand-digitised alphabets are a content investment, not an
algorithm. Named so it is not mistaken for something the pipeline can infer.

---

## 3. WHAT THIS PLAN DOES NOT CLAIM

Nothing here has been sewn. Every number is a render or a geometric measurement, and the three
intake asks — a flat-lit scan, light-garment artwork with a near-white element, and a mid-tone or
dark garment with tone-on-tone artwork — are still open and still empty. A boundary-deviation
figure is a good proxy for a ragged edge; it is not a sew-out.
