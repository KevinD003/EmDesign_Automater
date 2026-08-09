# 1a — emission order on badge Satin 3: mechanism, partial

**Status: NOT fully diagnosed. 1b not started.** I have reproduced your measurement exactly,
localised the jumps to one stage, and **refuted four candidate mechanisms with measurement** —
including both of the ones you named and one of my own. About 100 of the 171 jumps remain
unattributed. Reporting here rather than drilling further, because you asked for the mechanism
before the fix and a partial answer that names what it has *excluded* is more useful than a guess.

## Reproduced

| | jumps | median | p90 | max | total |
|---|---:|---:|---:|---:|---:|
| your instrumentation | 171 | 42.3 mm | 66.0 mm | — | — |
| mine, at the router call | 171 | **42.31 mm** | 66.01 mm | 67.88 mm | 6,109 mm |

104 of the 171 (61%) are over 20 mm, totalling 5,770 mm. Same object, same numbers.

## Localised: the jumps are born in the generation core, not downstream

| stage | jumps | median |
|---|---:|---:|
| `spine_satin` output (the core) | 166 | **44.46 mm** |
| what `_route_travel` is handed | 171 | 42.31 mm |

The router receives what the core produced. It is not creating these, and neither is the underlay
(183 stitches on this object) or the finishing chain.

## Refuted, each by measurement

**1. Contour fidelity** — 0.2% area error, ~1% of the gap. Already reported.

**2. Branch ordering (your first candidate, and my hypothesis too).** The medial axis of this
3-holed ring band *is* split into segments — 58 branches, 3,515 samples. I found `_skeleton_branches`
enumerates from `for node in nodes:` where `nodes` is a **set**, so branch order is Python hash
order, and I expected that to be the answer. It is not:

| branch order | median gap | p90 | max | total |
|---|---:|---:|---:|---:|
| as shipped | **0.00 mm** | 5.12 mm | 61.39 mm | 181.9 mm |
| greedy nearest-neighbour reorder | 0.00 mm | 5.12 mm | 61.39 mm | 181.9 mm |

Branches already come out essentially contiguous. Reordering them by adjacency changes the total
inter-branch travel by **0.0%**. The set-iteration order is a latent fragility worth fixing on its
own merits, but it is **not** causing this.

**3. Column sweep ordered on a bounding-box axis rather than the spine (your second candidate).**
Instrumented `_emit_columns` directly: **zero** jump-flagged transitions inside any single branch's
columns. Columns within a branch are adjacent, as they should be.

**4. Branch seams.** 55 seams measured, **median 6.44 mm**, p90 16.07 mm, max 38.59 mm. Real, but an
order of magnitude short of a 44 mm median, and far too few to account for 166.

## Found so far

**The wide-remainder tatami is 35% of this object and structurally jumpy.** The satin core appends
`_fill_by_component` over the parts too wide for a column:

- 1,176 of 3,324 core points (35%)
- across **11 disconnected components**, each requiring a jump to reach
- columns themselves account for only 2,148 points

So a third of what looks like "satin" on this object is scattered tatami patches around a ring, and
reaching them costs a jump each.

## What remains

Accounted for: ~57 branch seams (6.44 mm median) + ~11 remainder components. That is roughly 68 of
166 jumps, and the seams are far too short to produce a 44 mm median. **About 100 long jumps are
still unattributed.**

The next place to look is `_column_ends` / `_assign_boundary` in `columns.py` — the pairing of
boundary points to axis frames. On a ring, the boundary comprises an outer contour plus three hole
contours; if pairs are produced in boundary-traversal order rather than along-axis order, columns
would be emitted in an order that hops between the outer rim and the hole rims. That fits a ~44 mm
median on a shape of this size, but **I have not measured it and am not asserting it.**

## Judgement, unchanged

Your amendment stands regardless of which sub-stage it turns out to be: this is a **sequencing**
defect, not a cost-model one, and recalibrating `DETOUR_COST_MAX` can only choose between 21 minutes
of travel and 277 trims. I will not touch the cap until 1b lands.

One thing the ablation already tells us about the acceptance target: **the columns are only 2,148 of
3,324 core points.** A correctly-sequenced ring-band satin should be dominated by those columns with
near-zero travel — so the 4–6k stitch estimate I gave for this object still looks right, and the
scattered wide-remainder patches may deserve their own look (11 disconnected tatami islands inside
one satin object is a classification smell, not just a routing one).

## Next

1. Finish 1a — instrument `_column_ends` / `_assign_boundary` pairing order and attribute the
   remaining ~100 jumps. Report again before building.
2. Then 1b as you scoped it.
3. Machine-minutes **net of trim cost** stays the headline metric throughout.

B2 continues in parallel.
