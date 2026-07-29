# v2 Part 11 Audit — the underlay double-back, closed

**Date:** 2026-07-29 · **Tag:** `v2-part11` · graded against [`v2-part10`](./v2-part10-summary.json)
**Grid:** [`v2-part11-grid.png`](./v2-part11-grid.png) · **Per-fixture:** [`v2-part11/`](./v2-part11/)

**Penetration-floor violations: 2 → 0.** Zero across the ten-fixture corpus *and* all three probes,
which has not been true at any point in this project. The metric was **not** changed to get there —
its only edit swaps a literal `0.9` for an import of the same `0.9`, so the number means exactly what
it meant in Part 10.

---

## 0. Housekeeping, both items, confirmed by diff

Part 10 removed every *use* of `_MITRED_POINTS` and `_mitre_key` and reported them deleted. The
definitions were still in the file. **They are gone now**, and here is the diff rather than the
claim (`git diff -- app/services/digitizer.py`):

```diff
 COALESCE_REPAIR_PASSES = 200   # bound; each pass restores at most one point
-# Endpoints the mitre moved, for the current object only. `_coalesce_short` must
-# not drop these (see `_mitre_one_side`), and threading a flag through
-# _column_ends -> _emit_columns -> _skeleton_satin -> digitize_image would mean
-# four signature changes to carry one bit. Module-level state follows the
-# precedent `_CLASSIFICATION_LOG` already sets in this file; `_satin_columns`
-# clears it at the start of every object so it cannot leak between them.
-_MITRED_POINTS: set[tuple[float, float]] = set()
-
-
-def _mitre_key(pt) -> tuple[float, float]:
-    return (round(float(pt[0]), 4), round(float(pt[1]), 4))
+UNDERLAY_REPAIR_PASSES = 200   # bound; each pass drops at most one point
```

And the file itself, not the diff — `grep -rn "_MITRED_POINTS\|_mitre_key\|COALESCE_ZIGZAG"` over
every `.py` in the repo returns **one** line, the test asserting the name is absent:

```
./tests/test_stitch_quality_metrics.py:344:    assert not hasattr(D, "COALESCE_ZIGZAG"), "the old duplicate name should be gone"
```

### The duplicated constant: the digitizer owns it

`COALESCE_ZIGZAG` is gone; `digitizer.ZIGZAG_RATIO` is the single definition and
`measure_stitch_quality.py` imports it. **The pipeline owns the value, not the metric**, for one
structural reason that overrides the intuition that a metric should own its own threshold:
`scripts/` is not a package. It is a dev CLI that pushes the backend root onto `sys.path` at import
time. A shipped service importing from it would invert the dependency and make `app/` depend on a
tool that is not installed in production. The direction chosen is the one already in use —
`run_quality_bench.py:260` already imports `MIN_PENETRATION_MM` and `SATIN_SPACING_MM` from this
module — so this is existing convention, not a new one.

Pinned by `test_the_zigzag_ratio_is_defined_once`, which asserts **identity** (`is`), not equality,
so two files cannot drift back apart while still passing.

## 1. The geometry, measured before anything was changed

Both violations were located exactly, and their position confirmed **structurally** rather than
inferred from step length: `_axis_underlay` was instrumented to report how many points each object's
underlay contributed, and the violating triple's index compared against it.

```
Satin 1  (#122854)   triple @   1   gap=0.1828mm   underlay_len=  6   -> UNDERLAY
Satin 13 (#122854)   triple @ 173   gap=0.0000mm   underlay_len=268   -> UNDERLAY
```

The `Satin 13` case, printed from the actual coordinates:

```
  [   3] (  57.0375,   23.4000)  step= 2.0844
  [   4] (  59.2313,   23.4000)  step= 2.1937   <<< a
  [   5] (  61.4250,   23.4000)  step= 2.1938   <<< b   (branch tip)
  [   6] (  59.2313,   23.4000)  step= 2.1938   <<< c
  [   7] (  57.0375,   23.4000)  step= 2.1937
```

