# v2 Part 39 — Executing the graph-stitch prompt: baseline confirmed, and a new engine defect found

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Input:** `docs/PROMPT-graph-stitch-engine.md`, run as a work order.

**Outcome: no engine change shipped.** Two things were established that change what the
next attempt should do, and one of them is a defect nobody had named.

---

## 1. Baseline reproduced, and it is not measurement noise

Per the prompt's mandatory first step, the instrument self-tested (worst error 1.4° on
known stripes) and the baseline reproduced **exactly**: mean **49.9°**, median 54.1,
within-15° **15.8%**, within-30° 29.5% on `A03_real_neckline_panel.png`.

The open question was whether that ~50° was partly an artifact of imperfect registration
— some colour stops land on source content 100–233 BGR away. **It is not.** Splitting
every compared segment by registration quality:

| Subset | n | mean | median | within-15° |
|---|---|---|---|---|
| Well-registered (our thread matches the source colour there) | 17,336 | **50.3°** | 55.3 | 15.8% |
| Mis-registered / knockout (colour mismatch) | 22,499 | 47.8° | 50.9 | 17.4% |

Both halves sit at ~50°. **The direction error is real**, and the target in the prompt is
legitimate. This closes a caveat the previous audit had to leave open.

## 2. Where the error lives — satin, by stitch count

The prompt's §1 lists 560 satin objects against 224 tatami, which understates the
problem: by **compared segments** it is satin **30,332** vs tatami **3,794**, roughly 8:1.
Any change that touches only fills cannot move the headline number — which is exactly why
the Part 38 attempt landed inside the noise. Confirmed, and worth carrying forward.

## 3. The experiment — measured angle overriding an arbitrary satin axis

Satin fragments (median **26 stitches**) take their direction from a medial axis that, on
a stub, carries no information. The source *shows* the real direction. So: where the
source gives a coherent direction over a region, refuse satin and fill at the measured
angle.

Measured on the panel — **every no-regression gate improved**:

| Metric | Baseline | Blanket override |
|---|---|---|
| Direction mean | 49.9° | **42.5°** |
| Direction median | 54.1° | **46.7°** |
| within-15° | 15.8% | **20.5%** |
| within-30° | 29.5% | **35.8%** |
| Interior | 97.10 | **97.30** |
| Edge band | 94.20 | **96.20** |
| Spill | 16.50 | **16.00** |
| Floor / density | 0 / 0 | 0 / 0 |

On the numbers alone this ships. **Looking at it says otherwise.**

## 4. The defect this exposed — a refused satin FLOODS its enclosed gaps

`v2-part39-lattice-flood.png` shows the lattice trellis under both. The baseline stitches
open diamonds with bare fabric between the bars, as the source does. The override **fills
the diamonds solid with thread**, turning an open trellis into a yellow field.

The mechanism: a satin path follows the medial axis, so enclosed gaps never matter. A
fill takes the contour-filled region minus its detected `hole_contours` — and where those
holes are not captured, the fill floods straight across them. **Refusing satin therefore
silently changes what counts as "inside" the region.**

Worse, and the reason this is worth writing down: **the aggregate metrics got better while
this happened.** Filling gaps raises interior and edge coverage, and the extra thread
still sits inside the union outline, so spill *fell*. This is the same failure mode the
project has hit repeatedly in another disguise — a change that alters what the metric is
computed over stops being comparable. Here it took a rendered picture to see it.

**Attempt to salvage it:** keep satin wherever the column is genuinely longer than it is
wide (`axis_len / width >= 3`), overriding only stubs. That preserved the lattice but
gave back almost all the gain — direction **48.6°** (from 49.9), and **spill rose to
17.20**, failing the ≤16.50 gate. Rejected too.

## 5. What the next attempt must do differently

1. **Fix the hole capture first.** Before any satin→fill routing, a region's enclosed gaps
   must survive the conversion. This is a standalone bug with a standalone test: refuse
   satin on a lattice and assert the diamonds stay unstitched. Until it is fixed, every
   direction experiment that touches satin will be scored on flooded designs.
2. **Add gap-fidelity to the gates.** Interior/edge/spill cannot see thread laid where the
   source has none. A "bare-fabric agreement" metric — share of stitches landing on
   source pixels that are substrate — would have failed the blanket override immediately
   instead of rewarding it.
3. **Then pursue G1 properly.** The direction gain is real (49.9 → 42.5 from a single
   angle per region). A per-pixel field with rows following it should beat that, and it
   does not need to refuse satin at all — it can re-aim the satin column itself, which is
   where 8 of every 9 compared segments live.

## 6. Guardrails

No engine change shipped: 10/10 stream locks byte-identical, ruff at the 19 baseline,
corpus untouched. Deliverable is this audit, the lattice evidence image, and the two
findings in §1 and §4.
