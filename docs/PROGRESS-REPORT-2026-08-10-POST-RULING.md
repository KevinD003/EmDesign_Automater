# Progress report — execution of the CTO ruling of 2026-08-10

**For review.** Self-contained: a reviewer needs this file, `CTO-RULING-2026-08-10.md` (the
instructions being executed) and `CONSOLIDATED-REPORT-2026-08-10.md` (the state before it). Picks up
exactly where the ruling left off and covers everything to `9918397`.

## Provenance rule, applied throughout

The ruling set a standing requirement:

> When you next report a headline number, state how it was produced — ran the shipped code, ran a
> probe, or re-derived by hand — and treat the last two as provisional until the first is done.

**Every number in this report was produced by RUNNING THE SHIPPED CODE.** Where a before/after
comparison appears, "before" was produced by checking the parent commit out into a `git worktree`
and running the same entry point there — not by reimplementing it, and not from memory. This
distinction is not decorative: the previous report's single worst error was quoting numbers from a
reimplementation of `fills.py` as though they came from the code, and overstating a result 3.3×.

Two probe scripts were written to answer questions the shipped instrumentation could not. They live
in the session scratchpad, not the repo, and every figure they produced is reproduced below with the
code path it measured.

---

## 1. What landed

| # | commit | item | ruling § |
| --- | --- | --- | --- |
| 1 | `a95df3e` | Zhang-Suen parity fix + the density gate it tripped | 5.1 / priority 1 |
| — | — | classification width survey re-run on the stable skeleton | priority 1 |
| 2 | `bedc998` | UP1 — satin's per-side pull compensation, both halves | priority 2 |
| 3 | `9918397` | DET3 — substrate removal, all four parts | priority 3 |

All three are shipped-code changes affecting every upload. Both CI lanes were run to completion
before each commit; no commit was pushed on a partial verification.

| commit | lane 1 (default) | lane 2 (`STITCHIQ_NO_REBUILD_PASSTHROUGH=1`) |
| --- | --- | --- |
| `a95df3e` | 1221 passed | 1215 passed |
| `bedc998` | 1221 passed | 1215 passed |
| `9918397` | 1229 passed | 1223 passed |

---

## 2. The parity fix (`a95df3e`), and the gate it tripped

### 2.1 The change

`skeleton.py` computed Zhang-Suen's checkerboard parity as `(row + col + y0 + x0) % 2`, where
`y0`/`x0` are the region's offset **on the canvas**. The same artwork cropped or re-exported one
pixel differently thinned differently, so its medial axis moved, so its measured stroke width moved,
so it could be classified satin instead of tatami. Now `(row + col) % 2` — intrinsic to the window.

Landed alongside: deterministic branch discovery (`dict.fromkeys` over the point list, an explicit
`node_order`), and the no-axis arm split into `no_medial_axis` (a speck) versus `compact_no_axis` (a
disc) so a width survey can tell a 168 mm² disc from a 3 mm² freckle.

### 2.2 The density gate — investigated, not re-pinned

Landing it moved fixture 08's densest cell 13 → 14. `DENSITY_FLAG_PER_CELL` **is** 14, so
`flagged_cells == 0` and `max_per_cell <= 13` could not both survive. The previous revision of that
test carried an explicit tripwire — *"If a later change puts a 14 here, that is a genuine 'second
full layer' on a real cell and must be investigated, not re-pinned."*

Measured, shipped code, both trees:

| metric | before (`1431383`) | after (parity) |
| --- | --- | --- |
| `max_per_cell` | 13 | **14** |
| `p99_per_cell` | 5 | 5 |
| `flagged_cells` | 0 | **1** |
| `max_per_disc` (grid-free) | 23 | **26** |
| cells at the max | 1 | 1 |
| tail, top 12 | 13, 12, 9, 8, 8, 8, 8, 7, 7, 7, 7, 7 | 14, 12, 9, 8, 8, 8, 8, 7, 7, 7, 7, 7 |
| penetrations | 8,080 | 8,091 |
| objects | 20 | 20 |

Only the top entry moves. **It is not a density shift.**

The site is a **coincidence of two satin objects**, established with `cv2.pointPolygonTest` against
each object's stored contour at (35.93, 65.03):

