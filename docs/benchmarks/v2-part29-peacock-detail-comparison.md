# Peacock: final output vs original — every observable detail

**Date:** 2026-08-01 · Output = tree at `61049fb`, 8 colours, 130×180 hoop.
Method: the source photo and the final render were cropped into eight aligned
region pairs and inspected side by side; colours were measured by k-means on the
source foreground vs our emitted colour stops; geometry from the design's own
object metadata. Verdicts: ✓ match · ◐ partial · ✗ missing/wrong.

## 1. Global geometry

| Property | Source | Output | Verdict |
|---|---|---|---|
| Canvas | 380×578 px photo | 99.3 × 142.9 mm design | — |
| Aspect ratio | 0.657 | 0.695 | ◐ output ~6% relatively wider — pull compensation and mask solidify dilate every region outward |
| Composition | bird on Y-branch, flowers upper-left/left/right, tail sweeping down-right | all present, correct positions | ✓ |
| Element inventory | bird, 2 branch arms, ~4 flower clusters, ~14 leaves, ~11 tail eyes, talons, beak, crest | all present except detached beak; ~10–11 eyes; ~14 leaves (≈5 fragmented) | ◐ |

## 2. Colour — measured palette vs emitted stops

| Source cluster (k=10, share) | Nearest output stop | Verdict |
|---|---|---|
| `#253f64` navy highlight 16.4% | `#203a5e` | ✓ close |
| `#122b4f` navy SHADOW 12.7% | — merged into `#203a5e` | ✗ the tail's two-tone navy (lit vs shadow) is flattened to one navy |
| `#92be8a` light green 13.3% | `#8fc38a` | ✓ |
| `#70a171` mid green 13.1% | `#73a171` | ✓ near-exact |
| `#b7d3ad` pale mint (eye fringe highlights) 8.3% | — merged into `#8fc38a` | ✗ eye outer rings lose their two-green gradient |
| `#403e36` black-brown (crest, outlines) 8.3% | `#45413c` | ✓ |
| `#ead754` yellow 8.0% | `#e8d14b` | ✓ |
| `#4e7164` TEAL (neck transition, eye glints) 7.7% | — absent | ✗ the single most characteristic peacock colour is not in the output |
| `#796743` mid brown 6.4% | `#746147` | ✓ |
| `#b5a73c` olive (eye iris) 5.7% | `#aeac45` | ✓ |
| — | `#d6dbc9` pale (93 st) | ◐ stands in for cream highlights; appears as odd white patches in two flowers |

**Summary: 7 of 10 source colours matched within a few units of hex; the three
losses are all gradient partners** (deep navy, pale mint, teal) — flattened by
quantization at 8 colours. 13 stops mount 8 threads (5 deferred-detail re-mounts).

## 3. Region by region

### Head, crest, beak
| Detail | Source | Output |
|---|---|---|
| Beak | slender gold satin spike, ATTACHED, pointing up-left, brown tip | ✗ detached yellow bar floating 4mm from the head, wrong angle, tip lost |
| Crest plumes | 3–4 black plumes with white gaps between (striped) | ✗ merged into one solid dark mass — striping lost |
| Crest tufts | 3 small distinct green tufts on stalks | ◐ present but merged into one blob, enlarged |
| Head→neck | continuous navy, no break | ◐ white gap at the junction |

### Neck and body
| Detail | Source | Output |
|---|---|---|
| Neck colour | GRADIENT: green crown → teal → navy at the shoulder | ✗ flat navy; the teal transition colour is absent from the palette |
| Body shape | almond/leaf oval, ~leans right | ✓ shape and lean correct, ~10% wider |
| Body texture | SCALE PATTERN — rows of overlapping feather crescents in two greens | ✗ flat single-direction tatami at 58.7°; no scallop motif (needs MOTIF_FILL, unbuilt) |
| Body colour | mid green `#70a171` with light `#92be8a` scales | ◐ took the light green only |
| Navy body edging | continuous navy rim on the left side | ◐ present, two white breaks |

### Wing saddle and talons
| Detail | Source | Output |
|---|---|---|
| Wing coverts | 6–8 separate long yellow satin QUILLS, fanned, each navy-outlined | ◐ yellow mass with partial quill separation; outlines absent |
| Talons | 3–4 distinct yellow claws curled around the branch | ◐ chunky merged claws; grip readable, toes not separable |
| Branch under talons | two-tone brown, long-and-short shading | ◐ both browns present, flat fills, no shading interleave |

