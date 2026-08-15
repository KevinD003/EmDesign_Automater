# The A01/A02 promotion: parameters argued, census re-measured, three watch items answered

**Ruling of 2026-08-22, executed in order.** Nothing surfaced here is fixed in this tranche,
as ruled. Every headline number carries the command and the JSON key that reproduce it.

---

## 0. LEAD WITH THE REFUTATIONS

**R1 — `run_corpus100.py` has been measuring both photographs at a hoop the product does not
sell.** Its `BIG` set puts A01/A02 at `360x350`. The digitize dialog offers exactly four hoops
— `100x100`, `130x180`, `200x200`, `260x160`
(`apps/frontend/src/components/dialogs/DigitizeDialog.tsx:18`). Inheriting 360x350 was already
ruled out; the reason turns out to be stronger than "do not inherit". *Refutes my own opening
plan, which was to argue A02 up to a large-format hoop on garment-realism grounds.*

**R2 — the census did NOT change, and the expectation behind that prediction is refuted, not
the count.** The ruling expected count and band to move materially because "photographs are
where 0.20-0.23 mm stops being a tight band". Measured on the sixteen: **14 sub-thread
regions, 0.20-0.23 mm** — identical to the fourteen. The two photographs contribute **zero**,
and not narrowly (§3). Questioning the promotion as instructed produced a mechanism, not a
shrug: a photograph cannot reach `hairline_runs` at all.

**R3 — my max_colors-coupling hypothesis for the A02 substrate defect is refuted.** I
predicted the near-black cluster survives deletion because 6 colours pull its centre away from
black, and that 12 colours would fix it. Measured at four parameter blocks: the distance is
13.86 at 6 colours and **13.30 at 12** — still above `SUBSTRATE_DELTA = 12.0` at every block,
including the corpus runner's own `360x350` @ 12. The defect is not a promotion artefact.

**R4 — the phantom `COLOR_CHANGE` did not fire, and the standing statement's stated mechanism
was wrong.** It named dark garments as the class that leaves one. A dark garment cannot: the
dark-linework pass is skipped one guard earlier by `DARK_CLOTH_LUM = 60.0`, and A02's
substrate luminance is **0.0**. The class that can reach it is a *mid-tone* garment. Per the
ruling, the mechanism is corrected rather than the fixture (§5, watch item 3).

**R5 — a measured claim shipped in `pipeline.py` is now false.** The substrate rule's comment
says "measured on the black neckline panel, 2,925 stitches (5.1 % of all sewing) went into
near-black stops sitting **10.5** from the substrate". At the promoted parameters that
distance is **13.86**, and 4,638 penetrations (21.0 %) survive. Measured, not diagnosed: I
have not established when or why it moved. Second stale docstring number found this tranche
by the same mechanism as the first — a number measured once with no instrument to re-run it.

---

## 1. The parameters, argued (P0)

A photograph carries no scale. There is no ruler, no garment and no EXIF millimetre in either
file, so the physical size is **not recoverable — it is a choice**, and it travels with every
number below. `mm_per_px = min(hoop_w/iw, hoop_h/ih) * 0.9`, so the hoop *is* the scale.

Chosen from the four hoops the product sells (R1), on what a customer would actually order:

| | A01 peacock patch | A02 neckline plate |
| --- | --- | --- |
| source | 380 x 578 px | 474 x 695 px |
| **hoop** | **100x100** | **130x180** |
| frame at that hoop | 59.2 x 90.0 mm (2.33 x 3.54 in) | 110.5 x 162.0 mm (4.35 x 6.38 in) |
| **sewn extents** | 55.6 x 79.6 mm | 110.8 x 159.7 mm |
| reading | chest/shoulder patch; the modal patch order, and the product's own default hoop (`DigitizeDialog useState('100x100')`, `client.ts hoopSize = '100x100'`) | the 5x7 in hoop the neck-design market is sold in |
| **colours** | **6** | **6** |
| | the product default (`client.ts maxColors = 6`). NOT 4 — that is SH2's C-tier block, i.e. the inheritance the ruling forbids. NOT `PLAN_MAX_COLORS` (8) — a ceiling is not an order. | |
| **fabric** | **cotton** | **cotton** |
| | Held constant, with a reason rather than by inheritance: the realistic answers (twill for a patch backing, poplin for a kurta) are **not orderable** — the dialog offers cotton, polo/knit, denim, fleece, cap, towel. Decisively, fabric does not enter `mm_per_px`, so it cannot gate watch items 1 and 2, while changing it *would* confound "the first photographs in the set" with "the first non-cotton fixtures in the set". The realistic-fabric axis is left open and named. | |

