# StitchIQ digitizing engine — consolidated engagement report

**One document, whole engagement.** Every prior report is folded in here in order, with later
corrections applied in place, so a reviewer never reads a claim that was subsequently retracted.
Where an earlier report said something now known to be false, this document says so and gives the
measurement that overturned it.

Repo `KevinD003/EmDesign_Automater` · single branch `main` · **29 commits** from `757ad0e` to
`f146938`.

| | |
|---|---|
| Product | AI embroidery digitizing — customer uploads an image, gets a machine-ready stitch file |
| Backend | FastAPI, `apps/backend`; the engine is `app/services/digitizer/` (16 modules, 7,669 lines) |
| Frontend | React/TS/Vite, `apps/frontend` |
| Toolchain, pinned | python 3.11 · `opencv-python-headless==5.0.0.93` · `numpy==2.4.6` |

---

## PART 0 — How to weigh anything in this document

Over this engagement, **nine candidate explanations were proposed and refuted by measurement.** Most
were the leading hypothesis of either the CTO or me at the time.

| # | hypothesis | whose | refuted by |
|---|---|---|---|
| 1 | contour fidelity explains the digitize/rebuild gap | both | 0.2% area error — ~1% of the gap |
| 2 | branch ordering causes the badge's travel | both | greedy reorder changed total travel by 0.0% |
| 3 | column sweep ordered on a bounding-box axis | CTO | zero jump-flagged transitions inside any branch |
| 4 | branch seams explain a 44 mm median | mine | seams measured 6.44 mm median |
| 5 | `_extend_branch_ends` skews the width statistic | mine | removing it moved the median 3.62 → 3.71 mm |
| 6 | `SATIN_MAX_UNCOVERED` is a blind scalar share | mine | the uncovered mask is measurably an edge rind |
| 7 | badge Satin 3 has letter-gap slivers that are genuinely satin | mine | three independent measures: no such population |
| 8 | fixture 08's density flag is a grid artefact | mine | grid-free measure says 23 → 26, a real 13% rise |
| 9 | 06's sub-floor jump was a lucky-draw artefact | mine | it swings ~5 points before *and* after the fix |

**#7 and #8 were asserted confidently and were wrong. #8 was refuted by an instrument I built
specifically to confirm it.** Treat every unverified claim here — including mine — accordingly.
Everything below is either measured with a reproduction command, or explicitly labelled unverified.

### This document was itself fact-checked, and it failed in six places

Six agents cross-checked every number here against the code, git history and the source reports.
**30 issues, 6 must-fix.** All are corrected in place above; the corrections are marked where they
sit. The two that a reviewer should note:

| what was wrong | why it matters |
|---|---|
| The annulus "before" figures (§2.6) came from a **reimplementation** of the old algorithm, not from running it — overstating the defect **3.3×** | The same wrong numbers had been reported to the CTO, committed to `CTO-1B-BOUSTROPHEDON.md`, and baked into a test docstring. Corrected in all three. |
| "The originals came from a scratch directory that no longer exists" | The directory exists and holds all three photographs. The conclusion (corpus unreproducible) was right; the stated cause was invented. |

Also corrected: badge 17,181 → **17,183**; a "59 mm counter diameter" that appears in no measurement;
13.3 px/mm presented as a constant when it is derived per upload; and every command in PART 7, which
was missing the `.venv/bin/python` prefix the scripts require.

**The lesson generalises beyond this document:** the gates in this repo catch regressions in code and
caught almost nothing about the *evidence* the reports rest on. A number that was never re-derived
from a running system is the least trustworthy artefact here, and there were several.

---

## PART 1 — What actually runs for a customer upload

`POST /api/digitize` → `digitize_image()` in `app/services/digitizer/pipeline.py` → the digitizer
package. **No test file executes for a customer upload** — verified by an import scan of all 62
`app/` files, a live upload trace, and the Docker image not containing `tests/`.

Package layering is enforced, with a 1,500-line-per-module gate:

```
constants → geometry → provenance → skeleton → columns → fills → satin →
underlay → generation → routing → planning → staging → pipeline → rebuild
```

Two paths must agree: **digitize** (pixels → objects → stitches) and **rebuild** (stored objects →
stitches, after a user edits density/angle). Ten argument divergences between them were found and
closed during this engagement; that is what STEP 0 and STEP 3c were about.

