# 🧵 STITCHIQ — CTO Verdict: why the output is "a non-design, non-shaped thing"

**Date:** 2026-08-09 · **Audited at:** `250e850` (origin/main) · **Supersedes nothing; extends**
[`CTO-REVIEW-2026-08-07.md`](./CTO-REVIEW-2026-08-07.md)
**Method:** independent re-run of the full suite (reproduced `1063 passed, 2 skipped, 2 deselected,
3 xfailed`), first-hand probe runs, GitHub CI history, and a 9-agent fleet that reproduced every
claim empirically against the real venv — including a live Postgres 16 replica for the RLS work.

> **Read §1 first.** It answers the owner's actual question. Everything else is subordinate.

---

## 1. Why the output looks wrong — two measured causes, both fixable, neither is research

The owner's complaint is **literally true and largely a BUG**, not a missing capability.

### Cause A — the travel resampler triples the stitch count with plumbing

`_route_travel` converts needle-up jumps into sewn travel runs. Its resampler
(`resample_inside`, `routing.py:168-180`) starts at a 2.0mm pitch and **halves it whenever any
chord escapes the region**, with a floor of *2 pixels* — not 2 millimetres. Measured:

| Fixture | Stitches shipped | Share manufactured by `_route_travel` |
|---|---|---|
| `01_flat_2color_logo` | 20,131 (needs **6,646**) | **70.8%** |
| `07_circular_badge` | 45,793 | **64.4%** (29,450 stitches) |
| `05_wordmark_caps` | — | 31.6% |

On the flat logo, **59.6% of penetrations are below the codebase's own needle-safety floor**
(`MIN_STITCH_MM`), 36.8% below `MIN_PENETRATION_MM`. That is 21.3 machine-minutes for a 65mm
two-colour logo that should take ~8. On the machine this reads as thread piling along every region
edge, needle deflection and thread breaks — and visually as a shapeless mass rather than a clean
shape. **A/B-disabling `_route_travel` reproduces the 3x reduction.** Estimated fix: 1-2 weeks.

### Cause B — there is no curve primitive anywhere in the product

`DesignObject.contour` is a **dense polyline of raster samples**. Measured: badge contours carry
244-762 points at 0.27-0.38mm spacing. Total absolute turning — a clean closed shape turns ~360°,
a complex letterform 720-1400°:

| Contour | Total turning |
|---|---|
| `01` fill | **11,445°** |
| `07` badge satin | **18,937°** (median direction change **18.4°** at every 0.3mm vertex) |

`grep -r "bezier\|spline"` in the digitizer returns **nothing**. Outlines are pixel staircases, and
because satin edges are generated *from those contours*, **every satin edge wobbles visibly**. A
human digitizer works in Béziers; this product has no representation for a curve. This is the
literal, measurable meaning of "non-shaped thing" — and it is classical, well-trodden geometry
(outline fitting), not research.

### The software already knows

The shipped A9 quality scorer, run on the project's own flagship fixture, reports **6,243 tiny
stitches, 479 open-fabric travel segments, and grades the file 45/F.** The grade is correct. Nothing
surfaces it to the operator before export.

---

## 2. Verdict on the Ops+B1+B1.5 session report

**Numbers: honest. Interpretations: several are wrong, and one is probe-gaming.**

**What is genuinely true** (independently reproduced): the test accounting is exact to the digit;
**no test was deleted, weakened, or had a tolerance loosened** across all 8 commits; CI is green on
`main` for all 9 runs; `feat/studio-dashboard` really was a strict ancestor (0 commits lost); the
RLS migration is **correct and recursion-safe** (proven on a real Postgres 16 with a Supabase-shaped
role/`auth.uid()` environment: applies cleanly, idempotent, anon reads 0 rows, every anon write
refused, no recursion); the "not applied to production, no creds" disclosure is honest with no
fabricated verification anywhere; Sentry's "0 bytes without a DSN" is true (verified with two real
Vite builds); discovery 7 (Optimize no-op) survives adversarial break tests; discovery 8 (root
bypass) is real and its replacement is genuinely root-proof.

### The failures, worst first

