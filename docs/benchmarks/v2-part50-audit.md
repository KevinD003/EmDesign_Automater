# v2 Part 50 — R004-impl D0/D1: the instrument, and a field that nothing consumes

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** D0 and D1 from `docs/PROMPT-direction-field.md`, and stop there. No stitch
output change.

**Verdict: D1 is worth taking to D2, with one honest limitation that shapes what D2 has to
do.** On the photographed sew-out — the one reference that is not circular — the solved
field beats the current per-object angles by **4.4°** and the trivial baseline by **11.1°**,
and nearly doubles the share of the design within 15° of the real thread. Solve time is
**0.06–0.09 s** on the reference panel.

Stitch output is unchanged: **4 stream locks and 10 visual baselines untouched**, because
nothing reads the field.

---

## 1. D0 — an instrument that can rank candidates

`measure_stitch_direction.py` can only score a design that has already been stitched. That
was enough to prove per-region angles are at their ceiling (Part 46, 49.9°) and useless for
steering, because you cannot try a field without first wiring it into a generator.

`scripts/measure_direction_field.py` scores a **field** against a reference orientation
field, so candidates are ranked before anything consumes them. Three are built for every
fixture: the current per-object angles expressed as a field, the solved field, and a
constant 45° — the trivial baseline anything must beat.

**Self-test, extended past stripes.** The old test only proved the instrument can read a
*constant* orientation. A field that varies per pixel is the case this part exists for, so
two synthetic fields with analytic truth were added:

| case | median error | tolerance |
|---|---:|---:|
| stripes, 6 angles | ≤1.4° | 3.0 |
| radial spokes | **1.88°** | 8.0 |
| concentric rings | **1.71°** | 8.0 |

**Structure, not one scalar.** Each score carries `median`, `within_15_pct`,
`within_30_pct`, a 3×3 spatial breakdown, the Part 46 `qualified_share` (how much of the
mask had reference structure at all — low means *this artwork cannot answer the question*,
not *the field is bad*), and `committed_share` (how much the candidate is actually
confident about).

**A flaw in my own instrument, found and fixed mid-part.** The first version weighted each
pixel by the candidate's own confidence. A per-object field has confidence 1.0 everywhere;
a diffused field does not — so the diffused field was scored mostly where it happened to be
sure, and the comparison flattered it. Measured on the panel, that bias was worth **2.2°**
(31.73 → 33.91). Weights are now uniform over the qualified set: a candidate does not get
to choose which pixels it is judged on. A test pins it.

## 2. D1 — the field

`app/services/direction_field.py`. Representation is the **doubled angle**: a stitch
direction has no head or tail, so θ and θ+π are the same and averaging them raw puts
mean(179°, 1°) at 90° — exactly wrong. Everything operates on (cos 2θ, sin 2θ) and halves
back at the end.

Solver, deliberately the cheapest thing that could work: seed the field on the foreground
boundary with **the boundary's own tangent**, then diffuse inward by repeated
blur-and-reseed, which is Laplace with Dirichlet edges. The tangent comes from the contour
polyline, not an image gradient — a gradient at a mask edge is the *normal*, and using it
would put the field at right angles to the shape everywhere.

That produces **contour-parallel flow**: thread that follows the outline, which is what a
digitizer does for a petal, a leaf, or a ring.

## 3. What the pictures show

`docs/benchmarks/v2-part50-field/` — eleven panels, each *source | current per-object |
solved field*.

**`07_circular_badge.png` is the clearest case.** The badge's rings currently receive one
near-vertical angle across the whole annulus — a circular border stitched in vertical rows,
which is the "printed, not stitched" look. The solved field runs concentrically around the
rings, and the star's points follow the star's own edges.

**`08_mascot_detail.png`** shows the same on organic shapes: currently the head is vertical
and the muzzle diagonal, two unrelated angles meeting at a seam; the field flows around the
head, the muzzle and the ears continuously.

## 4. Scores

**Against the photographed sew-out** — the reference that matters, because its structure
tensor reads *real thread*, not artwork edges. 83% of the mask qualified:

| candidate | mean | median | within 15° | within 30° |
|---|---:|---:|---:|---:|
| constant 45° | 45.02 | 45.59 | 11.5% | 32.5% |
| per-object (current) | 38.27 | 29.80 | 20.8% | 50.4% |
| **solved field** | **33.91** | **27.67** | **34.3%** | 52.4% |

**Against the ten bench fixtures**, solved wins 9 of 10:

