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

---

# APPENDIX A — the 31 generalised quality defects, in full

*Source document: `docs/QUALITY-DEFECTS-2026-08-10.md`, reproduced here so this report is
self-contained. Produced by 41 agents across eight quality dimensions; every candidate defect was
independently re-checked by a second agent asked to REFUTE it, on two separate questions — is it
real in the code, and does it affect a broad class of artwork rather than one image. 31 confirmed,
all 31 generalised.*

*Licence constraint observed throughout: Ink/Stitch and other GPL software were not read or
consulted as source. Reasoning is from public documentation and embroidery craft only.*

Source: 31 confirmed defects (`verdict.real === true`) across 8 dimensions. Every one returned `verdict.generalised === true`. Nothing below is speculative — each row was reproduced against the shipped code.

---

### 1. All confirmed defects

| ID | Dimension | Defect | Artwork class affected | Severity | Generalised |
|---|---|---|---|---|---|
| CP1 | colour-palette | Colour plan non-deterministic — unseeded `cv2.kmeans` draws from OpenCV's thread-local RNG, which persists across requests on reused FastAPI worker threads | Palette/stop-count drift on multi-optimum art (photos, gradients, shaded mascots, many-colour flat); stitch-count drift on **all** art incl. flat | blocking | yes |
| CP2 | colour-palette | No thread-catalogue snapping in the digitize path; raw k-means centroids emitted as `thread_brand="Auto"`, `catalog_number=""` | All designs, unconditional | major | yes |
| CP3 | colour-palette | Area-weighted k-means lets shading absorb the colour budget; no slot reserved per perceptually-distinct hue; all planner distances are BGR Euclidean | Shaded/gradient region + flat accents. Worst on smooth-shaded flat art (fails the `is_textured` gate, so gets neither mean-shift nor bimodal split) | major | yes |
| CP4 | colour-palette | `PLAN_MAX_COLORS=8` caps every request at its only consumption point; the "requests above 8 are inert" justification is circular (swept through the already-capped entry point) | All. Lifting to 12 changes 43/60 corpus designs; all 3 tier-A photos gain 3–4 threads | major | yes |
| SH1 | shading-gradients | No graduated density, no stitch-length modulation, no feathered row ends; pitch constant within every region; `GRADIENT_BLEND` is a removed enum mapped to plain `TATAMI` | Every design (limitation lives in all five generator signatures) | blocking | yes |
| SH2 | shading-gradients | Ambiguous-blend cut strands 15–17% of foreground at label −1; the Part 29 seam-fill repair is gated on `is_textured` so never runs on the path that creates the damage | Flat-art path: soft ramps **and** flat art holding a colour midway between two centres. 33 of 109 corpus images >2% unowned | blocking | yes |
| SH3 | shading-gradients | No interdigitation between adjacent colours — labels are a one-owner-per-pixel partition; total cross-colour overlap ≤0.6–0.8 mm, uniform | Every multi-colour design; visible on shaded/gradient art | major | yes |
| SF1 | shape-fidelity | Contour smoothing inert above 0.10 mm/px — DP tolerance falls sub-pixel and Chaikin's output is rounded back onto the integer grid (identity + duplicate vertices) | Any design >~120 mm long side (2 of 4 shipped hoop presets), or any source <450 px at any hoop | blocking | yes |
| SF2 | shape-fidelity | Geometric resolution pinned to a fixed 1200 px raster; mm/px is a function of hoop alone, source detail cancels out | All artwork; error ∝ physical size (0.075 mm/px at 100 mm → 0.30 at 400 mm) | major | yes |
| SF3 | shape-fidelity | No curve representation anywhere — `contour` is an integer-pixel polyline; SVG is rasterised at 1200 px and re-traced with `findContours` | All vector uploads, all lettering (PIL glyph bitmaps at 160 px), all raster | major | yes |
| SF4 | shape-fidelity | Fill satin border paces on the centre line with no corner treatment; floor gate `continue`s the whole station when either rim is tight | Every fill ≥30 mm² and every kept hole; curved and cornered outlines | major | yes |
| SZ1 | size-scaling | Fill and satin pitch quantized to integer working pixels — sewn density set by hoop size and upload resolution, not the fabric profile | Every tatami fill and satin column in every design | blocking | yes |
| SZ2 | size-scaling | Sub-thread min-feature gate switches itself off above a computable hoop (166.7 mm at 1200 px canvas — **200×200 is a shipped preset**), because the DT width estimate is floored at 2×mm_per_px | All raster artwork with anti-aliased edges; fails in *both* directions across the crossover | blocking | yes |
| SZ3 | size-scaling | Contour fill sews at `row_px − 1` px — a fixed 1 px correction on a pitch only a few pixels wide; up to 2.0× over-dense | Rings, annuli, badge borders, square frames, letter bowls/counters | major | yes |
| SZ4 | size-scaling | Pull compensation rounded to whole pixels and returns the region untouched at `px ≤ 0` | Every tatami/contour/spiral/radial fill (not satin columns) | major | yes |
| UP1 | underlay-pull | Satin receives exactly **half** the per-side pull compensation a fill receives from the same stored number (`pull_mm/2` vs `pull_mm`) | Every satin object and every fill object in every design | blocking | yes |
| UP2 | underlay-pull | Pull comp never reaches the visible edge of a bordered fill — the satin border is built from the **undilated** contour and its outer lip sits at a fixed +0.6 mm | Every fill ≥30 mm²; the entire supported pull range (≤0.5 mm) is hidden inside the border | not stated (treat as major) | yes |
| UP3 | underlay-pull | Pull comp and both underlay insets use a **square** structuring element — L∞ dilation delivers `px` on axes, `px·√2` on diagonals | Every object with non-axis-aligned boundaries: curves, diagonals, rotated glyphs, circular badges | major | yes |
| UP4 | underlay-pull | Pull comp quantized to whole pixels, so its real value is a function of hoop and source resolution; can round to zero silently while the object still reports the nominal value | Every fill object. −25%…+30% across the four shipped hoops; zero for any sub-400 px upload at 200×200 | major | yes |
| DIR1 | stitch-direction | Every automatic tatami fill is one scalar angle per object; on a constant-curvature arc the error is exactly sweep/4 and no scalar can beat it | Curved regions too wide for satin and without a hole: leaves, petals, paisley bodies, wide banners, large C/S/G/J bowls. 40/40 corpus fill objects took the scalar path | blocking | yes |
| DIR2 | stitch-direction | Direction field solved on every digitize and consumed by nothing; only reader is a test/script diagnostic | Every digitize (~1% CPU, 14.4 MB pinned per run); absent capability affects all curved artwork | major | yes |
| DIR3 | stitch-direction | Boundary-seeded diffusion reaches ~12 work-px of usable coherence; field is bitwise zero over the interior of any wide region | Wide-area fills — backgrounds, garment bodies, large colour blocks. ~10/93 corpus images severely affected | blocking | yes |
| DIR4 | stitch-direction | `theta`/`sample()` return exactly 0 rad where the field is undefined — indistinguishable from a genuine horizontal answer; no sentinel, no NaN | Latent (no consumer yet). Worst on the largest regions: 35% of a big-flat-area fixture's foreground | major | yes |
| DET1 | small-detail-loss | Sub-thread gate deletes whole regions on a DT-median estimate that reads ~half the true stroke width; the same package already avoids this estimator for the satin cap | Hairline linework, keylines, thin borders, script and small lettering, ring/annulus outlines, lattice. Effective floor is 0.30–0.55 mm, non-monotone in hoop | blocking | yes |
| DET2 | small-detail-loss | `emitted_mask` is written in pass A, filled with no hole subtraction, before pass B discards anything — so the loss warning and the photographic rescue both read an inflated mask | Artwork with knockouts (rings, frames, badges, counters) and artwork with sub-thread strokes. 95/100 corpus designs over-credited, 42/100 by ≥2× | blocking | yes |
| DET3 | small-detail-loss | Artwork deleted as "the garment" on the basis of the **image border colour**, which is never an input; erased pixels are subtracted from both loss bases so it cannot be reported | White/light-ink artwork, knockout/reverse logos, and every transparent PNG (alpha is composited onto white, forcing a white substrate). Fires on 51–53/100 corpus designs | blocking | yes |
| DET4 | small-detail-loss | `MIN_REGION_MM2 = 2.0` hard physical cliff (a 1.6 mm dot); `dropped_speck_count` never read, `_DROP_LOG` has no consumer, and the loss counter structurally skips anything below the same threshold | Stipple/halftone, scattered ornament, punctuation and i-dots, freckles, catchlights, small counters, registration ticks | major | yes |
| CB1 | competitor-baseline | Element-level content-loss detector runs connected components over the **union of all colours**, so any element touching a sewn neighbour of any colour scores as covered; second condition skips sub-`min_area_px` components | Every design whose foreground is one connected blob — badges, logos on a filled ground, all photographs. 15/30 corpus designs had one component ≥90% of the mask | major | yes |
| CB2 | competitor-baseline | `max_colors` bounds nothing downstream (three stages add stops above k); raising the request re-quantizes and can silently delete artwork — reachable inside the UI's own 2–8 range | All classes. 38/100 exceed the stop bound at the default request of 6; objects drop on 22/100 going 6→10 | major | yes |
| CB3 | competitor-baseline | Non-adjacent colour stops mounting the same thread never merged and never made adjacent; no dependency-aware sequencing pass exists | Multi-region artwork; worst on photographic/textured. 22 duplicate stops across 6 of 13 A-tier designs | major | yes |
| CB4 | competitor-baseline | Fragmentation → trim time: one object per connected component, `_route_travel` is intra-object only, `connect_method` hard-coded `TRIM`, no same-colour merge stage | Photographic/scanned/textured raster **only** — explicitly not flat vector art. 35–56% of run time is machine stops on real photos | major | yes (within class) |