| object | type | stitches | signed distance |
| --- | --- | --- | --- |
| `Satin 1 (#de6c26)` | SATIN | 3,905 | −0.15 mm |
| `Satin 19 (#30221e)` | SATIN | 53 | −0.05 mm |

- **`Satin 1` supplies ~17 of the 26**, at penetration indices 1767–1881, arriving as *alternate*
  ends of a column zigzag — successive penetrations 2.6–4.7 mm apart, every other one landing in the
  same 0.5 mm disc. Identical before and after the fix.
- **`Satin 19` supplies the +3, and it is a tie-off.** After: five consecutive penetrations entered
  by `JUMP@8071`, steps 0.617 / 0.342 / 0.700 / 0.610 / 0.610, the last returning to exactly
  `(36.006, 64.803)` — the coordinate of the second. Before: the same signature with three members
  revisiting `(35.869, 64.717)`. This matches the design's own final tie-off at stream 8155–8157
  (steps 1.0 / 0.707 / 0.707, returning to its anchor).

**The ruling's third bullet — "the site is a lock" — is correct about the delta and incomplete about
the site.** Most of the density there predates the fix and comes from `Satin 1`.

### 2.3 The gate now discriminates cause

- `p99_per_cell <= 6` — **kept verbatim**; the real density-shift detector, and it did not move.
- `max_per_disc <= 26` — **new**; translation-invariant, so unlike `max_per_cell` it cannot be a grid
  artefact.
- `flagged_cells <= 1` — relaxed by one, **and** every flagged cell must now prove it is a tie-off by
  containing a coordinate revisit in its neighbourhood.

The count bound is weaker; the gate is stronger where it matters. A change that piles **fill** into a
cell has no coordinate revisit and now fails, where the old form would have passed it at 13. Two
tests assert the discriminator answers **no** to dense stitching with no revisit and **yes** across a
grid straddle — a check that cannot say no is worse than no check, because it reads in a diff as a
safety assertion.

Full detail: `docs/DENSITY-LOCK-SITE-2026-08-10.md`.

---

## 3. Classification width survey on the stable skeleton — expectation refuted

The ruling directed: *"Re-run the classification width survey afterwards: the four flagged objects
may change."* Ran `scripts/measure_classification_width.py` on both trees.

| | pre-parity (`1431383`) | stable skeleton |
| --- | --- | --- |
| objects surveyed | 25 | 25 |
| decisions changed | — | **none** |
| objects flagged SATIN-over-width | 1 | **1, identical** |

`07_circular_badge` seq 3 reads the same on both: judged 3.62 mm, measured 6.98 mm (1.9×), 97 % of
the band over the cap, bimodal. The only movement anywhere is sub-0.2 mm jitter in `judged` on five
objects (03 seq 1: 3.12 → 2.93; 06 seq 2: 1.52 → 1.48; 05 seq 5: 3.19 → 3.16; 08 seq 5: 6.90 → 6.92;
03 seq 2: 5.46 → 5.40) and branch-count changes from the now-deterministic branch discovery (03 seq
2: 6 → 16 branches; 05 seq 4: 3 → 1).

**So the expectation that the flagged set would change is refuted on this bench.** The survey was
already stable; the parity fix does not move classification here.

### 3.1 Input for the deferred area-over-cap veto (5.3)

The survey flags on `true_w`, which is only computable for roughly-annular shapes. Three SATIN
objects have an **area-weighted** width over the 4.5 mm cap, not one:

| object | judged | areaW | true | flagged? |
| --- | --- | --- | --- | --- |
| 07_circular_badge seq 3 | 3.62 | 4.92 | 6.98 | yes |
| 08_mascot_detail seq 1 | 3.70 | **5.61** | — | **no** |
| 08_mascot_detail seq 2 | 3.00 | **4.88** | — | **no** |

A veto built on `true_w` misses both mascot objects. Built on `areaW` it catches all three. That is
the threshold input the ruling asked to be set on the stable skeleton.

---

## 4. UP1 (`bedc998`) — satin's pull compensation

### 4.1 Both halves of the defect

**Half one, `generation.py`.** `pull_mm` is documented per side and applied per side to fills:
`_dilate_pull` dilates by `pull_mm / mm_per_px`, and a dilation grows a mask by its radius on every
side. Satin took `(pull_mm / 2) / mm_per_px`. From one stored number a satin stroke and the fill
beside it were compensated by different amounts — the satin 2× under-compensated, pulling in on
stretchy fabric and opening a gap along the seam it was meant to close.