---

## PART 2 — The engagement in order

### 2.1 Governing verdict (`docs/CTO-VERDICT-2026-08-09.md`)

Ruled the architecture question **(c)** — one shared generation core, digitize and rebuild as thin
wrappers — and **inverted the ordering**: do not chase parity with digitize, because digitize was
itself the defect (44.4% of stitches under `MIN_STITCH_MM`, 21.3 machine-minutes against rebuild's
2.1% / 8.4 min).

### 2.2 STEP −1 → 3d (`docs/CTO-VERDICT-EXECUTION-REPORT.md`) — approved

| step | what |
|---|---|
| −1 | **the travel resampler's floor was 2 PIXELS, not 2 millimetres** — the root cause; added a cost cap and a needle-safety pitch floor |
| 0 | digitize and rebuild share the finishing parameters as functions, not as duplicated arithmetic |
| 1 | restored the parity signal the rebuild pass-through was answering for |
| 2 | a second CI lane with the pass-through disabled |
| 3a | **a fill was a property of where the object sat, not of the object** — `_scanline_angled` rotated about the canvas centre |
| 3b | rebuild works on the raster digitize actually used |
| 3c | one satin implementation, two callers (`generation.spine_satin`) |
| 3d | **re-pinning the stream lock now has to pass quality bands** — `STITCH_LOCK_WRITE=1` refuses a violating write |

3d is the load-bearing one for a reviewer: an exact hash catches *any* change but cannot tell a good
change from a bad one, and the moment of re-pinning is where the 2-pixel-floor regression got
blessed as a new baseline.

### 2.3 A measurement disagreement (`docs/CTO-RESPONSE-3E-AND-ATELIER.md`)

STEP 3e directed closing the digitize/rebuild gap by moving digitize **down** to rebuild's
behaviour. My measurements said regeneration was *more* expensive on eight of ten fixtures, and on
the badge by **+13,105 stitches and +16 machine-minutes** — opposite sign to the ruling. I stopped
rather than ship a 16-minute-per-garment regression.

The CTO retracted the direction, and set a standing policy, verbatim: *"Do not treat a CTO ruling as
settled when your measurements contradict it."* Exercised twice since; measurement won both times.

### 2.4 The real defect (`docs/CTO-3E-FINDINGS.md`)

**Travel routing was manufacturing 31% of all corpus stitches** — 30,053 of 97,590, 37.6
machine-minutes. On the badge, 48%. Contour fidelity, the hypothesis the ruling rested on, was
measured at 0.2% area error.

Net of trim cost, the badge was **47.0 machine-minutes with travel and 34.4 without** — so the
saving was real, not an artefact of ignoring the trims that replace travel.

### 2.5 Attribution (`docs/CTO-1A-EMISSION-ORDER.md`)

Reported *partial* rather than guessing: four candidate mechanisms refuted by measurement (rows 1–4
of Part 0), ~100 of 171 jumps still unattributed. The CTO completed it: on an annular component a
serpentine row splits into two runs and the fill connects them **straight across the counter**. The
measured jump median on badge Satin 3 was **42.31 mm** at the router call and 44.46 mm at the core
output; on a ring of this size that is the scale of a straight crossing, which is what identified the
mechanism. *(An earlier draft said "the 59 mm median was the counter diameter". No source records a
59 mm figure and the counter diameter was never measured; the identification rested on the 42–44 mm
median, not on a diameter.)*

### 2.6 The engagement's main win (`docs/CTO-1B-BOUSTROPHEDON.md`)

`_scanline_fill` walked every scan row and emitted each run back to back, so on an annulus it hopped
left-run → right-run across the hole once per row, and `_route_travel` sewed a detour around the rim
each time. Rows are now split into **monotone cells** at critical rows where the run count changes;
each cell is sewn to completion; cells are visited nearest-first.

Isolated on a 300 px annulus, **identical point count before and after — 2,149 — so the fix removes
no coverage; it is pure reordering:**

| | points | jumps | over 100 px | total jump distance |
|---|---:|---:|---:|---:|
| old | 2,149 | 44 | 24 | 3,968.1 px |
| new | 2,149 | 15 | **0** | **233.9 px** |

