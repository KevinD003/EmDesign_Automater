# PROMPT — Rebuild the stitch engine on graph foundations

*Paste this whole file as the opening prompt of a fresh session. It is written to be
executed without re-deriving anything: every number below was measured, and every dead
end is fenced off so you do not spend the session rediscovering it.*

---

## Mission

STITCHIQ's digitizer gets **shape, border, colour and texture right** and its stitches
still do not look like a real sew-out. The cause is established and measured: **stitch
direction is decided locally and independently, region by region, when it is globally a
connected problem.** Fix that by re-founding the stitch stage on graph formulations —
direction as a field solved on a graph, regions consolidated on an adjacency graph,
sequencing as a traversal, linework as an actual graph.

Work in `/home/user/EmDesign_Automater` on branch
`claude/code-quality-improvements-hyu6dg`. The engine is
`apps/backend/app/services/digitizer.py` (~4,300 lines).

---

## 1. Ground truth — measured, do not re-measure

Test input: `apps/backend/tests/fixtures/corpus100/A03_real_neckline_panel.png`
(a photograph of a real embroidered neckline panel), digitized at hoop `360x350`,
`max_colors=12`.

**Current baseline (this is what you must beat):**

| Metric | Value | Tool |
|---|---|---|
| Stitch-direction error vs the real sew-out | **mean 49.9°, median 54.1°, within-15° 15.8%, within-30° 29.5%** | `scripts/measure_stitch_direction.py` |
| …by type | satin **49.3**, tatami **48.9**, running **52.6** | same |
| Interior coverage | 97.10 | `scripts/measure_stitch_quality.py` |
| Edge-band coverage | 94.20 | same |
| Spill | 16.50 | same |
| Floor violations / density flags | 0 / 0 | same |
| Objects | **1,014, median 16 stitches, 79% under 40** | — |
| Trims / jumps | **1,080 / 2,014** on 57,027 sewn | — |
| One colour mask | **45,092 px in 125 components** (largest 1,767) | — |

45° is a coin flip. **We are at 49.9° — our stitch directions carry no information about
the real ones.** That single number is the target.

**Already proven, so do not re-investigate:**

- The **satin generator is sound**. Same-side spacing on clean synthetics: straight bar
  median 0.450 / p90 0.464; curved ring 0.453 / 0.537; tight r=10mm ring 0.454 / 0.544.
  It holds pitch on curvature. It degrades (median 0.547, 28.9% over 0.6mm) *only* on the
  ragged photographic region map — a symptom of bad input regions, not a bad generator.
- **Fills already cover their regions**: 224 fills, **zero** below a 93% gate, worst first
  attempt 98.5%. Coverage is not the defect.
- **Long sewn stitches are not a defect**: 0.51% over 5mm, 1.6% of thread length.
- An **18×18mm flower is ONE object at a single −42° angle**. In the source that area is
  five satin petals with five directions. This is the defect, in one sentence.

---

## 2. Fenced-off dead ends — re-attempting these is a session wasted

| Attempt | What happened | Why it is closed |
|---|---|---|
| **Lobe separation by watershed on the mask** | Cut concave regions at their necks. Big fill blobs *did* become satin (objects >200 stitches 5 → 39) | It **destroyed 34% of the declared outline area** (1,034,193 px vs 1,569,069) and **spill rose 16.4% → 36.3%**. Cutting the MASK removes area. If you partition, partition the *skeleton graph* and assign every pixel to a branch — lose nothing |
| **Stronger contour smoothing** | Swept eps 0.10→0.40, Chaikin 1→3 | Worse on both interior and edge at every setting. Shipped values are already optimal |
| **Wider morphological close on textured masks** | 0.4mm → 0.6/0.8/1.0mm | Object count **rises** (1,014 → 1,143). Morphology is not the consolidation lever |
| **Verifying that a fill covers its region** | Built stitch→measure→re-aim | Never fires (see above). Dead code |
| **Reading the fill angle from the source's structure tensor** | Validated field, drove `_fill_angle` from it | Gain **within noise** (49.6 → 49.1 mean) because it reaches only the 224 tatami fills; **560 satin objects take their angle from the medial axis**. The idea is right, the insertion point was wrong — it must feed *all* stitch types |
| **Refusing satin so the measured angle can fill instead** (Part 39) | Every gate improved: direction **49.9 → 42.5**, interior 97.30, edge **96.20**, spill 16.00 | It **floods enclosed gaps**: the lattice diamonds fill solid with thread (`v2-part39-lattice-flood.png`). A satin path follows the axis so gaps never matter; a fill floods any hole not captured in `hole_contours`. **Fix the hole capture BEFORE re-trying anything that converts satin to fill** — and note the metrics *rewarded* the flooding |

