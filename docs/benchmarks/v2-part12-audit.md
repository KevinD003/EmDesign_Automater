# v2 Part 12 Audit — Part 11's open questions closed; launch-readiness measured

**Date:** 2026-07-29 · **Tag:** `v2-part12` · graded against [`v2-part11`](./v2-part11-summary.json)
**Grid:** [`v2-part12-grid.png`](./v2-part12-grid.png) · **Per-fixture:** [`v2-part12/`](./v2-part12/)
**Companion:** [`docs/LAUNCH-READINESS-GAPS.md`](../LAUNCH-READINESS-GAPS.md) — the Part B
determinations and ranked plan live there; this audit is the Part A engineering.

**Every stitch stream in the corpus is byte-identical to Part 11.** The only bench change is one
new additive field (`density`). Floor violations stay **0**; the new accumulation metric reports
**0 flagged cells** on the healthy corpus while demonstrably firing on the pile-up class it exists
to catch (§5). One physical item could not be executed here and is not pretended otherwise (§4).

LINT-VERIFY: findings=15 files=apps/backend/app/services/digitizer.py apps/backend/scripts/measure_stitch_quality.py apps/backend/scripts/run_quality_bench.py apps/backend/scripts/discriminator_search.py apps/backend/scripts/verify_lint_claim.py apps/backend/tests/test_stitch_quality_metrics.py apps/backend/tests/test_discriminator_search.py apps/backend/tests/test_verify_lint_claim.py

---

## 1. A1 — the local-discrimination claim, now evidence instead of argument

`scripts/discriminator_search.py` (committed, tested, output reproduced by
`python scripts/discriminator_search.py`). Two halves:

**Constructive.** A triple is determined up to rigid motion + reflection by the complete invariant
`(|ab|, |bc|, angle at b)`, and any physical discriminator must respect that symmetry. So the
decisive test is whether a violating reversal's *exact coordinates* are also a legitimate satin
emission `(B0, A1, B1)`. Measured:

```
07 Satin 1  (0.1828mm): legs 2.0193/2.0110mm, angle  5.19 deg, violates=True, satin-realizable=True
07 Satin 13 (0.0000mm): legs 2.1937/2.1937mm, angle  0.00 deg, violates=True, satin-realizable=True
sampled violating reversals that are ALSO a legitimate satin emission: 590/590 (100.0%)
```

For 100% of cases — including both real ones — every function `f(a,b,c)` returns the same answer
for both readings. **Separation is impossible for the individual triple.** Part 11's claim stands,
now constructively.

**The honest caveat.** Across *distributions* partial separation exists (best candidate: leg ratio,
balanced accuracy 0.908 on the full adversarial space, collapsing toward chance — gap |ac| 0.551 —
on the equal-leg subfamily real decimation emits; both real cases have leg ratios 1.004 and 1.000,
deep inside the overlap). A distributional prior is not a usable filter: its false positives are by
construction real satin violations, the population the metric exists to catch. Sweep tables in the
script output; the balanced-accuracy correction (unbalanced populations reward the trivial
always-say-satin classifier) is §-documented in the script itself.

## 2. A2 — reversal side preference: measured, and neither fixed policy wins

The repair's only degree of freedom is which point of the coincident pair to drop, and its only
cost is the merged stitch it creates (an unanchored underlay span). Swept over 3,552 violating
asymmetric turnarounds (legs, adjacent steps and kink all varied):

```
return-drop creates the LONGER merged stitch:  1,760/3,552 (49.5%)
excess when it loses: mean 0.577mm, max 1.786mm
guard divergence (return-merge > MAX while outbound fine): 0
```