**Half two, `columns.py`.** A column whose boundary sat at or past the satin cap landed exactly on
`max_half_px` with **no** pull compensation, while every narrower column on the same stroke grew by
it. Compensation switched off at precisely the widest columns — the ones that pull in hardest.
`_raycast_columns`, the per-branch fallback doing the same job three functions down, has always
clamped and *then* added. The two generators disagreed.

### 4.2 Effect, measured

p90 sewn column width — the cleanest read, since the mean is diluted by travel and by crossings split
at `max_step_px`:

| fixture | fabric | `pull_mm` | p90 before | p90 after | Δ |
| --- | --- | --- | --- | --- | --- |
| 05_wordmark_caps | cotton | 0.20 | 3.763 | 3.967 | **+0.204** |
| 05_wordmark_caps | fleece | 0.50 | 4.012 | 4.518 | **+0.506** |
| 06_wordmark_script | cotton | 0.20 | 2.353 | 2.502 | +0.149 |
| 06_wordmark_script | fleece | 0.50 | 2.604 | 3.079 | **+0.475** |
| 04_thin_line_outline | cotton | 0.20 | 1.103 | 1.290 | **+0.187** |
| 04_thin_line_outline | fleece | 0.50 | 1.619 | 1.875 | +0.256 |

Satin grows by the full `pull_mm`, as fills always have.

Bench aggregate: stitches **65,018 → 64,912** (−106, −0.16 %), machine-minutes 85.480 → 85.400.
Quality moved slightly the right way where it moved at all:

| fixture | sub-floor share | stitches < 0.5 mm |
| --- | --- | --- |
| 07_circular_badge | 0.0316 → **0.0304** | 541 → **520** |
| 08_mascot_detail | 0.0544 → **0.0515** | 438 → **411** |
| 03_gradient_soft | 0.0106 → 0.0105 | 89 → 88 |
| 06_wordmark_script | 0.0899 → 0.0908 ✗ | 162 → 162 |

**`satin_share` and `coverage_ratio` are identical on all ten fixtures.** That was the check that
mattered: pull compensation still cannot reach the satin-vs-tatami decision. That was R2 and it stays
fixed.

### 4.3 A coverage gap in the bench, not in UP1

**All ten bench fixtures are cotton, `pull_mm` 0.20.** Knit is 0.40, jersey 0.45, fleece and towel
0.50. The bench understates this fix by 2.5× and cannot see fabric-dependent defects at all. Flagged
as a corpus problem for the CTO; not something UP1 should have changed.

### 4.4 Gates

- **Stream locks re-pinned** under `STITCH_LOCK_WRITE=1`, which refuses a band-violating write. Badge
  `sub_floor_share` 0.0317 → 0.0305 and `sub_penetration_share` 0.0025 → 0.0024; script
  `sub_penetration_share` 0.0110 → 0.0095, stitches 1,841 → 1,823; 04 stitches 1,874 → 1,882.
- **Seven visual baselines regenerated.**
- **`test_rebuild_satin_residuals`** asserted the literal source string `"(pull_mm / 2.0) /
  mm_per_px"`. It had **pinned the defect as the contract** and failed when the defect was corrected.
  It is named for the double-count, not for how much pull is applied; it now asserts through the AST
  that pull reaches the half-width argument at all.
- **`test_probes_three_paths`** badge worst-object band 0.32 → 0.34. This is the one judgement call
  in the commit and is set out in full below.

### 4.5 The one judgement call

Aggregate digitize↔rebuild divergence **improved**; one 46-stitch object went the other way.

| object | digitize | rebuild | loss before → after |
| --- | --- | --- | --- |
| Satin 15 | 43 → 46 | 35 → 31 | −18.6 % → **−32.6 %** |
| Satin 16 | 33 → 36 | 27 → 27 | −18.2 % → −25.0 % |
| Satin 5 | 26 → 29 | 18 → 25 | −30.8 % → −13.8 % |
| **total stream ratio** | | | **1.0217 → 1.0153** |

Instrumented `rebuild` to rule out a path split: **all 14 of the badge's satin objects go through
`generation.spine_satin` and all 14 are viable**, so both paths receive the correction. The residual
is the contour round trip — digitize rasterises the source image, rebuild rasterises the stored
polygon — and on a 46-stitch object a few pixels of polygon approximation is ±7 %.

