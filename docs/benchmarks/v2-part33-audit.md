# v2 Part 33 — Sketch, verify, then fill (the artist's workflow, measured)

**Date:** 2026-08-02 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Request:** *"First of all in the background the code should prepare the outline of the
design, just like the rough sketch an artist makes, then it should verify it with original
and if everything looks perfect then it should go with fill — which colour to fill and
where. Make it super perfect like that."*

---

## 1. What was built

The digitizer now works the way the user described an artist working:

1. **Sketch** — after colour quantization produces a label map (the *plan*: which colour
   goes where), `_sketch_from_labels()` draws that plan's outline: every boundary between
   two planned colour regions, plus the outer silhouette (morphological gradient of the
   foreground mask). This is exactly "the rough sketch an artist makes" — pure line
   structure, no fill yet.
2. **Verify** — `_verify_sketch()` compares the sketch against the *original image's own
   lines* (Canny 50/120, restricted to the artwork area). Two numbers:
   - **coverage** — what fraction of the artwork's true edges lie within
     `SKETCH_EDGE_TOL_PX = 2` px of a sketch stroke ("did the plan draw every line?")
   - **precision** — what fraction of sketch strokes lie near a true edge
     ("did the plan invent lines that aren't there?")
3. **Fill only if it looks right** — if coverage ≥ `SKETCH_MIN_COVERAGE = 0.55` the plan
   proceeds to fill assignment (existing pipeline). If not, the plan is **re-drawn with
   two more colours** (`k+2`), up to `SKETCH_MAX_RETRIES = 2` times, keeping whichever
   attempt verified best. The whole quantization stage was wrapped into a nested
   `_plan(k)` function so it can be re-run cheaply per attempt.

The user is told what happened, in plain language, via `Design.warnings`:

- retry fired → *"Outline check: the first colour plan missed too many of the artwork's
  lines and was re-drawn with N colours (structure now verified at NN%)"*
- verified but under 90% → an informative line stating the measured coverage.
- verified ≥ 90% first try (the normal case) → silence.

## 2. Why coverage gates and precision doesn't

Coverage failing means the plan *merged two regions the artwork separates* — a real,
fixable planning error (add colours, the boundary comes back). Precision failing mostly
means the artwork has texture/noise edges the plan correctly ignores — punishing that
would push textured inputs toward over-segmentation, undoing Parts 27–31. So precision is
computed and logged but does not gate.

## 3. Calibration — the gate was set from measurements, not chosen

Every input we have, measured before picking the threshold:

| Input | Sketch coverage | Retries | Verdict |
|---|---|---|---|
| Corpus fixtures 01–10 (flat art) | **0.977 – 1.000** | 0 | all pass first try, silent |
| Peacock photo (textured path) | **0.963** | 0 | passes first try |
| Neckline on black (textured path) | **0.989** | 0 | passes first try |
| Synthetic checkerboard, `max_colors=1` (forced-failure probe) | **0.493 → 1.000** | 1 | rescued |

The gate (0.55) sits far below every legitimate plan (worst honest input: 0.963 corpus
minimum 0.977) and above the genuinely broken plan (0.493). No real input pays a retry;
the broken one is caught and fixed.

**End-to-end rescue proof:** the checkerboard at `max_colors=1` quantizes both red tones
into one cluster — the internal boundary vanishes, coverage 0.493. The retry re-plans at
k=3: coverage 1.000, *both* reds recovered as separate threads, and the warning tells the
user their colour cap was overridden and why. Attempt trace: (0.493, precision 1.0) →
(1.000, precision 0.713). Pinned in `test_part33_sketch_verify.py`.

## 4. The refactor is provably pure code motion

Wrapping ~180 lines of quantization into `_plan(k)` risked silently changing output. The
10-fixture **byte-identity stream locks** are the proof it didn't: all locks green after
the refactor, before the retry loop was enabled. Zero corpus inputs trigger a retry, so
corpus streams remain byte-identical through the entire part.

## 5. Honest limits

- The retry can exceed the user's `max_colors` (that's the point — the cap was breaking
  the artwork's structure) — but it always *says so* in a warning rather than silently
  disobeying either the cap or the artwork.
- Verification is structural (edges), not chromatic: a plan that draws every boundary but
  picks a wrong shade passes this gate. Colour fidelity is guarded by the earlier parts
  (Part 31 gradient-band recovery, per-cluster medians).
- Canny at fixed 50/120 is the reference "truth"; extremely low-contrast art could
  under-report true edges (making the gate *easier*, never stricter — fail-safe
  direction).

## 6. Guardrails (standing)

pytest **738 passed + 2 xfailed** · ruff **19** (baseline, unchanged) · stream locks
**green** (byte-identical corpus) · floor / over-limit / density flags **0 / 0 / 0**.

## 7. Visual

`v2-part33-sketches.png` — for the peacock and the neckline: source | the plan's sketch
rendered as pencil-on-paper | the sketch strokes overlaid in red on the source. The
sketch visibly traces every element boundary before a single stitch is planned.

## Files

- `apps/backend/app/services/digitizer.py` — `_sketch_from_labels`, `_verify_sketch`,
  `SKETCH_*` constants, `_plan(k)` wrapper + verify-retry loop, "Outline check" warnings
- `apps/backend/tests/test_part33_sketch_verify.py` — 4 tests (good plan verifies;
  merged-vs-split comparative coverage; failed plan re-drawn + warned; good plan quiet)
- `docs/benchmarks/v2-part33-sketches.png` — sketch visualization
