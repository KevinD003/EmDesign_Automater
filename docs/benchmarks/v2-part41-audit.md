# v2 Part 41 — The garment is not a thread

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Instruction:** "We never do the thread for background. It's a black cloth. Do only for
the design."

Correct, and it was the top defect in the Part 40 review. Fixed.

---

## 1. What was happening

On the black neckline panel, **2,928 stitches — 5.1% of all sewing — were laid over bare
fabric**: the black cloth showing *between* the design's elements, rendered as black
thread. Two independent paths produced it.

**Path A — a colour cluster the same colour as the cloth.** The substrate estimate is
BGR (2,2,2); the offending stops sat **10.5** away, inside the 12.0 `SUBSTRATE_DELTA`, so
the rule already saw them. But it only dropped *large* garment-coloured regions and kept
small ones as "knocked-out detail" — a catchlight in a pupil, a letter counter. On this
design the small garment-coloured regions are the **gaps between petals**.

That default was wrong for embroidery. You do not stitch the background colour; you let
the cloth show. Now a garment-coloured cluster is not stitched **at all** on raster
input. SVG input is unchanged — a white shape on a white page is artwork the file states
outright, and Part 25 measured this rule deleting exactly that.

**Path B — the dark-linework pass, and it was the bigger half.** Part 30 added a
black-hat pass to stitch outlines darker than their surroundings. On a dark garment
**nothing can be darker than the cloth**, so it finds the gaps between elements and
traces the garment itself: 2,644 stitches in 230 running objects.

Worth recording because it nearly fooled the fix: dropping the black *colour stop* alone
removed only 284 stitches, because the linework simply **recoloured to the next-darkest
thread** — which is worse, since that thread is visible on bare cloth. The pass has to be
skipped outright when the substrate is dark (`DARK_CLOTH_LUM = 60`).

## 2. Result

| | Before | After |
|---|---|---|
| Sewn stitches | 57,027 | **54,099** (−2,928) |
| Objects | 1,014 | **768** (−246) |
| Trims | 1,080 | **837** (−243) |
| Colour stops | 22 | **19** |
| `RUNNING_SINGLE` objects | 230 | **0** |
| Interior coverage | 97.10 | **97.10** |
| Edge band | 94.20 | **94.20** |
| Spill | 16.50 | 16.60 |
| Floor / density flags | 0 / 0 | **0 / 0** |

**Less thread, less machine time, 243 fewer trims — with coverage identical.** Nothing of
the design was lost; only fabric that should never have been covered.

`v2-part41-no-background.png` shows it: the black dashes are gone from the trellis bars
and the neckline band, and both now read as clean thread on bare cloth, much closer to
the original.

## 3. Scope — this touches dark-garment designs only

**All 10 byte-identity stream locks are unchanged.** No corpus fixture is on dark cloth,
and none had kept garment-coloured regions, so the flat-art corpus is bit-for-bit
identical. Tier A of the 100-design corpus re-run: 13 designs, **0 errors, 0 empty,
interior median 99.05 (unchanged), floor 0, over-limit 0**.

Dead code removed with it: `_drop_large_substrate_regions` (37 lines) and
`SUBSTRATE_ENCLOSED_MAX_AREA`, both of which existed only to decide *which* garment
regions to keep. There is no longer such a decision.

## 4. Tests

`tests/test_part41_no_background_thread.py` pins the rule in both directions:

- no colour stop may be within `SUBSTRATE_DELTA` of the cloth;
- no `RUNNING_SINGLE` linework on a dark garment;
- **light cloth still gets its linework** — the guard is about dark cloth, and Part 30's
  outline pass must survive on white;
- the design itself is untouched — both elements still stitch, over 500 sewn stitches.

## 5. Still open (from the Part 40 review)

Unchanged by this part, in priority order: the **missing bead-chain border** (content
loss), trellis bars reading as chains rather than smooth satin, small flowers fusing into
masses, lost tendrils, and flatter shading. The direction work in
`PROMPT-graph-stitch-engine.md` covers the last four.

## Files

- `apps/backend/app/services/digitizer.py` — substrate clusters skipped; dark-linework
  guard; two dead symbols removed
- `apps/backend/tests/test_part41_no_background_thread.py`
- `docs/benchmarks/v2-part41-no-background.png`
