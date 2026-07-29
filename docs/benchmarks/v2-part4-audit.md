# v2 Part 4 Audit — true edge-bounded satin

**Date:** 2026-07-28 · **Tag:** `v2-part4` · graded against [`v2-part3`](./v2-part3-summary.json)
**Grid:** [`v2-part4-grid.png`](./v2-part4-grid.png) · **Per-fixture:** [`v2-part4/`](./v2-part4/)

The rewrite [`v2-part2-5-audit.md`](./v2-part2-5-audit.md) §2 and
[`v2-part3-audit.md`](./v2-part3-audit.md) §8.4 both deferred: pair each stroke's two boundary
contours and generate columns between *corresponding* points, instead of offsetting a centreline by
a locally measured half-width.

**This part changes only HOW satin is drawn. It does not change WHICH objects are satin — verified
object by object in §5.**

---

## 1. What was actually wrong with measured-half-width columns

Parts 2 → 2.5 → 3 each improved the *measurement* of the half-width — distance transform, then a
ray-cast along the column's own direction — and each time edge-band coverage stayed under the tatami
baseline. Part 2.5 §2 identified why the distance transform was wrong; the ray-cast that replaced it
has its own version of the same flaw. **Both aim outward from the axis along an estimated direction,
and that direction comes from a 1-pixel stair-stepped skeleton.** Wherever the estimate tilts, the
end lands off the outline — short on one side, past it on the other.

Edge-bounded satin removes the estimate. A column end *is* a boundary point.

## 2. Correspondence across branch/merge topology — how it was solved

This is the part the earlier audits called the hard problem, and the solution is defined by what it
refuses to attempt.

**It never tries to split the region's contour into two global left/right arcs.** At a junction —
three strokes meeting, the contour weaving between them — no such split exists; that is precisely why
the earlier audits treated it as blocking. What exists instead is a *local* answer per branch.

1. **Partition the boundary by the skeleton's own topology.** Every boundary pixel is assigned to its
   **nearest axis branch** (`_nearest_axis`, `_assign_boundary`). Each branch therefore sees only the
   boundary belonging to it, and a junction fillet simply goes to whichever branch is nearest. The
   contour is divided by the medial axis rather than by any assumption about the shape.
2. **Parameterise within a branch.** A point gets `t` — arc length along that branch, refined by
   projecting onto the local tangent — and `side`, the sign of the cross product with the tangent.
3. **Corresponding points are equal `t`, opposite `side`.** Both arcs are resampled onto one shared
   grid (`_arc_at`), so column *k* connects genuinely corresponding boundary points.

Two refinements were forced by measurement, not anticipated:

- **One boundary point per station, the outermost** (`_extreme_per_station`). A stroke's boundary
  carries many pixels per column pitch and, around a corner, dozens share a `t`. Interpolating across
  those ties averages the endpoint *inward*: measured as a 1.4–2.1 point coverage loss on the first
  working version.
- **Pitch set by the faster boundary, not the axis** (`_pace_by_boundary`). On the outside of any
  curve, and at every junction where one arc sweeps a fillet while the other barely moves, an
  axis-paced pitch spreads columns apart on the fast side and leaves a fan of wedge gaps. Measured as
  a 0.6–1.3 point **interior** loss on fixtures 05/07/08.

## 3. Terminals (caps) and rings

Both fall out of the parameterisation; neither has a special code path in the column generator.

**Caps.** `t` is refined by tangential projection, so it keeps increasing *past* the last axis
sample rather than piling up on it. The grid therefore runs `CAP_EXTRA_COLUMNS` pitches beyond both
terminals; out there both arcs clamp to their own end point, so the pair converges onto the cap and
the terminal is stitched instead of stopping a half-width short (`_column_grid`).

**Rings.** A closed loop is detected by its axis returning to its start (`CLOSED_LOOP_TOL_PX`), and
is then the *simpler* case: no terminals to cap, and `t` is cyclic. `_arc_at` repeats each arc one
period either way so interpolation wraps, and the grid stops one pitch short of closing so the last
column sits beside the first. **5 of 293 branches across the corpus are closed loops** — fixture 04's
outer ring and 07's badge rings among them.

Both are covered by tests added in this part (§7).

## 4. The defect that was actually costing the coverage — and it predates this part

With edge-bounded columns in and both refinements applied, edge band was *still* only ~85–92%.
Painting the uncovered pixels rather than reading the summary showed the miss was a **thin dotted rim
running the whole length of every stroke** — not the ends, not the junctions.

