# Competitive gap analysis — why STITCHIQ output still reads as "auto-digitized"

**Date:** 2026-07-31 · Measured against the codebase at `e8f9cc3`, not against intentions.
Companion to [`COMPETITOR-COMPARISON.md`](./COMPETITOR-COMPARISON.md) (feature matrix). That
document answers *"do we have the feature?"*; this one answers *"why does the stitching look
different?"* — which is the question the output actually raises.

Every "STITCHIQ today" cell below is backed by a grep, a measurement, or a live run, cited inline.

---

## A. The four gaps that cause the visible difference

Ranked by how much each one changes what a person sees. These are not feature checkboxes — they
are the mechanisms behind "it doesn't look like real embroidery yet".

| # | Gap | STITCHIQ today (measured) | Wilcom / Hatch / Embird | Why it shows | Effort |
|---|---|---|---|---|---|
| **A1** | **Fill direction is a single global angle** | **Every tatami fill is emitted at 0°.** `stitch_angle=round(rect[2],1) if is_satin else 0.0` (digitizer.py:883) — measured on the new coffee emblem: all 5 fills at `0.0°`. | Angle per object, set from the shape's own geometry; plus **contour fill** (rows follow the outline), **radial**, **spiral**, **wave** ([Hatch curved fills](https://hatchembroidery.com/resources/blog/how-to-use-curved-fills-to-create-amazing-effects), [Embird parallel/contour fills](https://www.embird.net/studio/manual/3075par_fill.htm)) | Real embroidery catches light along the thread. One global angle makes every shape reflect identically, so a logo reads as flat stripes — the "printed, not stitched" look. A round badge stitched in horizontal rows is the single most obvious tell. | **M** — angle from each region's principal axis is ~30 lines; contour fill is a new generator |
| **A2** | **Only 2 of 6 declared underlay types are ever produced** | `UnderlayType` declares NONE/CENTER_WALK/EDGE_WALK/DOUBLE_ZIGZAG/PARALLEL/CONTOUR, but only two are assigned: `CENTER_WALK` for satin, `EDGE_WALK` for fills (digitizer.py:784, 820). Measured on the emblem: `{CENTER_WALK: 10, EDGE_WALK: 5}`. **DOUBLE_ZIGZAG, PARALLEL and CONTOUR are enum values with no generator.** | Underlay chosen by *cover stitch type, object shape and fabric*, commonly two layers combined (edge run + tatami, or zigzag + contour); width-dependent rules (centre-run <2mm, edge-run 2.5–3.5mm, zigzag >4mm) | Underlay is what makes satin sit **up** off the fabric. One flat running stitch under everything gives the thin, sunken look, and on knits/fleece the top stitching disappears into the pile. | **M** — the enum values already exist; each is a generator + a selection rule |
| **A3** | **No photographic / gradient digitizing** | Zero implementations: grep for `photostitch\|dither\|halftone\|stipple\|floyd` across `app/services/` returns **nothing**. A photo becomes flat k-means colour blocks. | PhotoStitch / Color PhotoStitch (Wilcom), PhotoFlash + Reef PhotoStitch (Hatch), Sfumato (Embird) — density-modulated or interleaved rows that reproduce tone | Any customer uploading a photo, portrait, or a logo with a gradient gets posterised blocks. This is a whole product category we return nothing useful for. | **L** — a real feature, but a well-understood one (density-modulated rows) |
| **A4** | **No digitized font library or lettering engine** | Lettering renders a **system TrueType** through the raster digitizer (`lettering.py`), then classifies like any image. No glyph outlines, no kerning tables, no baselines. Measured consequence: sub-3mm type leaves blobs rather than clean satin. | 62–250 **hand-digitized** fonts with per-glyph satin, stitch-aware kerning, 9 baseline types, auto letter-spacing by size | Lettering is most of commercial embroidery. Rasterising a font throws away the outline the satin should follow, so small text can never be as clean as a glyph digitized once, properly, and reused. | **L** — the single biggest feature gap, and the one competitors market hardest |

## B. Where we are already competitive or ahead

Stated so the plan targets real gaps rather than re-doing solved work.

| Capability | Status | Evidence |
|---|---|---|
| Machine-safety measurement | **Ahead of every competitor** — none publishes an equivalent | Enforced 0.30mm same-side penetration floor, 12.7mm limit, per-cell density; 0 violations corpus-wide, CI-checked |
| Satin quality on strokes | **Competitive** | Edge-bounded columns between paired boundaries, mitred apexes, boundary-paced pitch (Parts 4–11) |
| Fill edge finish | **Competitive** | Satin border on fills (Part 15) — the pro finish; 100/100 interior+edge on 4 fixtures |
| Fabric profiles | **Competitive** | 12 fabrics × {pull, density, underlay step, inset}; Wilcom/Hatch vary by object group too (see C3) |
| Export formats | **Competitive** | DST/PES/PEC/JEF/EXP/VP3/XXX/U01/CSV, round-trip tested; verified live on new art |
| Quality reporting | **At parity with EmbroidAI, ahead of the desktop suites** | 0–100 score + findings, auto-run, in the package ZIP |
| Determinism | **Ahead** | Same input ⇒ byte-identical output, locked by hash tests |

