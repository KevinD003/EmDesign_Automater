# v2 Part 10 — targeted floor repair, replacing Part 9's blanket protection

**Date:** 2026-07-29 · **Tag:** `v2-part10` · graded against [`v2-part9`](./v2-part9-summary.json)

**Floor violations 3 → 2. Sub-0.5mm stitches 33 → 9.** Both machine-safety numbers improve at once,
and no coverage number moves on any fixture. The narrower fix Part 9 flagged as unattempted works.

---

## 0. Housekeeping — the comment Part 9 said it fixed and did not

`test_mitre_closes_a_sharp_apex_without_breaking_the_floor` still read
`apex_M 96.6 -> 97.9, apex_V 98.1 -> 98.7`. **The Part 9 audit reported this as corrected; the edit
never landed.** The cause: Part 9 applied it with a Python `str.replace` whose search string said
"the opposite direction to the letter probe's…" while the file says "the opposite of the letter
probe's…". A `replace` that matches nothing returns the string unchanged and raises nothing, so the
no-op was silent and the audit was written from intent rather than from the file.

Fixed now, and **verified by diffing the file**:

```
-    # (apex_M 96.6 -> 97.9, apex_V 98.1 -> 98.7). The shape is pinned here so the
+    # (apex_M 96.6 -> 97.3, apex_V 98.1 -> 97.8). The shape is pinned here so the
```

The provenance of the wrong figures (an intermediate build taken before the `MIN_STITCH_MM` guard)
is now recorded in the comment itself, along with the fact that Part 9's correction silently failed —
so the next reader does not have to rediscover it.

## 1. The narrower fix

Part 9 protected **every** mitred endpoint, and the point after it, from `_coalesce_short`. That
holds the floor but pays a short stitch for every mitre whether or not that mitre was ever going to
cause a violation. Corpus cost: sub-0.5mm stitches 6 → 33.

The narrower rule inverts the order. **Coalesce first, then put back only the points whose absence
actually breaks the floor:**

1. `_coalesce_short` drops as before, recording which points it removed after each survivor.
2. `_restore_for_floor` scans the survivors for a same-side pair under the floor — using the *same*
   zigzag test the metric uses, so a running-stitch underlay cannot trigger a spurious restore.
3. For each violation it re-inserts **one** dropped point from the span between the offending pair.
   Any such point restores the A-B-A-B alternation, so the repair is minimal by construction.
4. Repeat until clean (bounded at `COALESCE_REPAIR_PASSES = 200`; each pass restores one point).

The floor is passed only for satin objects. A tatami row advances along a line and never zigzags, so
the repair could not fire there — but not passing it keeps fills on byte-identically the path they
had.

## 2. Result

| | v2-part8 (blanket absent) | v2-part9 (blanket) | **v2-part10 (targeted)** |
|---|---|---|---|
| floor violations | 5 | 3 | **2** |
| sub-0.5mm stitches | 6 | 33 | **9** |

**It beat the target on both axes.** The brief asked for violations held at 3 with sub-0.5mm
meaningfully under 33; the result is 2 and 9. The extra violation closed is fixture 08's
`Satin 16` at 0.2519mm — **a pre-existing case, unfixed since Part 7** — because the repair does not
care how a violation arose, only that one exists in the emitted stream.

### Floor violations, per fixture and per object

```
07_circular_badge   Satin 1 (#122854)    UNDERLAY  0.1828mm   pre-existing since Part 5
07_circular_badge   Satin 13 (#122854)   UNDERLAY  0.0000mm   pre-existing since Part 5
```

**Both remaining violations are in the running-stitch underlay**, which no floor governs — the
medial-axis underlay can double back sharply enough to put two penetrations 0.18mm apart. For the
first time since Part 6, **there are zero satin-column violations anywhere in the corpus.** The
underlay double-back is now the only producer left, and it has survived six parts unfixed.

### Sub-0.5mm stitches, from actual stitch coordinates

```
per fixture:  01:0  02:0  03:0  04:2  05:0  06:0  07:4  08:2  09:1  10:0     TOTAL 9
```

Cross-checked two ways — walked directly from the `Stitch` coordinates in a standalone script, and
read from `stitches_under_0_5mm` in the bench JSON. Both give 9. Of those, **3 predate the mitre
entirely** (04:2 and 09:1 were already there in v2-part8, and fixture 09 has no satin at all), so the
mitre's true residual cost is **6 short stitches, not 27**.

## 3. Corpus — precisely what moved

