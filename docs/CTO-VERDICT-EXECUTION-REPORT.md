# Execution report — CTO verdict of 2026-08-09

**Scope:** STEP −1 through STEP 3d of `docs/CTO-VERDICT-2026-08-09.md`, plus the ALSO FIX list.
**Status:** complete. **B2 is unblocked.**
**Branch:** all work on `main` (`e4a9789`). Every commit CI-green on GitHub.

Suite at the end: **1,174 passed / 2 skipped** (default lane) and **1,168 passed / 8 skipped**
(pass-through-disabled lane), from a starting point of ~1,063.

---

## 1. The ruling, and why it reversed the previous plan

The verdict ruled the architecture question **(c)**: one shared generation core, with
`digitize_image` and `rebuild_design` as thin wrappers. It also **inverted the ordering** of the
work that was queued.

The previous plan was to chase rebuild toward parity with digitize. The verdict's measurement
showed digitize was itself the defect:

| | digitize | rebuild ("lossy") |
|---|---|---|
| consecutive stitches under `MIN_STITCH_MM` | **44.4%** | 2.1% |
| under `MIN_PENETRATION_MM` | **36.8%** | 0.4% |
| machine time | **21.3 min** | 8.4 min |

Parity executed perfectly would have taken rebuild from 0.4% to 40.0% floor violations and
doubled machine time. **Fix the reference first.**

---

## 2. What was done, with measurements

### STEP −1 — the travel resampler's floor was 2 *pixels*, not 2 millimetres (`7e2290d`)

`resample_inside` halved its travel pitch until chords cleared the boundary, bottoming out at
`while pitch >= 2.0` — **2.0 pixels**, about a tenth of a millimetre at the working resolution.
On every concave boundary it re-injected exactly the sub-floor penetrations `_coalesce_short` had
removed one line earlier. **70.8% of every shipped stitch on fixture 01 was manufactured there.**

A second cause: a travel run could cost arbitrarily more than the jump it replaced. New
`DETOUR_COST_MAX = 2.0`, chosen by sweep on machine time.

| fixture | stitches | sub-0.5 mm | machine-min |
|---|---|---|---|
| 01_flat_2color_logo | 17,078 → **8,749** | 44.4% → **3.8%** | 21.4 → **13.7** |
| 07_circular_badge | 45,793 → **34,665** | 29.9% → **14.9%** | 58.0 → **46.5** |
| 05_wordmark_caps | 2,518 → **1,864** | 15.0% → **1.0%** | 3.4 → **2.7** |

The bench had measured stitch counts for a whole phase and **never once asserted a fixture was
sewable**. Added `sub_floor_share` and `machine_minutes` (time *including* 2.5 s per trim, so a
routing change cannot shift cost sideways from stitches to trims and look like a win).

### STEP 0 — the two paths now share their finishing parameters, as functions (`1cc9cc6`)

`route_pad` was 8 px on digitize and 2 px on rebuild, because rebuild's copy omitted the
border-overhang term. Measured on P1's own ring, rebuilt after a real 1% density edit:
**98 needle paths straight across the open counter → 1.** Digitize output bit-identical.

Shared as **functions, not constants** — copying is what caused the drift. A structural test walks
the AST of every module and fails if a second copy of a derived quantity appears.

### The three defects `250e850` left behind (`4e57069`)

My own prior commit. Two of the three were **silently deleting an object**.

| | before | after |
|---|---|---|
| 05_wordmark_caps | 1,058 st · worst −86.6% · **5/6 objects survive** | 1,368 st · worst **−6.8%** · **6/6** |
| 06_wordmark_script | 733 st · worst −85.0% · **6/7 survive** | 1,263 st · worst **−18.9%** · **7/7** |

- **R1** the underlay stayed on the bounding rect while the column above it followed the spine —
  on a ring the underlay leaves the column and is sewn on bare fabric. *This was my regression.*
- **R2** pull compensation applied twice.
- **R3** the auto-angle gate was **tighter than its own noise floor**: 0.15° against
  requantization noise measured up to 3.7°. Five of seven untouched script columns were being
  sent to the very path B1.5 had moved them off.

### Four more dropped generator arguments (`a9ab6fa`)

Found by an independent four-lens audit, then verified at the line. Trims on an edited rebuild:
02_logo_fine_text **12 → 5**, badge **63 → 55**. The silent object delete now **raises**.

