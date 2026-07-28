# v2 Part 2.5 Audit — renderer fidelity + satin edge crispness

**Date:** 2026-07-28 · **Tag:** `v2-part2-5` · graded against [`v2-part2`](./v2-part2-summary.json)

Closes the two open items from [`SESSION-REVIEW-PART2`](../SESSION-REVIEW-PART2-2026-07-28.md) §5–§6:
the preview renderer misrepresenting stitches, and the satin edge-band regression.

---

## 1. Renderer fidelity

### 1a. Satin rendered as scattered ticks

**Quantified first.** The old renderer drew every stitch as an isolated hairline. Measuring the
share of a design's area the render shows as *inked*, against what the stitch geometry actually
covers:

| Fixture | render showed | geometry covers | shortfall |
|---|---|---|---|
| 05 wordmark_caps (satin) | **62.2%** | 87.1% | **−24.9 pts** |
| 06 wordmark_script (satin) | **74.9%** | 90.2% | −15.3 pts |
| 01 flat_2color_logo (tatami) | **71.2%** | 84.3% | −13.1 pts |

So the preview understated *every* fill, and satin worst — which is exactly why a Part 2 reviewer
concluded the strokes were "hollow… outline stitching, not satin".

**Fix, two parts:**
1. **Swath fill.** A satin run is `[top, bottom, top, bottom, …]`; the quad between consecutive
   crossings is what thread physically occupies, so it is filled rather than left to a hairline.
2. **3× supersampling** with a LANCZOS downsample, which removes the sub-pixel rasterisation gaps
   that were eroding tatami as well.

**The swath is gated so it cannot invent coverage.** It fills only when the advance between
crossings is under 1.5 thread widths *and* both crossings are longer than the advance. That is
false for a scanline fill (consecutive points run *along* a row, not across) and false for sparse
satin — so a genuinely gappy fill still renders gappy. This matters: the whole point of the metric
work in Parts 0–1 was that the preview must not flatter the stitches.

| Fixture | before | **after** |
|---|---|---|
| 05 wordmark_caps | 62.2% | **91.8%** |
| 06 wordmark_script | 74.9% | **93.1%** |
| 01 flat_2color_logo (tatami) | 71.2% | **96.5%** |

### 1b. Light thread invisible on light paper

The preview paper is `(250, 250, 250)`. White thread is `(255, 255, 255)` — a total channel
difference of **15**, i.e. invisible under any sane threshold. This is what made a reviewer
conclude fixture 02's white type was not stitched when 398 white stitches were present.

**Fix:** any thread whose luminance is within 60 of the paper's now gets a darker backing halo drawn
one thread-width wider beneath it. Verified on a synthetic three-row swatch:

| Thread | pixels differing from paper | |
|---|---|---|
| pure white `#ffffff` | **23.4%** | visible |
| cream `#f7f4e8` | **41.4%** | visible |
| navy `#1446a0` (control) | 43.7% | unchanged |

## 2. Satin edge crispness

The brief allowed either a full edge-bounded rewrite or a narrower fix with the gap documented.
**A contained fix was shipped**, and it turned out to address the actual cause.

**Root cause.** The distance transform returns the radius of the largest inscribed circle — the
distance to the *nearest* edge, not the distance to the edge *in the direction the column runs*.
Part 2 applied it symmetrically, so on any stroke whose medial axis is not perfectly centred (most
real glyphs, and every curve) one column end fell short of the outline while the other overshot it.
That is the ragged edge, and no amount of tangent smoothing would have fixed it.

**Fix.** Each column end now **ray-marches to the real boundary** along its own direction, giving
each side its own true half-width. ~25 lines; no change to classification, thresholds, or topology.

### Measured, same methodology as Part 2 (interior = glyph eroded 0.6 mm)

