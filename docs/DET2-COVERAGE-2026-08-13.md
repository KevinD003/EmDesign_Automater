# DET2 — coverage now counts thread, not intentions

**Status: landed.** One code change (`pipeline.py`), one shipped instrument
(`scripts/coverage_audit.py`), one test file. `TEXTURE_RETRY_UNCOVERED` was **not**
re-derived here, per the ruling's separation requirement — see §6 for what that now owes.

All numbers below: **ran the shipped code**, cotton, each fixture at its own bench hoop,
`cv2.setRNGSeed(20260728)`. Every figure in this document is reproducible with

```
apps/backend/.venv/bin/python scripts/coverage_audit.py --json out.json
```

and read from `out.json` at the JSON key named beside it.

---

## 1. The defect

`emitted_mask` is the only record of which artwork the pipeline believes it sewed. Two
consumers read it:

* `uncovered_px` — the pixel share of artwork no object covers. This is the gate the
  photographic-texture rescue fires on, and the only automatic detector of wholesale loss.
* `lost_share` — element-level, and the source of the user-facing *"About N% of the artwork
  is too small or too faint to sew"* warning.

The write sat in **pass A**, immediately after the minimum-area test:

```python
cv2.drawContours(emitted_mask, [contour], -1, 255, thickness=cv2.FILLED)
```

Pass A does not sew. It decides which regions are worth sewing. So the mask recorded an
intention, filled to the outer contour, and that stood in for an outcome. It over-counted
in two ways at once:

1. **Knocked-out holes.** `thickness=cv2.FILLED` on the top-level contour claims the letter
   counters, donut holes and ring interiors that the fill explicitly does not cross.
2. **Regions pass A accepted and pass B abandoned.** A feature thinner than the thread
   (`sub_thread_feature`), a generator returning fewer than two points, an empty fill —
   each `continue`s out of pass B leaving no object, and the mask still claimed the pixels.

Both errors push the same way. **A coverage metric that cannot go down is not a metric.**

## 2. The fix

The pass-A write is deleted. The mask is written once, in pass B, after the object exists:

```python
objects[-1].params_hash = object_params_hash(objects[-1])
emitted_mask[region > 0] = 255
```

`region` is the mask the generators were handed: the smoothed contour, minus every hole
that survived the knockout rules, plus any small hole the fill absorbed. Hole subtraction is
therefore not a second step — it is already true of the thing being recorded.

`region`, not `top_region`: pull compensation lays thread outside the region by design, and
crediting that against the artwork would reintroduce the same optimism in a smaller dose.

**Still not counted:** the dark-linework overlay, which emits objects after this loop. Those
are thin runs sewn on top of fills that are already marked, so their marginal coverage is
near zero — and the residual error is an *under*-estimate of coverage, which is the safe
direction for a loss detector. Named here rather than fixed, because fixing it means
deciding what footprint a 0.4 mm run claims, which is the physical-units question.

## 3. The falsifiable prediction, tested

> After the `emitted_mask` fix with hole subtraction, fixture 03_gradient_soft_subject's
> pipeline-reported `uncovered_px` MUST RISE from 0.00 % toward the 11.96 % that SH2-FINDINGS
> measured independently.

**03_gradient_soft_subject: 0.00 % → 13.32 %.** Prediction met. The corrected figure sits
1.36 points above SH2's independently-measured 11.96 %, which is the expected direction and
magnitude: SH2 measured *unowned* foreground (`labels == -1`), while this measures
*unsewn* foreground, and the two differ by the owned pixels that smoothing and the width
gate shave off every shape.

**Stop condition not triggered** — 03 did not stay at 0.00 %, and did not land below 2 %.

## 4. All fourteen fixtures

Ten bench fixtures plus the four corpus100 images SH2 measured, at SH2's configuration.

| fixture | conditions | before | after | delta | objects | stitches |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 01_flat_2color_logo | cotton @ 100×100 | 0.00 % | 0.34 % | +0.34 | 2 → 2 | 6,165 → 6,165 |
| 02_logo_fine_text_3color | cotton @ 130×180 | 0.11 % | 0.37 % | +0.26 | 16 → 16 | 8,437 → 8,437 |
| **03_gradient_soft_subject** | cotton @ 130×180 | **0.00 %** | **13.32 %** | **+13.32** | 4 → 4 | 8,399 → 8,399 |
| **04_thin_line_outline** | cotton @ 100×100 | **2.42 %** | **31.59 %** | **+29.17** | 10 → 10 | 1,855 → 1,855 |
| 05_wordmark_caps | cotton @ 130×180 | 0.95 % | 3.37 % | +2.42 | 6 → 6 | 1,802 → 1,802 |
| 06_wordmark_script | cotton @ 130×180 | 5.84 % | 9.46 % | +3.62 | 7 → 7 | 1,796 → 1,796 |
| 07_circular_badge | cotton @ 130×180 | 0.19 % | 3.33 % | +3.14 | 22 → 22 | 17,174 → 17,174 |
| 08_mascot_detail | cotton @ 130×180 | 0.66 % | 2.04 % | +1.38 | 20 → 20 | 8,024 → 8,024 |
| 09_nonuniform_background | cotton @ 130×180 | 0.00 % | 1.09 % | +1.09 | 2 → 2 | 3,090 → 3,090 |
| 10_low_contrast_subject | cotton @ 130×180 | 0.00 % | 0.66 % | +0.66 | 4 → 4 | 8,170 → 8,170 |
| C24_many_colours | cotton @ 130×180 | 12.53 % | 17.95 % | +5.42 | 26 → 26 | 19,784 → 19,784 |
| C11_many_colours | cotton @ 130×180 | 2.66 % | 6.94 % | +4.28 | 23 → 23 | 19,377 → 19,377 |
| C05_gradient_field | cotton @ 130×180 | 0.00 % | 0.10 % | +0.10 | 1 → 1 | 2,711 → 2,711 |
| C18_gradient_field | cotton @ 130×180 | 0.00 % | 0.10 % | +0.10 | 1 → 1 | 2,744 → 2,744 |