**Two facts established in Part 39, carry them forward:**
- The ~50° error is **not** registration noise: well-registered segments measure 50.3°, mis-registered ones 47.8°. The target is legitimate.
- By **segment count** it is satin **30,332** vs tatami **3,794** (~8:1), not the 560/224 object split. Anything touching only fills cannot move the number.

---

## 3. The work — four graph formulations

### G1. Direction as a field on a graph (the headline fix)

Replace "one angle per region" with **one smooth angle field per colour layer**, solved
globally.

- **Nodes**: foreground pixels (or superpixels, if you need the speed) of one colour layer.
- **Edges**: 4- or 8-neighbours.
- **Unary evidence** per node, whichever are available:
  - medial-axis tangent, propagated from the skeleton (always available);
  - the **source's own thread direction** where the input is a photographed sew-out —
    `_orientation_field` in `scripts/measure_stitch_direction.py` is validated
    (**worst error 1.4°** on synthetic stripes at 0/30/45/60/90/120°) — weight it by its
    coherence so flat areas abstain;
  - boundary tangent near the outline, which is what makes a fill hug its own edge.
- **Pairwise**: smoothness between neighbours. **Angles are axial** — 179° and 1° are
  nearly the same direction — so never average raw degrees. Represent each node as the
  doubled-angle unit vector `(cos 2θ, sin 2θ)`, diffuse/optimise *that*, and recover
  `θ = ½·atan2(y, x)`. Getting this wrong is the classic failure and it looks like
  random noise at 0°/180° seams.
- **Solve**: Laplacian/heat diffusion on the doubled-angle vectors is the cheap correct
  start; graph cuts over quantized angle labels if you need discrete regularisation.
  Anisotropic weights (weaker smoothing across a strong image edge) are what keeps two
  petals from bleeding into one direction.
- **Consume**: generalise `_scanline_angled` into a guided fill whose rows are level sets
  of a potential integrated from the field. Then feed the *same* field to satin
  (`_skeleton_satin` / `_satin_columns`) so all 1,014 objects move, not 224.

### G2. Region consolidation on a region-adjacency graph

1,014 objects with median 16 stitches is the fragmentation that degrades satin pitch and
inflates trims. Morphology is ruled out. Do it structurally:

- **Nodes**: connected components of a colour layer. **Edges**: components within a
  thread-width or two, weighted by gap width, colour distance and direction agreement
  (from G1 — two fragments of one petal will agree).
- Merge by connected components over a thresholded edge set, or by modularity/spectral
  clustering. Merged fragments become **one object with one continuous stitch path**
  rather than N objects with N tie-offs.
- Guard: never merge across a *real* gap the source leaves as bare fabric — see §5.

### G3. Sequencing as graph traversal

1,080 trims and 2,014 jumps on 57k stitches is far above what a professional file shows.

- Within a colour block: objects as nodes, entry/exit points and travel distance as edge
  weights → **TSP** (2-opt / Christofides is plenty). `services/optimizer.py` already does
  a nearest-neighbour pass at the object level; this wants to run at the *stitch-path*
  level with real entry/exit choice.
- Across colours: order the colour blocks to minimise re-threads, respecting layering
  (underlay before top, knockouts before overlay).
- Prefer a **hidden travel run under a later layer** over a trim wherever one exists —
  that is a reachability query on the layer graph.

### G4. Linework as a literal graph

The lattice trellis (a documented failure — it digitizes to zero objects on a dark
background, and to fragments elsewhere) **is a graph**: crossings are nodes, bars are
edges.

- Skeletonise, build the graph, and stitch it as an **Eulerian path / Chinese postman**
  so each bar is one continuous satin column, traversed once, with minimal doubling.
- This replaces dozens of disconnected stubs with a continuous, professional-looking
  trellis, and it generalises to stems, tendrils and outline networks.

---

## 4. Success criteria — all must hold

**Primary (the point of the work):**

- Stitch-direction error **mean ≤ 30°** (from 49.9) and **within-15° ≥ 35%** (from 15.8%)
  on the neckline panel, measured with `scripts/measure_stitch_direction.py`.
