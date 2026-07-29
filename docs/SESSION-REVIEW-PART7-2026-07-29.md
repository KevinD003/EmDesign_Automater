# STITCHIQ v2 — Part 7 Work Report for Independent Review

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part7-audit.md`](./benchmarks/v2-part7-audit.md)

> **Brief:** fix the boundary partition so it does not stall at asymmetric junctions, after building
> an adversarial test case, with the penetration floor left ON throughout.
>
> **The named mechanism was real and is fixed. It was not what was costing the coverage.** That is
> §2, and it is the finding worth arguing with.

---

## 1. The adversarial case, and the partition fix

`tests/fixtures/junction_probe/` — a 3.75mm stem with a 0.63mm stroke leaving it at 30°, plus 60°
and 2.4:1 and 1:1 controls. Kept out of the ten-fixture corpus.

Colouring each boundary pixel by the branch it is assigned to
([before](./benchmarks/v2-part7-partition-before.png) /
[after](./benchmarks/v2-part7-partition-after.png)) shows the defect directly: the hairline branch
owned a tall vertical run of the **stem's** boundary on both sides. The numbers say why:

```
stem boundary pixel at the junction height:
    12.0px from the stem axis        12.4px from the hairline axis    <- a tie decided by noise
```

**Fix — subtract the local medial radius.** A boundary point lies at exactly `r(a)` from the axis
point whose maximal inscribed disc touches it, so minimise `|p − a| − r(a)` rather than `|p − a|`:

```
stem boundary pixel:  stem 12.0 − 12.0 = 0.0    hairline 12.4 − 2.8 = 9.6   -> stem      ✓
hairline boundary:    hairline 2.8 − 2.8 = 0.0  stem     13.5 − 12.0 = 1.5  -> hairline  ✓
```

Scale-free by construction. Pinned by a test: the hairline owns **12** stray stem-boundary points
under the old rule, **1** under the new one.

## 2. The finding worth arguing with: the brief named the wrong dominant cause — and so did I, twice

Fixing the partition did not recover 05/06/08. On its own it moved fixture 05 from 89.3 to **88.2**
interior — slightly worse. So I stopped theorising and painted the misses
([before](./benchmarks/v2-part7-uncovered-05-before.png)).

Then the decisive measurement: **`_enforce_floor` was dropping only 35 of 632 columns on fixture 05
(5.5%).** The wedges were not dropped columns. They were columns **never generated**.

The cause is the *other* floor enforcement point. Part 5 gated the pacing loop on
`min(moved_a, moved_b) >= floor_px` — the **slow** side must advance a full floor before a column is
emitted. On a curve that is right. At a junction, where one arc is stalled, the minimum never
reaches the floor, so the branch emits **no columns at all** across that stretch.

Part 6 §4 said the floor "removed the overdraw that was hiding the hole". Half right: it also stopped
generation outright, and that was the larger effect. Pacing now runs on the fast side only; the
safety guarantee is untouched because `_enforce_floor` still applies the 0.30mm floor to the final
endpoints, and §4 shows the violation count is unchanged.

**Two audits in a row have attributed a coverage loss to the wrong cause and only got it right by
painting the pixels.** That is worth a process change, not just a fix.

## 3. Result — partial recovery, and a real regression

**Are the M/U gaps recovered? Partially.** Interior on the junction-heavy fixtures: **08 94.1→96.9,
06 94.5→96.7, 05 89.3→90.1.** Missed interior pixels on fixture 05 **6,402 → 5,372 (−16%)**, and the
fans around the `M` apexes and `U` join are visibly thinned
([after](./benchmarks/v2-part7-uncovered-05-after.png)).

**Not recovered: the flat blocks at the apexes**, now the dominant remaining loss. They are not a
partition problem — at an `M` apex the medial axis terminates *inside* the shape and the triangle
above it is unreachable by any branch's columns under any assignment. That needs a junction-region
treatment (mitre, or a tatami patch for the remainder) and is the honest next step.

**The regression: edge band.** 03 −2.7, 08 −1.9; the ring probe loses 3–6 points at every radius with
interior and violations unchanged. Pacing on the fast side puts more columns on the concave boundary,
more of which `_enforce_floor` drops. **This part trades edge band for interior.** Both numbers are
in the audit; I am not averaging them.

## 4. Constraints held

```
classification (stitch_types + all 96 per-object verdicts) identical to v2-part6:  True
penetration violations:  v2-part6  3  ->  v2-part7  3
stitches over the 12.7mm machine limit:                                            0
colour_count / segmentation_method / filled_area_mm2 identical on all ten:         True
```

The floor was **on for every measurement in this document**, including the crops.

## 5. Verification

```
pytest — WITH rembg:     110 passed, 1 warning in 25.82s
pytest — WITHOUT rembg:  110 passed, 1 warning in  8.60s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

digitizer.py 94%   measure_stitch_quality.py 95%   run_quality_bench.py 65% (pre-existing)
```

`_free_ends` (the one function added) is 25 lines. Pre-existing over-limit functions named per the
standard: `digitize_image` 336, `rebuild_design` 129, `_skeleton_branches` 76, `_skeleton_satin` 55.
`ruff` 14 findings, all pre-existing (three introduced during the work, fixed before commit). Secrets
scan clean. No new constants.

**One thing I kept that the data does not justify:** the free-end cap distinction measures at +0.01
interior / +0.05 edge band — within noise. It is the geometrically correct treatment and costs one
function, but the ablation table is in the audit so you can cut it.

## 6. What to attack

1. §2 — should painting the pixels be a *required* step before any coverage cause is asserted?
2. This part trades edge band for interior. Right direction, after three parts spent buying edge band?
3. The apex blocks need a junction-region treatment. Does a tatami patch belong inside a satin object?
4. The free-end distinction is within noise. Keep or cut?
5. The probe proves the mechanism but not its cost. What would a probe that reproduces it look like?