JSON key: `uncovered_px`, per row keyed by `fixture`.

**Stitch counts and object counts are identical on all fourteen.** The change is diagnostic
only — it moves no thread. That is the check that separates "the metric was wrong" from
"the pipeline was wrong": every delta above is a correction to what was *reported*.

**Every fixture moved up. None moved down.** That is what a one-directional over-count looks
like when it is removed, and it is the reason to distrust the direction of every coverage
figure quoted in this repo before today.

### A note on the corpus configuration

The four corpus images run at **`max_colors=4`**, which is SH2's setting, not
`run_corpus100.py`'s `max_colors=12`. The difference is not cosmetic: C24 reads **12.53 %**
at 4 colours and **1.05 %** at 12. Taking the corpus runner's default would have silently
replaced SH2's baseline with a different measurement under the same name. Confirmed by
reproducing SH2's 12.53 % and 2.66 % exactly before pinning the constant.

## 5. What the corrected mask surfaced

### 04_thin_line_outline loses a fifth of the drawing, and now says so

The fixture is a wheel: a thick outer ring, a thin inner ring, eight spokes and a hub. The
**inner ring measures 0.21 mm across** — under `MIN_FEATURE_W_MM` — so pass B correctly
refuses it:

```
{'seq': 11, 'region_median_w_mm': 0.21, 'skeleton_median_w_mm': 0.0,
 'uncovered_share': 1.0, 'reason': 'sub_thread_feature', 'decision': 'SKIPPED'}
```

**55.9 mm², 9,936 px, 20.00 % of the owned foreground, one connected component, zero
objects.** Rasterising the emitted stitch path at a 0.4 mm thread width puts **35 px of
thread inside it — 0.35 % of its area.** It is not partially sewn. It is not sewn.

Before this change the pipeline reported 2.42 % uncovered and **emitted no warning at all**.
It now reports 31.59 % and emits:

> About 20% of the artwork is too small or too faint to sew at this size and was left out.
> A larger hoop keeps more detail.

That warning is **true**, it is the correctly-worded advice for this failure, and it is new.
This is the first time the loss detector has caught a whole element on a bench fixture.

The refusal itself is correct — 0.21 mm cannot be sewn with 40wt thread — so nothing about
the *design* changes here. What changed is that the customer is told.

### 04 now crosses the photographic-rescue gate

`TEXTURE_RETRY_UNCOVERED` is 0.19. At 31.59 %, fixture 04 crosses it, its largest uncovered
chunk (55.9 mm²) clears `TEXTURE_RETRY_MIN_CHUNK_MM2` (50.0), and **the rescue now fires on
this fixture where it previously did not**. It is then rejected — the retry does not recover
0.19 of coverage — and the returned design is byte-identical, which is why the stitch count
above is unchanged. The cost is a second full digitize of the fixture, paid and discarded.

**One of fourteen crosses 0.19.** SH2 recorded "0 of 14 fixtures cross 0.19" under every rule
variant; that statement was made against the inflated mask and **is now false**.

## 6. What this owes

`TEXTURE_RETRY_UNCOVERED = 0.19` was derived against the inflated mask. Its comment cites a
0.228 worst case that no longer means what it meant. It is **deliberately unchanged in this
commit** — the ruling separated the mask fix from the re-derivation, and firing a smoothing
retry on a hairline drawing is the wrong response to a hairline drawing anyway, which is a
threshold question and not a mask question.

The re-derivation now has what it needs: fourteen honest before/after figures and a shipped
script that regenerates them.

## 7. Tests

`tests/test_det2_coverage_is_measured_after_sewing.py`, two tests:

1. **Behavioural** — digitizing 04 at bench configuration produces a `sub_thread_feature`
   SKIP, `uncovered_px >= 0.10`, and the too-small-or-too-faint warning. Asserted against a
   floor rather than the measured 31.59 %, so it does not become a tripwire for smoothing
   changes it is not about.
2. **Structural** — parses `pipeline.py` and asserts that *every* mutation of `emitted_mask`
   inside `digitize_image` lies within pass B's loop over the planned clusters. Deliberately
   an AST property, not a string match: this repo has already shipped one test that pinned a
   defect as contract by asserting on the literal source text of the line it guarded.

## 8. Fixture limits

Fourteen synthetic images, all cotton, at two hoop sizes. No photograph and no real artwork.
The two fixtures carrying the largest corrections (03's soft gradient, 04's hairlines) are
exactly the classes where real exports differ most from synthetic ones — real artwork carries
anti-aliased edges at the widths `MIN_FEATURE_W_MM` sits among. The direction of the
correction is not in doubt; its magnitude on real artwork is unmeasured.

## 9. Reproducing every number here

```
cd apps/backend
.venv/bin/python scripts/coverage_audit.py --json after.json            # §4 "after" column
.venv/bin/python scripts/coverage_audit.py --compare before.json        # §4 deltas
```

| number | command | key |
| --- | --- | --- |
| 03 uncovered, after | `coverage_audit.py --json out.json` | `[fixture=03_gradient_soft_subject].uncovered_px` |
| 04 uncovered, after | same | `[fixture=04_thin_line_outline].uncovered_px` |
| 04's new warning | same | `[fixture=04_thin_line_outline].warnings` |
| stitch counts | same | `[*].stitches` |
| conditions label | same | `[*].conditions` |

The "before" column is reproducible from a `git worktree` at `98ef7d6` with the same script.
