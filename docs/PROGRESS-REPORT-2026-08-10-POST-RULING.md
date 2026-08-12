# Progress report — execution of the CTO ruling of 2026-08-10

**For review.** Self-contained: a reviewer needs this file, `CTO-RULING-2026-08-10.md` (the
instructions being executed) and `CONSOLIDATED-REPORT-2026-08-10.md` (the state before it). Picks up
exactly where the ruling left off and covers everything to `ccd45a3`.

## Revision 7 — what changed since revision 6

1. **Hypothesis C (ONNX/rembg nondeterminism) tested and refuted** — but its precondition question
   produced a finding worth having, and the hardening was adopted anyway. §18.
2. **Two real defects fixed** (`ccd45a3`): ONNX inference pinned, and the visual diff strip made
   atomic.
3. **The flake is still not identified.** Three hypotheses refuted is not an identification.

## Revision 6 — what changed since revision 5

1. **SH2 was attempted and NOT shipped.** Three candidate rules, all measured, all refuted for
   different reasons. No code landed; `main` is unchanged. §16, detail in
   `SH2-FINDINGS-2026-08-10.md`.
2. **Three process failures**, #12–#14, one of which briefly hid a red test suite behind a green
   exit code.
3. **An unidentified flaky test** — two full runs of one tree gave 17 and 16 failures over an
   identical 1,265 total.

## Revision 5 — what changed since revision 4

Revision 4 was verified: the reviewer reproduced the six-fabric sweep independently and confirmed
both corrections exact in both directions, including non-monotonicity in `pull_mm`.

1. **`Satin 1`'s column-end pivot is investigated** — mechanism established, no fix written, and one
   question left explicitly open rather than guessed. §14, full detail in
   `SATIN1-PIVOT-MECHANISM-2026-08-10.md`.
2. **The verification discipline is now a hard rule**, arising from process failure #11. §10.
3. §12.1 gains the reviewer's addition: the coverage-on-expert-file reading is reported **first and
   on its own**, before any comparison number.

## Revision 4 — what changed since revision 3

Revision 3 was reviewed and the landing site approved. Since then:

