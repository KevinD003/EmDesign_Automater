# v2 Part 51 — R004-impl D2: tatami cannot consume this field, and here is why

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** D2 — tatami fills consume the direction field, with a confidence
fallback. Bar: beat **38.27°** on the photographed panel without losing coverage.

**Verdict: D2 was implemented, measured, and reverted. No engine change ships.**

It is not a close call, and the reason is not the one the brief anticipated. The
brief expected the open question to be *what to do where the field is undecided*.
The measurement says the fallback policy barely matters. Two other things decide
the outcome, and both are structural:

1. **The seed mask is most of the field's quality.** The field my wiring fed the
   generator scored **38.84°** on tatami territory. The field Part 50 validated
   scores **32.34°** on the same territory. Same solver, same panel — different
   boundary to diffuse from. My first result was a change that a **constant angle
   beat**, and that was my defect, not the field's.
2. **A straight row cannot use a field.** Even with the right field, collapsing it
   to one angle per region recovers **55%** of what the field is worth and throws
   away the rest. That ceiling is a property of scanline fills, not of thresholds.

And the bar itself could not have resolved this: tatami is **9.3%** of the panel's
area. Every tatami-only policy I measured — field, constant, random — lands within
**0.7°** on the whole-panel number.

---

## 1. What I built, and what it measured

`_field_fill_angle` in `fills.py` took the field's doubled-angle mean over each
tatami region and fell back to the region's principal axis below a coherence
threshold; `pipeline.py` solved the field once per design and passed it to the
tatami site. Threshold `FIELD_MIN_COHERENCE = 0.10`, chosen from a pre-wiring
sweep. All of it is reverted.

Wired, against the sew-out:

| | whole panel | tatami territory |
|---|---:|---:|
| current (region principal axis) | 38.27 | 40.09 |
| **D2 as wired, threshold 0.10** | **38.10** | **38.32** |

It cleared the bar. It should not have been merged on that, and the check that
stopped it was the one the brief asked for: measure where the change actually
landed.

## 2. The bench never consumed the field at all

Interior coverage, edge-band coverage, penetration floor and **stitch counts were
byte-identical on all ten fixtures**. That was suspicious enough to explain rather
than report, so I instrumented every tatami call site:

| | |
|---|---|
| tatami regions across the bench | 26 |
| regions that took the field | **0** |
| field coherence over those regions | median **0.0002**, max **0.0138** |

Alignment was checked before concluding anything — field and region masks are the
same shape with 100% overlap, so this is not a framing bug. Per-pixel coherence
inside a large flat region is **exactly zero**: boundary-seeded diffusion at 24
iterations reaches roughly a quarter of the way into a 1200 px mask, and the
middle of a 311,000 px region is never touched. Part 50 §5 predicted a washout
and measured committed share at 7–14% over the whole mask; at *region* granularity
on large fills it is not 7%, it is nil.

So on flat artwork D2 is not a small change. It is no change.

## 3. The control that killed the first result

The panel is the only non-circular reference, so it decides. I ran the policy
sweep against the wired engine, then the controls:

| policy on tatami regions | whole | tatami |
|---|---:|---:|
| random angle, mean of 4 seeds | 38.30 | 40.38 |
| current: region principal axis | 38.27 | 40.09 |
| constant 45° | 38.27 | 40.05 |
| D2 as wired (threshold 0.10) | 38.10 | 38.32 |
| **constant 90°** | **37.98** | **37.05** |

**A constant beat my direction field**, and the current principal axis performed
no better than a random angle. The panel has a dominant thread direction near
90°, so on this territory the metric rewards guessing the mode. Any policy a
constant also achieves is not evidence the field is being used — that control now
lives in the committed script.

The threshold sweep said the same thing a second way: the best point was **0.00**,
i.e. *ignore the confidence gate entirely*, and there was no knee anywhere. The
confidence fallback — the specific mechanism the brief asked for — was not
earning its place.

## 4. Why: I wired in a different field from the one Part 50 validated

The pre-wiring sweep predicted 35.59° on tatami and the wired engine delivered
38.32°. I first wrote that off as an over-optimistic offline model. **That was
wrong, and it is the correction that matters in this part** — the offline model
was right and the implementation was feeding the generator a worse field.

