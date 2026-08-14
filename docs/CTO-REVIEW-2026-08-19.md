# CTO review pack — the 2026-08-18 ruling executed: the defect, the corpus, RS1 shipped

**Repository:** `KevinD003/EmDesign_Automater`, branch `main`
**Base:** `6eb538c` → **Head:** `5e67ece` · four commits.

**CI, from the GitHub API — run ID and conclusion per commit:**

| commit | content | CI run | conclusion |
| --- | --- | --- | --- |
| `ce254a8` | P0 defect: a drawn path's first point is a penetration | 31739296838 | **success** |
| `a926d18` | P0 corpus enumeration + standing statement | 31739695252 | **success** |
| `80d2df4` | RS1 first build | 31743114541 | **failure** — see §4, reported in full |
| `5e67ece` | RS1 boundary fix + re-pins | 31745879992 | **success** |

Local lanes on `5e67ece`: default **1382 passed, 0 failed**, no-rebuild **1376 passed, 0 failed**,
failure sets empty. Offered alongside CI, not instead of it.

**The headline belongs to the harness, not to me: on the way to green, the visual regression
suite caught the pipeline sewing background noise — a defect every numeric gate passed — and the
investigation it forced produced three measured refutations and the ruling's authorised boundary.
Details in §5, which is the section to read if you read one.**

---

## 1. P0 — the one-penetration defect. Own commit, as ruled, and the dependency check answered.

**The convention, decided:** a jump POSITIONS the needle; a stitch PUTS IT DOWN. A run opening
with a bare jump starts one pitch late, and a two-point path sews a single unanchored
penetration. Your reading was correct — the emitter was right, `_manual_run` was wrong — and it
is now stated in the code, not just made consistent.

**The dependency check you required:** `_manual_run` has exactly **one caller** — rebuild's
RUNNING branch. No underlay path uses it (`_edge_walk`, `_center_walk`, `_run_along` are separate
implementations). The two-callers-need-different-entry-handling case does not arise.

**A failed first attempt, recorded because it is load-bearing:** keeping a leading jump entry and
duplicating the start as a stitch does not work — `_finish_rebuild_segment`'s coalesce pass
deletes the duplicate as a zero-length stitch. The working fix returns every point as a
penetration and leaves the positioning jump to the caller, which is digitize's own architecture.

**Acceptance exactly as ruled**, standing alone and falsifiable: a Line object survives
`rebuild_design` with an unchanged penetration count — constructed objects at 2/3/10/50 points,
single and double runs. Two interactions the tests record rather than hide: the tie-in lock lands
immediately after the *first* stitch, and RUNNING_DOUBLE reads N+(N−1)−1 because the turnaround
is an A-B-A same-hole reversal the floor legitimately removes — losing the entry again would read
N+(N−1)−2, so the assertion still discriminates.

## 2. P0 — the corpus item. Measured, classified, proposed. Nothing uncovered was fixed.

**Method:** `coverage run --branch` over exactly the population in question — the fourteen at
bench conditions through digitize, then a rebuild of each — with four blind spots stated,
including one driver artifact called out so it is not misread (force=True hides the provenance
pass-through; its 39 % is the driver's doing).

**Numbers:** pipeline.py **90 %**, rebuild.py **71 %**, underlay.py **50 %** branch coverage from
the fourteen. Every uncovered group is enumerated with its one-line input class in
`docs/CORPUS-COVERAGE-2026-08-18.md`.

**The distinction that shaped the proposal:** pipeline's holes are input classes (customer
artwork — fixtures are the right tool); rebuild's holes are mostly editor states (appliqué,
curved fills, flow divides do not arrive in a PNG — constructed-design tests are the honest tool,
and image fixtures there would be coverage theatre). Two rebuild guards are deliberately
unreachable alarms, named as such.

**Smallest set — five entries, two of which are promotions, not creations:** the repo already
tracks three real photographs the bench fourteen never included. F1 `A01_real_peacock` (textured
path, linework, RUNNING_SINGLE, sketch retries). F2 `A02_real_neckline_black` (dark-garment
suppression AND the phantom COLOR_CHANGE — the P2 fixture, folded in as ruled). F3/F4
transparent-PNG + SVG logo pair (the DET3 declaration path; synthetic but faithful — born-digital
classes). F5 oversized source (honest only with a genuinely large real photo; flagged).

