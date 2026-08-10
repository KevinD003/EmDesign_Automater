# StitchIQ engine — full review handoff, 2026-08-10

**For a reviewing Claude.** This covers everything from the last report through to the current state,
including the things that went wrong. Written to be checked, not believed: every number below has a
command beside it or is labelled as unverified.

Repo `KevinD003/EmDesign_Automater`, single branch **`main`**.

---

## 0. Read this first — how to weigh anything in this document

The single most useful fact for a reviewer: **over this engagement, eight candidate explanations
were proposed and refuted by measurement, and most were the leading hypothesis of either the CTO or
the build engineer at the time.**

| # | hypothesis | refuted by |
|---|---|---|
| 1 | contour fidelity explains the digitize/rebuild gap | 0.2% area error, ~1% of the gap |
| 2 | branch ordering causes the badge's travel | greedy reorder changed total travel 0.0% |
| 3 | column sweep ordered on the wrong axis | zero jump-flagged transitions within a branch |
| 4 | branch seams explain a 44mm median | seams measured 6.44mm median |
| 5 | `_extend_branch_ends` skews the width statistic | removing it moved the median 3.62 → 3.71mm |
| 6 | `SATIN_MAX_UNCOVERED` is a blind share | the uncovered mask is measurably an edge rind |
| 7 | badge Satin 3 has letter-gap slivers that are genuinely satin | three independent measures: no such population |
| 8 | fixture 08's density flag is a grid artefact | grid-free measure says 23 → 26, a real 13% rise |

**#7 and #8 were mine, asserted confidently, and both were wrong.** #8 was refuted by an instrument I
built specifically to confirm it. Treat every unverified claim in this repo — including in this
document — accordingly.

---

## 1. What is actually shipped and working

`main` is green. Every fix is in **production code** under `apps/backend/app/services/digitizer/`,
which is the code path every customer upload runs through. No test file executes for an upload —
verified three ways: import scan of all 62 app files, a live upload trace, and the Docker image not
containing `tests/`.

### 1a. The boustrophedon fix — the engagement's main win

`fills.py`. `_scanline_fill` walked every scan row and emitted each of its runs back to back, so on
an annulus it hopped left-run → right-run **straight across the hole** once per row, and
`_route_travel` sewed a detour around the rim each time.

Rows are now split into **monotone cells** at critical rows where the run count changes; each cell
is sewn to completion; cells are visited nearest-first.

| | badge (07) |
|---|---|
| machine-minutes, net of trim cost | **47.0 → 22.65** |
| stitches | 35,077 → 17,181 |
| trims | 76 → 28 |
| corpus digitize stitches | 97,590 → 65,004 (−33.4%) |
| coverage, all ten fixtures, both paths | 99.3–100%, none lost |

Isolated on a 300px annulus: **2,151 points before and after** — pure reordering, no coverage
removed — while total jump distance fell 13,059.6px → 233.9px and hole crossings 68 → 0.

