# STITCHIQ v2 — Part 8 Work Report for Independent Review

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part8-audit.md`](./benchmarks/v2-part8-audit.md)

> **Read this first: one mandatory verification item is NOT met.** Residual penetration-floor
> violations go **3 → 5**. Details and the revert switch are in §4. Everything else held.

---

## 1. Part 7's account of the apex was wrong, and the probe proved it

Part 7 §4 said the medial axis "terminates inside the shape" at an `M` apex, leaving a triangle
"not reachable by any branch at any assignment". Measured:

```
apex_V branches: 3   samples [72, 6, 71]
  branch 1: (160,242) -> (160,229)          <- a 6-sample SPUR into the apex
nearest axis sample to the apex tip: 3.0px
columns already reaching within 30px of the apex: 21
```

The axis reaches the tip. Nothing is unreachable. **Part 7 asserted a mechanism without painting
it — the very practice it then made binding — and got it wrong.**

The real conflict: at a sharp vertex the **outer** arc needs a column every 0.4mm to cover it, while
every one of those columns wants its **inner** end on the reflex point, packing far tighter than the
0.30mm floor. `_enforce_floor` drops them and the outer fan opens into the bare apex.

## 2. The mitre (option a), tried first as required — and its failed first attempt

Inner ends laid along the corner's **bisector** instead of into its point. The medial axis *is* that
bisector and advances even where the boundary does not.

**It did not close cleanly at first.** Firing on any sub-floor step scattered fresh gaps along every
straight arm. A corner stalls a boundary for *several consecutive* columns; a straight stroke throws
isolated ones. Requiring a run of 3 kept the apex gain and removed the arm damage. Three further
guards were each forced by measurement (axis must advance; mitred column ≥ `MIN_STITCH_MM`; revert
anything made worse) — the middle one took violations from 7 to 5.

## 3. Result

| Fixture | interior p7 → **p8** | edge band p7 → **p8** |
|---|---|---|
| **05** | 90.1 → **95.3** | 87.5 → **89.5** |
| **06** | 96.7 → **97.7** | 90.1 → **92.3** |
| **08** | 96.9 → 96.7 | 91.5 → **92.3** |
| 03 | 97.9 → 97.9 | 92.5 → 92.6 |

**Exactly what moved** (Part 7 was loose here and the brief called it out): interior moved on 05, 06,
08, 10 and is unchanged to one decimal on 01/02/03/07/09; edge band moved on 03/05/06/07/08 and is
unchanged on 01/02/04/09/10; spill moved on 05/06/08 only.

Apex crops before/after: [05](./benchmarks/v2-part8-apex-05.png) ·
[06](./benchmarks/v2-part8-apex-06.png) · [08](./benchmarks/v2-part8-apex-08.png). The red blocks are
broken up and much reduced — **partially closed, not eliminated.**

**Part 7 open question 2, answered:** 08 recovers **+0.8 of its 1.9 lost edge band (~42%)**; 03
recovers **+0.1 of 2.7 — essentially nothing.** Consistent with the mechanism: 03's loss is ring
curvature with no apex to mitre. Reported either way.

## 4. The item I did not meet

```
penetration violations:  v2-part7  3  ->  v2-part8  5
```

4 in the running-stitch underlay (a producer no floor governs, unchanged in kind since Part 5), 1 in
a satin column. The mechanism is understood — a mitred column is shorter, and short columns interact
with `_coalesce_short` downstream of `_enforce_floor` — but not eliminated. The `MIN_STITCH_MM` guard
took it from 7 to 5 at a cost of 2.4 interior points on fixture 05.

**Not shipping this silently.** If the line is that the floor may never regress, the revert is one
constant (`MITRE_MIN_STALLED = 10**9`) and costs all of §3.

## 5. A case where the mitre measures worse — pinned, not tuned away

On a **butt-jointed** V (two strokes meeting with no rounded join) the mitre measures **97.3 → 95.1
interior**, opposite to the letter probe's joined apexes. The test records the regression rather than
reshaping the fixture to flatter the change.

## 6. The letter probe (Part 7 §7 item 5)

`tests/fixtures/letter_probe/` — short arms, sharp apexes, bench-scale stroke, with `apex_U` as a
no-sharp-apex control and `apex_narrow` at 28.9°. It reproduces the corpus defect immediately, which
Part 7's `junction_probe` did not. The uncovered-pixel painter is now committed tooling
(`measure_stitch_quality.py --paint`) rather than a throwaway script, since the practice is binding.

## 7. Verification

```
pytest — WITH rembg:     113 passed, 1 warning in 27.94s
pytest — WITHOUT rembg:  113 passed, 1 warning in  8.61s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

classification (stitch_types + all 96 verdicts) identical to v2-part7:  True
stitches over the 12.7mm machine limit:                                 0
colours / segmentation / filled area identical on all ten:              True

digitizer.py 94%   measure_stitch_quality.py 95%   run_quality_bench.py 65% (pre-existing)
```

`_mitre_stalled_side` hit 71 lines and was split; nothing added exceeds 50. `ruff` 14 findings, all
pre-existing. Secrets clean. One new named constant, `MITRE_MIN_STALLED = 3`.

## 8. What to attack

1. §4 — is §3's gain worth two extra sub-floor penetrations, or hold the mitre until the
   `_coalesce_short` interaction is closed?
2. §5 — the mitre helps joined apexes and hurts butt joints. Should it detect the difference?
3. 03's edge band never recovered. Is Part 7's curvature trade still right two parts on?
4. `MITRE_MIN_STALLED = 3` is unmeasured. What do 2 and 4 do?
5. Two parts running, painting the pixels caught an asserted mechanism that was wrong. Enforce it by
   tooling rather than convention?
