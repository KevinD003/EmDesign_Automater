# v2 Part 49 — R008: the dropped specks do not separate into ornament and noise

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** R008, with an explicit gate: *"Write down the distributions that separate
the ornament from noise. If they do **not** separate cleanly, stop and report that."*

**They do not. Stopping at step 1, as instructed.** No detector, no generator, no threshold
change. What ships is the instrumentation the attempt needed, the measurement, and the
reason it failed — including the mechanism, which is more useful than the failure.

---

## 1. The premise checked out; the separation did not

Part 48's figures were right: the panel drops **768** regions, median area **0.896 mm²**
against the 2.0 mm² floor, median bead diameter **1.07 mm**. And the ornament really is in
there — `v2-part49-dropped-specks.png` marks every dropped region on the source, and you
can see strings of markers following the neckline arc and the trellis bars.

So the beads are being filtered. The question R008 turns on is whether they can be told
apart from everything else that gets filtered. Three tests, all negative.

**Test 1 — interior-of-a-chain.** A bead in the middle of a row has two neighbours on
roughly opposite sides at roughly equal spacing. Noise does not.

| criterion | regions |
|---|---:|
| neighbours >134° apart | 206 (26.8%) |
| …and spacing within 40% | 126 |
| …and adjacent (<6 bead diameters) | **121 (15.8%)** |

Grown into runs: 77 components, **longest 10 beads**. A signature neckline border is dozens
of beads following a curve. Ten is not that.

**Test 2 — gap-tolerant growing.** Perhaps the runs break because some beads clear the
floor. So grow greedily along a direction, tolerating gaps, and sweep the permissiveness:

| max step | max turn | runs ≥5 | regions covered | longest |
|---:|---:|---:|---:|---:|
| 3.2 mm | 30° | 4 | 27 (3.5%) | 10 |
| 5.3 mm | 45° | 34 | 252 (32.8%) | 14 |
| 8.5 mm | 45° | 51 | 430 (56.0%) | 29 |
| 8.5 mm | 60° | 57 | 515 (67.1%) | 29 |

**There is no knee.** Coverage rises smoothly from 3.5% to 67% as the rules loosen. A
distinct chain population would show a jump and then a plateau — a setting where the chains
are in and the noise is still out. There isn't one, so any threshold picked here is picking
how much noise to accept, not finding the ornament.

**Test 3 — the population is wrong.** Maybe the chains look sparse because only *some*
beads fall under the floor. Combine the dropped regions with the small kept objects
(≤8 mm², four times the floor) and re-run test 1:

| population | n | interior-of-chain |
|---|---:|---:|
| dropped only | 768 | 15.8% |
| dropped + small kept | 1,297 | **15.0%** |

No better. Hypothesis refuted.

## 2. Why it does not separate — the useful part

**529 of the panel's 771 objects are already small** (≤8 mm²). On a dense floral panel,
"small round region" is not a distinguishing feature: it describes the flower centres, the
petal tips, the leaf dots and the beads equally. A bead chain is small round regions in a
row — but so is a row of flower centres along a stem, and so is the fringe of a petal.

There is a second mechanism, found while building the test fixture. Dots below roughly 4 px
**never reach the drop log at all** — they are removed before contouring:

| dot radius | hoop | regions in the drop log |
|---:|---|---:|
| 2 px | 40×40 | 0 |
| 3 px | 40×40 | 0 |
| 5 px | 40×40 | 24 |
| 5 px | 130×180 | 0 (kept as objects) |

So a bead chain is split across three populations — beads kept as objects, beads dropped as
specks, and beads that vanish before either — and no single one of them contains the whole
chain. That is the structural reason the runs are short, and it is not fixable by looking
harder at the drop log.

**What would be needed instead:** detection at the mask stage, before regions are cut apart
by colour clustering and before anything is filtered — a repeated-motif-along-a-path
detector, which is a different and larger piece of work than "group the specks". That is a
real finding and it changes what R008 is, so it is recorded rather than worked around.

## 3. What ships