1. **The reviewer reproduced the fabric sweep independently and got a different fleece figure. They
   were right.** I had reported jersey's numbers as fleece. Chasing that turned up a *second*
   labelling error inside my own correction. Both are fixed in §9.5 and both are recorded as process
   failures (#9, #10).
2. **Headline numbers are now structurally labelled** — `run_quality_bench` refuses to print one
   without its fabric and hoop — and six committed documents got a retroactive labelling pass. §11.
3. **The standing rule is extended** at the reviewer's direction: state the limits of the fixture,
   *and* state what you inspected versus what you inherited. §10.
4. **The plan beyond the current queue is now set**, including a hard stop the moment real artwork
   arrives. §12.
5. Process failure #11: I told the owner a CI lane was running when it was not.

## Revision 3 — what changed since revision 2

Revision 2 was reviewed. Since then:

1. **The reviewer corrected their own Q4 ruling, twice**, and the second correction invalidated a whole
   work item. Recorded in §8; the item is closed in §7.1.2.
2. **Item 1 of the revised order — the real-artwork landing site — is complete**, in four commits.
   New §9.
3. **A new standing rule** on stating fixture limits, generalised from process failure #5. §10.

## Revision 2 — what changed since the version that was reviewed

Revision 1 covered `a95df3e` … `9918397` and was reviewed. Three things came back, and this revision
folds them in rather than appending:

1. **The reviewer found a defect in the DET3 work that revision 1 presented as complete.**
   Anti-aliased alpha — every logo any real tool exports — still had its artwork deleted. Root cause,
   fix and measurements are §5.4. The claim in revision 1 that DET3 closed the transparent-PNG case
   was **wrong for the common case**.
2. **My own §7.1.2 was wrong.** The "90 unattributed stitches" are excluded by design, not by
   defect. Corrected in place, with the real adjacent defect that diagnosis turned up.
3. Rulings arrived on all four questions and the priority order was revised. §8 now records the
   answers and the order rather than the questions.

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
| 4 | `ecad056` | DET3 completion — a declared foreground **is** the foreground; + ruling Q2 | revised order 1 |
| 5 | `0361344` | corpus reproducible from the repository; dead `stitch_start` removed | landing site |
| 6 | `1551fc4` | real job-pair loader + expert comparison harness | landing site |
| 7 | `224b850` | fabric axis on the bench | landing site |
| 8 | `8bfdf40` | headline numbers labelled structurally; retroactive doc pass | directive 1 |
| 9 | `87b14cc` | `Satin 1` pivot — mechanism investigated, no fix | next action |
| 10 | `22d1dbb` | four resolutions; sequencing reversed, `5c` retired | review |
| 11 | `84440fb` | **SH2 findings — three rules measured, NO CODE LANDED** | order item 1 |
| 12 | `85306ff` | item 0 — flaky test narrowed, two hypotheses refuted | order item 0 |
| 13 | `ccd45a3` | ONNX inference pinned; visual diff strip written atomically | order item 0 |

Commits 1–4 are shipped-code changes affecting every upload; 5–8 are the instrument and its
labelling; 9–11 are documentation only. **No shipped-code change has landed since `ecad056`.** Both CI lanes were run to completion before each code commit,
and from failure #11 onward the `N passed` **summary line** was read rather than the tail — a lane
without one did not run (§10.1).

| commit | lane 1 (default) | lane 2 (`STITCHIQ_NO_REBUILD_PASSTHROUGH=1`) |
| --- | --- | --- |
| `a95df3e` | 1221 passed | 1215 passed |
| `bedc998` | 1221 passed | 1215 passed |
| `9918397` | 1229 passed | 1223 passed |
| `ecad056` | 1231 passed | 1225 passed |
| `0361344` | 1231 passed | 1225 passed |
| `1551fc4` | 1252 passed | 1246 passed |
| `224b850` | 1258 passed | 1252 passed |
| `8bfdf40` | 1265 passed | 1259 passed |
| `ccd45a3` | 1265 passed | 1259 passed |

`1551fc4` and `224b850` were split rather than committed together, because the lanes that verified
the harness had **started before** the fabric-axis files were copied in and never collected their
tests. Committing both on that evidence would have claimed verification that did not exist.

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

> **Superseded in part by ruling Q2 (§5.5, `ecad056`).** `max_per_disc` is now the PRIMARY bound and
> `max_per_cell` is kept loose and labelled a grid artefact. The discriminator and `p99` below are
> unchanged. The shape of the argument stands; the bound that carries it moved.

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

A veto built on `true_w` misses both mascot objects. Built on `areaW` it catches all three.

> **My recommendation here was OVERRULED, and correctly — see Q3 in §8.** `areaW` is a dispersion
> statistic computed from the same density-biased samples as the median it is meant to check, and it
> **fires on two correctly-classified tatami objects** (07 seq 1 at 1.38, seq 10 at 1.49). It agreed
> with my three satins by luck. The veto will use the local-thickness area-over-cap fraction
> instead, which measures 0.000000 on all 13 correctly-classified satins. The survey data below
> stands; the statistic I proposed to build on it does not.

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

### 5.4 DET3 was incomplete — anti-aliased alpha (`ecad056`)

**Found by the reviewer, not by me, in work I had presented as finished.** Redrawing §5.1's fixture
with `cv2.LINE_AA` instead of `cv2.LINE_8` — same geometry, one flag — regressed it to zero.
Reproduced on the shipped code before changing anything:

| | composited unique colours | declared mask | stitches | objects |
| --- | --- | --- | --- | --- |
| `LINE_8` | 1 | 32,937 px | 1,960 | 2 |
| `LINE_AA` | 65 | 34,733 px | **0** | **0** |

The declaration was **detected in both**, and `substrate_removed_mm2` was 0.0 in both — so the
substrate exemption shipped in `9918397` worked exactly as designed, and the artwork died anyway.

**Root cause, stated generally.** Anti-aliasing blends an edge pixel's RGB toward zero as well as its
alpha, so compositing over white yields a grey ramp at every edge. Those greys open extra k-means
clusters; the white interior stays indistinguishable from the white page; and the corner-average
background heuristic deletes the design *through the other door*, with no channel reporting it —
which is the exact deletion DET3 exists to prevent.

**The declared mask exempted the substrate rule but did not constrain segmentation.** A file that
states which pixels are artwork must have that statement honoured by the segmentation stage too:
declared pixels are foreground, and a background heuristic does not get to overrule the file.
`fg_mask` is now the declared mask for alpha input exactly as it already was for SVG.

| | before `ecad056` | after |
| --- | --- | --- |
| `LINE_8` | 1,960 st / 2 obj | 2,006 st / 2 obj |
| `LINE_AA` | **0 st / 0 obj** | **1,982 st / 2 obj** |

`LINE_8` moves because its foreground is now the file's exact declaration rather than a neural
matte — the same reason vector input never used the matte.

Two tests: the `LINE_AA` variant, asserting the same **object count** as the hard-edged fixture (the
two differ by a few hundred edge pixels, so only the structure must agree); and a structural test
pinning that the mask which exempts the substrate rule **is** the foreground, because the two uses
sit a hundred lines apart in different branches and honouring one without the other is this bug.

**Why this matters beyond one fixture:** every logo exported from Illustrator, Photoshop, Figma or
Canva has anti-aliased edges. The hard-edged transparent PNG my original fixture used is the rare
case, and it was the only case the shipped fix covered.

### 5.5 Ruling Q2 applied in the same commit

The density gate's primary bound moves to the grid-free `max_per_disc`, which is translation
invariant. `max_per_cell` is a grid artefact by construction — demonstrated twice in the very
investigation that produced it (§2.2, §6.1) — so it is kept loose and labelled, because every
committed baseline and the corpus runner record it. `p99_per_cell <= 6` verbatim; tie-off
discriminator retained.

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

5. **I shipped DET3 as complete when it covered only the rare case, and reported it that way.**
   The failure was not the missed code path; it was the fixture. I chose a hard-edged shape,
   measured a clean 0 → 1,960, and did not ask whether the fixture resembled real input. Every logo
   from every real design tool is anti-aliased. A headline number is only as general as the fixture
   that produced it, and I did not state — or check — the limits of mine. The reviewer found it in
   one variation.

6. **My own §7.1.2 was a wrong diagnosis, stated confidently.** I reported the 90 unattributed
   stitches as "per-object counts are wrong somewhere" and marked it blocking. They are lock
   stitches, excluded deliberately, and `_lock_stream`'s docstring says so in as many words. I had
   read the count difference and inferred a defect instead of reading the function that produces it.
   Corrected in §7.1.2, along with the real defect sitting next to it.

7. **I derived work from an impossible specification without checking it.** The harness spec said
   "per-object stitch-type agreement against an expert machine file". I wrote that this was *blocked*
   by attribution, planned the work, and reported it as a priority item — never once asking what a
   DST actually contains. It contains no objects. The measurement could not have existed at any
   priority. The moment to have caught it was when I wrote the word "blocks": a claim that X blocks Y
   is a claim about Y, and I had not looked at Y.

8. **I made the render-alignment decision wrong in both directions.** First an ink test of "darker
   than white" on a canvas that is (222, 228, 232) — every channel already under 250 — so the whole
   canvas read as ink. Then, fixing that, I registered the two renders on absolute millimetres, which
   is wrong for comparing against a machine file whose coordinates are relative to its own origin.
   The second error was caught only because I had written a test asserting a pure translation must
   not register as a difference; without it, the harness would have shipped producing plausible,
   entirely fictional difference images on the first real job.

9. **I reported jersey's numbers as fleece.** The fabric axis summary gave the badge as
   "denim → fleece 17,178 → 14,160 stitches". 14,160 is **jersey**; fleece is 14,464. I took the
   minimum across six fabrics and labelled it with the fabric I *expected* to be the minimum —
   assuming response is monotone in `pull_mm`, which it is not, because `row_mm` and `satin_mm` move
   too. Nothing told me fleece was the minimum; I did not read the row. Caught by the reviewer
   reproducing the sweep. **It shipped in the same commit that established the need for labelling.**

10. **The correction to #9 contained the same class of error.** I gave the hoop as 100×100 for all
    three fixtures; two run at 130×180. Caught within the hour by the guard written in response to
    #9, which prints `[cotton @ 130x180]` where my table said otherwise. Two labelling errors in two
    hours, inside the corrections to a labelling problem — which is the argument for §11's structural
    guard rather than for care.

11. **I told the owner a CI lane was running when it was not.** I had chained `ruff && pytest` in one
    background command; ruff exited non-zero on a finding of mine, so pytest never started and the
    "lane" was four lines of lint output. I reported it as running. Noticed only because the tail did
    not look like pytest. A command that reports success for the wrong reason is worse than one that
    fails: the claim "both lanes green" is the load-bearing claim in every commit here.

12. **I piped the verification command through `tail`, and it hid a red suite behind a green exit
    code.** The background task reported **"exit code 0"** for a run with 17 failures, because a
    pipeline's status is `tail`'s, not pytest's — and `| tail -12` also truncated the evidence file
    to twelve lines, so I could see only 11 of the 17 failures and nearly reasoned about the failure
    set from an incomplete list. I caught it only because §10.1 makes me read the summary line rather
    than trust the exit code. **The rule now extends: do not CHAIN and do not PIPE the lanes.** A
    pipe destroys both the status and the evidence.

13. **I inverted the meaning of my own threshold.** I believed a smaller value would be *less*
    aggressive and preserve flat art; the parameter is a MINIMUM THICKNESS TO OWN, so a smaller
    value owns *more*. Measurement refuted me within one run (08: 8,024 → 7,694). Had I not run the
    experiment I would have shipped the worse constant believing it the safer one.

14. **I diffed against a stale artefact.** Comparing SH2 to `v2-swarm-summary.json` — 41,126 stitches
    and `machine_minutes: n/a`, predating many landed changes — produced "+60.6 % stitches and two
    classification flips". All fiction. The provenance rule already says to build "before" from a
    worktree at the parent commit; I reached for a committed JSON because it was to hand.

---

## 7. Open items

### 7.1 Opened by this stretch (new, not on any prior list)

1. **`Satin 1`'s column-end pivot puts ~17 penetrations in one 0.5 mm disc.** Pre-existing on both
   trees, untouched by anything here, and the larger half of the corpus's worst density site. Never
   examined. This is a satin column geometry question — the inner side of a tight turn re-using its
   pivot — not a flag-level question.
2. **Per-object stitch attribution — CLOSED, not done. No consumer can exist.**
   *(Premise corrected twice: once by me in revision 2, once by the reviewer, whose correction
   invalidated the item entirely.)*

   **Revision 3 resolution.** The consumer this was for cannot exist. A DST carries no object
   metadata and a PES carries colour blocks and nothing else, so **there is no expert-side object to
   agree with**. The specification that generated this work — "per-object stitch-type agreement
   against an expert machine file" — asked for a measurement that no machine file can supply. I
   derived work from it without checking what the expert side actually contains, which I should have
   done the moment I wrote "blocks the comparison harness".

   Deferred indefinitely. The one real action was carried out in `0361344`: the dead
   `stitch_start=obj_start` argument is removed, since it claimed provenance that was silently
   discarded. The paragraphs below record what was true when it was diagnosed.

   Revision 1 reported `sum(object.stitch_count)` = 8,001 against 8,091 actual penetrations as
   "per-object counts are wrong somewhere". **They are not.** The 90 are lock stitches — tie-offs
   and tie-ins added by `_lock_stream` as a post-pass over the assembled stream, after per-object
   counts are computed. Its docstring states the exclusion is deliberate: *"they describe the
   object's own stitching, not its plumbing."* Nothing is miscounted.

   **The real defect is next to it.** `pipeline.py:1008` passes `stitch_start=obj_start` into
   `DesignObject`, commented *"Provenance for the B1.5 pass-through: where this object's stitches
   are"*. `DesignObject` has no such field, and Pydantic v2's default `extra='ignore'` discards the
   argument **silently** — verified: absent from `model_fields`, `hasattr` is `False`. The
   pass-through actually works off `params_hash`. The line is dead and its comment misleads anyone
   who reads it as evidence that stitch positions are recorded.

   This also explains, cleanly, why the density probe in §2.2 reported
   `object_attribution_trusted: False` and had to fall back to whole-stream attribution — and why
   the +3 delta it localised turned out to be a lock.

   So the work is **not** "fix wrong counts". It is a penetration→object map that survives
   `_lock_stream`'s insertions and attributes each lock to the object it terminates, which is what
   per-object stitch-type agreement against an expert machine file requires.
3. **The bench is entirely cotton.** It structurally understates UP1 by 2.5× and cannot see
   fabric-dependent defects at all. **Escalated by the reviewer** — a fabric axis must exist before
   the physical-units tranche or that tranche is tuned blind. Folded into order item 3 (§8).

### 7.2 Remaining from the ruling

> **Sequencing is now set by the revised order in §8.** This list is the inventory; §8 is the order.

- **SH2** — bare-fabric moats, up to 443 mm² at a 200 mm hoop, with `TEXTURE_RETRY_UNCOVERED`
  re-derived rather than assumed.
- **The physical-units contract** (SZ1 / SZ3 / SZ4 / UP2 / UP3 / UP4) as its own tranche, not
  interleaved, re-pinned at a hoop above 133 mm.
- **The real-artwork landing site** — a loader for real job pairs as a corpus tier kept strictly
  separate from A/B/C; a comparison harness against the expert's machine file; and
  `build_corpus100.py` made reproducible on a fresh checkout.
- **Deferred**: the area-over-cap veto (5.3) — statistic now ruled, see Q3 in §8; 1c; 3e-i, which
  goes after the physical-units tranche because SH2 and that tranche both move streams.
- **Stays open, unabsorbed**: 5.2 (+6 trim divergence), 5.4 (knockout policy), 5.5 (veto dissent).

### 7.3 `build_corpus100.py` — **FIXED in `0361344`**, see §9.2

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

## 8. Rulings received, and the revised order

Revision 1's four questions were answered. Recorded here so the decisions travel with the work.

| Q | ruling | status |
| --- | --- | --- |
| Q1 — 3e-i | **Defer, as landed.** A 46-stitch object at ±7 % on a contour round trip is noise. 3e-i's only safety property is "must not change either path's stream", and SH2 *and* the physical-units contract both move streams — so 3e-i goes **after** the physical-units tranche. | accepted, no change needed |
| Q2 — density gate | **Primary bound moves to the grid-free `max_per_disc`; keep the revisit discriminator; keep `p99_per_cell <= 6` verbatim.** `max_per_cell` is a grid artefact by construction. | **done, `ecad056`** (§5.5) |
| Q3 — veto statistic | **Neither `areaW` nor `true_w`.** Use the local-thickness area-over-cap fraction, `dilate(EDT > cap/2, disk(cap/2))`. Measured separation: **0.000000** on all 13 correctly-classified satins, **0.558–0.798** on all 4 misclassified, **0.894–1.000** on all 8 tatami — any threshold in 0.01–0.55 is identical, so take the middle. `areaW` is a dispersion statistic computed from the same density-biased samples as the median it is meant to check, and it **fires on two correctly-classified tatami objects** (07 seq 1 at 1.38, seq 10 at 1.49); it agreed with my three satins by luck. Ship with a regression asserting 0.000000 on the 13 known-good satins so corpus growth cannot erode the margin. | pending, after the physical-units tranche |
| Q4 — attribution | **RETRACTED BY THE REVIEWER.** Originally "pull ahead of SH2, it blocks the comparison harness". Two errors, both acknowledged as theirs: the 90 stitches ruling was made on my wrong diagnosis without verifying it; and, worse, **the harness specification it served asked for a measurement that cannot exist** — per-object agreement against a file format that carries no objects. | **closed, not done** (§7.1.2) |

**Q4's retraction changed the spec, not just the order.** The harness now compares at the two
granularities both sides genuinely have — design level and colour-block level — plus a rendered
side-by-side and difference image. Explicitly **not** per-object. Built to that spec in `1551fc4`
(§9.4).

**On §4.3 (the all-cotton bench), escalated by the reviewer:** it is a corpus defect worth more than
revision 1 gave it. The bench cannot see *any* fabric-dependent behaviour — it understated UP1 by
2.5× and will understate the entire physical-units contract the same way. A fabric axis must exist
before that tranche or it will be tuned blind. **Done in `224b850`** (§9.5), folded into the landing
site so the instrument exists before it is needed — and it immediately showed that every headline
number in this series is a cotton number.

### Revised order (current, after the sequencing reversal)

1. ~~Real-artwork landing site + the fabric axis~~ — **done**, `0361344` / `1551fc4` / `224b850` (§9)
2. **SH2** — `TEXTURE_RETRY_UNCOVERED` re-derived against the corrected `emitted_mask`, derivation
   shown, not assumed at 0.19. ← **next**
3. **The A>cap veto** — moved AHEAD of the physical-units tranche, see below. ~1 day.
4. The physical-units contract as its own tranche, **across the fabric axis, per fabric**, re-pinned
   above a 133 mm hoop.

Then 1c, then 3e-i.

**The veto moved forward, and this reversed a ruling.** A later ruling had placed it *after* the
physical-units tranche. I argued that contradicted the same ruling's own safety property: it forbade
overlapping the veto with 3e-i because *"a forbidden refactor diff [would be] indistinguishable from
an intended classification diff"* — and the physical-units tranche moves **every fixture and every
fabric differently** (§9.5), so the veto's intended 3-of-10 classification diff landing on top of it
is that same indistinguishability, worse. The veto also does not *need* the tranche: **A>cap is pure
region geometry**, `dilate(EDT > cap/2, disk(cap/2))` on the raw mask, with no dependence on pitch,
pull compensation or units. Accepted, with one condition traced by the reviewer and now binding:

> The physical-units work must take **float pacing**, not grid-snapping. Grid-snap
> (`mm_per_px' = row_mm / round(row_mm / mm_per_px)`) changes `mm_per_px`, re-rasters the region, and
> **would** move A>cap. If grid-snap is taken for any reason, the A>cap survey is re-run afterwards
> and that is stated.

Superseded: DET3 completion (done, `ecad056`) was item 1 of the previous order; per-object
attribution was item 2 and is now closed as having no possible consumer.

Unchanged and still open, unabsorbed: 5.2 (+6 trim divergence), 5.4 (knockout policy), 5.5 (veto
dissent), and `Satin 1`'s column-end pivot (§7.1.1) — the larger half of the corpus's worst density
site, still never examined.

---

## 9. Item 1 of the revised order — the real-artwork landing site

Complete, in four parts across three commits. **Nothing is tuned against real artwork; there is
none.** A test asserts the harness carries no thresholds and no pass/fail, so it cannot quietly
acquire an opinion before the material arrives.

To use it: drop `tests/fixtures/corpus_real/<job-name>/artwork.png` beside `expert.dst` and run
`scripts/compare_expert.py`.

### 9.1 The dead provenance line (`0361344`)

`pipeline.py` passed `stitch_start=obj_start` into `DesignObject` with a comment claiming it recorded
"where this object's stitches are". `DesignObject` has no such field, so Pydantic's default
`extra="ignore"` discarded it **silently** — verified absent from `model_fields`, `hasattr` False.
Removed rather than implemented: the index would be invalidated anyway by `_lock_stream`, which
inserts tie-offs into the assembled stream afterwards, and the B1.5 pass-through has always worked
off `params_hash` alone.

### 9.2 The corpus is reproducible from the repository (`0361344`)

§7.3's diagnosis was correct. Fixed, and **measured on a fresh `git worktree` checkout**:

| tier | fresh checkout, before | after |
| --- | --- | --- |
| A-real | 10 (photos silently skipped) | **13** |
| B-real-derived | **0** (silently — `tier_b` returned on empty `reals`) | **40** |
| C-parametric | 90 | **47** |

**Verified claim:** two independent fresh checkouts now produce **byte-identical corpora, all 101
files**. The tier split is asserted as 13/40/47 rather than printed, and every manifest entry is
checked to have an image on disk — the case that used to pass silently.

**A second defect, worse, found by testing the first.** Tier C **could not be generated at all**, by
anyone, from this repository. `_contrasting()` sorts the palette by *descending* distance from the
canvas, so `pal[3]` is by construction the **least** contrasting entry — and `hairline_linework` drew
its only ink from `pal[3]`. The helper written to stop blank fixtures was guaranteeing one: on
`PALETTES[1]` against white it resolves to (250, 250, 250), and `_write`'s blank guard correctly
aborted the build at `C01`. Confirmed **pre-existing** by running the unmodified script from `HEAD`,
which fails identically — so the per-tier RNG split did not cause it. The 47 tier-C images on disk
predate the helper.

### 9.3 The loader (`1551fc4`)

Real pairs live in their own tier, `R-real-job`, with no path by which they can be averaged into
corpus100's A/B/C — whose own docstring warns that a tier-C average must never be read as a
real-world score. Half a pair **raises rather than skips**, for the same reason `build_corpus100.py`
now refuses a missing tier-A source.

### 9.4 The comparison harness (`1551fc4`)

Built at the two granularities **both sides genuinely have**, per the revised spec — design level
(stitch count, colour count, machine-minutes net of trim, trims, jumps, bounding box, and our own
coverage metric run over the **expert's** stream as well) and colour-block level (per-block stitch
count, extent, thread colour, matched nearest-colour then by spatial overlap) — plus a rendered
side-by-side and difference image. `TRIM_SECONDS`, `RNG_SEED` and `coverage_metrics` are **imported**
from the bench rather than restated.

**Three bugs its 21 tests found, all in this code, after its own self-test had passed:**

1. **`job.json` was read as the machine file.** `_expert_exts()` asks pyembroidery what it can read,
   and pyembroidery reads a `.json` stitch format — so a job's own metadata matched as a machine file
   and **every job carrying one** failed with "2 machine files". The first real job with metadata
   would have hit it.
2. **Render alignment, decided wrongly twice.** Ink was first detected as "darker than white" — but
   the canvas is `FABRIC_BGR` (222, 228, 232), every channel under 250, so the whole canvas counted
   as ink and the difference image was uniformly "both". Fixing that, I then registered the two
   renders on **absolute millimetres**, which is wrong here: a DST stores coordinates relative to its
   own origin, so where an expert placed the design in the hoop is a property of their file, not
   their stitching. **Measured: a pure 7 mm translation read as 23.6 % disagreement** — the outline
   drawn twice, a picture of nothing. Now aligned on bounding-box centre, with the cost stated in the
   docstring: a placement difference is invisible in the image and appears in the `width_mm` /
   `height_mm` deltas instead, where it belongs.
3. **A test of mine matched its own docstring.** The check that blocks are not read from
   `design.objects` tripped on the prose "the expert side has no objects". Asserted on the AST now.

### 9.5 The fabric axis (`224b850`)

Three fixtures × six fabrics spanning the whole 0.15–0.50 mm pull range.

> **CORRECTION (revision 4).** Revision 3 and commit `224b850` gave the badge as
> "denim → fleece **17,178 → 14,160** stitches, 22.64 → 18.78 machine-minutes". **14,160 / 18.78 is
> JERSEY, not fleece.** I quoted the minimum across the six fabrics and labelled it with the fabric I
> expected to be the minimum. Fleece is **14,464 / 19.08**. Caught by the reviewer reproducing the
> sweep independently and getting a different fleece figure.
>
> This is precisely the failure the labelling directive targets, committed in the same commit that
> established the need for labelling. A number is not safe because it is measured; it is safe when it
> carries what it is a measurement *of*.

All figures below re-run on the shipped code at `224b850`, at each fixture's own bench hoop:

| fixture | hoop | denim (`pull` 0.15) | fleece (`pull` 0.50) | full range across all six |
| --- | --- | --- | --- | --- |
| 05_wordmark_caps | 130×180 | p90 step 3.8750 | p90 step **4.5178** | 3.8750 – 4.5178 |
| 01_flat_2color_logo | 100×100 | 6,200 st / 7.88 min | **4,913 st / 6.27 min** | 4,913 – 6,200 st |
| 07_circular_badge | 130×180 | 17,178 st / 22.64 min | **14,464 st / 19.08 min** | 14,160 (jersey) – 17,178 (denim) st; 18.78 – 22.64 min |

> **A second correction, thirty minutes after the first.** The table above initially said 100×100 for
> all three fixtures. Two of them run at 130×180. I was caught by the labelling guard written in
> response to the *first* error — `run_quality_bench` now prints `[fabric @ hoop]` on every line, and
> the badge came back `[cotton @ 130x180]` while my table said otherwise.
>
> Two labelling errors in two hours, in the corrections to a labelling problem. That is the argument
> for the structural guard rather than for care.

**This finding outlives the task: every headline number in this engagement is a cotton number.**
The badge's machine-minutes run **18.78 – 22.64** across the six fabrics — a 3.86-minute spread,
17.0 % of the maximum. Denim → fleece alone is 22.64 → 19.08, 15.7 %. The **22.65 machine-minute**
figure quoted throughout this series is the *cotton* reading (22.63 at this hoop), and it sits near
the top of that band. Nothing reported was wrong; nothing carried its fabric label either — and the
physical-units tranche will move each fabric differently.

Note also that **fleece is not the minimum**: jersey is, on the badge, despite a lower `pull_mm`.
Fabric response is not monotone in pull, because `row_mm` and `satin_mm` move too — another reason a
single-fabric number cannot be extrapolated.

**A trap pinned rather than left to mislead:** `p90_step_mm` is **flat across every fabric** on
fill-dominated fixtures (3.9750 on 01, 3.9975 on 07). That is not a broken measurement — fill rows
are split at a fixed maximum stitch length, so the 90th percentile sits *on* that cap regardless of
fabric. `median_step_mm` is the fabric-sensitive column for fills. A test asserts the flatness **and**
says that if it ever changes, the premise needs rewriting rather than the assertion loosening.

Six tests assert the axis **discriminates**, because an axis whose numbers do not move with fabric
would look like coverage while providing none.

---

## 10. New standing rule — state the fixture's limits

Generalised from process failure #5 at the reviewer's direction:

> Every headline number states the **limits of the fixture that produced it** — what about the input
> was chosen, and what a realistic input would have that this one does not. If you cannot name a way
> your fixture is unlike real artwork, you have not looked hard enough.

**Extended after failures #7–#10, at the reviewer's direction:**

> …and state what you have **inspected** versus what you **inherited** from a spec, a comment, or a
> reviewer.

The reviewer's observation is that #7 and #8 are the same shape, and #9 makes it three: accepting a
premise about a thing without opening it. "Blocks the comparison harness" was a claim about DST
contents I never checked. "Darker than white" was a claim about a canvas that is (222, 228, 232).
"Denim → fleece" was a claim about which row held the minimum, and I did not read the row. Their own
note on it: *"I gave you the impossible spec; you carried it further than you should have, and I set
it. Both halves are worth remembering."*

Applied to this stretch: the hoops in §9.5 are **inspected** — read from `FIXTURE_PARAMS`, which is
why error #10 was caught. "Fleece is the softest so it must be the minimum" was **inherited from
nothing at all**; it was not in a spec, I assumed it.

### 10.1 Verification discipline — a hard rule after failure #11

The reviewer's judgement: *"Process failure #11 is the most important item in this report."* "Both
lanes green" is the load-bearing claim under every commit in this series, no gate can catch a false
one, and it was briefly untrue. Two rules follow, and they are absolute:

1. **Never chain the verification command with anything that can short-circuit it.** The lanes run as
   their own command. `ruff && pytest` is banned — ruff exiting non-zero on a finding means pytest
   never starts, and the output still *looks* like a completed run.
2. **Read the summary line, not the tail.** A lane without an `N passed` line **did not run**. For a
   verification claim, "inspected" means reading the pass/fail line — not recognising the shape of
   the output.

From here every report states which line was read.

### 10.2 Two-run diff on a red tree — the control that replaced the flake hunt

Adopted after the flake resisted identification across four full runs (§19). It defends against the
failure mode whether or not that particular flake is ever found:

> **On any red tree, the failure set must be diffed across TWO runs before any test is classified as
> an expected re-pin. A test appearing in one run and not the other is never a re-pin — it is
> quarantined and named.**

This is cheaper and more durable than identification. The danger was never a flaky test as such; it
was a flaky failure landing inside the set that gets waved through as "expected", which is exactly
where the one observed instance appeared.


It has already produced four defects that passed their own tests. Applied to §9:

- **§9.2** — the reproducibility check ran on one machine against pinned
  `opencv-python-headless==5.0.0.93` and `numpy==2.4.6`. It shows the corpus is reproducible *from
  the repository rather than from a scratchpad*; it does **not** show byte-identity across OpenCV
  versions, since PNG encoding and `INTER_CUBIC` are implementation-defined.
- **§9.4** — every test runs on `07_circular_badge`, a synthetic 4-colour flat design digitized by
  **us**. Nothing has seen a real DST, a real expert's file, or a photograph. These verify the
  instrument *reads* correctly; block matching has only met blocks we generated, which are cleaner
  than an expert's.
- **§9.5** — the sweep uses three synthetic bench fixtures at their existing hoops, and **every
  fabric in it is a profile we defined**. It proves the axis detects fabric dependence; it says
  nothing about whether our fabric parameters are right, because no real garment has been sewn or
  measured.

---

---

## 11. Headline numbers are now labelled structurally (`8bfdf40`)

The cotton finding in §9.5 is not a bench gap; it applies to documents already committed and already
read by the owner. The badge's 22.65 machine-minutes — reported to him as a headline improvement —
is a **cotton @ 130×180** reading sitting near the top of a band that fabric alone moves 17%.

### 11.1 The guard

Care was not the fix. Two labelling errors happened in two hours *inside the corrections to a
labelling problem* (§6, failures #9 and #10). So the bench now refuses:

- `_conditions()` raises `SystemExit` unless **both** fabric and hoop are present — including on an
  empty string, which would print `[ @ 100x100]` and *read* as labelled;
- every console line leads with `[fabric @ hoop]`;
- the summary JSON carries a `conditions` block — the fabrics and hoops the run spans, plus a
  per-fixture map — placed **before** `totals`, so a reader meets the label before the number.
  `totals` sums across fixtures and is what gets quoted, so it was the easiest place for an
  unlabelled aggregate to escape.

Seven tests, including one asserting `conditions` precedes `totals` in the source, and one checking
that committed summaries agree with their own per-fixture params.

### 11.2 The retroactive pass

Six committed documents — `STATUS.md`, `CONSOLIDATED-REPORT`, `CTO-1B-BOUSTROPHEDON`,
`HANDOFF-ENGINE`, `REVIEW-HANDOFF`, `CTO-CLASSIFICATION-MECHANISM` — gained a **MEASUREMENT
CONDITIONS** banner naming cotton and the per-fixture hoop, and every headline table row quoting
22.65 is labelled inline.

Done **mechanically**, by a script reporting what it changed per file, because hand-labelling is what
failed twice the same day.

---

## 12. The plan beyond the current queue

Set by the reviewer, recorded here so it is not re-derived from severity rank later.

### 12.1 Hard stop — the real-artwork pass

**The moment any job pair exists, run the measurement pass. One pair is enough; do not batch it
behind other work.** Produce a short findings document answering only:

1. **What does our coverage metric read on the EXPERT's file?** **Reported FIRST and ON ITS OWN,
   before any comparison number.** This is metric *calibration*, not comparison — if we read 96 % on
   a master digitizer's file, the metric is wrong and the file is fine. The reviewer's point, sharper
   than the reason the test was written for: it is the one reading that **cannot be gamed by
   tuning**. If it comes back implausible, **every other number in the document is suspect and the
   correct output is a metric fix, not a comparison.**
2. How far apart are we on stitch count, colours, machine-minutes, trims?
3. Which of the 31 known defects actually fire on real artwork, and at what rate?
4. What does the difference image show that no metric caught?

Then **re-prioritise the remaining defect list against that evidence**. The current ranking was
derived entirely from synthetic fixtures and three photographs and must not be carried forward
unexamined.

### 12.2 Default if no real artwork has arrived — CURVES (SF1/SF2/SF3 together)

- The "faceted curves" class the owner can see: above ~120 mm a circle is stored as a raw pixel
  staircase (670 points with 90° corners at a 200 mm hoop; 2,216 points with 404 duplicate vertices
  at 400 mm), and **satin edges are generated from those contours**, so every satin edge wobbles.
- SF1 is inert above 0.10 mm/px — **live for 2 of 4 shipped hoop presets**, i.e. half of users.
- It is a **prerequisite, not a peer**: B2 transforms cannot scale cleanly without a curve primitive
  (points scale, curvature quantisation does not), and B4 lettering round-trips font outlines through
  a 160 px raster.
- An exact SVG upload currently comes out no better than a JPEG of the same logo.

Scope as a **model change first** — a real Path primitive with node types and handles, additive and
optional — measured before any generator consumes it. **Report the model design before building.**

### 12.3 CP2 — thread-catalogue snapping, parallelisable

Cheapest remaining customer-visible fix. Today the digitizer emits raw k-means centroids as
`thread_brand="Auto"`, `catalog_number=""`, so **the file format makes the final thread choice**:
`#123456` becomes "Peacock Blue" in PEC, "Navy Blue" in JEF, filler in EXP and DST. Same design,
different colours per export, and no operator can buy the thread. Needs catalogue data plus the
CIE-Lab matcher that already exists.

### 12.4 Not to be reopened — neural/learned work

The classical defect list is not exhausted, every learned approach needs a training corpus that does
not exist, and the rebuild loop is what will eventually generate it. Revisit only when real job pairs
number in the hundreds.

---

## 13. Owed and not done

Stated plainly rather than listed a fifth time.

- **SH2** — attempted, three rules measured, **none shippable**. §16.
  `TEXTURE_RETRY_UNCOVERED` remains underived; it needs DET2's corrected `emitted_mask` first, and
  DET2 is unfixed.
- **The unidentified flaky test** — three hypotheses refuted (§17, §18), not identified. The
  experiment that would name it is specified in §17.6 and unrun.
- **Two doc corrections owed**, both from claims relayed without their conditions:
  `QUALITY-DEFECTS-2026-08-10.md` states the SH2 fix was "measured to leave hard-edged flat art
  bit-identical" — never measured, and false for rule A (6,165 → 6,221); and
  `SH2-FINDINGS-2026-08-10.md` dismisses C24 as having "no real-world analogue", when its
  MECHANISM — a flat region deleted because its colour fell midway between two centres — fires
  whenever artwork exceeds the palette budget, which CB2 measured on 38/100 corpus designs.
- **`Satin 1`'s pivot** — mechanism now established (§14). One question left open, deliberately: it
  decides which of two fixes is right, and guessing it would produce a plausible wrong fix.
- Still unabsorbed: **5.2** (+6 trim divergence at the G4 configuration, mechanism still a
  hypothesis), **5.4** (knockout policy), **5.5** (the A>cap dissent).
  *"5c" is not a fifth item — it was §5c in `CTO-1B-BOUSTROPHEDON` and became 5.2 when the
  consolidated report absorbed it. The label is dropped so it stops reading as one.*

---

## 14. `Satin 1`'s column-end pivot — mechanism (`87b14cc`)

Listed in three progress reports without being investigated; promised once and not delivered. Now
investigated. **Mechanism only, no fix**, as directed. Full detail:
`SATIN1-PIVOT-MECHANISM-2026-08-10.md`.

### 14.1 It is a pivot, not a dense stroke

Measured on the emitted stream in **design millimetres**, fixture `08_mascot_detail`,
**cotton @ 130×180**:

| quantity | value |
| --- | --- |
| penetrations inside the 0.5 mm disc | 25 |
| **column ends landing in the disc** | **42** |
| distinct far ends of those columns | 31 |
| **angular span of the columns** | **175.6°** |
| column length | 0.707 – 6.946 mm |

Forty-two satin columns converge on one 0.5 mm spot from very nearly a half turn, their outer ends
sweeping an arc across 31 positions. The columns *rotate about* this point.

### 14.2 The mitre that should prevent it fires on 19 % of stalled stations

The codebase already names this failure, in `_mitre_stalled_side` — *"every one of those columns
wants its INNER end on the reflex point, so the inner penetrations pile into a spot far tighter than
the floor allows"* — and resolves it by laying inner ends along the corner's bisector. Instrumented
on the shipped `_mitre_one_side`, across the whole fixture:

| outcome | stations |
| --- | --- |
| **`run_too_short`** (`run < MITRE_MIN_STALLED`) | **4,731** |
| `axis_not_advancing` | 548 |
| `step_from_partner_short` | 6 |
| `step_to_partner_short` | 5 |
| **mitred** | **258** of 1,329 stalled (**19 %**) |

`floor_px` 3.077, `min_len_px` 5.0, 5,698 stations. The dominant refusal by an order of magnitude is
`run_too_short`: the mitre acts only inside a run of `MITRE_MIN_STALLED` **consecutive** stalled
stations.

### 14.3 The one thing not established — and why it was not guessed

**Whether this pivot is one branch or several is untested.** The hypothesis — that `_mitre_one_side`
sees only one branch's endpoint array and is therefore structurally blind to columns arriving from
*different* branches at one point — was attempted, and the attempt **abandoned as unsound**.

Column endpoints are produced in `_skeleton_satin_hires`'s **upscaled** pixel space, so locating the
site among them needs a scale conversion. A validation check against the design's own stitch extents
**refuted the conversion**: endpoints mapped to x 27.49–279.14 mm on a design spanning
26.95–93.05 mm, and the factor is not even uniform (279/93 = 3.00, 223/91.5 = 2.44) because the
upscale is chosen per call from the stroke width. A branch count computed through it would have been
fiction, so it was **discarded rather than reported**.

Everything in §14.1 and §14.2 is in design mm on the emitted stream and does not depend on it.

**That unknown decides the fix**, which is why none is proposed:

| if… | the fix is |
| --- | --- |
| the mitre *declined* here | relax `MITRE_MIN_STALLED` — cheap, contained, testable |
| the mitre *cannot see* this | a cross-branch pass — a design change |

Settling it needs the hi-res scale captured **per `_column_ends` call**. One number.

### 14.4 Fixture limits

One site, one object, one **synthetic** fixture at one fabric and hoop. No real artwork has been
measured, so whether real logos produce pivots of this severity is unknown. The mitre statistics are
**design-wide** and establish that `run_too_short` dominates overall — they do **not** establish
which guard declined at *this* site, which is the same open question as §14.3.

---

## 15. Four resolutions from the last review

Three of the four were the reviewer's own errors, self-identified. Recorded because the corrections
change the plan and the record.

### 15.1 A re-sent ruling — reconciled, not re-executed

An earlier ruling was re-sent whose two P1 items had already shipped in `a95df3e`. Verified before
responding rather than assumed: `skeleton.py:63` reads `((row + col) % 2)` with line 29 recording the
old `(row + col + y0 + x0) % 2`, and `generation.py:137` splits the no-axis arm on area via
`NO_AXIS_SPECK_MM2`. The width survey had also been re-run — and **refuted** that ruling's
expectation that the four flagged objects would change (§3).

### 15.2 Sequencing — my objection upheld, a later ruling reversed

The A>cap veto now goes **after SH2 and before the physical-units tranche**. Reasoning and the binding
float-pacing condition are in §8. The reviewer independently traced the independence claim:
`spine_satin` requires the region **undilated**, so classification runs on the raw mask, and every
item in the physical-units contract changes emission or dilation rather than that mask.

### 15.3 "18 of 24" versus my 13 — mine stands

The 18 came from an agent under a condition that was dropped in relay: artwork built at 1200 px so
`_MIN_WORK_PX == _MAX_WORK_PX` and **no resampling occurs**, deliberately isolating parity. A second
investigator on the same fleet reported 14 through the ordinary path. **The figure of record is
13 of 24, full pipeline** — the number that describes real behaviour. The reviewer's own note: they
relayed a figure without its condition one exchange after ruling that an unlabelled number is how
"22.65 minutes" became a fact.

That is the third instance this stretch of the same failure — a number travelling without the
conditions that make it true — and the first two were mine (§6, #9 and #10).

### 15.4 "5c" was never a fifth item

It was §5c in `CTO-1B-BOUSTROPHEDON` and became **5.2** when the consolidated report absorbed it —
the same +6 trim divergence at the G4 configuration. The label is dropped throughout so it stops
reading as an extra open item. Unabsorbed remains exactly: **5.2, 5.4, 5.5**, plus the A>cap dissent.

### 15.5 `Satin 1` — resolved and deferred

The question §14.3 left open is settled, **by the reviewer's measurement and not mine**: no value of
`MITRE_MIN_STALLED` moves the site, which eliminates "the mitre declined" and leaves **cross-branch
blindness** — `_mitre_one_side` sees one branch's endpoint array at a time. A per-branch pass cannot
fix it. That makes the fix a design change rather than a threshold, so it is deferred behind SH2, the
veto and the physical-units tranche. `SATIN1-PIVOT-MECHANISM-2026-08-10.md` is updated.

### 15.6 SH2 — designed, not yet built

Read the code this stretch; the fix is now specific. `planning.py` runs the ambiguous-blend cut only
`if not is_textured`, while the seam fill that would re-own those `-1` pixels sits inside
`if is_textured:` — unreachable on exactly the path that creates the damage. The fix is to extract the
seam fill and run it **unconditionally**, gating ownership on the `-1` band's **local thickness**
(`2 × EDT` of the `-1` mask) instead of on `is_textured`: discard bands at or below one anti-alias
width (~`up_f` px), own everything thicker. Hard-edged flat art carries ≤1 px bands and stays
bit-identical; the gradient and `C24_many_colours` moats close.

`TEXTURE_RETRY_UNCOVERED` is then re-derived against the corrected `emitted_mask`, with the derivation
shown. **Not implemented, and not claimed as implemented.**

---

## 16. SH2 — attempted, measured, not shipped (`84440fb`)

Order item 1. **No code landed.** Three candidate rules were built and measured; each is refuted by a
different fixture. Full detail in `SH2-FINDINGS-2026-08-10.md`.

### 16.1 The defect, confirmed with the pipeline's own numbers

`planning.py` runs the ambiguous-blend cut only `if not is_textured`, while the Part 29 seam fill
that would re-own those `-1` pixels sits inside `if is_textured:` — unreachable on exactly the path
that creates the damage.

| fixture | unowned foreground | pipeline's own `uncovered_px` |
| --- | --- | --- |
| 03_gradient_soft_subject | **11.96 %** | **0.00 %** |
| C24_many_colours | **15.60 %** | 12.53 % |
| C11_many_colours | 6.30 % | 2.66 % |

Fixture 03 loses 11.96 % of its foreground to nobody while the pipeline reports **0.00 % uncovered**.
That gap is **DET2's inflated `emitted_mask`, measured directly** rather than argued — the damage is
invisible to the very gate meant to catch it.

### 16.2 Three rules, three refutations

`_own_thick_blend` extracts the seam fill and runs it unconditionally. What varies is which `-1`
pixels earn ownership. All figures `[cotton @ per-fixture hoop]`, "before" from a worktree at
`22d1dbb`:

| rule | 01 hard-edged | 05_wordmark_caps | 03 unowned | C24 unowned |
| --- | --- | --- | --- | --- |
| baseline | 6,165 | 1,802 | 11.96 % | 15.60 % |
| **A** thickness ≥ 0.4 mm | 6,221 | 1,914 (**+6.2 %**) | **0.81 %** | **0.22 %** |
| **B** thickness ≥ 1 aa px | 6,268 | 1,881 | 0.00 % | 0.22 % |
| **C** A + ≥2 owned neighbours | **6,165 identical** | 1,827 | **0.81 %** | 15.33 % **lost** |

**A** closes both moats but grows glyphs. `05_wordmark_caps` is a ONE-colour wordmark whose halo
borders ink on one side and unowned background on the other; owning it drove the rebuild fidelity
probe to an **18.4 % object loss against a 14 % band**. Growing shapes by a pixel per side is the
precise effect the ambiguous cut was written to prevent, so A trades this defect for its predecessor.

**B** was tried on a reasoning error (#13 below) and refuted: 08 goes 8,024 → 7,694, 07 goes
17,174 → 17,656, both worse than A.

**C** enforces the cut's own definition — a blend is between TWO colours — and makes hard-edged art
bit-identical. It **loses C24**, whose unowned region is not a band at all but a **whole rectangle
deleted wholesale**, bordered by background, with no second owned neighbour.

### 16.3 What the three jointly establish

The population is three things, and no single scalar separates them:

| case | shape | must be |
| --- | --- | --- |
| halo round a glyph | thin, one owned neighbour | left unowned |
| transition band | thick, two owned neighbours | owned |
| wholesale-deleted region (C24) | large area, may have one neighbour | owned |

A rule combining thickness with "two owned neighbours **or** area over a floor" would cover all
three. **Not attempted** — fitting a second threshold against ten synthetic fixtures at the end of a
session is how a constant gets tuned to noise.

### 16.4 Also established

- **No classification flipped** under rule A: `satin_share` identical on all ten fixtures. Corpus
  cost +1.8 % machine-minutes.
- The defect doc's claim that this fix "leaves hard-edged flat art bit-identical" is **inherited and
  false for A** (01 is hard-edged — 3 distinct source colours — and moved), though **true for C**.
- **`TEXTURE_RETRY_UNCOVERED` was not re-derived.** It needs DET2's corrected `emitted_mask` first.
  Under every variant 0 of 14 fixtures cross 0.19, so none mis-fires the photographic rescue — a
  narrower statement than the derivation the ruling asked for.

### 16.5 Fixture limits

Ten synthetic flat fixtures plus four parametric corpus images, all **cotton**, at 100×100 and
130×180. No photograph and no real artwork measured. Real exports carry anti-aliased edges at widths
this threshold sits directly among, so the halo-versus-transition boundary is exactly where real
artwork is most likely to diverge from these fixtures — and **C24, the case that drove rule A, is a
generated rectangle grid with no real-world analogue in the corpus.**

### 16.6 Verification

Both lanes read by summary line: **`16 failed, 1249 passed`** (default) and
**`16 failed, 1243 passed`** (no-rebuild-passthrough). Red, so nothing shipped. Of the 16, 13 were
expected re-pins (4 stream locks, 8 visual baselines, 1 gate meta-test downstream of a stale
baseline) and 3 were genuine: a missing facade export, plus the two `05_wordmark_caps` fidelity
failures above.

---

## 17. Item 0 — the flaky test: two hypotheses refuted, one defect found, not yet named

**Status: NOT identified.** Recorded in full because a nondeterministic suite makes "both lanes
green" unfalsifiable, and because two plausible explanations are now eliminated rather than left
hanging.

### 17.1 What is being explained

Two full runs of one tree (the red SH2 tree) gave **17 failed / 1,248 passed** and
**16 failed / 1,249 passed** — an identical 1,265 total, one test flipping.

### 17.2 Hypothesis A — concurrent lanes racing on a shared file. REFUTED as the cause.

It did surface **a real defect**: `visual_regression.compare()` writes
`tests/visual/diffs/<name>.png`, a shared non-`tmp_path` location, whenever a fixture fails. Two
concurrent lanes both failing the same fixture write that file simultaneously. It **cannot flip an
assertion** — the verdict is computed before the write — so it corrupts the diff strip a human reads
to judge whether a change was intended, not the result. Worth fixing; not the flake.

### 17.3 Hypothesis B — wall-clock assertions under CPU contention. REFUTED by measurement.

This box has **4 CPUs**, and two full suites have been run concurrently on it throughout the
engagement. Several tests assert wall-clock budgets (`test_event_loop_lag` on a lag ratio,
`test_part48_trim_routing` on a 3-second bound, the rate-limit suite). Measured:

| condition | result |
| --- | --- |
| timing tests alone | 35 passed, 71.4 s |
| timing tests during a concurrent full suite, run 1 | 35 passed, 43.7 s |
| timing tests during a concurrent full suite, run 2 | 35 passed, 40.1 s |

They not only pass under load, they run **faster** than in isolation — so the box was not saturated
the way the hypothesis assumed. Refuted.

### 17.4 Clean tree

A full suite on the clean tree, itself under concurrent load: **`1265 passed`**, zero failures. The
flake does **not** manifest on green, which is why it cannot be hunted on the current tree.

### 17.5 Where it is narrowed to

The truncated file held the **last 11 lines** of a sorted-by-execution-order failure list, and those
11 are exactly the last 11 of the complete 16-failure list. For the other run to have had 17, the
extra failure must sort **at or before `test_swarm_perf_lock::test_stitch_stream_locked[05]`**.

The stream lock covers exactly four fixtures (04, 05, 06, 07), all four of which failed — complete
coverage, so "another lock should have failed" is eliminated. That leaves, as the strongest
candidates, a second parametrisation of the two tests that were **already marginal**:
`test_probe6_regenerating_reproduces_the_design` (6 fixtures, 1 failed) and
`test_editing_a_satin_design_keeps_every_object`. Both measure per-object stitch loss against a
band — precisely where a marginal case flips.

### 17.6 The experiment that would settle it

Re-apply SH2 rule A, run the full suite three times **sequentially** (not concurrently, to keep
hypothesis A out of the picture), and diff the failure sets. ~51 minutes. Not run.

**Why this matters more than it looks:** the flake appeared *among failing tests* on a red tree —
the exact set that gets classified as "expected re-pin". A flake that hides there is a flake that
gets waved through.

---

## 18. Hypothesis C — ONNX nondeterminism: refuted, and hardened anyway (`ccd45a3`)

Third hypothesis for the flake (§17). **Refuted.** Two real defects fixed on the way, neither of
them the flake.

### 18.1 The precondition question, answered — and it is the reassuring answer

Before testing the hypothesis: does the determinism suite actually exercise the learned path, or does
the texture gate route flat synthetic art down the OpenCV fallback? If the latter, the learned path
had never been determinism-tested at all — a finding regardless of the flake.

Measured through `segmentation.foreground_mask` rather than inferred:

| fixture | path | | fixture | path |
| --- | --- | --- | --- | --- |
| 01_flat_2color_logo | **rembg** | | 06_wordmark_script | **rembg** |
| 02_logo_fine_text_3color | **rembg** | | 07_circular_badge | **rembg** |
| 03_gradient_soft_subject | **rembg** | | 08_mascot_detail | **rembg** |
| 04_thin_line_outline | **rembg** | | 09_nonuniform_background | **rembg** |
| 05_wordmark_caps | **rembg** | | 10_low_contrast_subject | **rembg** |

**All ten.** The learned path is fully covered; the determinism suite's two fixtures both take it.

### 18.2 The hypothesis — refuted

Preconditions held: `segmentation.py` set **no** `SessionOptions`, so ONNX ran with default
multi-threaded reductions whose order is not guaranteed. The existing determinism test only repeats
uploads **in one process in isolation**, which cannot see cross-process or under-load variation.

Stitch-stream hash, separate processes each time:

| condition | runs | distinct hashes |
| --- | --- | --- |
| idle box, `03_gradient_soft_subject` | 3 | **1** |
| during a concurrent full suite, `03` | 4 | **1** |
| during a concurrent full suite, `01` | 2 | **1** |

Nine digitizes, two fixtures, six of them under load — one hash each. **ONNX nondeterminism does not
reproduce here.**

### 18.3 Hardened regardless, and measured free BEFORE adopting

`_deterministic_session_options()` pins `intra_op_num_threads=1`, `inter_op_num_threads=1`,
`ORT_SEQUENTIAL`, returning None if `onnxruntime` cannot be imported so segmentation degrades to
rembg's default rather than being lost. The reasoning recorded in the docstring: *"did not vary on
this box today" is not the same claim as "cannot vary"*.

**The measurement that mattered was the one checking my own fix was cheap.** Pinning changes reduction
order, so had it changed the MATTE it would have changed every fixture's stream and required a full
re-pin — hardening masquerading as a one-liner. It does not:

| fixture | mask hash, default | mask hash, pinned |
| --- | --- | --- |
| 03_gradient_soft_subject | `022849c6c269ee91` | **identical** |
| 01_flat_2color_logo | `ea356a5cfec54419` | **identical** |
| 08_mascot_detail | `a99c92262c77285b` | **identical** |

and the shipped path still hashes `6e7d51ec…` after the change. Measured before adopting, not
discovered in the lanes.

### 18.4 The diff strip is now atomic

`visual_regression.compare()` wrote `tests/visual/diffs/<name>.png` directly — shared, non-`tmp_path`
— whenever a fixture failed, and two lanes are routinely run at once and fail the same fixture. Now a
per-process temp file plus `os.replace`: predictable path (the failure message prints it), indivisible
write. It cannot flip an assertion, but the artefact it corrupted is **the one used to judge re-pins**,
which is the same class of problem as the flake.

### 18.5 Fixture limits

Nine runs, two fixtures, one machine, one `onnxruntime`/`rembg` version, load from a single concurrent
suite on **4 CPUs**. This establishes that ONNX was **not the cause here** — not that it is
deterministic in general. A different execution provider, a GPU, or a many-core host could all
behave differently, which is precisely why the pin is worth having despite the negative result.

### 18.6 Verification

Read from untruncated files, no chain, no pipe:

- lane 1 (default) — **`1265 passed, 2 skipped, 2 deselected, 3 xfailed, 1 warning`**
- lane 2 (`STITCHIQ_NO_REBUILD_PASSTHROUGH=1`) — **`1259 passed, 8 skipped, 2 deselected, 3 xfailed, 1 warning`**

Two independent clean-tree runs earlier in the stretch also gave `1265 passed`.

### 18.7 Standing state of item 0

**Three hypotheses refuted, two defects fixed, flake NOT identified.** Refutations are not an
identification, and the count should not be mistaken for progress on the question that was asked. The
experiment that directly observes it — re-apply SH2 rule A, three **sequential** full runs, diff the
failure sets (~51 min) — remains unrun.

---

## 19. The flake: the direct experiment ran, did not identify it, and is now a control

Ruled: run the sequential experiment once, then stop hunting and convert it to a process control.
Both halves done.

### 19.1 The experiment

SH2 rule A re-applied **as apparatus only** — it is disqualified (18.4 % object loss against a 14 %
band) and was reverted afterwards; nothing from it reached `main`. Its signature was verified by
measurement rather than assumed, since it was reconstructed from the description rather than restored
from a stash: `01_flat_2color_logo` moves `d42892c0…`/8,969 → `df9670e7…`/8,852.

| run | condition | result | failure set |
| --- | --- | --- | --- |
| 1 | sequential | `15 failed, 1250 passed` | baseline |
| 2 | sequential | `15 failed, 1250 passed` | **identical** |
| 3 | sequential | `15 failed, 1250 passed` | **identical** |
| 4 | **concurrent** with lane 2 | `15 failed, 1250 passed` | **identical** |
| — | lane 2, concurrent | `15 failed, 1244 passed` | — |

**Four full runs, one failure set.** The flake did not reproduce sequentially *or* under the
concurrent condition it was originally observed in.

### 19.2 What the counts said, and the reasoning error they exposed

15 versus the original 16 is fully explained: the reconstruction exports `_own_thick_blend`, so
`test_facade_reexports_every_definition` passes. That left the original pair as **alone → 16,
concurrent → 17**, which pointed back at concurrency — and is why run 4 was added.

Worth recording as a reasoning error of mine: I had refuted two *mechanisms* of concurrency (a
shared-file race that cannot flip a verdict; CPU contention that measurably does not bite) and
treated that as refuting the *association* with concurrency. It does not. Disproving the explanations
one happens to think of is not disproving the correlation. Run 4 tested the association directly and
it, too, came back negative.

### 19.3 Standing position, stated no larger than the evidence

- The clean tree is stable at **1,265 passed** across repeated runs.
- The rule-A tree is stable at **15 failures, identical sets**, across four runs including a
  concurrent one.
- The flake has been observed **exactly once**, among failures, on a tree carrying a rejected
  experimental change, through a truncated file.

That is a materially smaller claim than "the suite is nondeterministic", and it is the claim the docs
now make. It also remains possible that one of the two defects fixed while hunting — the ONNX pin or
the atomic diff write — removed it; that is untested and not asserted.

### 19.4 The durable answer

§10.2: on any red tree, diff the failure set across two runs before classifying anything as an
expected re-pin. A test in one set and not the other is quarantined and named, never waved through.
That defends the actual danger — a flaky failure hiding inside the "expected" set — whether or not
this flake is ever identified.

### 19.5 Two doc corrections, both claims relayed without their conditions

- `QUALITY-DEFECTS-2026-08-10.md` said the SH2 fix was "measured to leave hard-edged flat art
  bit-identical". Never measured, and false for the thickness rule (`01` moves 6,165 → 6,221). Now
  corrected in place, including that it *is* true for the stricter variant.
- `SH2-FINDINGS-2026-08-10.md` dismissed C24 as "a generated rectangle grid with no real-world
  analogue". That conflated appearance with mechanism. A flat region deleted because its colour fell
  between two centres fires whenever artwork exceeds the palette budget — **CB2: 38 of 100 corpus
  designs**. Corrected, with the consequence stated: the two-owned-neighbours variant that loses C24
  is insufficient, not merely conservative.