49.5% is the honest answer to "which preference wins": **neither** — the problem is symmetric, so
any fixed choice is wrong half the time. Shipped: **adaptive** — drop the side leaving the smaller
merged stitch, ties keeping the return side. Verified by hand on both fixture-07 cases: Satin 13 is
an exact tie (4.39mm either way) and Satin 1's return merge is already smaller (2.13 vs 2.21mm), so
the corpus is byte-identical — which §7 confirms from the bench, not just the argument. The losing
case is pinned as `test_reversal_repair_drops_the_side_with_the_smaller_merged_stitch` (outbound
merge 1.7mm vs return 2.99mm; Part 11's policy would have picked the 2.99).

## 3. A3 — the two unwired paths: one wired and proven, one proven impossible

**`_edge_walk` — wired.** Where erosion leaves a hairline spike, the contour walks out the spike
and back 2px away: the same out-and-back geometry as a branch tip. No corpus fixture produces one
("doesn't violate on this corpus" ≠ "cannot violate"), so the adversarial case constructs it: a
block with a 3px spike, swept over 21 spike lengths so sampling phase must land on the tip. Raw
`_edge_walk` produces violations at lengths 34 and 54 (gap 2.0px); with the floor wired, **zero
across the whole sweep**. Both `digitize_image`'s tatami path and `rebuild_design`'s fill path now
pass the floor. Corpus effect: none (§7) — the wiring is protection, not change.

**`_center_walk` — deliberately NOT wired, with proof.** Its loop emits at strictly increasing
rotated-x, one `step_px` per point, and the un-rotation is an isometry — so any same-side pair is
≥ `2·step_px` apart (~4mm against a 0.30mm floor) and the zigzag triple test can never pass.
Wiring it would be dead code. Pinned by `test_center_walk_cannot_zigzag`, a property test over 30
seeded random blob masks, rather than left as an assertion.

**A finding from building the adversarial case, recorded for §5:** when the spike is the contour's
*starting* point, the same-hole pair sits at the seam — first and last penetrations of the loop,
adjacent in space, maximally far apart in the stream. **No consecutive-triple metric can ever see
that pair.** This is a structural blind spot of the Part 5 metric, discovered by trying to break
the repair rather than by theorising.

## 4. A4 — fabric validation: protocol committed; results honestly absent

This environment cannot run an embroidery machine, and this project's standards forbid inventing
results. What could be done has been done:

- **The reconciliation the brief demanded (also B2):** the widely-cited "running stitch never below
  0.5mm" is a *stitch-length* rule. This pipeline enforces stitch length at `MIN_STITCH_MM = 0.5` —
  exactly the cited value, in both digitize and rebuild paths. `MIN_PENETRATION_MM = 0.30` bounds a
  *different* quantity (same-side spacing, invisible to consecutive stitch length) that the industry
  guides do not measure. **The pipeline is not more permissive than the guidance; it enforces the
  guidance plus one additional check.** Now documented at the constant's definition
  (digitizer.py, `MIN_PENETRATION_MM` block) instead of living only in audit prose.
- **`docs/FABRIC_TEST_PROTOCOL.md`** — equipment, four fabrics (woven cotton, knit, fleece,
  terry/sherpa), four test pieces (penetration-spacing ladder 0.50→0.10mm, stitch-length ladder,
  pile-up patch at 2×/3×/4× layers, three real fixtures), per-fabric procedure, acceptance rules
  that say which constant moves in which direction on which observation, and a recording worksheet.
  The pile-up patch doubles as the density metric's validation (§5).

The brief's "physical fabric test-stitch results section" therefore reads: **no physical results
exist anywhere in this project's history, none were produced this part, and the protocol above is
the executable path to them.** Anything else would be fiction.

## 5. A5 — the metric's successor: penetration accumulation per cell

`density_metrics` in `measure_stitch_quality.py`, wired into the bench (`density` field) and the
CLI `measure` aggregate. Every STITCH is counted into a 0.5mm grid — **order-independent**, which
is precisely what the triple test is not. It sees the three defect classes the floor cannot:
stacked objects, repeated passes, and far-apart-in-stream same-hole pairs like §3's contour seam.

Corpus measurement (WITH rembg): max per cell **7** (fixture 08), typical fixture peaks 2–4,
p99 2–4. Flag level `DENSITY_FLAG_PER_CELL = 14` = **2× the worst healthy cell** — a second full
layer stacked on the densest spot the corpus legitimately produces. Provisional, unvalidated on
fabric, same standing and same protocol as the floor — stated in the constant's comment.

Does it discriminate? On the healthy corpus: 0 flagged cells, by design — the corpus contains no
stacked-object defects. That it *fires* on the defect class is proven, not assumed:
`test_density_flags_a_pile_up` (15 penetrations in one cell → flagged) and
`test_density_is_order_independent_where_the_triple_test_is_blind` (the seam pair: invisible to
`same_side_spacings`, visible to the cell count). Unlike the floor at Part 11's close, this metric
also carries a *continuous* signal (max/p99 per fixture, hottest cells with coordinates) rather
than a single exhausted boolean.

## 6. A6 — lint claims are now machine-checked

`scripts/verify_lint_claim.py` + a CI step. An audit embeds
`LINT-VERIFY: findings=N files=...` (repo-root-relative); the checker re-runs ruff over exactly
those files and **fails CI on mismatch**. Parts 7–10's miscount ("14 over every touched file" when
14 was digitizer.py alone) becomes a build failure instead of surviving four parts. Historical
audits without the marker are skipped — history is not retroactively gated. This audit carries the
first marker (top of file): **15 findings over the eight touched files — 14 pre-existing in
digitizer.py + 1 pre-existing in run_quality_bench.py (untouched since Part 5)** — and the checker
verified it before commit (`1 carry LINT-VERIFY markers / ok ... 15 findings, verified`).

