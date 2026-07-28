# STITCHIQ — Work Report for Independent Review
**Session date:** 2026-07-28 · **Repo:** `KevinD003/EmDesign_Automater` · **Branch:** `claude/code-quality-improvements-hyu6dg`

> **Purpose of this document.** It is a complete, self-critical record of everything an AI
> assistant (Claude, `claude-opus-5`) changed in this repository during one session, written so an
> independent reviewer can audit the work without having watched it happen. It deliberately
> includes what was *not* done, what is unproven, and one place where the assistant published a
> wrong finding and then corrected it. §8 lists specific questions a reviewer should press on.

---

## 1. What the project is

STITCHIQ is an embroidery design platform: a Python/FastAPI backend that reads and writes machine
embroidery files (`pyembroidery`), auto-digitizes images into stitches (classical OpenCV — k-means
colour quantisation → contour regions → scanline fills), and generates lettering; plus a
TypeScript/React frontend (Konva 2D canvas, Three.js 3D preview) for editing and export.

Two user prompts drove this session:

1. *"This is not perfect. I am not getting good result... Many of the features do not work properly."*
2. A structured plan (`STITCHIQ_Claude_Improvement_Prompt.md`) whose **Part 0** asked for a quality
   benchmark harness and an honest baseline audit, explicitly forbidding any change to the
   digitizing pipeline.

## 2. Commits produced (4)

| Commit | Type | Summary |
|---|---|---|
| `0d7125b` | fix | 9 defects making features fail or look broken |
| `987fc45` | docs | STATUS.md v33 |
| `db7d098` | test | Part 0 — benchmark harness, 10 fixtures, v1 baseline artifacts |
| `ce6da5f` | docs | v1 baseline audit scores + STATUS.md v34 |

Net: **47 files changed, 1,629 insertions, 29 deletions.** Application source touched only in
`0d7125b` and only there: **92 insertions / 12 deletions across 6 files.** The rest is tests,
fixtures, benchmark artifacts, and documentation.

---

## 3. Part A — Response to prompt 1 (commit `0d7125b`)

### 3.1 Method
Rather than reading code and guessing, the app was actually run: backend + frontend booted, every
API endpoint exercised over HTTP through the Vite proxy, and the UI driven in headless Chromium
(Playwright) with screenshots and console/network capture.

### 3.2 The starting state was misreported
`STATUS.md` claimed *"pytest 81/81"*. Actual on a clean Linux checkout: **80 passed, 1 failed**.
The failing test was `test_unsupported_glyphs_rejected`. The documentation overstated the baseline.

### 3.3 The nine defects fixed

| # | Defect | Evidence it was real | Fix |
|---|---|---|---|
| 1 | **Fresh install broken.** The documented setup (`requirements.txt` + `requirements-dev.txt`) omitted `pyembroidery`, so Open / Export / Convert / Package all failed on a clean clone | Reproduced on a fresh venv | Moved `pyembroidery` into core `requirements.txt` |
| 2 | **Dark designs invisible.** Stitches drew on a near-black canvas; black lettering (the default) was unviewable | Screenshot | Light fabric backdrop + stitches at physical thread width (0.4 mm) in `StitchCanvas.tsx` |
| 3 | **Report banners collided.** Check/Quality/Optimize all rendered in one fixed corner, hiding each other and **intercepting pointer events so the Dashboard tab was unclickable** | Playwright click timeout: `<div class="validation-report"> intercepts pointer events` | `.report-stack` container below the toolbar |
| 4 | **Lettering accepted unsupported glyphs.** Emoji rendered as the font's `.notdef` "tofu" box and were digitized into ~299 stitches of garbage rectangles | Reproduced directly | Per-character comparison against U+0378 (permanently unassigned) → reject with a clear message |
| 5 | **Small lettering lost detail.** The dot on `i`/`j` was removed by the digitizer's 4 mm² speck filter | `i` at 8 mm → 1 object; expected 2 | New `min_region_mm2` parameter; lettering passes 0.5 mm² |
| 6 | **Sparse fill.** Tatami row pitch 0.6 mm | See caveat in §7.2 | 0.6 → 0.45 mm |
| 7 | **Nav overlap.** Studio/Dashboard toggle reused an absolutely-positioned class and sat on top of Sign-in | Screenshot | `.page-nav .view-toggle { position: static }` |
| 8 | **Confusing thread names.** DST (a colourless format) surfaced pyembroidery's filler threads literally named "Random" | Parsed output | → `"Color n (file has no color data)"` |
| 9 | Favicon 404 | Console | Inline SVG icon |

### 3.4 Verification
- pytest **80 passed / 1 failed → 83 passed** (+3 new regression tests)
- vitest **57/57**, `tsc --noEmit` clean, production build clean
- Full headless-Chrome re-drive: **zero console errors, zero failed requests** (before: favicon 404 + the blocked-click failure)

---

## 4. Part B — Response to prompt 2, Part 0 (commits `db7d098`, `ce6da5f`)

