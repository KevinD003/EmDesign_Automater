# v2 Part 52 — the two-pass split: the validated seed now exists before any generator runs

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** restructure `digitize_image` into a collection pass and a generation
pass so the union-of-object-contours seed is available before sewing. Do not
retry D2. Do not change stitch output.

**Verdict: done, and stitch output is byte-identical.** The pipeline now solves
the direction field once per design, after every region is known and before any
of them is sewn, from the best of the three seeds Part 51 ranked. Nothing consumes
it yet — deliberately.

**One correction to Part 51, found by this part and material to how its numbers
should be read.** Part 51 reported a **6.50°** spread between seed classes
(32.34 union vs 38.84 silhouette). Measured under a single registration, the real
spread is **2.35°**. Part 51 compared a union seed rasterised in one coordinate
frame against a silhouette taken from another; about **4.15°** of the gap was the
frame, not the seed. **The ranking survives and so does Part 51's verdict** — the
union seed still wins on every territory, and D2's revert rested on
policy comparisons that all shared one frame. Only the seed table's magnitudes
were overstated, and they were mine.

---

## 1. What changed

`digitize_image` was one loop: for each colour cluster, find its regions and
immediately sew them. It is now two.

**Pass A** builds each cluster's mask, applies the substrate rule, finds the
contours, filters the specks, smooths the survivors, and unions them into a seed.
It emits no stitch, opens no colour stop, and writes to neither diagnostic log.

**The field** is solved once, from that seed.

**Pass B** sews exactly what pass A decided, in the original order, writing the
drop log and the classification log at the original points with the original
`seq` values — which is why both logs and all four streams are unchanged.

Three things stayed in pass B on purpose:

- **Proximity ordering.** It needs where the last stitch landed, which is
  generation state. Pass A establishes *which* regions exist, never in what order
  they are sewn.
- **The drop log.** A speck decided in pass A would otherwise land in the log
  before any object had been sewn, changing its order and its `seq`.
- **The sub-thread-feature skip.** It sits inside classification; moving it would
  have pulled the distance transform forward for no measured gain.

New module `staging.py`, between `planning` and `pipeline` in the layering, holds
`RegionPlan` / `ClusterPlan` / `DigitizePlan` and the `FieldArtifact` snapshot.

## 2. The correctness gate — which seed, checked on a real run

`scripts/measure_two_pass_seed.py` takes the seed the pipeline actually built,
rebuilds the two rivals from the same run, and scores all three against the
photographed sew-out. **All three solved in the pipeline's own frame and lifted by
the same transform** — see §3 for why that sentence is the whole gate.

| seed | whole | tatami | satin |
|---|---:|---:|---:|
| **union of object contours** — what pass A ships | **37.97** | **36.49** | **37.75** |
| per colour cluster, composited | 40.30 | 37.67 | 40.23 |
| segmentation foreground silhouette | 38.31 | 38.84 | 38.17 |

The union wins on every territory. The nearest rival is 1.18° behind on tatami
and 0.34° on the whole design. **Gate passes.**

## 3. The correction: Part 51 mixed two registrations

The first run of this gate said the pipeline's field scored **36.49** where Part 51
had validated **32.34** — a 4.15° gap on what should have been the same seed. That
is two thirds of the spread Part 51 attributed to seed choice, so it had to be
explained rather than reported.

It was not the seed. Checked in order and ruled out: the seed accumulator is
**bit-identical** to a naive full-frame construction (IoU 1.000000 over 771
regions); holes are not the cause (punching *more* holes helps — dropping the
small ones costs 2.7°); and solving in the working frame is not the cause — Part
51's own union mask downsampled into that frame still scores **32.64**.

What differs is the mapping. Part 51's `rasterise` stretches the design's mm
extents to fill the source frame; the pipeline's regions sit at their true
positions in the working frame. The design's bounding box fills **98.9% × 99.2%**
of that frame, so the two mappings differ by about a 1% scale and a 6 px shift —
which on artwork this fine moves **~17% of all boundary pixels** (IoU 0.704), and
the field is strongest exactly at boundaries.