Part 50 solved on the union of the design's object contours. My wiring solved on
`fg_mask`, the segmentation foreground — one blob covering 52% of the frame,
whose boundary is the *silhouette of the subject*, not the boundaries of the
colour regions. Diffusing inward from a silhouette describes the outside of the
motif and says nothing about the shapes inside it.

Per pixel, on the same panel and territory:

| seed mask | whole | tatami | satin |
|---|---:|---:|---:|
| **union of every object contour** (Part 50) | **33.91** | **32.34** | **33.49** |
| per colour cluster, composited | 36.74 | 35.31 | 36.46 |
| `fg_mask` silhouette (what I wired) | 38.31 | 38.84 | — |

6.5° of field quality, lost to a choice of mask I made without measuring it. With
the right field the collapse does beat the constant control — 35.83 against 37.05
on tatami — so the mechanism was sound and the input was not.

## 5. The ceiling a scanline fill cannot reach

On tatami territory, with the correct field:

| | tatami |
|---|---:|
| current principal axis | 40.09 |
| field collapsed to one angle per region | 35.83 |
| **field per pixel** | **32.34** |

The field is worth **7.75°**; one angle per region captures **4.26°** of it, or
**55%**. The remaining 45% is unreachable while fill rows are straight, and no
threshold recovers it — a ring is the clean case, where the field runs all the way
round, the doubled-angle mean cancels to zero, and *no* single angle is even
approximately right. That is pinned by a test.

## 6. The blocker that stops a corrected D2 from shipping today

The winning seed is the union of every object contour. **That does not exist at
any point where a fill is generated** — object contours are produced inside the
cluster loop, one region at a time, after the field would have to be solved.

The seed that *is* available before fills — each colour cluster's own mask —
measures at 35.31 per pixel and **38.94 collapsed**, worse than the fg_mask
version it was meant to replace. So there is no drop-in correction. Consuming the
validated field needs `digitize_image` restructured into two passes: build all
region masks, solve, then generate. That is a materially larger change than this
brief scoped, and shipping the available-but-worse seed to look busy would be the
exact failure mode this part exists to report.

## 7. Cost

Not merged, so nothing is spent in the engine. For whoever builds the two-pass
version: one union solve on the panel is **0.06 s**; eighteen per-cluster solves
are **0.40 s**. Solve cost is flat in contour count — a 9× larger noise mask with
far more contours costs under 3× the time — which is the property that keeps the
Part 48/49 noise-multiplier hazard off this path. A test asserts that shape.

## 8. Gates

| Gate | Result |
|---|---|
| Backend suite | ✅ **874 passed, 2 xfailed** in 718.73 s (868 + 6 new) |
| Stream locks | ✅ 4 pass — no engine change |
| Visual baselines | ✅ 10/10 at SSIM ≥ 0.995 |
| `ruff check app` | ✅ 12, the standing baseline, unchanged |
| New script + tests lint | ✅ clean |
| Coverage / penetration floor | ✅ untouched; nothing ships |
| Honesty gate | ✅ see §2 and §3 — reported as a null result, not a win |
| Stop condition | ✅ **triggered**; D2 is not merged |

## 9. Files

- `apps/backend/scripts/measure_field_consumption.py` — ranks seed masks, measures
  the collapse cost, and runs the constant/random controls
- `apps/backend/tests/test_part51_field_consumption.py` — 6 tests pinning the ring
  cancellation, the doubled-angle mean, the seed-mask sensitivity and the cost bound
- `apps/backend/tests/fixtures/reference_sewout.jpg` — **the sew-out photograph, now
  in the repo.** Parts 46, 50 and 51 all headline against it and it existed only in
  an ephemeral uploads directory. Every direction number in this project was
  irreproducible from a fresh clone until this commit.

## 10. What this says about D3

The brief guessed satin was next because it is where the area is. The measurement
agrees for a second, stronger reason.

Satin is **93.7%** of the panel by area against tatami's 9.3%, and it carries the
same headroom: **37.90 → 33.49** per pixel. More importantly a satin column
already varies its angle along its length, so it can consume a field **without the
regional collapse that costs tatami 45% of the gain**. Satin is the generator this
field was always suited to.

Curved tatami rows — warping the scanline grid along the field — are the other
half, and they are a separate piece of work worth its own scoping, not a
continuation of D2.

Both need the two-pass restructure in §6 first. That is the next thing to build,
and it is a prerequisite, not an optimisation.