> **CORRECTED 2026-08-10 after fact-check.** The `old` row previously read 2,151 / 78 / 68 /
> 13,059.6 px, and the reduction was quoted as 98.2%. Those figures came from a REIMPLEMENTATION of
> the pre-1b algorithm rather than from running it: my probe toggled the serpentine direction per
> *segment* and skipped the `segs.sort()`, where the shipped code sorted and toggled per *row*. That
> manufactured extra long jumps and **overstated the defect by 3.3×**. The numbers above come from
> executing `fills.py` at commit `98ce364` (the last touch before 1b) against the same probe. True
> reduction in total jump distance is **−94.1%**, and hole crossings **24 → 0**. The fix, the
> mechanism and every pipeline-level number below are unaffected — those were measured by running the
> real pipeline before and after, not by reimplementation.

| | badge (07) |
|---|---|
| machine-minutes, net of trim | **47.0 → 22.65** (−52%) |
| stitches | 35,077 → 17,183 |
| trims | 76 → 28 |
| corpus digitize stitches | 97,590 → 65,004 (−33.4%) |
| coverage, all ten, both paths | 99.3–100%, none lost |

Independently reproduced by the CTO with a *different* coverage metric (0.4 mm @ 8 px/mm vs my
0.35 mm @ 6 px/mm): 17,162 st / 22.54 min / 100.0%.

**One of ten acceptance criteria missed and reported as missed:** router jumps 171 → 68, against a
target of 10–20. Travel now manufactures 155 stitches on that object instead of 16,989, so the
quantity the criterion proxied is down 99% — but 68 is not 20.

### 2.7 Classification (`docs/CTO-CLASSIFICATION-MECHANISM.md` — **carries a retraction**)

**The mechanism, which stands:** `median_w` is `np.median` over axis **samples**, so it weights each
unit of *axis length* equally rather than each unit of shape. Knocking lettering out of a band
multiplies axis length in that arc, so the lettered arc gets 2.4× the sampling density and outvotes
the plain arc. Badge Satin 3's band measures **6.98 mm with 96.7% of its circumference over the
4.5 mm cap**; the classifier judged **3.62 mm** and chose satin.

The control that isolates it: the concentric ring, same design, same raster, **no lettering** —
judged 5.26 mm against a true 5.51 mm, accurate to 5%, correctly rejected.

**What I got wrong.** I claimed the object contained letter-gap slivers that were "genuinely satin",
and that a scalar therefore could not describe it. Three independent measures (radial run-length
over 1,440 rays, exact local thickness, area distribution) agree: it is a single unbroken ~7.1 mm
ring over 82–84% of its circumference; **no ray has a largest run ≤3 mm**. That population does not
exist. I also reported 100% coverage on an object shipping **6.96% bare fabric** — my coverage
metric was too coarse to resolve a comb of radial slots.

**Ruled remedy, not started:** an area-over-cap satin veto in `generation.spine_satin`. Measured
separation is 0.000000 on all 13 correct satins vs 0.558–0.798 on all 4 misclassified.
**Acceptance is coverage, not machine-minutes** — machine time gets worse by design (corpus +7.5%,
badge ~22.6 → 25.1).

### 2.8 Determinism, part one (`docs/CTO-P1-PARITY.md`) — **written, evidenced, NOT on main**

`skeleton.py :: _thin_state` keyed thinning parity to absolute `(y + x)` under a comment insisting
the crop origin "MUST be added back". The goal was right, the means backwards: `_zhang_suen_thin`
walks parities in a fixed order, so a one-pixel shift swaps every pixel's checkerboard colour.

| | bars changing `stitch_type` on a one-pixel shift |
|---|---:|
| before | **13 of 24** |
| after | **0 of 24**, every median width identical |

100-image evidence: tier A real **clean**; tier B five object-count changes, all benign
(`B01_rotate` −63 objects, −2,081 stitches, −33 trims at unchanged coverage — spuriously split
objects merging); safety metrics unchanged corpus-wide.

**Why it is not on main — see PART 5.** It is a genuine trade-off, not a metric bug.

### 2.9 Widening the evidence base

Until this point **every headline number came from 10 synthetic fixtures**, while a 100-design
corpus and its runner sat unused in the tree. Both are now in the loop:

