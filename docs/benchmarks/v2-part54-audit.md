# v2 Part 54 — the reference protocol: a capture spec that was measured, and a fallback

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** unblock R004 by making the reference trustworthy. Priority A if a
better photograph can be obtained; Priority B otherwise. No generator change.

**Explicit statement, as the gate requires: the reference is NOT good enough to
resume consumer work, and no better photograph exists in this environment.** The
best image available is the same 736×1689 panel (the two other uploads are
smaller: 474×695 and 380×578). So Part 54 delivers Priority A's *protocol and
tooling* — validated end to end — and Priority B's fallback, stated plainly.

**The one number worth carrying forward is corrected.** Part 53 recommended
"roughly 0.05 mm/px". That was arithmetic. Measured, the requirement is
**0.074 mm/px** — 2.5× the current linear resolution — and, more usefully,
**0.120 mm/px already takes satin from 23% usable to 84%.**

---

## 1. Priority A — the tooling, built and validated

### The capture spec, derived rather than asserted

Downsample the reference we have, re-measure the column width at which the
reading flips from edges to thread, and read off the law. No simulation:

| mm/px | frame | crossover | satin usable |
|---:|---:|---:|---:|
| **0.186** (the panel) | 736×1689 | 2.0 mm | **23%** |
| 0.219 | 625×1435 | 2.0 mm | 22% |
| 0.266 | 515×1182 | 2.2 mm | 15% |
| 0.338 | 404×928 | 2.2 mm | 14% |
| 0.413 | 331×760 | 2.2 mm | 14% |
| 0.531 | 257×591 | 3.0 mm | 2% |

**The row at 0.186 reproduces Part 53 exactly** — crossover 2.0 mm, 23% of satin
usable — from a different code path. That is the check that makes the rest of the
table worth reading.

In pixels the crossover runs 10.8, 9.1, 8.3, 6.5, 5.3, 5.6. It drifts, because two
limits are in play: the analysis window (fixed in pixels) binds at fine scales,
thread pitch (fixed in mm) binds at coarse ones. Extrapolation uses the **finest**
point, 10.8 px — the relevant regime and the conservative end. The panel's
narrowest satin is ~0.8 mm, so **0.8 ÷ 10.8 ≈ 0.074 mm/px**.

### What it would buy

| capture | crossover | satin usable | tatami usable |
|---:|---:|---:|---:|
| 0.186 mm/px (today) | 2.0 mm | 23% | 32% |
| 0.120 mm/px | 1.3 mm | 84% | 77% |
| **0.074 mm/px** | **0.8 mm** | **95%** | **86%** |

### Crop registration

A macro shot of one region is worthless until it sits in the design's coordinate
frame, and Part 52 is the standing warning about mappings nobody checked. ORB plus
a partial-affine estimate recovers translation, rotation and scale.
**Self-tested against transforms applied deliberately:**

| upscale | origin error | scale error | inliers |
|---:|---:|---:|---:|
| 2× | 0.5 px | 0.2% | 53 |
| 3× | 0.4 px | 0.1% | 38 |
| 4× | 0.5 px | 0.1% | 16 |

A test also requires that random noise **fails** to register rather than
producing a confident wrong placement.

### Validity instrument

`crossover_width` answers "above what width is this reference trustworthy" for
any photograph, and `measure_field_headroom.py --validity` reports the share of
satin above it. The protocol document makes running these a precondition of
scoring anything on a new photograph.

## 2. Two mistakes I made building this, both caught

**The simulation was wrong and was thrown away.** The obvious route is a synthetic
sew-out with known thread direction, swept over resolution. Built first — and it
reported "edges" at *every* width and *every* blur, including zero blur. Cause: a
perfectly periodic thread pattern near the sampling limit aliases to **zero 3-tap
gradient response** (Sobel over `[a, b, a]` is 0), so the only signal left was the
column edges. Making it physical (soft ridge profile, drifting phase, per-thread
brightness) helped but still needed **two free parameters fitted to one
observation**, which would fit anything. Deleted in favour of the downsample law,
which needs none.

