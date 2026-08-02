# v2 Part 34 — The partial matte: a full neckline panel, stitch files, and the stitch-out

**Date:** 2026-08-02 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Request:** stitch file + animation + renders for an uploaded full-length floral
neckline panel (gold lattice trellis, red/orange roses, on black).

---

## 1. What the first run exposed — and why every gate before it passed

The first digitize produced a valid stream… of a quarter of the design: an
arbitrary diagonal swath of the lattice plus the bottom flowers. Measured cause:

| Hypothesis | Ink recall | Foreground share | Verdict |
|---|---|---|---|
| U2-Net matte | **0.203** | 11.5% of frame (ink is 40.6%) | won the tier race — wrongly |
| Classical flood tier | **1.000** | 56.0% | never consulted |

The Part 32 ink-recall floor is 0.2 — calibrated against a *total* failure
(recall 0.004). This matte came in at **0.203, one point above the floor**: a
*partial* matte, a failure mode the calibration set simply didn't contain.
`_reclaim_ink` couldn't repair it either — the missed embroidery is one huge
border-touching component, the exact signature its caps correctly refuse.

## 2. Why "raise the floor" is the wrong fix

The corpus's legitimate minimum is fixture 09 at **0.407** (its photographic
backdrop counts as ink, so a low-but-real recall is correct there). No fixed
threshold splits 0.203 from 0.407 with real safety margin — Part 32's audit
already recorded catching a 0.5 draft for exactly this reason.

## 3. The fix: the tier that explains the ink wins

Full calibration over every input (corpus + peacock + both necklines):

| Input | Matte recall | Flood frac | Flood ink recall |
|---|---|---|---|
| Fixtures 01–08, 10 | 0.709 – 1.000 | — | — (never reach the comparison) |
| Fixture 09 (photo backdrop) | 0.407 | 0.479 | **0.656** |
| Neckline 1 (Part 32 failure) | 0.004 | 0.433 | 0.998 |
| **Neckline panel (this part)** | **0.203** | 0.560 | **1.000** |

The structure is unmistakable: both failures have a flood tier that explains
≈all the ink; the one legitimate low-recall matte (fixture 09) has a flood tier
that explains only 0.656 — flood *cannot* model a photographic backdrop. So the
new rule is comparative, not absolute:

> A matte missing over half the ink (`_MATTE_COMPARE_RECALL = 0.5`) is overruled
> **only if** the flood tier explains ≥ 95% of the ink
> (`_FLOOD_EXPLAINS_INK = 0.95`) with a sane foreground fraction.

Margins: 0.297 below the recall threshold (failure 0.203), 0.294 below the
flood-explanation threshold (fixture 09's 0.656). Every corpus tier decision is
unchanged — matte recalls ≥ 0.709 never enter the comparison, fixture 09 enters
and survives — so the stream locks stay green with zero regeneration.

## 4. The delivered design (after the fix)

| Metric | Value |
|---|---|
| Size | **135.1 × 311.7 mm** (large-format 360×350 hoop) |
| Stitches | **54,519** sewn (+1,688 jumps, 917 trims, 21 colour changes) |
| Objects | 851 |
| Threads | **11 distinct** across 22 stops (layering re-opens stops) |
| Gradient recovery | +3 shades the colour cap had merged (Part 31) |
| Digitize time | 37.3 s |
| Exports | DST 184 KB · PES 373 KB · EXP 131 KB — all round-trip through the reader at 135×312 mm, 22 stops |

Outline check (Part 33) passed first attempt — the colour plan's sketch verifies
against the artwork's own lines, so no re-plan was needed.

Honest notes: the source is itself a *render* of an embroidery design at
1689 px for ~312 mm of height, and the fine-detail warning fires correctly —
the dot-chain necklace borders and 1 px stem tendrils are at the edge of what
this stitch length can carry; the lattice trellis digitizes as satin bars whose
crossings merge where the source's do; black flower centres are knockouts
(base fabric on a black garment), matching Part 32's neckline verdict.

## 5. Guardrails

pytest full suite green (2 new partial-matte tests; see STATUS row for count) ·
ruff at baseline · stream locks byte-identical (tier decisions unchanged —
verified by calibration before the code was written).

## Files

- `apps/backend/app/services/segmentation.py` — comparative partial-matte rule
  (`_MATTE_COMPARE_RECALL`, `_FLOOD_EXPLAINS_INK`) with calibration recorded
- `apps/backend/tests/test_part34_partial_matte.py` — both directions pinned:
  partial matte loses to a flood that explains the ink; fixture-09-shaped
  evidence keeps its matte
- `docs/benchmarks/v2-part34-neckline-panel.png` — source vs stitched render