- `scripts/run_corpus100.py` — 100 designs, 0 errors, ~921 s
- `scripts/compare_corpus100.py` — diffs two runs **by provenance tier and refuses to blend them**.
  Tier C parametric regression is a note; tier A/B **fails and exits 1**.
- `scripts/measure_classification_width.py` — flags objects sewn as satin on a width they do not have
- `measure_stitch_quality.py :: _max_per_disc` — grid-free density

### 2.10 The 31 quality defects (`docs/QUALITY-DEFECTS-2026-08-10.md`)

41 agents across eight dimensions; every candidate re-checked by a second agent asked to **refute**
it, on two questions: is it real in the code, and does it affect a broad class of artwork rather than
one image. **31 confirmed, all 31 generalised.** Blocking items:

| id | defect | scope |
|---|---|---|
| **CP1** | colour plan non-deterministic — unseeded `cv2.kmeans` on a reused threadpool worker | all uploads — **FIXED, §2.11** |
| **DET3** | artwork deleted as "the garment" from the image's **border colour**, which is never an input; the deletion is subtracted from both loss bases so it cannot be reported | fires on 51–53/100 designs; 14 lose ≥20% of foreground silently |
| **SH2** | blend pixels get label −1, enter no region; the repair is gated behind a branch that never runs on flat art | 16.5% bare fabric on plain rectangles; 443 mm² largest hole at a 200 mm hoop |
| **SF1** | contour smoothing inert above 0.10 mm/px | 2 of 4 shipped hoop presets |
| **SZ1** | fill/satin pitch quantised to integer working pixels — density set by hoop and upload resolution, not the fabric profile | every fill and column |
| **SZ2** | min-feature gate switches itself off above a 166.7 mm hoop — **200×200 is a shipped preset** | all raster artwork |
| **UP1** | satin receives exactly **half** the per-side pull compensation a fill gets from the same stored number | every satin and fill object |
| **DIR1/3** | one scalar fill angle per object; direction field is zero over the interior of wide regions | curved and wide fills |
| **DET1/2** | sub-thread gate deletes regions on an estimate reading ~half true width; `emitted_mask` inflated so the loss warning under-reports | 95/100 designs over-credited, 42/100 by ≥2× |

Also confirmed: **DIR2 — the direction field is solved on every digitize and consumed by nothing.**

### 2.11 CP1 fixed — the same upload now gives the same design

Reproduced on four byte-identical uploads, one worker, RNG dirtied between each:

```
run 1   6 stops   8,694 stitches   b4c46a47c7ff
run 2   6 stops   8,755 stitches   14179697c718
run 3   6 stops   8,673 stitches   5d968f48523b
run 4   5 stops   8,486 stitches   4687cff58aff
```

Four different products from one file — including a different **number of threads to buy**. After:
`5 stops / 8,457 stitches / d6162e292ed3`, four times out of four.

**Why no test caught it, which is the more useful half.** Every bench script and quality test calls
`cv2.setRNGSeed(RNG_SEED)` *immediately before* `digitize_image`. The harness was supplying the
determinism the library owed — the whole suite was reproducible while production was not, and a test
that seeds before the call **structurally cannot observe this defect**. The new tests never seed and
actively dirty the RNG between runs.

The seed goes at the **top of `digitize_image`, before the image is decoded**, so no stage inherits
foreign randomness; a structural test asserts that ordering. `DIGITIZE_RNG_SEED = 20260728` is
deliberately the harness's own seed, so **all 14 stream locks pass with every committed hash
unchanged — no re-pin.** A fourth test fails loudly if the two constants ever diverge.

---

## PART 3 — The evidence base is weaker than its labels claim

The "100-design corpus" is **not** 100 designs of variety:

| labelled | actually |
|---|---|
| 13 "tier A real" | **3 photographs** + 10 copies of the synthetic bench fixtures |
| 40 "real-derived" | crops/rotations/recolours of *those same 3 photographs* |
| 47 "parametric" | 13 hard-coded shape classes → ~29 distinct layouts |

