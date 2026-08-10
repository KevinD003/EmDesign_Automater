# Handoff — StitchIQ digitizing engine, 2026-08-10

**For whoever picks this up next.** Everything below is measured unless it says otherwise. Where a
number is a guess I have labelled it a hypothesis, and there are two of those still open. Believe the
labels — a good deal of this engagement was spent discovering that plausible explanations were wrong.

Repo `KevinD003/EmDesign_Automater`, branch **`main`** (single-branch by owner instruction), head
`ee17c03`, CI green.

---

## 0. The one thing to internalise

**Do not trust a stitch-count improvement, a passing gate, or a plausible mechanism. Measure it.**

This engagement's largest defect — travel routing manufacturing 31% of all corpus stitches — survived
a full test suite for months because the exact-hash lock moved with the regression each time someone
re-pinned it. Since then, of the candidate mechanisms proposed for the various defects, **six were
refuted by measurement**: contour fidelity, branch ordering, column sweep axis, branch seams,
`_extend_branch_ends`, and `SATIN_MAX_UNCOVERED` being a blind share. Four of those six were the
leading hypothesis of either the CTO or me at the time.

Standing policy from the CTO, verbatim: *"Do not treat a CTO ruling as settled when your measurements
contradict it."* That has been exercised twice and both times the measurement won.

The headline metric is **machine-minutes net of trim cost** — `stitches/800 + trims × 2.5s`. Not
stitch count. A change that trades stitches for trims must be judged on the total.

---

## 1. Where the numbers are

Corpus, canonical bench parameters (`scripts/run_quality_bench.py :: FIXTURE_PARAMS`), digitize path:

| | before this engagement | now |
|---|---:|---:|
| corpus stitches | 97,590 | **65,004** |
| badge (07) machine-minutes | 47.0 | **22.65** |
| badge trims | 76 | 28 |
| coverage, all ten, both paths | 99.1–100% | **99.3–100%** |
| digitize/rebuild ratio within 5% | 8 of 10 | **9 of 10** |

