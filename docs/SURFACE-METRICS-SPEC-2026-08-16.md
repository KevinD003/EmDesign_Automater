# Surface metrics — specification (build gated behind RS1, per the ruling of 2026-08-16)

**Spec only. Nothing here is built.** One read-only prototype was run to test the spec's own
feasibility claim, and its failure mode is reported in §1.3 because it decides the design.

The gap being instrumented, in the ruling's words: nothing this repository owns can tell a jagged
edge from a clean one, so raggedness can regress freely while CI stays green. Renders show
whiskers and spikes where a satin edge should be a knife line, and "HARBOR CLUB" is mush. Not one
of those has a number. These two metrics are that number, and they exist to gate the curve
primitive before it is written — the DET2 sequence applied to the surface.

---

## 1. Metric 1 — BOUNDARY DEVIATION

### 1.1 Definition

For each satin and fill object, for **each side of the column separately**: the signed distance
(mm) from every emitted **edge penetration** to the object's own stored smoothed contour.

Reported per object:

| number | meaning | expectation |
| --- | --- | --- |
| **offset** — p50 of signed distance, per side | where the edge sits relative to the contour | predicted by the object's own `pull_compensation`: satin edges land outside by the stored pull, deliberately. Offset is **calibration**, not raggedness |
| **roughness** — p95 − p5 of signed distance, per side | how much the edge wanders around wherever it sits | this is the whisker number. A knife edge with pull comp is offset but tight; spikes are dispersion |
| **max \|deviation\|** | the single worst penetration | catches the one spike p95 forgives |

Per design: median and worst object roughness, and the worst object named.

