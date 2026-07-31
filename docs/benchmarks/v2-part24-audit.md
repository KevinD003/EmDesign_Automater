# v2 Part 24 — closing the two gaps that made our output look auto-digitized

**Date:** 2026-07-31 · Branch `claude/code-quality-improvements-hyu6dg`
Acts on gaps **A1** and **A2** of [`../COMPETITIVE-GAP-ANALYSIS.md`](../COMPETITIVE-GAP-ANALYSIS.md).

Everything below is measured. Baseline tag `v2-part24-base3`, result tag `v2-part24`,
both produced by `scripts/run_quality_bench.py` in the same container with the same
RNG seed and the same rembg build.

---

## 1. Headline

| | Before (Part 23) | After (Part 24) |
|---|---|---|
| Distinct fill angles across the corpus | **1** (`0.0°`, every fill) | **15** |
| Underlay types actually generated | **2** of 6 | **3** of 6 (+1 more implemented, see §5) |
| Mean interior coverage | 98.06 % | **98.61 %** (+0.56) |
| Mean edge-band coverage | 97.32 % | **97.62 %** (+0.30) |
| Mean spill | 12.19 % | 12.22 % (+0.03) |
| Floor violations / over-limit / flagged density cells | 0 / 0 / 0 | **0 / 0 / 0** |
| Total stitches | 41,126 | 44,333 (**+7.80 %**) |
| Tests | 678 | **692** |

No fixture got worse on any coverage measure.

---

## 2. The instrument was wrong first

The first attempt at A1 appeared to destroy coverage — fixture 01 fell 100.0 → 84.5,
fixture 09 100.0 → 96.6. **That was the measuring tool, not the stitching**, and the
whole result would have been abandoned on a false negative if it had been taken at
face value. Two independent biases, both invisible while every fill was emitted at 0°:

| # | Bias | Evidence | Fix |
|---|---|---|---|
| M1 | `cv2.line(..., thickness)` paints a different perpendicular width per angle | For a nominal 4px: **5.00px at 0° and 90°, 4.25px at 45°**. Against a 4.5px row pitch that decides "covers" vs "gap". | Draw each segment's exact swept band — a rotated rectangle plus round caps, sub-pixel via OpenCV `shift` |
| M2 | A single measurement frame rewards rows that align with the pixel grid | The **unchanged Part 23 designs** re-measured in a rotated frame: fixture 09 scored **100.0 / 99.4 / 97.6 / 99.9** at 0 / 22.5 / 45 / 11°; fixture 10 **100.0 / 99.3 / 97.4 / 99.9**. The stitches never moved. | Average coverage over four measurement frames |

The 0.05mm gap between a 0.45mm row pitch and 0.4mm thread is half a pixel at
`PX_PER_MM = 10`. At 0° every row shares one phase, so it all vanished — which is
why the corpus reported clean 100.0s.

Verification that the instrument is now sound:

| Check | Before fix | After fix |
|---|---|---|
| Same disc filled at 0…90°, spread in interior coverage | 7.0 pts | **0.0 pts** |
| Real design measured in three unrelated frames, spread | 2.6 pts | **0.2 pts** |

Both are pinned by `tests/test_coverage_metric_is_angle_fair.py`, including a test
that asserts the OLD rasteriser still fails, so nobody restores it as a
one-line simplification.

**The corrected Part 23 numbers are the baseline used everywhere below.** Under the
sound instrument, A1 alone is coverage-neutral (+0.06 interior), not −1.04.

---

## 3. A1 — per-object fill angle

`stitch_angle = round(rect[2], 1) if is_satin else 0.0` sent every tatami fill to 0°.
`_scanline_angled` already existed but was reachable only through `rebuild_design`,
i.e. only after a user hand-set an angle in the UI.

| Case | Rule | Why |
|---|---|---|
| Elongated shape (axis ratio ≥ 1.15) | Rows along the **principal axis** of the pixel covariance | Row ends land on the two SHORT edges instead of the two long ones, so the ragged seam sits on the smallest share of the perimeter. This is what "auto angle" means in the desktop suites. |
| Isotropic shape | Angle ~45° **off the region's dominant boundary direction** | Rows parallel to a strong edge are the classic amateur tell; rows perpendicular line up every row-end on it |
| No preferred boundary direction (disc, ring) | 45° | The default new fills get in Hatch and Wilcom, and correct here |

Moments, not `minAreaRect`: a plus sign, a ring and a star all have a square hull and
would get an arbitrary rect angle, while their moment axis correctly reports them as
isotropic.

**A mistake worth recording:** the edge-avoidance was first written as a doubled-angle
vector mean, which cannot represent a bimodal boundary. A diamond's edges run at +45
and −45; doubled those are +90 and −90, which cancel — so it returned exactly 45.0 for
the one shape whose direction most needed avoiding, i.e. rows straight down its own
edges. Replaced with a length-weighted orientation histogram and an explicit search
minimising `|cos(2Δ)|`. Diamond now measures 2.0°.

Verified behaviour:

