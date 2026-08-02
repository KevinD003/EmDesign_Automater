# v2 Part 37 — Why the stitching still isn't as good as the source (diagnosis; two fixes tried and rejected)

**Date:** 2026-08-02 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Report:** "The digitizer gets the perfect border, shape, texture, colour and everything
but the stitch is not perfect."

**Outcome: no engine change shipped.** Two candidate fixes were implemented and
measured; both made things worse on the metric that matters most for how finished work
looks, so both were reverted. What follows is the diagnosis, the numbers, and the fix
that the evidence actually points to.

---

## 1. The gap, seen directly

`v2-part37-stitch-gap.png` puts the source sew-out, our output, and the experiment side
by side at 14 px/mm on the same 52mm window.

The source reads as **shapes**: five distinct petals per flower, curling stems, pointed
leaves. Ours reads as **blobs**: the petals fuse into one red mass.

The reason is not colour and not the boundary — both are right. It is **direction**.
In embroidery, shape is carried by stitch direction: a flower reads as five petals
because each petal is stitched along *its own* axis. Our quantizer correctly merges
same-thread petals into one red region (they *are* one thread), and the fill then runs
**one angle across the whole blob**.

Measured on the neckline panel: an **18×18mm flower is ONE object at a single −42°
angle** with 414 stitches. In the source that area is five satin petals with five
directions.

## 2. What the stitch engine is and isn't doing wrong

| Measurement | Value | Read |
|---|---|---|
| Satin same-side spacing, clean synthetic bar | median 0.450, p90 0.464 | **the generator is sound** |
| …clean curved ring | median 0.453, p90 0.537 | curvature handled |
| …tight ring (r=10mm) | median 0.454, p90 0.544 | high curvature handled |
| …**the real photographic panel** | median 0.547, p90 0.742, max 3.6, **28.9% over 0.6mm** | ragged photographic regions degrade it |
| Objects | 1,014, median **16 stitches**, 79% under 40 | heavy fragmentation |
| One colour mask | 45,092 px in **125 components**, largest 1,767 px | the label map is lace |
| Long sewn stitches > 5mm | 0.51% of sewn, 1.6% of thread | **not** a significant defect |

So the satin generator itself is accurate — it holds pitch on curves. The degradation
comes from stitching a photographic region map that is fragmented and ragged, and from
one angle per region.

## 3. Fix attempt A — lobe separation (rejected)

Cut concave regions at their necks by watershed on the distance transform, so each petal
becomes its own object with its own angle (and, when narrow, its own satin column).
Implemented, gated to textured input so the flat corpus could not move.

| | interior | edge band | stitches | floor | density |
|---|---|---|---|---|---|
| baseline | 97.10 | **94.20** | 57,027 | 0 | 0 |
| all concave regions cut | 97.50 | 92.80 | 53,103 | 0 | 0 |
| only cuts yielding elongated lobes | 97.40 | 93.10 | 52,878 | 0 | 0 |

It does what it was meant to — the big single-angle fill blobs became satin columns
(objects over 200 stitches went 5 → 39). But re-scoring exposed something the table
above hides, and it is worse than a bad trade: **the split design's declared outline is
34% smaller** (1,034,193 px vs 1,569,069) and **spill rises 16.4% → 36.3%**. The
watershed was not shaving a 1px ridge, it was destroying a third of each region's area,
and the interior/edge figures above were computed against that shrunken reference — so
they *flattered* the split rather than penalising it. **Reverted.**

Lesson repeated from earlier parts: when a change alters the reference the metric is
computed against, the metric stops being a comparison. Both designs had to be scored
against one common outline before the verdict meant anything.

## 4. Fix attempt B — stronger contour smoothing (rejected)

The source's boundaries are smoother than ours, so the smoothing was swept:

| eps (mm) / Chaikin | interior | edge band |
|---|---|---|
| **0.10 / 1 (shipped)** | **97.10** | **94.20** |
| 0.25 / 2 | 96.90 | 93.70 |
| 0.40 / 2 | 96.80 | 93.40 |
| 0.25 / 3 | 96.70 | 93.70 |

Every increase is worse on both metrics. The shipped values are already at the optimum.
**No change.**