### Tail (the design's core)
| Detail | Source | Output |
|---|---|---|
| Field | deep navy, LONG stitches flowing along the tail's curve, two-tone lit/shadow | ◐ solid navy ✓, but rows at fill angle −11° (do not follow the sweep), single tone |
| Centre stems | thin green quills running the full tail length, one per feather | ◐ partial: mid-tail strips present, several disconnected or missing |
| Eye count | ~11 | ✓ 10–11 recovered |
| Eye structure | pale-green feathered outer ring → olive/yellow ring → navy pupil → green glint | ◐ green ring + olive ring + navy pupil correct in most; glint lost (teal); 2–3 eyes merged with stems into green patches |
| Eye ring edges | soft fringed/barbed ring boundary | ✗ hard blob boundaries |
| Bottom fringe | ordered green barbs pointing down along the hem | ◐ green barb clusters present, less ordered |
| Edge whiskers | fine navy barbs along both tail edges | ◐ present but chaotic vs the source's combed order |
| Pinholes | none — regions abut | ◐ a few white pinholes remain around eye rings (much reduced by seam fill) |

### Left branch and flowers
| Detail | Source | Output |
|---|---|---|
| Branch line | tapering, forked, two browns, smooth curve | ✓ path and both browns correct; slightly chunkier |
| Flower form | 5 rounded petals per bloom, separable, navy outline, dark centre stamen dot | ✗ petal boundaries mostly lost — blooms read as yellow blobs; outlines absent; centres appear as navy specks in ~half |
| Bloom count/placement | upper cluster + mid pair + lower double-bloom | ✓ all four sites have yellow mass |
| Buds | 2 small yellow buds on stalks upper-left | ◐ present, detached from stalks |
| Leaves | pointed ovals, satin, DARK CENTRE VEIN, stem-stitch outline | ◐ positions/shapes right; veins ✗ (a few remain as navy blobs); outlines ✗ |

### Right branch
| Detail | Source | Output |
|---|---|---|
| Branch fork | S-curved arm, tapering to a point | ✓ curve correct; tip blunter; short whiskers on the bark edge |
| Flower | one 5-petal bloom + white bud pair below | ◐ bloom is a blob with the white bud rendered as a pale patch with stray triangle |
| Leaves | 5, veined, outlined | ◐ 5 present, 2 fragmented, no veins/outlines |

## 4. Stitch-level comparison

| Property | Source (hand-digitized patch) | Output |
|---|---|---|
| Stitch vocabulary | long-and-short shading, satin quills, scale motif, flowing directional long stitch, stem-stitch outlines, fringe barbs | 104 satin objects + 9 tatami fills; no outline runs, no motif, no long-and-short |
| Direction control | stitch direction FOLLOWS each form (tail sweep, body curve, petal fan) | per-object principal-axis angle only (e.g. tail −11.3°, body 58.7°) — correct on strokes, cannot curve within an object |
| Outlines | nearly every element edged in stem stitch | none — RUNNING/BACKSTITCH generators exist but are never auto-selected |
| Density | dense, overlapping layers (true patch coverage) | 12,762 stitches single-layer + underlay; a real sew-out of this size would run 25–40k |
| Colour changes | unknown (typical: 8–10) | 13 stops / 8 threads |
| Machine safety | unknowable from photo | floor 0, over-limit 0, density flags 0 — measured |

## 5. The five roots behind every ✗ above

1. **8-colour quantization flattens gradients** — deep navy, pale mint and teal
   are gradient partners of kept colours. More stops would trade colour fidelity
   against changes; the real answer is A3 (photo-stitch blending), still open.
2. **No outline pass** — the source edges nearly everything in stem stitch;
   we never emit running-stitch outlines around fills. Buildable: the contour
   data already exists on every object.
3. **No motif/scale fill and no in-object direction flow** — body scales and
   curved tail grain need MOTIF_FILL and guided/curved fill, both still enum-only.
4. **Small-element merging** — crest stripes, petal boundaries, beak attachment
   are sub-millimetre separations; mean-shift + solidify heal noise and these
   real gaps alike. Sharper separation needs edge-aware segmentation, not caps.
5. **Photo reconstruction ceiling** — everything here is inferred from pixels a
   real digitizer chose by hand; the vector path remains the clean route.

## 6. Scorecard

| Dimension | Score |
|---|---|
| Composition & element inventory | 9/10 |
| Shapes & proportions | 7/10 |
| Colour fidelity | 7/10 (7 of 10 matched; gradients flattened) |
| Fill solidity / coverage | 8/10 (spill 9.6%, interior 97.6) |
| Texture & stitch artistry | 3/10 (no motif, no outlines, no directional flow) |
| Fine detail (beak, stripes, petals, veins) | 4/10 |
| Machine safety | 10/10 measured |
