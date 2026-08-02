# v2 Part 36 — 100-design corpus run, three engine fixes, and three editors

**Date:** 2026-08-02 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Request:** "Check our app with 100 such embroidery images for improvement. And improve
it all — along with Photoshop-style image edit, thread editor, DST editor and such
things they have in competitors."

---

## 1. The corpus — read the provenance before any number

This environment has **no outbound access to image hosts**, so 100 distinct real-world
embroidery designs could not be downloaded. The corpus is built from everything
genuinely available, in three labelled tiers, and every table below keeps the label so
a synthetic average is never read as a real-world score:

| Tier | n | What it is |
|---|---|---|
| **A — real** | 13 | The 3 user-supplied embroidery images (photographed peacock patch, floral neckline on black, full-length neckline panel) + the 10 existing quality-bench fixtures |
| **B — real-derived** | 40 | Crops, rotations, rescales and recolours of the real photographs. **Real thread texture, real lighting, real artwork structure** — only the framing is synthetic. This is the tier that stresses the photo pipeline honestly |
| **C — parametric** | 47 | Generated artwork spanning classes known to be hard: hairline linework, lattice trellis, tiny lettering, dense florals, badges with text, gradients, high colour count, thin borders, scattered specks, rings/holes, monograms, noisy subjects |

Reproduce with `scripts/build_corpus100.py` (fixed seed) and `scripts/run_corpus100.py`
(process pool). The 27MB of images and the raw JSON stay out of git by `.gitignore`.

## 2. Results

| | Before | After |
|---|---|---|
| Crashes | **0 / 100** | **0 / 100** |
| Designs producing **zero stitches** | **12** | **9** |
| Interior coverage (median, all measurable) | 97.00 | **97.15** |
| Penetration-floor violations (total) | — | **3** (2 designs) |
| Over-machine-limit stitches (total) | — | **6** (2 designs) |
| Density flags (total) | — | **85** (68 in one design) |

Per tier, after:

| Tier | n | empty | interior median | slowest |
|---|---|---|---|---|
| A — real | 13 | **0** | **99.05** | 54.7s |
| B — real-derived | 40 | **0** | **95.90** | 53.9s |
| C — parametric | 47 | 9 | 100.00 | 10.2s |

**No real or real-derived design fails.** All nine remaining empties are tier-C
thin-stroke synthetics.

### The measurement instruments were wrong twice, and that was caught

The first harness reported `floor=-88, over_limit=-88` — nonsense from wrong dict keys.
Fixing those, `over_limit` then read **285–865 "violations" on clean designs** because it
counted *every* consecutive pair: a jump or a post-trim move is legitimately long, since
the needle travels with the thread cut. Restricting it to consecutive **sewn** stitches
gives 0/0/0 on all three real designs. Both instrument errors are recorded in the
script; an unvalidated instrument is worth less than no instrument.

## 3. Three engine defects found and fixed

All twelve empty designs traced to thin strokes, through three stacked causes:

1. **The palette never saw the ink.** The colour palette is seeded from an *eroded*
   foreground (to stop anti-alias halos seeding phantom threads). Erosion deletes thin
   strokes entirely, so on a lattice the palette was sampled only from the white
   diamonds — k-means saw three shades of white, the ink was never a cluster, and the
   design digitized to **zero objects**. *This hole applies to any outline-only colour:
   linework, stems, text strokes.* Fixed by recovering colour **modes** the eroded
   sample missed, restricted to locally-uniform stroke cores (a real ink is a sharp
   histogram peak; the blend band our own upscaler creates is a smear, and requiring a
   local maximum is what keeps the halos out).
2. **Duplicate k-means centres discarded the ink.** k-means returns k centres even when
   the artwork has fewer colours, so a 2-colour image asked for 8 gets duplicates. Every
   ink pixel then sits equidistant from two *identical* centres, the "ambiguous blend"
   test calls it an anti-aliasing halo, and it is dropped. Fixed by requiring the two
   nearest centres to be genuinely different colours, and by merging duplicate centres —
   **greedily into the dominant centre, never transitively**: a union-find chained
   white → halo → halo → ink across the gradient and collapsed the whole image into one
   cluster (measured; the greedy form fixed it).
3. **The speck filter measured polygon area, not ink.** `cv2.contourArea` uses the
   shoelace formula over pixel *centres*, so a 1px-wide stroke encloses **zero** area
   however long it is. Thin artwork was deleted outright — 15,641 contours of "area 0".
   Now the filter counts drawn pixels, which is what "drop specks under 2mm²" always
   meant.

**Corpus impact:** exactly **one** of ten byte-identity locks moved (fixture 07), and it
moved the right way — 15 → 17 objects, 8,642 → 8,696 stitches (+0.6%), interior coverage
identical at 99.40, floor violations 0, density flags 0. Previously-dropped thin detail
is now stitched. The lock was regenerated deliberately with that diff recorded.