### 4.1 Hard constraint respected
Part 0 required a **zero-line diff on `digitizer.py`** — measurement only. Verified:
`git diff HEAD -- apps/backend/app/` is empty across both Part 0 commits. The harness *imports*
the pipeline; it does not modify it.

### 4.2 Fixture corpus — `apps/backend/tests/fixtures/quality_bench/`
Ten fixtures. All are **original art generated programmatically** by `_generate_fixtures.py`
(PIL/NumPy), so there is no third-party or copyright question and the corpus is byte-reproducible.

`01` flat 2-colour logo · `02` 3-colour logo with fine text · `03` soft-edge gradient subject ·
`04` thin-line outline art · `05` all-caps wordmark · `06` script-style wordmark ·
`07` circular badge with straight + curved text · `08` high-detail mascot ·
`09` **non-uniform background** · `10` **low-contrast subject**

`09` and `10` were added beyond the brief because `STATUS.md` §9 documents the background
heuristic as a known weakness; the corpus should contain cases the pipeline is expected to fail.

### 4.3 Harness — `apps/backend/scripts/run_quality_bench.py`
Emits per-fixture output PNG + JSON, a combined `<tag>-summary.json`, and a labelled input→output
grid. Design decisions worth reviewing:
- Renders through the **app's own** `services.package.render_preview`, so the audit grades what a
  customer actually receives in the production ZIP, not a harness-private drawing.
- `--tag` plus a **pinned OpenCV RNG seed** make future runs diff-able. Verified deterministic:
  two consecutive runs produced identical metrics.
- Per-fixture digitize parameters are declared in the script (not chosen per run) so a
  before/after comparison is like-for-like.
- Guarded by 5 tests in `tests/test_quality_bench.py` (pytest 83 → **88**).

### 4.4 Objective baseline results

| Fixture | Colours asked → got | Objects | SATIN / TATAMI | Jumps | Stitches |
|---|---|---|---|---|---|
| 01 flat_2color_logo | 2 → 2 | 2 | 0 / 2 | 77 | 1,699 |
| 02 logo_fine_text_3color | 3 → **2** | 4 | 0 / 4 | 140 | 3,289 |
| 03 gradient_soft_subject | 4 → **3** | 3 | 0 / 3 | 278 | 3,900 |
| 04 thin_line_outline | 2 → **1** | 14 | 4 / 10 | 187 | 1,377 |
| 05 wordmark_caps | 2 → **1** | 6 | 1 / 5 | 173 | 1,371 |
| 06 wordmark_script | 2 → **1** | 13 | 5 / 8 | 77 | 1,094 |
| 07 circular_badge | 4 → **2** | 13 | 0 / 13 | **718** | 4,083 |
| 08 mascot_detail | 5 → **3** | 13 | 0 / 13 | 303 | 2,039 |
| 09 nonuniform_background | 4 → 4 | 4 | 0 / 4 | 78 | 5,816 |
| 10 low_contrast_subject | 4 → **3** | 4 | 0 / 4 | 144 | 2,612 |

- **8 of 10 fixtures lose at least one colour.** In `02` the lost layer was the white type; in
  `08` it was the cream muzzle — i.e. the lost layer *was the subject*.
- **Satin is chosen for 10 of 76 objects (13%).** Badge and mascot are 100% tatami.
- **Passing:** no stitch exceeded the 12.7 mm machine limit; zero crashes; zero warnings; 2.2 s
  for all ten designs.

### 4.5 Scoring method and result
Ten independent graders (one per fixture, each reading input art + stitch output + metrics), then
ten **adversarial reviewers** instructed to assume the first pass was too generous and to lower
anything they could not justify from the image. **The adversarial pass lowered at least one score
on all ten fixtures.**

**Final: mean 1.2 / 5 · 0 of 10 fixtures customer-acceptable.**
Stitch-type appropriateness scored **1/5 on every fixture** — the most uniform result, and the one
least dependent on visual interpretation since it is corroborated by the `stitch_types` counts.

Representative concrete defects: `07` stitches "HARBOR CLUB" as "**HARBOR C UB**" (the L is gone)
and drops the curved "ESTABLISHED 1908" entirely; `08` renders round eyes as flat rectangular bars
and loses all 5 freckles and both catchlights; `09` stitches most of its background.

---

## 5. Part C — A process failure worth recording

Two of the twenty grading agents hung permanently. Both had escalated from *looking* at the images
to running quantitative pixel analysis via shell commands; those calls hit a permission prompt that
a sub-agent cannot answer, so they blocked forever holding pipeline slots, which starved the four
agents queued behind them. The user noticed the stall before the assistant did.

Diagnosis was from the agents' own transcripts (`[Request interrupted by user]`). Remedy: constrain
that stage to read-only tools and resume from the cached run, so completed work was not repeated.
**Lesson: the most rigorous agents failed precisely because they tried to measure rather than
eyeball.** Worth noting for anyone building similar review pipelines.

---

## 6. Part D — A published finding that was wrong, and corrected

This is the most important item for a reviewer to scrutinise.