Note: **SZ4 and UP4 are the same code line** (`geometry.py:110`), found independently from two dimensions. Fix once.

---

### 2. Top 5 by (impact on perceived quality) × (breadth)

Each item is anchored on one defect and names the siblings that **must move in the same change** or the fix regresses something else.

---

### #1 — DET3: artwork is deleted as "the garment" based on the image's border colour
*Siblings: DET2 (the deletion is subtracted from both loss bases so nothing can report it), CB1.*

**Mechanism.** `substrate = _border_color(img)` — the median of the image's four edges. Any k-means cluster within `SUBSTRATE_DELTA = 12` BGR of it is erased: unconditionally if any component touches background, otherwise at ≥5% of foreground or ≥40 mm² (a 6.3×6.3 mm element). Erased pixels go into `substrate_owned`, which is ANDed out of both `owned` (the loss metric) and `art_base` (the photographic rescue), so the deletion is invisible to every warning channel by construction. `digitize_image` and `/api/digitize` have **no garment-colour parameter at all**. And `_decode_image_bgr` composites alpha as `img*α + 255*(1−α)`, so every transparent PNG — the docstring's own "single most common real digitizing input" — forces a pure white substrate that the customer cannot avoid or override.

**Why it looks worse than commercial output.** Controlled A/B, identical geometry, page colour the only variable: a white knockout square on a white page is kept at 39.7 mm² and **deleted at 81 mm² and above**; the same images on a grey page keep it at every size up to 506 mm². A 15×15 mm white knockout comes back with the white element gone, one colour stop instead of two, and the only warnings are a resolution notice and *"the artwork only separated into 1 distinguishable colour"* — which is false, and blames the artwork. Corpus-wide: fires on 51–53 of 100 designs, 135,000–193,000 mm² removed, 14 designs lose ≥20% of their foreground with no warning at all. Commercial software asks for the garment colour explicitly and shows you the knockout; here the artboard background silently decides what gets sewn.