Two notes for the record: CI previously ran **no lint at all** (research finding, ci.yml had only
pytest + frontend steps), and the new step is deliberately not a bare `ruff check .` gate — that
would fail every build on the 14 documented pre-existing findings. Also: ci.yml's own header says
the workflow has never been verified against real GitHub runners; the first PR will test it.

## 7. Constraints held — corpus effect of all of the above: nothing

Field-by-field diff of `v2-part12-summary.json` against `v2-part11-summary.json`, excluding
runtime and paths:

```
fields that moved:            ONLY the new `density` field, on all ten fixtures
stitch streams:               byte-identical (stitch_count, jump_count, max/mean, sub-0.5mm: 9)
classification:               identical (stitch_types + all 96 verdicts)
coverage:                     identical on all ten
floor violations:             0 -> 0  (corpus and all three probes; probe tables unchanged)
density flagged cells:        0       (max per cell: 08=7, 07=6, rest <=5)
stitches over 12.7mm:         0
```

The A2 policy change and the A3 wiring were both designed to be corpus-invisible (tie-break
preservation; protection against a case the corpus doesn't contain) — and the bench confirms it
rather than the design asserting it.

## 8. Verification

```
pytest — WITH rembg:     141 passed, 1 warning in 29.19s
pytest — WITHOUT rembg:  141 passed, 1 warning in 12.32s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

18 tests added (123 → 141): 5 for the discriminator script, 6 for the lint verifier, 3 for A2/A3
(adaptive side choice, edge-walk spike sweep, center-walk impossibility property), 4 for the
density metric (pile-up fires, healthy path doesn't, order-independence vs the triple test's
blindness, corpus-health pin bracketing both rembg paths — 7 with, 6 without, both far under 14).

| §1 Coverage (floor 80%) | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 1,078 | 52 | **95%** |
| `scripts/measure_stitch_quality.py` | 204 | 11 | **95%** |
| `scripts/discriminator_search.py` | 89 | 2 | **98%** |
| `scripts/verify_lint_claim.py` | 45 | 3 | **93%** |
| `scripts/run_quality_bench.py` | 250 | 87 | **65%** ⚠ pre-existing, untouched since Part 5 |

**§3 Size.** `_drop_floor_reversals` 51 lines (touched; trimmed from 54 back toward the limit —
reported, one over), `density_metrics` 33, everything else added ≤46. Pre-existing over-limit:
`digitize_image` 350, `rebuild_design` 134, `_skeleton_branches` 76, `_skeleton_satin` 55.
`digitizer.py` at 2,200 lines remains the standing documented exception (+38 this part).

**§1 Lint.** The LINT-VERIFY line above IS the claim; 8 findings introduced during the work were
fixed before commit (3 f-strings, 4 stale noqa, 1 subprocess check-policy, found by the same ruff
run). **§4 Security.** Secrets scan over the diff — clean. Constants added: `DENSITY_CELL_MM`,
`DENSITY_FLAG_PER_CELL`, `UNDERLAY_REPAIR_PASSES` (Part 11's, now shared by the A2 rewrite), all
commented with their grounding.

## 9. What to attack

1. §1's constructive argument assumes any meaningful discriminator is isometry-invariant. Is there
   a physically meaningful *anisotropic* signal (e.g. relative to the fabric grain) that breaks the
   symmetry argument? Nothing in the current model represents grain at all.
2. §5's flag at 2× healthy-max is grounded in the corpus, not in fabric. The protocol's pile-up
   patch (2× ≈ the flag exactly) will move it in one direction or the other — until then the metric
   flags nothing real, and a critic may fairly say its demonstrated firing is synthetic.
3. §2 shipped adaptive on a 49.5/50.5 measurement — defensible, but the visual claim rests on
   "underlay is invisible under top stitching," which Part 11 verified for ONE dropped point. No
   asymmetric case exists in the corpus to paint. Should one be constructed as a fixture?
4. The B7 research finding (964/979 of fixture 07's jumps are within-object, 831 from one
   scanline rule) is the largest untouched efficiency item in the project, and no part has ever
   audited jump count as a quality number with a target.
5. The launch-readiness document's tier 1 cannot be executed by this codebase's author. Every part
   since 6 has carried "asserted, not measured" — at what point does carrying it stop being honest
   and start being a decision not to test?