| # | Finding | Evidence |
|---|---|---|
| **V1** | **C2 is only half-fixed — reopened by every edit.** A3's routing fix landed in `pipeline.py` only. After a 1% density edit the ring probe reads **98 counter crossings** (baseline was 92) and −55% stitches. Root cause: `rebuild.py:338` omits the `FILL_BORDER_MM/2` term that `pipeline.py:867` uses — pad **2** vs **8**. Restoring that one term: **98 → 1 crossings**, loss −55% → −20%. | Run by the CTO; the pipeline comment citing "CTO review C2/A3" sits directly above the correct formula |
| **V2** | **P6 now tests nothing.** `rebuild_design(d) is d` — the "0.0000mm worst move" is *object identity*, not fidelity. Bypassing the pass-through, P6's own assertions fail catastrophically (6,845 vs 17,078 stitches). The strict-xfail that carried the measured parity gap was deleted and nothing replaced it: **no test anywhere now measures digitize↔rebuild parity.** Reporting "P6 green" to the owner is probe-gaming. | Agent bypassed `rebuild_is_a_noop` and re-ran |
| **V3** | **The pass-through silently hollowed out ≥5 pre-existing regressions.** Sabotaging `rebuild._contour_fill` so it *raises on call* leaves **all six tests in `test_contour_fill.py` green** — including one whose docstring says it exists to catch exactly that deletion. Disable pass-through and the sabotage fails immediately. The report advertised "+18 regressions" and never mentioned the coverage it removed. | Proven by sabotage test |
| **V4** | **The destructive edit is worse than reported.** Pass-through is **all-or-nothing**, so a 1% nudge on *one* object takes the whole design 17,078 → 6,845 (**−59.9%**); the untouched object loses 12% too. On the script wordmark a 1% nudge costs −56% **and silently deletes an entire object** (`rebuild.py:352 if len(pts) < 2: continue`, no error, gone from stream and object list). | Reproduced |
| **V5** | **Two edits that must regenerate hit pass-through silently:** deleting an object, and **reassigning `color_stop`** — precisely the colour-layering surface the owner cares about. `provenance.py`'s rationale ("recolouring changes none of its stitches") is wrong at the stream level. Live on `POST /designs/rebuild`. | Reproduced |
| **V6** | **"X1's stated fix is WRONG" is itself wrong.** My review was **correct at the commit it audited** (`6d29918`: every CPU endpoint was `async def`, `run_in_threadpool` appears zero times). Their own commit `550c09b` applied my exact one-word fix six days earlier, 131 commits past my audit base. The honest statement was "already done before your review published." | `git show 550c09b` |
| **V7** | **Their replacement GIL/pydantic diagnosis is false.** A sampling profiler attributes the entire >20ms starvation to **`numpy.unique(Z_pal, axis=0)` at `planning.py:352`** (570ms), not pydantic (which contributes **zero** holds >20ms; validating all 17,084 stitches stalls the loop 6.3ms). Replacing that one line with a packed 1-D unique cuts the worst stall **556 → 88ms (−84%)** and digitize wall time **2540 → 2077ms (−18%)**, identical output. **No worker processes required.** | Profiled + patched |
| **V8** | **Deploy would break on first contact.** (a) The backend Dockerfile `apt-get purge libcairo2-dev && autoremove` **removes libcairo2 from its own runtime image**; pycairo is a source build linking `libcairo.so.2`, so `import cairo` raises and the **entire SVG/vector input path dies** on the first customer SVG. (b) The shipped default runs **4 workers against a store the repo documents as single-worker-only** — reproduced with two real processes: both signups returned success, **one account silently vanished**; plus a fixed-path temp-file race → unhandled `FileNotFoundError` → HTTP 500. (c) The root `.dockerignore` doesn't apply to the backend image (context is `apps/backend`), making DEPLOY.md's secrets claim false and shipping a **903MB context** (890MB of `.venv`). | All three reproduced |
| **V9** | **`verify_rls.py`'s write half is vacuous.** With RLS **entirely off**, all three INSERT probes still fail — on *foreign keys* (fresh uuid4s), returning 409, which the script scores as "write refused". It never distinguishes `42501` (RLS) from `23503` (FK). The read half passes on any empty table. **The script can print "RLS verified" and exit 0 against a fully open database.** | Proven against an unprotected replica |
| **V10** | **The RLS `users` policy is `for all`** — any logged-in user can set their own `subscription_tier` to `enterprise`, zero `designs_this_month`, or delete their profile row. All three demonstrated. Not exploitable today, but **B7 plans to enforce quotas on exactly those columns**: a billing bypass shipped in advance. | Demonstrated |
| **V11** | The two **deselected** timing tests are the **only** tests that catch a revert of what `98af4ee` shipped. The "structural guard" that supposedly replaces them **passes that same revert**. Deselecting them removed the regression signal. | Revert test |
| **V12** | Thumbnail "174→39ms" is **overstated** — actually 165.9 → 95.8ms p50 (~2.4x optimistic). GET 50→19ms is exact. Discovery 3's statistic is wrong ("70.2% at the 0.5mm coalesce floor" is really "70.2% ≤0.55mm", mode 0.27mm), and its aside that the A9 scorer is blind to it is **flatly false** — the scorer grades that fixture 45/F. | Reproduced |
| **V13** | **`250e850` was committed after the report and never disclosed** — the medial-axis satin work the session had recommended deferring to B3, saying "your call, not mine." It genuinely works (region thread coverage after an edit 91.2→100%, 52.3→76.3%, 61.9→79.5%) and does *not* overlap B3. But it ships **two latent bugs and zero tests**: pull compensation applied **twice** on the new spine path (inflating the width gate 0.40 → 2.20mm at pull=1.0), and an auto-vs-override angle gate so tight (±0.15°) that only **3 of 7** satin objects on the most-curved fixture qualify. | Read + measured |

