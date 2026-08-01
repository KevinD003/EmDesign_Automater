# v2 Part 24b — contour fill, and a recommendation of my own that measurement killed

**Date:** 2026-07-31 · Branch `claude/code-quality-improvements-hyu6dg`
Follows [`v2-part24-audit.md`](./v2-part24-audit.md). Two items were attempted:
raising the satin width cap, and contour fill. **One shipped. One did not.**

Baseline `v2-part24-base3` (Part 23 code, sound instrument), result `v2-part24b`.

---

## 1. NOT SHIPPED — raising `SATIN_MAX_W_MM`

Part 24's audit said our 4.5mm satin cap was "the real gap … competitors satin to
8–12mm", and recommended raising it. **That recommendation was wrong, and the
sweep says so plainly.**

| Cap | Satin objs | Interior | Edge band | Stitches | **Floor violations** |
|---|---|---|---|---|---|
| **4.5 (current)** | 55 | **98.61** | **97.62** | 45,875 | **0** |
| 6.0 | 58 | 98.50 | 96.97 | 42,893 | **303** |
| 8.0 | 60 | 98.10 | 96.56 | 44,331 | **1,846** |
| 10.0 | 65 | 95.57 | 94.43 | 47,428 | **5,137** |
| 12.0 | 66 | 94.51 | 93.19 | 52,698 | **6,743** |

Every metric degrades, and the 0.30mm penetration floor — at zero corpus-wide
since Part 6 — breaks immediately. On fixture 07 at cap 8.0, the ring object
alone puts **526 of 1,794 penetrations under the floor, minimum 0.15mm**, exactly
half the floor.

I first assumed curvature was the cause: the inner boundary of a curved column is
shorter than the outer one that paces it, which gives a clean derivation
(`W ≤ 2r(1−k)/(1+k)`, so W ≤ 7.1mm at r = 25mm and 2.9mm at r = 10mm) and would
have justified a curvature-aware cap. **A straight 8mm bar was then measured and
it violates too** — 383 penetrations under floor, min 0.155mm — so the derivation
described a real effect that is not the operative one here. The cap change was
abandoned rather than shipped on a plausible mechanism.

**The honest conclusion: 4.5mm is not a conservative preference, it is the width
at which our medial-axis satin can still hold the floor.** Going wider requires
reworking the Part 7 boundary-pacing and branch handling, which is its own
project. Recorded here so it is not re-attempted from the same wrong premise.

---

## 2. SHIPPED — contour fill

Rows that follow the outline, for bands. `StitchType.CONTOUR_FILL` had been a
declared enum value with no generator since v1.

Rows are **iso-distance curves of the region's own distance transform**.
Distance-to-boundary is measured perpendicular to the boundary by definition, so
neighbouring rows sit exactly one pitch apart everywhere including where the band
bends. Offsetting the outline polygon instead would need self-intersection
cleanup at every concave turn; the distance transform gets that free, because a
region that pinches simply splits into two components at the level where it
pinches.

### Result

| | Part 24 | Part 24b |
|---|---|---|
| Mean interior | 98.61 | **98.62** |
| Mean edge band | 97.62 | 97.62 |
| Mean spill | 12.22 | 12.22 |
| Floor / over-limit / density flags | 0 / 0 / 0 | **0 / 0 / 0** |
| Stitches | 44,333 | 45,589 (+2.83 %) |

Coverage-neutral overall, +0.1 on the badge — and the win the coverage metric
cannot see is travel:

| Fixture | Jumps | Trims | Stitch types after |
|---|---|---|---|
| 03_gradient_soft_subject | **144 → 70** | 0 → 0 | SATIN 2, **CONTOUR_FILL 1**, TATAMI 1 |
| 07_circular_badge | **630 → 461** | 17 → 17 | TATAMI 4, SATIN 16, **CONTOUR_FILL 1** |

