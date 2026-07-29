# STITCHIQ v2 — Part 4 Work Report for Independent Review

**Date:** 2026-07-28 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part4-audit.md`](./benchmarks/v2-part4-audit.md) ·
**Grid:** [`docs/benchmarks/v2-part4-grid.png`](./benchmarks/v2-part4-grid.png)

> **Brief:** replace skeleton-±-measured-width satin with true edge-bounded satin — pair each
> stroke's two boundary contours and lay columns between corresponding points. Handle correspondence
> across junction topology, caps at terminals, and rings. Change HOW satin is drawn, never WHICH
> objects are satin.
>
> **§3 is the finding most worth arguing with, and it is not flattering to Parts 2–3.**

---

## 1. Correspondence across junctions — the solution is what it refuses to do

Both prior audits called this the blocker: at a junction, three strokes meet and the contour weaves
between them, so there is no global split of the region's outline into "left side" and "right side".

The answer is to stop looking for one. **Every boundary pixel is assigned to its nearest axis
branch**, so the contour is partitioned by the skeleton's own topology and each branch sees only the
boundary that belongs to it. A junction fillet just goes to whichever branch is nearest. Within a
branch, a point gets `t` (arc length, refined by projecting onto the local tangent) and a `side`
(sign of the cross product). **Corresponding points are equal `t`, opposite `side`** — both arcs get
resampled onto one shared grid, and column *k* joins genuinely corresponding boundary points.

**Caps and rings then need no special code path in the column generator.** Because `t` is refined
tangentially it keeps increasing *past* the last axis sample instead of piling up on it, so running
the grid two pitches beyond each terminal makes both arcs clamp to their own end point and the pair
converges onto the cap. A ring is detected by its axis returning to its start and is the *simpler*
case — no terminals, `t` cyclic, arcs repeated one period each way so interpolation wraps. **5 of
293 branches in the corpus are closed loops** (fixture 04's outer ring, 07's badge rings).

Two refinements were forced by measurement rather than foreseen: keeping the **outermost** boundary
point per column station (interpolating across ties averaged endpoints inward — a 1.4–2.1 point
loss), and pacing the pitch by the **faster boundary** rather than the axis (axis pacing fans columns
apart on the outside of curves — a 0.6–1.3 point *interior* loss).

## 2. Result: edge band now beats the tatami baseline on every satin fixture

| # | Fixture | interior p2.5 → p3 → **P4** | **edge band** p2.5 → p3 → **P4** | spill p2.5 → p3 → **P4** |
|---|---|---|---|---|
| 01 | flat_2color_logo *(control)* | 98.7 → 98.7 → **98.7** | 94.6 → 94.6 → **94.6** | 2.1 → 2.1 → **2.1** |
| 02 | logo_fine_text | 99.0 → 99.0 → **99.0** | 96.8 → 96.9 → **97.3** | 3.7 → 3.7 → **3.7** |
| 03 | gradient_soft | 97.9 → 96.9 → **98.6** | 94.8 → 87.3 → **97.2** | 10.4 → 7.9 → **8.0** |
| 04 | thin_line_outline | — *(no interior)* | 99.6 → 96.7 → **99.9** | 54.0 → 46.6 → **47.3** |
| 05 | wordmark_caps | 96.3 → 95.5 → **99.8** | 85.5 → 82.2 → **98.3** | 12.6 → 11.2 → **12.2** |
| 06 | wordmark_script | 98.2 → 98.2 → **100.0** | 91.4 → 91.8 → **99.8** | 25.8 → 23.0 → **23.0** |
| 07 | circular_badge | 98.1 → 97.5 → **98.2** | 96.3 → 95.0 → **96.9** | 5.7 → 4.9 → **5.0** |
| 08 | mascot_detail | 98.6 → 97.8 → **97.8** | 95.8 → 92.3 → **97.2** | 5.4 → 4.0 → **4.5** |
| 09 | nonuniform_bg *(control)* | 99.0 → 99.0 → **99.0** | 93.3 → 93.3 → **93.3** | 3.9 → 3.9 → **3.9** |
| 10 | low_contrast | 98.6 → 98.6 → **98.6** | 94.9 → 94.4 → **95.2** | 3.0 → 3.0 → **3.0** |

The `p2.5` column is the **tatami baseline** for 02/03/04/07/08/10. For 05/06 it is Part 2.5's satin,
since those were already satin; their tatami reference (Part 2.5 audit §2) is **05 interior 84.5,
band 84.1, spill 20.0; 06 92.9 / 87.5 / 27.5** — so against tatami, **05 gains 14.2 points of edge
band and 06 gains 12.3**.

**Interior did not pay for it** — every fixture at or above both prior parts except 08, level with
Part 3. Spill essentially flat, and still under the tatami baseline on 03/05/06.

## 3. The finding worth arguing with: a bug present since Part 2 was masking the real edge coverage

With edge-bounded columns in and both refinements applied, edge band was *still* only ~85–92%. The
metrics all looked reasonable. Painting the uncovered pixels showed the miss was a **thin dotted rim
running the full length of every stroke** — not the ends, not the junctions.

`_emit_columns` emitted both ends of every column with an alternating lead: `A0 B0 B1 A1 A2 B2 …`.
That puts two penetrations **one pitch apart on the same boundary, back to back in the path**. At a
0.4mm satin pitch that is a 0.4mm stitch — under the project's own 0.5mm minimum — so
`_coalesce_short` correctly deleted it. Net effect: **half the needle penetrations along both
boundaries were being thrown away**, leaving them 0.8mm apart under 0.4mm thread.

Strict alternation (`A0 B0 A1 B1 …`, every step a full crossing) is worth more than everything else
in this part:

| Fixture | edge band before the fix | **after** |
|---|---|---|
| 03 | 84.4% | **97.2%** |
| 05 | 82.0% | **98.3%** |
| 06 | 90.2% | **99.8%** |
| 08 | 92.4% | **97.2%** |

**This shipped in Parts 2, 2.5 and 3.** It was hidden there because the ray-cast endpoints
over-reached past the outline, partly papering over the missing penetrations — which also explains
why Part 2.5 §3's outward-bias knob *appeared* to buy coverage. The fair challenge to raise with me:
three earlier audits graded satin edge quality against a handicapped baseline, so their comparative
conclusions — particularly Part 2.5 §4's spill argument — deserve re-reading.

Second time in this sequence that opening the picture found what the metric set could not (Part 3
§3b was the first).

## 4. Classification is untouched — structurally, then verified

`_skeleton_satin` was split into two passes: `_axis_samples` takes the classification widths from the
distance transform and feeds nothing downstream, so column generation *cannot* influence the verdict.

```
all 10 fixtures identical stitch_types:            True
per-object verdicts (seq, reason, decision), 96 objects, every fixture:  IDENTICAL
stitches over the 12.7mm machine limit, from the JSON, all 10 fixtures:  0
```

Non-satin objects untouched: fixtures 01 and 09 (no satin object) are bit-stable — 1,632 and 1,006
stitches, 63 and 41 jumps, identical coverage numbers. Colour counts, segmentation tier and
`filled_area_mm2` unchanged on all ten.

## 5. An outward bias, measured and rejected — for the second time

While the §3 defect was still present, a half-pixel outward bias looked principled (a contour point
is the centre of the outermost pixel *inside* the shape). Swept: 0.0 / 0.5 / 1.0 / 1.5px. Once §3 was
fixed it buys **nothing** — 03's edge band 97.2 → 97.2, 05's 98.3 → 98.4 — and costs spill throughout
(03 8.0 → 9.7, 05 12.2 → 15.6, 04 47.3 → 55.3). Removed, and the constant deleted rather than parked
at zero. Recorded so the choice stays auditable.

## 6. Costs, stated plainly

**Stitch count +30% corpus-wide** (26,031 → 33,759), concentrated in satin fixtures (05 1,079 →
1,962). Two intended causes: §3's fix restores penetrations that were being deleted — the old counts
were *artificially low* — and boundary-paced pitch adds columns on fast-moving boundaries.

**The honest risk:** on the inside of a tight curve, boundary-paced pitch puts penetrations closer
than the nominal pitch, which in production can perforate light fabric. **Nothing in the metric set
detects this**, and no corpus fixture is tight enough to show it. Runtime 12.8s → 13.2s. Jumps
exactly flat at 2,046.

## 7. Still wrong

1. **08's interior 97.8%** — the only coverage number that has not recovered to its tatami baseline
   (0.8 under). Its satin objects are ears and whiskers, where short branches meet at shallow angles.
2. **Inner-curve penetration spacing is unmeasured** (§6). That metric is the missing instrument.
3. **The nearest-branch partition is a Voronoi split**, so a junction's boundary divides on a straight
   bisector rather than on anything the stroke geometry implies. Fine on this corpus; a hairline
   meeting a thick stem could hand the fillet to the wrong branch.
4. **03's annuli are still the weakest satin *call*** (Part 3 §8.2). This part fixed how they are
   drawn (band 87.3 → 97.2), not whether they should be satin at all.

## 8. Verification, including Engineering Standards

```
pytest — WITH rembg:     95 passed, 1 warning in 20.62s
pytest — WITHOUT rembg:  95 passed, 1 warning in  6.14s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Five tests added (90 → 95): closed-loop detection and wrap; a ring stitched without a seam across its
hole; columns reaching an open stroke's terminal caps; the ray-cast fallback; and a regression guard
on §3 (no sub-pitch along-edge steps in a satin path).