**The standing statement** lives beside the fixtures
(`tests/fixtures/quality_bench/README.md`), ending in the rule: do not quote "the suite passed"
against a photograph, a transparent export, or a dark garment — the same error as a stitch count
without its fabric and hoop.

**The sharpened real-job-pairs ask, in your terms:** the synthetic corpus demonstrably misses the
majority object type of the one real artwork on record — 55 of 100 angelfish objects are
RUNNING_SINGLE against zero corpus reach. A measured hole, not an assertion.

## 3. P1 — RS1, steps 2–5, in your order.

**Your recorded prediction: CONFIRMED, and there is no third mechanism.** Same probe, same
geometry, only the convention fix between the tables — every −50 % row vanished (at N=2 the lost
penetration WAS the fifty percent). Worst residual: −8.33 % at 2.5 mm, −20 % at 1.4 mm, every
remaining loss a whole small number of points on a short branch — quantisation, not a mechanism.

**Pitch, measured through the real path after the convention fix, as you required:** digitize →
rebuild on 04's actual ring gives **+2.75 % at 1.4 mm (109→112)** and **+3.17 % at 2.5 mm
(63→65)**. My constructed-probe claim of exact zero did not survive the real path, and the doc
says so. Fidelity does not separate the pitches; the visual-class argument decides:
`HAIRLINE_RUN_PITCH_MM = OUTLINE_RUN_MM` (1.4) — a hairline is a traced-line-class stroke, not a
manual path.

**The two criteria, kept separate as ruled:** sewability (spur pruning at the standing
`SPUR_MIN_MM` floor + length ≥ one pitch, both derived) gates the product;
assertability (penetrations ≥ 1/band, derived from the band arithmetic itself) lives in the band
tests as an exclusion — short-but-sewable branches are sewn and excluded from percentage
assertions under the stated minimum.

**The emitter:** each surviving branch becomes a `Hairline` RUNNING_SINGLE object emitted through
`_manual_run` itself — the identical function rebuild calls — with the fine centreline stored as
the path-contour. Round trip is pinned within 04's own fidelity band. Stream accounting holds
with **no new category**: run objects follow the main loop's obj_start-before-lead-in convention.

**DET2's fourteen, before → after — coverage moves for a real reason for the first time:**

| fixture | uncovered | objects | note |
| --- | --- | --- | --- |
| **04** | **31.59 % → 16.69 %** | 10 → 11 | warning GONE — the ring is sewn; 04 drops back under the 0.19 texture-rescue gate **for the right reason** |
| 08 | 2.04 % → 1.92 % | 20 → 21 | run verified real: source pixels under the path are exactly `#30221e` |
| C24 | 17.95 % → 17.75 % | 26 → 31 | five runs |
| C11 | 6.94 % → **6.83 %** | 23 → 27 | four runs; the 4-branch network deferred (§5). **Corrected 2026-08-20** — 6.74 % was spliced in from the PRE-boundary run; see CTO-REVIEW-2026-08-20 §1 |
| 07, 09 | unchanged | unchanged | refused at the boundary (§5) |
| other eight | unchanged | unchanged | — |

04's remaining 16.69 % is anti-alias fringe and edge shaving — honest, asserted in-band
(0.05–0.19) by the rewritten DET2 test, whose docstring now carries the full three-stage history
of that assertion.

## 4. The red run on `80d2df4`, in full.

I pushed the first RS1 build before its lanes finished — the same process failure as `1b9bb8f`,
and I am reporting it the same way. Eight failures: one facade re-export miss; two measuring
scripts whose **area assumptions** run objects exposed the day the type gained fixture coverage
(`coverage_metrics` rasterised a run's path-contour with `fillPoly` — 04's ring read as a phantom
DISC; `penetration_metrics` swept a sideless run into same-side spacing, whose docstring claimed
runs "contribute nothing" — written when nothing could test it); and five intentional re-pins.
All fixed or re-pinned in `5e67ece`; the metric fixes follow the same convention the surface spec
already set — side-based instruments skip runs; a run's footprint is its stroke at thread width.