Also: `Design.fabric_type` existed all along and rebuild ignored it, using cotton constants — so
editing one object on a fleece design re-stitched it with cotton underlay spacing.

### STEP 1 — the parity signal restored (`556c670`)

P6 asked "does rebuilding an unedited design reproduce its stream?" and asserted stitch counts,
coordinates **and** commands — all comparing `d` to `d`, because the pass-through returns the same
object. **It could not fail.** Six probes were hollowed out the same way.

With the short-circuit disabled, here is what had been invisible:

| fixture | digitize | regenerated | ratio | worst object |
|---|---:|---:|---:|---:|
| 01_flat_2color_logo | 8,374 | 9,084 | 1.08 | −4.9% |
| 07_circular_badge | 10,759 | 10,322 | 0.96 | **−36.2%** |
| 02_logo_fine_text | 7,296 | 6,821 | 0.93 | **−23.1%** |

Every probe now runs on **three paths**: digitize, rebuild-unedited (forced), rebuild-after-a-real-edit.

### STEP 2 — a second CI lane with the pass-through disabled (`8659ce2`)

Rather than read for the hollowed-out regressions, I found them empirically.
`STITCHIQ_NO_REBUILD_PASSTHROUGH=1` makes every rebuild regenerate; anything that only passed
because of the short-circuit fails and names itself. **Exactly seven did** (the verdict predicted
≥5). Five legitimately have the pass-through as their subject and are marked; two were hiding real
properties and were rewritten.

One of those two returned a genuinely good answer that had never been asked: **rebuild reaches a
fixed point in one pass** — digitize 8,903 → first regeneration 9,664 → then bit-identical
forever. That is the real C6 guarantee, now provable.

CI backend time roughly doubles to ~45 min. That is the cost of closing this defect class.

### STEP 3a — a fill was a property of *where the object sat* (`61d6854`)

| probe | before | after |
|---|---:|---:|
| grow the canvas, region untouched | 0.83 px | **0.0 px** |
| translate the object +100 px | **35.16 px** | ~3e-14 |

35 px is a different row phase entirely. Consequences, worst last: the two paths could never agree
on the grid even in principle; deleting one object re-phased the fill of every object left alone;
and **B2 is move/scale/rotate** — moving an object would have silently restitched it.

### STEP 3b — rebuild works on the raster digitize actually used (`98ce364`)

digitize rasters at **0.075 mm/px**; rebuild was picking **0.1 mm/px** from the object bounding
box. New `Design.source_mm_per_px`. Mean worst-object loss **16.6% → 12.0%**; mean |ratio − 1|
**0.042 → 0.028**. Not uniform — 05's worst object got slightly worse and 02's total ratio moved
further from 1.0, both recorded rather than averaged away.

### STEP 3c — one satin implementation, two callers (`4e8551c`)

`generation.spine_satin` is now the only implementation; `rebuild.py` no longer reads
`SATIN_MAX_W_MM` or `SATIN_MAX_UNCOVERED` at all. **Verified behaviour-preserving:** stitch-stream
hashes byte-identical before and after on four fixtures, on both paths.

Scoped deliberately: classification stays in `pipeline.py`. Deciding *from pixels* whether a region
should be satin is digitize's job and rebuild must not do it, because the stored object is the
user's intent. What both must agree on is what a **decided** object becomes.

### STEP 3d — re-pinning must now pass the quality bands (`e4a9789`)

The hash was never the problem — it catches *any* change, which is right for perf work. **The weak
point was re-pinning:** one command, no questions. That is how the STEP −1 regression got locked in
as the baseline with every gate green.

`STITCH_LOCK_WRITE=1` now **refuses to write** a stream that fails its bands. Verified end-to-end:
with the badge's band set to an impossible 1.0 min, the re-pin was refused and the lock file was
left byte-identical.

---

## 3. The ten divergences

Every one was the same shape — same generator, different arguments — and **none was catchable by a
stitch hash**, because the hash moves with the regression.