## C. Second-order gaps (visible to a professional, not to a casual user)

| # | Gap | STITCHIQ today | Competitors | Effort |
|---|---|---|---|---|
| C1 | Corner quality on small shapes | `_smooth_contour` rounds sharp corners of small inner shapes — visible as octagons on the VERTEX diamond | Corner detection preserves vertices, mitres them | S |
| C2 | Sub-3mm type leaves blobs instead of dropping cleanly | Measured on the new emblem: "SINCE 2019" (~2.7mm) → dark blobs | Minimum-size warning at digitize time; auto-suggest a larger size | S |
| C3 | Fabric values are flat per fabric | One profile per fabric | Hatch varies values by **object group** (tatami / wide satin / narrow satin / lettering); Wilcom also by object size | S–M |
| C4 | Same-colour detail pass shows as a duplicate thread stop | Deferred detail (Part 16) opens a second stop of the same hex | Sequencing merges same-colour blocks where the overlap allows | S |
| C5 | Travel/jump strategy | Trim + jump between objects; branch chaining reduced jumps 17% | Wilcom **Branching**: one entry, one exit, one trim per group, travel runs hidden under later stitching | M |
| C6 | Appliqué / 3D foam / trapunto | `APPLIQUE` handled in rebuild only; no foam or trapunto | Full workflows incl. foam-specific satin caps | M each |
| C7 | Stitch-level editing | Object-level only (density, angle, underlay, pull) | Individual stitch insert/move/delete | M |

## D. What is *not* the gap (measured, so we stop chasing it)

| Suspected | Verdict |
|---|---|
| "Coverage/density is wrong" | **No.** Interior + edge band are 100/100 on 4 of 10 fixtures and ≥95 on most; density is fabric-aware |
| "Stitches are unsafe" | **No.** 0 floor violations, 0 over-limit, 0 flagged density cells corpus-wide |
| "Colour separation is broken" | **Mostly no.** k-means + median representatives are accurate; the real defect there was the neural matte deleting elements, fixed in Part 22 |
| "The renderer lies" | **Fixed** (Part 14) — previews had understated output since v1 |

## E. Recommended order

Sequenced by *visible improvement per unit of risk*, not by feature glamour.

| Order | Item | Why first |
|---|---|---|
| **1** | **A1 — per-object fill angle** from each region's principal axis | Biggest visual change for the least code; every fill in every design improves at once; no new stitch type needed |
| **2** | **A2 — underlay selection** (zigzag/double-zigzag by column width + fabric) | The enum values already exist; makes satin sit up and fixes the sunken look on knits/fleece |
| **3** | C1 + C2 (corners, clean sub-3mm drop) | Small, contained, removes two visible defects seen on the new-art test |
| **4** | **A4 — lettering engine** (glyph outlines → satin, kerning) | Largest gap and largest effort; do it once the cheap wins have landed |
| **5** | **A3 — photo digitizing** | Opens a new category; independent of the above |

**Guardrail for all of them:** the 10-fixture corpus must stay byte-identical or better, floor
violations at 0 — the same bar that reverted a bad optimization in Part 20 and passed a good one in
Part 21.

## Sources

- [Hatch — curved fills (contour/radial/spiral/wave)](https://hatchembroidery.com/resources/blog/how-to-use-curved-fills-to-create-amazing-effects)
- [Embird Studio manual — parallel & contour fills](https://www.embird.net/studio/manual/3075par_fill.htm)
- [Hatch Digitizer — feature set](https://hatchembroidery.com/products/hatch-embroidery/digitizer)
- [Wilcom techniques — stitch angle / reshape](https://www.digitemb.com/blog/useful-techniques-in-wilcom/)
- [Contour fills in Wilcom/Hatch — the "flow" effect](https://embroideryhooping.com/blogs/articles/contour-fills-in-wilcom-hatch-digitize-blocks-the-clean-flow-effect-without-turning-it-into-a-satin-mess)
- [Digitizing gradients and shading](https://360digitizingsolutions.com/how-to-digitize-gradient-and-shaded-effects-in-embroidery/)
- [Machine embroidery fill stitch guide](https://embroiderylegacy.com/the-ultimate-machine-embroidery-fill-stitch-guide/)
