# STITCHIQ v2 — Part 5 Work Report for Independent Review

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part5-audit.md`](./benchmarks/v2-part5-audit.md) ·
**Standards:** [`docs/ENGINEERING_STANDARDS.md`](./ENGINEERING_STANDARDS.md)

> **Brief:** (1) add a penetration-density safety metric and answer Part 4 §11.2 with data, adding a
> floor if the data warrants; (2) commit the interior/edge-band/spill methodology as a script;
> (3) write down the engineering standards. Measurement and documentation only — no fixture's
> `stitch_types`, `stitch_count` or `jump_count` may change.
>
> **§2 is the finding worth arguing with, and §4 is a conflict in the brief I could not resolve
> without a decision that is yours.**

---

## 1. The metric

A satin path alternates sides (`A0 B0 A1 B1 …`), so points `i-1` and `i+1` are the same-side pair
and their distance is that boundary's penetration spacing. The triple counts only when it
**zigzags** — same-side gap shorter than either crossing — which a running-stitch underlay or a
tatami row can never satisfy, because their points advance along a line.

Taken from the **stitch stream only**, never from a digitizer internal. What the machine sews is the
stream, so the metric stays valid however a future part generates columns.

## 2. Part 4 was wrong about its own corpus — and the bigger cause is not the one it predicted

Part 4 §8 wrote: *"no fixture in the corpus is tight enough to show it."* Measured:

| Fixture | min same-side penetration | below the 0.30mm floor |
|---|---|---|
| 05 wordmark_caps | **0.000mm** | 371 / 1,793 (20.7%) |
| 07 circular_badge | **0.000mm** | 938 / 4,776 (19.6%) |
| 08 mascot_detail | **0.000mm** | 1,130 / 4,704 (24.0%) |

Not "no fixture" — **every satin fixture**, with hundreds of penetrations at *exactly* zero, i.e. the
needle entering the same hole twice.

Splitting by position in the run separates two producers, and the larger one is **not** the curvature
mechanism Part 4 flagged:

| Fixture | terminal triples under floor | mid-run under floor |
|---|---|---|
| 05 | 43 / 147 (**29.3%**) | 328 / 1,646 (19.9%) |
| 07 | 295 / 790 (**37.3%**) | 643 / 3,986 (16.1%) |
| 08 | 313 / 703 (**44.5%**) | 817 / 4,001 (20.4%) |

**Part 4's cap handling is the source of the exact zeros.** It runs the column grid past each stroke
terminal, where both boundary arcs clamp to their own end point — so those columns are duplicates.
Part 4 introduced that, reported it as elegant ("no special code path"), and did not notice. The
curvature effect it *did* predict is real and second in size.

## 3. At what curvature does it bite — the probe

**A dead end first, because the second version only looks obvious afterwards.** The probe started as
U-turns of decreasing radius. It failed: every open stroke has two terminals, and by §2 those pin the
minimum near zero at *every* radius, so the curvature signal was buried. Rings have **no terminals**,
so every penetration is a bend penetration.

Constant 2.5mm stroke, centreline radius `R` in stroke widths. Pacing by the outer boundary predicts
inner-side spacing `pitch x (R - w/2) / (R + w/2)`:

| R | predicted | **measured p05** | below floor |
|---|---|---|---|
| 8.0 w | 0.353mm | **0.264mm** | 79 / 764 |
| 4.0 w | 0.311mm | **0.185mm** | 82 / 386 |
| 2.0 w | 0.240mm | **0.093mm** | 77 / 192 |
| 1.25 w | 0.171mm | **0.009mm** | 62 / 126 |

Monotone in curvature as predicted, and consistently *tighter* than the closed form — a small ring's
inner boundary is a coarse pixel circle, so the extreme-point-per-station rule crowds harder than an
ideal arc.

**Answer to Part 4 §11.2:** the concave side is already under 0.30mm at `R = 8w`, a curve most
digitizers would call gentle. This is not a tight-curve edge case; it is the normal case.

## 4. The floor works — and I did not enable it, because the brief conflicts with itself

Implemented at two points: pacing skips a column unless **both** boundaries advanced past the floor,
and then `_enforce_floor` re-checks the **final** endpoints. The second pass is necessary — pull
compensation moves each end outward *after* the pacing decision, which on a ring's concave side pulls
it to a smaller radius and shrinks the spacing again. Pacing alone fixed 86–91%; the final-endpoint
pass fixes all of it.

| R | min penetration | below floor | interior | edge band |
|---|---|---|---|---|
| 8.0 w | 0.000 → **0.301mm** | 79 → **0** | 100.0 → 99.8 | 100.0 → 98.8 |
| 4.0 w | 0.000 → **0.300mm** | 82 → **0** | 100.0 → 98.5 | 100.0 → 94.8 |
| 2.0 w | 0.000 → **0.303mm** | 77 → **0** | 100.0 → 95.5 | 99.9 → **87.5** |
| 1.25 w | 0.000 → **0.300mm** | 62 → **0** | 100.0 → **71.5** | 99.6 → **53.7** |

On the corpus it clears every fixture to zero violations (07 keeps 3 — see below) but costs fixture
05 ten points of interior *and* edge band, undoing most of Part 4's gain there.

**The conflict.** Part 1 of the brief says implement a floor if the data warrants; the constraints say
this part "should not change any fixture's `stitch_types`, `stitch_count`, or `jump_count`" and the
verification demands byte-identity with v2-part4. **Enabling the floor changes the stitch count of
every satin object.** Both cannot hold.

I shipped the floor **implemented, tested and measured, with enforcement off** — so this stays the
measurement part it was scoped as, and the decision to buy production safety at 5–10 points of
coverage is put in front of you with numbers instead of taken silently inside a metrics change.
**My recommendation: enable it in its own part**, with a coverage re-grade, and consider a
radius-aware floor (full above `R = 4w`, relaxed below) rather than the flat one measured here. Say
the word and I'll do that next.

**Three residual violations on fixture 07, attributed rather than waved at.** Two are in the
running-stitch **underlay**, not in satin columns — the medial-axis underlay can double back sharply
enough to put two penetrations 0.18mm apart, and the floor governs columns only. That is a second
producer the metric found and the floor does not address. The third is in a 0.63mm-wide column;
likely `_coalesce_short` running after generation and removing a penetration, but **not chased to
certainty** — it is 0.02% of that fixture, and I am flagging it as unproven rather than asserting it.

## 5. The pipeline is unchanged — verified

```
  => all 10 identical on stitch_types + stitch_count + jump_count: True
  => every pre-existing metric field identical (SHA-256 of the record,
     runtime and the two NEW fields stripped):                      True
