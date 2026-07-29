# v2 Part 7 Audit — junction-aware boundary partition

**Date:** 2026-07-29 · **Tag:** `v2-part7` · graded against [`v2-part6`](./v2-part6-summary.json)
**Grid:** [`v2-part7-grid.png`](./v2-part7-grid.png) · **Per-fixture:** [`v2-part7/`](./v2-part7/)

Part 6 §4 named the mechanism this part was to fix: a Voronoi-style boundary partition stalling at
asymmetric junctions, exposed once the penetration floor stopped the overdraw from hiding it.

**The named mechanism is real, is now fixed, and was not the main cause of the gaps.** That finding
is §3, and it is the one worth arguing with. The penetration floor was left ON throughout.

---

## 1. The adversarial case, built first

`tests/fixtures/junction_probe/` — a thick stem with a thinner stroke leaving it, varying the two
things a Voronoi partition is sensitive to: thickness ratio (6:1, 2.4:1, 1:1) and meeting angle
(30°, 60°). Both strokes are 3.75mm and 0.63mm, inside the satin cap, so the junction actually
reaches the satin path. Kept out of the ten-fixture corpus.

**Before — the stall, drawn.** Each boundary pixel coloured by the branch it is assigned to, axes
drawn dark. [`v2-part7-partition-before.png`](./v2-part7-partition-before.png):

The **red** hairline branch owns not only its own diagonal boundary but a **tall vertical run of the
STEM's boundary on both sides**. That is the defect. The worked numbers:

```
stem half-width        = 12px      hairline half-width = 2.8px
a stem boundary pixel at the junction height is
    12.0px from the stem axis           -> raw nearest: 12.0
    ~12.4px from the hairline axis      -> raw nearest: 12.4   << almost a tie
```

A tie at 12.0 vs 12.4 is decided by a pixel of noise, so a long run of stem boundary lands on the
hairline. Those pixels then project onto the hairline's *short* axis, where they all collapse to
nearly one arc-length station — the stall.

**After** — [`v2-part7-partition-after.png`](./v2-part7-partition-after.png): the stem's boundary is
owned entirely by the stem branches; the hairline owns only its own.

## 2. The fix: subtract the local medial radius

The medial axis already defines the right answer, and the previous rule was throwing it away. A
boundary point `p` lies at **exactly** the local radius `r(a)` from the axis point `a` whose maximal
inscribed disc touches it, and strictly further from every other axis point. So instead of
minimising `|p − a|`, minimise

```
|p − a| − r(a)
```

which is ~0 for the branch `p` actually bounds and positive for any other, **at any thickness
ratio**. Re-running the worked example:

```
stem boundary pixel:   stem axis  12.0 − 12.0 = 0.0     hairline axis  12.4 − 2.8 = 9.6   -> stem  ✓
hairline boundary px:  hairline    2.8 −  2.8 = 0.0     stem axis      13.5 − 12.0 = 1.5  -> hairline ✓
```

Pinned by `test_thick_stem_boundary_is_not_handed_to_a_hairline_branch`: on the probe shape the
hairline owns **12** stray stem-boundary points under the old rule and **1** under the new one.

## 3. The finding worth arguing with: that was not what was costing the coverage

Fixing the partition did **not** recover fixtures 05/06/08. Measured on its own it moved 05 from
89.3 to 88.2 interior — slightly *worse*. So I stopped and painted the misses instead of theorising
further, the way Part 4 §4 and Part 6 §4 both had to.

[`v2-part7-uncovered-05-before.png`](./v2-part7-uncovered-05-before.png) (red = missed interior,
orange = missed edge band) shows two distinct shapes of loss:

1. **Fans radiating from a point** at the `M` apexes, the `U` bowl join and the `T` crossing.
2. **Flat rectangular blocks** at the very top of each `M`/`W` apex.

Then the decisive measurement: **`_enforce_floor` was dropping only 35 of 632 columns on fixture 05
(5.5%).** The wedges were therefore not dropped columns — they were columns **never generated**.