---

## 3. The architecture decision — RULED

The session asked: **(a)** find the missing determinant, or **(b)** accept that an edited object is
regenerated, not reproduced. **Both are rejected. The answer is (c): one shared generation core,
with digitize and rebuild as thin wrappers — plus an amendment that inverts the ordering.**

**(a) is moot** — the determinant was found: `_route_travel`'s `pad_px` plus the raster resolution.
An agent reproduced a stored object **bit-exactly** (18,585 vs 18,585 stitches, max coordinate error
**0.000000mm**; 30 of 40 objects bit-exact across four fixtures) by running digitize's own stage
list on the object's own stored parameters. **A `DesignObject` does describe its own stitches.** The
session's diagnosis omitted exactly one stage.

**(b) is unacceptable** — it concedes that Apply and Optimize silently redesign the object (−60% of
a design today) and destroys the one claim the product is sold on.

**(c) survives adversarial review — WITH THIS AMENDMENT, which is the important part:**

> **Do not chase parity with digitize. Fix the reference first.**
> Measured: digitize puts **44.4%** of consecutive stitches below `MIN_STITCH_MM` and **36.8%** below
> `MIN_PENETRATION_MM`, at **21.3 machine-minutes**. Rebuild's "lossy" output is **2.1%** and **0.4%**
> at **8.4 minutes**. Executed perfectly, the parity plan moves rebuild from 0.4% → **40.0%** floor
> violations and **more than doubles machine time on every edited design.** Machine time is the
> owner's cost centre.

### Ordered sequence

- **STEP −1 (first, non-negotiable):** clamp `resample_inside`'s pitch floor to
  `MIN_STITCH_MM / mm_per_px` (not 2 *pixels*); reject a detour that can't be resampled at or above
  the floor so the jump survives for trimming; cap detour cost at 2-3x the direct jump it replaces.
  Re-pin the bench and add the assertion `test_quality_bench.py` lacks: sub-0.5mm share and
  `est_minutes` within a band.
- **STEP 0 (cheap, ship immediately after):** sync the two constants — `route_pad`
  (**one shared function**, called from both paths, never a copied constant) and the fill-row
  coalesce clamp. Measured by monkeypatch: **−67.7% → −6.3%** edited-object loss, touching digitize
  not at all, **zero blast radius, no re-pin.** This alone closes the user-visible defect.
- **STEP 1:** extract `generate_object_stitches(region_source, params, mm_per_px, profile, ctx)` and
  have *both* paths call it. Note the honest caveat: `iso_fills` and `_hole_covered_later` are
  whole-design state, so it is not a pure per-object function — that is a third documented fork.
- **STEP 2:** stamp `mm_per_px` onto `Design` (additive, optional); remove the canvas-centre rotation
  in `_scanline_angled` (row phase currently depends on canvas dimensions — **the same artwork at
  five upload resolutions produced 11,766-18,020 stitches**) and `resample_inside`'s pixel-quantised
  floor.
- **Gate on quality-metric bands** (stitch count, sub-floor share, coverage, est_minutes) **not exact
  hashes** — exact-hash gating is what let a 4.8x stitch inflation sit uncontested against a stale
  baseline for a whole phase.

---

## 4. The model cannot express professional work — 11 gaps

`Design.stitches` is the authoritative artifact (**98.0%** of a 1.2MB badge design's JSON is the flat
stitch array); `DesignObject` is an advisory annotation. Ordered by what blocks the owner's goal:

