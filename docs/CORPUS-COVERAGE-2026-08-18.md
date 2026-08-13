# The corpus-representation item — what no fixture reaches, and the smallest set that would

**Per the ruling of 2026-08-18. Enumerate and cover; nothing uncovered is fixed here.**

## 0. The finding this item generalises

The fourteen bench fixtures produce **zero `RUNNING_SINGLE` objects**. The angelfish record — the
only real competitor artwork this repository has ever digitized — is `RUNNING_SINGLE` **55 of 100
objects**. More than half the objects on real artwork take a path with no fixture coverage, and
the entry-convention defect fixed in `ce254a8` would have dropped 55 penetrations from that one
design on every rebuild with nothing in 1,371 tests to notice. Three zero-coverage paths were
found one at a time (dark linework, the phantom COLOR_CHANGE, `stops_partition_matches`); this
item replaces one-at-a-time discovery with an enumeration.

## 1. Method, and its blind spots

`coverage run --branch` over **exactly the population in question**: the fourteen at bench
conditions through `digitize_image`, then `rebuild_design(force=True)` on each result, scoped to
the digitizer package. Driver and raw report in the session records; headline:

| file | branch coverage from the fourteen |
| --- | ---: |
| pipeline.py | 90 % |
| rebuild.py | 71 % |
| underlay.py | 50 % |
| satin.py | 70 % |
| geometry.py | 70 % |

Blind spots, stated:

1. **Fixture reach, not test-suite reach.** Constructed-object tests cover paths no fixture does
   (the entry-convention regression file among them). That distinction is the point of the item.
2. **Bench conditions only** — cotton, bench hoops, bench colour counts. Branches keyed on other
   fabrics or API parameters read as uncovered without being corpus holes.
3. **Branch coverage sees untaken branches, not untested values.** A threshold whose both sides
   fire on easy inputs still hides its extremes.
4. **One driver artifact, called out so it is not misread:** the driver forces regeneration, so
   the provenance pass-through (`rebuild.py:158`, most of `provenance.py`) reads uncovered as a
   consequence of `force=True`, not of the corpus. The pass-through is exercised by the corpus via
   the two CI lanes.

## 2. The enumeration — every uncovered branch group, with the input class that reaches it

### pipeline.py (digitize path) — uncovered by all fourteen