That is 3e-i's subject, and the ruling holds 3e-i back from any change that alters either path's
stream. UP1 alters the stream. So it was recorded, not chased. The band was widened by the measured
0.6 points plus 1.4 of headroom, deliberately not to a round number that would absorb a future
regression unnoticed.

---

## 5. DET3 (`9918397`) — substrate removal

### 5.1 The headline

A white ring and bar on a **transparent** background, before and after:

| | before (`bedc998`) | after |
| --- | --- | --- |
| stitches | **0** | **1,960** |
| objects | **0** | 2 |
| colour stops | 0 | 1 |

The entire design was deleted, and the only warning emitted was an unrelated note about colour count.
A transparent PNG has its alpha composited onto white, so white artwork on transparent becomes white
artwork on a white page, matches a white border, and is removed as "the garment".

### 5.2 The four parts

**(d) The alpha channel is a declaration.** Compositing answers *what colour is this pixel* and
discards *is this pixel artwork* — precisely what the substrate rule was reduced to guessing from the
border. SVG input was already exempt because its mask is declared rather than inferred; an alpha
channel is the same kind of statement. `_decode_raster` returns the mask alongside the image;
`_decode_image_bgr` remains as a wrapper on the package's exported surface.

A declaration must **partition** the image, and an alpha channel fails that at both extremes — fully
opaque (what many exporters attach to artwork with no transparency; says nothing about background)
and fully transparent (says nothing about which pixels are design). Both are treated as no
declaration.

**(a) The garment colour is an input.** `substrate_color="#RRGGBB"` or a BGR triple. Verified it
decides the outcome rather than merely being accepted:

| call | stitches | removed |
| --- | --- | --- |
| border guess (default) | 4,176 | 2,321.9 mm² @ `#142850` |
| declared `#142850` (the navy) | 4,176 | 2,321.9 mm² @ `#142850` |
| declared `#dcaa28` (the gold) | 4,257 | **1,037.4 mm² @ `#dcaa28`** |

Declaring the colour the guess already found is byte-identical. An unparseable value raises instead
of falling back to the guess: a substrate the caller asked for and did not get would delete different
artwork than either party intended, which is the defect the parameter closes.

**(b)/(c) The removal gets its own channel.** `substrate_removed_mm2`, `substrate_color_used` and
`substrate_color_declared` on the `Design` (and the TypeScript mirror), plus a warning naming the
area and the colour. A *guessed* substrate says it was guessed and invites correction; a declared one
does not. This matters because `substrate_owned` is subtracted from **both** coverage bases — a
design could lose a fifth of its foreground and every quality metric would still read as if it had
sewn everything.

### 5.3 Two adjacent things fixed rather than left

- The **textured retry** re-enters `digitize_image` and would have dropped the caller's
  `substrate_color`, so the retry would delete different artwork than the first pass.
- The **structural determinism test** pinned the decode by the literal name
  `"_decode_image_bgr(data)"`. With the call renamed it would have found nothing and asserted on
  `-1` rather than failing. It now matches the decode *step*, the claim being about ordering.

No baseline or lock moved: the bench is entirely opaque input, so the rule's behaviour there is
unchanged by construction.

---

## 6. Process failures in this stretch

Recorded because the previous report's reviewer said the self-reported failures are what make the
rest credible.

1. **The fixed-box mistake, made twice, after being told about it.** The ruling asked for a probe
   "built around the lock geometry rather than a fixed box". The first density probe judged run
   structure **per cell** — so a tie-off oscillating across a 0.5 mm boundary read as 13 singletons
   and was reported `looks_like_lock: false` for a genuine lock. The test helper then repeated it
   verbatim, reporting "not a tie-off" for a lock whose revisited coordinate bins one cell over. Both
   are now pinned as tests.

2. **A bug I introduced in DET3 and nearly shipped.** An all-transparent alpha was treated as a
   declaration, so it skipped the substrate rule on a blank canvas and pushed the whole image into a
   full-canvas distance transform. `test_fully_transparent_rgba` asserts only "no 5xx", so it passed
   — the **only** evidence was pytest's warning count going 1 → 2. Found by chasing that, fixed, and
   pinned by its own test.

