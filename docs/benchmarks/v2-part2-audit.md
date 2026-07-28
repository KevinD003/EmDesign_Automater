# v2 Part 2 Audit — real satin-stroke lettering

**Date:** 2026-07-28 · **Tag:** `v2-part2` · graded against [`v2-part1-fix`](./v2-part1-fix-summary.json)
**Artifacts:** [`v2-part2-grid.png`](./v2-part2-grid.png) · [`v2-part2-summary.json`](./v2-part2-summary.json) · per-fixture PNG+JSON in [`v2-part2/`](./v2-part2/)

Scope of this re-grade: **lettering quality only.** Background separation, colour-layer
preservation and the Part 1 halo fix are untouched and verified unchanged (§4).

---

## 1. Two scope decisions, flagged rather than made silently

**(a) Not using `skimage.morphology.skeletonize`.** The brief suggested it "or an equivalent you
justify". `scikit-image` is **not** in `requirements.txt` or `requirements-dev.txt` — it appears in
this venv only because the optional `rembg` extra pulls it in — and `cv2.ximgproc.thinning` is
absent from `opencv-python-headless`. Depending on either would make lettering behave differently
on CI than locally: precisely the environment-dependence the Part 1 review caught. **Zhang-Suen
thinning is implemented in NumPy instead**, so both installs produce identical stitches.

**(b) A shared change to `digitize_image` was required.** `generate_lettering` does not stitch
anything itself — it renders text to a bitmap and delegates to `digitize_image` (lettering.py:123).
The bench likewise runs fixtures 05/06 as PNGs through that same function. A change confined to
`lettering.py` would therefore have left **every bench number identical**, and there would be
nothing to grade.

The change is an explicit **`text_mode` flag** (default `False`), not shape-driven detection —
adaptive classification for arbitrary artwork is Part 3. `generate_lettering` passes `True`;
fixtures 05/06 declare `"text": True` in `FIXTURE_PARAMS`, visible in the diff and in every summary
JSON. Fixtures 02 and 07 deliberately do **not**: isolating type inside a mixed logo needs
per-object stroke detection, so their text is unchanged and is honestly reported as such.

## 2. What the algorithm does

1. **Thin** the glyph to a 1px medial axis (Zhang-Suen), after a 3×3 close to stop boundary noise
   sprouting hairs.
2. **Prune spurs** shorter than the local stroke width — dead-end branches are thinning artifacts,
   and each one would otherwise start its own satin run with its own jump.
3. **Split** the skeleton into ordered branches between endpoints and junctions.
4. **Extend** each branch past its ends, along its tangent, clipped to the glyph (§3).
5. **Walk** each branch at the satin pitch, emitting a pair of points perpendicular to a
   window-smoothed tangent, at ±the local half-width from the distance transform — so column width
   follows the stroke, which is what script faces need.
6. **Fall back per segment**: where the stroke is wider than satin can span, the column is clamped
   to the satin limit and only the *unreachable remainder* is tatami-filled. The whole glyph is
   dropped to tatami only if its **median** width exceeds the limit.

Why median and not the over-limit fraction: the distance transform spikes at letter junctions
('M' vertex, 'U' bowl join) where the medial axis is genuinely far from every edge, even though the
*stroke* is no wider. Measured on "SUMMIT": stems are **3.66 mm median** but the 90th percentile
reads **7.32 mm**, purely from junctions. A fraction-based test fell back to tatami on letters that
were perfectly satin-able.

## 3. Three defects found and fixed while building this

Each was found by measuring, not by eye, using a geometric coverage metric (share of object area
within half a thread width of an actual stitch segment — never the bitmap).