**The pipeline's own sensor endorses one choice and rejects the other**, which is an
independent check rather than my judgement. `FINE_DETAIL_SRC_PX_PER_MM = 10.0`:

* A01 @ 100x100 reads **9.77** px/mm — no warning, **by 2.3 %**. Stated because it is narrow:
  100x100 is the smallest hoop at which the product considers this artwork's detail
  survivable, and a slightly larger source would flip it.
* A02 @ 100x100 reads **11.32** and the pipeline emits *"the image is 695px across but the
  design is only 61mm wide — fine detail may not survive at this size. Try a larger hoop."*
  A02 @ 130x180 reads 6.29, well clear.

The frame figures are arithmetic (`design_w_mm = iw * mm_per_px`, pre-rescale), corroborated
by the pipeline printing "only 61mm wide" for the case my arithmetic puts at 61.38 mm. Sewn
extents are smaller than the frame wherever the artwork does not reach the edge, and can
exceed it slightly where pull compensation dilates past it — A01 sews 55.6 x 79.6 mm inside a
59.2 x 90.0 mm frame; A02 sews 110.8 x 159.7 mm inside 110.5 x 162.0 mm.

Landed in `coverage_audit.A_TIER_PARAMS`, with the argument in the source, not only here.

### 1b. The one-off two-hoop observation, as ruled

One hoop each in the standing sixteen; this pair is reported, not committed.

| | A01 @ **100x100** | A01 @ 130x180 | A02 @ **130x180** | A02 @ 100x100 |
| --- | ---: | ---: | ---: | ---: |
| objects | 122 | 218 | 306 | 174 |
| penetrations | 5,453 | 15,058 | 22,079 | 8,519 |
| `RUNNING_SINGLE` | 36 | 61 | 0 | 0 |
| uncovered | 13.41 % | 10.40 % | 20.15 % | 20.93 % |
| minutes net of trim | 10.77 | 26.53 | 38.14 | 15.73 |
| sub-thread regions | 0 | 0 | 0 | 0 |

**How much the choice moves the answer: every quantity, by up to 2.8x — and not one verdict.**
A 1.8x linear hoop change moves A01's penetrations 2.76x and its machine time 2.46x. It moves
none of the three watch items: the census is empty at both hoops for both photos, watch item 2
fires on A01 at both and never on A02, and watch item 3 is unreachable at both. The invented
parameter is load-bearing for the numbers and not for the conclusions.

---

## 2. The promotion (P0) — what landed

| item | state |
| --- | --- |
| `coverage_audit.fixtures()` returns 16 in three declared tiers | **finished** |
| `A_TIER_PARAMS` with the argument in-source | **finished** |
| A01/A02 sha256-pinned; the guard now reads BOTH corpus tiers | **finished** |
| presence test renamed off the count; a new test asserts 16 = 10 + 4 + 2 | **finished** |
| two visual baselines, each examined by eye | **finished** |
| standing statement rewritten **in the promotion commit** | **finished** |
| `scripts/measure_hairline_census.py` — the census as an instrument | **finished** |
| `hairline_runs` docstring re-measured, and the "refused" predicate corrected | **finished** |
| branch coverage re-measured after the promotion | **untouched** — stated as such in the standing statement |

The enumeration of 2026-08-21 predicted the pinning gap exactly: the C-tier guard asserted
against `CORPUS_EXTRA` alone, so two newly-cited real photographs would have entered the
standing set **unpinned**.

All fourteen pre-existing visual baselines re-rendered at **SSIM 1.000000** and rewrote
byte-identical. The promotion moves no existing number.

---

## 3. The census, re-measured on the sixteen (P0)

    scripts/measure_hairline_census.py --json census.json
    keys: summary.sub_thread_regions, summary.run, summary.skipped_multi_branch,
          summary.width_min_mm, summary.width_max_mm

**14 sub-thread regions across 16 fixtures, 6 contributing any. 11 RUN, 3 SKIPPED (all
multi-branch), 0 skipped for want of a branch. Widths 0.20-0.23 mm.**