3. **An arithmetic error reported to the owner.** The bench stitch total was stated as
   60,853 → 60,712 (−0.23 %). The correct figures from the summary JSONs are **65,018 → 64,912**
   (−106, −0.16 %). The conclusion — the total barely moves — is unchanged.

4. **A test that had pinned a defect as a contract.** `test_rebuild_satin_residuals` asserted the
   literal string `"(pull_mm / 2.0) / mm_per_px"`, so correcting UP1 failed it. Worth generalising:
   a source-text assertion pins the *spelling*, and the spelling of a buggy line is not a contract.

---

## 7. Open items

### 7.1 Opened by this stretch (new, not on any prior list)

1. **`Satin 1`'s column-end pivot puts ~17 penetrations in one 0.5 mm disc.** Pre-existing on both
   trees, untouched by anything here, and the larger half of the corpus's worst density site. Never
   examined. This is a satin column geometry question — the inner side of a tight turn re-using its
   pivot — not a flag-level question.
2. **`sum(object.stitch_count)` is 8,001 against 8,091 actual penetrations on fixture 08** — 90
   unattributed, on both trees. It did not affect anything above, because the probe checked the
   totals and fell back to whole-stream attribution rather than inventing object boundaries. It
   **blocks the real-artwork comparison harness**, which the ruling specifies must measure per-object
   stitch-type agreement against an expert machine file.
3. **The bench is entirely cotton.** It structurally understates UP1 by 2.5× and cannot see
   fabric-dependent defects at all.

### 7.2 Remaining from the ruling

- **SH2** — bare-fabric moats, up to 443 mm² at a 200 mm hoop, with `TEXTURE_RETRY_UNCOVERED`
  re-derived rather than assumed.
- **The physical-units contract** (SZ1 / SZ3 / SZ4 / UP2 / UP3 / UP4) as its own tranche, not
  interleaved, re-pinned at a hoop above 133 mm.
- **The real-artwork landing site** — a loader for real job pairs as a corpus tier kept strictly
  separate from A/B/C; a comparison harness against the expert's machine file; and
  `build_corpus100.py` made reproducible on a fresh checkout.
- **Deferred**: the area-over-cap veto (5.3) — its threshold input is now measured, §3.1 above; 1c;
  3e-i, which must not overlap a stream-altering change.
- **Stays open, unabsorbed**: 5.2 (+6 trim divergence), 5.4 (knockout policy), 5.5 (veto dissent).

### 7.3 Diagnosed but not yet fixed — `build_corpus100.py`

Read during this stretch; the fix is not written. `tier_a()` reads the three real photographs from a
**hardcoded session scratchpad path**, not from the tracked copies already in the repo at
`tests/fixtures/corpus100/A0{1,2,3}*.png`. On a fresh checkout that path does not exist, so:

1. tier A silently drops 13 → 10;
2. `reals` is empty, so `tier_b` returns immediately — **40 → 0 images**, silently;
3. tier C is then asked for `100 − 10 = 90` instead of 47;
4. and because one module-level `RNG` is consumed in draw order across all tiers, tier C's parametric
   stream moves too.

A fresh checkout produces a 10 / 0 / 90 corpus while the audit trail says 13 / 40 / 47, with no
warning. 87 of the 101 files are untracked, so regeneration is the only path back to the corpus. The
fix is to read tier A from the repo copies, fail loudly on a missing tier-A source rather than
shrinking, and give each tier its own seeded generator.

---

## 8. Questions for the reviewer

1. **§4.5** — the badge fidelity band 0.32 → 0.34 is the only judgement call landed here. Aggregate
   divergence improved and the residual is attributed to the contour round trip, which is 3e-i's
   territory and fenced off by the ruling. Is deferring correct, or should 3e-i be unblocked?
2. **§2.3** — the density gate now trades a weaker count bound for a cause test. Is "a flagged cell
   must contain a coordinate revisit in its neighbourhood" the right contract, or should
   `DENSITY_FLAG_PER_CELL` move to the grid-free measure outright?
3. **§3** — the ruling's expectation that the flagged set would change is refuted. The area-over-cap
   veto's threshold should therefore be set on `areaW`, not `true_w` (§3.1). Confirm before it is
   built.
4. **§7.1.2** — the 90 unattributed stitches block the comparison harness. Should that be pulled
   ahead of SH2?