| Fixture | interior | edge band | spill | stitches p9 → p10 | sub-0.5mm |
|---|---|---|---|---|---|
| 01 | 98.7 → 98.7 | 94.6 → 94.6 | 2.1 → 2.1 | 1,632 → 1,632 | 0 → 0 |
| **02** | 99.0 → 99.0 | 97.1 → 97.1 | 3.7 → 3.7 | 3,724 → **3,714** | 8 → **0** |
| 03 | 97.9 → 97.9 | 92.6 → 92.6 | 7.7 → 7.7 | 3,228 → 3,228 | 0 → 0 |
| 04 | — | 99.9 → 99.9 | 47.1 → 47.1 | 1,861 → 1,861 | 2 → 2 |
| 05 | 95.3 → 95.3 | 89.5 → 89.5 | 11.1 → 11.1 | 1,492 → 1,492 | 0 → 0 |
| **06** | 97.7 → 97.7 | 92.3 → 92.3 | 21.0 → 21.0 | 1,227 → **1,219** | 5 → **0** |
| **07** | 97.9 → 97.9 | 95.5 → 95.5 | 4.8 → 4.8 | 7,817 → **7,806** | 10 → **4** |
| **08** | 96.7 → 96.7 | 92.3 → 92.3 | 4.0 → 4.0 | 5,012 → **5,005** | 7 → **2** |
| 09 | 99.0 → 99.0 | 93.3 → 93.3 | 3.9 → 3.9 | 1,006 → 1,006 | 1 → 1 |
| 10 | 98.6 → 98.6 | 94.4 → 94.4 | 3.0 → 3.0 | 2,389 → 2,389 | 0 → 0 |

**No interior, edge-band or spill figure moved on any fixture, to one decimal.** The only movement is
in stitch counts on 02, 06, 07 and 08 — exactly the four fixtures Part 9's blanket protection had
inflated — each shedding the short stitches the blanket rule had forced.

**Probes: all three byte-identical to v2-part9.** Letter `apex_M` 97.3 / 92.1, `apex_U` 96.9 / 91.2,
`apex_V` 97.8 / 95.1, `apex_narrow` 96.3 / 90.3. Curvature `r8w` 99.3 / 94.6, `r4w` 98.2 / 91.0,
`r2w` 94.1 / 82.8, `r1.25w` 86.5 / 72.8. Junction `equal_30deg` 97.7 / 94.7, `hairline_30deg`
99.5 / 98.1, `hairline_60deg` 99.7 / 97.8, `medium_30deg` 99.3 / 98.3. Violations 0 on the letter and
curvature probes; 1 on `hairline_30deg`, unchanged and pre-existing.

## 4. What the targeted fix let us delete

`_MITRED_POINTS` — the module-level register Part 9 introduced and flagged in its own §7 as "state,
and state is how bugs hide" — became **write-only** once the repair moved downstream. It is deleted,
along with `_mitre_key` and the two tests that pinned its behaviour. The mitre no longer publishes
anything to the rest of the pipeline; `_coalesce_short` needs only the floor value.

That answers Part 9 §8 item 3 ("`_MITRED_POINTS` as module state — worth four signature changes to
remove?") in the best available way: **it needed none, because the right fix did not need the state
at all.**

## 5. Verification

```
pytest — WITH rembg:     116 passed, 1 warning in 29.56s
pytest — WITHOUT rembg:  116 passed, 1 warning in 11.78s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

floor violations:      v2-part9  3  ->  v2-part10  2
sub-0.5mm stitches:    v2-part9 33  ->  v2-part10  9
classification (stitch_types + all 96 verdicts):   identical to v2-part9
stitches over the 12.7mm machine limit:            0
colour / segmentation / filled area:               identical on all ten
```

Three tests replace the two removed: the repair restores a point when its removal leaves a sub-floor
same-side pair, is a byte-exact no-op on a clean satin path, and never fires on a running stitch.

| §1 Coverage (floor 80%) | Cover |
|---|---|
| `app/services/digitizer.py` | **94%** |
| `scripts/measure_stitch_quality.py` | **95%** |
| `scripts/run_quality_bench.py` | 65% ⚠ pre-existing, untouched |

**§3 Size.** `_coalesce_short` 30 lines, `_restore_for_floor` 31 — both new/rewritten here, both
inside the limit. Pre-existing over-limit, named as the standard requires: `digitize_image` 342,
`rebuild_design` 129, `_skeleton_branches` 76, `_skeleton_satin` 55. `digitizer.py` 2,111 lines
remains the standing documented exception.

**§4 Security.** Secrets scan clean. Two new named constants, both commented: `COALESCE_ZIGZAG = 0.9`
(mirrors the metric's own triple test) and `COALESCE_REPAIR_PASSES = 200` (a bound, not a tuning
knob). Two constants and one register removed.

**§1 Lint.** `ruff check` over every touched file: **14 findings, all pre-existing.**

## 6. What to attack

1. `COALESCE_ZIGZAG = 0.9` duplicates a constant that also lives in `measure_stitch_quality.py`. The
   pipeline now contains a copy of a metric's definition — if the metric's changes, they silently
   disagree. Shared constant, or is the duplication the lesser evil?
2. The repair restores the *first* dropped point in the span. Any point in the span works for the
   alternation, but not all are equally good geometrically. Does the choice matter?
3. Both remaining violations are the underlay double-back, unfixed for six parts and now the only
   producer left. It is a running stitch, not satin — does the floor even apply to it, or should the
   metric exclude it and report 0?
4. §0 — a silent `str.replace` no-op produced a false claim in an audit. Should edits to tracked
   files be diff-verified as a matter of course rather than trusted?
