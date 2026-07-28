# STITCHIQ v2 — Part 1 Work Report for Independent Review
**Date:** 2026-07-28 · **Repo:** `KevinD003/EmDesign_Automater` · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Commits:** `a1b4109` (code) · `ec9b0a2` (audit + STATUS) — see §9 for exact list

> Companion to [`SESSION-REVIEW-2026-07-28.md`](./SESSION-REVIEW-2026-07-28.md) (earlier fixes + Part 0).
> Written for a reviewer who did not watch the work. §7 lists what is unproven; §8 lists what to attack.

---

## 1. The task

Part 1 of the phased plan: fix the three highest-impact root causes from the v1 baseline audit
(colour/layer loss, background separation, contour smoothing), plus two already-diagnosed bugs
(`render_preview` stroke width, harness density metric). Explicitly **not** in scope: satin/tatami
classification, pull compensation, fill patterns — those are Parts 2–4.

## 2. The central finding: two root causes were one bug

The audit listed background separation (#1) and colour-layer loss (#2) separately. They are the
same rule failing in opposite directions. v1 decided background by **colour identity** —
`_is_background()` deleted any k-means cluster within ΔBGR < 40 of the four-corner average,
*everywhere in the frame*. Measured per fixture:

| Fixture | Layer | Δ from corner avg | v1 outcome |
|---|---|---|---|
| 02 | white lettering | **0.0** — identical to the page | deleted; type left as unstitched holes |
| 08 | cream muzzle | **34.8** — just inside the cutoff | deleted; muzzle + both eye-whites gone |
| 07 | cream inner disc | **28.0** | deleted; 4 colours → 2 |
| 09 | tan / teal gradient | **53.0 / 50.8** — just outside | **kept**; backdrop embroidered |

No threshold fixes this — 02's white type is *exactly* the background colour. Background had to
become a question of **where a pixel is**, not **what colour it is**.

## 3. What was built

1. **`app/services/segmentation.py` (new)** — returns a foreground *mask*, three tiers with clean
   fallback: **rembg/U2-Net** (MIT, optional, lazily imported, output sanity-checked) → **border
   flood-fill** (region-grows inward with local tolerance; absorbs a smooth gradient backdrop but
   not an enclosed shape) → the **v1 corner heuristic**. Measured: rembg handled all ten fixtures;
   flood-fill alone would have failed 03 (0.6% foreground) and 09 (47.9%), which is why the learned
   tier leads. rembg is declared in `requirements-features.txt` only — it downloads a 176MB model,
   so CI and offline installs must not depend on it.
2. **k-means clusters foreground pixels only** — the colour budget is spent on real design layers
   instead of losing a slot to the background (v1's "+1 for background" fudge is gone).
3. **Substrate rule** — a garment-coloured region is ink only if it passes **enclosure** (fully
   surrounded by ink: a catchlight inside a pupil passes; the aperture of a "G" opens onto the
   background and fails) **and** size caps (a ring's interior is enclosed but is garment showing
   through). Enclosure is topological and carries the decision; size is a guard.
4. **Contour smoothing** — Douglas-Peucker then Chaikin, skipped below 10 points, capped at 1% of
   perimeter, biased toward preservation.
5. **Conditional morphological opening** — v1's unconditional 3×3 opening erased ~2px strokes,
   which is what deleted the "L" from HARBOR CLUB.
6. **Speck threshold 4.0 → 2.0 mm²** so the mascot's 2.6 mm² freckles survive.
7. **Sub-0.5 mm coalescing** — needle penetrations closer than 0.5 mm are merged; they break thread
   and strike needles and cost nothing to remove.
8. **`render_preview` stroke scales with `px_per_mm × 0.4`** instead of a hard-coded 2px.
9. **Harness metrics** — density over *filled* area (bbox version retained for comparability), plus
   `fill_row_pitch_mm` / `coverage_ratio` measured from **stitch geometry, never the bitmap**.

## 4. Objective results (v1 → v2-part1, identical fixtures/params/RNG)

| Metric | v1 | v2-part1 |
|---|---|---|
| Colour count matching the request | 2 / 10 | **5 / 10** |
| Sub-0.5 mm stitches, all fixtures | 3,456 | **2** |
| Fixture 09 stitch count (background) | 5,816 | **1,010** |
| Stitches over the 12.7 mm machine limit | 0 | **0** |
| Coverage ratio (from geometry) | — | **1.0 on all ten** |
| Jumps, all fixtures | 2,175 | **2,768 — REGRESSION** |

## 5. The five acceptance questions

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | 02's white text stitches? | **YES** | 2→3 colours; new `#f2f5f4` stop, 398 stitches; verified by plotting that stop alone on grey |
| 2 | 08's cream muzzle stitches? | **YES** | 3→5 colours; `#faf0e0` 797 st + `#fefefe` catchlights 20 st; freckles and round eyes visible |
| 3 | 07's "L" reappears? | **YES** | crop: v1 "HARBOR C **U**B" → v2 "HARBOR **CLU**B"; cream disc also stitched (1,904 st) |
| 4 | 09 stops stitching background? | **YES** | 5,816 → 1,010 stitches; output is only the diamond + dot |
| 5 | 10's "LC" legible? | **NO** | colour count unchanged; crops show marginal change only. **Not fixed.** |

## 6. The counterweight — subjective quality barely moved

Same adversarial method as Part 0 (10 graders → 10 adversarial re-graders, challenged score stands):

| | background/edge | contour | colour fidelity |
|---|---|---|---|
| v1 | 3.3 | 2.5 | 3.2 |
| v2-part1 | **3.6** | **2.4** | **3.1** |

Verdicts: **1 improved · 7 mixed · 2 regressed.**

This sits uncomfortably beside §4 and both are true. Part 1 fixed the *named defects* without
lifting *perceived quality*, because what dominates a grader's eye — blocky tatami where satin
belongs, text present but not legible — is untouched by Part 1. Fixture 02 illustrates it: the
white type genuinely stitches now, yet still reads "EORTEFIELD" rather than "NORTHFIELD" because a
6 mm cap-height word rendered as tatami cannot resolve. The missing layer was a Part-1 bug; the
legibility is a Part-2 bug.

### Adversarial review caught a regression I introduced
Reviewers found fixture 01's gold triangle had eroded away from the blue disc, opening a bare
wedge. Verified and traced: **Chaikin corner-cutting shrinks a polygon**, and adjacent layers are
smoothed independently, so they pull apart. Measured white area in the join region:
**v1 27.5% · v2 @ 2 iterations/0.18 mm 41.1% · v2 @ 1 iteration/0.10 mm 27.8%.** Settings reduced;
parity restored; fixture 01's jumps improved 77 → 63 as a side effect.

### Two reviewer findings that were wrong
- **"02's white text isn't stitched."** Wrong, but instructive: `render_preview` draws on a
  near-white ground, so **white thread is invisible**. Re-plotting stop 3 alone on grey shows 398
  stitches forming the wordmark. The observation was right; the inference wasn't. This exposes a
  third rendering defect in the same family as the stroke-width bug — the customer-facing preview
  cannot depict light thread at all. Logged, not fixed (out of scope).
- **"Coverage says 1.0 but there are visible voids."** Actually **right**, and it is a real flaw in
  a metric I added: `coverage_ratio` compares row pitch to thread width, so it detects rows too far
  apart but *not regions never filled*. It must not be used as a gate. Recorded in the audit.

## 7. Known limitations / not fixed

1. **Jumps regressed on 7 of 10** (2,175 → 2,768), violating the brief's no-regression line.
   Evidenced cause: v2 stitches content v1 deleted (objects 76 → 97; fixture 07 gained a
   1,904-stitch cream disc), and the one fixture where content was *removed* improved (09: 78 → 41).
   Proper fix is decomposing annular regions before scanline fill — a fill-pattern change the brief
   reserves for Parts 2–4.
2. **Fixture 05 gains a spurious colour stop** — "SUMMIT" is one ink colour, v2 returns two. The
   extra is a light halo at Δ21.4 from white: too far to trip the substrate rule, too close to be a
   real layer. An "anti-aliasing halo has no interior" suppressor was attempted, broke three tests
   without fixing it, and was **reverted rather than tuning thresholds until fixtures looked right**.
3. **Fixture 10 not fixed** — low-contrast input needs contrast-aware palette selection.
4. **Fixture 02's small second line** ("EST. 1974 · SUPPLY CO.") still produces zero stitches.
5. **rembg costs runtime** — fixture 01 went 0.10 s → 2.58 s; whole bench 2.2 s → ~7 s. It bought
   nothing measurable on clean white-background fixtures where flood-fill agreed with it. A cheap
   "is the background already uniform?" pre-check would skip the model there.
6. **The adversarial scores in §6 graded the pre-smoothing-fix build.** Fixture 01's "regressed"
   verdict is stale (defect since measured back to parity); fixture 05's is not.
7. **Ten synthetic fixtures.** Thresholds risk overfitting. The substrate rule is a heuristic over a
   genuine ambiguity — a glyph counter and knocked-out type are the same shape, separable only by
   scale and enclosure.
8. **Nothing has been stitched on a real machine.** All claims are geometry and renders.

## 8. What a reviewer should attack

1. Is the **enclosure + size** substrate rule principled, or three thresholds fitted to ten images?
   What breaks it — a logo with a large deliberate white knockout on a white-ish garment?
2. Does the **jump regression** actually matter in production, or is sub-0.5 mm elimination
   (3,456 → 2) worth more? Which would a real embroiderer prefer?
3. Is leading with **rembg** justified when flood-fill matched it on 8 of 10 and it costs 25× the
   runtime on easy cases?
4. Is `coverage_ratio` salvageable, or should it be removed until it can detect voids?
5. Do the **§6 scores** invalidate the §4 claims? Is "objective up, subjective flat" a real finding
   or a rationalisation?
6. Is `CHAIKIN_ITERS=1` a fix, or just a smaller dose of a method that is wrong for adjacent layers?
   (Area-preserving smoothing, or smoothing the shared label map once rather than each layer, would
   be the principled fix.)

## 9. Verification and reproduction

**Tests:** pytest **88 passed** · vitest **57 passed** · `tsc --noEmit` clean.
**Files touched** (brief allowed digitizer, the rembg integration, `render_preview`, the harness):
`app/services/digitizer.py` · `app/services/segmentation.py` (new) · `app/services/package.py`
(`render_preview` only) · `scripts/run_quality_bench.py` · `requirements-features.txt` (declaring
the optional dep) · `docs/benchmarks/*` · `STATUS.md` (v35, mandated by its own protocol).

```bash
git checkout claude/code-quality-improvements-hyu6dg
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -r requirements-features.txt      # optional: enables the rembg tier
python tests/make_fixtures.py
python -m pytest tests -q                     # 88 passed
python scripts/run_quality_bench.py --tag v2-part1
cd ../.. && npm install && npm test -w apps/frontend && npm run typecheck
```
Without rembg the pipeline still runs (flood-fill fallback); fixtures 03 and 09 get materially
worse, which is itself a useful measurement.

**Key artifacts:** [`docs/benchmarks/v2-part1-audit.md`](./benchmarks/v2-part1-audit.md) ·
[`v2-part1-grid.png`](./benchmarks/v2-part1-grid.png) · [`v2-part1-summary.json`](./benchmarks/v2-part1-summary.json)
· [`v1-baseline-audit.md`](./benchmarks/v1-baseline-audit.md) (the baseline being beaten)

## 10. Status

Part 1 complete against its stated scope. Parts 2–7 not started — gated on your sign-off.
Part 2 (real satin-stroke lettering) is well motivated by these results: satin remains at 13% of
objects, stitch-type appropriateness is still 1/5 on every fixture, and §6 shows legibility, not
layer recovery, is now the binding constraint on perceived quality.