Independently reproduced by the CTO with a different coverage metric (0.4mm thread @ 8px/mm vs the
series' 0.35mm @ 6px/mm): 17,162 st / 22.54 min / 100.0%.

Reproduce: `scripts/run_quality_bench.py`. Tests: `tests/test_boustrophedon_cells.py` (12 cases).

### 1b. The 100-image corpus, brought into use

Until today, **every headline number in this engagement came from 10 synthetic fixtures.** The
100-design corpus and `scripts/run_corpus100.py` were already in the tree and had not been run once.
They now have a baseline (100/100, 0 errors, 921s) and a tier-aware comparer.

`scripts/compare_corpus100.py` diffs two runs and **refuses to blend the provenance tiers**. A
regression on tier C parametric artwork is a note; one on tier A or B **fails and exits 1**.

### 1c. A grid-free density measure

`measure_stitch_quality.py :: _max_per_disc`. See §3 — it was built to settle an argument and then
overturned the position that built it.

---

## 2. The corpus is much weaker than its labels claim — verify this yourself

The "100-design corpus" is **not** 100 designs of variety:

| labelled | actually |
|---|---|
| 13 "tier A real" | **3 photographs** + 10 copies of the synthetic bench fixtures |
| 40 "real-derived" | crops/rotations/recolours of *those same 3 photographs* |
| 47 "parametric" | generated from 13 hard-coded shape classes → ~29 distinct layouts |

**There are 3 real photographs in the entire backend test suite** — user-supplied embroidery
sew-outs: a peacock patch, a black floral neckline, a floral neckline panel. A fourth committed
file, `reference_sewout.jpg`, is a pixel-identical duplicate of one of them. The three originals came
from a scratch directory that no longer exists, so `build_corpus100.py` **cannot be re-run on a fresh
checkout**.

The build engineer repeated the corpus's own tier labels without checking inside them, and told the
owner "13 real". That was wrong in the way that matters.

**Consequence for any reviewer:** a green suite and a clean corpus diff say the code did not break
what already worked. They say very little about a photograph the pipeline has never seen. The scale
gap is stark — the badge everything was tuned on is 17,181 stitches / 22 objects; the real peacock
photo is 42,449 stitches / 335 objects.

---

## 3. The blocked decision, with a correction

**Status: the Zhang-Suen parity fix is written, evidenced, and NOT on main.** Recover with
`git revert --no-edit 01c2cb8`.

### The defect

`skeleton.py :: _thin_state` computed thinning parity as `((row + col + y0 + x0) % 2)` under a
comment insisting the crop origin "MUST be added back". The goal was right, the means backwards:
`_zhang_suen_thin` walks parities in a fixed order, so keying to absolute `(y + x)` makes thinning
depend on **where the artwork sits on the canvas**.

Measured through `spine_satin`, 24 bars spanning the satin cap, four one-pixel offsets each:

| | bars changing `stitch_type` on a one-pixel shift |
|---|---:|
| before | **13 of 24** |
| after | **0 of 24**, every median width identical |

On short bars `median_w` swung 0.00 ↔ 2.86mm — the axis was erased outright. The signature was
diagnostic: `(0,0)` always agreed with `(+1,+1)`, `(+1,0)` with `(0,+1)`. Only a checkerboard does
that. Crop-relative parity delivers **both** invariants, so the old comment's premise was false.

Corpus effect: 65,004 → 65,018 stitches (+0.02%), coverage unchanged. **This buys correctness, not
cost.**

### 100-image evidence

| tier | result |
|---|---|
| A real (13) | **clean** — no structural change, no regression |
| B real-derived (40) | 5 object-count changes, all benign on inspection. `B01_rotate` −63 objects, −2,081 stitches, −33 trims, −129 jumps at unchanged coverage (spuriously split objects merging). `B00_crop` +1.2 coverage, largest gain in the corpus. The two rotate variants moving in **opposite** directions (−63, +5) is the position-lottery signature disappearing. |
| C parametric (47) | `C23_monogram` −0.9 coverage; `C45_thin_border` splits into a third object (+44% stitches); `C04`/`C17` tiny lettering go 16 stitches → 0 (a class already mostly failing — `C30` was 0/0 in baseline) |
| safety, all 100 | density flags 0 → 0, floor violations 1 → 1, over-limit 0 → 0 |

### What blocks it, and the correction

`tests/test_stitch_quality_metrics.py::test_density_corpus_health_is_pinned` fails: fixture 08's
`max_per_cell` 13 → 14 and `flagged_cells` 0 → 1. A prior commit had written, of this exact number,
*"must be investigated, not re-pinned."*

The build engineer investigated and argued it was a **grid artefact** — a tie-off cluster (3–4
deliberate penetrations inside a thread width) straddling a 0.4mm cell boundary, with the real
neighbourhood total moving only 25 → 26 and p99 unchanged at 5.

**That argument is wrong.** `_max_per_disc` — which counts penetrations within a radius of every
penetration, with no grid, so translation cannot change it — was built to confirm it and says:

| | `max_per_cell` (grid) | `max_per_disc` (grid-free) |
|---|---:|---:|
| old parity | 13 | **23** |
| new parity | 14 | **26** |

The densest neighbourhood genuinely rose **13%**. The pin caught a real, localised density increase.

**So the open question is a genuine trade-off, not a metric bug:** the parity fix removes a
significant generalisation defect (13/24 bars misclassifying on a one-pixel shift) at the cost of
+13% peak local density at one lock site on one fixture. A reviewer should decide whether that
trade is acceptable, or whether the new thinning's interaction with lock placement should be fixed
first.

**Unverified and worth checking:** whether the penetrations in that neighbourhood are in fact
tie-off stitches. A probe using a ±0.25mm box around the reported coordinate caught only one stitch,
so the metric's grid origin is not where assumed; the question was never answered.

---

## 4. Other open items

**5c — a digitize/rebuild trim divergence.** Badge at the G4 configuration (6 colours, 100×100):
before the boustrophedon fix both paths ran 57 trims; after, digitize 19 and rebuild 25. Rebuild
improved (57 → 25); the fix removed noise that was hiding a 6-trim gap. The proposed mechanism —
digitize routes at 13.3 px/mm on the source image, rebuild at 10 px/mm on the object bounding box —
**is a hypothesis and has not been measured.** It must not be quietly absorbed by later work.

**`compact_no_axis`.** `generation.py`'s no-medial-axis arm has no size test and zeroes both
`median_w` and the sample count, so every width-based statistic is structurally blind to it. A
14.6mm disc (`09_nonuniform_background` seq 1, 168mm², sewing correctly at 100% coverage) shares a
reason string with 2.6mm punctuation dots. A fix exists in `5280abb` but is unlanded with the parity
work.

**Classification width statistic.** `median_w` is `np.median` over axis **samples**, so it weights
axis *length* equally rather than shape. Lettering knocked out of a band multiplies axis length in
that arc, so it outvotes the plain arc. Badge Satin 3: band measures **6.98mm** with 96.7% of its
circumference over the 4.5mm cap; the classifier judged **3.62mm** and chose satin. The concentric
ring with no lettering reads 5.26 against a true 5.51 and is correctly rejected — that control
isolates the cause to the lettering. **A CTO ruling directs an area-over-cap veto** with measured
separation 0.000000 on 13 correct satins vs 0.558–0.798 on 4 misclassified; acceptance is **coverage,
not machine-minutes** (machine time gets worse by design: corpus +7.5%, badge ~22.6 → 25.1).
Sequenced behind the parity fix. **Not started.**

**Recorded, not acted on:** professional judgement that 1.5mm gold lettering should never be knocked
out of a navy band — sew the band solid and put lettering on top in the second colour, because
±0.3mm registration drift eats a 1.5mm letter. A knockout-policy question upstream of classification.

---

## 5. Process failures this engagement — a reviewer should weigh these

1. **Pushed before verification.** `5280abb` went to `main` ahead of the local two-lane run, trading
   the standing verify-then-push discipline for durability in an ephemeral container. Both lanes then
   failed. `main` was red for ~30 minutes; reverted in `01c2cb8`.
2. **Measured on 10 images for the whole engagement** while a 100-image corpus sat unused.
3. **Repeated the corpus's tier labels without opening them** and reported "13 real" when it is 3.
4. **Set a quality band from a single reading.** 06_wordmark_script's band was tightened 12% → 8%
   from one measurement; the quantity swings ~5 points under a one-pixel source shift (3.22–7.76%
   before the fix, 3.13–8.16% after). The gate then correctly refused a re-pin.
5. **Shipped a comparer with three defects**, all found by running it for real: arithmetic on a
   not-applicable sentinel (reporting a 101-point coverage collapse and calling `-1.0 → 0.0` an
   *improvement*), a tolerance picked rather than measured, and object count not graded at all.
6. **Twice leaned toward explaining away a failing gate** (#7 and #8 in §0). Both times the
   measurement went the other way.

The gates caught 1, 4 and 5. That is the system working; it is also the reason not to weaken it.

---

## 6. How to verify anything here

| what | command |
|---|---|
| ten-fixture bench | `scripts/run_quality_bench.py` |
| 100-image corpus | `scripts/run_corpus100.py --workers 3 --json out.json` (~15 min) |
| compare two corpus runs | `scripts/compare_corpus100.py base.json cand.json` |
| classification widths | `scripts/measure_classification_width.py` |
| default test lane | `pytest tests -q` (~14 min) |
| second lane | `STITCHIQ_NO_REBUILD_PASSTHROUGH=1 pytest tests -q` (~13 min) |
| stream locks | `STITCH_LOCK_WRITE=1 pytest tests/test_swarm_perf_lock.py -q` — **refuses** a band-violating re-pin |
| renders | `scripts/visual_regression.py [--update]` — SSIM gate 0.995 |

Pinned toolchain: python 3.11, `opencv-python-headless==5.0.0.93`, `numpy==2.4.6`. Digitize rasters
at **13.3 px/mm** (measured — an earlier report said "~18" by reading it off constants).

**When a real improvement lands, re-cut the quality bands.** The badge's band was 55 machine-minutes
against a 47 reading; at 22.65 that band would wave the entire pre-fix regression back through. A
gate that cannot fail is not a gate.

---

## 7. The owner's standing requirements

- **One branch, `main`.** Everything lands there. Three stale remote branches remain because the
  environment's git proxy blocks delete pushes and the GitHub MCP has no delete-branch tool; all
  three are verified safe to delete (two fully merged; the third's only unique commit is a
  byte-identical duplicate of a file already on main).
- **Every change must generalise.** No fix that works only for one image. Report the mechanism, the
  class of artwork affected, and how you know it is not fixture-specific.
- **Competitor-level output on any uploaded image.** Where it falls short, find precisely what is
  wrong — shades, colour, shape, size — and fix it generally.
- **Never open a pull request unless asked.** `apps/backend/data/` stays gitignored. **Ink/Stitch is
  GPL — concepts from public documentation only, never source.**

---

## 8. The highest-value thing a reviewer can push for

Real customer artwork. Everything provable today rests on **3 photographs**. A folder of actual
uploads, run through `run_corpus100.py`'s measurement path and inspected by eye, would tell us more
about production quality than any amount of work on the existing fixtures.

A separate generalised competitor-gap investigation ran against this codebase: 41 agents over eight
quality dimensions, each finding independently re-checked by a second agent asked to refute it.
**31 defects confirmed, all 31 verified as generalised.** Results in
`docs/QUALITY-DEFECTS-2026-08-10.md` — read it next.

The single most important one for a reviewer: **CP1, the colour plan is non-deterministic.**
`cv2.kmeans` is called unseeded, drawing from OpenCV's thread-local RNG, and the digitize endpoint is
a plain `def` so FastAPI dispatches it to a reused threadpool worker — RNG state carries from one
customer's request to the next. Four byte-identical uploads on the same worker returned 5/7/6/7
colour stops and 8,288/8,864/8,825/8,705 stitches. **This must be fixed before any other A/B
measurement in this document can be trusted, including the parity trade-off in §3.**
