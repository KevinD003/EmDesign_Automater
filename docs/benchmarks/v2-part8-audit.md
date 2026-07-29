# v2 Part 8 Audit — satin mitre at sharp apexes, and a letter-shaped probe

**Date:** 2026-07-29 · **Tag:** `v2-part8` · graded against [`v2-part7`](./v2-part7-summary.json)

> **One mandatory verification item is NOT met: residual penetration-floor violations go 3 → 5.**
> That is §6, stated up front rather than buried. Everything else held.

---

## 1. Part 7 §4's account of the apex was wrong, and the probe proved it

Part 7 §4 asserted: *"at an `M` apex the medial axis terminates inside the shape, and the triangle
above that terminal is not reachable by any branch at any assignment."* Measured on `apex_V`:

```
branches: 3   sample counts: [72, 6, 71]
  branch 1: start (160, 242)  end (160, 229)      <- a 6-sample SPUR into the apex
shape apex at y=245
nearest axis sample to the apex: 3.0px   local radius there: 4.0px
columns whose ends reach within 30px of the apex: 21
```

**The axis reaches to within 3px of the tip**, via a short spur, and 21 columns already reach the
apex region. Nothing is "unreachable". Part 7 asserted a mechanism without painting it — the very
thing Part 7 §7 item 1 then made binding — and it was wrong.

**The real conflict**, from the picture: at a sharp vertex the **outer** arc sweeps right around the
corner and needs a column every 0.4mm to cover it, while every one of those columns wants its
**inner** end on the reflex point. The inner penetrations therefore pile far tighter than the 0.30mm
floor allows, `_enforce_floor` drops those columns, and the outer fan opens into the bare apex block.
The two constraints are in direct conflict — this is the corner form of the `R = 1.25w` case the
curvature probe found in Part 5.

## 2. The letter probe (Part 7 §7 item 5)

`tests/fixtures/letter_probe/` — short arms, sharp apexes, 3.75mm stroke at bench scale, so the apex
is a large share of each shape instead of a rounding error. `apex_M`, `apex_V`, `apex_narrow` (28.9°
vertex) and `apex_U` as the **control** (a bowl, no sharp apex). It reproduces the corpus defect
immediately: red apex blocks at both chevron vertices, clean arms.

Part 7's `junction_probe` did not, and §5 of that audit said so — long clean arms make the junction a
negligible fraction of the area.

## 3. Option (a), the mitre — tried first, as the brief required

A hand digitizer resolves a corner with a **mitre**: the inner ends are laid along the corner's
*bisector* rather than into its point. The medial axis **is** that bisector, and it advances station
to station even where the boundary does not. So where a boundary has stalled, the end is moved onto
the axis point for its own station.

**It did not close cleanly on the first attempt**, and the failure is recorded because the fix is
only obvious afterwards. Firing on any sub-floor step scattered fresh gaps along every straight arm
(interior 96.6 → 97.0 but new dashes everywhere). A corner stalls a boundary for *several consecutive*
columns; a straight stroke throws isolated short steps. Requiring a run of `MITRE_MIN_STALLED = 3`
kept the apex gain and removed the arm damage.

Three further guards were each forced by measurement, not designed in:

| guard | why | measured |
|---|---|---|
| axis must itself advance | past a terminal `mid` is clamped to the axis end, so consecutive stations share one coordinate | removed 0.000mm stamped duplicates |
| mitred column ≥ `MIN_STITCH_MM` | a shorter column loses a point to `_coalesce_short`, breaking A-B-A-B alternation — the identical failure Part 6 measured for retraction | violations 7 → 5 |
| revert anything made worse | `stalled` is computed once and goes stale as points move | kept the guard honest |

## 4. Corpus result

| Fixture | interior p7 → **p8** | edge band p7 → **p8** | spill | stitches |
|---|---|---|---|---|
| 01 (control) | 98.7 → **98.7** | 94.6 → **94.6** | 2.1 → 2.1 | 1,632 → 1,632 |
| 02 | 99.0 → **99.0** | 97.1 → **97.1** | 3.7 → 3.7 | 3,682 → 3,714 |
| 03 | 97.9 → **97.9** | 92.5 → **92.6** | 7.7 → 7.7 | 3,202 → 3,228 |
| 04 | — | 99.9 → **99.9** | 47.1 → 47.1 | 1,861 → 1,861 |
| **05** | 90.1 → **95.3** | 87.5 → **89.5** | 11.4 → 11.1 | 1,320 → 1,492 |
| **06** | 96.7 → **97.7** | 90.1 → **92.3** | 20.7 → 21.0 | 1,093 → 1,219 |
| 07 | 97.9 → **97.9** | 95.3 → **95.5** | 4.8 → 4.8 | 7,605 → 7,804 |
| **08** | 96.9 → 96.7 | 91.5 → **92.3** | 3.9 → 4.0 | 4,602 → 5,004 |
| 09 (control) | 99.0 → **99.0** | 93.3 → **93.3** | 3.9 → 3.9 | 1,006 → 1,006 |
| 10 | 98.5 → **98.6** | 94.4 → **94.4** | 3.0 → 3.0 | 2,371 → 2,389 |