**There are 3 real photographs in the entire backend test suite.** A fourth committed file is a
pixel-identical duplicate. `build_corpus100.py` **cannot be re-run on a fresh checkout** — and the
reason is worse than a missing input. Its three source photographs live in an EPHEMERAL SESSION
SCRATCH DIRECTORY outside the repo, not in version control; and even with them present the script
hard-aborts (`C01_hairline_linework: only 0.000% of the canvas differs from the background`). The
corpus is therefore **unreproducible by anyone, including on the machine that built it**.
*(An earlier draft said the scratch directory no longer exists. It does, and still holds all three
files — the sources are pixel-identical to the committed A01/A02/A03. The conclusion holds; the
stated cause did not.)*

I repeated the corpus's own tier labels without opening them and told the owner "13 real". That was
wrong in the way that matters.

Scale gap worth internalising: the badge everything was tuned on is **17,183 stitches / 22 objects**;
the real peacock photograph is **42,449 stitches / 335 objects** (measured in the 2026-08-10
baseline run; that JSON lives in session scratch, not the repo, so a reviewer cannot re-check it
without re-running `run_corpus100.py`. The committed `scripts/corpus100-part48.json` records an
older run of the same design at 37,204 / 335).

---

## PART 4 — Current state

`main` is green. Working tree clean. `f146938` (CP1) is committed locally and **held from push until
both CI lanes finish** — pushing ahead of verification is exactly what put `main` red earlier today.

**Three stale remote branches remain.** All verified safe: two fully merged, the third's only unique
commit is a byte-identical duplicate of a file already on main. Two files exist on them and not on
main — `digitizer.py` (686 lines, superseded by the 7,669-line package) and `Dashboard.tsx`
(90 lines, superseded by `components/dash/`; its logic survives in `lib/dashboard.ts`). I cannot
delete them: the environment's git proxy blocks delete pushes and the GitHub MCP has no delete tool.
**Owner action:** github.com/KevinD003/EmDesign_Automater/branches.

---

## PART 5 — Open decisions a reviewer should rule on

**5.1 — The parity trade-off (blocking P1).** The fix removes a serious generalisation defect
(13/24 bars misclassify on a one-pixel shift) but raises peak local density **23 → 26, a real 13%**,
at one lock site on fixture 08. I first argued this was a grid artefact; the grid-free measure I
built to prove that says otherwise. Options: accept the trade with the evidence recorded; investigate
the new thinning's interaction with lock placement first; or leave it out. Recover with
`git revert --no-edit 01c2cb8`. **Unverified:** whether those penetrations are tie-off stitches — my
probe used a ±0.25 mm box and caught one stitch, so the metric's grid origin is not where I assumed.

**5.2 — 5c, a digitize/rebuild trim divergence.** Badge at the G4 configuration: before 1b both
paths ran 57 trims; after, digitize 19 and rebuild 25. Rebuild improved; 1b removed noise hiding a
6-trim gap. My proposed mechanism (digitize routes at 13.3 px/mm on the source, rebuild at 10 px/mm
on the bounding box) **is a hypothesis and is not measured.** Must not be quietly absorbed.

**5.3 — The area-over-cap veto.** Ruled, sequenced, not started. Acceptance is coverage, not machine
time.

**5.4 — Recorded, not acted on.** Professional judgement that 1.5 mm gold lettering should never be
knocked out of a navy band — sew the band solid and put lettering on top in the second colour,
because ±0.3 mm registration drift eats a 1.5 mm letter. A knockout-policy question upstream of
classification.

**5.5 — The standing dissent on the veto.** It separates perfectly on N=4 positives over ten
synthetic fixtures from one generator script, and this corpus contains **no legitimate wide satin by
design**. Real artwork will bring one. Log the statistic from day one and treat the first real-artwork
wide satin as a test of the rule, not a nuisance.

---

## PART 6 — Process failures, so a reviewer can discount appropriately

1. **Pushed before verification.** `5280abb` went to `main` ahead of the local run; both lanes then
   failed. `main` was red ~30 minutes. Reverted in `01c2cb8`. Now committing locally and holding.