The cause is the *other* floor enforcement point. Part 5 gated the pacing loop on
`min(moved_a, moved_b) >= floor_px`, requiring the **slow** side to advance a full floor before a
column is emitted. On a curve that is right. At a junction, where one arc is stalled, the minimum
never reaches the floor — so the branch emits **no columns at all** across that stretch. Part 6 §4's
story ("the floor removed the overdraw that was hiding the hole") was half right: the floor did
remove the overdraw, but it also stopped generation outright, and that second effect was the larger
one.

**Fix:** the pacing loop now paces on the fast side only (`max(moved) >= pitch`). The safety
guarantee is untouched — `_enforce_floor` still applies the 0.30mm floor to the *final* endpoints,
which is what the metric measures, and §5 shows the violation count is unchanged.

## 4. Result — partial recovery, honestly mixed

| Fixture | interior p6 → **p7** | edge band p6 → **p7** | stitches |
|---|---|---|---|
| 01 (control) | 98.7 → **98.7** | 94.6 → **94.6** | 1,632 → 1,632 |
| 02 | 99.0 → **99.0** | 97.1 → **97.1** | 3,741 → 3,682 |
| 03 | 98.0 → 97.9 | 95.2 → **92.5** ⚠ | 3,380 → 3,202 |
| 04 | — | 99.9 → **99.9** | 1,860 → 1,861 |
| **05** | 89.3 → **90.1** | 88.5 → 87.5 | 1,490 → 1,320 |
| **06** | 94.5 → **96.7** | 90.5 → 90.1 | 1,280 → 1,093 |
| 07 | 97.5 → **97.9** | 95.4 → 95.3 | 7,752 → 7,605 |
| **08** | 94.1 → **96.9** | 93.4 → **91.5** ⚠ | 4,600 → 4,602 |
| 09 (control) | 99.0 → **99.0** | 93.3 → **93.3** | 1,006 → 1,006 |
| 10 | 98.5 → **98.5** | 94.2 → **94.4** | 2,375 → 2,371 |

**Are the M/U junction gaps recovered? Partially.** Interior coverage on the junction-heavy fixtures
recovers meaningfully — **08 +2.8, 06 +2.2, 05 +0.8** — and
[`v2-part7-uncovered-05-after.png`](./v2-part7-uncovered-05-after.png) shows the *fans* around the
`M` apexes and the `U` join substantially thinned. Total missed interior pixels on fixture 05:
**6,402 → 5,372 (−16%)**.

**What is NOT recovered: the flat blocks at the apexes.** They are unchanged, and they are now the
dominant remaining loss. They are not a partition problem at all — at an `M` apex the medial axis
*terminates inside the shape*, and the triangular region above that terminal is not reachable by any
branch's columns at any assignment. Neither the partition fix nor the pacing fix can close it; it
needs a junction-region treatment (a mitre, or a tatami patch for the unreachable remainder), which
is a different mechanism and the honest next step.

**And a real regression: edge band.** Fixture 03 loses 2.7 points and 08 loses 1.9. Pacing on the
fast side alone puts more columns on the concave boundary, more of which `_enforce_floor` then drops,
so the concave edge ends up less well served. The curvature probe shows the same trade at every
radius (r8w edge band 98.8 → 94.1, r4w 94.8 → 90.4, r2w 87.5 → 81.7) with **interior and violations
unchanged**. So this part trades edge band for interior. Both numbers are above; I am not averaging
them.

**A variant measured and rejected:** restricting the dropped gate to closed loops, to spare the
rings. It changed nothing — after `_extend_branch_ends` pushes samples past the skeleton, almost no
annulus still closes within `CLOSED_LOOP_TOL_PX`, so the condition was false for both the probe rings
and fixture 03. Removed rather than left as a no-op.

**Ablation of the three changes** (all with the floor on, means over the 8 satin fixtures):