| fixture | regions | detail |
| --- | ---: | --- |
| 04_thin_line_outline | 1 | 0.21 mm, 1 branch, RUN |
| 07_circular_badge | 1 | 0.20 mm, **3 branches, SKIPPED** |
| 08_mascot_detail | 1 | 0.20 mm, 1 branch, RUN |
| 09_nonuniform_background | 1 | 0.20 mm, **6 branches, SKIPPED** (the verified-noise region) |
| C24_many_colours | 5 | 0.23 mm each, 1 branch, all RUN |
| C11_many_colours | 5 | 0.23 mm each; four RUN, **one 4-branch SKIPPED** |
| **A01, A02** | **0** | — |
| the other eight | 0 | — |

Count unchanged (14 → 14). Band unchanged (0.20-0.23 → 0.20-0.23). **The re-measure was still
worth it**, and this is the part a reword would have missed:

1. **The old sentence's predicate was wrong.** It called all 14 "refused". Eleven are sewn.
   A number can stay right while its verb goes stale, and only the boundary's arrival made the
   verb wrong — which is exactly why re-measuring beats re-reading.
2. **The census is now decomposed** — 11 / 3 / 0 rather than one total — so a future noise
   criterion has a named target: the 3 multi-branch refusals, not "the 14".
3. **There is now an instrument.** The claim it replaces was taken once, by hand, in a
   scratchpad that no longer exists, and could not survive the boundary that changed its
   meaning.

### Questioning the promotion, as instructed

> *"I expect both to change materially ... and if they do not, question the promotion before
> you believe the number."*

They did not. The question resolves to a **structural** answer, not a doubt about the
promotion:

* the photographs' narrowest classified regions are **0.34 mm** (A01) and **0.38 mm** (A02),
  with **none under 0.30 mm**, against `MIN_FEATURE_W_MM = 0.25`. Not a knife edge — 36 % and
  52 % clear.
* the two C-tier images that do reach the function carry **five regions apiece at 0.23 mm**.
* the discriminating variable is the textured path, which only a photograph takes:
  `_interior_texture` reads **7.43** (A01) and **10.20** (A02) against `TEXTURE_SMOOTH_MIN =
  6.0`, while every flat fixture reads 0.00-4.10. That path mean-shift-filters the image and
  then closes each cluster mask at 0.4 mm and opens it at 0.3 mm.