| Fixture | variant | interior | **edge band** | spill outside outline |
|---|---|---|---|---|
| 05 | tatami (reference) | 84.5% | 84.1% | 20.0% |
| 05 | Part 2 (skeleton ± dist) | 95.2% | 78.1% | 11.5% |
| 05 | **Part 2.5 (ray-cast)** | **94.9%** | **81.0%** | **10.8%** |
| 06 | tatami (reference) | 92.9% | 87.5% | 27.5% |
| 06 | Part 2 (skeleton ± dist) | 98.2% | 88.7% | 18.8% |
| 06 | **Part 2.5 (ray-cast)** | **98.5%** | **90.8%** | **20.6%** |

- **Fixture 06 edge band now exceeds tatami** (90.8% vs 87.5%) while interior also improved.
- **Fixture 05 closed 48% of its edge gap** (6.0 pts → 3.1 pts) with interior essentially flat
  (95.2 → 94.9%).

### The edge-band metric alone was misleading

Tatami earns part of its edge-band number by **overshooting the outline** — the Part 0 audit itself
observed "row-end ticks overrunning the letter edges". Measuring spill (stitched area *outside* the
design outline) shows satin is the crisper of the two on both fixtures:

**05: satin spills 10.8% vs tatami's 20.0%. 06: 20.6% vs 27.5%.**

So although fixture 05's edge-band coverage is still 3.1 points under tatami, satin's edges are
objectively *tidier* — it covers slightly less of the edge band while spilling roughly half as much
past the outline. Reporting both numbers rather than the flattering one.

### A tuning knob deliberately not used

Adding a small outward bias to the column ends closes 05's remaining edge gap (81.0% → 82.4% at
+1.0 px) — but spill rises with it (10.8% → 18.0% on 05, 20.6% → 32.9% on 06, the latter overtaking
tatami). That trades crispness for a coverage number, i.e. it buys back the exact furriness the
reviewers complained about. **Bias left at zero**; the measurement is recorded here so the choice is
auditable rather than asserted.

### What a full edge-bounded rewrite would still need

Ray-casting is a per-sample correction; it is not a true edge-bounded satin. That would require
pairing the stroke's two boundary contours and generating columns between *corresponding* points —
which needs stroke segmentation at every junction, correspondence between the two contours across
branch/merge topology, and explicit cap handling at terminals. Materially larger than this part, and
the remaining prize is the last ~3 points on fixture 05's edge band.

## 3. Verification

**All 8 non-text fixtures unchanged.** Comparing metric JSONs with volatile fields (`runtime_s`,
`output_png`) stripped, SHA-256 of the canonicalised record:

```
01_flat_2color_logo        v2-part2=a7dcf16820339659  v2-part2-5=a7dcf16820339659  IDENTICAL
02_logo_fine_text_3color   v2-part2=a98c9c32c9524696  v2-part2-5=a98c9c32c9524696  IDENTICAL
03_gradient_soft_subject   v2-part2=1e764e6573ca0ff3  v2-part2-5=1e764e6573ca0ff3  IDENTICAL
04_thin_line_outline       v2-part2=63e13612a80890e4  v2-part2-5=63e13612a80890e4  IDENTICAL
07_circular_badge          v2-part2=7776f8a98e989d8f  v2-part2-5=7776f8a98e989d8f  IDENTICAL
08_mascot_detail           v2-part2=f2dc737f0162eb3a  v2-part2-5=f2dc737f0162eb3a  IDENTICAL
09_nonuniform_background   v2-part2=77ef5189fc6d47b5  v2-part2-5=77ef5189fc6d47b5  IDENTICAL
10_low_contrast_subject    v2-part2=641c1102ff0560b6  v2-part2-5=641c1102ff0560b6  IDENTICAL
  => all 8 non-text fixtures identical: True
```

**Note on "byte-identical":** the output *PNGs* necessarily differ, because item 1 deliberately
changed the renderer. The stitch **data** — every metric describing the actual stitches — is
identical, which is the property that matters. Claiming byte-identical PNGs would have been false.

Text fixtures, as expected: `05` 1,252 → 1,205 stitches, `06` 1,207 → 1,214; satin share 1.0,
jumps 93 / 107 and colour counts 1 / 1 all unchanged.

```
pytest — WITH rembg:     90 passed, 1 warning in 16.76s
pytest — WITHOUT rembg:  90 passed, 1 warning in 5.30s
collected:               90 tests collected
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```