Separating offset from roughness is the load-bearing decision. A metric that reports raw distance
reads intended pull compensation as raggedness and either false-alarms on every satin or gets
loosened until it cannot fire — the DENSITY-LOCK lesson. The stored `pull_compensation` predicts
the offset, so the offset column doubles as a free check that pull comp is actually being applied
(UP1's subject); the roughness column is the surface-quality number.

### 1.2 Units and gates — derived, not fitted

Everything is reported in **mm and in thread widths** (40wt ≈ 0.4 mm). No pass threshold is set
in this spec: the instrument reports first, on the fourteen and on real artwork when it arrives,
and any later gate is expressed in thread widths ("a knife edge wanders less than half a thread")
— a physical argument, not a constant fitted to the fourteen. If after measurement no defensible
physical threshold exists, the metric stays a reported trend with a ratchet rule (no commit may
worsen design-median roughness), which needs no threshold at all.

### 1.3 Where it must be measured — decided by a failed prototype

The obvious implementation is post-hoc: take the final stream, capture penetrations within a
radius of each object's contour, measure. **This was prototyped read-only on fixtures 07, 01 and
05, and it is confounded three ways:**

1. **Capture truncation.** Every object's max |d| came back at exactly the 0.8 mm capture radius
   — the window truncates the distribution it is measuring. A spike 1.5 mm out is invisible.
2. **Interior pollution.** Fill interiors near the boundary enter the "edge" population: fixture
   01's plain tatami fills read roughness 1.3 mm, which is row geometry, not edge wander.
3. **Side ambiguity.** On a satin column narrower than twice the capture radius, both edges land
   in one band and the spread measures **column width**, not raggedness.

The prototype's numbers are therefore not surface measurements and are not reported as such. What
they establish is the design constraint: **edge identity cannot be recovered spatially from the
final stream; it exists only at generation time.** The column-end points in `columns.py`
(`_column_ends` / the `end[over]`/`end[~over]` arrays) *are* the satin edge penetrations, per
side, by construction. A fill's boundary points are its scanline–edge intersections, equally
explicit at generation. The instrument therefore hooks emission in pass B — exactly as the stream
census does — and records per-object edge sets before locking, with results in a module-level
diagnostic and surfaced through `trace.py` under its own key
(`surface.boundary.{offset_p50,roughness,max}` per object plus design aggregates).

Consequences, stated:

* **Digitize and rebuild paths both get it for free-ish** — both call the shared generation core
  (`spine_satin`), which is where the edge sets exist. The hook lands once, in generation.
* **Imported and competitor designs cannot have it** — no contours, no generation pass. That is
  acceptable: this instrument gates *our* pipeline; the comparison harness speaks penetration
  space (Decision 2) precisely because that is all a competitor file carries.
* Cost: O(edge points) per object at emission; no extra passes.

### 1.4 What the design already carries vs what must be recorded

Already stored: per-object `contour`, `holes`, `pull_compensation`. Not recoverable post-hoc:
which penetrations are edge points and which side each belongs to → recorded at emission.
Nothing else is needed; no new model fields — diagnostic state plus TRACE keys, like the census.

---

## 2. Metric 2 — LEGIBILITY AT A FIXED CAP HEIGHT

### 2.1 Procedure

1. Text regions are **declared per fixture** — a rectangle and a nominal cap height in the fixture
   parameter table (05, 06, and 07's two ring texts to start). Declared, not detected: detection
   would put an OCR-ish model inside a gate, and a wrong detection would gate the wrong pixels.
   This is data entry against known fixtures, not fitting.
2. Render the design (`render_design`) and rasterise the source at the same mm/px; crop the
   declared region from both; binarise (Otsu); scale both so the declared cap height maps to a
   fixed pixel height.
3. Compare at the stated cap height. **The statement travels with the number**: "legible at 4 mm"
   and "legible at 8 mm" are different claims, and 07's ring text sits near the small end.

### 2.2 The pass condition — a decision, argued

**Topological legibility: the rendered text region must have the same discrete structure as the
source's — the same number of glyph components and the same number of counters (interior holes),
component for component.**

The argument: every failure the renders actually show is a topology change. Merged glyphs (the
"mush" on HARBOR CLUB) reduce component count. Flooded counters (a filled 'o', 'A', 'R', 'B')
reduce hole count. Broken strokes raise component count. Each is discrete, each is measurable by
`connectedComponentsWithStats` on the binarised crops, and the reference is **the source's own
structure** — so there is no threshold to fit. Match or mismatch, per declared region, at the
stated cap height.

Proposed gate: at the fixture's declared cap height, topology must match; the industry floor for
satin lettering (~4 mm cap height) is the smallest height at which we make the claim at all.
4 mm is a craft norm cited in the lettering literature, not a number derived from our fixtures.

Known limitation, stated so the pair is understood as a pair: a ragged-but-connected render
passes topology while looking bad. That is Metric 1's half of the job — legibility gates
*structure*, boundary deviation gates *edges*. Neither substitutes for the other.

**Secondary diagnostic, reported and never gated:** SSIM between the normalised crops. It trends
with the mushiness topology cannot see, but any SSIM pass threshold would be a constant fitted to
fourteen synthetic images, which is the exact thing this spec is forbidden from doing.

### 2.3 Derivability check, per the ruling

Everything comes from artefacts that already exist (the design's render, the source image, the
fixture table) plus declared text regions, which are data entry. **Nothing in either metric is
fitted against the fourteen.** The one number imported from outside is the 4 mm cap-height floor,
which is a craft norm and is cited as such. If the CTO wants it corroborated, the settling
evidence would be a physical sew-out of 05 at descending cap heights — which is also the only
evidence that would settle it, since legibility on cloth is the actual claim.

---

## 3. Sequencing

As ruled: **RS1 first**, these instruments after, both before the curve primitive starts.
RS1's own result is judgeable on coverage (DET2's table) and does not need these. The curve
primitive is what these exist to judge, and building the instrument before the change it gates is
the whole pattern of this engagement.

One interaction to flag: RS1 adds `RUNNING_SINGLE` objects for hairline regions. Runs have no
sides and no column ends, so Metric 1 skips them (a run's deviation from its own centreline is
near-zero by construction — it *is* the centreline). Metric 2 is unaffected. Neither metric
constrains RS1, which is consistent with RS1 going first.