The badge is down 61% in machine time since the engagement began. Independently reproduced by the CTO
with a different coverage metric (0.4 mm thread @ 8 px/mm vs the series' 0.35 mm @ 6 px/mm): 17,162
st / 22.54 min / 100.0%.

Reproduce with `scripts/run_quality_bench.py`. Pinned toolchain: python 3.11, `opencv-python-headless
5.0.0.93`, `numpy 2.4.6`. Raster is 13.3 px/mm on the digitize path (measured — do not read it off
constants, an earlier report said "~18 px/mm" from doing exactly that).

---

## 2. What landed most recently — 1b, boustrophedon cell decomposition

`apps/backend/app/services/digitizer/fills.py`. `_scanline_fill` used to walk every scan row and emit
each of its runs back to back, so on an annulus it hopped left-run → right-run **straight across the
counter** once per row, and `_route_travel` sewed a detour around the rim each time. Rows are now
split into **monotone cells** at the critical rows where the run count changes; each cell is sewn to
completion; cells are visited nearest-first entering at whichever of four corners is closest.

Isolated on a 300 px annulus: **2,151 points before and after** — pure reordering, no coverage
removed — while total jump distance falls 13,059.6 px → 233.9 px and hole crossings 68 → 0.

Full report: `docs/CTO-1B-BOUSTROPHEDON.md`. Tests: `tests/test_boustrophedon_cells.py` (12 cases).

Two traps this left behind, both live:

- **The stagger phase is anchored at the region's own first scanned row**, not at absolute canvas
  `y`. I used absolute `y` first and reintroduced the STEP 3a position-dependence, because
  `_scanline_angled` short-circuits to `_scanline_fill` below 0.5° **without cropping**. If you touch
  the phase, run `test_the_shallow_angle_shortcut_is_still_position_independent`.
- **Jump *count* is not the metric; jump *length* is.** 68 short repositionings costing 155 travel
  stitches is fine. 171 jumps at a 42 mm median costing 16,989 was the defect. A test that asserts on
  raw count conflates serpentine turns at a curved cap with real inter-cell hops — mine did, and was
  wrong.

---

## 3. The current investigation — classification, mechanism found, NOT fixed

Full detail in `docs/CTO-CLASSIFICATION-MECHANISM.md`. Re-runnable:
`scripts/measure_classification_width.py --only 07_circular_badge`.

**The mechanism.** `median_w` is `np.median` over axis **samples**, so it weights each unit of *axis
length* equally rather than each unit of the shape. Knocking lettering out of a band multiplies the
axis length in that arc — a strand above and below every letter instead of one strand down the centre
— so the lettered arc gets **2.4× the sampling density** and outvotes the plain arc.

Badge Satin 3: the band is **6.98 mm wide with 96.7% of its circumference over the 4.5 mm cap**, and
the classifier judged it at **3.62 mm** and sewed it as satin. The width histogram is bimodal — a mode
at 6–7 mm, a mode at 2–3 mm — and the median lands in the trough between them.

**The control that settles it:** the concentric ring beside it, same design, same raster, one
component, *no lettering* — judged 5.26 mm against a true 5.51 mm, accurate to 5%, correctly rejected
as a fill. The statistic works on the ring without text and fails by 1.9× on the ring with text.

**Both "obvious" answers to the CTO's framing are wrong.** The region is not mis-segmented — one
connected ring band is correctly one object. The cap is not mis-set — 4.5 mm is right for satin. The
object genuinely has two widths and no scalar is honest about it.

**Do not respond to this by moving a threshold.** An area-weighted width reads 4.92 mm and would
reject the object — and then tatami the 2–3 mm letter-gap slivers that genuinely *are* satin. Sample
median gets the plain arc wrong; area weighting gets the lettered arc wrong. The unit is wrong, not
the threshold.

Options, in my order of preference, none started:

1. **Split regions at width discontinuities before classifying.** Correct and general — any badge,
   seal or ribbon with text knocked out of a band has this shape. Blast radius: segmentation, the
   object model, `params_hash` provenance, B2's transforms.
2. **Per-branch decisions within one object.** Smaller, but makes `stitch_type` a lie at object level
   and the Studio shows `stitch_type` to the user.
3. **Leave it.** Coverage is 100%, the badge is 22.65 min, this costs ~155 travel stitches and five
   over-20 mm jumps.

**The survey is done and it weakens option 3.** 13 of 24 measurable objects are bimodal, so
bimodality alone is ordinary and is not a usable detector. The discriminator is **`areaW / judged`**
— how far the sample-count median sits from what the shape's area says. Among objects sewn as satin:
`08` seq 2 at 1.63×, `08` seq 1 at 1.52× (1,601 mm², 61 branches), `07` seq 3 at 1.36×, `03` seq 1 at
1.31× with half its band over the cap. A correctly-measured object reads 1.00×. **Four objects across
three fixtures show the signature, two of them over 1,500 mm²** — the badge is just the one where an
independent radial measure proves it.

Cheap interim if the full fix is not wanted yet: log `areaW/judged` in `_CLASSIFICATION_LOG` so the
corpus can be watched without changing any behaviour.

**Unrelated anomaly the survey turned up, recorded and not investigated:** `09_nonuniform_background`
seq 1 is a **168 mm² region with zero medial-axis branches**, falling out as `no_medial_axis` — the
path meant for freckles. The corpus's other `no_medial_axis` regions are 2.6 and 5.2 mm².

---

## 4. Queue, in the CTO's stated priority order

1. **Classification** — mechanism reported above; awaiting the direction call.
2. **1c** — `DETOUR_COST_MAX` recalibration plus a trim-count ceiling. Both the CTO and I expect a
   small prize now: travel manufactures 5% of Satin 3 rather than 80%, so the cost model has much
   less to get wrong. **"Leave it" is an explicitly valid outcome here** — the CTO said so. Measure,
   then say so and move on.
3. **3e-i** — one shared emission core for fills as well as satin. Acceptance is the **3c criterion**:
   the refactor must not change *either* path's stream on any of the ten fixtures. (Note: this is
   before/after identity *per path*. It does **not** mean digitize and rebuild become byte-identical
   to each other — they cannot, they differ by 0.99–1.11 across the corpus. This was explicitly
   confirmed with the CTO.)
