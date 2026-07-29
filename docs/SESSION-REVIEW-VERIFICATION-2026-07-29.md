# Verification pass — independent re-check of the pushed state

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg` · **HEAD:** `c68497d`
**Scope:** no code changed. This document records an independent re-run of every claim Parts 3–10
made, executed against the commit that is actually on GitHub.

The container had been recycled since Part 10 was written, so this is a genuinely fresh checkout —
the bench numbers below were regenerated from the pushed tree, not read back from the committed JSON.

---

## 1. Git state

```
branch                      claude/code-quality-improvements-hyu6dg
local  HEAD                 c68497d81956ffb21e138acbad18e33a8f00d1d6
origin/…-hyu6dg             c68497d81956ffb21e138acbad18e33a8f00d1d6   ← identical
commits ahead of origin     0
working tree                clean
tracked .env files          none
remote default branch       feat/studio-dashboard  (HEAD symref)
open pull request           none
```

All ten parts are pushed:

| Part | Commit | Part | Commit |
|---|---|---|---|
| 3 | `29cec05` | 7 | `5ec1397` |
| 4 | `811331d` | 8 | `72d40e1` |
| 4 (cleanup) | `5c116a6` | 9 | `55753e7` |
| 5 | `7123260` | 10 | `c68497d` |
| 6 | `b5ab544` | | |

**Note on the base branch.** `origin/HEAD` points at `feat/studio-dashboard`, not a `main`/`master`
— the repository has exactly two remote heads. The work branch is **25 commits ahead** of that
default. Worth knowing before any PR is opened, because the diff will be against
`feat/studio-dashboard`.

## 2. Reproducibility — the bench regenerates identically

`python scripts/run_quality_bench.py --tag v2-verify`, then a field-by-field comparison against the
committed `v2-part10-summary.json`:

```
every metric field on all ten fixtures:   IDENTICAL
fields that differ:                       runtime_s, output_png  (wall-clock and file path only)
```

That is the strongest available statement: the pushed commit is deterministic and the committed
audit numbers are not stale. The `v2-verify` artifacts were deleted afterwards rather than committed
— they are byte-equal to `v2-part10` and reproducible with one command, so keeping them would just
duplicate 12 MB of PNGs.

**Per-fixture, as regenerated:**

| Fixture | interior | edge band | spill | stitches | sub-0.5mm |
|---|---|---|---|---|---|
| 01 flat_2color_logo | 98.7 | 94.6 | 2.1 | 1,632 | 0 |
| 02 logo_fine_text_3color | 99.0 | 97.1 | 3.7 | 3,714 | 0 |
| 03 gradient_soft_subject | 97.9 | 92.6 | 7.7 | 3,228 | 0 |
| 04 thin_line_outline | — | 99.9 | 47.1 | 1,861 | 2 |
| 05 wordmark_caps | 95.3 | 89.5 | 11.1 | 1,492 | 0 |
| 06 wordmark_script | 97.7 | 92.3 | 21.0 | 1,219 | 0 |
| 07 circular_badge | 97.9 | 95.5 | 4.8 | 7,806 | 4 |
| 08 mascot_detail | 96.7 | 92.3 | 4.0 | 5,005 | 2 |
| 09 nonuniform_background | 99.0 | 93.3 | 3.9 | 1,006 | 1 |
| 10 low_contrast_subject | 98.6 | 94.4 | 3.0 | 2,389 | 0 |

Totals: **29,352 stitches · 96 objects · 0 fixtures with over-limit stitches · 0 with warnings.**

## 3. The machine-safety guarantees hold

Penetration-floor violations, tallied from the summary JSON across the last four parts — the
regression and its closure are both visible in the record, not just asserted:

| | Part 8 | Part 9 | Part 10 | **verify** |
|---|---|---|---|---|
| below-floor total | 5 | 3 | 2 | **2** |
| 07 `Satin 1` (underlay) 0.183mm | 1 | 1 | 1 | **1** |
| 07 `Satin 13` (underlay) 0.000mm | 3 | 1 | 1 | **1** |
| 08 `Satin 16` (column) 0.252mm | 1 | 1 | — | **—** |

```
stitches over the 12.7mm machine limit:   0   (all ten fixtures)
sub-0.5mm stitches, corpus-wide:          9   (Part 9 was 33)
satin-COLUMN floor violations:            0   ← both residuals are running-stitch underlay
```

## 4. Probes reproduce

All three regenerate the audited figures. Notably `apex_M 97.3` and `apex_V 97.8` — the exact numbers
the Part 10 housekeeping fix put into the test comment after Part 9's `str.replace` silently no-op'd.
That comment is now confirmed correct against a live run, not just against a diff.

| Probe | result |
|---|---|
| curvature | rings r8w 99.3/94.6 · r4w 98.2/91.0 · r2w 94.1/82.8 · r1.25w 86.5/72.8 · **0 below floor at every radius** |
| junction | equal_30deg 97.7/94.7 · hairline_30deg 99.5/98.1 · hairline_60deg 99.7/97.8 · medium_30deg 99.3/98.3 · 1 residual violation (hairline_30deg 0.259mm) |
| letter | apex_M 97.3/92.1 · apex_V 97.8/95.1 · apex_U 96.9/91.2 (control) · apex_narrow 96.3/90.3 · **0 below floor** |

## 5. Tests, coverage, lint, secrets

```
pytest — WITH rembg:      116 passed, 1 warning in 59.39s
pytest — WITHOUT rembg:   116 passed, 1 warning in  9.60s   (STITCHIQ_DISABLE_REMBG=1)
vitest:                   Test Files 9 passed (9) / Tests 57 passed (57)
```

**§1 Coverage** (floor 80%):

| File | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 1,049 | 61 | **94%** |
| `scripts/measure_stitch_quality.py` | 191 | 10 | **95%** |
| `scripts/run_quality_bench.py` | 248 | 87 | **65%** ⚠ pre-existing, untouched since Part 5 |

**§4 Security.** The standards' scan run over the whole ten-part range (`9f8af7a..HEAD`) returns only
prose matches — the words "secret"/"token" inside STATUS.md rows and the standards document
describing the scan itself. **No credential-shaped values.** No `.env` file is tracked.

## 6. Two discrepancies found, both minor, both reported rather than quietly corrected

**(a) The audits' ruff count is scoped more narrowly than the audits say.** Parts 7–10 each report
"`ruff check` over every touched file: **14 findings**, all pre-existing." Measured:

```
digitizer.py alone                                        14   ← the number the audits print
digitizer.py + measure_stitch_quality.py + run_quality_bench.py + both touched test files   15
```

The 15th is `scripts/run_quality_bench.py:192 RUF007`. It is genuinely pre-existing — that file has
not been touched since Part 5 — so the substantive claim ("all pre-existing") is true, and the count
is stable at 14 for `digitizer.py` across `5ec1397`, `72d40e1`, `55753e7` and `c68497d`, verified by
running ruff against each commit's version of the file. **The wording overstates the scope by one
file.** Nothing was regressed; the audits should have said "digitizer.py: 14".

**(b) A caveat about what the coverage metric actually grades.** Opening the regenerated grid rather
than only reading the numbers — the practice made binding in Part 7 §7 — fixture **10** reports
98.6% interior while its render is visibly wrong: the input is a low-contrast rounded square with
"LC" lettering, the output is a circle with unresolved detail in the middle. Fixture **08**'s
whiskers and facial detail are similarly smeared at 96.7%.

This is not a metric bug and not a regression. Verified in the code rather than assumed:
`_rasterise` (`scripts/measure_stitch_quality.py:180`) builds the outline mask from
`design.objects[].contour` — the **segmented** contours the pipeline produced — so
`coverage_metrics` grades *"did the stitches fill the shape the segmenter found"*, never *"did the
segmenter find the right shape."* Parts 3–10 all worked on stitch generation, where that is exactly
the right question. But it means **a high interior percentage is not evidence of fidelity to the
source artwork**, and the corpus's remaining visible weakness on 03/08/10 is upstream of everything
these ten parts touched. Worth stating plainly so the number is not read as more than it is.

## 7. What this pass did NOT verify

- **Nothing was run on a machine.** The 0.30mm floor, the 12.7mm limit and the 0.5mm minimum are
  still asserted from practice; no fabric test has been performed at any point in this project.
- **No stitch file was opened in third-party software.** Rendering is graded by the app's own
  preview renderer, which is the right call for grading the customer-visible artefact but is not an
  independent reader.
- **Segmentation quality** — see §6(b). Out of scope for Parts 3–10 and untested here.

## 8. Bottom line

Everything is on GitHub, the pushed commit reproduces every number Parts 3–10 claimed, all 116 + 57
tests pass on both rembg paths, and the two machine-safety guarantees hold. The only corrections this
pass produces are a scope wording fix on the lint count and a caveat about what "interior %" means —
neither of which changes any shipped behaviour.

No pull request has been opened; that still needs an explicit go-ahead.
