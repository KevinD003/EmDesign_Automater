# v2 Part 56 — R005 at the label map: a clean negative, and the stop condition fires

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** implement the first real R005 change upstream of contouring, at
the label-map stage. Gates and stop condition fixed by Part 55.

**Result: the change was implemented, measured against all four digitize gates,
and reverted. Gates 1, 2 and 3 fail. The stop condition fires.**

The honest headline is sharper than "the threshold was wrong": **the smoothing
radius was already at its floor.** A 3×3 majority vote is the smallest spatial
filter that exists, and at that setting it does essentially nothing on two of the
three photographs and overshoots badly on the third — taking 0.90 of interior
coverage and 26% of the stitches with it. There is no smaller setting to retreat
to, so this is not a tuning failure. It is evidence about the defect.

---

## 1. What was built

`_smooth_labels` in `planning.py`: each labelled pixel takes the most common
label in a window of `LABEL_SMOOTH_RADIUS_MM`, applied to photographic input only,
after `_absorb_specks` and before the seam fill.

Two things made it the right first attempt rather than an arbitrary one:

- **The radius was derived, not chosen.** `LABEL_SMOOTH_RADIUS_MM =
  MIN_FEATURE_W_MM / 2` — half the narrowest feature the engine can sew. Label
  structure finer than that can never become a stitched object, so dissolving it
  should cost no content *by construction*. That was the argument. §3 shows the
  argument is wrong.
- **It reaches what merging cannot.** `_absorb_specks` needs a compact component
  under an area threshold; a ragged one-pixel fringe along a boundary has no such
  component. Part 55 measured that nothing merges at a 0 mm gap, so the speckle
  is fringe, not blobs.

It was gated on `is_textured`, so flat artwork never reached it — gate 5 held by
construction rather than by luck.

## 2. The gate run

Same seed, same hoops, coverage from the corpus runner's own metric:

| design | objects | Δ | interior | stitches | trims |
|---|---|---:|---|---|---|
| A01 peacock | 336 → **330** | **−1.8%** | 95.80 → **95.60** | 38,409 → 39,237 | 364 → 344 |
| A02 neckline black | 834 → **859** | **+3.0%** | 95.90 → 95.90 | 58,800 → 63,032 | 796 → 741 |
| A03 panel | 771 → **342** | **−55.6%** | 97.00 → **96.10** | 56,505 → 41,749 | 663 → 339 |

| gate | requirement | result |
|---|---|---|
| 1 | objects −30% on **all three** | ❌ **fail** — A01 −1.8%, A02 **+3.0%** |
| 2 | interior coverage does not fall | ❌ **fail** — A01 −0.20, A03 **−0.90** |
| 3 | stitches fall or hold | ❌ **fail** — A01 +2.2%, A02 **+7.2%** |
| 4 | trims fall | ✅ pass — all three |

Gates 5–7 were not reached: a change failing 1–3 does not get to be defended on
flat-art baselines or noise runtime.

## 3. What the failure says about the defect

**The "no content cost by construction" argument is refuted.** A03 lost 0.90 of
interior coverage and **26% of its stitches** while shedding 56% of its objects.
That is the shape Part 55 named in advance — *"do not ship fewer objects by
deleting content"* — and it is exactly why coverage was made the anti-cheat. The
argument failed because dissolving sub-feature *label* structure is not the same
as dissolving sub-feature *geometry*: a fringe one pixel wide can be the edge of a
region that is 3 mm across, and voting it away moves a real boundary.

**The response is wildly heterogeneous.** −55.6%, −1.8%, +3.0% from one filter at
one radius on three photographs of real embroidery. A single global spatial scale
does not describe "photographic speckle" — the three images differ in how their
label noise is distributed, not merely in how much of it there is.

**A02 got worse.** Objects rose 3.0% and stitches 7.2%. Majority voting can *split*
a region: erode a narrow neck below the connectivity threshold and one object
becomes two. So this class of filter does not even monotonically reduce the object
count, which rules out "same idea, larger radius" as a next step.

**And the radius was already at its floor.** At these working resolutions,
`round(0.125 mm ÷ 0.26 mm/px)` is 0, so the implementation clamps to 1 px — a 3×3
window. Every number above is the *gentlest possible* version of this idea.

## 4. Stop condition

Part 55: *"If object count cannot fall by 30% without coverage falling, stop and
report that the fragmentation is content rather than quantization noise."*

**It fires.** On the one design where the object count fell far past 30%, coverage
fell with it. On the two where coverage held, the object count did not move.

The reading I take from that, stated as a claim that can be attacked: **much of
what Part 55 counted as fragmentation is content.** 336–834 objects on a
photograph is what happens when a photograph genuinely contains that many distinct
coloured areas. The tiny objects are isolated islands (Part 55: nothing merges at
0 mm) because they are isolated *things* — flecks of colour that are really there.

That does not make the machine cost imaginary. It relocates the problem: the
lever is not "recover the shape that was cut apart", because no shape was cut
apart. It is a product decision about how much of a photograph's colour detail is
worth sewing — which is a question about `max_colors` and about what the user
asked for, not a defect to be silently fixed in the label map.

## 5. What was reverted, and what ships

**Reverted:** `_smooth_labels`, `LABEL_SMOOTH_RADIUS_MM`, and the call site.
`app/` is byte-identical to Part 55.

**Ships:** `scripts/measure_r005_gates.py` — the four digitize gates on the three
tier-A photographs, so the next attempt is measured the same way without
rebuilding the harness, and so this negative is reproducible.

No test is added for reverted behaviour. The gate script is the artefact worth
keeping; a test asserting the absence of a function would pin nothing.

## 6. Gates on this part itself

| Gate | Result |
|---|---|
| Real win or clean negative | ✅ clean negative, stop condition fired |
| No content deleted to make a count fall | ✅ the change that did exactly that was reverted |
| No threshold tuned to fake a win | ✅ the radius was derived, and was at its floor anyway |
| No post-contour merging as the fix | ✅ the change was at the label map |
| No R004 work | ✅ none |
| `app/` unchanged at the end | ✅ byte-identical to Part 55 |
| Stream locks / visual baselines | ✅ 4 and 10/10 |
| Backend suite | ✅ **900 passed, 2 xfailed** — unchanged, `app/` reverted |
| `ruff check app` | ✅ 12, the standing baseline |

## 7. What I would ask for next

Not a third spatial filter. Two options, and the first is cheap:

1. **Test the content hypothesis directly.** Re-run the three photographs at
   `max_colors` 6 and 8 and measure the same four gates. If object count falls
   steeply while coverage holds, the fragmentation was colour count all along and
   the fix is a better default for photographic input — a product decision with a
   measurable answer. If coverage falls in step, §4's reading is confirmed and
   R005 should be closed as "working as intended, costs machine time".
2. **Reframe R005 as a cost problem rather than a quality problem.** Trims fell on
   all three designs even in this failed attempt (364→344, 796→741, 663→339). If
   the objects are real, the win available is in how they are *sewn*, not in how
   many there are — which is Part 48's territory, extended to cross-colour
   ordering that Part 48 deliberately declined.

I would run (1) before writing another line of engine code. It is one script run
against gates that already exist, and it can close R005 either way.
