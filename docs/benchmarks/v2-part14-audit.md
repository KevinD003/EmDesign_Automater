# v2 Part 14 Audit — the fidelity loop: output vs INPUT, iterated

**Date:** 2026-07-29 · **Tag:** `v2-part14` · graded against [`v2-part13`](./v2-part13-summary.json)
**Grid:** [`v2-part14-grid.png`](./v2-part14-grid.png) · **Evidence strips:**
[`02`](./v2-part14-fidelity-02.png) · [`07`](./v2-part14-fidelity-07.png) · [`10`](./v2-part14-fidelity-10.png)

The brief: the stitch result does not look like the input image — identify a problem, fix ONE
thing, check the picture, repeat. This part ran that loop. Three root causes were found and fixed,
one attempted fix was caught making things worse and repaired with a guard, and two candidate
mechanisms were **exonerated by measurement** before any code changed.

LINT-VERIFY: findings=14 files=apps/backend/app/services/digitizer.py apps/backend/app/services/package.py apps/backend/tests/test_fidelity.py

---

## 1. What the loop found, in order

### Iteration 0 — instrument before touching anything

Side-by-side input-vs-output for the worst fixtures (02, 08, 10), then stage-by-stage painting of
fixture 02's pipeline. Two suspects were **cleared by evidence before any fix**: the k-means
palette (centers measured correct, ambiguous-blend pixels only 0.3%) and the segmentation masks
(the green cluster painted **pixel-perfect** — crisp circle hole, crisp letters). The defects were
all downstream of the stages the previous 13 parts had hardened.

### Fix 1 — the renderer has been lying since v1 (`package.py`)

Painting the *stitch stream* showed complete fill rows hugging the sun hole; the *render* showed a
lens of missing dashes around it. The stream dump proved the geometry perfect
(`... 70.38 · JUMP → 46.62 · 40.18 ...` — segments ending exactly at the circle edge). The
renderer's `flush(); run = []` on every JUMP **discarded the jump's landing coordinate — the first
penetration of the next segment** — so every post-jump segment lost its first span (up to one
6.4mm max-step) and 2-point segments were never drawn at all.

One line (`run = [to_px(s.x, s.y)]`) fixes every render since v1. This is why fixture 10 looks
transformed in this part's grid **with a byte-identical stitch stream**: the machine file was
always better than the preview claimed. It also means every visual judgement made from renders in
Parts 0–13 understated coverage around every hole — the committed metric (which rasterizes the
stream itself) was never affected.

### Fix 2 — fills sew straight across small knockout holes (`digitizer.py`)

The fill's serpentine connects row segments with a plain stitch whenever the hop is under
`CONNECT_MM` (3mm). A hole narrower than that — every letter of NORTHFIELD — therefore collects
**one surface thread crossing per fill row**, which is why the lettering read as mush. Standard
digitizing practice applied: **small holes are not knocked out; the fill sews solid and the detail
stitches on top** (`HOLE_KNOCKOUT_MIN_MM2 = 50` — letter-scale absorbed, feature-scale like 02's
26mm sun keeps the knockout).

### Fix 2b — the burial regression, caught by looking, guarded by the labels image

The first, unguarded version of Fix 2 shipped for exactly one bench run: fixture 07's HARBOR CLUB
**vanished** — the navy letters stitch *before* the cream disc (darkest-first), so absorbing the
disc's letter holes buried them under cream. The guard (`_hole_covered_later`) absorbs a hole only
when the cluster owning its pixels is stitched **later** than the fill, or when the hole is a
fringe of a larger earlier shape that continues ≥30% around it (edge overlap = good registration,
not burial). Verified per-hole on 07: all nine letter holes correctly kept
(`dominant=navy rank 0 < fill rank 3 → absorb=False`). Both directions are pinned as tests.

### Fix 3 — the 3×3 opening erased whole small-type lines (`digitizer.py`)

Fixture 02's "EST. 1974 · SUPPLY CO." vanished from the white mask: the big NORTHFIELD letters kept
the mask coarse enough to pass the open guard, and the opening then deleted every sub-2px stroke as
a unit. `_open_preserving_detail` restores any connected component the opening erased *outright*
when it is bigger than dust (`SPECK_KEEP_MM2 = 0.15` ≈ 4px) — speckle still dies, thin type
survives to the object stage. (The EST line is 2.6mm tall — below embroiderable size — so it is
then dropped *as a whole* by the area filter instead of leaving the random dashes Part 13 shipped.
Dropping cleanly is the correct machine outcome; the input/output divergence is now a deliberate,
explainable one.)

### Cleared, not fixed — recorded so the next loop doesn't re-chase them

- The "sparse banding" seen in fill bodies at low zoom is **resize moiré** of 0.45mm rows plus
  honest thread-gap texture — the star's geometry painted complete.
- The star's "white streaks" at high zoom are the same texture, not missing rows (geometry painted
  row-complete).
- The sub-3mm circular ring text on 07 remains mush: that is the small-lettering competitive gap
  (COMPETITOR-COMPARISON.md), not a new mechanism.
- Fixture 02's sun still shows a ~1mm registration crescent on its left edge (the yellow fill sits
  slightly right of the green hole) — mechanism not yet painted, left as the loop's next target.

## 2. Corpus effect

```
                         stitches        jumps      interior   band       spill
02_logo_fine_text_3color 3,696 → 3,406   180 → 116  99.0→99.1  97.1→94.0  3.7→1.6
all other fixtures       byte-identical streams (renderer fix is display-only for them)
corpus jumps             1,692 → 1,628
floor violations 0 → 0 · classification identical · over-limit 0 · sub-0.5mm 9 · density flagged 0
```

Only fixture 02 changes its stream — its letters are white (stitched later), so absorption fires;
07/08/10's small details stitch earlier and the guard correctly keeps their knockouts. **Their
dramatic visual improvement in this part's grid is therefore pure renderer honesty.** 02's edge
band drops 3.1: the stored contours no longer carry letter holes, so the band region itself is
redefined for that object — the metric moved because the *shape* it grades changed, stated here so
the number is not read as lost thread.

## 3. Verification

```
pytest — WITH rembg:     170 passed (was 165; +5 fidelity regression tests)
pytest — WITHOUT rembg:  170 passed
ruff over touched files: 14 — all pre-existing in digitizer.py; package.py + test_fidelity.py clean
secrets scan: clean · new constants: HOLE_KNOCKOUT_MIN_MM2, HOLE_FRINGE_RING_MM,
HOLE_FRINGE_MIN_SHARE, SPECK_KEEP_MM2 — each commented with grounding
new functions ≤37 lines (_hole_covered_later 37, _open_preserving_detail 23)
```

The five tests pin: post-jump segments are drawn; small covered holes absorb; large holes keep
knockouts; earlier-stitched detail is never buried; thin type survives the opening while dust dies.

## 4. What to attack

1. The 02 sun registration crescent (~1mm, one-sided) — paint the yellow region against the green
   hole and find the shift's mechanism.
2. Small lettering (sub-4mm glyphs) is now clearly THE fidelity ceiling on 07/08 — same conclusion
   as the competitor comparison, reached from a different direction.
3. `_hole_covered_later` decides from the dominant label; a hole containing two details with
   opposite ranks takes the majority's fate. No corpus case exists; construct one?
4. The renderer lied for 14 parts because no test compared drawn pixels to stream geometry. Fix 1's
   test does now — should a render-vs-geometry coverage assertion run corpus-wide in CI?