```

## 6. Methodology committed, and it reproduces the history exactly

`scripts/measure_stitch_quality.py` replaces the prose description that every audit since Part 2.5
restated. The harness imports it rather than carrying a second copy.

Regenerating Part 4 §6's table with the committed script gives the same numbers to the decimal
(`02 99.0/97.3/3.7 · 05 99.8/98.3/12.2 · 07 98.2/96.9/5.0 · 08 97.8/97.2/4.5`).

**One deliberate wart, kept for that reason.** `_poly` truncates rather than rounds when rasterising
outline vertices. Rounding is more correct; switching moved fixture 07's spill 5.0 → 5.1 — enough to
make the committed script disagree with the audits it exists to make reproducible. Truncation kept,
reason in a comment at the call site.

## 7. Standards written down

`docs/ENGINEERING_STANDARDS.md` captures what has been applied since Part 3: both rembg paths
mandatory, coverage as a percentage with an 80% floor, ~50-line functions / ~800-line files with a
reporting duty for anything over, a runnable secrets scan, no magic numbers, conventional commits, no
build artifacts, and the honesty rules (report regressions, correct earlier audits visibly, record
rejected options with their measurements, say when something is unmeasured).

Each rule is stated so it can be measured, with the command that measures it — the Part 4 report
applied these from memory and I could not check the thresholds against anything.

## 8. Verification

```
pytest — WITH rembg:     107 passed, 1 warning in 24.29s
pytest — WITHOUT rembg:  107 passed, 1 warning in  7.95s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Twelve tests added (95 → 107), including the false-positive guards that matter most: a running stitch
and a tatami row must yield **no** same-side pairs, or the metric would report noise as a safety
problem.

| §1 Coverage (floor 80%) | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 965 | 58 | **94%** |
| `scripts/measure_stitch_quality.py` | 156 | 5 | **97%** |
| `scripts/run_quality_bench.py` | 248 | 87 | **65%** ⚠ |

`run_quality_bench.py` is under the floor at its **pre-existing** 65% — uncovered block is its CLI
driver and grid renderer plus two diagnostic `except` branches; the lines Part 5 adds are covered by
a new test. Stated as the standard requires rather than waived. (My first pass on
`measure_stitch_quality.py` was 66%; I added CLI tests to reach 97% rather than grant myself an
exception on a document I had just written.)

**§3 Size.** All 15 functions added or split out are ≤50 lines (`_main` was 72 and was split into
`_parse_args`/`_print_row`/`_print_detail`). New files 332 / 186 / 63 lines. `digitizer.py` at 1,855
lines remains the standing documented exception.

**§4 Security.** Secrets scan clean. Two new named, commented constants: `MIN_PENETRATION_MM = 0.30`,
`ZIGZAG_RATIO = 0.9`.

**§1 Lint.** `ruff check` over every touched file: **15 findings, exactly the pre-existing count.**
Four introduced during the work were fixed before commit.

## 9. What to attack

1. §2 — Part 4's cap handling puts hundreds of penetrations in the same hole, worse than the problem
   it flagged. Should I have fixed it here instead of measuring it?
2. `MIN_PENETRATION_MM = 0.30` is asserted from general practice, not measured on fabric. What is the
   right number, and should it depend on the `fabric_type` the pipeline already takes?
3. The floor costs fixture 05 ten points of coverage. Is a radius-aware floor principled, or a way to
   protect a number?
4. `ZIGZAG_RATIO = 0.9` decides what counts as a satin triple. What geometry does it misclassify?
5. The probe uses rings, which isolates curvature by excluding terminals — the very thing §2 shows is
   the bigger producer. Right instrument, or does it flatter the analysis?