| Shape | Angle | Correct because |
|---|---|---|
| 3:2 oval at 30° | 30.0° | its own axis |
| Long bar at −20° | −20.0° | its own axis |
| Axis-aligned square | −42.0° | ~45 off edges at 0/90 |
| Diamond (edges ±45°) | 2.0° | ~45 off edges at 45/135 |
| Disc, ring | 45.0° | nothing to avoid |

---

## 4. A2 — underlay selected instead of fixed

Part 23 assigned `CENTER_WALK` to every satin object and `EDGE_WALK` to every fill.
`DOUBLE_ZIGZAG`, `PARALLEL` and `CONTOUR` were enum members with no generator.

| Object | Band | Underlay now |
|---|---|---|
| Satin | < 2.0mm | Centre run (unchanged) |
| Satin | 2.0 – 4.0mm | Edge run |
| Satin | ≥ 4.0mm | **Double zigzag** — two passes, second offset half a step and walked back |
| Fill | < 100mm² | Edge run (unchanged) |
| Fill | ≥ 100mm² | **Edge run + tatami layer** at 3× the top pitch, crossing the top fill at 90° |

Zigzag half-width comes from the distance transform at each axis sample — the true
local half-width — so the lattice follows a stroke that narrows or curves rather than
assuming a constant bar.

**A second mistake worth recording:** the first `_zigzag_underlay` derived its jump
flag from the distance between consecutive points, which is what every other generator
in the module correctly does. But a zigzag's consecutive points are the two sides of
the column, so **every throw came back flagged as a jump** and the underlay stitched
nothing. Caught by measuring the emitted stream on a synthetic 6mm bar, not by
reading the code. Now 2 jumps in 38 points, 37/37 side alternations, insets 0.50mm,
every stitch 5.39mm.

---

## 5. What this did NOT achieve — stated plainly

| Item | Status |
|---|---|
| `DOUBLE_ZIGZAG` on the corpus | **Never fires.** The corpus's widest satin column measures 3.78mm against `SATIN_MAX_W_MM = 4.5`, so the ≥4mm band is a 0.5mm sliver. Implemented, rule-selected and covered by a synthetic test — but the real gap it exposes is that **we cap satin at 4.5mm while competitors satin to 8–12mm**. That cap is a classification change and was left alone. |
| `CONTOUR` underlay | Still no generator |
| Contour / radial / spiral fills | Still absent. The badge's outer **ring** is the proof it matters: it is now stitched vertically instead of horizontally, which is better, but a ring wants rows that follow it. |
| A3 photo digitizing, A4 lettering engine | Untouched — the large items from the gap analysis |
| Preview honesty | The preview now shows the underlay lattice through the top layer, because it draws every stitch equally. Real thread covers it; our renderer does not model that. |
| Cost | +7.80 % stitches, all underlay. Commercial underlay typically runs 10–20 %, so this is on the light side, but it is a real cost in sew time. |

---

## 6. Per-fixture

| Fixture | interior % | edge % | spill % | stitches |
|---|---|---|---|---|
| 01_flat_2color_logo | 99.9 → **100.0** | 100.0 → 100.0 | 4.3 → 4.3 | 3,563 → 4,051 |
| 02_logo_fine_text_3color | 99.1 → **99.4** | 100.0 → 100.0 | 3.8 → 3.8 | 4,415 → 5,057 |
| 03_gradient_soft_subject | 99.0 → **99.4** | 97.3 → **97.4** | 11.3 → 11.4 | 4,785 → 5,065 |
| 04_thin_line_outline | — | 99.8 → 99.8 | 47.3 → 47.3 | 1,731 → 1,731 |
| 05_wordmark_caps | 93.5 → **95.7** | 88.8 → **91.2** | 11.4 → 11.5 | 1,414 → 1,657 |
| 06_wordmark_script | 97.8 → 97.8 | 93.8 → 93.8 | 23.8 → 23.8 | 1,455 → 1,455 |
| 07_circular_badge | 98.4 → **98.9** | 97.8 → **98.0** | 5.7 → 5.7 | 11,767 → 12,409 |
| 08_mascot_detail | 96.6 → **97.1** | 95.8 → **96.0** | 3.5 → 3.6 | 5,712 → 5,834 |
| 09_nonuniform_background | 99.2 → **99.6** | 99.9 → **100.0** | 6.7 → 6.7 | 1,747 → 1,960 |
| 10_low_contrast_subject | 99.0 → **99.6** | 100.0 → 100.0 | 4.1 → 4.1 | 4,537 → 5,114 |

Fixtures 04 and 06 are unchanged byte-for-byte (thin strokes and script: no fill over
the underlay threshold, no satin over 2mm) — which is itself a check that the change
is scoped to where the rules say it should be. The stitch-stream lock in
`tests/test_swarm_perf_lock.py` confirms it: of its four locked fixtures only 05 and
07 moved.

## 7. Gates

* `pytest` **692 passed, 2 xfailed** (was 678); 14 new tests
* `ruff check` **19** findings — identical to the pre-change tree, diffed finding by finding
* Floor violations **0**, stitches over 12.7mm **0**, flagged density cells **0**
* Stitch-stream lock regenerated deliberately for 05 and 07, with the diff recorded above