| Defect | Symptom | Measurement | Fix |
|---|---|---|---|
| **Medial axis stops short of stroke ends** | every terminal lost its cap; letters looked eaten | coverage **82–89%** vs tatami's **96.7 / 99.3%** | extrapolate each branch end along its tangent, clipped to the glyph → **96.3 / 95.8%** |
| **Thinning hairs** | 'S' produced **82 branches from 179 skeleton px**; each started its own run, reading as scattered dashes | branch-length histogram | prune dead-ends shorter than the local stroke width |
| **Tangent noise** | a stair-stepped skeleton swings the estimated direction ~45° between adjacent samples, fanning columns into a furry edge | coverage 95.7 → **96.3%** | estimate the tangent over a ±3-sample window |

## 4. Objective results — `v2-part1-fix` → `v2-part2`

| Fixture | SATIN / objects | satin share | colours | jumps | mode |
|---|---|---|---|---|---|
| 01 flat_2color_logo | 0/2 → 0/2 | 0% → 0% | 2 → 2 | 63 → 63 | — |
| 02 logo_fine_text_3color | 1/16 → 1/16 | 6% → 6% | 3 → 3 | 171 → 171 | — |
| 03 gradient_soft_subject | 0/4 → 0/4 | 0% → 0% | 4 → 4 | 452 → 452 | — |
| 04 thin_line_outline | 0/11 → 0/11 | 0% → 0% | 1 → 1 | 285 → 285 | — |
| **05 wordmark_caps** | **1/6 → 6/6** | **17% → 100%** | 1 → 1 | **174 → 93** | text |
| **06 wordmark_script** | **3/12 → 12/12** | **25% → 100%** | 1 → 1 | 101 → 107 | text |
| 07 circular_badge | 0/18 → 0/18 | 0% → 0% | 3 → 3 | 866 → 866 | — |
| 08 mascot_detail | 0/21 → 0/21 | 0% → 0% | 5 → 5 | 385 → 385 | — |
| 09 nonuniform_background | 0/2 → 0/2 | 0% → 0% | 2 → 2 | 41 → 41 | — |
| 10 low_contrast_subject | 0/4 → 0/4 | 0% → 0% | 3 → 3 | 150 → 150 | — |

**Every non-lettering fixture is byte-identical** — same object counts, colour counts, jump counts.
That is the scope guarantee, measured rather than asserted: only fixtures with `text=True` moved.

### No-regression check on the Part 0/1 wins, read from the JSON

| Fixture | `color_count` part1-fix | `color_count` part2 | |
|---|---|---|---|
| 02_logo_fine_text_3color | 3 | **3** | unchanged |
| 07_circular_badge | 3 | **3** | unchanged |
| 08_mascot_detail | 5 | **5** | unchanged |
| 09_nonuniform_background | 2 | **2** | unchanged |

Sub-0.5 mm stitches 3 → 5 across all ten fixtures; **0** stitches over the 12.7 mm machine limit.

### Geometric coverage (not from the render)

| Fixture | tatami (before) | satin (after) |
|---|---|---|
| 05_wordmark_caps | 96.7% | **96.3%** |
| 06_wordmark_script | 99.3% | **95.8%** |

Caps reach parity; script sits 3.5 points below, concentrated at junctions where columns from
meeting strokes do not perfectly abut. Reported rather than smoothed over.

---
## 5. Adversarial re-grade

Same method as Parts 0/1: a grader per fixture, then an adversarial reviewer told to assume the
improvement was overstated. Challenged scores stand. 02 and 07 are **controls** — Part 2 should not
have touched them.

| Fixture | | grader | **challenged** | verdict | columns follow strokes? |
|---|---|---|---|---|---|
| 05 wordmark_caps | PRIMARY | 2 → 4 | **2 → 3** | improved | **yes** (confirmed from the image) |
| 06 wordmark_script | PRIMARY | 2 → 3 | **2 → 2** | mixed | disputed — see §6 |
| 02 logo_fine_text_3color | control | 2 → 2 | **1 → 1** | unchanged | n/a — correctly untouched |
| 07 circular_badge | control | 1 → 1 | **1 → 1** | unchanged | n/a — correctly untouched |

