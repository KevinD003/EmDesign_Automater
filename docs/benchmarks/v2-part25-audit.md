# v2 Part 25 — working the blocker list: concurrency, honesty, locks, travel, merging, SVG

**Date:** 2026-08-01 · Branch `claude/code-quality-improvements-hyu6dg`
Executes items 1–5 and 7 of [`../COMPETITIVE-BLOCKERS.md`](../COMPETITIVE-BLOCKERS.md)'s
recommended order, each researched against practice and measured before/after.
Items 6 (full branching/sequencing), 8 (lettering engine) and 9 (photo digitizing)
are **not** in this part — 6 got a substantial down-payment (travel routing), 8 and 9
remain the two large absences they were.

Baseline `v2-part24b`, result `v2-part25`, same container, same seed.

---

## 1. Item 1 — the event-loop blocker (shipped, verified in shipped code)

Every CPU-bound handler (`digitize`, `lettering`, `export` ×3, `convert`,
`worksheet` ×2, `optimize` ×2, `files.parse`, `designs.rebuild`) was `async def`
calling synchronous CPU work — which FastAPI runs **on the event loop**. All are now
plain `def`, dispatched to the threadpool.

| Probing `/health` every 250ms during a 12.6s digitize | Probes completed | Max latency |
|---|---|---|
| Before | **0** | never returned |
| After (shipped) | **37** | 857 ms |

With the runbook's `--workers 1`, this was "one user digitizing freezes everyone".

## 2. Item 2 — silent failures now speak (shipped, calibrated)

`Design.warnings` (backend model + frontend banner). Three signals, and **two drafts
were measured and thrown away first**:

| Draft | Why rejected |
|---|---|
| Count dropped regions | Cries wolf: the badge at a *comfortable* hoop drops ~1,650 anti-aliasing specks |
| Area share via `contourArea` | Reads thin linework as missing: fixture 04 scored "92% lost" with every line emitted |
| Pixel share of owned foreground | Confounds edge-shaving with loss: fixture 06's script read "27% lost", all strokes emitted |

What shipped: **(a)** element-level loss — owned foreground components no emitted
object touches at all; **(b)** a fine-detail scale heuristic (`source px/mm ≥ 10`),
because the dominant loss channel at small hoops is colour-merge during quantization,
which no post-hoc filter accounting can see; **(c)** the colour contract explained
("requested 4; artwork separated into 2").

Calibration: **10/10 fixtures quiet at intended hoops; badge into 70×70 and 40×40
both warn.** The 40×40 case that silently deleted 81% of objects now says so.

## 3. Item 3 — locks, trims, and travel (shipped; three measured failures on the way)

The stream had no tie-off code and 1,206 jumps, 638 of them past the 12.7mm machine
limit untrimmed. The blunt fix (trim every long jump) was counted and rejected: 695
trims × ~2.5s ≈ half an hour of machine time. What shipped instead:

* **`_route_travel`** — a jump whose path stays inside the object's own region
  becomes a hidden 2mm travel run; with a **boundary-detour fallback**: a fill row
  hopping across a hole now travels *around* it along the edge the border satin
  covers. Measured on a plain donut: **72 trims → 1**.
* **`_lock_stream`** — a lock triangle before every TRIM/COLOR_CHANGE/END and after
  every cut; remaining cross-fabric jumps > 10mm get tie-off + TRIM.
* Applied to `rebuild_design` too (a rebuilt donut carried 63 hole-crossing trims
  until it got the same routing).

Three failures, each caught by measurement, each already the corpus's own lesson:

| # | Failure | Evidence | Fix |
|---|---|---|---|
| 1 | Fixed 0.7mm back-step tie | **92 floor violations** — on a 0.4mm-pitch satin end it lands 0.3mm from the previous hole | Adaptive leg length |
| 2 | Adaptive length alone | Still 12 — a satin end's back-direction points **straight along the zig line**; the leg grew to 1.6mm and still landed 0.05mm from an old hole | Rotate the lock off the line (±35°/±70° candidates) |
| 3 | Travel out-and-back turnarounds | 11 violations at 0.05–0.18mm — the same needle-in-one-hole reversal as Part 11's underlay dead-ends | Same repair: `_drop_floor_reversals` re-run after routing |

Final floor count: **0**, with locks at every cut.

## 4. Items 4 + 7 — UI drift and stop merging (shipped)

* Underlay dropdown now lists every generator-produced type; before, an object
  carrying Part 24's `DOUBLE_ZIGZAG`/`PARALLEL` rendered as a **blank** select.
* `_merge_adjacent_same_hex`: consecutive stops of one thread collapse — colour
  changes **19 → 17** (fixtures 04 and 06 now mount one thread, not two).
  The other 3 avoidable changes are **non-adjacent** deferred-detail stops and are
  deliberately not merged: they exist for layering, and merging across an
  intervening colour would re-order the sewing. Stated, not hidden.

## 5. Item 5 — SVG import (shipped; the root cause starts closing)

`_decode_svg` (svglib + rlPyCairo, pinned in requirements): the artwork is rendered
**twice, on white and on black** — an opaque pixel is identical in both renders, so
the exact foreground mask falls out with no neural matte and no substrate guessing.

| Probe | Result |
|---|---|
| 3-colour badge SVG | 5 objects, colour stops **exactly** `#1e3a5f / #f5f0e0 / #d7a52d` — the source hexes |
| Same art as 400px PNG | comparable (5 objects) but colours re-estimated through anti-aliasing |
| **White artwork on a white page** | **digitizes** (`#ffffff` + `#c03030`) — invisible to every raster heuristic by definition. Found the substrate rule deleting it and gated that rule off for vector input, where foreground is declared, not guessed |
| Garbage bytes | still rejected with 415 |

The measured Part-22 class of bug (U2-Net deleting the wordmark) **cannot occur** on
this input path.

## 6. Corpus, before → after (all guardrails held)

| | Part 24b | Part 25 |
|---|---|---|
| Mean interior / edge band | 98.62 / 97.62 | **98.72 / 97.91** |
| Mean spill | 12.22 | 12.59 (+0.37 — travel + locks near edges) |
| Floor / over-limit / flagged density | 0 / 0 / 0 | **0 / 0 / 0** |
| Jumps | 1,216 | **822** |
| Untrimmed jumps > machine limit | 638 | **0** |
| Cuts without a lock | all of them | **0** |
| Colour changes | 19 | **17** |
| Trims | 54 | 535 |
| Stitches | 45,589 | 53,044 (+16.4%) |
| Tests | 698 | **714** (pytest 710+2xf, +vitest 114) |

Two costs, stated plainly: **+16.4% stitches** (travel runs and locks are real
thread), and **535 trims** — high against the industry's <1-per-block, but each one
replaces what was previously an *untrimmed thread trail* dragged across the design
and cut by hand. Getting trims down further is item 6's sequencing work, not a
threshold to fiddle.

Density note: the corpus's densest cell rose 10 → 11 penetrations — it is now a lock
site, which is 3–4 deliberate penetrations by design. Flag level 14 untouched;
flagged cells 0.

## 7. Honestly not done

* **Item 6 in full** — one-entry/one-exit branching and sequence optimization to cut
  the 535 trims and remaining 822 jumps structurally.
* **Item 8, lettering engine** and **item 9, photo digitizing** — months each,
  unchanged from the blockers doc.
* SVG `<text>` elements depend on svglib's font resolution — shapes and paths are
  the reliable path today; convert text to outlines on export from the design tool.
* `max_colors` over-ask (10 requested → 4 delivered) is now *explained* but the
  segmentation itself still decides the count.