**Stated precisely, because the obvious arithmetic is wrong**: a 0.3 mm-radius open would
predict a floor near 0.6 mm and the measured floors are 0.34/0.38 mm. The morphology is the
cause of the empty census; it does not by itself set the floor (the close runs first and can
fuse a sliver into a neighbour, and the reported width is a region's median). **The emptiness
is measured; the mechanism is inferred.** No photographic width floor is claimed.

**The consequence stands either way: RS1's 0.20-0.23 mm band describes flat hard-edged
artwork, not "the corpus", and no further photograph can widen it.** The input that would is a
flat-lit scan scoring under 6.0 — that is a concrete thing to ask a customer for.

---

## 4. What the promoted photographs measure

    scripts/coverage_audit.py --json audit.json      keys: rows[].uncovered_px, rows[].objects
    scripts/trace.py A01_real_peacock_patch_photo --key design.penetrations
    scripts/trace.py A02_real_neckline_black --key machine.minutes_net_of_trim

| | A01 @ cotton 100x100, 6 col | A02 @ cotton 130x180, 6 col |
| --- | ---: | ---: |
| objects | 122 | 306 |
| penetrations | 5,453 | 22,079 |
| colour stops | 13 | 13 |
| `SATIN` / `TATAMI` / `RUNNING_SINGLE` | 66 / 20 / **36** | 233 / 73 / **0** |
| uncovered | **13.41 %** | **20.15 %** |
| minutes net of trim | 10.77 | 38.14 |

**A02's 20.15 % is the highest uncovered share in the standing set** (C24 17.75 %, C11 6.83 %).
And the rescue that exists for it cannot fire: `TEXTURE_RETRY` is guarded on `not
is_textured`, so the three highest-uncovered fixtures are structurally outside it. That is
coherent by design — the retry exists for *undetected* texture — but it means the worst
coverage number in the set has no automatic response at all.

---

## 5. The three watch items

### Watch item 1 — noise-sewing, first class. **Answered: no.**

Both renders were generated and **looked at** (`tests/visual/baselines/A01…png`,
`…/A02…png`), and the question is also settled by measurement: `hairline_runs` was called
**zero** times on either photograph, so no single-branch region exists in either, in a noise
area or anywhere. The noise criterion does **not** become P0 on this evidence.

The honest limit: this is not evidence that the proxy is safe. It is evidence that the proxy
is **unreachable** on this input class, which is a weaker statement and a different one. The
boundary remains a proxy, not a detector.

What looking *did* find, on A02, is §6.

**All sixteen renders were looked at**, not only the two new ones — the ten bench baselines
here, the four C-tier ones when they first gained baselines at `9c55766`. Recorded because
"look at all sixteen" is only satisfied by doing it:

* **09 is clean.** The three stray dashes 24 mm from the design are gone; the single-branch
  boundary holds visually on the fixture that motivated it.
* **08** carries one small detached hook at the far left edge — its RS1 run object, previously
  verified as ink by exact source-colour match (`#30221e`), not noise.
* **07** has one dark speck inside the cream field. It is *not* RS1 — 07's only sub-thread
  region is a 3-branch SKIPPED one — so it is an ordinary small object, and it is thread on
  bare cloth. Pre-existing; noted, not fixed.
* Visible degradation, all pre-existing and out of scope here: 07's arc text
  ("ESTABLISHED 1962") is broken into fragments on its right side; 03 shows white pinholes
  along the seam between its two concentric fills; 05's satin column ends are irregular.
* Nothing else in the ten sews thread onto bare substrate.

### Watch item 2 — `RUNNING_SINGLE` at volume. **Fires, on A01.**

**36 of 122 objects (29.5 %)** are `RUNNING_SINGLE`, from the dark-linework pass — the same
order of magnitude as the angelfish record's 55 of 100, on our own output, for the first time.
At the second hoop, 61 of 218 (28.0 %): the share is stable, so it is a property of the
artwork, not of the scale. The one-penetration-per-run-object rebuild defect (fixed `ce254a8`,
pinned only by constructed objects) now has a fixture that would notice.

A02 emits **zero**, and the reason is measured: its substrate luminance is **0.0** against
`DARK_CLOTH_LUM = 60.0`, so the linework pass never runs on it.

### Watch item 3 — the phantom `COLOR_CHANGE`. **Not reached. The mechanism is wrong, not the fixture.**

All seven accounting identities pass on both photographs — **112 assertions collected**
(`pytest tests/test_stream_accounting.py --collect-only -q`, 7 x 16), up from 98.
`stops_partition_matches` is still never exercised false by a fixture.

Per the ruling — say the mechanism or the fixture class is wrong rather than adjusting the
fixture — **the mechanism as written is wrong**. The standing statement named dark garments.
The phantom needs the dark-linework pass to run and *then* be suppressed by the "darkest
thread IS the cloth" check. On a dark garment the pass is skipped one guard earlier
(`substrate_lum >= DARK_CLOTH_LUM`, 0.0 vs 60.0), so `chains` is empty, `if chains:` is false,
and the extra stop is never opened. The reachable class is a **mid-tone** garment — light
enough to clear 60.0 luminance, with its darkest thread inside `SUBSTRATE_DELTA` of the cloth.
The corpus contains none, and A02 could never have been it. The standing statement has been
corrected to say so.

---

## 6. What the promotion surfaced. Classified, not fixed.

### 6a. A02 sews 5.80 machine-minutes of invisible thread, every garment

Priced in the currency the business runs on, per the ruling of 2026-08-23 — "21 % of
penetrations" is a share, and a share is not a decision:

> **4,638 penetrations ÷ 800 spm = 5.80 machine-minutes per garment, spent sewing black
> thread onto black cloth**, on a design that takes 38.14 minutes end to end. Fifteen per
> cent of the run time. Invisible thread, real thread cost, real needle wear, real machine
> time — and it is the first defect in this engagement that converts directly into money.
> The promotion found it on its first real photograph.

    scripts/trace.py A02_real_neckline_black --key machine.minutes_net_of_trim   # 38.14
    4638 / SPM (800.0, run_quality_bench.py:52) = 5.7975 min

**4,638 of 22,079 penetrations (21.0 %) are `#080808` thread on a substrate the pipeline
inferred as pure black (BGR 0,0,0).** The cluster sits **13.856** from the substrate against
`SUBSTRATE_DELTA = 12.0` — analytically exact, `sqrt(3 x 8^2)` — so it misses deletion by
**1.86, or 15.5 %**. Visible in the baseline render as black fragments in the pockets between
flowers. At the corpus runner's own block the same defect is 10,706 penetrations =
**13.38 minutes**; at 100x100 it is 1,179 = **1.47 minutes**. It is never zero.

Classification: **the gate is wrong, and the fourteen were not hiding it — the parameters
never were.** Measured at four blocks:

| conditions | penetrations near substrate | share | closest surviving stop |
| --- | ---: | ---: | --- |
| 130x180, 6 col (**promoted**) | 4,638 / 22,079 | 21.0 % | `#080808` @ 13.86 |
| 130x180, 12 col | 4,500 / 21,932 | 20.5 % | `#080708` @ 13.30 |
| 360x350, 12 col (**corpus runner's own**) | 10,706 / 58,369 | 18.3 % | `#080708` @ 13.30 |
| 100x100, 6 col | 1,179 / 8,519 | 13.8 % | `#080808` @ 13.86 |

So the corpus runner has been producing this every run, and nothing looked, because A02 had no
render until this commit. The shipped comment claims the same stops sat at 10.5 (R5) —
under the gate, deleted. Measured, not diagnosed: I have not established what moved it.

Not fixed here, and the fix is not obvious in the right way: raising `SUBSTRATE_DELTA` past
13.9 is a constant fitted to one fixture, which is the move this repository keeps punishing.

### 6b. `SUBSTRATE_DELTA` has never been re-derived against the sixteen

Standing rule: when the field changes, list every calibrated constant evaluated against it and
say per constant whether it was re-derived or carried over. The promotion changed the fixture
set. The constants that read the substrate are:

| constant | value | status against the sixteen |
| --- | ---: | --- |
| `SUBSTRATE_DELTA` | 12.0 | **carried over** — fitted pre-promotion; §6a is it failing on a promoted fixture |
| `DARK_CLOTH_LUM` | 60.0 | **carried over** — A01 255.0 / A02 0.0, both far from it; no evidence either way |
| `TEXTURE_SMOOTH_MIN` | 6.0 | **carried over, and now supported** — flat 0.00-4.10, photographs 7.43/10.20; the promotion is the first real-photograph evidence for it |
| `FINE_DETAIL_SRC_PX_PER_MM` | 10.0 | **carried over** — A01 9.77, A02 11.32/6.29; it discriminates the two hoop choices, which is corroboration, not derivation |
| `MIN_FEATURE_W_MM` | 0.25 | **carried over, and unreachable** on photographs (§3) |
| `TEXTURE_RETRY_UNCOVERED` | — | **carried over, and inert on this class** by the `not is_textured` guard (§4) |

*A constant carried across a set change is a new constant with an old number on it.* Six are
carried. One is now measurably wrong on a member of the set.

---

## 7. Instrument work landed alongside

* `scripts/measure_hairline_census.py` — the census, re-runnable, reading the pipeline's own
  classification log and `hairline_runs`' own branch count. It **refuses** to emit if the two
  lists disagree in length, rather than assembling a row from two traversals.
* `generation._LAST_HAIRLINE_BRANCHES` — appended on **every** exit path of `hairline_runs`,
  including the empty-skeleton early return. The first draft appended only on the main path,
  which would have given a region the *previous* region's branch count under its own name:
  the C11 splice at a smaller scale, caught before it shipped.
* Snapshot/restore of that list alongside `_CLASSIFICATION_LOG` in the texture-retry branch,
  for the same reason the accounting census already had to be.

---

## 8. Verification

**CI run 31825862834** (`ci.yml` run number 127) on `1914ffa`: `status: completed`,
**`conclusion: success`** — read from the GitHub API (`get_workflow_run` /
`list_workflow_runs`), not from a local pytest line, because "CI green" is a headline number
and has to carry its run ID and conclusion like any other. Both jobs green:

| job | steps |
| --- | --- |
| `frontend` | typecheck, vitest, build — success |
| `backend` | `pytest tests -q` success (18:03); `STITCHIQ_NO_REBUILD_PASSTHROUGH=1 pytest tests -q` success (16:43); `verify_lint_claim.py` success |

Locally, for the record and NOT as the CI claim: default lane `1415 passed, 2 skipped,
2 deselected, 3 xfailed` (24:17, exit 0); passthrough lane `1409 passed, 8 skipped,
2 deselected, 3 xfailed` (24:49, exit 0).

**Sequencing, stated because it is not my usual order**: the push happened while the local
passthrough lane was still running. The default lane was fully green and the 146 set-sensitive
tests had passed before it, but the second lane had not finished at push time. It and CI both
came back green; had either not, the fix would have been mine and immediate.

## 9. Unchanged, and still the highest-value input

Nothing has been sewn. Two photographs of finished embroidery are not a sew-out. The
real-job-pairs intake spec is open and empty, and remains the highest-value thing anyone could
hand this project.