Both controls confirmed identical before/after by reviewers reading the JSONs, so **the scope
guarantee held under adversarial checking**, not just in my own diff.

## 6. The reviewers' central claim, tested

> *"AFTER is HOLLOW, not satin-filled… stitches sit ON the contour; they do not span from one
> stroke edge to the other. That is outline stitching, not satin."* — challenger, fixture 06

This would mean the whole implementation is wrong, so it was measured rather than argued. Coverage
was recomputed **separately for the stroke interior and the edge band** (interior = the glyph eroded
by 0.6 mm; edge = the remainder). Outline stitching covers the edge and not the interior; satin
columns cover both.

| Fixture | | all | **interior** | edge |
|---|---|---|---|---|
| 05 wordmark_caps | tatami (before) | 84.3% | 84.5% | 84.1% |
| 05 wordmark_caps | **satin (after)** | 87.1% | **95.2%** | **78.1%** |
| 06 wordmark_script | tatami (before) | 88.4% | 92.9% | 87.5% |
| 06 wordmark_script | **satin (after)** | 90.2% | **98.2%** | 88.7% |

**The claim is refuted.** Interior coverage *rose* under satin on both fixtures — to 95.2% and
98.2%. The columns do span the strokes; the glyphs are not hollow.

Why it looked hollow is worth recording, because it is the third instance of the same underlying
problem: **the preview renderer cannot faithfully draw satin.** It renders each stitch as a
hairline, so a satin column reads as a row of separate ticks with gaps between them, while tatami's
long horizontal runs read as solid. Fixture 06 makes this worst because its strokes are so thin
that **84% of the glyph's area lies within 0.6 mm of an edge** (interior 2,201 px vs edge 11,864 px)
— there is barely any "interior" to look solid. The reviewer's *observation* was accurate; the
inference from it was not. (Previously: fixed 2px stroke width, and light thread invisible on a
white ground.)

**But one of their criticisms is confirmed.** Edge-band coverage on fixture 05 *fell* 84.1% → 78.1%,
which is exactly the "ragged, furry, overshooting edges" the reviewers described. Satin columns
built from skeleton ± local width do not hug the outline the way a real digitiser's edge-defined
columns would. That is a genuine quality regression at the letter edge, traded for a large gain in
the interior, and it is not fixed here.

**And a third criticism was correct and has been fixed.** `fill_row_pitch_mm` reported **0.018 mm**
for satin fixtures — physically impossible for 0.4 mm thread. It measures spacing between distinct
y-values, which for a satin zigzag are the column vertices, not fill rows. The harness now returns
`0.0` for majority-satin designs instead of a meaningless number that looks like a measurement.
Caught by an adversarial reviewer reading my own metric more carefully than I did.

## 7. Honest position on Part 2

**What is established:** lettering now stitches as satin columns that follow stroke direction
(satin share 17% → 100% and 25% → 100%), interior coverage improved on both wordmarks, fixture 05's
jump count fell 174 → 93, no non-lettering fixture moved by a single stitch, and both test
environments pass at 90.

**What is not:** the challenged scores are **05: 2→3** and **06: 2→2**. On fixture 06 the reviewer
scored no net gain, and after checking their reasoning I only partly disagree — the hollowness claim
is wrong, but the ragged edges and the broken 'y' descender fragment are real, and a texture change
that does not clearly improve word legibility is a fair thing to score as neutral.

So: **structurally the right change, measurably better in the stroke interior, still visibly rough
at the edges.** Edge-defined satin (deriving each column from the two boundary curves of the stroke
rather than from skeleton ± width) is the known way to fix that, and is a larger change than Part 2
scoped.

**Also unimproved and stated plainly:** the text inside fixtures 02 and 07 is untouched, because
`text_mode` is per-design. Per-object stroke detection would be needed to find the type inside a
mixed logo, and that is Part 3's adaptive classification.
