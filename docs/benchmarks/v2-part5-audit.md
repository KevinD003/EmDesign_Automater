# v2 Part 5 Audit — penetration-density safety metric, committed methodology

**Date:** 2026-07-29 · **Tag:** `v2-part5` · graded against [`v2-part4`](./v2-part4-summary.json)
**Grid:** [`v2-part5-grid.png`](./v2-part5-grid.png) · **Per-fixture:** [`v2-part5/`](./v2-part5/)

Answers [`v2-part4-audit.md`](./v2-part4-audit.md) §8 ("nothing in the current metric set detects
that") and §11 item 2 ("at what curvature does it become fabric damage, and should there be a hard
floor?") — **with data, not argument**.

**The shipped pipeline is unchanged.** All ten fixtures keep byte-identical `stitch_types`,
`stitch_count` and `jump_count` — verified in §5.

---

## 1. The metric

Boundary-paced satin (Part 4) sets its pitch by the **faster** of a stroke's two boundaries. The
slower one — the concave side of a curve — therefore advances *less* than a pitch between columns,
packing its needle penetrations together. Packed tightly enough, the needle stops stitching on the
fabric and starts perforating a line through it.

**Definition.** A satin path alternates sides (`A0 B0 A1 B1 …`), so points `i-1` and `i+1` are the
same-side pair, and their distance is that boundary's local penetration spacing. The triple is
recognised because it **zigzags** — the same-side gap is shorter than either crossing. A
running-stitch underlay or a tatami row advances *along* a line and fails that test, so neither can
pollute the number.

Taken from the **stitch stream only** — no digitizer internal, no preview bitmap. What the machine
sews is the stream, so that is what gets graded, and the metric stays valid regardless of how a
future part generates columns.

Reported per satin object and per design: `min_mm`, `p05_mm`, `median_mm`, and the count below the
floor. `min_spacing_mm` is the safety number.

## 2. The corpus, measured

`scripts/measure_stitch_quality.py`, nominal pitch 0.4mm, floor 0.30mm:

| Fixture | interior | edge band | spill | **min penetration** | **below floor** |
|---|---|---|---|---|---|
| 01 flat_2color_logo | 98.7 | 94.6 | 2.1 | — (no satin) | — |
| 02 logo_fine_text | 99.0 | 97.3 | 3.7 | **0.000mm** | 179 / 2,449 |
| 03 gradient_soft | 98.6 | 97.2 | 8.0 | **0.000mm** | 253 |
| 04 thin_line_outline | — | 99.9 | 47.3 | **0.000mm** | 8 / 1,306 |
| 05 wordmark_caps | 99.8 | 98.3 | 12.2 | **0.000mm** | 371 / 1,793 |
| 06 wordmark_script | 100.0 | 99.8 | 23.0 | **0.000mm** | 298 |
| 07 circular_badge | 98.2 | 96.9 | 5.0 | **0.000mm** | 938 / 4,776 |
| 08 mascot_detail | 97.8 | 97.2 | 4.5 | **0.000mm** | 1,130 / 4,704 |
| 09 nonuniform_bg | 99.0 | 93.3 | 3.9 | — (no satin) | — |
| 10 low_contrast | 98.6 | 95.2 | 3.0 | **0.000mm** | 58 |

Part 4 §8 guessed "no fixture in the corpus is tight enough to show it." **That was wrong.**
Between 8% and 24% of same-side penetrations on the satin fixtures sit under 0.30mm, and hundreds
land at *exactly* 0.000mm — the needle entering the same hole twice.

Two distinct producers, separated by measuring how far into a run the violation sits:

| Fixture | terminal triples under floor | mid-run triples under floor |
|---|---|---|
| 05 | 43 / 147 (**29.3%**) | 328 / 1,646 (19.9%) |
| 07 | 295 / 790 (**37.3%**) | 643 / 3,986 (16.1%) |
| 08 | 313 / 703 (**44.5%**) | 817 / 4,001 (20.4%) |

1. **Stroke terminals.** Part 4's cap handling runs the column grid past the terminal, where both
   boundary arcs clamp to their own end point — so those columns are duplicates. That is the source
   of the exact zeros, and it is a defect Part 4 introduced and did not notice.
2. **Concave-side curvature** — the mechanism Part 4 predicted, at 16–20% of mid-run penetrations.

## 3. The curvature probe — at what curvature does it bite

`tests/fixtures/curvature_probe/`, kept **out** of the bench corpus so "the corpus" keeps meaning
the same ten fixtures.

**Why rings, not hairpins.** The first probe used U-turns of decreasing radius. It did not work:
every open stroke has two terminals, and by §2 those pin the minimum near zero at *every* radius, so
the curvature signal was buried. A ring has **no terminals** — every penetration is a bend
penetration. Recording the dead end because the second version only looks obvious afterwards.

Constant 2.5mm stroke, centreline radius `R` in stroke widths `w`. Pacing by the outer boundary
predicts an inner-side spacing of `pitch x (R - w/2) / (R + w/2)`:

| R | predicted inner spacing | **measured p05** | below floor | interior | edge band |
|---|---|---|---|---|---|
| 8.0 w | 0.353mm | **0.264mm** | 79 / 764 | 100.0 | 100.0 |
| 4.0 w | 0.311mm | **0.185mm** | 82 / 386 | 100.0 | 100.0 |
| 2.0 w | 0.240mm | **0.093mm** | 77 / 192 | 100.0 | 99.9 |
| 1.25 w | 0.171mm | **0.009mm** | 62 / 126 | 100.0 | 99.6 |

Monotone in curvature, as predicted, and **consistently tighter than the closed form** — the
inner boundary of a small ring is a coarse pixel circle, so the extreme-point-per-station rule picks
points that crowd harder than an ideal arc would.

**Answer to Part 4 §11.2:** the concave side is already under a 0.30mm floor at `R = 8w`, a curve
most digitizers would call gentle. There is no safe radius in the range that matters — it is not a
tight-curve edge case, it is the normal case.

## 4. The floor: implemented, measured, and NOT enabled by default

`set_penetration_floor(mm)` gates two enforcement points. Pacing skips a column unless **both**
boundaries have advanced at least the floor; then, after clamping and pull compensation have moved
the endpoints, `_enforce_floor` drops any column still violating. The second pass is necessary —
pull comp moves each end outward from the axis *after* the pacing decision, which on a ring's
concave side pulls it to a smaller radius and shrinks the spacing again. Enforcing only at pacing
fixed 86–91% of violations; enforcing on the final endpoints fixes them all.

**Probe, before → after:**

| R | min penetration | below floor | interior | edge band |
|---|---|---|---|---|
| 8.0 w | 0.000 → **0.301mm** | 79 → **0** | 100.0 → 99.8 | 100.0 → **98.8** |
| 4.0 w | 0.000 → **0.300mm** | 82 → **0** | 100.0 → 98.5 | 100.0 → **94.8** |
| 2.0 w | 0.000 → **0.303mm** | 77 → **0** | 100.0 → 95.5 | 99.9 → **87.5** |
| 1.25 w | 0.000 → **0.300mm** | 62 → **0** | 100.0 → 71.5 | 99.6 → **53.7** |

**Corpus, floor enforced:**

| Fixture | below floor | interior | edge band |
|---|---|---|---|
| 02 | 179 → **0** | 99.0 → 99.0 | 97.3 → 97.1 |
| 03 | 253 → **0** | 98.6 → 98.0 | 97.2 → 95.2 |
| 04 | 8 → **0** | — | 99.9 → 99.9 |
| 05 | 371 → **0** | 99.8 → **89.3** | 98.3 → **88.5** |
| 06 | 298 → **0** | 100.0 → 94.5 | 99.8 → 90.5 |
| 07 | 938 → **3** | 98.2 → 97.5 | 96.9 → 95.4 |
| 08 | 1,130 → **0** | 97.8 → 94.1 | 97.2 → 93.4 |
| 10 | 58 → **0** | 98.6 → 98.5 | 95.2 → 94.2 |

The trade is sharp and radius-dependent: **nearly free down to `R = 4w`, about 5 points of edge band
at `R = 2w`, and untenable at `R = 1.25w`** where the geometry is over-constrained — you cannot both
cover an outer boundary at 0.4mm pitch and keep the inner one above 0.3mm when the radius ratio is
0.43. On the corpus it costs fixture 05 ten points of interior and edge band, undoing most of
Part 4's gain there.

### Why it ships OFF

The brief for this part is explicit that it "should not change any fixture's `stitch_types`,
`stitch_count`, or `jump_count`", and enabling the floor changes the stitch count of every satin
object. Those two instructions cannot both be satisfied with the floor on.

Resolved by shipping the floor **implemented, tested and measured**, with enforcement off
(`_PENETRATION_FLOOR_MM = None`) — so this part remains the measurement part it was scoped as, and
the decision to accept a 5–10 point coverage cost for production safety is surfaced with numbers
rather than taken silently inside a metrics change. **Recommendation: enable it in its own part**,
with a coverage re-grade, and consider a radius-aware floor (full floor above `R = 4w`, relaxed
below) rather than the flat one measured here.

### Three residual violations, attributed

Fixture 07 keeps 3 of 4,776 with the floor on. Attributed rather than waved at:

- **2 are in the running-stitch UNDERLAY**, not in satin columns — the medial-axis underlay can
  double back sharply enough to put two penetrations 0.18mm apart. The floor governs satin columns
  only. This is a **second producer of tight penetrations the metric found and the floor does not
  address**; it belongs to whichever part takes on the underlay.
- **1 is in a 0.63mm-wide satin column.** The likely cause is `_coalesce_short`, which runs *after*
  column generation and removes penetrations under 0.5mm of travel; on a stroke narrower than that
  it can remove one and change which points end up adjacent. Not chased to certainty — it is 0.02%
  of that fixture — and flagged as unproven rather than asserted.

## 5. The pipeline is unchanged — verified

```
v2-part4 -> v2-part5
  01_flat_2color_logo        {'TATAMI': 2}              st 1,632->1,632  jumps  63->63   IDENTICAL
  02_logo_fine_text_3color   {'TATAMI': 4, 'SATIN': 12} st 3,963->3,963  jumps 188->188  IDENTICAL
  03_gradient_soft_subject   {'SATIN': 2, 'TATAMI': 2}  st 3,616->3,616  jumps 120->120  IDENTICAL
  04_thin_line_outline       {'SATIN': 11}              st 1,886->1,886  jumps  29->29   IDENTICAL
  05_wordmark_caps           {'SATIN': 6}               st 1,962->1,962  jumps  44->44   IDENTICAL
  06_wordmark_script         {'SATIN': 12}              st 1,691->1,691  jumps  54->54   IDENTICAL
  07_circular_badge          {'SATIN': 14, 'TATAMI': 4} st 9,165->9,165  jumps 979->979  IDENTICAL
  08_mascot_detail           {'SATIN': 12, 'TATAMI': 9} st 6,389->6,389  jumps 387->387  IDENTICAL
  09_nonuniform_background   {'TATAMI': 2}              st 1,006->1,006  jumps  41->41   IDENTICAL
  10_low_contrast_subject    {'SATIN': 2, 'TATAMI': 2}  st 2,449->2,449  jumps 141->141  IDENTICAL
  => all 10 identical on stitch_types + stitch_count + jump_count: True
  => every pre-existing metric field identical (SHA-256 of the record, runtime and
     the two NEW fields stripped):                                            True
```

## 6. The grading methodology is now committed

Interior / edge-band / spill has been described in prose in every audit since Part 2.5 and
reconstructed from that description each time. It is now `scripts/measure_stitch_quality.py`, and
the harness imports it rather than carrying a second copy that could drift.

**It reproduces the historical numbers exactly** — Part 4 §6's table, regenerated by the committed
script:

```
02 99.0 / 97.3 /  3.7      05 99.8 / 98.3 / 12.2      08 97.8 / 97.2 /  4.5
03 98.6 / 97.2 /  8.0      06 100.0 / 99.8 / 23.0     10 98.6 / 95.2 /  3.0
04    — / 99.9 / 47.3      07 98.2 / 96.9 /  5.0
```

**One deliberate wart, kept for that reason.** `_poly` truncates rather than rounds when rasterising
an outline vertex. Rounding is the more correct rasterisation, and switching moved fixture 07's spill
from 5.0 to 5.1 — enough to make the committed script disagree with the audits it exists to make
reproducible. Truncation kept, with the reason in a comment at the call site.

## 7. Verification

```
pytest — WITH rembg:     107 passed, 1 warning in 24.29s
pytest — WITHOUT rembg:  107 passed, 1 warning in  7.95s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Twelve tests added (95 → 107): the metric equals the pitch on a textbook zigzag; running stitch and
tatami rows produce no false pairs; a jump breaks a run; a synthetic concave arc packs below the
pitch; the floor takes a tight ring from violations to zero; the floor is off by default; coverage
metrics are in range and report `None` interior for a sub-erosion hairline; the CLI runs and writes
JSON; the CLI rejects an unknown fixture; the harness records both new fields.

**Standards compliance, read from [`docs/ENGINEERING_STANDARDS.md`](../ENGINEERING_STANDARDS.md):**

| §1 Coverage (floor 80%) | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 965 | 58 | **94%** |
| `scripts/measure_stitch_quality.py` | 156 | 5 | **97%** |
| `scripts/run_quality_bench.py` | 248 | 87 | **65%** ⚠ |

`run_quality_bench.py` is under the floor at its **pre-existing** 65%; the uncovered block is its CLI
driver and grid renderer (lines 313–417) plus two diagnostic `except` branches. The lines Part 5 adds
to `run_fixture` are covered by `test_bench_records_coverage_and_penetration`. Stated as the standard
requires rather than waived.

**§3 Size.** All 15 functions added or split out this part are ≤50 lines (largest: `_main` 45 after
splitting `_parse_args`/`_print_row`/`_print_detail` out of a 72-line original; `penetration_metrics`
42). New files: `measure_stitch_quality.py` 332 lines, `_generate_probe.py` 63,
`test_stitch_quality_metrics.py` 186 — all under 800. `app/services/digitizer.py` is 1,855 lines and
remains the **standing documented exception** (§3).

**§4 Security.** Secrets scan over the diff — clean. Two new named module constants, both commented:
`MIN_PENETRATION_MM = 0.30`, `ZIGZAG_RATIO = 0.9`. No magic numbers introduced.

**§1 Lint.** `ruff check` over every touched file: **15 findings, exactly the pre-existing count.**
Four introduced during the work were fixed before commit.

**§5 Commits.** Conventional prefixes.

## 8. What to attack

1. §2 shows Part 4's cap handling puts hundreds of penetrations in the *same hole* — worse than the
   curvature problem Part 4 flagged. Should the cap have been fixed here rather than measured?
2. `MIN_PENETRATION_MM = 0.30` is asserted from general embroidery practice, not measured on fabric.
   What is the right number, and does it depend on the fabric parameter the pipeline already takes?
3. The floor costs fixture 05 ten points of interior coverage (§4). Is a radius-aware floor
   principled, or just a way to keep a coverage number?
4. `ZIGZAG_RATIO = 0.9` decides what counts as a satin triple. What geometry does it misclassify?
5. The probe measures rings only, so it isolates curvature by excluding terminals — the very thing
   §2 shows is the bigger producer. Is that the right instrument, or does it flatter the analysis?