Also swept: the textured close/open (0.4/0.3mm). Widening the close does **not**
consolidate the fragments — object count rises rather than falls (1,014 → 1,143 at
0.6mm close). Morphology is not the lever.

## 5. Applying the staged sketch-verify idea to stitching (Part 38 follow-up)

The request was to run the Part 33 architecture over the stitch stage too:
understand the shape, prepare the outline, decide colour and fill, set the needle angle,
then stitch — verifying at each step. Two of those stages were built and measured, and
**both verifications came back saying the stage is already fine**:

**Verify the fill covers its region.** Implemented `_verified_fill`: stitch, measure what
the rows actually cover as swept thread bands, and re-aim the needle if coverage falls
short — adopting a retry only when it measures better, so it could never lower coverage.
Result on the panel: **224 fills, ZERO below the 93% threshold, worst first attempt
98.5%.** The verification never fires. Coverage of the region is not the defect; the code
would have been dead weight, so it was removed.

**Verify the needle angle against the source.** A photographed sew-out *shows* the real
thread direction, so it can be read rather than guessed. Built the structure-tensor
orientation field, validated it on synthetic stripes (worst error **1.4 deg**), and drove
the fill angle from it with a fallback wherever the source shows no coherent direction.
Result: angle agreement moved **49.6 -> 49.1 deg mean** and within-15-deg **16.7% ->
17.6%**, with interior/edge/spill/floor/density all *identical*. That is inside the noise,
and it only reaches the 224 tatami fills — 560 satin objects take their angle from the
medial axis instead. Not shipped: a stream change that perturbs locks needs a gain that
is visible above noise.

### What the new instrument does say

`scripts/measure_stitch_direction.py` (shipped) scores our stitch directions against a
real sew-out. On the neckline panel:

| | value |
|---|---|
| mean \|angle error\| | **49.9 deg** (0 = matches the sew-out, 45 = coin flip) |
| median | 54.1 deg |
| within 15 deg | 15.8% |
| within 30 deg | 29.5% |

Read honestly, with the caveats the script prints itself: registration is a linear map
from the design's bounding box to the frame, validated per colour stop (most stops agree
to 3-50 in BGR, so the mapping is sound); the outliers are real digitizing artifacts —
our near-black objects land where the source's yellow lattice is, i.e. **we stitch thread
into gaps the source leaves as bare fabric**. So part of that ~50 deg is genuine
direction error and part is us stitching things that should not be stitched at all. The
number is a baseline to beat, not a verdict on any one subsystem.

The important consequence: **the direction error is spread evenly across satin (49.3),
tatami (48.9) and running (52.6)**. It is not one bad stage. Any real fix has to change
how direction is decided everywhere, which is the guided fill below — and it now has a
target to optimise against instead of an opinion.

## 6. The fix the evidence actually points to

Direction must vary **within** an object, not be bought by cutting the object up:

> **A guided (curved) fill** — carry a per-pixel angle field over the region and let the
> fill rows follow it, instead of one global angle. Rows curve along a petal without any
> ridge being cut into the shape, so the direction gain arrives with **none** of the
> edge-band cost that made attempt A a bad trade.

The pieces already exist: `_contour_fill`, `_spiral_fill` and `_radial_fill` are all
non-straight fills, but they are triggered only by shape tests (rings, holes) rather than
driven by a field. The work is to generalise `_scanline_angled` to follow a field, derive
that field from the medial axis, and validate it on the corpus. That is a substantial
piece of engine work and it is the next thing to do — it is not a tuning change.

Secondary, and separable: the region map handed to the fill is fragmented (median object
= 16 stitches). Consolidating same-thread neighbours *before* stitching would help
independently of direction, and morphology is already ruled out as the way to do it.

## 7. Guardrails

No engine change shipped, so nothing moved: 10/10 stream locks byte-identical, corpus
untouched. The measurement scripts and the comparison image are the deliverable.

## Files

- `docs/benchmarks/v2-part37-stitch-gap.png` — source vs ours vs the rejected experiment
- `apps/backend/scripts/measure_stitch_direction.py` — **shipped**: the stitch-direction
  instrument, with a self-test on known angles and a registration check
- No changes to `app/services/digitizer.py` (all four experiments reverted after
  measurement: lobe separation, stronger smoothing, fill verification, source-read angle)
