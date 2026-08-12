# Generalised quality defects — where the engine falls short of commercial output

**Produced 2026-08-10 by a 41-agent investigation across eight quality dimensions.** Every defect
below was found by reading the shipped code, then independently re-checked by a second agent asked
to *refute* it. Only findings that survived appear here: **31 confirmed, and all 31 verified as
GENERALISED** — affecting a class of artwork, never a single fixture.

The owner's requirement drove the method, verbatim: *"Whatever changes you will made it should be
generalised changes not representing just for that particular image, it should be for all."* So each
finding carries the mechanism in the code, the class of artwork it damages, and the evidence.

Licence constraint observed throughout: Ink/Stitch and other GPL software were not read or consulted
as source. Reasoning is from public documentation and embroidery craft only.

**Read this alongside `docs/REVIEW-HANDOFF-2026-08-10.md`**, which covers project state, the blocked
parity decision, and the process failures of this engagement.

---

# EmDesign Automater — Ranked Defect Plan

Source: 31 confirmed defects (`verdict.real === true`) across 8 dimensions. Every one returned `verdict.generalised === true`. Nothing below is speculative — each row was reproduced against the shipped code.

---

## 1. All confirmed defects

| ID | Dimension | Defect | Artwork class affected | Severity | Generalised |
|---|---|---|---|---|---|
| CP1 | colour-palette | Colour plan non-deterministic — unseeded `cv2.kmeans` draws from OpenCV's thread-local RNG, which persists across requests on reused FastAPI worker threads | Palette/stop-count drift on multi-optimum art (photos, gradients, shaded mascots, many-colour flat); stitch-count drift on **all** art incl. flat | blocking | yes |
| CP2 | colour-palette | No thread-catalogue snapping in the digitize path; raw k-means centroids emitted as `thread_brand="Auto"`, `catalog_number=""` | All designs, unconditional | major | yes |
| CP3 | colour-palette | Area-weighted k-means lets shading absorb the colour budget; no slot reserved per perceptually-distinct hue; all planner distances are BGR Euclidean | Shaded/gradient region + flat accents. Worst on smooth-shaded flat art (fails the `is_textured` gate, so gets neither mean-shift nor bimodal split) | major | yes |
| CP4 | colour-palette | `PLAN_MAX_COLORS=8` caps every request at its only consumption point; the "requests above 8 are inert" justification is circular (swept through the already-capped entry point) | All. Lifting to 12 changes 43/60 corpus designs; all 3 tier-A photos gain 3–4 threads | major | yes |
| SH1 | shading-gradients | No graduated density, no stitch-length modulation, no feathered row ends; pitch constant within every region; `GRADIENT_BLEND` is a removed enum mapped to plain `TATAMI` | Every design (limitation lives in all five generator signatures) | blocking | yes |
| SH2 | shading-gradients | Ambiguous-blend cut strands 15–17% of foreground at label −1; the Part 29 seam-fill repair is gated on `is_textured` so never runs on the path that creates the damage | Flat-art path: soft ramps **and** flat art holding a colour midway between two centres. 33 of 109 corpus images >2% unowned | blocking | yes |
| SH3 | shading-gradients | No interdigitation between adjacent colours — labels are a one-owner-per-pixel partition; total cross-colour overlap ≤0.6–0.8 mm, uniform | Every multi-colour design; visible on shaded/gradient art | major | yes |
| SF1 | shape-fidelity | Contour smoothing inert above 0.10 mm/px — DP tolerance falls sub-pixel and Chaikin's output is rounded back onto the integer grid (identity + duplicate vertices) | Any design >~120 mm long side (2 of 4 shipped hoop presets), or any source <450 px at any hoop | blocking | yes |
| SF2 | shape-fidelity | Geometric resolution pinned to a fixed 1200 px raster; mm/px is a function of hoop alone, source detail cancels out | All artwork; error ∝ physical size (0.075 mm/px at 100 mm → 0.30 at 400 mm) | major | yes |
| SF3 | shape-fidelity | No curve representation anywhere — `contour` is an integer-pixel polyline; SVG is rasterised at 1200 px and re-traced with `findContours` | All vector uploads, all lettering (PIL glyph bitmaps at 160 px), all raster | major | yes |
| SF4 | shape-fidelity | Fill satin border paces on the centre line with no corner treatment; floor gate `continue`s the whole station when either rim is tight | Every fill ≥30 mm² and every kept hole; curved and cornered outlines | major | yes |
| SZ1 | size-scaling | Fill and satin pitch quantized to integer working pixels — sewn density set by hoop size and upload resolution, not the fabric profile | Every tatami fill and satin column in every design | blocking | yes |
| SZ2 | size-scaling | Sub-thread min-feature gate switches itself off above a computable hoop (166.7 mm at 1200 px canvas — **200×200 is a shipped preset**), because the DT width estimate is floored at 2×mm_per_px | All raster artwork with anti-aliased edges; fails in *both* directions across the crossover | blocking | yes |
| SZ3 | size-scaling | Contour fill sews at `row_px − 1` px — a fixed 1 px correction on a pitch only a few pixels wide; up to 2.0× over-dense | Rings, annuli, badge borders, square frames, letter bowls/counters | major | yes |
| SZ4 | size-scaling | Pull compensation rounded to whole pixels and returns the region untouched at `px ≤ 0` | Every tatami/contour/spiral/radial fill (not satin columns) | major | yes |
| UP1 | underlay-pull | Satin receives exactly **half** the per-side pull compensation a fill receives from the same stored number (`pull_mm/2` vs `pull_mm`) | Every satin object and every fill object in every design | blocking | yes |
| UP2 | underlay-pull | Pull comp never reaches the visible edge of a bordered fill — the satin border is built from the **undilated** contour and its outer lip sits at a fixed +0.6 mm | Every fill ≥30 mm²; the entire supported pull range (≤0.5 mm) is hidden inside the border | not stated (treat as major) | yes |
| UP3 | underlay-pull | Pull comp and both underlay insets use a **square** structuring element — L∞ dilation delivers `px` on axes, `px·√2` on diagonals | Every object with non-axis-aligned boundaries: curves, diagonals, rotated glyphs, circular badges | major | yes |
| UP4 | underlay-pull | Pull comp quantized to whole pixels, so its real value is a function of hoop and source resolution; can round to zero silently while the object still reports the nominal value | Every fill object. −25%…+30% across the four shipped hoops; zero for any sub-400 px upload at 200×200 | major | yes |
| DIR1 | stitch-direction | Every automatic tatami fill is one scalar angle per object; on a constant-curvature arc the error is exactly sweep/4 and no scalar can beat it | Curved regions too wide for satin and without a hole: leaves, petals, paisley bodies, wide banners, large C/S/G/J bowls. 40/40 corpus fill objects took the scalar path | blocking | yes |
| DIR2 | stitch-direction | Direction field solved on every digitize and consumed by nothing; only reader is a test/script diagnostic | Every digitize (~1% CPU, 14.4 MB pinned per run); absent capability affects all curved artwork | major | yes |
| DIR3 | stitch-direction | Boundary-seeded diffusion reaches ~12 work-px of usable coherence; field is bitwise zero over the interior of any wide region | Wide-area fills — backgrounds, garment bodies, large colour blocks. ~10/93 corpus images severely affected | blocking | yes |
| DIR4 | stitch-direction | `theta`/`sample()` return exactly 0 rad where the field is undefined — indistinguishable from a genuine horizontal answer; no sentinel, no NaN | Latent (no consumer yet). Worst on the largest regions: 35% of a big-flat-area fixture's foreground | major | yes |
| DET1 | small-detail-loss | Sub-thread gate deletes whole regions on a DT-median estimate that reads ~half the true stroke width; the same package already avoids this estimator for the satin cap | Hairline linework, keylines, thin borders, script and small lettering, ring/annulus outlines, lattice. Effective floor is 0.30–0.55 mm, non-monotone in hoop | blocking | yes |
| DET2 | small-detail-loss | `emitted_mask` is written in pass A, filled with no hole subtraction, before pass B discards anything — so the loss warning and the photographic rescue both read an inflated mask | Artwork with knockouts (rings, frames, badges, counters) and artwork with sub-thread strokes. 95/100 corpus designs over-credited, 42/100 by ≥2× | blocking | yes |
| DET3 | small-detail-loss | Artwork deleted as "the garment" on the basis of the **image border colour**, which is never an input; erased pixels are subtracted from both loss bases so it cannot be reported | White/light-ink artwork, knockout/reverse logos, and every transparent PNG (alpha is composited onto white, forcing a white substrate). Fires on 51–53/100 corpus designs | blocking | yes |
| DET4 | small-detail-loss | `MIN_REGION_MM2 = 2.0` hard physical cliff (a 1.6 mm dot); `dropped_speck_count` never read, `_DROP_LOG` has no consumer, and the loss counter structurally skips anything below the same threshold | Stipple/halftone, scattered ornament, punctuation and i-dots, freckles, catchlights, small counters, registration ticks | major | yes |
| CB1 | competitor-baseline | Element-level content-loss detector runs connected components over the **union of all colours**, so any element touching a sewn neighbour of any colour scores as covered; second condition skips sub-`min_area_px` components | Every design whose foreground is one connected blob — badges, logos on a filled ground, all photographs. 15/30 corpus designs had one component ≥90% of the mask | major | yes |
| CB2 | competitor-baseline | `max_colors` bounds nothing downstream (three stages add stops above k); raising the request re-quantizes and can silently delete artwork — reachable inside the UI's own 2–8 range | All classes. 38/100 exceed the stop bound at the default request of 6; objects drop on 22/100 going 6→10 | major | yes |
| CB3 | competitor-baseline | Non-adjacent colour stops mounting the same thread never merged and never made adjacent; no dependency-aware sequencing pass exists | Multi-region artwork; worst on photographic/textured. 22 duplicate stops across 6 of 13 A-tier designs | major | yes |
| CB4 | competitor-baseline | Fragmentation → trim time: one object per connected component, `_route_travel` is intra-object only, `connect_method` hard-coded `TRIM`, no same-colour merge stage | Photographic/scanned/textured raster **only** — explicitly not flat vector art. 35–56% of run time is machine stops on real photos | major | yes (within class) |

