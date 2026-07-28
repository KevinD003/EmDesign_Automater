# STITCHIQ v2 — Part 2 Work Report for Independent Review
**Date:** 2026-07-28 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Commits:** `a9c4a80` (code) · audit + STATUS v37 follow-ups

> Part 2: replace tatami-filled lettering with real satin-stroke lettering.
> §6 is what a reviewer should attack; §5 is a claim I tested and refuted, plus two I confirmed.

---

## 1. Two scope decisions, flagged not silent

**(a) I did not use `skimage.morphology.skeletonize`,** which the brief suggested "or an equivalent
you justify". `scikit-image` is absent from `requirements.txt` and `requirements-dev.txt` — it is in
my venv only because the optional `rembg` extra pulls it in — and `cv2.ximgproc.thinning` is absent
from `opencv-python-headless`. Depending on either would reproduce exactly the environment-dependent
failure your Part 1 review caught. **Zhang-Suen thinning is implemented in NumPy**, so both installs
produce identical stitches.

**(b) A shared change to `digitize_image` was required, and here is the proof.**
`generate_lettering` does not stitch anything — it renders text to a bitmap and delegates to
`digitize_image` (`lettering.py:123`). The bench runs fixtures 05/06 as PNGs through that *same*
function. A change confined to `lettering.py` would have left **every bench number identical**.

The change is an explicit **`text_mode` flag** (default `False`), not shape-driven detection, which
is Part 3. Fixtures 05/06 declare `"text": True` in `FIXTURE_PARAMS`, visible in the diff and in
every summary JSON. **02 and 07 deliberately do not** — so the text inside those mixed logos is
unimproved, and that is stated rather than glossed.

## 2. The algorithm

Thin the glyph to its medial axis → prune spurs shorter than the local stroke width → split into
branches → extend each branch past its ends to the stroke cap → walk it at the satin pitch, emitting
point pairs perpendicular to a window-smoothed tangent at ±the local half-width from the distance
transform. Where a stroke exceeds the satin cap, the column is clamped and only the unreachable
remainder is tatami-filled (per-segment fallback); the whole glyph drops to tatami only if its
**median** width exceeds the cap.

Median, not the over-limit fraction, because the distance transform spikes at letter junctions
('M' vertex, 'U' bowl join) where the medial axis is far from every edge although the stroke is no
wider — "SUMMIT" stems measure **3.66 mm median but 7.32 mm at p90**, purely from junctions. A
fraction test dropped perfectly satin-able letters to tatami.

## 3. Three defects found by measuring, not by eye

| Defect | Measurement | Fix |
|---|---|---|
| Medial axis stops half a stroke-width short of each stroke **end**, so every terminal lost its cap | coverage **82–89%** vs tatami's 96.7 / 99.3% | extrapolate branch ends along the tangent, clipped to the glyph → **96.3 / 95.8%** |
| Thinning sprouts hairs — each starts its own satin run with its own jump, reading as scattered dashes | letter 'S': **82 branches from 179 skeleton px** | prune dead-ends shorter than the local stroke width |
| Tangent from adjacent samples swings ~45° on a stair-stepped skeleton, fanning columns into a furry edge | coverage 95.7 → **96.3%** | estimate over a ±3-sample window |

## 4. Objective results (`v2-part1-fix` → `v2-part2`)

| Fixture | SATIN/objects | satin share | jumps | mode |
|---|---|---|---|---|
| **05 wordmark_caps** | **1/6 → 6/6** | 17% → **100%** | **174 → 93** | text |
| **06 wordmark_script** | **3/12 → 12/12** | 25% → **100%** | 101 → 107 | text |
| 01, 02, 03, 04, 07, 08, 09, 10 | unchanged | unchanged | unchanged | — |

**All eight non-lettering fixtures are byte-identical** — object counts, colour counts and jump
counts all unmoved. `color_count` for 02/07/08/09 read straight from the JSON: **3, 3, 5, 2**,
unchanged. Sub-0.5 mm stitches 3 → 5 across all ten; **0** stitches over the 12.7 mm limit.

**Tests, both environments, exact final lines:**
```
pytest — WITH rembg:     90 passed, 1 warning in 16.86s
pytest — WITHOUT rembg:  90 passed, 1 warning in 4.99s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)
```