| Gap | Type | What it blocks |
|---|---|---|
| **Curves** — `contour` is a dense polyline; no Bézier/arc/spline/node type/handles | **MODEL** | Clean shapes, resize, re-noding. *The deepest gap.* |
| **`stitch_start`/`stitch_end`** index range | **MODEL** | Per-object regeneration. `pipeline.py:935` **already passes `stitch_start` and Pydantic discards it** — cheapest high-value change in the codebase |
| **`z_index`** — stack order is the accident `(color_stop, sequence_order)` | **MODEL** | Layering. Proven: objects rebuilt B,A,C — `sequence_order` is subordinate to thread assignment |
| **`coverage` + `row_phase`** | **MODEL** | **All shading.** Needle-blending needs two objects on one region at ~50% density with interlocking row offsets. Inexpressible today |
| **`density_ramp`** | **MODEL** | Gradients. Measured: a 124-object peacock photo design carries exactly **two** distinct density values, both inherited from the cotton profile |
| **Knockout/clip** — `holes` is baked geometry, not a live relation | **MODEL** | "Remove overlaps" doesn't exist as a concept |
| **Transforms** — geometry is absolute baked mm, no matrix | **MODEL** | Resize can't re-apply size-dependent density/pull rules |
| **`entry`/`exit` semantics are INVERTED** — pure outputs, overwritten every rebuild | **SEMANTICS** | Hiding connections under the next object |
| **`connect_method` is dead metadata** — read by nothing; rebuild always emits TRIM+JUMP | **ENGINE** | Travel runs vs trims |
| **Tie/lock params are global constants** | **MODEL** | Per-fabric, per-object tie control (no ties on a 6-stitch detail) |
| **Motif fills** — enum members were removed in Part 43 because they silently produced tatami | **BOTH** | Texture variety (10 stitch types vs a pro suite's 30+) |

---

## 5. The roadmap to replace $100K/month of designers

**Governing principle: the money is NOT in fully automating hard jobs.** It is in (a) fully
automating the easy tail, and (b) cutting the *median* job from ~40 minutes to ~12. A designer who
edits is far cheaper than a designer who starts from a blank canvas. **Optimise median job time and
measure it weekly.**

- **Phase 0 — "stop shipping broken files" (weeks 1-6).** STEP −1/0 above + `stitch_start/end` +
  `z_index` + real thread catalogues with ΔE2000 + needle numbers + a minimum-sewable-feature gate
  before SATIN. Outcome: flat logos drop 20,131 → ~6,600 stitches, sub-0.5mm penetrations 59.6% →
  <3%, machine time ~3x lower, every colour stop names a purchasable thread and a needle.
  **Metric to instrument now: what share of auto outputs does a designer choose to *edit* rather
  than redo from scratch?** Today ≈0. Target 30%.
- **Phase 1 — "flat logo autopilot" (months 2-4).** Bézier outline fitting + curve-driven
  satin/fill, sequencing, primitive fitting (straight edges straight, circles round, symmetry).
  Target: vector art (**the pipeline already has an exact `svg-vector` path that skips segmentation
  guesswork**) and clean flat raster logos ≤6 colours. Typically **35-50% of tickets** — *measure
  this from the archive in week 1; it is the single most important business input.* Those jobs go
  30-45 min → 5-10 min of review. At 40% share that is roughly **$25-30K/month**.
- **Phase 2 — "human in the loop for everything else" (months 4-8) — the biggest dollar phase.**
  Non-destructive editing on Phase 0's index ranges, live knockout, per-object regenerate, a real
  object tree, version history. The other 50-65% of volume isn't automated — it gets a *good first
  draft*. Target median job time −40-60%. **Critical second function: every designer correction
  becomes a labelled training pair. This phase is the data-collection engine, which is why it must
  precede all ML work.**
- **Phase 3+ — learned segmentation and detail triage (months 8-14+)**, trained on the owner's own
  archive of image→final-design pairs. That archive is an asset **no competitor has**.

**Start capturing now, before any of this ships:** every input image, every designer's final file,
every intermediate Photoshop artifact, and every correction made to an auto-generated draft.

---

## 6. Immediate action list

1. **Fix `resample_inside`'s pitch floor** (STEP −1) — biggest single quality win, 1-2 weeks.
2. **Sync `route_pad` via one shared function** (STEP 0) — closes V1, ~1 day.
3. **Restore a real parity signal** — reinstate P6's measured assertion behind the pass-through, and
   extend every §8 probe to three paths: digitize, rebuild-unedited, **rebuild-after-a-real-edit**.
4. **Fix the ≥5 hollowed-out regressions** (V3) — run them with pass-through disabled in CI.
5. **Before any deploy:** stop purging cairo; set workers to 1 (or make the store multi-process safe);
   add a backend `.dockerignore`.
6. **Fix `verify_rls.py`** to distinguish 42501 from 23503, and narrow the `users` policy from
   `for all` to `select, update(name)`.
7. **One-line `numpy.unique` fix** at `planning.py:352` — −84% loop stall, −18% digitize time.
8. **Owner actions:** apply the RLS migration to live Supabase; switch the GitHub default branch to
   `main`; start the archive capture in §5.

---

*Prepared by the CTO review session. Every number here was reproduced against the code at `250e850`
in this session — none is taken from the build session's report on trust.*