Note: **SZ4 and UP4 are the same code line** (`geometry.py:110`), found independently from two dimensions. Fix once.

---

## 2. Top 5 by (impact on perceived quality) × (breadth)

Each item is anchored on one defect and names the siblings that **must move in the same change** or the fix regresses something else.

---

### #1 — DET3: artwork is deleted as "the garment" based on the image's border colour
*Siblings: DET2 (the deletion is subtracted from both loss bases so nothing can report it), CB1.*

**Mechanism.** `substrate = _border_color(img)` — the median of the image's four edges. Any k-means cluster within `SUBSTRATE_DELTA = 12` BGR of it is erased: unconditionally if any component touches background, otherwise at ≥5% of foreground or ≥40 mm² (a 6.3×6.3 mm element). Erased pixels go into `substrate_owned`, which is ANDed out of both `owned` (the loss metric) and `art_base` (the photographic rescue), so the deletion is invisible to every warning channel by construction. `digitize_image` and `/api/digitize` have **no garment-colour parameter at all**. And `_decode_image_bgr` composites alpha as `img*α + 255*(1−α)`, so every transparent PNG — the docstring's own "single most common real digitizing input" — forces a pure white substrate that the customer cannot avoid or override.

**Why it looks worse than commercial output.** Controlled A/B, identical geometry, page colour the only variable: a white knockout square on a white page is kept at 39.7 mm² and **deleted at 81 mm² and above**; the same images on a grey page keep it at every size up to 506 mm². A 15×15 mm white knockout comes back with the white element gone, one colour stop instead of two, and the only warnings are a resolution notice and *"the artwork only separated into 1 distinguishable colour"* — which is false, and blames the artwork. Corpus-wide: fires on 51–53 of 100 designs, 135,000–193,000 mm² removed, 14 designs lose ≥20% of their foreground with no warning at all. Commercial software asks for the garment colour explicitly and shows you the knockout; here the artboard background silently decides what gets sewn.