**The first crossover definition collapsed.** Scanning upward for the first bucket
that reads thread terminates on a single noisy narrow bucket — it reported
"0.4 mm crossover, 100% usable" at the very scale Part 53 had already measured as
unusable. The property wanted is monotone, so it is now checked from the top down:
the crossover is the lowest width from which *every* populated bucket above also
reads thread. Both the bug and the fix are pinned by tests.

## 3. Priority B — the fallback, stated plainly

No better photograph exists here, so this applies now.

### What the current reference can still answer

- **Which of two contour-parallel field variants is better seeded.** Part 52's
  seed ranking is unaffected: all three candidates are boundary-seeded variants of
  one solver, scored on one registration and one territory definition. The
  question "which boundary set" is legitimate even when the reference reads
  boundaries.
- **Direction on structures ≥ 2 mm.** 23% of satin and 32% of tatami segments.
  Real, but a minority, and not the population any generator change would target.
- **Coverage, penetration, trim count, stitch count, fragmentation, runtime.**
  None of these depend on the orientation reading at all. The corpus, the quality
  bench, the stream locks and the visual baselines are all untouched by this
  finding.

### What it cannot answer, and must stop being used for

- **Whether consuming the direction field improves satin.** 77% of satin sits
  below the crossover, and there the reference rewards contour-parallel answers
  by construction — which is precisely what produced Part 53's illusory +16.98°.
- **Whether consuming it improves tatami.** 68% of tatami sits below the crossover.
- **Any absolute direction figure on thin artwork**, including the 49.9° headline.

### The alternative axis, if no better photograph arrives

Judge R004 by **paired visual comparison against a real sew-out** rather than by a
scalar. The machinery already exists: Part 44's deterministic renderer and the
SSIM harness produce a stable image of any candidate, and Part 50's quiver panels
already show a digitizer's eye what the field does to a badge's rings. The
protocol would be: render candidate and control at the same seed, put them beside
the photograph, and have a human call it — recording the call, the fixtures and
the date, so it is evidence rather than an impression.

That is weaker than a number and it is honest about being weaker. It is also the
only axis available that does not reward agreeing with outlines.

## 4. Decision

**R004 numeric optimisation should stop until a better reference exists.**

- Do not implement D2 or D3. Part 53 showed neither is measurable; nothing in
  Part 54 changes that.
- Do not tune the field, the seed or any threshold against this panel. Every such
  score is partly a measure of how contour-parallel the candidate is.
- **The cheapest unblocking action is a photograph**, to `docs/REFERENCE-CAPTURE-PROTOCOL.md`.
  At 0.120 mm/px — 1.5× the current resolution, well within an ordinary camera on
  a close crop — satin goes from 23% to 84% usable.
- Meanwhile, spend effort on R005 (fragmentation) or R008 (motif detection), both
  of which are measurable with instruments this project already trusts.

## 5. Gates

| Gate | Result |
|---|---|
| Explicit statement | ✅ **not good enough to resume; no better photo available; fallback stated** |
| Validity check on every new measurement | ✅ `crossover_width` + the reproduction of Part 53's 23% |
| `app/` behaviour unchanged | ✅ **no file under `app/` changed** |
| Stream locks / visual baselines | ✅ 4 and 10/10 |
| Backend suite | ✅ **894 passed, 2 xfailed** in 797.15 s (888 + 6 new) |
| `ruff check app` | ✅ 12, the standing baseline |
| No generator change, no threshold tuning | ✅ nothing in this part touches the engine |

## 6. Files

- `docs/REFERENCE-CAPTURE-PROTOCOL.md` — the capture spec and shooting protocol
- `apps/backend/scripts/reference_protocol.py` — `--selftest`, `--spec`, `--validate`,
  plus `register_crop` and `crossover_width`
- `apps/backend/tests/test_part54_reference_protocol.py` — 6 tests