| radius-normalised | free-end caps | mean interior | mean edge band | violations |
|---|---|---|---|---|
| no | no | 96.39 | 93.81 | 4 |
| no | yes | 96.39 | 93.78 | 4 |
| yes | no | 96.70 | 93.49 | 3 |
| **yes** | **yes (shipped)** | **96.71** | **93.54** | **3** |

The free-end cap distinction (a branch end that is an interior junction gets no cap padding, because
the outline does not converge there) measures at **+0.01 interior / +0.05 edge band — within noise.**
It is kept because it is the geometrically correct treatment and costs one small function, but a
reviewer may fairly call it unearned, and the numbers to make that case are right here.

## 5. Constraints held

```
classification (stitch_types + all 96 per-object verdicts) identical to v2-part6:  True
penetration violations:  v2-part6  3  ->  v2-part7  3
stitches over the 12.7mm machine limit:                                            0
colour_count / segmentation_method / filled_area_mm2 identical on all ten:         True
```

The 3 residual violations are the same ones Part 5 attributed (2 in the running-stitch underlay,
which no floor governs; 1 in a 0.63mm column) — redistributed between fixtures 07 and 08 but
unchanged in count. **The floor was on for every measurement in this document**, including the
before/after crops.

**Junction probe, before → after** (floor on throughout):

| case | interior | edge band | violations |
|---|---|---|---|
| hairline_30deg | 99.2 → **99.7** | 98.7 → 98.1 | 1 → 1 |
| hairline_60deg | 99.7 → **99.7** | 98.3 → 97.8 | 0 → 0 |
| medium_30deg | 99.6 → 99.5 | 99.4 → 98.3 | 0 → 0 |
| equal_30deg (control) | 98.3 → **98.7** | 98.0 → 94.6 | 0 → 0 |

The probe's coverage barely moves, which is itself informative: its arms are long and clean, so the
junction is a small fraction of the area. **The probe proves the mechanism; it does not reproduce the
corpus's cost.** That is why §3 had to be settled by painting fixture 05 rather than by the probe.

## 6. Verification

```
pytest — WITH rembg:     110 passed, 1 warning in 25.82s
pytest — WITHOUT rembg:  110 passed, 1 warning in  8.60s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Two tests added: the adversarial partition assertion (§2) and an end-to-end check that the junction
shape still classifies as satin and honours the floor.

**Standards, read from [`docs/ENGINEERING_STANDARDS.md`](../ENGINEERING_STANDARDS.md):**

| §1 Coverage (floor 80%) | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 987 | 56 | **94%** |
| `scripts/measure_stitch_quality.py` | 168 | 8 | **95%** |
| `scripts/run_quality_bench.py` | 248 | 87 | **65%** ⚠ pre-existing, untouched here |

**§3 Size.** The one function added, `_free_ends`, is 25 lines. Pre-existing over-limit functions,
named as the standard requires: `digitize_image` 336, `rebuild_design` 129, `_skeleton_branches` 76,
`_skeleton_satin` 55. `digitizer.py` at 1,951 lines remains the standing documented exception, and it
grew by 74 lines this part.

**§4 Security.** Secrets scan clean. No new constants.

**§1 Lint.** `ruff check` over every touched file: **14 findings, all pre-existing**; three were
introduced during the work and fixed before commit.

## 7. What to attack

1. §3 — the brief named the wrong dominant mechanism, and so did Part 6 §4. Two audits in a row have
   attributed a coverage loss to the wrong cause and only got it right by painting the pixels. Should
   painting be a required step before any cause is asserted?
2. This part trades edge band for interior (03 −2.7, 08 −1.9; ring probe −3 to −6). Is that the right
   direction, given Parts 2–4 spent three parts buying edge band?
3. The apex blocks (§4) need a junction-region treatment. Mitre, or tatami patch for the unreachable
   remainder — and does a tatami patch belong inside a satin object?
4. The free-end cap distinction is within noise (§4 ablation). Keep or cut?
5. The probe proves the mechanism but not its cost (§5). What would a probe that reproduces the
   corpus's junction cost actually look like — short arms, sharp apexes, letter-like?