**Coverage — actual percentages via `pytest --cov`, not pass counts:**

```
app/services/digitizer.py     933 stmts   51 miss   95%    (91% before this part)
new code added by Part 4:    ~184 stmts    9 miss  ~95%
```

Ten of the fifteen added functions are fully covered; the nine uncovered lines are empty-input and
degenerate-branch guards in `_assign_boundary` (3), `_column_ends` (3), `_emit_columns`,
`_axis_samples` and `_satin_columns` (1 each).

**Size limits.** All 15 functions added here are ≤50 lines (largest `_assign_boundary` 44,
`_column_ends` 40). `_skeleton_satin`, pre-existing and rewritten here, went **133 → 53 lines**.
Pre-existing long functions not rewritten (`digitize_image` 336, `rebuild_design` 129,
`_skeleton_branches` 76) are unchanged and out of scope.

**No secrets or hardcoded values.** Diff scanned for key/secret/token/password/bearer/private-key and
URL-embedded credentials — none. Four new numeric constants, all named and commented at module level:
`CLOSED_LOOP_TOL_PX = 2.5`, `MIN_ARC_SAMPLES = 4`, `CAP_EXTRA_COLUMNS = 2`, `PROJECT_CHUNK = 256`.

**Lint.** `ruff check` reports 14 findings — **exactly the pre-existing count**; this part introduced
none (three I did introduce were fixed before commit).

**Commits** use conventional prefixes.

**One gap I am flagging rather than papering over:** the Engineering Standards document is not in the
repository, so the thresholds above (≤50 lines/function, a coverage floor) are the conventional ones
I applied, not ones I could read off the standard. Every raw measurement is given so any threshold
can be checked against it. If the standard says something different, point me at it.

Scope: `app/services/digitizer.py` and `tests/test_digitizer.py`. `SATIN_MAX_W_MM`,
`SATIN_MAX_UNCOVERED`, `SATIN_PREGATE_SLACK`, background separation, colour/layer logic and the
Part 0–3 renderer are untouched.

## 9. What to attack

1. §3 means three earlier audits graded satin against a handicapped baseline. Which of their
   conclusions no longer hold?
2. Boundary-paced pitch buys interior coverage by adding stitches. At what curvature does that become
   fabric damage, and should there be a hard floor on penetration spacing?
3. Construct the asymmetric junction that breaks the Voronoi boundary partition (§7.3).
4. 30% more stitches for 5–14 points of edge band. Right trade at production scale?
5. `CAP_EXTRA_COLUMNS = 2` is the only unmeasured constant in this part. What do 1 and 3 do?