| # | quantity | digitize | rebuild |
|---|---|---|---|
| 1 | `route_pad` | 8 px | 2 px |
| 2 | fill coalesce clamp | row pitch honoured | ignored |
| 3 | penetration floor | passed for satin | never |
| 4 | border sweep width | derived twice, identically — waiting to drift | |
| 5 | satin underlay axis | medial axis | bounding-rect midline |
| 6 | pull compensation | once | **twice** |
| 7 | wide-remainder pitch | fill row pitch | satin column pitch |
| 8 | wide-remainder angle | measured | silently 0.0 |
| 9 | PARALLEL underlay angle | the real row angle | a stale stored one |
| 10 | trim gate | `TRIM_MIN_GAP_MM` | unconditional |

Numbers 7 and 8 were invisible to the corpus by construction: `row_mm` and `satin_mm` coincide at
0.40 mm on cotton, and all ten bench fixtures are cotton.

---

## 4. Corrections to my own work — flagged, not buried

1. **My STEP −1 metric was wrong.** Graded on sub-0.5 mm alone, STEP 0 reads as a 24× regression.
   The entire gap is the tatami row connection — one row pitch by construction, industry-standard
   at 0.4–0.45 mm. At the real damage threshold the paths are at parity (**1.0% vs 0.8%**). Both
   lines are asserted now. The badge's "worst in corpus 14.9%" is **1.2%** at that threshold.
2. **R1 was my own regression.** `250e850` gave rebuild's satin top layer the spine and left its
   underlay on the rect midline — worse than either alone on curved satin. Ruff had been flagging
   the unused `axis_pts` and I read past it.
3. **"~18 px/mm" was never measured.** I had read it off the constants. The measured value is
   **13.3 px/mm**; four comments corrected.
4. **I expected the trim gate to be a large machine-time win. It is not.** On fixture 01 rebuild
   already trimmed *fewer* times than digitize (58 vs 77). Its value is correctness plus ~37 s
   across two fixtures.
5. **I wrote P2's lock criterion out by hand** in a new file and produced a *stricter* rule than
   P2's own — it failed all three paths including digitize, which P2 passes. It is imported now.
   Exactly the STEP 0 lesson, one commit later.

---

## 5. Still open — recorded, not certified

- **Residual parity gap:** badge **−25.5%**, fine-text **−20.0%** worst-object on regeneration.
  Banded where they actually are.
- **The badge's arc lettering is illegible** and its upper-left ring has gaps. Verified
  pre-existing (2,573 of 630,436 px changed). Small curved satin text — **B3/B4** territory.
- **P3** remains the one strict xfail: 102 st/letter against the ≥150 target — **B4**.

## 6. Other work shipped in the same window — outside this verdict

**This section was missing from the first version of this report, and its absence was a
reporting failure.** The rule going forward: every workstream gets a line in every report, whatever
its scope, and regardless of how low-risk I judge it.

**Atelier frontend redesign — `56f5709` (P1), `ad76331` (P2).** Owner-directed, not part of the CTO
plan. The owner wrote *"I have also updated the frontend so add that new frontend prepared by Claude
Design and remove the old one"*, then supplied a design handoff bundle
(`docs/design/ATELIER-HANDOFF.md` with its reference comp), then confirmed continuing.

- **P1** — token layer, fonts, and `data-theme` moved from `.dz-root` to `<html>`. Colour literals
  in `index.css` 74 → 8, by repointing token *definitions* rather than editing consumers. The
  Studio became themable for the first time. Two latent breakages caught by reading: a
  `.dz-root[data-theme='light']` block that could never match again, and a startup path that would
  have brought the Studio up light.
- **P2** — ⌘K command palette and mobile tab bar. Found a cascade bug in the shipped design file:
  the tab bar could never appear at any width, because its `display: none` sat after the media
  query setting `display: flex`. Verified with twelve browser checks.
- Frontend gate on both: tsc clean, vitest 186 passed, build clean. **No backend code touched.**

**P3–P5 are halted** pending the owner's confirmation, per the CTO ruling.

## 7. Blocked on the owner

1. **Live RLS is not applied.** S3 is open in production until an operator runs
   `db/migrations/001_identity_rls.sql` and `apps/backend/scripts/verify_rls.py`.
2. **The GitHub default branch is `feat/studio-dashboard`**, 143 commits behind. The agent proxy
   refuses repository-settings writes (403), so this needs a click: Settings → General → Default
   branch → `main`. Until then the three stale branches cannot be deleted either.
3. **The Docker images have never been built** — no daemon in the container.
