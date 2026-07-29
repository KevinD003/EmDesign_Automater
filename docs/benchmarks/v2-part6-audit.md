# v2 Part 6 Audit — penetration floor enforced

**Date:** 2026-07-29 · **Tag:** `v2-part6` · graded against [`v2-part5`](./v2-part5-summary.json)
**Grid:** [`v2-part6-grid.png`](./v2-part6-grid.png) · **Per-fixture:** [`v2-part6/`](./v2-part6/)

Part 5 built the penetration-density metric, measured the damage, and deliberately left enforcement
off so the decision could be taken on its own evidence. This is that decision, taken.

**Enforcement is now ON.** Same-side penetration violations across the corpus: **3,235 → 3**.

**§4 is the finding worth arguing with, and it is not flattering.**

---

## 1. What was wrong, restated from measurement

Every satin fixture in the corpus was violating a 0.30mm same-side floor on 8–24% of its
penetrations, with hundreds landing at *exactly* 0.000mm — the needle entering the same hole twice.
Two producers: Part 4's cap handling (duplicate columns past a terminal) and concave-side crowding on
curves.

## 2. Result

| Fixture | below floor | min penetration | over 12.7mm |
|---|---|---|---|
| 02 logo_fine_text | 179 → **0** | 0.000 → **0.301mm** | 0 |
| 03 gradient_soft | 253 → **0** | 0.000 → **0.300mm** | 0 |
| 04 thin_line_outline | 8 → **0** | 0.000 → **0.315mm** | 0 |
| 05 wordmark_caps | 371 → **0** | 0.000 → **0.301mm** | 0 |
| 06 wordmark_script | 298 → **0** | 0.000 → **0.300mm** | 0 |
| 07 circular_badge | 938 → **3** | 0.000 → 0.000mm | 0 |
| 08 mascot_detail | 1,130 → **0** | 0.000 → **0.300mm** | 0 |
| 10 low_contrast | 58 → **0** | 0.000 → **0.302mm** | 0 |
| **corpus** | **3,235 → 3** | | **0** |

**The curvature probe**, which isolates the mechanism (rings have no terminals):

| R | min penetration | below floor | interior | edge band |
|---|---|---|---|---|
| 8.0 w | 0.000 → **0.301mm** | 79 → **0** | 100.0 → 99.8 | 100.0 → 98.8 |
| 4.0 w | 0.000 → **0.300mm** | 82 → **0** | 100.0 → 98.5 | 100.0 → 94.8 |
| 2.0 w | 0.000 → **0.303mm** | 77 → **0** | 100.0 → 95.5 | 99.9 → 87.5 |
| 1.25 w | 0.000 → **0.300mm** | 62 → **0** | 100.0 → 71.5 | 99.6 → 53.7 |

**Nothing else moved.** `stitch_types` and all 96 per-object classification verdicts are identical to
v2-part5; so are `color_count`, `segmentation_method` and `filled_area_mm2` on all ten. Jumps
2,046 → 2,045. Zero stitches over the machine limit.

## 3. Choosing the floor value, and the enforcement rule

**Sweep of the floor** across the satin corpus (violations always counted against a fixed 0.30mm
reference so the rows compare):

| floor | violations vs 0.30mm | mean interior | mean edge band | stitches |
|---|---|---|---|---|
| off | 3,235 | 98.86 | 97.73 | 31,121 |
| 0.05mm | 2,157 | 97.79 | 96.72 | 28,815 |
| 0.10mm | 2,002 | 97.13 | 96.21 | 28,523 |
| 0.15mm | 1,848 | 96.79 | 95.80 | 28,251 |
| 0.20mm | 1,567 | 96.51 | 95.40 | 27,836 |
| 0.25mm | 1,065 | 96.16 | 94.85 | 27,321 |
| **0.30mm (shipped)** | **3** | **95.84** | **94.28** | **26,478** |