2. **Measured on 10 images for the whole engagement** while a 100-image corpus sat unused.
3. **Repeated corpus tier labels without opening them** — reported "13 real" when it is 3.
4. **Set a quality band from a single reading** (06's 12% → 8%); the quantity swings ~5 points under
   a one-pixel source shift. The gate then correctly refused my re-pin.
5. **Shipped a comparer with three defects**, all found by running it for real: arithmetic on an
   N/A sentinel (a 101-point "coverage collapse", and `-1.0 → 0.0` reported as an *improvement*), a
   tolerance picked rather than measured, and object count not graded at all.
6. **Three times leaned toward explaining away a failing gate or measurement** (Part 0 rows 7, 8
   and 9); rows 8 and 9 were live gate failures. Every time, the measurement went the other way.
7. **Reported a headline number from a reimplementation rather than from running the code** — the
   annulus "before" figures in §2.6, overstated 3.3×. Caught by this document's own fact-check, not
   by any gate. It is the same error as an earlier one in this engagement, where I hand-wrote a
   criterion instead of importing it and produced a stricter rule than the original.
8. **`250e850` shipped formally-deferred work undisclosed**, and the Atelier frontend workstream was
   absent from a report. Owner-directed, but it belonged in the report regardless.

The gates caught 1 and 4. Item 5 was caught by running the tool for real, and item 7 by an
adversarial fact-check of this document. Nothing caught 2, 3 or 6. That distribution is itself the
finding: gates catch regressions in code, and catch almost nothing about the *evidence* a report
rests on.

---

## PART 7 — How to verify anything above

| what | command |
|---|---|
| ten-fixture bench | `.venv/bin/python scripts/run_quality_bench.py` |
| 100-image corpus | `.venv/bin/python scripts/run_corpus100.py --workers 3 --json out.json` (~15 min) |
| compare corpus runs | `.venv/bin/python scripts/compare_corpus100.py base.json cand.json` |
| classification widths | `.venv/bin/python scripts/measure_classification_width.py` |
| default lane | `pytest tests -q` (~14 min) |
| second lane | `STITCHIQ_NO_REBUILD_PASSTHROUGH=1 pytest tests -q` (~13 min) |
| stream locks | `STITCH_LOCK_WRITE=1 pytest tests/test_swarm_perf_lock.py -q` — refuses a band-violating re-pin |
| renders | `.venv/bin/python scripts/visual_regression.py [--update]` — SSIM gate 0.995 |
| determinism | `.venv/bin/python -m pytest tests/test_digitize_is_deterministic.py -q` |

All paths are relative to `apps/backend/`. The scripts are mode 644 with no shebang, so they must be
run through the venv interpreter — `scripts/foo.py` alone gives `Permission denied`.

**The digitize raster is not a constant.** `pipeline.py` derives it per upload:
`mm_per_px = min(hoop_w/iw, hoop_h/ih) * 0.9`, then divides by the granularity upscale (capped 2×)
and by any downscale to `_MAX_WORK_PX = 1200`. 13.3 px/mm is the figure **for the standard 640×640
bench fixtures at their bench hoops** — it is not a property of the engine, and it changes with hoop
and source size. Earlier reports quoted "~18 px/mm" read off constants (wrong) and then "13.3 px/mm"
as though universal (right value, wrong scope). SZ1 and SZ2 in the defect report are consequences of
exactly this derivation.

**When a real improvement lands, re-cut the quality bands.** The badge's band was 55 machine-minutes
against a 47 reading; at 22.65 that band would wave the entire pre-fix regression back through.

---

## PART 8 — Recommended next steps

1. **DET3** — make the garment colour an input rather than an inference from the image border, and
   report removed area instead of subtracting it from the loss metrics. Highest customer-visible
   impact of the remaining defects; fires on half the corpus.
2. **SH2** — make blend-pixel ownership depend on the transition's *width* rather than a ratio, or
   run the existing seam fill unconditionally. **Do not ship without re-deriving
   `TEXTURE_RETRY_UNCOVERED = 0.19`**, which was calibrated against the inflated `emitted_mask`.
3. **UP1** — reconcile satin and fill pull compensation; one of the two is wrong by 2×.
4. **Rule on 5.1** so the parity fix can land or be closed.
5. **Get real customer artwork.** Everything provable today rests on 3 photographs. A dozen real
   uploads would tell us more about production quality than any further work on the existing
   fixtures.

**Constraints in force:** one branch (`main`); no pull requests unless asked; `apps/backend/data/`
gitignored; **Ink/Stitch is GPL — concepts from public documentation only, never source**; every
change must generalise across colour, design, shape and size.