| lines / branch | what it is | input class that reaches it (one line) |
| --- | --- | --- |
| 220–223 | SVG decode | an SVG upload |
| 258→261, 261, 268–272 | alpha-mask rescale at up/downscale | a transparent PNG with an alpha channel |
| 293→313, 313–314 | **declared mask constrains segmentation (DET3's fix)** | transparent PNG or SVG — every Illustrator/Figma/Canva logo export |
| 265→266, 266–272 | `_MAX_WORK_PX` downscale | any image larger than the work cap — a phone photo |
| 317→318 | segmentation-scale mismatch resize | photographic input through rembg |
| 320→322 | segmentation found nothing → treat all as ink | an image whose foreground is undetectable |
| 371→378, 1434–1441 | sketch retry loop + its warnings | artwork whose colour plan misses edges — detailed or photographic input |
| 1123→1188, 1141–1142, 1188→1194 | **dark-linework chains actually emitted** | a photograph or textured artwork with drawn outlines on light cloth |
| 1130→1134 | linework suppressed: darkest thread IS the cloth | the same subject on a **dark garment** |
| 1355→1362 | texture retry **accepted** | a photo where smoothing genuinely recovers coverage |
| 1396→1397 | fine-detail warning | high-resolution source at a small hoop |
| 1406→1407 | colour-cap warning | a request above `PLAN_MAX_COLORS` |
| 624→638, 708→709, 963→964, 932→935 | rare generation guards (no hierarchy, missing plan entry, <2 points, empty parallel underlay) | degenerate near-speck regions; 708→709 may be unreachable by construction from pass A — stated as unknown, not covered by a proposed fixture |
| 959→963, 982→986 | penetration floor disabled | an API option (`set_penetration_floor(None)`), not an input class |

### rebuild.py (edit path) — uncovered by all fourteen

| lines / branch | what it is | reached by |
| --- | --- | --- |
| 384→395 | **RUNNING_SINGLE/DOUBLE/TRIPLE/MANUAL** | any design with run objects — 55 of 100 on the angelfish; now pinned by constructed tests (`ce254a8`), still zero fixture reach |
| 271→276, 482–485, 522–530 | APPLIQUE phase emission | an appliqué design (editor-created) |
| 366→371 | SPIRAL_FILL / RADIAL_FILL | user-selected curved fills (editor) |
| 404→416 | divided-flow tatami | a user-drawn flow divide (editor) |
| 352→365 | `_satin_zigzag` fallback / user-forced satin | an edited satin whose spine attempt is non-viable |
| 287→295, 113–114 | angle-edit folding and auto-tolerance | an angle-edited satin |
| 139–151, 189 | validation errors; missing `source_mm_per_px` | imported or hand-built designs |
| 429–430, 501 | no-generator guard; <2-points error | **deliberately unreachable until something regresses** — they are the alarm, not a hole |

### The distinction that shapes the proposal

The pipeline's holes are **input classes** — kinds of artwork customers upload. Fixtures are the
right tool. The rebuild holes are mostly **editor states** — appliqué, curved fills, flow divides,
forced angles do not arrive in a PNG; they are made in the editor on top of a digitized design.
Constructed-design tests are the honest tool there, and several already exist. Proposing image
fixtures for editor states would manufacture coverage theatre.

## 3. The smallest new fixture set

Five entries close every corpus-reachable pipeline hole. Two are **promotions, not creations**:
the repository already tracks three real photographs (tier A of corpus100) that the bench
fourteen simply never included.

| # | fixture | covers | honest provenance |
| --- | --- | --- | --- |
| F1 | **promote `A01_real_peacock_patch_photo`** into the measured corpus | textured path, dark-linework chains, `RUNNING_SINGLE` emitter, sketch retries, rembg resize | **real photograph, already in the repo** |
| F2 | **promote `A02_real_neckline_black`** | dark-garment linework suppression (1130→1134), and the **phantom COLOR_CHANGE** — this is the P2 fixture, folded in as ruled | **real photograph, already in the repo** |
| F3 | new: anti-aliased **transparent-PNG logo** | declared-mask-constrains-segmentation (DET3), alpha rescale paths | synthetic, but faithful — this class IS born-digital |
| F4 | new: **SVG** of the same logo | SVG decode, declared-mask path from the vector side | synthetic by nature — SVGs are authored artifacts |
| F5 | new: **oversized source** (>`_MAX_WORK_PX`), ideally a real photo at native resolution | the downscale path, fine-detail warning | synthetic approximation **if** upscaled; honest only if a genuinely large real photo is used — flagged |

Still synthetic approximations of a photograph after this set: none of F1/F2 (real), F3/F4 are
faithful by class, F5 is the one to watch. What no fixture of any kind can cover: the
texture-retry **accepted** branch needs a photo where smoothing wins — F1 may or may not trigger
it; if it does not, that branch is reported as needing a real-job pair, not another synthetic.

**This sharpens the standing real-job-pairs ask in demonstrable terms: the synthetic corpus
misses the majority object type of the one real artwork on record. That is no longer an
assertion about representativeness; it is a measured coverage hole.**

## 4. Standing statement — what the fourteen are good for, and blind to

Committed at `apps/backend/tests/fixtures/quality_bench/README.md` so it lives beside the
fixtures it describes. Summary: the fourteen are strong on the flat-vector pipeline — palette
planning, classification, satin/tatami generation, routing, locking, accounting; nearly every
defect this engagement found and fixed was findable there. They are blind, in one direction, to
the messy real-world middle: photographs, texture, drawn linework, alpha/SVG declarations, dark
garments, oversized sources — and to every editor-side stitch type on the rebuild path.