- The improvement must appear in **all three types** (satin, tatami, running), not one.

**No-regression (hard gates):**

- Interior ≥ **97.10**, edge band ≥ **94.20**, spill ≤ **16.50** on the same design.
- Floor violations **0**, density flags **0**, over-limit sewn stitches **0**.
- `scripts/run_corpus100.py`: **0 crashes**, designs producing zero stitches **≤ 9**,
  tier-A interior median ≥ **99.05**, tier-B ≥ **95.90**.
- 10/10 byte-identity locks either untouched, or regenerated **deliberately** with the
  before/after diff measured and recorded (the established practice).

**Secondary (expected to follow, report either way):** trims well under 1,080; median
stitches per object well above 16.

---

## 5. Rules of engagement — these are not optional

1. **Validate every instrument before trusting its verdict.** This project has had a
   measuring instrument wrong **three times**: wrong dict keys (`floor=-88`); an
   over-limit count that included jump and post-trim travel (285–865 phantom violations
   on clean designs); and — worst — a change rejected by comparing it against a reference
   outline **that the change itself had shrunk by 34%**. When a change alters the
   reference, the metric stops being a comparison. Score both variants against **one
   common reference**.
2. **Measure, do not theorise.** Every claim in §1 came from a measurement, and several
   plausible theories died on contact with one. Build the probe first.
3. **Accept only if better.** Prefer designs where a new path is adopted per-object only
   when it measures better than the old one — that makes regressions structurally
   impossible and is why this is worth doing at all.
4. **Revert what does not pay.** Four experiments were reverted this session, correctly.
   Shipping a change whose benefit is inside the noise is worse than shipping nothing.
5. **State negative results plainly** in the audit. They are the most valuable output
   after working code.
6. **We stitch things the source leaves bare.** Measured: our near-black objects land
   where the source shows yellow lattice — i.e. we fill knockout gaps with thread. Fix or
   at minimum quantify this; it pollutes the direction metric and it is a real defect.

---

## 6. Deliverables

- Engine changes in `apps/backend/app/services/digitizer.py` (plus new modules — a
  `services/direction_field.py` and `services/stitch_graph.py` would be reasonable).
- Tests pinning each graph component, including the axial-averaging trap (assert that a
  field of 179° and 1° averages near 0°, not 90°).
- `docs/benchmarks/v2-part39-audit.md`: before/after table for every metric in §4, the
  visual comparison at 14 px/mm against the source, and an honest list of what did not
  work.
- `STATUS.md` changelog row. Commit and push to the branch; do not open a PR unless asked.

## 7. Orientation — where things are

| Thing | Where |
|---|---|
| Fill angle (per region, moments) | `_fill_angle`, `_edge_avoiding_angle` |
| Straight fill | `_scanline_angled`, `_fill_by_component` |
| Curved fills already present | `_contour_fill`, `_spiral_fill`, `_radial_fill` (shape-triggered, not field-driven) |
| Satin | `_skeleton_satin`, `_satin_columns`, `_column_ends`, `_pace_by_boundary` |
| Medial axis | `_axis_branches`, `_axis_frame` |
| Region emission loop | `digitize_image`, the `for ci, contour in enumerate(contours)` block |
| Direction instrument | `scripts/measure_stitch_direction.py` (`--self-test` first, always) |
| Quality instrument | `scripts/measure_stitch_quality.py` |
| 100-design corpus | `scripts/build_corpus100.py`, `scripts/run_corpus100.py` |
| Prior findings | `docs/benchmarks/v2-part36-audit.md`, `v2-part37-audit.md` |

**Start by running `scripts/measure_stitch_direction.py <panel> --hoop 360x350
--check-registration --self-test` and reproducing 49.9°. If you cannot reproduce the
baseline, fix that before writing any engine code.**

**Read `docs/benchmarks/v2-part40-review.md` first — a side-by-side against the original
ranks the defects by visibility, and the top TWO are not direction: (1) we lay 2,925
stitches (5.1% of sewing) of near-black thread plus 230 running objects onto bare fabric
the original leaves empty; (2) the bead-chain border is missing entirely. Both are
cheaper and more visible than the direction work below — do them first.**

**Then read `docs/benchmarks/v2-part39-audit.md` §5 — it names the two things to fix
before pursuing G1: enclosed-gap capture when satin is refused, and a bare-fabric gate,
without which the metrics actively reward stitching over gaps the source leaves open.**