A medial-axis branch dead-ends; the underlay walks out to the tip and back down **the same line**.
`a` and `c` are the same point to the last decimal — the needle enters the identical hole. `Satin 1`
is the same shape with a slight kink, landing 0.1828mm apart instead of 0.0000mm.

### The finding worth arguing with: the metric was not wrong

It is tempting to call this a metric bug — the docstring says the zigzag test is "false of any stitch
sequence that advances along a line", and a running stitch is exactly that. But a running stitch that
**reverses** is not advancing, and the honest statement is stronger than "the test has a hole":

> **Locally, a 180° running-stitch reversal and a satin column whose pitch has collapsed to zero are
> the same shape.** Both have `|ac| ≈ 0` with `|ab| ≈ |bc|` large and anti-parallel. No test on the
> triple `a,b,c` alone can separate them, because there is nothing to separate.

Three discriminators were considered and rejected on that basis — anti-parallelism, near-equal leg
lengths, and triangle collinearity all measure the same quantity the gap already measures. The only
signals that *do* separate them are contextual (in satin every consecutive triple is tight; here the
neighbours are 2.19mm and 4.39mm) or structural (position within the object's stream). **Both would
have meant teaching the metric about the pipeline's internals**, which is precisely what Part 5 built
it to avoid. So the metric was left alone and the generator fixed instead.

## 2. The fix (option (a)): drop one point of the coincident pair

`_drop_floor_reversals`, applied to `_axis_underlay`'s output, mirrors Part 10's principle —
**touch only what actually violates**:

```python
gap = _dist(a, c)
if gap >= floor_px or gap >= ZIGZAG_RATIO * min(_dist(a, b), _dist(b, c)):
    continue
for k in (i + 1, i - 1):        # prefer the return point, fall back to the outbound
```

Removing one of the coincident pair restores the spacing while leaving the thread on the same line —
`... 57.0, 59.2, 61.4, 57.0 ...` instead of `... 57.0, 59.2, 61.4, 59.2, 57.0 ...`. Three guards, each
of which earns its place:

| guard | why |
|---|---|
| skip any triple containing a jump | a jump breaks the run, so the metric never sees the triple, and the flag must survive |
| merged stitch ≤ `MAX_STITCH_MM` | closing a 0.0mm gap must never be paid for with an over-length stitch. If it cannot be done safely the point stays and **the violation is reported honestly** |
| bounded pass count | each pass drops at most one point; `UNDERLAY_REPAIR_PASSES = 200` |

**Cost, corpus-wide: two points.** Fixture 07's underlays go 6 → 5 and 268 → 267. Nothing else in the
corpus is touched at all.

## 3. Result

```
floor violations   v2-part10  2   ->   v2-part11  0
```

### Floor violations, per fixture and per object

```
v2-part10   07_circular_badge   Satin 1 (#122854)    UNDERLAY  0.1828mm   unfixed since Part 5
v2-part10   07_circular_badge   Satin 13 (#122854)   UNDERLAY  0.0000mm   unfixed since Part 5

v2-part11   (none)
```

### Corpus — precisely what moved

**One field on one fixture:** `07_circular_badge.stitch_count` 7,806 → 7,804. That is the two dropped
points and nothing else. Every other field on every other fixture is identical.

| Fixture | interior | edge band | spill | stitches | sub-0.5mm |
|---|---|---|---|---|---|
| 01 flat_2color_logo | 98.7 → 98.7 | 94.6 → 94.6 | 2.1 → 2.1 | 1,632 → 1,632 | 0 |
| 02 logo_fine_text_3color | 99.0 → 99.0 | 97.1 → 97.1 | 3.7 → 3.7 | 3,714 → 3,714 | 0 |
| 03 gradient_soft_subject | 97.9 → 97.9 | 92.6 → 92.6 | 7.7 → 7.7 | 3,228 → 3,228 | 0 |
| 04 thin_line_outline | — | 99.9 → 99.9 | 47.1 → 47.1 | 1,861 → 1,861 | 2 |
| 05 wordmark_caps | 95.3 → 95.3 | 89.5 → 89.5 | 11.1 → 11.1 | 1,492 → 1,492 | 0 |
| 06 wordmark_script | 97.7 → 97.7 | 92.3 → 92.3 | 21.0 → 21.0 | 1,219 → 1,219 | 0 |
| **07 circular_badge** | 97.9 → 97.9 | 95.5 → 95.5 | 4.8 → 4.8 | **7,806 → 7,804** | 4 |
| 08 mascot_detail | 96.7 → 96.7 | 92.3 → 92.3 | 4.0 → 4.0 | 5,005 → 5,005 | 2 |
| 09 nonuniform_background | 99.0 → 99.0 | 93.3 → 93.3 | 3.9 → 3.9 | 1,006 → 1,006 | 1 |
| 10 low_contrast_subject | 98.6 → 98.6 | 94.4 → 94.4 | 3.0 → 3.0 | 2,389 → 2,389 | 0 |

```
classification (stitch_types + all 96 per-object verdicts) identical:   True
sub-0.5mm stitches:                            9 -> 9   (unchanged, per fixture and total)
stitches over the 12.7mm machine limit:        0
max_stitch_mm / mean_stitch_mm / jump_count:   identical on all ten (07 max stays 8.96mm)
colour_count / segmentation_method / filled_area_mm2:  identical on all ten
```

### The visual cost, painted rather than asserted

Per the practice binding since Part 7, the claim "this is invisible" is backed by pixels.
Diffing the rendered output:

```
07_circular_badge:  138 differing pixels / 249,999  (0.055%), confined to x[347..362] y[341..363]
05_wordmark_caps:     0 differing pixels
```

[`v2-part11-underlay-repair-07.png`](./v2-part11-underlay-repair-07.png) is that region at 8×,
before and after. The letterform is identical; what changes is a trace of underlay showing through,
which is expected — underlay lies *under* the top stitching, so removing one of its points has almost
nowhere to show.

### Probes

| Probe | result |
|---|---|
| **curvature** | byte-identical. r8w 99.3/94.6 · r4w 98.2/91.0 · r2w 94.1/82.8 · r1.25w 86.5/72.8 · **0 below floor** at every radius |
| **junction** | **its last violation also closed.** `hairline_30deg` Satin 3 min **0.259 → 0.314mm**, below-floor **1 → 0**, penetrations 470 → 469. Interior/edge band unchanged on all four cases |
| **letter** | byte-identical. apex_M 97.3/92.1 · apex_V 97.8/95.1 · apex_U 96.9/91.2 · apex_narrow 96.3/90.3 · **0 below floor** |

The junction probe is the useful one here: it was built in Part 7 for an unrelated purpose, and the
repair closed its residual violation without being aimed at it. That is independent confirmation the
mechanism is the general one and not a fixture-07 special case.

## 4. What the violation count now means

Stated precisely, because the brief asks and because it is the kind of thing that quietly drifts:

> **Zero** same-side needle penetrations closer than 0.30mm anywhere in the ten-fixture corpus or in
> any of the three probes, measured from the emitted stitch stream by the *unchanged* Part 5 metric,
> with enforcement ON.

The metric's only edit this part is an import. Behaviour is provably identical, so this number is
directly comparable to every figure since Part 5 — 3,235 (Part 5, floor off) → 3 (Part 6) → 3 (Part 7)
→ 5 (Part 8) → 3 (Part 9) → 2 (Part 10) → **0**.

**Nothing was excluded to reach it.** Option (b) — excluding running-stitch underlay from the metric —
was not exercised, so no category of stitch has been quietly removed from the count's scope.

## 5. Option (b), argued anyway, because it bears on whether (a) was worth doing

(a) closed cleanly, so (b) was not needed. But the investigation raised the question the brief asks,
and answering it is what makes the fix defensible rather than merely green:

**Should the 0.30mm floor apply to a running stitch at all?** My position: **the physical risk is
genuinely smaller, but not zero, and fixing the generator was the right call regardless.**

The floor exists to stop *pile-up*: in satin, dozens of penetrations crowding along one boundary line
perforate the fabric the way a stamp edge does, and thread builds up in the same spot. An underlay
turnaround is **one** coincident pair at a branch tip — a single needle re-entry into an existing
hole, which is ubiquitous, deliberate practice in embroidery (every backtrack does it). The
cumulative mechanism that makes 0.05mm satin spacing dangerous is simply not present.

So a defensible case exists for excluding running stitch. I did not take it, for three reasons:

1. **The fix was cheaper than the argument.** Two points, zero coverage movement, no metric change.
   Weakening a safety metric to avoid a two-point edit is a bad trade.
2. **Excluding underlay would require the metric to identify underlay**, which as §1 shows it cannot
   do locally, and teaching it structure is exactly the coupling Part 5 avoided.
3. **The floor's own value is asserted, not measured.** `MIN_PENETRATION_MM = 0.30` has never been
   tested on fabric (stated in Part 6 and still true). Loosening an unvalidated safety rule on the
   strength of an unvalidated physical argument compounds two guesses.

**What this does mean:** anyone who later wants to relax the floor for running stitch now has the
mechanism written down and the cost quantified at two points. It is a live option, not a closed one.

## 6. Verification

```
pytest — WITH rembg:     123 passed, 1 warning in 29.80s
pytest — WITHOUT rembg:  123 passed, 1 warning in  9.84s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Seven tests added (116 → 123): the shared-constant identity pin; the reversal defect itself
(`test_underlay_reversal_produces_a_zero_same_side_gap`, which fails without the fix); the repair;
no-op on a plain running stitch; the `MAX_STITCH_MM` refusal; jump preservation; and an end-to-end
assertion that fixture 07 reports zero.

**Standards, read from [`docs/ENGINEERING_STANDARDS.md`](../ENGINEERING_STANDARDS.md):**

| §1 Coverage (floor 80%) | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 1,075 | 55 | **95%** (was 94%) |
| `scripts/measure_stitch_quality.py` | 191 | 10 | **95%** |
| `scripts/run_quality_bench.py` | 248 | 87 | **65%** ⚠ pre-existing, untouched since Part 5 |

**§3 Size.** `_drop_floor_reversals` is 46 lines and `_axis_underlay` 33 — both inside the limit.
Pre-existing over-limit functions, named as the standard requires: `digitize_image` 346,
`rebuild_design` 129, `_skeleton_branches` 76, `_skeleton_satin` 55. `digitizer.py` at **2,162** lines
remains the standing documented exception; it grew 51 lines this part.

**§1 Lint.** `ruff check` over all touched files: **14 findings, all pre-existing in `digitizer.py`**;
one was introduced during the work (an unused `noqa` on the new import) and fixed before commit.
Note for the record: Parts 7–10 each reported "14 over every touched file" when 14 is
`digitizer.py` alone — the discrepancy found in the 2026-07-29 verification pass. This part's 14 is
genuinely the whole touched set, because `measure_stitch_quality.py` and the test file are clean.

**§4 Security.** Secrets scan over the diff — clean. One new named constant,
`UNDERLAY_REPAIR_PASSES = 200`, commented; one renamed (`COALESCE_ZIGZAG` → `ZIGZAG_RATIO`, now
shared); two dead definitions removed.

## 7. What to attack

1. §1 — the claim that no local test can separate a reversal from a collapsed satin column. If that
   is wrong, the metric could be fixed instead of the generator, and this part fixed the wrong layer.
2. §5 — I argued the physical risk is smaller for running stitch and then declined to act on it. Is
   holding an unvalidated floor uniformly actually more conservative, or just less thought through?
3. The repair prefers dropping the **return** point over the outbound one. On a symmetric turnaround
   these are equivalent; on an asymmetric one they are not. Unmeasured — the same open question
   Part 10 §6 item 2 raised about restoring the *first* dropped point, still unanswered.
4. `_drop_floor_reversals` is wired into `_axis_underlay` only. `_center_walk` and `_edge_walk` also
   emit running stitch and could in principle double back; neither violates on this corpus, so
   neither was changed. Fixing only what demonstrably breaks, or leaving two known gaps?
5. With the floor at 0 corpus-wide and all three probes, **this metric no longer discriminates
   anything.** What replaces it as the next safety constraint — and is it time to test 0.30mm on
   actual fabric rather than carry it as an assertion into a seventh part?