`_emit_columns` was emitting both ends of every column with an alternating lead:
`A0 B0 B1 A1 A2 B2 …`. That puts two penetrations **one pitch apart on the same boundary, back to
back in the path**. At a 0.4mm satin pitch that is a 0.4mm stitch — under the project's 0.5mm
minimum — so `_coalesce_short` correctly deleted it. The effect was to **halve the needle
penetrations along both boundaries**, to 0.8mm apart under 0.4mm thread.

Strict alternation — `A0 B0 A1 B1 …`, every path step a full crossing — leaves nothing short enough
to be coalesced, and each boundary keeps a penetration every pitch. That single change is worth more
than everything else in this part:

| Fixture | edge band before the fix | **after** |
|---|---|---|
| 03 gradient_soft | 84.4% | **97.2%** |
| 05 wordmark_caps | 82.0% | **98.3%** |
| 06 wordmark_script | 90.2% | **99.8%** |
| 08 mascot_detail | 92.4% | **97.2%** |

This bug shipped in Parts 2, 2.5 and 3. It was invisible in those parts because the ray-cast
endpoints over-reached past the outline, partially papering over the missing penetrations — which
also explains why Part 2.5 §3's outward-bias knob appeared to buy coverage.

## 5. Classification is untouched — verified, not asserted

`_skeleton_satin` was restructured into two passes so this is structural, not incidental: the
classification widths come from `_axis_samples`, which reads the distance transform and feeds nothing
downstream. Column generation cannot influence it.

```
stitch_types, v2-part3 -> v2-part4
  01_flat_2color_logo        {'TATAMI': 2}                -> {'TATAMI': 2}                IDENTICAL
  02_logo_fine_text_3color   {'TATAMI': 4, 'SATIN': 12}   -> {'TATAMI': 4, 'SATIN': 12}   IDENTICAL
  03_gradient_soft_subject   {'SATIN': 2, 'TATAMI': 2}    -> {'SATIN': 2, 'TATAMI': 2}    IDENTICAL
  04_thin_line_outline       {'SATIN': 11}                -> {'SATIN': 11}                IDENTICAL
  05_wordmark_caps           {'SATIN': 6}                 -> {'SATIN': 6}                 IDENTICAL
  06_wordmark_script         {'SATIN': 12}                -> {'SATIN': 12}                IDENTICAL
  07_circular_badge          {'SATIN': 14, 'TATAMI': 4}   -> {'SATIN': 14, 'TATAMI': 4}   IDENTICAL
  08_mascot_detail           {'SATIN': 12, 'TATAMI': 9}   -> {'SATIN': 12, 'TATAMI': 9}   IDENTICAL
  09_nonuniform_background   {'TATAMI': 2}                -> {'TATAMI': 2}                IDENTICAL
  10_low_contrast_subject    {'SATIN': 2, 'TATAMI': 2}    -> {'SATIN': 2, 'TATAMI': 2}    IDENTICAL
  => all 10 fixtures identical stitch_types: True

per-object verdicts (seq, reason, decision) for all 96 objects:  IDENTICAL on every fixture
```

**Non-satin objects are untouched.** Fixtures 01 and 09 have no satin object and are bit-stable
across every metric: 1,632 and 1,006 stitches, 63 and 41 jumps, identical interior/edge-band/spill.
Colour counts, segmentation tier and `filled_area_mm2` are unchanged on all ten (e.g. 07
`6772.3 → 6772.3`, 08 `3020.6 → 3020.6`).

## 6. Coverage re-graded — interior and edge band, reported separately

Same methodology as Parts 2.5 and 3: rasterise the actual stitch path at 0.4mm thread, rasterise the
object outlines, measure interior (outline eroded 0.6mm), edge band (outline minus interior) and
spill (thread outside the outline).

The `v2-part2-5` column is the **tatami baseline** for 02/03/04/07/08/10, which were tatami then; for
05/06 it is Part 2.5's ray-cast satin, since those were already satin. The tatami reference for 05/06
is in [`v2-part2-5-audit.md`](./v2-part2-5-audit.md) §2 — **05: interior 84.5, band 84.1, spill 20.0;
06: 92.9 / 87.5 / 27.5**.