## 5. THE FINDING — the visual harness caught noise-sewing, and the boundary that resulted.

Re-pinning the baselines is where the ruling's discipline paid. The harness's rule is *look
before accepting*, and 09's new render showed **three stray dashes 24 mm above the design**. The
source under them is background noise texture — no ink. 09's refused region is quantisation
slivers of its nonuniform background; the old width-gate refusal had been **accidentally
suppressing an upstream mis-segmentation**, and RS1 unmasked it. Every numeric gate passed the
noise. The picture failed it. This is the strongest argument yet for building the surface
metrics, and it happened one ruling after you specced them.

**Verification before judgment, per region:** 04 real (the diff shows exactly the ring), 08 real
(exact source-colour match under the path), 09 noise (source crop).

**Three derived noise-vs-ink criteria, measured, all three refuted:**

| criterion | real regions | noise | verdict |
| --- | --- | --- | --- |
| spur survival after `_prune_spurs` | 99.8–100 % | 69.0 % | separates — but only via a threshold fitted to this corpus |
| colour coherence (mean \|px − centre\|) | 8.3–69.4 | **5.2** | **inverted**: speckle averages to its own centre |
| substrate distance vs `SUBSTRATE_DELTA` | C24 real: 61.4 | 64.8 | no separation |

Having demonstrated the derivation does not exist today, the fallback you authorised for exactly
this outcome applies: **only regions whose pruned skeleton is a single branch are run.**
Outcomes: **11** of 14 refused regions sewn (04 +1, 08 +1, C24 +5, C11 +4), including both independently verified as real; 09's
noise refused. **The named cost:** 07's two short real strokes and C11's 4-branch network — real
artwork, deferred until a derived criterion exists, with the three refutations recorded in
`hairline_runs`' docstring as the reason and a test that fails if the boundary widens silently.

Re-pins after the boundary: 04's stream lock re-pinned **through its quality bands**; 04 and 08
baselines updated after inspection; 07 and 09 revert to their existing pins untouched. All ten
visuals match; all locks pass.

## 6. P2 phantom COLOR_CHANGE — mechanism confirmed by reading; fixture next, as ruled.

Inside `if chains:` the darkest-thread-is-the-cloth check clears `chains = []`, and the
`COLOR_CHANGE` (with its `emitted_stop += 1`) is appended **after** that check but before the
per-chain loop — so a dark garment with suppressed linework emits a colour change, iterates an
empty list, and sews nothing. The operator stops, re-threads, sews zero stitches. Reached by F2's
input class exactly. Fix is not scoped further, per the ruling: the fixture (A02 promotion) comes
first.

## 7. Not done, and the order it happens in

| item | state |
| --- | --- |
| A01/A02 promotion into the measured corpus | next tranche — it changes "the fourteen" everywhere and deserves its own clean session |
| phantom COLOR_CHANGE fix | after its fixture, mechanism in §6 |
| surface metrics build | after the promotions; §5 is its justification |
| TEXTURE_RETRY re-derivation | after that — RS1 already changed its input honestly (04: 31.59 → 16.69, under the gate for the right reason); the report will state whether RS1 changed the answer |
| SH2 D1/D2 | last, under all three gates: committed tree, `code.dirty: false`, re-derived bands |

## 8. Reproducing

```
cd apps/backend
pytest -q tests/test_running_entry_penetration.py     # §1 acceptance
pytest -q tests/test_rs1_hairline_runs.py             # §3, §5 boundary
.venv/bin/python scripts/coverage_audit.py --json out.json   # §3 table, key uncovered_px
.venv/bin/python scripts/trace.py 04_thin_line_outline --key design.object_types
# CI verdicts: runs 31739296838 / 31739695252 / 31743114541 / 31745879992, key `conclusion`
```

## 9. What I would like ruled on

1. **§5's named cost.** 07's two strokes and C11's network are real artwork refused by the
   boundary. Acceptable as deferred, or do you want a fourth criterion attempted now? My
   recommendation: defer — three refutations say the derivation needs real artwork to calibrate
   against, which is the same dependency as everything else on the board.
2. **§7's ordering** — the corpus promotion as the next tranche's opening item, before the
   phantom fix and the surface build that both depend on it.
