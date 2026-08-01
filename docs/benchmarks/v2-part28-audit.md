# v2 Part 28 — learning from Ink/Stitch: staggered penetrations

**Date:** 2026-08-01 · Branch `claude/code-quality-improvements-hyu6dg`

Studied the Ink/Stitch project as directed. **Licence discipline first:** Ink/Stitch
is GPL — none of its code was read or copied. What was studied is its public
*documentation*: the parameter model and the behaviours it names. Two concepts
transferred; the implementations are entirely this project's own.

Sources: [Ink/Stitch fill stitch docs](https://inkstitch.org/docs/stitches/fill-stitch/) ·
[satin column docs](https://inkstitch.org/docs/stitches/satin-column/) ·
[fill tools](https://inkstitch.org/docs/fill-tools/)

## 1. The defect their docs name: the "valley effect"

Their fill documentation explains *staggers*: "stitches are staggered so that
neighboring rows of stitches don't all fall in the same column (which would
create a distracting valley effect)". Measured on our own output:

| Probe | Aligned interior penetrations |
|---|---|
| 40×20mm rectangle fill, before | **588 / 588 = 100%** |
| after (4-row stagger cycle) | **0%** |

Every fill we had ever produced punched its interior penetrations into columns
of holes — visible as ridges/valleys on the sew-out, and a genuine part of "the
fill of the thread is not perfect". The fix: interior penetrations sit on an
absolute grid offset a quarter-step per row, measured from the segment's
absolute end (not its travel start) so the stagger diagonal runs one way across
the whole fill instead of herringboning with the serpentine. End-guarded so a
split never lands nearly-in a row-edge hole; the worst end gap (1.3 steps) is
*smaller* than the old rounding-based subdivision's 1.5-step worst case.

Applies automatically to tatami, angled fills, and the parallel underlay layer
(all route through `_scanline_fill`).

## 2. The same defect was the satin cap's real blocker

Part 24b measured raising `SATIN_MAX_W_MM` and abandoned it: an 8mm cap produced
1,846 floor violations, and even a straight bar violated — the mechanism was
unknown. **Now it is known.** Locating the violating triples showed every one at
the column CENTRE: crossings wider than the 6mm machine step subdivide, and even
subdivision put every crossing's split point at the same fractions — successive
splits ~0.15mm apart down the centreline, a perforation line. The same disease
as the fill valleys, and Ink/Stitch documents the same cure (staggered split
satin stitches).

With split points staggered per crossing (quarter-step cycle, 0.3-step end guard),
re-measured:

| Probe @ cap 8.0mm | Floor violations before | after |
|---|---|---|
| Straight 8mm bar | 383 | **0** |
| 8mm ring | 769 | **0** |
| Gentle arc | 430 | **0** |
| Corpus sweep @ 6.0 / 8.0 | 303 / 1,846 | **0 / 0** |

**The cap decision, honestly:** wide satin is now SAFE to ~8mm — but the corpus
sweep shows coverage still *prefers* the current classification (interior 98.74
at cap 4.5 vs 98.28 at 8.0; satin has no border finish pass, so edge coverage
drops on objects that switch). So the default cap stays **4.5 as a quality
preference, no longer a safety limit** — and a user forcing SATIN on a wide
object via rebuild now gets a safe stream (`_satin_zigzag` got the same staggered
splits; before, that path perforated user-forced wide satin).

## 3. Corpus

| | Part 27 | Part 28 |
|---|---|---|
| Mean interior / edge | 98.73 / 98.10 | **98.74** / 98.10 |
| Spill | 12.37 | 12.37 |
| Floor / over-limit / density flags | 0/0/0 | **0/0/0** |
| Stitches | 54,905 | 55,618 (+1.3%) |
| Aligned fill penetrations | 100% | **~0%** |

Coverage identical-to-better while the sewn texture changes fundamentally — the
coverage metric cannot see penetration alignment, which is why this defect
survived 27 parts. The penetration-map image committed alongside shows it.

## 4. Studied and deliberately not taken (yet)

* **Meander/guided/ripple fills** — decorative generators; ours-to-add later,
  nothing blocking.
* **Short-stitch inset for dense curves** — their answer to concave-side
  crowding. Our Part 11-era measurement showed retraction losing on *narrow*
  columns (the shortened column dies in `_coalesce_short`); with the split-point
  discovery, the wide-satin case that needed it no longer does. Revisit only if
  a real design shows concave crowding at cap 4.5 — the corpus shows none.
* **Their parameter surface** (per-object max stitch length, stagger cycle,
  tolerance) — worth exposing in the properties panel as a follow-up.

## 5. Gates

* pytest **725 passed + 2 xfailed** (3 new: alignment share <10%, stitch-cap
  guard, wide-satin floor-zero on bar + ring)
* ruff **19** — baseline; corpus bench above; stream locks regenerated
  deliberately (every fill's interior penetrations moved — that is the feature)
