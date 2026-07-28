# STITCHIQ v2 — Part 2.5 Work Report for Independent Review
**Date:** 2026-07-28 · **Branch:** `claude/code-quality-improvements-hyu6dg` · **Commit:** `693aed0`

> Closes the two open items from [`SESSION-REVIEW-PART2`](./SESSION-REVIEW-PART2-2026-07-28.md)
> §5–§6: the preview renderer misrepresenting stitches, and the satin edge-band regression.
> §4 is the finding most worth arguing with.

---

## 1. Renderer fidelity

### 1a. Satin as scattered ticks

I measured the defect before fixing it — the share of a design's area the render shows as inked,
against what the stitch geometry actually covers:

| Fixture | render showed | geometry covers | shortfall |
|---|---|---|---|
| 05 wordmark_caps (satin) | **62.2%** | 87.1% | **−24.9 pts** |
| 06 wordmark_script (satin) | 74.9% | 90.2% | −15.3 pts |
| 01 flat_2color_logo (tatami) | 71.2% | 84.3% | −13.1 pts |

The preview understated **every** fill, satin worst. That is why a Part 2 reviewer concluded the
strokes were "hollow… outline stitching, not satin" — they were reading a broken renderer.

**Fix:** fill the quad between consecutive satin crossings (what thread physically occupies), plus
3× supersampling with a LANCZOS downsample to kill sub-pixel rasterisation gaps.

**The swath fill is gated so it cannot invent coverage** — it fires only when the advance between
crossings is under 1.5 thread widths *and* both crossings exceed the advance. That is false for a
scanline fill (consecutive points run *along* a row) and false for sparse satin, so both still
render with their real gaps. The renderer must not flatter the stitches; that was the entire point
of Parts 0–1.

| Fixture | before | **after** |
|---|---|---|
| 05 wordmark_caps | 62.2% | **91.8%** |
| 06 wordmark_script | 74.9% | **93.1%** |
| 01 flat_2color_logo (tatami) | 71.2% | **96.5%** |

### 1b. Light thread invisible

Paper is `(250,250,250)`; white thread is `(255,255,255)` — a total channel difference of **15**,
invisible under any threshold. This is what made a reviewer believe fixture 02's 398 white stitches
were absent. Thread within 60 luminance of the paper now gets a darker backing halo one thread-width
wider beneath it.

| Thread | pixels differing from paper |
|---|---|
| pure white `#ffffff` | **23.4%** (was ~0) |
| cream `#f7f4e8` | **41.4%** |
| navy `#1446a0` (control) | 43.7% (unchanged) |

## 2. Satin edge crispness — contained fix, and it found the actual cause

**Root cause.** The distance transform returns the radius of the largest inscribed circle — the
distance to the *nearest* edge, not the edge *in the direction the column runs*. Part 2 applied it
symmetrically, so on any stroke whose medial axis is off-centre (most glyphs, every curve) one
column end fell short of the outline and the other overshot. **No amount of tangent smoothing could
have fixed that**, which is why Part 2's attempts kept plateauing.

**Fix:** each column end now ray-marches to the real boundary along its own direction, so each side
gets its own true half-width. ~25 lines. No change to classification, thresholds, or topology.

| Fixture | variant | interior | **edge band** | spill outside outline |
|---|---|---|---|---|
| 05 | tatami (reference) | 84.5% | 84.1% | 20.0% |
| 05 | Part 2 | 95.2% | 78.1% | 11.5% |
| 05 | **Part 2.5** | **94.9%** | **81.0%** | **10.8%** |
| 06 | tatami (reference) | 92.9% | 87.5% | 27.5% |
| 06 | Part 2 | 98.2% | 88.7% | 18.8% |
| 06 | **Part 2.5** | **98.5%** | **90.8%** | **20.6%** |

- **06's edge band now exceeds tatami** (90.8% vs 87.5%), interior also up.
- **05 closed 48% of its edge gap** (6.0 → 3.1 pts), interior essentially flat.

## 3. A tuning knob measured and deliberately rejected

Adding an outward bias to column ends closes 05's remaining gap (81.0% → 82.4% at +1.0 px). Spill
rises with it: 10.8% → 18.0% on 05, and 20.6% → **32.9%** on 06, overtaking tatami. That trades
crispness for a coverage number — buying back the exact furriness the reviewers flagged. **Bias left
at zero.** Recorded here so the choice is auditable rather than asserted.

## 4. The finding worth arguing with: edge-band coverage flatters tatami

Tatami earns part of its edge-band number **by overshooting the outline** — the Part 0 audit itself
noted "row-end ticks overrunning the letter edges". Measuring spill (stitched area *outside* the
outline) inverts the ranking:

**05: satin spills 10.8% vs tatami's 20.0%. 06: 20.6% vs 27.5%.**

So on fixture 05, satin covers 3.1 points less of the edge band while spilling **roughly half** as
much past the outline. By the metric the Part 2 review used, satin still trails; by spill, satin is
clearly tidier. I am reporting both rather than the flattering one, but a reviewer may reasonably
argue I have picked a second metric that happens to favour my change — that is the fair challenge
here, and the raw numbers for both are above.

## 5. What a full edge-bounded rewrite would still need

Ray-casting is a per-sample correction, not true edge-bounded satin. That would require pairing the
stroke's two boundary contours and generating columns between *corresponding* points — needing
stroke segmentation at every junction, contour correspondence across branch/merge topology, and
explicit cap handling at terminals. Materially larger than this part, and the remaining prize is the
last ~3 points of fixture 05's edge band.

## 6. Verification

**All 8 non-text fixtures unchanged** — SHA-256 of canonicalised metric JSONs (volatile `runtime_s`,
`output_png` stripped):

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

**One honest correction to the brief's wording:** the output *PNGs* are **not** byte-identical, and
cannot be — item 1 deliberately changed the renderer, so every PNG in the run differs. The stitch
**data** is identical, which is the property the requirement is protecting. Claiming byte-identical
PNGs would have been false.

Text fixtures, as expected: `05` 1,252 → 1,205 stitches, `06` 1,207 → 1,214; satin share 1.0, jumps
93 / 107, colour counts 1 / 1 — all unchanged.

```
pytest — WITH rembg:     90 passed, 1 warning in 16.76s
pytest — WITHOUT rembg:  90 passed, 1 warning in 5.30s
collected:               90 tests collected
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Scope: `app/services/package.py` (`render_preview` only), `app/services/digitizer.py`
(`_skeleton_satin` column endpoints only), `STATUS.md` (v38), benchmark artifacts. No classification
thresholds, background separation, or colour/layer logic touched; `text_mode` not expanded.

## 7. What to attack

1. Is introducing **spill** as a second metric legitimate, or metric-shopping to make a 3.1-point
   shortfall look like a win? (§4)
2. The swath gate is a **heuristic** (advance < 1.5 thread widths, crossings > 1.5× advance). What
   stitch pattern would fool it into filling a gap that is genuinely open?
3. Supersampling at 3× makes the preview ~9× the pixels internally. Is the cost acceptable for a
   package artifact, and is the `_MAX_SS_PIXELS` ceiling set sensibly?
4. Should the backing-halo threshold (luminance gap < 60) be relative to a configurable garment
   colour rather than the fixed paper tone, given real previews are viewed against unknown fabric?