**Precisely which numbers moved** (Part 7's audit was loose about this and the brief called it out):
interior moved on **05 (+5.2), 06 (+1.0), 08 (−0.2), 10 (+0.1)** and is unchanged to one decimal on
01/02/03/07/09. Edge band moved on **05 (+2.0), 06 (+2.2), 07 (+0.2), 08 (+0.8), 03 (+0.1)** and is
unchanged on 01/02/04/09/10. Spill moved on 05 (−0.3), 06 (+0.3), 08 (+0.1) only.

**Apex crops, before/after** (top = v2-part7, bottom = v2-part8; red = missed interior):
[`05`](./v2-part8-apex-05.png) · [`06`](./v2-part8-apex-06.png) · [`08`](./v2-part8-apex-08.png).
The solid red blocks at the `M` apexes are broken up and substantially reduced. **They are not
eliminated** — the apex is partially, not fully, closed.

## 5. Part 7 open question 2, answered: yes, partially

Does closing the apexes recover Part 7's edge-band regression?

| Fixture | p6 (before Part 7) | p7 | **p8** | recovered |
|---|---|---|---|---|
| 03 | 95.2 | 92.5 | **92.6** | **+0.1 of the 2.7 lost** — essentially no |
| 08 | 93.4 | 91.5 | **92.3** | **+0.8 of the 1.9 lost, ~42%** |

So: **08 recovers a meaningful fraction, 03 does not.** That is consistent with the mechanism — 03's
loss came from ring-like concave curvature, which has no apex to mitre, while 08's ears and whiskers
do have sharp joins. Reported either way, as the brief required.

## 6. The mandatory item this part does NOT meet

```
penetration violations:  v2-part7  3  ->  v2-part8  5
```

Attributed: **4 in the running-stitch underlay** (a producer no floor governs, unchanged in kind
since Part 5) and **1 in a satin column**. Worst spacing 0.000mm on fixture 07, which is the
pre-existing underlay case, and 0.252mm on 08.

The mechanism is understood but not eliminated: the mitre shortens a column, and shortened columns
interact with `_coalesce_short` downstream of `_enforce_floor`, which is where the extra violations
appear. The `MIN_STITCH_MM` guard took this from **7 to 5** and cost 2.4 points of interior on
fixture 05 (97.7 → 95.3) — that trade is measured, and a stricter guard would trade more coverage for
the last two.

**I did not get this back to 3, and I am not shipping it silently.** If the reviewer's line is that
the floor may never regress, the revert is one constant (`MITRE_MIN_STALLED = 10**9`) and costs the
whole of §4's gain.

## 7. A case where the mitre measures WORSE

Pinned as a characterisation test rather than tuned away. On a **butt-jointed** V — two separate
strokes meeting with no rounded join — the mitre measures **97.3 → 95.1 interior**, the opposite
direction to the letter probe's joined apexes (`apex_M` 96.6 → 97.3, `apex_V` 98.1 → 97.8 at the
shipped guard settings). The mitre is not uniformly beneficial, and `test_mitre_closes_a_sharp_apex_
without_breaking_the_floor` records the regression instead of hiding it.

**Probes, shipped settings:** letter `apex_M` 97.3 / `apex_U` (control) 96.9 / `apex_V` 97.8;
curvature `r8w` 99.3, `r4w` 98.2, `r2w` 94.1, `r1.25w` 86.5 (up from 76.0 — the mitre helps tight
rings); junction unchanged within a point. **Violations 0 on the letter and curvature probes.**

## 8. Verification

```
pytest — WITH rembg:     113 passed, 1 warning in 27.94s
pytest — WITHOUT rembg:  113 passed, 1 warning in  8.61s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

classification (stitch_types + all 96 per-object verdicts) identical to v2-part7:  True
stitches over the 12.7mm machine limit:                                            0
colour_count / segmentation_method / filled_area_mm2 identical on all ten:          True
```

Three tests added: the mitre characterisation above, a guard that the mitre leaves a straight stroke
untouched, and one pinning `paint_uncovered` — the binding-practice painter, now a committed part of
`measure_stitch_quality.py` (`--paint`) rather than a throwaway script.

| §1 Coverage (floor 80%) | Cover |
|---|---|
| `app/services/digitizer.py` | **94%** |
| `scripts/measure_stitch_quality.py` | **95%** |
| `scripts/run_quality_bench.py` | 65% ⚠ pre-existing, untouched |

**§3 Size.** `_mitre_stalled_side` reached 71 lines and was split into `_mitre_one_side` +
`_min_stitch_px`; nothing added by this part now exceeds 50. Pre-existing over-limit functions:
`digitize_image` 336, `rebuild_design` 129, `_skeleton_branches` 76, `_skeleton_satin` 55,
`_column_ends` 51. `digitizer.py` at 2,032 lines remains the standing documented exception.

**§4 Security.** Secrets scan clean. One new named constant, `MITRE_MIN_STALLED = 3`, commented.
**§1 Lint.** `ruff` 14 findings, all pre-existing.

## 9. What to attack

1. §6 — the floor regressed 3 → 5. Is §4's coverage gain worth two extra sub-floor penetrations, or
   should the mitre be held until the `_coalesce_short` interaction is closed?
2. §7 — the mitre helps joined apexes and hurts butt joints. Should it detect the difference?
3. §5 — 03's edge band did not recover. Its loss is ring curvature, which Part 7 traded away
   knowingly. Is that trade still the right one two parts later?
4. `MITRE_MIN_STALLED = 3` is the one unmeasured constant here. What do 2 and 4 do?
5. Part 7 asserted an unreachable apex without painting it and was wrong (§1). Two parts running,
   the binding practice caught an error. Should it be enforced by tooling rather than convention?