**There is no knee.** Coverage falls smoothly, roughly 0.5 points of interior per 0.05mm of floor.
That is worth stating because the sweep was run hoping to find a cheap value and did not: even
removing only the exact duplicates (floor 0.05mm) costs a full point of interior, because a duplicate
column still lays a full crossing of thread — it is wasteful and unsafe, but it is not free to remove.

The value therefore rests on the safety argument, not on the coverage curve. **0.30mm is asserted
from general embroidery practice and is still not measured on fabric** — Part 5 §8.2 flagged that and
it remains true.

**Enforcement rule: drop the violating column.** Two cleverer strategies were implemented and
measured first, because deleting a whole crossing to fix one boundary looks wasteful:

| strategy | residual violations | mean interior | mean edge band |
|---|---|---|---|
| **drop the column (shipped)** | **3** | 95.84 | 94.28 |
| slide the end along its boundary | 245 | 96.60 | 95.33 |
| retract the end along its column | 44 | 96.61 | 95.34 |

Both buy about half a point of coverage and give up the guarantee, which is the whole point of a
safety floor. They fail for the same reason in two forms: **moving a penetration instead of removing
it only relocates the crowding.** Sliding forward shortens the gap to whatever comes next. Retraction
shortens the *column*, and a column under the 0.5mm minimum stitch length has a point removed by
`_coalesce_short` further down the pipeline, which breaks the strict A-B-A-B alternation and creates
fresh same-side adjacencies. A strict second pass rescues neither (measured 59 and 45) because by
then the damage is downstream. Both implementations were deleted rather than left behind a flag.

## 4. The cost, including a visible regression

| Fixture | interior | edge band | spill | stitches |
|---|---|---|---|---|
| 01 (control) | 98.7 → 98.7 | 94.6 → 94.6 | 2.1 → 2.1 | 1,632 → 1,632 |
| 02 | 99.0 → 99.0 | 97.3 → 97.1 | 3.7 → 3.7 | 3,963 → 3,741 |
| 03 | 98.6 → 98.0 | 97.2 → 95.2 | 8.0 → 7.9 | 3,616 → 3,380 |
| 04 | — | 99.9 → 99.9 | 47.3 → 47.2 | 1,886 → 1,860 |
| **05** | 99.8 → **89.3** | 98.3 → **88.5** | 12.2 → 11.7 | 1,962 → 1,490 |
| **06** | 100.0 → **94.5** | 99.8 → **90.5** | 23.0 → 22.0 | 1,691 → 1,280 |
| 07 | 98.2 → 97.5 | 96.9 → 95.4 | 5.0 → 4.9 | 9,165 → 7,752 |
| **08** | 97.8 → **94.1** | 97.2 → **93.4** | 4.5 → 4.3 | 6,389 → 4,600 |
| 09 (control) | 99.0 → 99.0 | 93.3 → 93.3 | 3.9 → 3.9 | 1,006 → 1,006 |
| 10 | 98.6 → 98.5 | 95.2 → 94.2 | 3.0 → 3.0 | 2,449 → 2,375 |

Corpus stitches **33,759 → 29,116 (−13.8%)**.

**This is visible, not just numeric.** Fixture 05's wordmark now shows gaps at the `M` and `U`
junctions where it did not in Part 5. Compare
[`v2-part5/05_wordmark_caps-output.png`](./v2-part5/05_wordmark_caps-output.png) with
[`v2-part6/05_wordmark_caps-output.png`](./v2-part6/05_wordmark_caps-output.png).

**The honest reading, which is worse for the earlier parts than for this one.** The loss is
concentrated at junctions (05, 06, 08 are the junction-heavy fixtures; the ring probe loses almost
nothing above `R = 4w`). At a junction one boundary arc genuinely stalls, because the nearest-branch
partition hands a branch a fillet that doubles back — the weakness Part 4 §9.3 named as a Voronoi
split and left standing. The columns generated there were already wrong; they overlapped heavily and
their surplus thread was painting over the gap. **The floor did not create the junction hole. It
removed the overdraw that was hiding it**, which is also why the coverage numbers fall so much
further at junctions than the probe's curvature-only case predicts.