**The claim (made by most graders, and repeated by the assistant to the user):** the fills have poor
coverage — visible white gaps, fabric showing through. It was reported as a headline defect.

**It was wrong.** Measuring the stitch geometry rather than the picture:

| | Measured | Professional reference |
|---|---|---|
| Fill row pitch (fixture 01) | **0.281 mm** median | ~0.40 mm |
| Rows with pitch > 1.0 mm | **0 of 232** | 0 |
| Stitch density | **0.59 st/mm²** | 0.62 st/mm² |
| Fixtures with any >1 mm gap | **0 of 10** | 0 |

At 0.28–0.42 mm pitch with 0.4 mm thread the rows overlap — coverage is complete. The decisive
test: re-rendering the same design at 20 px/mm makes apparent coverage *worse* (33% → 80% white),
which is impossible for a real fill. The cause is `render_preview` drawing fixed **2-pixel**
polylines regardless of scale.

Several agents compounded the error by citing "4–8 st/mm² for a functioning tatami" as their
reference — that would be a stitch every 0.125 mm², which is not a real figure.

**Outcome:**
- The audit doc (§3) flags every coverage-driven deduction as **confounded and unproven**; the
  non-coverage defects are corroborated by the metrics table and stand.
- A **real but different** defect was identified: this misleading PNG ships to customers inside the
  production package ZIP. It was **not fixed**, because Part 0 forbids touching rendering logic. It
  is logged for a later part.
- The assistant corrected its own earlier statement to the user rather than leaving it standing.

---

## 7. Known limitations — please challenge these

1. **The baseline is not the original pipeline.** It was captured at `0d7125b`, which already
   includes two digitizer constant changes from Part A (row pitch 0.6 → 0.45 mm; lettering
   min-region 4 → 0.5 mm²). Documented in the audit §1, but a reviewer may reasonably argue the
   baseline should have been taken *before* any change.
2. **The 0.6 → 0.45 mm row-pitch change was never benchmarked.** By the same arithmetic used in §6,
   0.6 mm would give ~0.56 mm pitch against 0.4 mm thread — genuine partial coverage — so the change
   is defensible, but this is **inference, not measurement**. The pre-change pipeline was never run
   through the bench.
3. **No real photograph in the corpus.** Fixture 03 is synthetic photo-like art. A real photo would
   be harder.
4. **No true script font.** Fixture 06 uses a serif italic; no CC0 script face was available.
5. **Scores are AI-generated judgements, not human embroiderer judgements**, and are partly
   confounded per §6. The objective metrics table is the more trustworthy artifact.
6. **Nothing was ever stitched on a real machine.** All quality claims are from geometry and
   renders.
7. **CI remains unverified** — the workflow config has still never run.
8. **Branch differs from the plan.** The plan named `feat/studio-dashboard`; work went to
   `claude/code-quality-improvements-hyu6dg` because the session was pinned there.
9. **Supabase cloud paths were exercised only in keyless in-memory fallback** — no live
   credentials were available, so auth returned 503 by design.

## 8. Questions a reviewer should press on

1. Does §6 fully retract the coverage claim, or does residual coverage-based reasoning still leak
   into the per-fixture scores in the audit?
2. Is `stitch_density_per_mm2` (stitches per **bounding-box** mm²) a misleading metric to publish at
   all, given it invited exactly the misreading in §6? Should it be per *filled* area?
3. Is grading through `render_preview` sound in principle (it's what customers see), or does §6
   prove the harness should measure geometry directly?
4. Are the per-fixture digitize parameters in `FIXTURE_PARAMS` fair, or do they flatter the pipeline?
5. Does a 1.2/5 baseline risk being *too* harsh — making almost any later change look like an
   improvement?
6. Is the ~0.4 mm thread-width assumption used throughout §6 correct for standard 40-weight
   embroidery thread?

## 9. Reproducing everything

```bash
git clone <repo> && cd EmDesign_Automater && git checkout claude/code-quality-improvements-hyu6dg
npm install
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python tests/make_fixtures.py

python -m pytest tests -q                      # expect 88 passed
python tests/fixtures/quality_bench/_generate_fixtures.py   # regenerates the corpus identically
python scripts/run_quality_bench.py            # regenerates the baseline; metrics are deterministic
cd ../.. && npm test -w apps/frontend          # expect 57 passed
npm run typecheck && npm run build -w apps/frontend
```

**Key files:** `docs/benchmarks/v1-baseline-audit.md` (the audit) ·
`docs/benchmarks/v1-baseline-grid.png` (visual proof) ·
`apps/backend/scripts/run_quality_bench.py` (harness) ·
`apps/backend/tests/fixtures/quality_bench/_generate_fixtures.py` (corpus) · `STATUS.md` (project log)

## 10. Status

Part 0 is complete against its stated acceptance criteria: grid exists with varied real outputs;
the audit is specific and critical (no score above 2 on any criterion); `digitizer.py` has a
zero-line diff; STATUS.md carries a changelog entry (v34). Parts 1–7 of the improvement plan are
**not started** — they were explicitly gated on sign-off of Part 0.