4. **B2 (transforms)** — in parallel, under three recorded constraints: rotation must rotate
   `stitch_angle` (+19.9% measured on fixture 01 otherwise) with documented semantics; scaling must
   re-apply size-dependent rules (density, pull comp, satin width limits, minimum-feature gate); and a
   transform probe goes in the bench asserting untouched objects change 0.0% and coverage stays ≥99%.

Frontend **Atelier P3–P5 are halted** pending the owner's confirmation, per a CTO ruling. P1 and P2
shipped and are not reverted.

---

## 5. Open, unresolved, do not let these be quietly absorbed

**5c — a +6 trim divergence between digitize and edited-rebuild.** Badge at the G4 configuration
(6 colours, 100×100): before 1b both paths ran 57 trims; after, digitize 19 and rebuild 25. Rebuild
did not get worse — it went 57 → 25. 1b removed the routing noise that was hiding a 6-trim gap.

My explanation is that the known raster difference (digitize routes at 13.3 px/mm on the source
image, rebuild at 10 px/mm on the object's bounding box) makes a move that routes inside the region on
one path fail on the other and become a trim. **This is a hypothesis. It is not measured.** The CTO's
standing instruction: if 1c or 3e-i explains it, say so explicitly; if neither does, it stays open.

**Fixture 08 density margin is one.** `max_per_cell` moved 12 → 13 against a flag at 14. p99 unchanged
at 5 and `flagged_cells` still 0, so it is not a density shift — one cell's hottest point moved 0.4 mm
and gained a penetration at a lock site. Measured on both segmentation paths (13 with rembg, 12
without); the pin brackets both. **A 14 here later must be investigated, not re-pinned.**

---

## 6. Gates, and how to not fool yourself with them

| gate | command | note |
|---|---|---|
| suite, default lane | `pytest tests -q` | ~14 min |
| suite, no-passthrough lane | `STITCHIQ_NO_REBUILD_PASSTHROUGH=1 pytest tests -q` | ~13 min; both must pass |
| stream locks | `STITCH_LOCK_WRITE=1 pytest tests/test_swarm_perf_lock.py -q` | **refuses** to re-pin a stream that violates its quality bands |
| visual baselines | `scripts/visual_regression.py [--update]` | SSIM gate 0.995; an unchanged pipeline scores exactly 1.000000 |
| bench | `scripts/run_quality_bench.py` | canonical parameters for every number in the docs |
| classification | `scripts/measure_classification_width.py` | flags objects sewn as satin on a width they do not have |

**The lock's quality bands are the load-bearing part, not the hash.** An exact hash catches any
change, which is right for an optimization that should be byte-identical — but it cannot tell a good
change from a bad one, and the moment of re-pinning is where the 2-pixel-floor regression got blessed.
`STITCH_LOCK_WRITE=1` now asserts rather than writes when a band is violated.

**When you land a real improvement, re-cut the bands.** The badge's band was 55 machine-minutes
against a reading of 47; at 22.65 that band would wave the entire pre-1b regression back through. It
is now 28.0. A gate that cannot fail is not a gate.

`ruff check .` is **not** a zero gate — the digitizer carries documented pre-existing findings. CI runs
`scripts/verify_lint_claim.py` instead, which re-runs the counts claimed in audit documents. Keep
files you touch clean; do not mass-fix the rest.

There is a **1,500-line-per-module gate** on the digitizer package. Layering, strictly:
`constants → geometry → provenance → skeleton → columns → fills → satin → underlay → generation →
routing → planning → staging → pipeline → rebuild`.

---

## 7. Constraints in force

- **Never open a pull request unless explicitly asked.** Commit and push to `main`.
- `apps/backend/data/` is gitignored and must never be tracked. Real secrets only in a gitignored
  `.env`.
- **Ink/Stitch is GPL.** Concepts from public documentation only — no code read or copied.
- Do not put the model identifier in commit messages, PR text, code comments, or any pushed artifact.
- Report **every** workstream in every report, including work you judge low-risk. This rule exists
  because two workstreams went unreported and the second one was a fair hit.

---

## 8. Blocked on the owner

Live RLS apply; GitHub default branch still not switched to `main` (proxy 403); Docker images never
built.