**Generalised fix.**
1. Make the assumption an **input**: add an optional `substrate_hex` to `digitize_image` and the `/digitize` form, defaulting to the inferred border colour. Surface it in the UI next to fabric.
2. Make it a **statement**: whenever the rule removes area, emit a warning carrying the mm² and the assumed colour. The data is already in `substrate_px`; it is written to `plan` and never read.
3. Stop hiding it from the metrics: report substrate-removed pixels as a **separate channel** rather than subtracting them from both loss bases, so "left bare on purpose" and "lost" are two numbers.
4. For alpha input, infer the substrate from the alpha-declared foreground only — or treat a fully transparent border as *unknown substrate* and disable the rule entirely, as the SVG path already does (`svg_mask is None` gate).

---

### #2 — SH2: the ambiguous-blend cut leaves unowned bare-fabric moats
*Siblings: DET2 (the rescue that could catch this reads the inflated `emitted_mask`), SH3 (no interdigitation, so the seam is a hard line even where it is filled).*

**Mechanism.** `planning.py:413` runs the cut only `if ... not is_textured` — i.e. on flat art. Pixels whose two nearest centres are within `AMBIGUOUS_BLEND_RATIO` get `fg_labels = −1`, owned by no layer, and `pipeline.py:381` builds every region as `labels == cluster_idx`, so −1 enters no mask. The Part 29 seam fill that would re-own them sits inside `if is_textured:` — unreachable on exactly the path that creates the damage. `geometry.py:49` states it outright: "pixels owned by nobody are never re-covered at all." The per-cluster escape hatch `AMBIGUOUS_MAX_CUT_SHARE = 0.35` is useless because each band individually loses 0.5–33% while the union is 15–17%.

**Why it looks worse than commercial output.** Measured bare fabric with a 0.45 mm thread raster against a foreground eroded 0.8 mm (so edge shaving is excluded): fixture 03 gradient 5.9% bare, largest blob 54 mm²; a blue→red ramp 7.9% bare with **full-height stripes 4.35 × 66.75 mm**; the hard-edge control with the same two colours 0.00%. Worst case is not even a gradient — `C24_many_colours`, plain flat rectangles, is 16.5% bare with a single **212.8 mm²** blob, because whole rectangles whose colour fell midway between two centres are deleted wholesale. At a 200 mm hoop the largest blob is 443 mm². Disabling the cut collapses all of it to ~0.3%. No commercial digitizer ships holes in the middle of a filled region.