Every jump is a travel move that becomes a trim and a thread tail, so halving
them on annular regions is a production gain, not a cosmetic one.

### Three things got wrong on the way, each caught by measuring

| # | Mistake | How it showed | Fix |
|---|---|---|---|
| 1 | **Trigger caught solid shapes.** First version fired on any region rejected as `wider_than_satin_cap` while still stroke-like. | Fixture 07's **star** came back with **1,708 missed-interior components** — a solid shape's medial axis is a branching tree, so iso-distance rows crease along every branch. | Require a hole |
| 2 | **Trigger keyed on the classification branch.** `reason == "wider_than_satin_cap"` never sees a wide ring: a 10mm badge border trips the cheap `broad_fill_pregate` and never reaches that branch — so the single most common contour-fill shape in real artwork was silently excluded. | A synthetic 10mm ring came back TATAMI. | Test the SHAPE: `_band_ratio = 2·peak_dist / √area` |
| 3 | **Row pitch had no quantisation margin.** Contour rows are boundaries of `dist >= level` on a pixel grid, so each sits within ±0.5px of its true curve and two neighbours can land a full pixel further apart than nominal. | Fixture 03 scored 98.4 and 07 98.0 against 99.4 / 98.9 for the straight fills they replaced. | One pixel tighter. Both reach 99.4 / 99.0. |

Mistake 3 is the instructive one: multipliers of **0.9, 0.8 and 0.7 all produced
byte-identical output**, because they round to the same integer pixel. That is
the tell that the defect was quantisation and not density — a density
explanation would have shown a gradient.

### The trigger, and why the threshold is not where the shapes alone put it

`_band_ratio = 2 · peak_distance / √area` — thickness relative to extent.

| Shape | Ratio | | Shape | Ratio |
|---|---|---|---|---|
| narrow ring | 0.154 | | disc + pinhole | 0.505 |
| letter-O bowl | 0.269 | | solid star | 0.731 |
| wide ring | 0.276 | | disc | 1.111 |
| square frame | 0.303 | | | |
| very wide ring | 0.405 | | | |

The shape survey alone would put the line near 0.45. **The corpus puts it at
0.30.** Measuring the regions that actually reach the branch: the two that gain
are at 0.151 and 0.237; the three at 0.334, 0.430 and 0.439 all lose — together
costing 0.11 interior for **+9.6 % stitches**, because a region that chunky has
enough medial-axis branching for rows to crease even though it still has a hole.
The survey says where a band stops being a band; the corpus says where contouring
stops paying, and that is the tighter of the two.

`rebuild_design` gained a `CONTOUR_FILL` branch. Without it, editing any
parameter would have silently converted the rows back to straight ones at
whatever angle the object happened to carry — a test pins that.

---

## 3. Cumulative, Part 23 → Part 24b

| | Part 23 | Part 24b |
|---|---|---|
| Distinct fill angles | 1 | **15** |
| Underlay types generated | 2 of 6 | **3 of 6** |
| Fill behaviours | 1 (straight, one angle) | **3** (angled, edge-avoiding, contour) |
| Mean interior | 98.06 | **98.62** |
| Mean edge band | 97.32 | **97.62** |
| Mean spill | 12.19 | 12.22 |
| Floor / over-limit / density flags | 0 / 0 / 0 | **0 / 0 / 0** |
| Stitches | 41,126 | 45,589 (+10.85 %) |
| Tests | 678 | **698** |

Every fixture improved or held on every coverage measure.

## 4. Still open

* `CONTOUR` underlay — no generator
* Radial, spiral and motif fills — absent
* An open arc (a "C") would contour well but has no hole, so it is excluded. The
  hole requirement is the conservative call, not the complete one.
* `DOUBLE_ZIGZAG` still unreachable on the corpus, and §1 explains why raising
  the cap that would unlock it is not a small change
* A3 photo digitizing, A4 lettering engine — untouched
* +10.85 % stitches cumulative, all of it underlay and contour density