| # | Fixture | interior p2.5 → p3 → **P4** | edge band p2.5 → p3 → **P4** | spill p2.5 → p3 → **P4** |
|---|---|---|---|---|
| 01 | flat_2color_logo (control) | 98.7 → 98.7 → **98.7** | 94.6 → 94.6 → **94.6** | 2.1 → 2.1 → **2.1** |
| 02 | logo_fine_text | 99.0 → 99.0 → **99.0** | 96.8 → 96.9 → **97.3** | 3.7 → 3.7 → **3.7** |
| 03 | gradient_soft | 97.9 → 96.9 → **98.6** | 94.8 → 87.3 → **97.2** | 10.4 → 7.9 → **8.0** |
| 04 | thin_line_outline | — (no interior) | 99.6 → 96.7 → **99.9** | 54.0 → 46.6 → **47.3** |
| 05 | wordmark_caps | 96.3 → 95.5 → **99.8** | 85.5 → 82.2 → **98.3** | 12.6 → 11.2 → **12.2** |
| 06 | wordmark_script | 98.2 → 98.2 → **100.0** | 91.4 → 91.8 → **99.8** | 25.8 → 23.0 → **23.0** |
| 07 | circular_badge | 98.1 → 97.5 → **98.2** | 96.3 → 95.0 → **96.9** | 5.7 → 4.9 → **5.0** |
| 08 | mascot_detail | 98.6 → 97.8 → **97.8** | 95.8 → 92.3 → **97.2** | 5.4 → 4.0 → **4.5** |
| 09 | nonuniform_bg (control) | 99.0 → 99.0 → **99.0** | 93.3 → 93.3 → **93.3** | 3.9 → 3.9 → **3.9** |
| 10 | low_contrast | 98.6 → 98.6 → **98.6** | 94.9 → 94.4 → **95.2** | 3.0 → 3.0 → **3.0** |

**Edge band now beats the tatami baseline on every satin fixture** — 02 +0.5, 03 +2.4, 04 +0.3,
07 +0.6, 08 +1.4, 10 +0.3, and against the Part 2.5 tatami reference **05 +14.2 (84.1 → 98.3)** and
**06 +12.3 (87.5 → 99.8)**. That is the target the brief set.

**Interior did not pay for it.** Every fixture is at or above both prior parts except 08, which is
level with Part 3 (97.8) and 0.8 under the tatami baseline. 05 gains 4.3 points over Part 3 and 06
reaches 100.0.

**Spill is essentially flat** and stays under the tatami baseline on 03, 05 and 06 — the metric
Part 2.5 §4 introduced to show tatami buys edge band by overshooting. Satin no longer needs that
argument: it wins on edge band outright while spilling no more than before.

## 7. An outward bias, measured and rejected — again

While the coalescing defect of §4 was still in place, a half-pixel outward bias looked justified: a
contour point is the centre of the outermost pixel *inside* the shape, so half a pixel of reach is
arguably owed. Sweeping it:

| bias | 03 band / spill | 05 band / spill | 04 band / spill |
|---|---|---|---|
| **0.0px (shipped)** | **97.2 / 8.0** | **98.3 / 12.2** | **99.9 / 47.3** |
| 0.5px | 97.2 / 9.7 | 98.4 / 15.6 | 100.0 / 55.3 |
| 1.0px | 97.3 / 11.4 | 98.3 / 19.1 | 100.0 / 60.1 |
| 1.5px | 97.3 / 12.7 | 98.3 / 22.3 | 100.0 / 64.1 |

Once §4 was fixed the bias buys **nothing** — edge band is already 97–100% — and costs spill
throughout. Removed, and the constant deleted rather than left at zero. This is the second time this
knob has been measured and declined (Part 2.5 §3); recording it so the choice stays auditable.

## 8. Costs

**Stitch count is up 30% corpus-wide** (26,031 → 33,759), concentrated in the satin fixtures: 05
1,079 → 1,962, 06 1,000 → 1,691, 07 7,161 → 9,165. Two causes, both intended:

1. §4's fix restores the penetrations coalescing was deleting — roughly a doubling on satin edges.
   The earlier counts were *artificially low* because half the intended stitches were being dropped.
2. `_pace_by_boundary` adds columns where a boundary runs faster than the axis.

Density on satin objects rises accordingly (05 1.25 → 2.27 st/mm², 08 1.37 → 2.12). Comparing that
to the v1 audit's "professional 0.62 st/mm²" would be wrong — that figure is for tatami fills. But
the honest risk is real: **on the inside of a tight curve, boundary-paced pitch puts penetrations
closer together than the pitch**, which in real production can perforate light fabric. Nothing in the
current metric set detects that, and no fixture in the corpus is tight enough to show it.

**Runtime 12.8s → 13.2s** for ten designs (+3%). **Jumps are exactly flat** (2,046 → 2,046).

**Machine limit, straight from the JSON:** `stitches_over_machine_limit = 0` on all ten fixtures;
max stitch 8.96mm; sub-0.5mm stitches 0–1 per fixture.

## 9. What is still wrong

