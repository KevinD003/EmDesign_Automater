# v2 Part 13 Audit — competitor-driven product round: fabric profiles, jump reduction, quality in the product

**Date:** 2026-07-29 · **Tag:** `v2-part13` · graded against [`v2-part12`](./v2-part12-summary.json)
**Grid:** [`v2-part13-grid.png`](./v2-part13-grid.png) · **Per-fixture:** [`v2-part13/`](./v2-part13/)
**Companions:** [`docs/COMPETITOR-COMPARISON.md`](../COMPETITOR-COMPARISON.md) (live-web research, cited) ·
[`docs/LAUNCH-READINESS-GAPS.md`](../LAUNCH-READINESS-GAPS.md) (tier plan this part executes from)

Headline numbers: **corpus jumps 2,042 → 1,692 (−17.1%)** with floor violations **0 → 0**,
classification identical, sub-0.5mm 9 → 9, over-limit 0 → 0. Fabric-aware density/underlay profiles
for 12 fabrics with the all-cotton corpus **byte-neutral by construction**. The quality report is now
**in the product**: auto-scored after every digitize, shown in the studio, written into the package
ZIP — verified end-to-end on localhost with a committed screenshot, not just through unit tests.

LINT-VERIFY: findings=15 files=apps/backend/app/services/digitizer.py apps/backend/app/services/optimizer.py apps/backend/app/services/package.py apps/backend/app/services/lettering.py apps/backend/app/services/embroidery_io.py apps/backend/app/routers/export.py apps/backend/app/routers/optimize.py apps/backend/app/routers/lettering.py apps/backend/app/models/design.py apps/backend/scripts/run_quality_bench.py apps/backend/tests/test_pullcomp.py apps/backend/tests/test_optimize.py apps/backend/tests/test_export.py apps/backend/tests/test_package.py apps/backend/tests/test_embroidery_io.py apps/backend/tests/test_lettering.py

---

## 1. Fabric profiles (LAUNCH-GAPS tier 2 item 2, promoted by the user's brief)

`FABRIC_PROFILES` replaces the scalar `PULL_BY_FABRIC`: 12 fabrics × {pull, fill-row pitch, satin
pitch, underlay step, edge inset}. **Cotton is exactly the old globals, so the all-cotton regression
corpus cannot move** — and §4 confirms it didn't, from the bench, not the design. `digitize_image`
resolves the profile once and seeds per-object `density`, which is why `rebuild_design` became
fabric-aware with **zero changes** — it already re-fills from per-object fields.