That is a defensible thing for a safety floor to do, but it means **Part 4 and Part 5's junction
coverage numbers were flattered by duplicate stitching**, and the real fix is the junction-aware
boundary partition, not the floor. That is the next part, and it should recover most of 05/06/08.

## 5. Three residual violations on fixture 07

Attributed, not waved at: **2 are in the running-stitch underlay** (the medial-axis underlay can
double back sharply enough to put two penetrations 0.18mm apart; the floor governs satin columns
only) and **1 is in a 0.63mm-wide column**, most likely `_coalesce_short` removing a point after
column generation and breaking the alternation. Unchanged from Part 5 §4 and still not chased to
certainty — 0.01% of the corpus.

## 6. Verification

```
pytest — WITH rembg:     108 passed, 1 warning in 22.97s
pytest — WITHOUT rembg:  108 passed, 1 warning in  6.75s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

One test added and two rewritten: the shipped default must honour the floor
(`test_floor_is_enforced_by_default`), enforcement must never flip a classification verdict
(`test_enforcement_does_not_change_which_objects_are_satin`), and an autouse fixture now restores the
module-level floor after every test — **added because the first version of the default test failed**:
an earlier test disabled the floor in a `finally` and leaked that state into the rest of the session.

**Standards, read from [`docs/ENGINEERING_STANDARDS.md`](../ENGINEERING_STANDARDS.md):**

| §1 Coverage (floor 80%) | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 965 | 52 | **95%** |
| `scripts/measure_stitch_quality.py` | 166 | 8 | **95%** |
| `scripts/run_quality_bench.py` | 248 | 87 | **65%** ⚠ |

`run_quality_bench.py` remains under the floor at its pre-existing 65% (CLI driver and grid renderer);
unchanged by this part.

**§3 Size.** No function added or edited by this part exceeds 50 lines (`_main` reached 51 and
`_apply_floor` was split out of it). Pre-existing over-limit functions, named as the standard
requires: `digitize_image` 336, `rebuild_design` 129, `_skeleton_branches` 76, `_skeleton_satin` 54.
`digitizer.py` at 1,877 lines remains the standing documented exception.

**§4 Security.** Secrets scan over the diff — clean. No new constants; `MIN_PENETRATION_MM` was
already named and commented in Part 5.

**§1 Lint.** `ruff check` over every touched file: **15 findings, exactly the pre-existing count.**

**One bug fixed in the measurement CLI.** `--floor-mm` defaulted to `None` and *called*
`set_penetration_floor(None)`, which meant "report only" in Part 5 but silently **disabled
enforcement** once Part 6 turned the floor on. Absent the flag the shipped default now stands, and
`--no-floor` is the explicit way to reproduce the before/after. This was caught because a
`--fixture 05` run reported the floor-off numbers.

## 7. What to attack

1. §4 — the floor exposed junction geometry that was being hidden by overdraw. Does that mean Parts 4
   and 5 over-reported coverage at junctions, and should their tables carry a note?
2. `MIN_PENETRATION_MM = 0.30` is still asserted, not measured on fabric, and §3 shows the coverage
   cost is linear in it. What is the right number, and should it vary with `fabric_type`?
3. Shipping a visibly worse wordmark to buy a safety property the user cannot see is a product
   judgement, not an engineering one. Is it the right call before the junction fix lands?
4. Drop was chosen over retraction on the strength of the guarantee (3 vs 44 violations). Is 44
   violations in ~27,000 penetrations actually unsafe, or is that over-caution paid for in coverage?
5. The three residual violations (§5) include a mechanism — the underlay doubling back — that no
   floor currently governs. When does that get fixed?