Part 51's silhouette figure came from the pipeline and is unaffected: **38.84 in
both**. Its union and per-cluster figures came from the stretched frame and were
each flattered by roughly 2.4–4.2°. Same direction, same size, on both — which is
what makes the mapping the explanation rather than a coincidence.

**What this does and does not change.** Part 51's decision to revert D2 stands
untouched: the constant-90° control, the random control and the region angles were
all built in the one frame, so those comparisons were internally consistent. What
changes is the claim "the seed is worth 6.5°". It is worth **2.35°**.

## 4. Behaviour gate

| | |
|---|---|
| Stream locks | ✅ 4 pass, byte-identical |
| Visual baselines | ✅ 10/10 at SSIM ≥ 0.995 |
| Panel stitch count | ✅ **56,505 before and after** |
| Objects / regions | ✅ 771 both, 19 clusters |
| Drop log, classification log | ✅ unchanged — written in pass B at the original points |
| Backend suite | ✅ **883 passed, 2 xfailed** in 748.42 s (874 + 8 new + 1 layering) |
| `ruff check app` | ✅ 12, the standing baseline |

No behaviour change was shipped to justify the refactor. The field is solved and
handed on; nothing reads it.

## 5. Performance gate

Same script, HEAD versus the split, same seeds and hoops:

| input | HEAD | two-pass | |
|---|---:|---:|---|
| reference panel 736×1689 | 47.58 s | **44.98 s** | −5% |
| 600×600 random noise | 83.24 s | 85.96 s | +3% |
| 900×900 random noise | 153.50 s | **151.13 s** | −2% |
| 1500×1500 random noise | 181.52 s | **177.21 s** | −2% |

Within run-to-run noise on all four, in both directions. Stitch counts identical.

The pathological cases matter because Parts 48 and 49 both shipped per-region work
inside the pre-filter contour loop, where the multiplier is the *noise* count. Two
things keep this part off that path: the field is solved **once per design** at a
fixed resolution, and seed accumulation is **bounding-box local** — a region costs
its own area, not the frame's. Both are pinned by tests, and `staging.add_to_seed`
carries the reason in its docstring rather than in a commit message.

## 6. Tests

`tests/test_part52_two_pass.py`, 8 tests:

- the pipeline exposes a field solved from the union seed, over exactly the
  regions that became objects
- the seed is the object outlines, not the foreground silhouette — asserted
  against the real foreground of a run, on a fixture with interior structure
  (a solid logo legitimately fills its own convex hull, so a shape property
  proves nothing here; my first version of this test asserted one and failed)
- the field is solved **once** per design — not per cluster, not per region
- **every region is collected before any is sewn**, asserted on the real call
  order of `solve` against `_fill_by_component`
- a blank image yields no field rather than a solve on nothing
- `add_to_seed` is exactly equal to a full-frame draw
- seed accumulation does not scale with frame size
- solving is flat in region count

Plus `staging` added to the layering contract, which the package test enforces.

## 7. Files

- `apps/backend/app/services/digitizer/staging.py` — the intermediate representation
- `apps/backend/app/services/digitizer/pipeline.py` — the split
- `apps/backend/scripts/measure_two_pass_seed.py` — the correctness gate
- `apps/backend/tests/test_part52_two_pass.py` — 8 tests

## 8. What comes next, and what the numbers now say about it

The prerequisite is in place, so D2-retry and D3 are both unblocked. The brief said
not to choose in advance, and the corrected numbers make that the right call:
under one registration the union seed's per-pixel score is **36.49** on tatami and
**37.75** on satin, against **40.09** and **37.90** for the angles assigned today.

That is a materially smaller headroom than Part 51's uncorrected table suggested —
on satin it is now **0.15°**, not 4.4°. So the honest position is that **neither
consumer looks compelling on this evidence**, and the next part should measure
before building. Two things could still change that, and both are measurable
without writing a generator: the field's per-pixel ceiling was computed with a
solver seeded and diffused at 384 px, and the satin territory's score is dominated
by columns whose angle already varies along their length, so the aggregate may be
hiding where the gain is.

Measure that first. Do not pick tatami or satin until it says which.
