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
(objects over 200 stitches went 5 → 39). But it costs **1.1–1.4 points of edge-band
coverage**, because a watershed ridge runs from the neck out to the outline and notches
it. Outline crispness is precisely what makes stitching look finished, so trading it for
+0.3 interior is a bad deal. **Reverted.**

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

## 5. The fix the evidence actually points to

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

## 6. Guardrails

No engine change shipped, so nothing moved: 10/10 stream locks byte-identical, corpus
untouched. The measurement scripts and the comparison image are the deliverable.

## Files

- `docs/benchmarks/v2-part37-stitch-gap.png` — source vs ours vs the rejected experiment
- No changes to `app/services/digitizer.py` (both experiments reverted after measurement)