`_DROP_LOG` now records each dropped region's **centroid** alongside its area and
perimeter. Before, the log could answer "how much was dropped" and "how big" but never "was
it structured", which is the question any ornament recovery starts from.

Re-deriving the positions outside the pipeline is not equivalent, and that is the reason
this is instrumentation rather than a script: the morphological open inside the contour loop
removes single-pixel noise, so a naive re-derivation on the raw cluster mask counted
**25,822** regions where the pipeline drops **768**. My first measurement did exactly that
and was wrong by 34×; the numbers above are from the instrumented pipeline.

## 4. What explicitly did not happen

- **The speck floor was not lowered.** Part 36 measured that 1.0 mm² adds objects without
  recovering detail, and the brief ruled it out. Nothing here changes it.
- **No detector was shipped on a threshold that "looked about right".** The sweep in test 2
  would have let me pick 8.5 mm / 45° and claim 56% recovery. Without a knee, that number
  means "I accepted this much noise", and it would have been found later as false beads
  scattered over the flowers.

## 5. A performance regression I shipped, and the fuzz suite caught — again

The first version of the centroid took `cv2.moments` over `probe`, the **full-size** filled
image, once per dropped region. On a design with a few hundred specks that is invisible.
On random noise, where one colour holds tens of thousands of them, it took the fuzz suite's
1500×1500 post from a measured **~16 s to over ten minutes**.

`test_random_noise_palette_stress_never_5xx` failed — 28 minutes into a full run, because
the suite runs under `-x` and everything before it passed. Nothing else caught it: the
targeted tests, the locks, the visual baselines and ruff were all green, exactly as in
Part 48.

Fixed by taking moments over the **contour** rather than the filled image, which is
O(points on the outline) — a handful for a speck — with a mean-of-points fallback for a
degenerate outline whose area moment is zero. Fuzz suite back to 7 passed in 4m39s.

**This is the second performance regression in this same loop in two parts.** Part 48's was
an unbounded O(n²) ordering over pre-filter contours; this one is a per-region full-image
operation in the same place. The pattern is that the contour loop runs once per region
*before* filtering, so anything added to it is multiplied by the noise count, not the design
count. A cost test now sits in the fast file rather than only in a 28-minute run.

## 6. Verification

No pipeline behaviour changed — the drop log is diagnostic and nothing reads it in the
stitch path.

| Gate | Before | After |
|---|---|---|
| Backend suite | 849 passed, 2 xfailed | **854 passed, 2 xfailed** (+5) |
| Fuzz suite | 7 passed | **7 passed** (regressed to a >10 min hang, then fixed) |
| `ruff check app` | 12 | **12** |
| Stitch stream locks | 4 pass | **4 pass, unchanged** |
| Visual baselines | 10/10 | **10/10, unchanged** |

An earlier draft of this section quoted "853 passed" from arithmetic — 849 plus the four
tests written at the time — before the run finished. It was removed before committing, and
it would have been wrong **twice over**: that run came back **1 failed, 769 passed**,
stopping at the fuzz test above, and the final count is **854**, because fixing the
regression added a fifth test. Both errors point the same way. Quoting a count you have not
seen is the habit this series keeps catching in the briefs it reviews, and it was one
command away from appearing here.

Tests in `tests/test_part49_drop_log_position.py`: every entry carries area, perimeter and
position; the positions are real mm coordinates with spread rather than a constant; the log
is cleared between runs; output is deterministic.

One of those tests was wrong on its first pass and is worth recording — it asserted the
centroids lie inside the design's stitched extents. A dropped region is by definition
somewhere nothing was sewn, so on the fixture the dots sit outside the surviving rectangle
entirely. The assertion, not the code, was wrong.

## 7. Next

R008 as scoped is not the next move; it needs re-scoping around motif-along-a-path
detection at the mask stage, and that is comparable in size to the direction field.

Given both large items now need scoping, **R004-impl D0/D1** is the better next step — the
direction instrument and the field visualised while consumed by nothing, per
`docs/PROMPT-direction-field.md`. It has a written plan, a stated abandon condition, and its
first two stages change no stitch output at all.
