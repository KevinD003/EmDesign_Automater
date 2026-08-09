# 3e-ii and 3e-iii findings — report before building

**Headline: the contour-fidelity hypothesis is wrong, and the real cause is much bigger than the
digitize/rebuild gap it was invoked to explain.**

Travel routing manufactures **31% of the entire bench corpus** — 30,053 of 97,590 stitches, 37.6
machine-minutes. On the badge it is **48%**. That is the answer to 3e-iii, and it makes 3e-ii's
question secondary.

---

## 3e-ii — contour fidelity: measured, and REFUTED

Method: patched `generation.spine_satin` to capture the region mask digitize's satin core actually
receives, then rebuilt the mask the way `rebuild_design` does — from the **stored** contour and
holes, at the **same** raster (0.0975 mm/px) — and diffed them. Then ran the same core on each.

Target: badge Satin 3, the largest object and 8,861 of the 13,105-stitch design gap.

| | area | contour | result of the same core |
|---|---:|---|---|
| digitize's actual region | 1,551.9 mm² (163,250 px) | — | 3,324 pts · median_w 3.58 mm · axis 1,304 |
| mask from the stored contour + holes | 1,555.2 mm² (163,600 px) | 1,080 pts, 3 holes | 3,405 pts · median_w 3.71 mm · axis 1,396 |
| **delta** | **+3.3 mm² (+0.2%)** | | **+81 pts (+2.4%)** |

**The stored contour is faithful.** 0.2% area error, and feeding it through the identical core costs
81 extra points. The object gap it was supposed to explain is **+8,861**. Contour fidelity accounts
for roughly **1%** of it.

My suspicion was wrong, and so was the ruling that adopted it. **No Bezier/path primitive is needed
to close this gap** — that model change may still be worth having for other reasons, but it is not
the fix here and should not be justified by these numbers.

## Where the gap actually is

Same object, rebuilt with stages removed one at a time:

| configuration | stitches |
|---|---:|
| full | 21,334 |
| no underlay | 21,151 |
| **no travel routing** | **4,345** |
| neither | 4,162 |

**Travel routing is 16,989 stitches — 80% of the object.** Underlay contributes 183. Generation
contributes ~4,300.

The satin core the last four steps were spent unifying produces about a fifth of this object. The
rest is `_route_travel` converting inter-column jumps into sewn runs, and on a three-holed ring band
it does that constantly.

---

## 3e-iii — is 44 machine-minutes right for one 4-colour badge? **No.**

Travel routing's contribution across the bench, digitize path, canonical params:

| fixture | with travel | without | manufactured | share |
|---|---:|---:|---:|---:|
| 01_flat_2color_logo | 8,963 | 6,731 | 2,232 | 25% |
| 02_logo_fine_text_3color | 9,982 | 8,910 | 1,072 | 11% |
| 03_gradient_soft_subject | 11,180 | 8,763 | 2,417 | 22% |
| 04_thin_line_outline | 1,861 | 1,889 | −28 | −2% |
| 05_wordmark_caps | 1,844 | 1,814 | 30 | 2% |
| 06_wordmark_script | 1,763 | 1,583 | 180 | 10% |
| **07_circular_badge** | **35,077** | **18,259** | **16,818** | **48%** |
| 08_mascot_detail | 8,039 | 7,362 | 677 | 8% |
| 09_nonuniform_background | 4,029 | 3,371 | 658 | 16% |
| **10_low_contrast_subject** | **14,852** | **8,855** | **5,997** | **40%** |
| **TOTAL** | **97,590** | **67,537** | **30,053** | **31%** |

### The net figure, not the gross one

Removing travel is not free — the jumps it absorbed become trims. Measured on the badge:

| | stitches | trims | jumps | machine-min |
|---|---:|---:|---:|---:|
| with travel | 35,077 | 76 | 195 | **47.0** |
| without travel | 18,259 | 277 | 537 | **34.4** |
| net | −16,818 | **+201** | +342 | **−12.6 min** |

Even after paying 201 extra trims at 2.5 s each (+8.4 min), the badge is **12.6 machine-minutes
cheaper** without travel routing. So the saving is real, not an artefact of ignoring trim cost.

### The judgement you asked for

**No, the bench's absolute numbers are not defensible as production output for the badge.** 47
minutes for one 4-colour badge is roughly double what it should be, and 21 of those minutes are
thread sewn to avoid jumps.

**But neither extreme is right.** 277 trims on a single badge is its own defect — thread ends to
secure, operator intervention, trimmer wear. The honest reading is that `_route_travel` is
**correctly motivated and badly calibrated on hole-heavy geometry**: on a ring band it will walk
around a counter rather than jump across it, every single column transition.

STEP −1 already put a cost cap on this (`DETOUR_COST_MAX = 2.0`, chosen by sweep on fixture 01) and
a needle-safety pitch floor. Fixture 01 came down 25%. The badge shows the cap is tuned for the
wrong geometry: on a shape whose every detour is a hole rim, 2× the direct distance is almost always
"affordable", so the cap never bites.

**Satin 3 specifically:** ~4,300 stitches of actual satin column, 16,989 of travel. Neither 12,354
(digitize) nor 21,215 (regeneration) is defensible. A three-holed ring band of 1,555 mm² at 0.4 mm
pitch should cost on the order of 4–6k stitches plus a modest number of trims.

---

## 3e-i — status and one clarification needed

Not started, because 3e-ii and 3e-iii were "report before building" and their result changes what
3e-i is worth. It remains **correct to do** — one shared emission core removes the divergence *risk*
regardless of direction — and I will take it next unless you redirect.

**Clarification on the acceptance criterion.** You wrote *"hashes byte-identical on both paths for
all ten fixtures (as 3c achieved)"*. What 3c achieved was **before/after identity per path** — the
refactor changed neither path's output. It did **not** make digitize and rebuild byte-identical to
each other, and they cannot be: they differ by 0.97–1.38 across the corpus. I am reading your
criterion as the 3c one — *the refactor must not change either path's stream on any of the ten
fixtures* — and will verify it that way unless you meant something stronger.

---

## What I recommend, in priority order

1. **Re-calibrate travel routing on hole-heavy geometry** — the largest single quality and
   cost defect currently measurable, worth ~12.6 min/garment on the badge and 31% of corpus
   stitches. Needs a cost model that counts a hole-rim detour honestly rather than as "2× the
   chord", plus a trim-count ceiling so the cure is not 277 trims.
2. **3e-i**, the structural unification — cheap, direction-neutral, prevents recurrence.
3. **Contour fidelity / the path primitive** — still a real model gap, but **de-prioritised**: it is
   measured at 0.2% area error and ~1% of the gap it was invoked to explain.

Ratio-within-5% is recorded as a tracking indicator only, per your ruling. I note it will *not*
move much until item 1 lands, because travel routing dominates both paths.

**B2 proceeds in parallel**, with the three recorded constraints.