Values sit inside published ranges (wovens 0.4–0.5mm, denim/canvas 0.35–0.40, knits +10–15%
spacing, fleece 0.5–0.6 — sources in the comparison doc) and are **provisional**, same standing as
the floor, same protocol. One deliberate judgement call: **terry is set denser (0.4mm satin), not
sparser** — terry-specific guidance (10–20% tighter so loops can't separate the stitching)
contradicts the loft-generic guides that group it with fleece; the conflict is recorded at the
constant and in the comparison doc, and the protocol's terry sew-out is the tiebreaker.

Measured in the product, not just asserted: fixture 07 digitized as fleece produces **4,611
stitches vs 7,825 as cotton** — visible in the UI smoke test (§6). Pinned by
`test_fleece_fill_rows_are_sparser_than_cotton`, which measures the actual fill-row pitch (a first
version asserted on stitch *count* and was wrong — fleece's larger pull comp widens the region and
adds stitches while rows get sparser; and the 200px test square quantized both pitches to the same
1px row, so the test also had to move to a 640px source. Both dead ends kept in the docstring).

## 2. Jump reduction (LAUNCH-GAPS tier 3 item 6 — the biggest measured inefficiency)

Part 12's research measured 964/979 of fixture 07's jumps *within* objects. Two of the three named
emitters are fixed:

- **`_fill_by_component`** — a scattered too-wide-for-satin mask was serpentined as ONE region, so
  every row hopped between every fragment (435 of 07's jumps). Now each connected component fills
  separately, nearest-first from the needle's current position; single-component masks take the old
  path unchanged.
- **`_order_branches`** — skeleton branches were emitted in `for node in nodes` SET order,
  spatially arbitrary. Now chained greedily by nearest endpoint (reversing branches where that
  shortens travel), which also makes branch order deterministic instead of hash-order.
- **Not done:** the ring-fill hole-hop (~396 jumps on 07) — needs region splitting at the hole,
  a different mechanism, left named.

| Fixture | jumps p12 → **p13** | Fixture | jumps p12 → **p13** |
|---|---|---|---|
| 02 | 188 → **180** | 07 | 979 → **807** (−18%) |
| 05 | 44 → **34** | 08 | 387 → **229** (−41%) |
| 06 | 50 → **48** | others | unchanged |

**Corpus: 2,042 → 1,692 (−17.1%).** Context from the research: each trimmed jump costs ~3–7s of
machine time, so on fixture 08 alone this is minutes per run.

### The regression it caused, and the architectural fix

Reordering manufactured a fresh floor violation (07 `Satin 5`, 0.277mm). Instrumentation — not
theory — showed every `_axis_underlay` call returning clean: the violating triple was **created
downstream by `_coalesce_short`** on the combined underlay+top sequence. That is the structural
hole: every repair ran *before* the last sequence-changing transform, so any reshuffle could leak a
new violation. Fix: `_drop_floor_reversals` now also runs as a **backstop after coalescing** (satin
only, no-op on clean objects). Violations corpus-wide: **0**, and the guarantee no longer depends
on upstream ordering at all.

### Honest cost

Fixture 08 gives back **0.3 interior / 0.5 edge band** (96.7→96.4 / 92.3→91.8); 07 band −0.2;
05/06 tick *up* ~0.1. Stitch counts shift ±32 on 4 fixtures (coalescing cascades are
sequence-dependent — the Part 9 lesson). Probes: curvature byte-identical; junction/letter move
within ±0.4 with **0 below floor everywhere**. The render diff on 08 is 26% of pixels — that is
stitch *order* re-drawing travel lines, not coverage: the coverage numbers above are the measured
truth. I did not paint a mechanism claim for the 0.3/0.5 because I am not asserting one beyond
"sequence-dependent coalescing", explicitly flagged as unpainted.

## 3. Quality visible in the product (tier 2 items 3 + 4 + 5)

- **`analyze_quality`** now covers hoop fit (blocking finding, −25), max/mean stitch, and
  jumps/1,000 — and its report is **auto-run after every digitize/lettering call, rendered in a new
  studio QualityPanel** (score badge, metrics grid, findings, hoop-fit line), and written as
  `quality.json` into the production package ZIP.
- **A research-forced correction:** the Part 12 brief's "industry target ≤4–5 jumps per 1,000" does
  **not exist** — the dedicated web search found no such published benchmark anywhere; guidance is
  trim cost (~3–7s each). The first implementation cited the fictional target because I told it to;
  the message now states the trim cost instead, and the test pins that the message must NOT claim
  an industry target. The audit trail for the correction is the comparison doc §item 1.
- **Export hardening:** `/api/formats` now derives from pyembroidery's real writer table — the
  falsely-advertised **"vip" is gone** (pyembroidery cannot write it; HUS is import-only, stated in
  the code); JEF/EXP/VP3/XXX/PEC gained round-trip tests.
- **Lettering:** `letter_spacing_mm` (UI control, −2..10mm) and `font_path` pass-through; the
  default path is pinned **byte-identical** to the pre-change render, so existing behavior can't
  have drifted.

## 4. Corpus constraints held

```
classification (stitch_types + all 96 verdicts) identical:  True
floor violations:                     0 -> 0   (corpus + all three probes)
stitches over 12.7mm:                 0        sub-0.5mm: 9 -> 9
density flagged cells:                0        (max/cell unchanged: 08=7)
coverage: identical on 01/03/04/09/10; 05 +0.1/+0.1; 06 +0.1/+0.1; 07 0/−0.2; 08 −0.3/−0.5 (§2)
colour_count / segmentation_method / filled_area_mm2:       identical
```

## 5. Competitor comparison (the user's "compare with competitors")

Full matrix with live-web citations: [`COMPETITOR-COMPARISON.md`](../COMPETITOR-COMPARISON.md).
The one-paragraph version: STITCHIQ's cohort is the AI digitizers (EmbroidAI, SewFlow, StitchPilot,
StitchFast), not Wilcom/Hatch. After this part it matches or beats the cohort on fabric profiles,
quality reporting, export honesty, and pathing claims — and is alone in *measuring* machine-safety
(enforced 0.30mm floor, CI-checked). The widest visible gaps to paid products remain lettering
depth (digitized fonts/kerning/baselines) and underlay TYPE selection (double-zigzag/knockdown for
loft, width-dependent choice), both named with sources and deferred deliberately.

## 6. Localhost, verified — not instructed

`npm run dev` (vite :5173 proxying to uvicorn :8000) was actually run in this environment and
driven by a scripted browser: upload fixture 07 → fabric **fleece** → Digitize → the panel
auto-populates (score 99/A, 4,611 stitches, 160 jumps at 34.7/1,000, hoop fit OK, max 8.7mm).
Committed as [`v2-part13-ui-quality-panel.png`](./v2-part13-ui-quality-panel.png). README gained a
"try it in 60 seconds" walkthrough.

## 7. Verification

```
pytest — WITH rembg:     165 passed, 1 warning in 35.93s     (was 141; +24)
pytest — WITHOUT rembg:  165 passed, 1 warning in 13.06s
vitest:                  Test Files 10 passed / Tests 64 passed (was 57; +7)
npm run typecheck:       clean          npm run build: ✓ built in 4.47s
```

| §1 Coverage (floor 80%) | Cover | | Cover |
|---|---|---|---|
| `digitizer.py` (1,122 stmts) | **96%** | `optimizer.py` | **92%** |
| `lettering.py` | **87%** | `measure_stitch_quality.py` | **95%** |
| `discriminator_search.py` | **98%** | `verify_lint_claim.py` | **93%** |
| `run_quality_bench.py` | **65%** ⚠ pre-existing | | |

**§3 Size.** New functions all ≤50: `_fill_by_component` 31, `_order_branches` 28,
`_fabric_profile` 2; optimizer/lettering splits all ≤31. `digitize_image` grew to 368 (standing
exception, +18); `digitizer.py` at 2,283 lines. **§1 Lint.** The LINT-VERIFY line above is the
claim: **15 findings over the sixteen touched files — 14 pre-existing in digitizer.py, 1
pre-existing in run_quality_bench.py**; findings introduced during the work (one `zip` pairwise, plus
the services agent clearing six pre-existing ones in its files) were fixed before commit.
**§4 Security.** Secrets scan clean. Constants: `FABRIC_PROFILES`/`FABRIC_DEFAULT` (commented with
grounding + the terry conflict), `TRIM_COST_S`; `PULL_BY_FABRIC` deleted (name-compat kept via
`PULL_DEFAULT_MM` and `_default_pull`).

## 8. What to attack

1. §2's fixture-08 cost is reported but its mechanism is unpainted. If 0.3/0.5 matters, the next
   part should paint 08's uncovered diff before and after reordering and either recover it or eat it
   knowingly.
2. The floor backstop makes three enforcement points for one invariant (generation repairs,
   coalesce restore, final backstop). Is the backstop alone sufficient — could the upstream two be
   deleted for simplicity, and what would that cost geometrically?
3. `FABRIC_PROFILES` is flat per fabric; Hatch varies by object group (tatami / wide satin / narrow
   satin / lettering) and Wilcom by object size. Second-order, but it is what "fabric assist
   maturity" means.
4. The terry density conflict (denser vs sparser) is resolved by picking a source. Only the sew-out
   settles it.
5. The ring-fill hole-hop (~396 jumps on 07) is now the dominant single jump producer left.