1. **Fixture 08 interior is 97.8%, still 0.8 under its tatami baseline** — the only coverage number
   in the corpus that has not recovered. Its satin objects are the mascot's ears and whiskers, where
   short branches meet at shallow angles and the nearest-branch partition splits a fillet awkwardly.
2. **Inner-curve penetration density** (§8) is unmeasured. A "minimum penetration spacing on the
   concave side" metric is the missing instrument.
3. **The nearest-branch partition is a Voronoi assignment**, so at a junction the boundary is split by
   a straight bisector rather than by anything the stroke geometry implies. It works on this corpus;
   a very asymmetric junction (a hairline meeting a thick stem) could hand the fillet to the wrong
   branch.
4. **Fixture 04's 47.3% spill** persists and is still a unit artifact: 0.28–0.62mm strokes traced with
   0.4mm thread must spill. Tatami spilled more (54.0%).
5. **Fixture 03's annuli remain the weakest satin *call*** — the Part 3 §8.2 objection stands, even
   though the drawing is now excellent (band 87.3 → 97.2). This part fixed how they are stitched, not
   whether they should be.

## 10. Verification

```
pytest — WITH rembg:     95 passed, 1 warning in 20.62s
pytest — WITHOUT rembg:  95 passed, 1 warning in 6.14s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

Five tests added, 90 → 95 collected: closed-loop detection and wrap,
ring stitching without a seam across the hole, columns reaching an open stroke's terminal caps, the
ray-cast fallback, and a regression guard on §4 (no sub-pitch along-edge steps in a satin path).

**Coverage — `pytest --cov`, actual percentages, not pass counts:**

```
app/services/digitizer.py     933 stmts    51 miss    95%     (was 91% before this part)
new code added by Part 4:    ~184 stmts     9 miss    ~95%
```

Per added function: `_boundary_points`, `_axis_frame`, `_nearest_axis`, `_extreme_per_station`,
`_arc_at`, `_column_grid`, `_pace_by_boundary`, `_raycast_columns`, `_axis_branches`,
`_uncovered_mask` — **fully covered**; `_assign_boundary` 3 lines, `_column_ends` 3,
`_emit_columns` 1, `_axis_samples` 1, `_satin_columns` 1 uncovered (empty-input and degenerate-branch
guards).

**Size limits.** All 15 functions added by this part are ≤50 lines (largest: `_assign_boundary` 44,
`_column_ends` 40). `_skeleton_satin`, which existed before and was rewritten here, went **133 → 53
lines** (39 excluding its docstring). Pre-existing long functions not rewritten in this part
(`digitize_image` 336, `rebuild_design` 129, `_skeleton_branches` 76) are unchanged. File:
1,775 lines.

**No secrets or hardcoded values introduced.** The diff contains no credential-shaped strings
(scanned for key/secret/token/password/bearer/private-key/URL-embedded credentials). Four new
numeric constants, all named and commented at module level: `CLOSED_LOOP_TOL_PX = 2.5`,
`MIN_ARC_SAMPLES = 4`, `CAP_EXTRA_COLUMNS = 2`, `PROJECT_CHUNK = 256`.

**Lint.** `ruff check` reports **14 findings, exactly the pre-existing count** — this part introduced
none. (The 14 are pre-existing and out of scope.)

**Commits** use conventional prefixes (`feat:`, `fix:`, `docs:`, `test:`).

**A gap in this section, stated rather than papered over:** the Engineering Standards document is not
in the repository, so the specific thresholds above (≤50 lines/function, a coverage floor) are the
conventional ones I applied, not ones I could read off the standard. The raw measurements are all
given so any threshold can be checked against them.

Scope: `app/services/digitizer.py` and `tests/test_digitizer.py`. Classification thresholds
(`SATIN_MAX_W_MM`, `SATIN_MAX_UNCOVERED`, `SATIN_PREGATE_SLACK`), background separation, colour/layer
logic and the Part 0–3 renderer are untouched.

## 11. What to attack

1. §4 says a bug present since Part 2 was masking the real edge coverage, which means three earlier
   audits reported satin edge quality against a handicapped baseline. Does that invalidate the
   conclusions those parts drew — particularly Part 2.5 §4's spill argument?
2. Boundary-paced pitch (§2) buys interior coverage by adding stitches. At what curvature does it
   become fabric damage rather than coverage, and should there be a hard floor on penetration spacing?
3. The nearest-branch partition (§9.3) is a Voronoi split. Construct the asymmetric junction that
   breaks it.
4. 30% more stitches for 5–14 points of edge band (§8). Is that the right trade at production scale?
5. `CAP_EXTRA_COLUMNS = 2` is the only unmeasured constant in this part. What does 1 or 3 do?
