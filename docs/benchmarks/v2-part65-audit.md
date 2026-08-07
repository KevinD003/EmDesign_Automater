# v2 Part 65 — photographic rescue: the fish test, fixed in the engine

**Date:** 2026-08-07 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** the Part 64 angelfish result was not competitive. Self-evaluate:
re-run the test, find the defect, fix it in the main code, deliver a
competitive result — and apply the same loop to repo consolidation.

**Delivered.** The angelfish now digitizes as a complete design — full striped
body, both fins, tail streamers, face details, and the surrounding coral/swirl
ornaments recovered as running stitch — via one engine change in
`pipeline.py`: an **outcome-gated photographic rescue**. Before/after:
`docs/benchmarks/part65-fish-before-after.png`; the committed benchmark
(`competitor-bench/visual/angelfish-royal-present.png`) now shows the new
result against the competitor render.

---

## 1. Self-evaluation: the diagnosis chain

1. **Where the body died.** The classification log showed 37 of 67 planned
   regions SKIPPED as `sub_thread_feature` — the yellow body's masks had
   median widths ~0.16 mm. The photo shows individual thread rows; the colour
   quantizer shatters the shaded body into a web of sub-thread slivers.
2. **Why the existing photo path never fired.** Part 27's mean-shift smoothing
   is gated on interior texture ≥ 6.0. The fish measures **1.86**: its thread
   texture is so dense that the metric's edge-avoiding interior sample shrinks
   toward its abstention floor. Applying the smoothing manually recovered the
   whole fish — the cure existed; the gate missed the patient. The gate cannot
   simply be lowered: flat-art fixtures measure up to 4.10 on the same metric.
3. **Why the first two gate candidates were wrong, measured.** The pipeline's
   element-level `lost_share` read the failed fish at **0.9%** — the webbed
   body is one connected element, "covered" by any surviving fragment. An
   owned-pixels ratio read **15.9%** — most of the dead body is never *owned*
   (halo suppression leaves shattered pixels at label −1), so it never enters
   that base either. The base that matches what the eye sees is
   **segmentation foreground minus deliberate substrate**: fish 22.8%
   unsewn, worst fixture (06's hairline script, inflated by legitimate edge
   shaving) 14.8%, every other fixture ≤ 4.4%.

## 2. The fix (main code, `pipeline.py` + `constants.py`)

**Outcome-gated retry, triple-locked.** After the plain path, measure the
pixel share of segmentation foreground no emitted object covers. The retry
fires only when (1) that share is ≥ `TEXTURE_RETRY_UNCOVERED = 0.19`
(between the worst fixture's 0.148 and the fish's 0.228) **and** (2) the
largest *connected* unsewn piece is ≥ `TEXTURE_RETRY_MIN_CHUNK_MM2 = 50` —
the rescue's failure shape is a body-sized chunk of artwork left unsewn, not
a high ratio. The smoothed result is then kept **only if** (3) it recovers
≥ `TEXTURE_RETRY_MIN_GAIN = 0.10` of the artwork. Flat art cannot pass the
third gate even with the first two forced open — smoothing recovers nothing
on art that was already traced (pinned). The kept result carries a user
warning naming what happened and recommending flat artwork over photos.

**Two defects in my first version, caught by the suite — this is why the
chunk gate exists.** The share ratio alone fired on two degenerate inputs:
a faint image whose plain path *correctly* emits an empty design reads
uncovered = 1.0, and the first rescue "recovered" it into 3,680 stitches of
sewn noise — breaking Part 47's empty→422 contract (three tests red); and a
speck-noise fuzz image (uncovered = thousands of sub-8 mm² dots) both
doubled the cost of exactly the pathological input Parts 48/49 warn about
and let the recursive run clobber the module drop-log the caller's design
was described by (Part 49's test red). The chunk gate excludes both shapes
by construction — nothing-at-all and dots-only both lack a 50 mm² connected
piece — and a rejected retry now restores the drop/classification logs it
overwrote. All four previously-red tests pass unmodified.

| | uncovered (foreground px) | objects | stitches | types |
|---|---:|---:|---:|---|
| fish, plain path | 0.228 | 30 | 5,957 | SATIN 30 |
| fish, rescued (shipped) | **0.102** | 100 | 6,504 | SATIN 39 / RUN 55 / TATAMI 6 |
| worst fixture (06 script) | 0.148 | — | — | never retried |
| other 9 fixtures | ≤ 0.044 | — | — | never retried |

The rescued result recovers content the plain path never saw at all: the
competitor's decorative swirls and coral (55 running-stitch paths — R008's
gap, partially closed here as a side effect of the body rescue), and the
orange face markings as tatami. Fragmentation (100 objects) remains the
recorded next gap; the content is now *present* to be consolidated.

