# Session review — v2 Part 11

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part11-audit.md`](./benchmarks/v2-part11-audit.md)

## Headline

**Penetration-floor violations: 2 → 0.** Zero across the ten-fixture corpus and all three probes.
The metric was not changed to get there — its only edit swaps a literal `0.9` for an import of the
same value, so the count means exactly what it meant in Part 10.

## What was asked, and what happened

| Item | Result |
|---|---|
| Delete `_MITRED_POINTS` / `_mitre_key` for real | **Done**, diff hunk pasted in the audit §0 and the repo grepped |
| Merge the duplicated zigzag constant | **Done** — digitizer owns it, metric imports it, pinned by an identity test |
| (a) Targeted fix for the underlay double-back | **Done, closed completely** — cost two points corpus-wide |
| (b) Argue whether the floor should apply to running stitch | Argued in audit §5 even though (a) succeeded; **not exercised**, nothing excluded |
| Report the final count and what it means | Audit §4 |

## The part worth reading

The instinct here was to call this a metric bug — the zigzag test's own docstring says it excludes
"any stitch sequence that advances along a line", and a running stitch is exactly that. Measuring it
gave a stronger and less convenient answer:

> Locally, a 180° running-stitch reversal and a satin column whose pitch has collapsed to zero are
> **the same shape**. No test on the triple alone can separate them, because there is nothing to
> separate.

Three candidate discriminators were tried and rejected — anti-parallelism, near-equal leg lengths,
triangle collinearity — each of which turns out to re-measure the gap the metric already measures.
The only signals that work are contextual or structural, and both would mean teaching the metric the
pipeline's internals, which is exactly the coupling Part 5 built it to avoid. So the generator was
fixed rather than the instrument.

## Cost

Two underlay points, on one fixture. `07_circular_badge.stitch_count` 7,806 → 7,804 is the **only**
field that moved anywhere in the corpus. Interior, edge band and spill are identical on all ten
fixtures; classification and all 96 per-object verdicts identical; sub-0.5mm unchanged at 9; zero
stitches over the machine limit.

Visually: **138 differing pixels out of 249,999** on fixture 07 (0.055%), confined to a single
16×23px region, and **zero** on fixture 05. Painted rather than asserted, per the practice binding
since Part 7 — before/after at 8× is committed as `v2-part11-underlay-repair-07.png`.

## Independent confirmation

The junction probe — built in Part 7 for an entirely different purpose, and not aimed at by this
change — had its own last residual violation closed too (`hairline_30deg` Satin 3, min 0.259 →
0.314mm). That is the mechanism generalising rather than a fixture-07 special case.

## Honest notes

- **Option (b) has a real case behind it.** The physical risk genuinely is smaller for a running
  stitch: the floor exists to stop cumulative pile-up, and a turnaround is one needle re-entry, which
  is ubiquitous deliberate practice. I declined to act on it because the fix cost two points, because
  the metric cannot identify underlay locally anyway, and because `MIN_PENETRATION_MM = 0.30` has
  still never been tested on fabric — relaxing an unvalidated rule on the strength of an unvalidated
  argument compounds two guesses. Anyone who wants to revisit it now has the mechanism written down
  and the cost quantified.
- **A reporting discrepancy from the earlier verification pass is carried into this audit:** Parts
  7–10 each said "ruff: 14 findings over every touched file" when 14 was `digitizer.py` alone.
- **`_drop_floor_reversals` is wired into `_axis_underlay` only.** `_center_walk` and `_edge_walk`
  also emit running stitch and could in principle double back; neither violates on this corpus, so
  neither was changed. That is two known-unfixed paths, named rather than hidden.
- **This metric now discriminates nothing.** At 0 corpus-wide and 0 on all three probes it has no
  remaining signal. What replaces it as the next safety constraint is an open question, and so is
  whether 0.30mm should finally be tested on fabric rather than carried as an assertion into a
  seventh part.

## Verification

```
pytest — WITH rembg:     123 passed, 1 warning in 29.80s
pytest — WITHOUT rembg:  123 passed, 1 warning in  9.84s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

digitizer.py                 1,075 stmts   55 miss   95%   (was 94%)
measure_stitch_quality.py      191 stmts   10 miss   95%
run_quality_bench.py           248 stmts   87 miss   65%   pre-existing, untouched

ruff over all touched files:   14, all pre-existing (1 introduced, fixed before commit)
secrets scan:                  clean
```

Seven tests added (116 → 123), including one that fails without the fix and an end-to-end assertion
that fixture 07 reports zero.
