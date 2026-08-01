# v2 Part 26 — curved fills to parity, and a dashboard that shows the truth

**Date:** 2026-08-01 · Branch `claude/code-quality-improvements-hyu6dg`
Re-checked against the competitor benchmark
([`../COMPETITIVE-GAP-ANALYSIS.md`](../COMPETITIVE-GAP-ANALYSIS.md)), closed the
remaining curved-fill gap, and rebuilt the dashboard to surface every measurement
this project produces. Frontend work follows the data-viz method (form → colour by
job → validated palette → mark specs → hover → accessibility → render and look).

## 1. Curved fills — the last row of gap A1 closes

Hatch/Wilcom/Embird market contour, spiral and radial "curved fill effects".
Part 24b shipped contour; this part ships **spiral** and **radial**, selectable
per object in the properties panel (rebuild path — the ten-fixture corpus is
untouched by construction, and the stream locks confirm it).

Measured on a 30mm disc probe (thread-band metric, 0.4mm thread / 0.4mm pitch):

| Fill | Jumps | Interior | Spill | Property |
|---|---|---|---|---|
| Straight 45° | 77 | 100.0% | 2.1% | baseline |
| **Spiral** | **6** | 100.0% | **0.8%** | ONE continuous path — zero interior row-ends, the strongest answer to ragged rows on round shapes |
| **Radial** | 122* | 100.0% | 1.5% | sunburst spokes, rim-spaced at the row pitch (*in-region jumps become travel downstream) |

**A defect caught by the density metric before it shipped:** the first radial
version sent every 4th spoke to r=0 — **59 penetrations in ONE 0.5mm cell**, an
order of magnitude past the flag level of 14. Fixed with a hub keep-out (no spoke
enters 2 pitches of the centre) plus a short spiral cap over the hub: max
7/cell, within the corpus's healthy range. The test pins ≤ 12.

Both fills: 100% interior coverage, inside-region guarantee, machine-valid
segments, rebuild round-trip (switch type → Apply → type survives). 5 new tests.

## 2. Dashboard — every measurement, where the user looks

New `DesignAnalytics` section on the dashboard (screenshots committed alongside):

* **Six stat tiles** — quality score/grade, stitches + physical size, est. machine
  time (charging trims at 2.5s and colour changes at 15s, not just stitch count),
  colours + changes, trims + jumps, travel share + longest jump.
* **Stitch-length histogram** — 0.5mm bins from the real stream; single series in
  the validated palette's series-1, no legend (one series), peak-only direct
  label, per-bar hover tooltips, recessive baseline, muted axis.
* **Thread usage by colour** — per-stop sewn length; bar colour here IS the data
  (the actual thread hex), names and lengths in text tokens.
* **Digitizer warnings** — the Part 25 loss/colour warnings repeated where
  decisions get made, not just in the studio.
* **Capabilities vs desktop suites** — the honest scoreboard, every row traceable
  to a measured audit; includes our two `no`s (photo digitizing, stitch-level
  editing) and one `partial` (lettering) in plain sight.

Chart discipline per the dataviz method: colour by job (single-series token /
data-inherent thread hex / reserved status colours with icon + word, never colour
alone), text in text tokens, thin marks with surface gaps and rounded data ends.
Rendered and inspected: one clipped peak label and one clipped table found and
fixed at the screenshot stage.

## 3. Properties panel — the fill family is now interchangeable

TATAMI ⇄ CONTOUR_FILL ⇄ SPIRAL_FILL ⇄ RADIAL_FILL ⇄ APPLIQUE, with plain-language
labels ("Contour — rows follow outline", "Spiral — one continuous path"). Design
polish pass: dataviz token layer, focus-visible outlines, hover states.

## 4. Scoreboard after this part

| Gap analysis item | Status |
|---|---|
| A1 fill direction (angle + contour + spiral + radial) | **closed** |
| A2 underlay selection | closed (Part 24) |
| Travel/locks/trims (blockers #3) | closed (Part 25) |
| SVG vector import (blockers #5) | closed (Part 25) |
| A4 lettering engine | **open** — TrueType raster path only |
| A3 photo digitizing | **open** |
| Stitch-level editing | **open** |

## 5. Gates

* Backend **715 passed + 2 xfailed** (5 new curved-fill tests); ruff **19** — baseline
* Frontend **123 passed** (9 new analytics tests); `tsc --noEmit` clean
* Ten-fixture corpus untouched (curved fills are rebuild-only); stream locks green
* Live UI exercised end-to-end: digitize fixture 07 through the running app → dashboard renders warnings, tiles, charts, capabilities