| | mean over fixtures | median |
|---|---:|---:|
| per-object | 41.76 | 44.12 |
| **solved** | **32.59** | **33.38** |
| constant 45° | 46.27 | 44.97 |

**Read the bench numbers with a caveat I have to state, because it cuts against my own
result.** On flat artwork the reference orientation field is dominated by the artwork's own
*edges*, and the solved field is seeded from those same edges — so agreement there is partly
circular. That is why the panel is the headline and the bench is supporting evidence. It is
also why `qualified_share` sits at 0.09–0.27 on most fixtures: flat art has almost no
interior structure to be right or wrong about. The two exceptions are the fixtures with
real interior variation — `03_gradient_soft_subject` at 0.86 qualified, where the field
scores **19.39 against 42.66**.

One number worth not conflating: per-object scores 38.27 here and Part 46 reported 49.9°.
Those are different quantities — Part 46 scored the **stitches actually sewn**, this scores
the **angle assigned to each region**. Neither is an improvement on the other.

## 5. The limitation that shapes D2

The field is strong near boundaries and **washes out in large interiors**. Share of the mask
where confidence exceeds 0.30:

| fixture class | committed share |
|---|---:|
| thin strokes (`04`, `05`, `06`) | **81–94%** |
| large flat areas (`01`, `02`, `07`, `08`, `09`, `10`) | **7–14%** |

That is exactly what boundary-seeded diffusion should do, and it is a real gap: a fill needs
a direction *everywhere*, including the middle of a big shape. The complementarity is
convenient — the field is most confident precisely where one-angle-per-region is worst
(borders, rings, thin strokes), and least confident where one angle is adequate — but D2
cannot assume it. **D2 must decide what happens where the field is undecided**, and falling
back to the region's principal axis is the obvious candidate to measure first.

## 6. Cost — bounded before anything depends on it

The mask is solved at 384 px on its longest side, so cost is fixed by resolution rather than
by how many contours the input contains. That bound is deliberate: Parts 48 and 49 both
shipped per-region work inside the pre-filter contour loop, where the multiplier is the
*noise* count, and both were caught only by the fuzz suite.

| input | contours | solve |
|---|---:|---:|
| bench fixtures (10) | — | **23–71 ms** |
| reference panel, 771 regions | — | **60–91 ms** |
| 600×600 noise | 24,737 | 0.374 s |
| 900×900 noise | 55,839 | 0.392 s |
| 1500×1500 noise | 154,449 | **0.405 s** |
| 4000×4000 solid | — | 0.055 s |

**Flat, not linear in contour count** — a 6× rise in contours costs 8% more time. A test
asserts that shape directly rather than a wall-clock number alone.

## 7. Gates

| Gate | Result |
|---|---|
| Self-tests on stripes **and** a nontrivial field | ✅ 1.71–1.88° on radial and rings |
| Ranks ≥2 candidates on the same artwork | ✅ three candidates, 9/10 fixtures to solved |
| Qualified-subset reporting preserved | ✅ plus `committed_share` |
| Visualisations for all ten fixtures | ✅ eleven panels, plus the panel |
| Readable for a digitizer's eye | ✅ see §3 |
| Stream locks unchanged | ✅ 4 pass |
| Visual baselines unchanged | ✅ 10/10 |
| Cost measured and bounded | ✅ §6 |
| No stitch-output change | ✅ nothing consumes the field |

**Abandon condition not triggered.** The brief says to stop if the field is not visibly
better than the current per-object axes. It is — on the picture and on the one
non-circular score.

## 8. Files

- `apps/backend/app/services/direction_field.py` — the field, solver, and the two comparison fields
- `apps/backend/scripts/measure_direction_field.py` — D0 instrument
- `apps/backend/scripts/visualise_direction_field.py` — D1 renderer
- `apps/backend/tests/test_part50_direction_field.py` — 14 tests
- `docs/benchmarks/v2-part50-field/` — eleven panels

## 9. Next — D2, with its first question already known

Fills consume the field, tatami first. The open question is not whether to use the field but
**what to do where it is undecided**, which §5 measures at 86–93% of a large flat region.
Falling back to the region's principal axis there is the first thing to try and the first
thing to measure.

No target is written down. The brief said to derive one from the instrument, and what the
instrument shows is that 33.91° is achievable on the panel against 38.27° today — so D2's
bar is "beat 38.27 on the panel without losing coverage", not a number picked in advance.
