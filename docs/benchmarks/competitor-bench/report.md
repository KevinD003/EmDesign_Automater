# Competitor benchmark (v2 Part 64)

Regenerate with `scripts/bench_competitor.py`. Every number is either
measured exactly from a stream, read from STITCHIQ objects, or marked
inferred/unavailable — nothing in between.

## Summary

| case | kind | SQ objects | SQ stitches | SQ trims | competitor stitches | competitor trims |
|---|---|---|---|---|---|---|
| 01-flat-logo | fixture | 2 | 4820 | 85 | — | — |
| 05-lettering | fixture | 6 | 1366 | 10 | — | — |
| 07-badge | fixture | 16 | 12196 | 77 | — | — |
| 03-photo-derived | fixture | 3 | 4875 | 23 | — | — |
| 08-small-detail | fixture | 15 | 4775 | 21 | — | — |
| sample-dst | machine_file | — | — | — | 26 | 14 |
| sample-pes | machine_file | — | — | — | 26 | 2 |
| angelfish-royal-present | render_only | 100 | 6504 | 108 | — | — |

## Comparison framing

Four verdicts exist: better / worse / different-but-not-clearly-worse /
not measurable. With the competitor data held today, **every numeric
cross-comparison is 'not measurable from the files available'**:
the five fixture cases have no competitor output for their artwork, the
two foreign machine files have no artwork (and are trivial test
patterns — most blocks under 4 stitches), and the render-only case has
no competitor stitch file. The one comparison the current population
supports is *visual*, on the render-only case, and any better/worse
verdict drawn from it is human judgement over the visual pack — it is
recorded in the Part 64 audit as such, not asserted here as a metric.

What would upgrade this to numeric verdicts, in order of value:
native competitor design files (objects + properties) for matched
artwork; else competitor machine files exported for artwork we can also
digitize (stream + inferred-block comparisons on matched ground).

### 01-flat-logo  (fixture)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | 2 | — |
| stitch count | 4820 | — |
| trim count | 85 | — |
| jump travel mm | 2132.1 | — |
| color stops | 2 | — |
| stitch types | TATAMI 2 | — |
| objects with holes | 1 | — |
| small objects <8mm2 | 0 | — |
| distinct angles | 2 | — |

Visual: `benchmarks/competitor-bench/visual/01-flat-logo.png`

### 05-lettering  (fixture)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | 6 | — |
| stitch count | 1366 | — |
| trim count | 10 | — |
| jump travel mm | 203.8 | — |
| color stops | 1 | — |
| stitch types | SATIN 6 | — |
| objects with holes | 0 | — |
| small objects <8mm2 | 0 | — |
| distinct angles | 2 | — |

Visual: `benchmarks/competitor-bench/visual/05-lettering.png`

### 07-badge  (fixture)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | 16 | — |
| stitch count | 12196 | — |
| trim count | 77 | — |
| jump travel mm | 2449.9 | — |
| color stops | 4 | — |
| stitch types | SATIN 13, TATAMI 3 | — |
| objects with holes | 10 | — |
| small objects <8mm2 | 2 | — |
| distinct angles | 6 | — |

Visual: `benchmarks/competitor-bench/visual/07-badge.png`

### 03-photo-derived  (fixture)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | 3 | — |
| stitch count | 4875 | — |
| trim count | 23 | — |
| jump travel mm | 1021.2 | — |
| color stops | 3 | — |
| stitch types | SATIN 2, TATAMI 1 | — |
| objects with holes | 2 | — |
| small objects <8mm2 | 0 | — |
| distinct angles | 3 | — |

Visual: `benchmarks/competitor-bench/visual/03-photo-derived.png`

### 08-small-detail  (fixture)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | 15 | — |
| stitch count | 4775 | — |
| trim count | 21 | — |
| jump travel mm | 632.4 | — |
| color stops | 4 | — |
| stitch types | SATIN 12, TATAMI 3 | — |
| objects with holes | 4 | — |
| small objects <8mm2 | 3 | — |
| distinct angles | 13 | — |

Visual: `benchmarks/competitor-bench/visual/08-small-detail.png`

### sample-dst  (machine_file)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | — | 10 |
| stitch count | — | 26 |
| trim count | — | 14 |
| jump travel mm | — | 487.3 |
| color stops | — | 2 |
| stitch types | — | unknown 10 |
| objects with holes | — | — |
| small objects <8mm2 | — | — |
| distinct angles | — | — |

> No source artwork for this file: no matched STITCHIQ side exists. Stream metrics exact; types inferred from segment statistics.

Visual: `benchmarks/competitor-bench/visual/sample-dst.png`

### sample-pes  (machine_file)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | — | 3 |
| stitch count | — | 26 |
| trim count | — | 2 |
| jump travel mm | — | 96.6 |
| color stops | — | 2 |
| stitch types | — | fill 1, unknown 2 |
| objects with holes | — | — |
| small objects <8mm2 | — | — |
| distinct angles | — | — |

> No source artwork for this file: no matched STITCHIQ side exists. Stream metrics exact; types inferred from segment statistics.

Visual: `benchmarks/competitor-bench/visual/sample-pes.png`

### angelfish-royal-present  (render_only)

| metric | STITCHIQ | competitor |
|---|---|---|
| object count | 100 | unavailable (render only) |
| stitch count | 6504 | unavailable (render only) |
| trim count | 108 | unavailable (render only) |
| jump travel mm | 1776.5 | unavailable (render only) |
| color stops | 8 | unavailable (render only) |
| stitch types | RUNNING_SINGLE 55, SATIN 39, TATAMI 6 | unavailable (render only) |
| objects with holes | 0 | — |
| small objects <8mm2 | 36 | — |
| distinct angles | 41 | — |

> Competitor render (royal-present.ru marketing photo, watermarked). No stitch file: numeric competitor columns are unavailable.

Visual: `benchmarks/competitor-bench/visual/angelfish-royal-present.png`