**Generalised fix.**
1. Make the assumption an **input**: add an optional `substrate_hex` to `digitize_image` and the `/digitize` form, defaulting to the inferred border colour. Surface it in the UI next to fabric.
2. Make it a **statement**: whenever the rule removes area, emit a warning carrying the mm² and the assumed colour. The data is already in `substrate_px`; it is written to `plan` and never read.
3. Stop hiding it from the metrics: report substrate-removed pixels as a **separate channel** rather than subtracting them from both loss bases, so "left bare on purpose" and "lost" are two numbers.
4. For alpha input, infer the substrate from the alpha-declared foreground only — or treat a fully transparent border as *unknown substrate* and disable the rule entirely, as the SVG path already does (`svg_mask is None` gate).

---

### #2 — SH2: the ambiguous-blend cut leaves unowned bare-fabric moats
*Siblings: DET2 (the rescue that could catch this reads the inflated `emitted_mask`), SH3 (no interdigitation, so the seam is a hard line even where it is filled).*

**Mechanism.** `planning.py:413` runs the cut only `if ... not is_textured` — i.e. on flat art. Pixels whose two nearest centres are within `AMBIGUOUS_BLEND_RATIO` get `fg_labels = −1`, owned by no layer, and `pipeline.py:381` builds every region as `labels == cluster_idx`, so −1 enters no mask. The Part 29 seam fill that would re-own them sits inside `if is_textured:` — unreachable on exactly the path that creates the damage. `geometry.py:49` states it outright: "pixels owned by nobody are never re-covered at all." The per-cluster escape hatch `AMBIGUOUS_MAX_CUT_SHARE = 0.35` is useless because each band individually loses 0.5–33% while the union is 15–17%.

**Why it looks worse than commercial output.** Measured bare fabric with a 0.45 mm thread raster against a foreground eroded 0.8 mm (so edge shaving is excluded): fixture 03 gradient 5.9% bare, largest blob 54 mm²; a blue→red ramp 7.9% bare with **full-height stripes 4.35 × 66.75 mm**; the hard-edge control with the same two colours 0.00%. Worst case is not even a gradient — `C24_many_colours`, plain flat rectangles, is 16.5% bare with a single **212.8 mm²** blob, because whole rectangles whose colour fell midway between two centres are deleted wholesale. At a 200 mm hoop the largest blob is 443 mm². Disabling the cut collapses all of it to ~0.3%. No commercial digitizer ships holes in the middle of a filled region.

**Generalised fix.** Make blend-pixel ownership a property of the transition's **width**, not the ratio. Distance-transform the −1 mask and discard only pixels whose local band thickness is at most one anti-alias width (~`up_f` px, i.e. sub-thread in mm); assign everything thicker to its nearest centre. Equivalently: run the existing seam fill **unconditionally** instead of under `is_textured`, keeping the discard for sub-thread bands only. Both forms are scale-relative and measured to leave hard-edged flat art bit-identical.

