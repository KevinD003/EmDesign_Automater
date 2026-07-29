# STITCHIQ v2 — Part 6 Work Report for Independent Review

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part6-audit.md`](./benchmarks/v2-part6-audit.md)

> Part 5 built the penetration-density metric, measured the damage, and left enforcement off so the
> decision could be taken on its own evidence. This is that decision, taken: **the floor is now
> enforced, and corpus violations go 3,235 → 3.**
>
> **§3 is the finding worth arguing with. It is not flattering to Parts 4 and 5, and it includes a
> visible regression I am not going to bury.**

---

## 1. Result

| | before | after |
|---|---|---|
| same-side penetration violations (corpus) | 3,235 | **3** |
| minimum penetration, worst fixture | 0.000mm | **0.300mm** |
| stitches over the 12.7mm machine limit | 0 | **0** |
| classification verdicts (96 objects) | — | **all identical** |
| colours / segmentation / filled area | — | **all identical** |
| corpus stitches | 33,759 | 29,116 (−13.8%) |

On the curvature probe — rings, which isolate the mechanism because they have no terminals —
violations go to **zero at every radius**, and the cost is negligible above `R = 4w`
(interior 100.0 → 98.5) but severe at `R = 1.25w` (edge band 99.6 → 53.7).

## 2. Two cleverer ideas, both implemented, both rejected on measurement

Deleting a whole crossing to fix one boundary looks wasteful, so I built the alternatives before
settling for it:

| strategy | residual violations | mean interior | mean edge band |
|---|---|---|---|
| **drop the column (shipped)** | **3** | 95.84 | 94.28 |
| slide the end along its boundary | 245 | 96.60 | 95.33 |
| retract the end along its column | 44 | 96.61 | 95.34 |

Both buy about half a point of coverage and give up the guarantee. They fail for the same underlying
reason in two forms: **moving a penetration instead of removing it only relocates the crowding.**
Sliding forward shortens the gap to whatever comes next. Retraction shortens the *column*, and a
column under the 0.5mm minimum stitch length loses a point to `_coalesce_short` further down the
pipeline — which breaks the A-B-A-B alternation and manufactures new same-side adjacencies. A strict
second pass rescued neither (59 and 45), because by then the damage is downstream of the function
doing the enforcing. Both implementations were deleted rather than parked behind a flag.

I also swept the floor value hoping for a cheap knee. **There isn't one** — coverage falls smoothly,
~0.5 points of interior per 0.05mm, and even removing only the exact duplicates costs a full point,
because a duplicate column still lays a full crossing of thread. The value rests on the safety
argument alone, and `MIN_PENETRATION_MM = 0.30` is still asserted from general practice rather than
measured on fabric.

## 3. The finding worth arguing with: the floor exposed geometry that overdraw was hiding

Fixture 05's wordmark now shows **visible gaps at the `M` and `U` junctions** that were not there in
Part 5. Interior 99.8 → 89.3, edge band 98.3 → 88.5. Fixtures 06 and 08 move the same way; the ring
probe, which has no junctions, barely moves at comparable radii.

That pattern is the explanation. At a junction one boundary arc genuinely stalls, because the
nearest-branch partition hands a branch a fillet that doubles back — the weakness **Part 4 §9.3 named
as a Voronoi split and left standing**. The columns generated there were already wrong: they
overlapped heavily, and their surplus thread was painting over the gap. **The floor did not create
the junction hole; it removed the overdraw that was hiding it.**

Which means **Part 4 and Part 5's junction coverage numbers were flattered by duplicate stitching** —
the second time in this sequence that a measurement has invalidated an earlier part's comparison
(Part 4 §4 was the first). The real fix is the junction-aware boundary partition, not the floor, and
it should recover most of 05/06/08. That is the next part.

**And a product judgement I should not make alone:** this ships a visibly worse wordmark today to buy
a safety property the user cannot see, on the argument that the wordmark was never as good as it
looked. If you would rather hold enforcement until the junction fix lands, say so — reverting is one
constant (`_PENETRATION_FLOOR_MM = None`) and the measurements are all reproducible either way.

## 4. Residual

Three violations remain, all on fixture 07 and unchanged from Part 5: **2 in the running-stitch
underlay** (which the floor does not govern — the medial-axis underlay can double back sharply enough
to put two penetrations 0.18mm apart) and **1 in a 0.63mm-wide column**, most likely `_coalesce_short`
breaking the alternation. 0.01% of the corpus, still not chased to certainty, still flagged as
unproven rather than asserted.

## 5. A bug this part found in its own instrument

`measure_stitch_quality.py --floor-mm` defaulted to `None` and *called*
`set_penetration_floor(None)`. That meant "report only" in Part 5, but once Part 6 turned the floor on
by default it silently **disabled enforcement** for every CLI run. Caught because a `--fixture 05`
run printed the floor-off numbers. Absent the flag the shipped default now stands; `--no-floor` is the
explicit way to reproduce the before/after.

Same class of mistake in the tests: one test disabled the floor in a `finally` and leaked that state
into the rest of the session, which is how the first version of `test_floor_is_enforced_by_default`
failed. An autouse fixture now restores the default after every test.

## 6. Verification

```
pytest — WITH rembg:     108 passed, 1 warning in 22.97s
pytest — WITHOUT rembg:  108 passed, 1 warning in  6.75s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

| §1 Coverage (floor 80%) | Stmts | Miss | Cover |
|---|---|---|---|
| `app/services/digitizer.py` | 965 | 52 | **95%** |
| `scripts/measure_stitch_quality.py` | 166 | 8 | **95%** |
| `scripts/run_quality_bench.py` | 248 | 87 | **65%** ⚠ pre-existing, unchanged by this part |

**§3 Size.** Nothing added or edited here exceeds 50 lines (`_main` hit 51; `_apply_floor` was split
out). Pre-existing over-limit functions named as the standard requires: `digitize_image` 336,
`rebuild_design` 129, `_skeleton_branches` 76, `_skeleton_satin` 54. `digitizer.py` at 1,877 lines
remains the standing exception.

**§4 Security.** Secrets scan clean; no new constants. **§1 Lint.** `ruff` 15 findings, exactly the
pre-existing count. **§5 Commits.** Conventional prefixes.

## 7. What to attack

1. §3 — should Parts 4 and 5's junction coverage tables carry a correction note?
2. `MIN_PENETRATION_MM = 0.30` is asserted, and §2 shows cost is linear in it. Right number? Should it
   vary with `fabric_type`, which the pipeline already takes?
3. Is shipping a visibly worse wordmark, today, the right call before the junction fix?
4. Drop beat retraction on the guarantee (3 vs 44). Is 44 in ~27,000 penetrations actually unsafe, or
   is that over-caution paid for in coverage?
5. The underlay doubling back (§4) is a producer no floor currently governs. When does that get fixed?
