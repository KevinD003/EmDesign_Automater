# Status against the ruling of 2026-08-16 — mid-tranche, not a completion report

**Repository:** `KevinD003/EmDesign_Automater`, branch `main`, head `62b42b0`, working tree clean.
**CI:** green on `62b42b0` — run **31664684721**, 0 failed jobs, confirmed independently by the CTO
in the ruling itself. No commit has been pushed since.

Shape per the standing format: each item labelled **finished**, **measured but not written**, or
**untouched**. Every number carries where it came from. Numbers produced by scratchpad probes are
labelled as probe results, not shipped-instrument results.

**Ordering note:** the P0-C clean-run experiment required a tree not being edited, so every edit
below waited behind it and lands in sequence now that it is complete. Two infrastructure restarts
killed the batch mid-flight; completed runs and their clean-tree snapshots survived both times, so
nothing measured was lost — only wall-clock.

---

## 1. P0-C — four clean runs. COMPLETE. INSTRUMENT-1 IS CLOSED.

| run | lane | container | result | failure set | tree snapshot after |
| --- | --- | --- | --- | --- | --- |
| 1 | default | cold | **1371 passed, 0 failed** | empty | porcelain empty |
| 2 | no-rebuild | warm | **1365 passed, 0 failed** | empty | porcelain empty |
| 3 | default | warm | **1371 passed, 0 failed** | empty | porcelain empty |
| 4 | no-rebuild | warm | **1365 passed, 0 failed** | empty | porcelain empty |

All four on head `62b42b0`, recorded before run 1 and re-verified at each restart boundary.

**Failure-set diff, as ruled — sets, not counts: empty vs empty on every pair. The observed
run-to-run spread on the shipping tree is ZERO.** Within-lane counts are identical
(1371/1371, 1365/1365); the 6-test difference between lanes is the pass-through suite the
no-rebuild lane skips, visible as its 8 skipped.

The cold-vs-warm boundary the restarts accidentally created adds one more refutation: run 1 on a
fresh container is byte-identical in outcome to runs 2-4 on warm ones, so cross-run filesystem
state — the last untested hypothesis class from the original six — produces no difference on a
clean committed tree.

**Close-out, in the ruling's words:** mechanism identified as most likely (G — a dirty tree under
source-reading tests), not reproducible because the tree is unrecoverable, superseded by the
dirty-tree control: every SH2 measurement comes from a committed tree with `code.dirty: false`,
evidenced by its TRACE document. **The residual, stated plainly: we never identified a varying
test, and we are choosing not to.** The "no A/B decision on a delta smaller than the observed
spread" rule is now satisfiable with spread = 0 on the shipping tree.

## 2. P0-A — nine bands re-derived. MEASURED; LANDING IN THE COMMIT AFTER THIS DOCUMENT.

Measured by a read-only scratchpad probe that reproduces each test's own procedure exactly — same
seed (1234), same hoop (cotton @ 100x100), same 1 % density edit for the parity set — on the
committed tree at `62b42b0`. The probe is `rederive_bands.py`; it will be quoted in the commit.

| test | fixture | old band | worst (span) | worst (pen) | **new band** | worst object |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| P6 | 01_flat_2color_logo | 0.10 | +0.35 % | +0.33 % | **0.10** | 1 → 1 |
| P6 | 04_thin_line_outline | 0.12 | −2.60 % | −0.38 % | **0.10** | **3 → 1** |
| P6 | 05_wordmark_caps | 0.14 | −3.00 % | −1.03 % | **0.13** | 2 → 2 |
| P6 | 06_wordmark_script | 0.20 | −9.69 % | −10.31 % | **0.21** | 1 → 1 |
| P6 | 07_circular_badge | 0.34 | −32.61 % | −34.09 % | **0.36** | 15 → 15 |
| P6 | 02_logo_fine_text_3color | 0.27 | −20.00 % | −15.38 % | **0.23** | 14 → 14 |
| PARITY | 04_thin_line_outline | 0.15 | −2.60 % | −0.38 % | **0.13** | **3 → 1** |
| PARITY | 05_wordmark_caps | 0.15 | −3.00 % | −1.03 % | **0.14** | 2 → 2 |
| PARITY | 06_wordmark_script | 0.25 | −9.69 % | −10.31 % | **0.26** | 1 → 1 |

Derivation rule, restated: each band keeps the absolute headroom it carried over its own
measurement, rounded up to 0.01. Nothing fitted. The CTO re-derived all nine by hand against this
rule and confirmed consistency.

**Direction: five tighten, three loosen, one unchanged.** A real fidelity regression moves them
one way. Rebuild fidelity did not change; it is now measured correctly. Asserted, not assumed.

**Decision 1 (approved)** lands with: the nine bands; the loss comparison moved to
`penetration_count`; the CTO's fixture-04 argument in the commit message — *object 3's −2.60 % was
jumps and trims, not thread; the old band on 04 was guarding travel bookkeeping, not fidelity, and
penetration space makes the assertion mean something for the first time* — and the worst-object
change 3 → 1 noted in the band comment so the next reader knows the assertion changed subject.