**Safety, verified not asserted:** locked fixtures never reach the retry
(all ≤ 0.148 < 0.19) — the 4 stream locks and 10 visual baselines passed
before the full suite was run; determinism under the seed is pinned including
the recursive path.

## 3. Consolidation and cleanup (the second half of the order)

Checked, with the conclusion stated rather than motion for its own sake:

- **Orphan scan, frontend:** every non-test module under `src/` is imported
  by at least one other file — nothing to delete.
- **Orphan scan, backend scripts:** every measurement script is either a
  documented "reproduce" path in an audit/snapshot or a live tool. The only
  unreferenced files found were two *untracked local* corpus snapshots
  (`corpus100-before/after.json`) — deleted locally; they were never in git.
- **`scripts/split_digitizer.py`** (the Part 42 one-shot refactor tool) is
  dead code but the Part 42 audit explicitly records it as "kept as
  provenance"; deleting it would contradict a shipped decision. Kept.
- **Shared analysis code already has one home:** `extract_training_rows.py`
  and the Part 64 tests import `stream_metrics` / `split_blocks` /
  `block_features` / `infer_block_type` from `bench_competitor.py` — one
  canonical implementation. It was **not** promoted into `app/` because no
  application code consumes it; promoting scripts into the app without a
  consumer adds API surface, not value. The duplicated row-angle helpers in
  the Part 62/63 test files are deliberate test-pinning, also left.
- Prior cleanup this branch already caught the one piece of tracked deadwood
  (the stray `unit-dst.png`).

## 4. Standing instruction acknowledged

From this part on, every prompt gets this loop by default: run the test
myself → diagnose from measurements, not impressions → fix in the main code
files → verify against the full suite and the locked baselines → deliver
evidence. This audit is the template.

## 5. Gates

| Gate | Result |
|---|---|
| Fish test re-run and evaluated | ✅ diagnosis chain in §1, from the pipeline's own logs |
| Fix in main code, not scripts | ✅ `pipeline.py` retry + 2 constants; scripts only regenerate evidence |
| Competitive-level result delivered | ✅ full subject + ornament recovery; before/after panel committed |
| Locked fixtures byte-identical | ✅ 32 lock/baseline tests green before the suite; retry unreachable for them by measurement |
| New behaviour pinned | ✅ 4 new tests: gate margin, reject path, keep path (warning + smoothed stream), determinism |
| Degenerate inputs protected | ✅ empty→422 contract and speck-noise cost/log tests green with the chunk gate; first version broke both and the suite caught it |
| Backend suite | ✅ **947 passed, 2 xfailed** in 811.05 s (943 + 4 new) |
| Frontend | ✅ untouched this part |
| `ruff check app` | ✅ 12, the standing baseline |
| Cleanup honest | ✅ scans run; findings and non-deletions stated with reasons |

## 6. Files

- `apps/backend/app/services/digitizer/pipeline.py` — the rescue (retry block,
  `_LAST_UNCOVERED_PX`, `_texture_smooth` internal parameter)
- `apps/backend/app/services/digitizer/constants.py` — `TEXTURE_RETRY_UNCOVERED`,
  `TEXTURE_RETRY_MIN_GAIN`, with the calibration measurements in the comment
- `apps/backend/tests/test_part65_photo_rescue.py` — 4 tests
- `docs/benchmarks/part65-fish-before-after.png` — the delivery evidence
- `docs/benchmarks/competitor-bench/` — regenerated with the rescued engine
  (training rows: 85 → 155, the recovered fish objects included)