**Do not ship without also:** re-deriving `TEXTURE_RETRY_UNCOVERED = 0.19`. It was calibrated against the inflated `emitted_mask` (the angelfish's 22.8% was itself understated — 37 of its 67 regions were skipped and all credited as covered). Measured honestly, 14 flat designs cross the gate, so fixing DET2 without re-deriving the constant will mis-fire the photographic rescue on flat linework.

---

### #3 — CP1: the colour plan is non-deterministic
*No siblings — but this must be fixed **first**, because it invalidates the A/B measurement of every other item on this list.*

**Mechanism.** `planning.py:353` calls `cv2.kmeans(Z_pal, k, ..., attempts=3, cv2.KMEANS_PP_CENTERS)` with no seed, so k-means++ draws from OpenCV's thread-local `theRNG()`. The only `cv2.setRNGSeed` in the entire app sits inside `_split_bimodal_clusters`, gated on `is_textured`, so it never runs before the main palette k-means and on flat artwork never runs at all. `routers/digitize.py:24` is a plain `def`, so FastAPI dispatches to the anyio threadpool, whose workers are reused — the RNG state carries from one customer's request to the next.

**Why it looks worse than commercial output.** Four byte-identical POSTs of the same file, one event loop, all served by the **same worker thread**: 5 / 7 / 6 / 7 colour stops and 8288 / 8864 / 8825 / 8705 stitches. In-process 5× repeats give five distinct palettes with a worst thread drift of ΔE00 15.2 (pale olive vs pale lavender) and a 10% stitch spread. A 3-repeat sweep over 16 fixtures moved the stitch count on 12 of them. Commercial digitizers are deterministic; a customer who re-runs the same upload and gets a different thread list has no product.

**Generalised fix.** Seed OpenCV's RNG **immediately before every `cv2.kmeans` call site**, from a hash of the input (image bytes + hoop + max_colors) — not once at process start (only the first call would be pinned) and not from wall clock. Raise `attempts` and keep the best-inertia run. Verified: monkeypatching `cv2.kmeans` to seed first collapses all 13 fixtures tested to exactly one palette, one stitch count, one object count.

**Test note.** The existing guard `test_swarm_qa_corpus_digitize.py:215` (docstring: "the pipeline has no RNG") passes only because `TestClient` used outside a context manager spins a fresh portal, loop and worker thread per request. Put the client in a `with` block and it fails. Also seed `scripts/run_corpus100.py`, which digitizes the whole corpus in one process — every graded result there currently depends on the image's position in the run.

---

### #4 — SZ1: nothing in the engine delivers the millimetre value it claims
*Siblings — same contract, must move together: SZ3 (contour fill `row_px − 1`), SZ4/UP4 (pull comp rounding), UP1 (satin gets pull/2, fills get pull), UP2 (border built from the undilated contour), UP3 (square structuring element).*

**Mechanism.** Every physical quantity is paced on the integer working-pixel grid or applied under a convention that disagrees with its neighbour:
- `row_px = max(1, round(row_mm / mm_per_px))` and `for y in range(0, h, row_px)` — the sewn pitch is `row_px × mm_per_px`, only accidentally equal to the fabric's `row_mm`.
- `_contour_fill` subtracts a whole pixel: `step = max(1.0, row_px − 1.0)`, a fixed correction on a pitch of 2–5 px.
- `_dilate_pull` does `px = round(pull_mm / mm_per_px)` then `if px <= 0: return region` — with a **square** kernel, so it delivers `px` on axes and `px·√2` on diagonals.
- Satin adds `pull_mm/2` per side as a continuous float; fills add `pull_mm` per side as an integer dilation. Two generators, one number, a 2:1 disagreement.
- The fill's finishing satin border is swept on the **undilated** contour at a fixed ±0.6 mm, and every supported `pull_mm` is ≤0.5, so the whole compensable range is hidden inside it.

**Why it looks worse than commercial output.** Measured, cotton, 0.40 mm nominal: actual pitch 0.390 / 0.420 / 0.375 / 0.450 / 0.405 / 0.450 / 0.360 / 0.450 / **0.270** mm across hoops 40→360 — non-monotone, 67.5%–112.5% of target. The decisive control: the same 54.9 mm design in a 100 mm hoop, only the upload's pixel size varying — a 300 px source sews at 0.300 mm and 5458 stitches, a 350 px source at 0.514 mm and 3229 stitches. **Identical physical embroidery, 1.67× the density and 69% more machine time**, decided by a number the customer does not associate with density at all. The fabric selection can vanish entirely: at hoop 150, cotton (0.40) and knit (0.50) both sew 0.450 mm. Contour fill runs a ring at 0.225 mm against a 0.400 mm target at a 300 mm hoop — 2.0× over-dense, which is board-stiff and puckers. Pull compensation is zero for any sub-400 px upload at 200×200 while the object still reports `pull_compensation: 0.2`. And the stored `density` field is always the nominal value, so worksheets and exports report a number the stitches do not have.

**Generalised fix — one contract, applied everywhere.**
1. **Float pacing.** Carry pitch as `row_pitch_px = row_mm / mm_per_px` and walk `_scanline_fill` with a float accumulator instead of `range(0, h, row_px)`. Same for satin pitch, contour step, both underlay pitches. (Alternative that fixes pitch only: snap the grid to the density — `mm_per_px' = row_mm / round(row_mm / mm_per_px)`.)
2. **Contour fill:** cap the iso-contour correction at a fraction of pitch — `step = max(1.0, row_px − 1.0, 0.8 × row_px)` is bit-exact with today at `row_px ≥ 5` (so the existing coverage test stays green) and holds coarse grids at 1.25× instead of 2.0×.
3. **Isotropic sub-pixel offsets.** Replace `_dilate_pull`'s integer square dilation and both underlay erosions (`underlay.py:63`, `:211`) with a distance-transform threshold: `dist = distanceTransform(1 − region, DIST_L2, 5); region_out = dist <= pull_mm / mm_per_px`. Euclidean, sub-pixel, no rounding, no orientation bias — fixes SZ4, UP3 and UP4 in one change.
4. **One definition of `pull_compensation`** (per side, in mm, at the boundary) honoured by both generators. The code, `constants.py:278`, the user guide and the fabric test protocol all already say "per side"; fills honour it, satin delivers half. Change `generation.py:91` to `pull_mm / mm_per_px`. Also fix the un-compensated clamp at `columns.py:358` where a column at the width cap gets **zero** pull comp.
5. **Border carries the compensation.** Build the fill's satin border from the contour of `top_region`, not `contour` (and invert the sign for holes), so the outermost thread is the compensated one. `routing.py:49` already budgets `FILL_BORDER_MM/2 + pull_mm` — that expression is the invariant the border generator violates.
6. **Assert the contract.** For every emitted object: `|realised_pitch − prof["row_mm"]| / row_mm < 0.02`, and realised per-side offset within one pixel of `pull_mm` at 0/15/30/45°. Warn otherwise. This class of defect is invisible today because nothing measures the pitch actually used.

**Tests that will need rewriting, not reverting:** `test_part59_trim_profiles.py:52` (byte-identity, one 2-colour fixture), `test_contour_fill.py` row-pitch margin test (only exercises `row_px` 5–6, where −1 px is a benign 20%), `test_rebuild_satin_residuals.py:213` (asserts the literal string `"(pull_mm / 2.0) / mm_per_px"` — it guards *that pull is added at all*, not the factor), `test_pullcomp.py` (its fixture is an axis-aligned square at a `px = 0` grid, so it cannot see the bug or the fix). Note the whole bench corpus is cotton, where `row_mm == satin_mm == 0.40` — `test_rebuild_generator_arguments.py:144` says so in as many words. It was never positioned to catch any of this.

---

### #5 — DET1 + SZ2: the minimum-feature gate is a pixel counter wearing a millimetre label
*These two are the same estimator read from opposite ends of the crossover and must be fixed together.*

**Mechanism.** `region_med_w = median(nonzero distanceTransform) × 2 × mm_per_px`, compared against `MIN_FEATURE_W_MM = 0.25`; below it the **entire connected region** is dropped with `continue` — no object, no stitch, no colour stop. Two compounding errors: (a) for a stroke *W* px wide the DT runs 1..W/2..1, so `2×median` reads ≈ *W*/2 — the estimator systematically under-reads by half, and the same package already knows this (`generation.py:98`: "the DT median under-reads a rectangle badly, measured 3.6 mm for an 8 mm bar", which is why the satin cap uses the skeleton median instead); (b) the DT's smallest non-zero value is 1.0 and it returns exactly 1.0 for every region 1–4 px wide, so the estimate is floored at `2 × mm_per_px` and **the gate becomes unsatisfiable once `mm_per_px ≥ 0.125`** — 166.7 mm on a 1200 px canvas, or as low as 111 mm for a 400–599 px source.

**Why it looks worse than commercial output.** Below the crossover it deletes real work: measured, a straight bar is skipped at 0.300 mm and sewn at 0.375 mm; an annulus needs 0.525 mm. At 130×180, fixture 04 has 9 of 10 regions at DT median 1.0 and all 9 are skipped — one object emitted. `C28_lattice_trellis` returns **HTTP 422 "nothing could be sewn"** at 130×180 and **276 objects** at 200×200. Above the crossover it does the opposite: every 1 px anti-alias sliver is sewn as a real object with its own thread. `A_fixture_05`, a **one-colour** caps wordmark, comes back with six colour stops — five of them anti-alias ramp greys. Across the crossover 10 of 10 bench fixtures flip their skip count to zero and 6 of 10 change objects and colour stops discontinuously. **200×200 is one of the four hoops the UI ships**, so picking the standard 200 mm hoop silently disables the filter for every user and every image. Neither behaviour resembles a commercial result: fine linework should be sewn as a run, not deleted, and anti-alias fringe should never open a thread change.

**Generalised fix.**
1. **Replace the estimator.** Measure width sub-pixel — the skeleton/medial-axis median `spine_satin` already computes, or `DIST_MASK_PRECISE` plus an area/skeleton-length estimate. A pure pixel threshold is *not* enough: the DT median is blind between 1 px and 4 px, so the estimator needs replacing, not just rescaling.
2. **Re-derive the constant at the same time.** `MIN_FEATURE_W_MM`'s calibration note ("phantom halos 0.15 mm; real hairlines 0.30–0.33 mm") is circular — 0.15, 0.21, 0.30 and 0.33 are exactly the old estimator's first four output levels (2×1.0, 2×1.4, 2×2.0, 2×2.1969 × 0.075) at hoop 100. Swapping the estimator without re-deriving 0.25 will re-admit the blend halos Part 17 exists to kill.
3. **Downgrade, don't delete.** A region genuinely under one thread should be sewn as a single running stitch along its medial axis — `_axis_branches` + `_resample_open` already exist and are used by the dark-linework pass.
4. **Fail loudly.** When `2 × mm_per_px ≥ MIN_FEATURE_W_MM` the grid cannot answer the question: raise the working resolution for that run, or record a warning that sub-thread filtering was not possible. Never pass everything through in silence.
5. **Regression test:** sweep one fixture across hoops and assert object and colour-stop counts do not step discontinuously.

---

**Immediately below the cut, and why:** SF1 (staircase curves) is blocking and very visible, but bites only at design sizes >~120 mm — 2 of 4 shipped hoop presets, not all of them. DIR1 (scalar fill angle) is the classic auto-digitizer tell and hits 40/40 corpus fill objects, but thin curved strokes route to medial-axis satin, which does follow the axis, so the visible class is narrower than "all curved artwork". Both belong in the next tranche.

---

### 3. What a customer would SEE

**Gaps and bare fabric** (SH2, UP1, UP2, SF4, SH3, SZ4/UP4)
Unstitched fabric showing through the middle of a filled region — full-height stripes 4.35 × 66.75 mm on a gradient, a single 212.8 mm² hole in flat rectangular artwork, 443 mm² at a 200 mm hoop. Satin columns finishing narrow, because they get half the pull compensation a fill gets (0.1 mm/side missing on cotton, 0.25 mm on fleece) — and zero at the width cap. Bordered fills finishing at the wrong outer dimension, because the visible outline is drawn on the uncompensated contour. A fan of wedge-shaped gaps at every convex corner of every fill border: on a star tip the outer rim jumps 1.9 mm against a 0.4 mm nominal pitch, and on a small-radius feature the floor gate deletes half the stations so the whole feature runs at ~3× pitch. And every colour boundary is a hard line — the two colours share at most 0.6–0.8 mm of thread where commercial needle-blending interlocks over several millimetres.

**Lost detail** (DET3, DET1, SZ2, DET4, CB2, DET2, CB1)
Whole white or light-ink elements missing, with no warning — a white knockout over 81 mm² is deleted outright, and every transparent PNG is at risk because alpha is composited onto white. Hairlines, keylines, thin borders and script lettering deleted below the gate crossover and phantom anti-alias slivers *added* above it — one lattice fixture returns "nothing could be sewn" at one hoop and 276 objects at another. Punctuation, i-dots, stipple and any dot under 1.6 mm gone at the 2.0 mm² area cliff. Asking for **more** colours removes artwork: the badge fixture's "HARBOR CLUB" wordmark — ten satin objects of 25–43 stitches — vanishes going from 7 to 8 requested colours, absorbed into the cream fill that sews over it. And none of it is reported: the loss detector runs connected components over the union of all colours, so 95 of 100 corpus designs over-credit their own coverage, 42 by ≥2×; one fixture emits zero objects and still reports 11% lost.

**Banding** (SH1, SH3, CP3)
Gradients arrive as up to 8 flat posterised bands with a hard line between each. There is no graduated density, no stitch-length modulation and no feathered row ends anywhere in the product — pitch is a constant within every region, and the blend stitch type is a removed enum mapped to plain tatami. Separately, the bands themselves eat the colour budget: a large shaded field pulls extra centres into itself and pushes distinct accent colours off the palette entirely (accent survival falls 100% → 39.6% as the shading depth goes ΔL* 0 → 40, at fixed k and fixed accent area).

**Faceted curves** (SF1, SF2, SF3, DIR1)
Above ~120 mm design size a circle is stored as a raw pixel staircase — 670 points with 90° corners at a 200×200 hoop, 2216 points with 404 duplicate vertices at 400 mm — because the smoother's tolerance falls below one pixel and Chaikin's output is rounded back onto the same grid. An exact SVG circle comes out no better than a JPEG of one. And on curved filled shapes (leaves, petals, banners, large letter bowls) the rows run dead straight across the curve at up to 90° to the flow — median 34° within-region flow spread against a single scalar angle on all 40 corpus fill objects measured.

**Wrong colours** (CP2, CP1, CP3, CP4)
Thread colours nobody can buy: the digitizer emits raw k-means centroids as `thread_brand="Auto"`, `catalog_number=""`, so the **file format** makes the final thread choice — `#123456` becomes `#134a46` "Peacock Blue" in PEC, `#071650` "Navy Blue" in JEF, and random filler in EXP and DST. Same design, different colours per export. Distinct accent hues dropped in favour of shading bands (14 sewable modes lost across 13 corpus images that had *fewer* colours than the budget). A hard cap of 8 while the artwork separates into 12, accompanied by a warning that blames the artwork for the engine's cap. And a different palette every run.

**Puckering and density** (SZ1, SZ3, SZ4)
0.270–0.514 mm actual row pitch against a 0.400 mm target, decided by hoop size and upload resolution rather than the fabric you chose — too dense puckers, too sparse shows fabric through. Rings, frames and letter bowls up to 2.0× over-dense and board-stiff. Selecting the fabric can change nothing at all: cotton and knit both sew 0.450 mm at a 150 mm hoop. Two uploads of the same logo at 300 px and 350 px produce identical physical embroidery at 1.67× the density and 69% more machine time.

**Production cost** (CB4, CB3)
On photographic input 35–56% of run time is the machine stopped: 93–155 trims per design, median 17–25 stitches per object, and no inter-object travel or branching to hide the moves. The operator's worksheet lists 18 numbered threads for 10 actual spools, because same-thread stops that could be made adjacent never are.

**Inconsistency** (CP1)
Upload the same file twice and get a different design: measured through the real HTTP endpoint, four identical POSTs returned 5 / 7 / 6 / 7 colour stops and 8288 / 8864 / 8825 / 8705 stitches.

---

### 4. Marked `generalised = false` — "do not fix these image-specifically"

**Nothing is.** All 31 confirmed defects returned `verdict.generalised === true`. There is no defect in this set that should be fixed per-image.

Two things belong in this section anyway, because they are the places where a per-image fix is the tempting wrong answer:

**CB4 (fragmentation → trim time) is class-gated, not universal.** Its author-assigned `generality` is `class-specific`; the verdict confirms it generalises *within* real photographic/textured raster input (reproduced on 3 photographs plus 5 B-tier derivatives) and explicitly **does not** affect flat vector-like art (C05, C07, C08, C12 each digitize to 1–3 objects with 0 trims). The fix must therefore be gated **geometrically** — merge same-colour components whose connecting corridor lies inside the union of that colour's regions plus everything sewn later — so it degrades to today's behaviour where no corridor exists and cannot regress flat designs. Do not gate it on a fixture list or an "is this a photo" heuristic.

**Sub-claims falsified during verification. Do not build fixes around these:**
- **CP3** — 84 of the 98 missed corpus colour modes come from 9 images that simply hold 16–24 modes against k=8. That is plain budget shortfall, not shading theft. The clean signal is 14 modes across 13 images. Do not tune against the 9.
- **CP3** — `_split_bimodal_clusters` is a *partial rescue* (raises accent survival 39.6% → 83.3%), not an aggravator. Its centres are appended, not taken from k. Do not remove it.
- **CP4** — the four `tiny_lettering` fixtures return zero stitches at both caps; they do not evidence the colour cap. And the 78% → 89.1% coverage table is a raw-`cv2.kmeans` proxy that bypasses centre merging, the blend cut and the speck filter — at pipeline level only 8 of 60 designs gain colours at k=12 and **4 lose** one. A cap lift is a tradeoff, not a free win.
- **DET1** — the report's "same physical width, source resolution varied" sweep does not reproduce; work resolution is clamped to 1200 px, so the free variable is the **hoop**. Do not chase upload pixel counts here (they *are* the free variable for SZ1/SZ2/UP4 — different defects).
- **UP3** — the "45° diamond grew +0.247 mm in x but +0.156 mm in y" evidence is not caused by the square kernel (a square kernel is symmetric; measured, the diamond grows +14 px on both axes). That asymmetry has another cause, most likely fill-row pacing at an angle. Do not cite it, and do not treat it as fixed when UP3 is fixed.
- **DIR1** — "the sweep/4 result independently reproduces the 49.9° coin-flip baseline" is an arithmetic identity (mean absolute deviation of a uniform distribution is span/4), not corroboration. And `STATUS.md:131` records that the 49.9° figure is itself partly a structure-tensor instrument artefact.
- **CB3** — the per-design duplicate counts in the report are wrong (peacock is 15/10, not 15/9; A02 is 17/11, not 10/7), and only **1** of the peacock's 5 duplicates is removable by a permutation that respects the dependencies the pipeline models. The other four need the main colour sequence moved off darkest-first, which is a layering decision.
- **DIR2** — the direction field being unconsumed is deliberate, documented and test-enforced staging with a measured reason for stopping (`docs/benchmarks/v2-part51-audit.md`: "D2 was implemented, measured, and reverted"). Its CPU cost is ~1% of a run, not a performance problem. The real unconditional cost is the 14.4 MB full-frame snapshot pinned in a module global on a long-lived server. Fix the memory, treat the wiring as feature work, and note that wiring it before DIR3 and DIR4 are fixed will simply reproduce Part 51's null result.

---

### 5. What was NOT investigated

**There is no measured comparison against commercial output anywhere in this work or in the repo.** `apps/backend/scripts/bench_competitor.py` holds five in-repo fixtures with no competitor output, two foreign machine files with no source artwork, and one watermarked competitor render with no stitch file; its own report says every numeric cross-comparison is "not measurable from the files available". Every "worse than commercial" judgement above is reasoning from published feature descriptions and from craft first principles — not from a matched benchmark.

**Nothing was sewn.** All coverage, bare-fabric and interdigitation numbers are synthetic thread rasters (0.40–0.45 mm stroke over consecutive stitch pairs) with a stated floor of ~4% on the hard-edge control. Differentials and the coincidence of bare pixels with the −1 mask carry the findings; the absolute percentages do not. Puckering, pull-in and registration were reasoned about, never observed on fabric.

**Not audited at all:**
- **Lettering engine** (`services/lettering.py`) — only noted in passing that it rasterises PIL glyph bitmaps at 160 px (480 in arc mode) and feeds them to `digitize_image`, so font curves take the same raster round-trip at a coarser grid than an SVG upload. No kerning, spacing, baseline, arc, or small-type-legibility work.
- **Export / machine-file layer** — `embroidery_io` was probed only for colour substitution on five formats. The 47 read / 19 write formats, DST/PES/EXP stream correctness, jump/trim command encoding, and real machine compatibility were not examined.
- **Appliqué and foam paths** — `underlay.py:382-399` (edge-cover satin at 2 mm width with `floor_px = 0`, so worse corner amplification than SF4) was noticed and never measured. The three-phase appliqué sequence was not reviewed.
- **Rebuild / edit path** — sampled where it shares generators with digitize (`rebuild.py:187`, `:244`, `:435`), never audited as a feature. Undo/redo, persistence, `stitch_edit.transform_range`, and object-level editing semantics untouched.
- **Frontend** — only `DigitizeDialog` (hoop list, colour clamp), `PropertiesPanel` (density input) and `ThreadPalette` (manual match button) were read. No UI/UX review.
- **Routing quality beyond fragmentation** — start/end point selection, colour-block ordering, travel-stitch visibility under later layers, and the `_lock_stream` tie-off geometry were not independently verified (the repo's own detector reports 0 unlocked ends of 806 and 0 attached jumps >10 mm; I did not re-derive that).
- **CONTOUR underlay type** — the one `UnderlayType` member with no reachable generator. Not investigated.
- **Fabric profile *values*** — whether 0.40 mm on cotton or 0.2 mm pull is correct craft was not assessed. Only whether the code delivers the number it stores (it does not).
- **Performance, memory and concurrency** beyond the RNG finding and the 14.4 MB per-digitize pin. No leak audit, no load testing, no multi-tenant isolation review, no security or auth review.
- **Interaction effects.** Each defect was verified largely in isolation, with the other thirty left at their shipped (broken) values. The combined effect of fixing several at once — particularly the physical-units contract (#4), which touches every generator — has not been modelled. Expect the ten-fixture bench to move substantially, and re-pin it at a hoop above 133 mm, since at 100×100 and 130×180 it cannot see SF1, SZ2 or half of #4 at all.

**Corpus caveat.** Tier C of `tests/fixtures/corpus100` is synthetic by its own generator's header. Incidence rates quoted above ("51/100 designs", "24/100", "42/100 over-credited") are frequencies *within this corpus*, not real-world frequencies. The class-level exposure of each defect is established by the controlled synthetic probes and by the tier-A/tier-B real photographs, not by the tier-C counts.

---

# APPENDIX B — superseded documents

These remain in the repo for traceability. **Everything in them is in this report**, with
corrections applied. Where they still show an uncorrected figure it is marked inline.

| file | status |
|---|---|
| `CTO-VERDICT-2026-08-09.md` | the governing verdict — CTO-authored, unmodified |
| `CTO-VERDICT-EXECUTION-REPORT.md` | STEP −1 → 3d — summarised in PART 2.2 |
| `CTO-RESPONSE-3E-AND-ATELIER.md` | the 3e disagreement — PART 2.3 |
| `CTO-3E-FINDINGS.md` | travel routing is 31% of the corpus — PART 2.4 |
| `CTO-1A-EMISSION-ORDER.md` | partial attribution — PART 2.5 |
| `CTO-1B-BOUSTROPHEDON.md` | the main win — PART 2.6. **Corrected** for the annulus figures |
| `CTO-CLASSIFICATION-MECHANISM.md` | PART 2.7. **Carries its own retraction banner** |
| `CTO-P1-PARITY.md` | PART 2.8 |
| `HANDOFF-ENGINE-2026-08-10.md` | **superseded** — banner added |
| `REVIEW-HANDOFF-2026-08-10.md` | **superseded** — banner added, 4 figures corrected inline |
| `QUALITY-DEFECTS-2026-08-10.md` | reproduced in full as Appendix A |
