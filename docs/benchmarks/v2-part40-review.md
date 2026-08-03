# v2 Part 40 — Side-by-side review of the current output against the original

**Date:** 2026-08-03 · Rendered as thread bands (0.4mm, with loft shading), not
polylines, so it shows what will actually sew. Design as shipped today (all Part 37–39
experiments reverted).

Images: `v2-part40-review-full.png` (whole panel), `v2-part40-review-zooms.png`
(three matched crops).

---

## What is right

At full-panel scale the result is **close**. Composition, proportion and placement are
correct: the neckline opening, the trellis panel, the flower garlands down both sides,
the bottom motif and the terminal bud all land where the original has them. The palette
matches — the yellows, the two greens, the red/orange range read as the same design. A
customer would recognise it as the same artwork.

That is the digitizer's half of the job, and it is done.

## What is wrong — ranked by how visible it is

### 1. Black thread laid where the original has bare fabric — the most conspicuous defect

Every crop shows short **black dashes** scattered over the yellow neckline band, along
every trellis bar, and around the flowers. The original has no thread there at all: that
is the black garment showing between elements.

Measured: **2,925 stitches (5.1% of all sewing) sit in near-black stops**, plus
**230 `RUNNING_SINGLE` objects averaging 5 stitches each**. These come from the
dark-linework pass (Part 30), which reads the dark gaps *between* elements as if they
were drawn outlines.

Honest qualification: on a **black** garment black thread on black fabric is close to
invisible in the finished piece — so this costs thread, time, trims and object count more
than it costs looks *on this garment*. On any other fabric colour it would be glaring.
Either way the design is stitching content that does not exist.

### 2. The bead-chain border is missing entirely

Crop A. The original runs a **chain of round beads** parallel to the neckline satin on
both sides, and again around the trellis. It is a signature element of this design.
Ours does not reproduce it — the chain is simply absent, and the black dashes sit
roughly where it should be.

This is a *content* loss, not a quality loss: a row of small round dots is exactly the
class of feature the speck/detail filters discard, and it is the same family as the
"9 designs produce zero stitches" thin-stroke problem from Part 36.

### 3. Trellis bars are chain-like instead of smooth

Crop B. The original's bars are even-width satin with clean crossings. Ours are the right
shape and the diamonds are readable, but each bar is **wobbly, uneven in width, and
visibly segmented** — it reads as a chain rather than a smooth bar, and the crossings
lump. This is the fragmentation already measured (median object = 16 stitches): a bar
that should be one continuous satin column is being stitched as a run of short pieces.

### 4. Small flowers merge into masses

Crop C. The original's five-petal star flowers are individually crisp, each petal
separated by a dark line. In ours they fuse into red masses — the direction defect
already established (one angle per merged region), now visible at the element level.

### 5. Fine ornament is lost

The curling tendrils and spirals around the upper flowers in the original are largely
gone in ours, and the yellow leaf shapes at the bottom lose their internal spine
direction, reading as flat blobs rather than leaves.

### 6. Shading is flatter

The original's roses carry a smooth orange→red→yellow gradient within a single flower.
Ours banded them into discrete colour blocks. Part 31's gradient-band recovery already
narrowed this, and it is the least objectionable difference of the six.

## What this changes about the plan

The graph-stitch prompt targets direction (defects 3, 4, 5). This review says two things
should be **ahead of it**, because they are more visible and cheaper:

1. **Stop stitching bare fabric** (defect 1). This is already listed as a prerequisite in
   `PROMPT-graph-stitch-engine.md` §5 — but it should be treated as the *first* task, not
   a precondition. It removes 5.1% of sewing and 230 spurious objects, and it is a
   correctness bug, not a tuning question.
2. **Recover bead-chain / dot-row ornament** (defect 2). A repeating row of small round
   dots needs to be detected as an *element class* and stitched as a chain, rather than
   filtered out dot-by-dot as specks.

Defects 3–5 are the direction/fragmentation work the prompt already covers.

## Files

- `docs/benchmarks/v2-part40-review-full.png` — whole panel, original vs ours
- `docs/benchmarks/v2-part40-review-zooms.png` — three matched crops
- No engine change; this is a review.