**Generalised fix.** Make blend-pixel ownership a property of the transition's **width**, not the ratio. Distance-transform the −1 mask and discard only pixels whose local band thickness is at most one anti-alias width (~`up_f` px, i.e. sub-thread in mm); assign everything thicker to its nearest centre. Equivalently: run the existing seam fill **unconditionally** instead of under `is_textured`, keeping the discard for sub-thread bands only. Both forms are scale-relative. **CORRECTION (2026-08-10): the claim that this leaves hard-edged flat art bit-identical was never measured, and is FALSE for the thickness rule. Measured: `01_flat_2color_logo` — hard-edged, 3 distinct source colours — moves 6,165 -> 6,221 stitches. It IS bit-identical under the stricter variant that also requires two owned neighbours, which loses C24. See `SH2-FINDINGS-2026-08-10.md`.**

**Do not ship without also:** re-deriving `TEXTURE_RETRY_UNCOVERED = 0.19`. It was calibrated against the inflated `emitted_mask` (the angelfish's 22.8% was itself understated — 37 of its 67 regions were skipped and all credited as covered). Measured honestly, 14 flat designs cross the gate, so fixing DET2 without re-deriving the constant will mis-fire the photographic rescue on flat linework.

---

### #3 — CP1: the colour plan is non-deterministic
*No siblings — but this must be fixed **first**, because it invalidates the A/B measurement of every other item on this list.*

**Mechanism.** `planning.py:353` calls `cv2.kmeans(Z_pal, k, ..., attempts=3, cv2.KMEANS_PP_CENTERS)` with no seed, so k-means++ draws from OpenCV's thread-local `theRNG()`. The only `cv2.setRNGSeed` in the entire app sits inside `_split_bimodal_clusters`, gated on `is_textured`, so it never runs before the main palette k-means and on flat artwork never runs at all. `routers/digitize.py:24` is a plain `def`, so FastAPI dispatches to the anyio threadpool, whose workers are reused — the RNG state carries from one customer's request to the next.

**Why it looks worse than commercial output.** Four byte-identical POSTs of the same file, one event loop, all served by the **same worker thread**: 5 / 7 / 6 / 7 colour stops and 8288 / 8864 / 8825 / 8705 stitches. In-process 5× repeats give five distinct palettes with a worst thread drift of ΔE00 15.2 (pale olive vs pale lavender) and a 10% stitch spread. A 3-repeat sweep over 16 fixtures moved the stitch count on 12 of them. Commercial digitizers are deterministic; a customer who re-runs the same upload and gets a different thread list has no product.

**Generalised fix.** Seed OpenCV's RNG **immediately before every `cv2.kmeans` call site**, from a hash of the input (image bytes + hoop + max_colors) — not once at process start (only the first call would be pinned) and not from wall clock. Raise `attempts` and keep the best-inertia run. Verified: monkeypatching `cv2.kmeans` to seed first collapses all 13 fixtures tested to exactly one palette, one stitch count, one object count.

**Test note.** The existing guard `test_swarm_qa_corpus_digitize.py:215` (docstring: "the pipeline has no RNG") passes only because `TestClient` used outside a context manager spins a fresh portal, loop and worker thread per request. Put the client in a `with` block and it fails. Also seed `scripts/run_corpus100.py`, which digitizes the whole corpus in one process — every graded result there currently depends on the image's position in the run.

---

### #4 — SZ1: nothing in the engine delivers the millimetre value it claims
*Siblings — same contract, must move together: SZ3 (contour fill `row_px − 1`), SZ4/UP4 (pull comp rounding), UP1 (satin gets pull/2, fills get pull), UP2 (border built from the undilated contour), UP3 (square structuring element).*

**Mechanism.** Every physical quantity is paced on the integer working-pixel grid or applied under a convention that disagrees with its neighbour:
- `row_px = max(1, round(row_mm / mm_per_px))` and `for y in range(0, h, row_px)` — the sewn pitch is `row_px × mm_per_px`, only accidentally equal to the fabric's `row_mm`.
- `_contour_fill` subtracts a whole pixel: `step = max(1.0, row_px − 1.0)`, a fixed correction on a pitch of 2–5 px.
- `_dilate_pull` does `px = round(pull_mm / mm_per_px)` then `if px <= 0: return region` — with a **square** kernel, so it delivers `px` on axes and `px·√2` on diagonals.
- Satin adds `pull_mm/2` per side as a continuous float; fills add `pull_mm` per side as an integer dilation. Two generators, one number, a 2:1 disagreement.
- The fill's finishing satin border is swept on the **undilated** contour at a fixed ±0.6 mm, and every supported `pull_mm` is ≤0.5, so the whole compensable range is hidden inside it.

**Why it looks worse than commercial output.** Measured, cotton, 0.40 mm nominal: actual pitch 0.390 / 0.420 / 0.375 / 0.450 / 0.405 / 0.450 / 0.360 / 0.450 / **0.270** mm across hoops 40→360 — non-monotone, 67.5%–112.5% of target. The decisive control: the same 54.9 mm design in a 100 mm hoop, only the upload's pixel size varying — a 300 px source sews at 0.300 mm and 5458 stitches, a 350 px source at 0.514 mm and 3229 stitches. **Identical physical embroidery, 1.67× the density and 69% more machine time**, decided by a number the customer does not associate with density at all. The fabric selection can vanish entirely: at hoop 150, cotton (0.40) and knit (0.50) both sew 0.450 mm. Contour fill runs a ring at 0.225 mm against a 0.400 mm target at a 300 mm hoop — 2.0× over-dense, which is board-stiff and puckers. Pull compensation is zero for any sub-400 px upload at 200×200 while the object still reports `pull_compensation: 0.2`. And the stored `density` field is always the nominal value, so worksheets and exports report a number the stitches do not have.

**Generalised fix — one contract, applied everywhere.**
1. **Float pacing.** Carry pitch as `row_pitch_px = row_mm / mm_per_px` and walk `_scanline_fill` with a float accumulator instead of `range(0, h, row_px)`. Same for satin pitch, contour step, both underlay pitches. (Alternative that fixes pitch only: snap the grid to the density — `mm_per_px' = row_mm / round(row_mm / mm_per_px)`.)
2. **Contour fill:** cap the iso-contour correction at a fraction of pitch — `step = max(1.0, row_px − 1.0, 0.8 × row_px)` is bit-exact with today at `row_px ≥ 5` (so the existing coverage test stays green) and holds coarse grids at 1.25× instead of 2.0×.
3. **Isotropic sub-pixel offsets.** Replace `_dilate_pull`'s integer square dilation and both underlay erosions (`underlay.py:63`, `:211`) with a distance-transform threshold: `dist = distanceTransform(1 − region, DIST_L2, 5); region_out = dist <= pull_mm / mm_per_px`. Euclidean, sub-pixel, no rounding, no orientation bias — fixes SZ4, UP3 and UP4 in one change.
4. **One definition of `pull_compensation`** (per side, in mm, at the boundary) honoured by both generators. The code, `constants.py:278`, the user guide and the fabric test protocol all already say "per side"; fills honour it, satin delivers half. Change `generation.py:91` to `pull_mm / mm_per_px`. Also fix the un-compensated clamp at `columns.py:358` where a column at the width cap gets **zero** pull comp.
5. **Border carries the compensation.** Build the fill's satin border from the contour of `top_region`, not `contour` (and invert the sign for holes), so the outermost thread is the compensated one. `routing.py:49` already budgets `FILL_BORDER_MM/2 + pull_mm` — that expression is the invariant the border generator violates.
6. **Assert the contract.** For every emitted object: `|realised_pitch − prof["row_mm"]| / row_mm < 0.02`, and realised per-side offset within one pixel of `pull_mm` at 0/15/30/45°. Warn otherwise. This class of defect is invisible today because nothing measures the pitch actually used.

**Tests that will need rewriting, not reverting:** `test_part59_trim_profiles.py:52` (byte-identity, one 2-colour fixture), `test_contour_fill.py` row-pitch margin test (only exercises `row_px` 5–6, where −1 px is a benign 20%), `test_rebuild_satin_residuals.py:213` (asserts the literal string `"(pull_mm / 2.0) / mm_per_px"` — it guards *that pull is added at all*, not the factor), `test_pullcomp.py` (its fixture is an axis-aligned square at a `px = 0` grid, so it cannot see the bug or the fix). Note the whole bench corpus is cotton, where `row_mm == satin_mm == 0.40` — `test_rebuild_generator_arguments.py:144` says so in as many words. It was never positioned to catch any of this.

---

### #5 — DET1 + SZ2: the minimum-feature gate is a pixel counter wearing a millimetre label
*These two are the same estimator read from opposite ends of the crossover and must be fixed together.*

**Mechanism.** `region_med_w = median(nonzero distanceTransform) × 2 × mm_per_px`, compared against `MIN_FEATURE_W_MM = 0.25`; below it the **entire connected region** is dropped with `continue` — no object, no stitch, no colour stop. Two compounding errors: (a) for a stroke *W* px wide the DT runs 1..W/2..1, so `2×median` reads ≈ *W*/2 — the estimator systematically under-reads by half, and the same package already knows this (`generation.py:98`: "the DT median under-reads a rectangle badly, measured 3.6 mm for an 8 mm bar", which is why the satin cap uses the skeleton median instead); (b) the DT's smallest non-zero value is 1.0 and it returns exactly 1.0 for every region 1–4 px wide, so the estimate is floored at `2 × mm_per_px` and **the gate becomes unsatisfiable once `mm_per_px ≥ 0.125`** — 166.7 mm on a 1200 px canvas, or as low as 111 mm for a 400–599 px source.

**Why it looks worse than commercial output.** Below the crossover it deletes real work: measured, a straight bar is skipped at 0.300 mm and sewn at 0.375 mm; an annulus needs 0.525 mm. At 130×180, fixture 04 has 9 of 10 regions at DT median 1.0 and all 9 are skipped — one object emitted. `C28_lattice_trellis` returns **HTTP 422 "nothing could be sewn"** at 130×180 and **276 objects** at 200×200. Above the crossover it does the opposite: every 1 px anti-alias sliver is sewn as a real object with its own thread. `A_fixture_05`, a **one-colour** caps wordmark, comes back with six colour stops — five of them anti-alias ramp greys. Across the crossover 10 of 10 bench fixtures flip their skip count to zero and 6 of 10 change objects and colour stops discontinuously. **200×200 is one of the four hoops the UI ships**, so picking the standard 200 mm hoop silently disables the filter for every user and every image. Neither behaviour resembles a commercial result: fine linework should be sewn as a run, not deleted, and anti-alias fringe should never open a thread change.

**Generalised fix.**
1. **Replace the estimator.** Measure width sub-pixel — the skeleton/medial-axis median `spine_satin` already computes, or `DIST_MASK_PRECISE` plus an area/skeleton-length estimate. A pure pixel threshold is *not* enough: the DT median is blind between 1 px and 4 px, so the estimator needs replacing, not just rescaling.
2. **Re-derive the constant at the same time.** `MIN_FEATURE_W_MM`'s calibration note ("phantom halos 0.15 mm; real hairlines 0.30–0.33 mm") is circular — 0.15, 0.21, 0.30 and 0.33 are exactly the old estimator's first four output levels (2×1.0, 2×1.4, 2×2.0, 2×2.1969 × 0.075) at hoop 100. Swapping the estimator without re-deriving 0.25 will re-admit the blend halos Part 17 exists to kill.
3. **Downgrade, don't delete.** A region genuinely under one thread should be sewn as a single running stitch along its medial axis — `_axis_branches` + `_resample_open` already exist and are used by the dark-linework pass.
4. **Fail loudly.** When `2 × mm_per_px ≥ MIN_FEATURE_W_MM` the grid cannot answer the question: raise the working resolution for that run, or record a warning that sub-thread filtering was not possible. Never pass everything through in silence.
5. **Regression test:** sweep one fixture across hoops and assert object and colour-stop counts do not step discontinuously.

---

**Immediately below the cut, and why:** SF1 (staircase curves) is blocking and very visible, but bites only at design sizes >~120 mm — 2 of 4 shipped hoop presets, not all of them. DIR1 (scalar fill angle) is the classic auto-digitizer tell and hits 40/40 corpus fill objects, but thin curved strokes route to medial-axis satin, which does follow the axis, so the visible class is narrower than "all curved artwork". Both belong in the next tranche.

---

## 3. What a customer would SEE

**Gaps and bare fabric** (SH2, UP1, UP2, SF4, SH3, SZ4/UP4)
Unstitched fabric showing through the middle of a filled region — full-height stripes 4.35 × 66.75 mm on a gradient, a single 212.8 mm² hole in flat rectangular artwork, 443 mm² at a 200 mm hoop. Satin columns finishing narrow, because they get half the pull compensation a fill gets (0.1 mm/side missing on cotton, 0.25 mm on fleece) — and zero at the width cap. Bordered fills finishing at the wrong outer dimension, because the visible outline is drawn on the uncompensated contour. A fan of wedge-shaped gaps at every convex corner of every fill border: on a star tip the outer rim jumps 1.9 mm against a 0.4 mm nominal pitch, and on a small-radius feature the floor gate deletes half the stations so the whole feature runs at ~3× pitch. And every colour boundary is a hard line — the two colours share at most 0.6–0.8 mm of thread where commercial needle-blending interlocks over several millimetres.

**Lost detail** (DET3, DET1, SZ2, DET4, CB2, DET2, CB1)
Whole white or light-ink elements missing, with no warning — a white knockout over 81 mm² is deleted outright, and every transparent PNG is at risk because alpha is composited onto white. Hairlines, keylines, thin borders and script lettering deleted below the gate crossover and phantom anti-alias slivers *added* above it — one lattice fixture returns "nothing could be sewn" at one hoop and 276 objects at another. Punctuation, i-dots, stipple and any dot under 1.6 mm gone at the 2.0 mm² area cliff. Asking for **more** colours removes artwork: the badge fixture's "HARBOR CLUB" wordmark — ten satin objects of 25–43 stitches — vanishes going from 7 to 8 requested colours, absorbed into the cream fill that sews over it. And none of it is reported: the loss detector runs connected components over the union of all colours, so 95 of 100 corpus designs over-credit their own coverage, 42 by ≥2×; one fixture emits zero objects and still reports 11% lost.

**Banding** (SH1, SH3, CP3)
Gradients arrive as up to 8 flat posterised bands with a hard line between each. There is no graduated density, no stitch-length modulation and no feathered row ends anywhere in the product — pitch is a constant within every region, and the blend stitch type is a removed enum mapped to plain tatami. Separately, the bands themselves eat the colour budget: a large shaded field pulls extra centres into itself and pushes distinct accent colours off the palette entirely (accent survival falls 100% → 39.6% as the shading depth goes ΔL* 0 → 40, at fixed k and fixed accent area).

**Faceted curves** (SF1, SF2, SF3, DIR1)
Above ~120 mm design size a circle is stored as a raw pixel staircase — 670 points with 90° corners at a 200×200 hoop, 2216 points with 404 duplicate vertices at 400 mm — because the smoother's tolerance falls below one pixel and Chaikin's output is rounded back onto the same grid. An exact SVG circle comes out no better than a JPEG of one. And on curved filled shapes (leaves, petals, banners, large letter bowls) the rows run dead straight across the curve at up to 90° to the flow — median 34° within-region flow spread against a single scalar angle on all 40 corpus fill objects measured.

**Wrong colours** (CP2, CP1, CP3, CP4)
Thread colours nobody can buy: the digitizer emits raw k-means centroids as `thread_brand="Auto"`, `catalog_number=""`, so the **file format** makes the final thread choice — `#123456` becomes `#134a46` "Peacock Blue" in PEC, `#071650` "Navy Blue" in JEF, and random filler in EXP and DST. Same design, different colours per export. Distinct accent hues dropped in favour of shading bands (14 sewable modes lost across 13 corpus images that had *fewer* colours than the budget). A hard cap of 8 while the artwork separates into 12, accompanied by a warning that blames the artwork for the engine's cap. And a different palette every run.

**Puckering and density** (SZ1, SZ3, SZ4)
0.270–0.514 mm actual row pitch against a 0.400 mm target, decided by hoop size and upload resolution rather than the fabric you chose — too dense puckers, too sparse shows fabric through. Rings, frames and letter bowls up to 2.0× over-dense and board-stiff. Selecting the fabric can change nothing at all: cotton and knit both sew 0.450 mm at a 150 mm hoop. Two uploads of the same logo at 300 px and 350 px produce identical physical embroidery at 1.67× the density and 69% more machine time.

**Production cost** (CB4, CB3)
On photographic input 35–56% of run time is the machine stopped: 93–155 trims per design, median 17–25 stitches per object, and no inter-object travel or branching to hide the moves. The operator's worksheet lists 18 numbered threads for 10 actual spools, because same-thread stops that could be made adjacent never are.

**Inconsistency** (CP1)
Upload the same file twice and get a different design: measured through the real HTTP endpoint, four identical POSTs returned 5 / 7 / 6 / 7 colour stops and 8288 / 8864 / 8825 / 8705 stitches.

---

## 4. Marked `generalised = false` — "do not fix these image-specifically"

**Nothing is.** All 31 confirmed defects returned `verdict.generalised === true`. There is no defect in this set that should be fixed per-image.

Two things belong in this section anyway, because they are the places where a per-image fix is the tempting wrong answer:

**CB4 (fragmentation → trim time) is class-gated, not universal.** Its author-assigned `generality` is `class-specific`; the verdict confirms it generalises *within* real photographic/textured raster input (reproduced on 3 photographs plus 5 B-tier derivatives) and explicitly **does not** affect flat vector-like art (C05, C07, C08, C12 each digitize to 1–3 objects with 0 trims). The fix must therefore be gated **geometrically** — merge same-colour components whose connecting corridor lies inside the union of that colour's regions plus everything sewn later — so it degrades to today's behaviour where no corridor exists and cannot regress flat designs. Do not gate it on a fixture list or an "is this a photo" heuristic.

**Sub-claims falsified during verification. Do not build fixes around these:**
- **CP3** — 84 of the 98 missed corpus colour modes come from 9 images that simply hold 16–24 modes against k=8. That is plain budget shortfall, not shading theft. The clean signal is 14 modes across 13 images. Do not tune against the 9.
- **CP3** — `_split_bimodal_clusters` is a *partial rescue* (raises accent survival 39.6% → 83.3%), not an aggravator. Its centres are appended, not taken from k. Do not remove it.
- **CP4** — the four `tiny_lettering` fixtures return zero stitches at both caps; they do not evidence the colour cap. And the 78% → 89.1% coverage table is a raw-`cv2.kmeans` proxy that bypasses centre merging, the blend cut and the speck filter — at pipeline level only 8 of 60 designs gain colours at k=12 and **4 lose** one. A cap lift is a tradeoff, not a free win.
- **DET1** — the report's "same physical width, source resolution varied" sweep does not reproduce; work resolution is clamped to 1200 px, so the free variable is the **hoop**. Do not chase upload pixel counts here (they *are* the free variable for SZ1/SZ2/UP4 — different defects).
- **UP3** — the "45° diamond grew +0.247 mm in x but +0.156 mm in y" evidence is not caused by the square kernel (a square kernel is symmetric; measured, the diamond grows +14 px on both axes). That asymmetry has another cause, most likely fill-row pacing at an angle. Do not cite it, and do not treat it as fixed when UP3 is fixed.
- **DIR1** — "the sweep/4 result independently reproduces the 49.9° coin-flip baseline" is an arithmetic identity (mean absolute deviation of a uniform distribution is span/4), not corroboration. And `STATUS.md:131` records that the 49.9° figure is itself partly a structure-tensor instrument artefact.
- **CB3** — the per-design duplicate counts in the report are wrong (peacock is 15/10, not 15/9; A02 is 17/11, not 10/7), and only **1** of the peacock's 5 duplicates is removable by a permutation that respects the dependencies the pipeline models. The other four need the main colour sequence moved off darkest-first, which is a layering decision.
- **DIR2** — the direction field being unconsumed is deliberate, documented and test-enforced staging with a measured reason for stopping (`docs/benchmarks/v2-part51-audit.md`: "D2 was implemented, measured, and reverted"). Its CPU cost is ~1% of a run, not a performance problem. The real unconditional cost is the 14.4 MB full-frame snapshot pinned in a module global on a long-lived server. Fix the memory, treat the wiring as feature work, and note that wiring it before DIR3 and DIR4 are fixed will simply reproduce Part 51's null result.

---

## 5. What was NOT investigated

**There is no measured comparison against commercial output anywhere in this work or in the repo.** `apps/backend/scripts/bench_competitor.py` holds five in-repo fixtures with no competitor output, two foreign machine files with no source artwork, and one watermarked competitor render with no stitch file; its own report says every numeric cross-comparison is "not measurable from the files available". Every "worse than commercial" judgement above is reasoning from published feature descriptions and from craft first principles — not from a matched benchmark.

**Nothing was sewn.** All coverage, bare-fabric and interdigitation numbers are synthetic thread rasters (0.40–0.45 mm stroke over consecutive stitch pairs) with a stated floor of ~4% on the hard-edge control. Differentials and the coincidence of bare pixels with the −1 mask carry the findings; the absolute percentages do not. Puckering, pull-in and registration were reasoned about, never observed on fabric.

**Not audited at all:**
- **Lettering engine** (`services/lettering.py`) — only noted in passing that it rasterises PIL glyph bitmaps at 160 px (480 in arc mode) and feeds them to `digitize_image`, so font curves take the same raster round-trip at a coarser grid than an SVG upload. No kerning, spacing, baseline, arc, or small-type-legibility work.
- **Export / machine-file layer** — `embroidery_io` was probed only for colour substitution on five formats. The 47 read / 19 write formats, DST/PES/EXP stream correctness, jump/trim command encoding, and real machine compatibility were not examined.
- **Appliqué and foam paths** — `underlay.py:382-399` (edge-cover satin at 2 mm width with `floor_px = 0`, so worse corner amplification than SF4) was noticed and never measured. The three-phase appliqué sequence was not reviewed.
- **Rebuild / edit path** — sampled where it shares generators with digitize (`rebuild.py:187`, `:244`, `:435`), never audited as a feature. Undo/redo, persistence, `stitch_edit.transform_range`, and object-level editing semantics untouched.
- **Frontend** — only `DigitizeDialog` (hoop list, colour clamp), `PropertiesPanel` (density input) and `ThreadPalette` (manual match button) were read. No UI/UX review.
- **Routing quality beyond fragmentation** — start/end point selection, colour-block ordering, travel-stitch visibility under later layers, and the `_lock_stream` tie-off geometry were not independently verified (the repo's own detector reports 0 unlocked ends of 806 and 0 attached jumps >10 mm; I did not re-derive that).
- **CONTOUR underlay type** — the one `UnderlayType` member with no reachable generator. Not investigated.
- **Fabric profile *values*** — whether 0.40 mm on cotton or 0.2 mm pull is correct craft was not assessed. Only whether the code delivers the number it stores (it does not).
- **Performance, memory and concurrency** beyond the RNG finding and the 14.4 MB per-digitize pin. No leak audit, no load testing, no multi-tenant isolation review, no security or auth review.
- **Interaction effects.** Each defect was verified largely in isolation, with the other thirty left at their shipped (broken) values. The combined effect of fixing several at once — particularly the physical-units contract (#4), which touches every generator — has not been modelled. Expect the ten-fixture bench to move substantially, and re-pin it at a hoop above 133 mm, since at 100×100 and 130×180 it cannot see SF1, SZ2 or half of #4 at all.

**Corpus caveat.** Tier C of `tests/fixtures/corpus100` is synthetic by its own generator's header. Incidence rates quoted above ("51/100 designs", "24/100", "42/100 over-credited") are frequencies *within this corpus*, not real-world frequencies. The class-level exposure of each defect is established by the controlled synthetic probes and by the tier-A/tier-B real photographs, not by the tier-C counts.