**Per-site enumeration** (the space-change rule, applied):

| site | quantity compared | decision |
| --- | --- | --- |
| `test_probes_three_paths.py` FIDELITY_BANDS ×6 | per-object loss ratio | **re-derived** (table above) |
| `test_rebuild_satin_residuals.py` PARITY_BANDS ×3 | per-object loss ratio | **re-derived** (table above) |
| `test_fidelity.py` max/min-by-count selections | object selection, no ratio | **space-independent in practice** — probe shows same object selected in both spaces on all four fixtures checked; stays on `stream_span` with its space named |
| `scripts/bench_competitor.py` | comparison harness | **moves to penetrations** per Decision 2 — the space a competitor DST can supply; keeps `median_stitches_per_object` honest |
| `scripts/measure_fragmentation.py`, `measure_r005_gates.py`, `extract_training_rows.py` | recorded span-space history | **carried over on `stream_span`**, each stating its space in its docstring |

## 3. P0-B — `accounting.py` extraction. UNTOUCHED, prediction on record.

Census, `_STREAM_COMMANDS`, stop attribution and the accounting assembly move from `routing.py`
to their own module. The falsifiable claim to be confirmed or corrected in the commit: the
rebuild-path census is *not free but close — a two-point census at rebuild's single `_lock_stream`
call site, instrument shared, its own test file needed*.

## 4. P1 RS1 — the fix. UNTOUCHED, order fixed by the ruling.

Band measurement first (against §2's re-derived bands), then the viability gate — derived
threshold or the single-branch-only fix covering 13 of 14 with the boundary named in code — then
pitch measured at both 1.4 and 2.5 mm and chosen out loud, `MIN_FEATURE_W_MM` unmoved, the warning
moving with the behaviour, and DET2's fourteen before/after alongside since coverage will move for
a real reason for the first time.

## 5. P2 phantom COLOR_CHANGE — MEASURED (frequency), fixture not built.

**0 of 14 fixtures reach the path.** All fourteen show `stops == stop_segments`, partition
matched, no zero-penetration stop (probe over `_LAST_STREAM_ACCOUNTING`, all fourteen at bench
conditions). Per the ruling: that is the finding — a live code path, guarded only by
`stops_partition_matches`, with zero corpus coverage. The fixture that reaches it (dark-linework
chains dropped as garment-coloured after their COLOR_CHANGE is emitted) gets built **before** the
fix is scoped.

## 6. P2 surface metrics — SPEC FINISHED. Build gated behind RS1, as ruled.

`SURFACE-METRICS-SPEC-2026-08-16.md`, delivered and committing to `docs/` with this batch. The
three decisions in it, compressed:

1. **Boundary deviation separates offset from roughness.** Offset (p50 signed distance, per side)
   is calibration — the stored `pull_compensation` predicts it, so it doubles as a free check that
   pull comp is applied. Roughness (p95−p5) is the whisker number the renders complain about.
2. **The instrument hooks emission, not the final stream — decided by a failed prototype.** The
   post-hoc spatial version was prototyped read-only and is confounded three ways: max |d|
   saturates at exactly the capture radius; fill interiors pollute the edge population; both sides
   of a narrow column share one capture band, so the spread measures column width. Edge identity
   exists only at generation time (`columns.py`'s end arrays are the edge penetrations per side,
   by construction). Digitize and rebuild both get it through the shared generation core.
3. **Legibility is topological.** At a declared cap height, glyph components and counters must
   match the source's own structure — mush, flooded counters and broken strokes are each a
   discrete topology change, and matching against the source needs no fitted threshold. SSIM is
   reported, never gated. The one imported number (4 mm cap-height floor) is a craft norm, cited
   as such; a sew-out of 05 at descending cap heights is the only evidence that would truly settle
   it.

## 7. P3 — TEXTURE_RETRY, SH2 D1/D2. UNTOUCHED, correctly sequenced.

TEXTURE_RETRY after RS1, because RS1 may change its input: if 04's refused ring gets run instead,
04 may stop crossing 0.19 for the right reason rather than a tuned one. The report will state
whether RS1 changed the answer. SH2 remains gated on §2's bands, a committed tree, and
`code.dirty: false`.

## 8. Landing sequence, the moment run 4's snapshot lands

Each pushed separately so CI rules on each:

1. docs — this status report and the surface spec;
2. P0-A — bands, Decision 1, Decision 2, enumeration;
3. P0-B — `accounting.py`, with the rebuild-census prediction confirmed or corrected;
4. RS1 begins with the band measurement.

## 9. Reproducing

```
cd apps/backend
# §2, once landed:      pytest -q tests/test_probes_three_paths.py tests/test_rebuild_satin_residuals.py
# §5, the frequency:    trace.py <fixture> --key accounting.stops_partition_matches   (all fourteen True)
# CI verdict:           GitHub API run 31664684721, key `conclusion`
# P0-C run 1:           scratchpad flake2/default-1.txt + dirty-default-1.txt (empty = clean)
```