**A test also had to be corrected, not weakened.** `test_fleece_fill_rows_are_sparser_than_cotton`
measured row pitch as gaps between distinct *y* values — valid only when rows run
horizontally. On a symmetric square the edge-avoiding fill angle has two equally valid
answers ~90° apart; cotton picked 47° and fleece −42°, so the comparison was between two
different projections and **passed by coincidence**. When the palette fix made both
fabrics agree at 47°, the coincidence vanished. It now measures thread length per unit
area — orientation-independent, and it discriminates cleanly (cotton 3.465 vs fleece
2.971 mm/mm²).

## 4. Honest limits — the ranked next-fix list

- **9 designs still produce no stitches**, all tier-C thin strokes. Some are *correctly*
  refused: 1px lines at that hoop size are ~0.16mm, under the 0.4mm thread itself — the
  right behaviour is to say so, and the design does emit "About 100% of the artwork is
  too small or too faint to sew at this size". Others (the 46px-gap lattice on black)
  should stitch and do not; the same class on a white background now does.
- **`B06_crop` is the worst real-derived design**: 68 density flags, 2 floor violations,
  5 over-limit stitches. It is one crop of a real photo and it is the single biggest
  quality outlier in the corpus — the next thing to fix.
- **9 designs report interior coverage as unavailable** (the metric returns None for
  certain geometries, e.g. `04_thin_line_outline` and the `B*_scale` variants). The
  coverage instrument, not the designs, needs that gap closed.
- **Digitize time rose** (corpus total 1082s → ~1500s at peak, now 606s with the final
  build) — the palette-recovery pass adds a median blur and a histogram per plan.
  Worth profiling before it matters at scale.

## 5. Three editors competitors ship, now shipped here

All three are real backends with tests, not UI shells.

**Image editor** (`services/image_edit.py`, `POST /api/image/{analyze,edit}`) — the prep
step Hatch and Wilcom both put in front of digitizing, because the colour plan is only
as good as the artwork handed to it. Crop, straighten (canvas grows so a rotate never
eats a corner), flip, scale, brightness/contrast/gamma, per-channel auto-levels,
saturation/hue, sharpen, denoise, posterize, threshold, and background removal that
reuses **the digitizer's own segmentation** so the preview cannot lie about what will be
stitched. Ops compose in a fixed documented order, so the same sliders always give the
same pixels. `analyze` measures the image and quotes the number behind each suggestion
("Low contrast (tonal span 118/255) — auto-levels will separate the colours…").

**Thread editor** (`services/thread_store.py`, `/api/threads/custom`, `/api/threads/palettes`) —
per-user custom thread chart (brand/name/code/hex, validated and normalised) plus named
palettes saved from a design's stops and re-applied to another. Every shop runs cones the
shipped catalogue does not have; this is where they live.

**Stitch (DST) editor** (`services/stitch_edit.py`, `/api/stitches/{edit,stats}`) —
edits the *stream*, so it works on an imported machine file with no objects at all:
select a range, delete it, retype it (jump ↔ stitch), strip trims, split a colour block,
translate/scale/rotate/mirror. Two machine invariants are restored after **every** edit
and any repair is reported rather than silently applied: no move may exceed the 12.7mm
reach (scaling a block up is exactly what produces those, and the file would fail at the
machine, not here), and the stream ends with exactly one END and no doubled controls.
A unit test caught a real bug in my own accounting — appending END masked a removal in
the length delta, so an automatic repair went unreported.

Two layout defects were caught by *looking at the rendered app*: the Studio's right rail
was a 3-row grid holding five panels (the thread editor collapsed to its heading, the
transform sliders were clipped), and the warnings banner was squeezed into a one-word
column by the canvas's centring flex.

## 6. Guardrails

pytest **768 passed + 2 xfailed** (20 new: 16 editor, 4 thin-stroke) · vitest **127** · tsc + vite build clean ·
ruff at the **19**-error baseline · 9/10 stream locks byte-identical, the tenth
regenerated deliberately with its improvement measured.

## Files

- Engine: `app/services/digitizer.py` (palette mode recovery, centre merge, blend-cut
  relief, pixel-area speck filter)
- Editors: `app/services/{image_edit,thread_store,stitch_edit}.py`,
  `app/routers/{image_edit,thread_edit,stitch_edit}.py`
- Frontend: `components/dialogs/ImageEditor.tsx`,
  `components/panels/{ThreadEditor,StitchEditor}.tsx`, `api/client.ts`, `index.css`
- Corpus: `scripts/build_corpus100.py`, `scripts/run_corpus100.py`
- Tests: `tests/test_part36_editors.py` (16), `tests/test_part36_thin_strokes.py` (4),
  corrected `tests/test_pullcomp.py`
