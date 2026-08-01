# v2 Part 27 — the peacock test: photographed embroidery as input

**Date:** 2026-08-01 · Branch `claude/code-quality-improvements-hyu6dg`
A user-supplied photograph of a REAL stitched patch — thread sheen, shading,
fuzzy edges — the hardest raster input class. First run confirmed the complaint
("the fill of the thread is not perfect") and found something worse. Two fixes,
each measured, each improving the corpus or leaving it untouched.

## 1. What the first run produced

| Metric | Value |
|---|---|
| Objects | 86 — **the entire left branch with flowers was MISSING** |
| Tail | shattered into navy shreds with green speckle |
| Spill | 36.8% |

## 2. Fix 1 — the matte was rejecting real elements on two rules at once

The dropped branch was ONE 12,952px component: **5.90% of frame** (over the 2%
reclaim cap) and **attached** to the kept subject (the bird stands on it — and
attached components were assumed to be the matte's own 1px edge fringe).

Both rules were re-derived from measurement:

* **Border contact replaces the blanket area cap.** Fixture 09's photographic
  backgrounds — the reason the 2% cap exists — measure 6.94% and 9.19% and
  **both touch the frame border**; a dropped artwork element floats free. Interior
  (border-clear) components now reclaim up to 8%.
* **Thickness separates fringe from element.** A matte-edge fringe is 1–2px
  thick by nature; the branch has real body. Attached components ≥4px max
  inscribed radius are reclaimable; Part 22's fringe verdict (reclaiming it cost
  fixture 05 −0.5 interior / +2.2 spill) is preserved by the same rule.

**Corpus effect: an improvement, not a regression.** The matte had been silently
dropping thick attached elements in the corpus too — fixture 04 recovered 559px
of real linework (spill 48.1 → **46.0**), fixture 03 edge +1.3, fixture 08 edge
+0.6. Floor/over-limit/density all still 0. Stream locks regenerated deliberately.

## 3. Fix 2 — thread sheen shatters quantization; smooth it, but only when measured

A photo's colour areas carry shading that k-means splits into speckle islands
(341 fragments ≥50px on the peacock). Mean-shift posterization fixes it — but
must never touch flat artwork. The gate is **measured interior texture**, and it
was wrong twice before it was right:

| Attempt | Defect |
|---|---|
| Whole-foreground local stddev | Confounds texture with EDGES: fixture 04's thin linework scored **99.2** — ranked more "textured" than the actual photo of thread (34.7) |
| Interior-only, measured at work resolution | The 2× granularity upscale smooths texture **7.43 → 5.86**, under the 6.0 gate — the fix silently never ran |
| Interior-only, measured at SOURCE resolution | Corpus 0.00–4.10, peacock 7.43, gate 6.0 — **separation by measurement** |

Mean-shift parameters chosen by counting fragments: raw 341 → sp10/sr40 218 →
**sp14/sr52 159** (triple bilateral managed only 226).

## 4. Result on the peacock

| | First run | Final (8 colours) |
|---|---|---|
| Composition | left branch **gone** | complete — branches, flowers, leaves, crest |
| Tail | navy shreds | cohesive field, eye motifs read correctly |
| Spill | 36.8% | **20.1%** |
| Floor / density flags | 0 / 0 | 0 / 0 |
| Colour-count contract | silent | warned (8 stops / 6 threads, deferred detail explained) |

Honest remainder: edges are fuzzier than flat-art output (the photo's own edge
texture), and a photograph of embroidery is still reconstructed — a vector or
flat-art source of the same design would digitize cleaner. This part makes the
photo path *usable*, not equal to the vector path.

## 5. Gates

* pytest **722 passed + 2 xfailed** (7 new: texture-gate ranking, fringe-vs-element, border-vs-interior reclaim)
* ruff **19** — baseline; corpus bench: interior +0.01, edge **+0.19**, spill **−0.22**, floor 0
