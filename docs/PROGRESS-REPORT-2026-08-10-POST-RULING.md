# Progress report — execution of the CTO ruling of 2026-08-10

**For review.** Self-contained: a reviewer needs this file, `CTO-RULING-2026-08-10.md` (the
instructions being executed) and `CONSOLIDATED-REPORT-2026-08-10.md` (the state before it). Picks up
exactly where the ruling left off and covers everything to `224b850`.

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

Commits 1–4 are shipped-code changes affecting every upload; 5–7 are the instrument. Both CI lanes
were run to completion before each commit; no commit was pushed on a partial verification.

| commit | lane 1 (default) | lane 2 (`STITCHIQ_NO_REBUILD_PASSTHROUGH=1`) |
| --- | --- | --- |
| `a95df3e` | 1221 passed | 1215 passed |
| `bedc998` | 1221 passed | 1215 passed |
| `9918397` | 1229 passed | 1223 passed |
| `ecad056` | 1231 passed | 1225 passed |
| `0361344` | 1231 passed | 1225 passed |
| `1551fc4` | 1252 passed | 1246 passed |
| `224b850` | 1258 passed | 1252 passed |

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

### Revised order (current)

1. ~~Real-artwork landing site + the fabric axis~~ — **done**, `0361344` / `1551fc4` / `224b850` (§9)
2. **SH2**, with `TEXTURE_RETRY_UNCOVERED` re-derived rather than assumed ← **in progress**
3. The physical-units contract as its own tranche, re-pinned above a 133 mm hoop

Then the veto (Q3 statistic), then 1c, then 3e-i.

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

| fixture | denim → fleece | driver |
| --- | --- | --- |
| 05_wordmark_caps | p90 step **3.8750 → 4.5178** | pull compensation reaching the satin columns (UP1) |
| 01_flat_2color_logo | **6,200 → 4,913** stitches | `row_mm` 0.40 → 0.55 |
| 07_circular_badge | **17,178 → 14,160** stitches; **22.64 → 18.78** machine-minutes | same |

**This finding outlives the task: every headline number in this engagement is a cotton number.** Fill
stitch counts move 17–21 % with fabric. The **22.65 machine-minute** badge figure quoted throughout
this series sits near the top of a 21 % range. Nothing reported was wrong; nothing carried its fabric
label either — and the physical-units tranche will move each fabric differently.

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