## 5. Adversarial re-grade — one claim refuted, two confirmed

| Fixture | | grader | **challenged** | verdict |
|---|---|---|---|---|
| 05 wordmark_caps | PRIMARY | 2 → 4 | **2 → 3** | improved |
| 06 wordmark_script | PRIMARY | 2 → 3 | **2 → 2** | mixed |
| 02, 07 | controls | unchanged | **unchanged** | scope held |

### Refuted: "the strokes are hollow — outline stitching, not satin"
A challenger claimed fixture 06's stitches sit *on* the contour with bare interiors. That would mean
the implementation is fundamentally wrong, so I measured interior and edge coverage separately
(interior = glyph eroded 0.6 mm):

| Fixture | | all | **interior** | edge |
|---|---|---|---|---|
| 05 | tatami | 84.3% | 84.5% | 84.1% |
| 05 | **satin** | 87.1% | **95.2%** | **78.1%** |
| 06 | tatami | 88.4% | 92.9% | 87.5% |
| 06 | **satin** | 90.2% | **98.2%** | 88.7% |

Interior coverage **rose** on both. The strokes are not hollow. It *looked* hollow because the
preview renders each stitch as a hairline, so satin columns read as separate ticks while tatami's
long runs read solid — and fixture 06's strokes are so thin that **84% of the glyph area lies within
0.6 mm of an edge** (interior 2,201 px vs edge 11,864 px). Their observation was accurate; the
inference was not. This is the **third** instance of the preview misrepresenting stitches, after the
fixed 2px stroke width and light-thread-invisible-on-white.

### Confirmed: ragged edges are real
Edge-band coverage on fixture 05 **fell 84.1% → 78.1%** — exactly the "furry, overshooting" edges
the reviewers described. Skeleton ± local width does not hug an outline the way edge-defined satin
would. **Not fixed**; it is a real trade of edge crispness for interior coverage.

### Confirmed: my own metric was degenerate
`fill_row_pitch_mm` reported **0.018 mm** for satin fixtures — impossible for 0.4 mm thread. It
measures spacing between distinct y-values, which for a zigzag are column vertices, not fill rows.
Now returns `0.0` for majority-satin designs instead of a meaningless number that looks like a
measurement. Caught by a reviewer reading my metric more carefully than I had.

## 6. What to attack

1. **Is 06's "2 → 2 mixed" the right call?** I only partly disagree with it. The hollowness claim is
   wrong, but the ragged edges and a broken 'y' descender fragment are real, and "different texture,
   not clearly more legible" is a fair neutral score.
2. **Edge crispness regressed while interior coverage improved.** Is that trade acceptable, or does
   it mean skeleton-driven satin is the wrong primitive and edge-defined columns (from the stroke's
   two boundary curves) should have been built instead? That is the known fix and is larger than
   Part 2's scope.
3. **`text_mode` is per-design.** Text inside a mixed logo (02, 07) is untouched. Is deferring that
   to Part 3 right, or should Part 2 have shipped per-object stroke detection?
4. **Was enabling `text=True` for fixtures 05/06 a fair parameter change?** It is declared in the
   diff and in every JSON, and no other fixture moved — but it does mean 05/06 are compared under a
   changed setting.
5. **Three renderer defects are now known and only one is fixed.** Should the customer-facing preview
   be fixed before more quality work is graded through it?

## 7. Reproduction

```bash
git checkout claude/code-quality-improvements-hyu6dg && git pull
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt    # deliberately NO rembg
python tests/make_fixtures.py
python -m pytest tests -q                                   # expect 90 passed
python scripts/run_quality_bench.py --tag v2-part2
```
Then `pip install -r requirements-features.txt` and re-run — expect **90 passed** again. Satin
lettering is identical either way, by design (no skimage dependency).

**Key artifacts:** [`docs/benchmarks/v2-part2-audit.md`](./benchmarks/v2-part2-audit.md) ·
[`v2-part2-grid.png`](./benchmarks/v2-part2-grid.png) · [`v2-part2-summary.json`](./benchmarks/v2-part2-summary.json)
