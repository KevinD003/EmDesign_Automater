# v1 Baseline Audit — STITCHIQ auto-digitizer

**Date:** 2026-07-28 · **Tag:** `v1-baseline` · **Harness:** `apps/backend/scripts/run_quality_bench.py`
**Artifacts:** [`v1-baseline-grid.png`](./v1-baseline-grid.png) · [`v1-baseline-summary.json`](./v1-baseline-summary.json) · per-fixture PNG+JSON in [`v1-baseline/`](./v1-baseline/)

> This is the number every future digitizer change is graded against. It is deliberately
> unflattering. Scores were produced by ten independent graders (one per fixture, each
> reading the input art, the stitch output, and the measured metrics), then each score was
> put through a second adversarial reviewer instructed to assume the first was too generous
> and to lower anything it could not justify from the image. Where the two disagreed, the
> **challenged (lower) score stands**, and the disagreement is noted.

---

## 1. What was measured, and against what

Ten fixtures live in `apps/backend/tests/fixtures/quality_bench/`. All are **original art
generated programmatically** by `_generate_fixtures.py` in that folder — no third-party or
copyrighted images are used, and the corpus is byte-reproducible by re-running that script.

| # | Fixture | Case it probes |
|---|---|---|
| 01 | `flat_2color_logo` | The easy case: two flat colors, hard edges, big shapes |
| 02 | `logo_fine_text_3color` | Small text inside a logo; knocked-out (white) type |
| 03 | `gradient_soft_subject` | Continuous tone / soft edges (photo-like) |
| 04 | `thin_line_outline` | Line art — ring outlines and thin spokes, no solid areas |
| 05 | `wordmark_caps` | All-caps bold sans lettering |
| 06 | `wordmark_script` | Fine modulated strokes (serif italic standing in for script) |
| 07 | `circular_badge` | Crest: concentric rings, star, straight text + curved text |
| 08 | `mascot_detail` | Many small features: eyes, catchlights, freckles, whiskers |
| 09 | `nonuniform_background` | **Non-uniform background** — the documented failure mode (STATUS §9) |
| 10 | `low_contrast_subject` | Subject within ~30 RGB of its backdrop — probes the ΔBGR<40 background cut |

Two honest caveats about the corpus:

- **No real photograph.** Fixture 03 is synthetic photo-like art (a shaded sphere with a soft
  shadow), because no photo could be sourced license-cleanly in this environment. It still
  carries the property that matters — continuous tone with no hard edge to threshold — but a
  real photo would be harder still.
- **No true script font.** No CC0 script/cursive face ships on the build image, so fixture 06
  uses a serif *italic*. It exercises the same weakness (thin, width-modulated strokes with
  fine terminals) but a real connected script would stress it further.

**Baseline provenance.** These numbers were captured at commit `0d7125b`, which is *after* the
usability fixes in that commit — including a digitizer change (tatami row pitch 0.6 → 0.45 mm)
and a lettering change (min region 4 mm² → 0.5 mm² for text). The baseline therefore reflects
the pipeline as it stands today, not as it stood before those fixes. Outputs here would be
*worse*, not better, without them. `digitizer.py` and the renderer have a **zero-line diff in
this Part-0 commit** — the harness only imports them.

---

## 2. Objective metrics (no judgement, just counts)

Rendered by the app's own preview renderer (`services.package.render_preview`), so this is
what a customer receives in the production package — not a harness-private drawing.

| Fixture | Colors asked → got | Objects | SATIN / TATAMI | Jumps | Trims | Stitches <0.5 mm | Stitches | Est. min |
|---|---|---|---|---|---|---|---|---|
| 01 flat_2color_logo | 2 → **2** | 2 | 0 / 2 | 77 | 0 | 80 | 1,699 | 2.1 |
| 02 logo_fine_text_3color | 3 → **2** | 4 | 0 / 4 | 140 | 2 | 236 | 3,289 | 4.1 |
| 03 gradient_soft_subject | 4 → **3** | 3 | 0 / 3 | 278 | 0 | 321 | 3,900 | 4.9 |
| 04 thin_line_outline | 2 → **1** | 14 | 4 / 10 | 187 | 13 | 309 | 1,377 | 1.7 |
| 05 wordmark_caps | 2 → **1** | 6 | 1 / 5 | 173 | 5 | 292 | 1,371 | 1.7 |
| 06 wordmark_script | 2 → **1** | 13 | 5 / 8 | 77 | 12 | 364 | 1,094 | 1.4 |
| 07 circular_badge | 4 → **2** | 13 | 0 / 13 | **718** | 11 | **617** | 4,083 | 5.1 |
| 08 mascot_detail | 5 → **3** | 13 | 0 / 13 | 303 | 10 | 288 | 2,039 | 2.5 |
| 09 nonuniform_background | 4 → 4 | 4 | 0 / 4 | 78 | 0 | **677** | 5,816 | 7.3 |
| 10 low_contrast_subject | 4 → **3** | 4 | 0 / 4 | 144 | 1 | 272 | 2,612 | 3.3 |

What the numbers say on their own, before anyone looks at an image:

- **8 of 10 fixtures lost at least one color.** Only 01 and 09 returned the requested count.
  Every fixture containing text lost a color — which is precisely the text being merged into
  its background plate instead of becoming its own thread.
- **Satin is used in 3 of 10 fixtures — 10 of 76 objects (13%).** The badge (13 objects) and
  the mascot (13 objects) are **100% tatami** despite both being full of thin strokes and small
  text. This single fact explains most of the "blocky text" complaint.
- **Jump counts are production-hostile.** The badge needs 718 jumps across 13 objects — about
  55 jumps per object. That is a trim-heavy, thread-break-prone sew-out, not a clean one.
- **Sub-0.5 mm stitches are everywhere** (617 on the badge, 677 on fixture 09). Stitches that
  short cause thread breaks and needle strikes on a real machine.
- **One genuine pass:** no fixture emitted a stitch over the 12.7 mm machine limit (max
  observed 9.0 mm), nothing crashed, nothing warned, and all ten ran in 2.2 s total. The
  pipeline is **robust and fast — it is the accuracy that is failing, not the plumbing.**

---

## 3. ⚠️ A confound found while auditing: the preview renderer misstates coverage

Most graders' single loudest complaint was "the fill has white gaps — fabric shows through".
**That complaint is largely wrong, and the reason matters.**

`services.package.render_preview` draws every stitch run as a PIL polyline with a hard-coded
`width=2` **pixels**, independent of scale. At the default 5 px/mm that happens to be ≈0.4 mm —
about a real thread — but the rasteriser puts 2-pixel strokes on rows spaced ~2.1 px apart, and
integer rounding lets a 1–2 px white line slip between them. Render the same design at 20 px/mm
and the "coverage" gets *worse* (white area 33% → 80%), which is impossible for a real fill and
proves the gaps are in the drawing, not in the stitches.

Measuring the actual stitch geometry instead of the picture:

| | Measured | Professional reference |
|---|---|---|
| Fill row pitch (fixture 01, blue disc) | **0.281 mm** median | 0.40 mm typical |
| Rows with pitch > 1.0 mm (real holes) | **0 of 232** | 0 |
| Stitch density | **0.59 st/mm²** | 0.62 st/mm² (0.4 mm pitch × 4 mm stitch) |
| Fixtures with any >1 mm row gap | **0 of 10** | 0 |

At a 0.28–0.42 mm pitch with 0.4 mm thread the rows *overlap*: coverage is complete. Several
graders reasoned from the harness's `stitch_density_per_mm2` field (0.4–0.6) that the fill was
"an order of magnitude below a functioning tatami (4–8 st/mm²)". That reference figure is wrong —
4–8 st/mm² would be a stitch every 0.125–0.25 mm² — and the field is stitches per **bounding-box**
mm², not per filled mm², so it reads low for any design with empty space.

**Consequences, recorded honestly:**

1. Every coverage-driven deduction below is **confounded** and should be treated as unproven.
   The scores are still a valid *floor* (the non-coverage defects are independently corroborated
   by the metrics table), but the absolute numbers are harsher than the stitches deserve.
2. There is a **real defect here, just a different one**: this misleading PNG is shipped to the
   customer inside the production package ZIP (`build_package` → `<stem>-preview.png`). The
   product is showing customers gaps that will not exist in the sew-out. Logged for a later
   part — *not* fixed here, since Part 0 must not touch rendering logic.
3. **Action for Part 1's re-run:** grade coverage from stitch geometry (row pitch vs. thread
   width), not from the preview bitmap, and/or scale the preview's stroke to `px_per_mm × 0.4`.

---

## 4. Scores

Ten independent graders scored, then ten adversarial reviewers re-scored with instructions to
assume the first pass was generous. **The adversarial pass lowered at least one score on all
10 fixtures** — no grader survived unchallenged. Final (challenged) scores stand:

| Fixture | Background / edge | Contour smoothness | Lettering | Stitch-type fit | Customer verdict |
|---|:---:|:---:|:---:|:---:|---|
| 01 flat_2color_logo | 2 | 1 | — | 1 | ❌ reject |
| 02 logo_fine_text_3color | 2 | 2 | 1 | 1 | ❌ reject |
| 03 gradient_soft_subject | 1 | 2 | — | 1 | ❌ reject |
| 04 thin_line_outline | 2 | 1 | — | 1 | ❌ reject |
| 05 wordmark_caps | 1 | 2 | 1 | 1 | ❌ reject |
| 06 wordmark_script | 2 | 1 | 1 | 1 | ❌ reject |
| 07 circular_badge | 1 | 1 | 1 | 1 | ❌ reject |
| 08 mascot_detail | 1 | 1 | — | 1 | ❌ reject |
| 09 nonuniform_background | 1 | 1 | — | 1 | ❌ reject |
| 10 low_contrast_subject | 2 | 2 | 1 | 1 | ❌ reject |
| **Mean** | **1.5** | **1.4** | **1.0** | **1.0** | **0 / 10 acceptable** |

**Stitch-type appropriateness scored 1/5 on every single fixture** — the most uniform result in
the audit, and the one least affected by the render confound, because it is corroborated by the
`stitch_types` counts rather than by looking at pixels.

### Worst defect per fixture (render-artifact claims excluded)

| Fixture | Defect that would fail a customer |
|---|---|
| 01 | Blue fill stops 5–6 mm short of the gold triangle on ~half the scanlines, leaving a bare registration gap; contour breaks into detached dashes at the disc extremities |
| 02 | **The white layer was never generated.** Both lines of type — the point of the logo — exist only as unstitched voids in the green. On any non-white garment the type simply is not there |
| 03 | Continuous tone collapsed into concentric hard-edged bands; the soft drop shadow became a hard grey crescent larger than in the source |
| 04 | The inner ring is not a ring — it survives as four detached arc fragments. Line art is area-filled (10 TATAMI) instead of stroked |
| 05 | 5 of 6 letters are tatami-filled instead of satin — the "blocky text" complaint, measured |
| 06 | 1–4 mm script strokes fed to tatami; every character breaks into disconnected horizontal dashes. 13 objects for 7 letters = fragmentation |
| 07 | "HARBOR CLUB" stitches as "**HARBOR C UB**" (the L is gone); the curved "· ESTABLISHED 1908 ·" is entirely absent; 4 colors → 2; **718 jumps across 13 objects** |
| 08 | Cream dropped entirely → muzzle and both eye-whites unstitched. Round eyes became flat rectangular bars; all 5 freckles and both catchlights vanished |
| 09 | **Total subject/background failure.** The gradient backdrop was quantised into two extra colors and stitched as large teal and tan areas — the majority of 5,816 stitches are background |
| 10 | "LC" illegible — the L's stem survives as two stray 2-px dashes; subject and backdrop merge into one grey mass |

---

## 5. Root causes (what Parts 1–5 actually have to fix)

Ranked by how many fixtures they damage:

1. **Background separation is a corner-color heuristic** (`_is_background`, ΔBGR < 40 vs. the
   average of four corners). Fails completely on a non-uniform backdrop (09) and on a
   low-contrast subject (10). → **Part 1 / Part 5.**
2. **Color quantisation loses layers.** 8 of 10 fixtures returned fewer colors than requested;
   in 02 and 08 the lost layer *was the subject* (white type; cream muzzle). k-means on raw BGR
   has no notion of "this is a distinct design element". → **Part 1 / Part 5.**
3. **Almost everything becomes tatami.** 10 of 76 objects satin; the badge and mascot are 100%
   tatami. Small text and thin strokes need satin or running stitch, and the classifier's fixed
   0.8–4 mm × aspect-2.5 window never fires on them. → **Parts 2 and 3.**
4. **No stroke/line primitive.** Outlines and thin art are area-filled and shatter into dashes
   (04, 06). → **Parts 2 and 4.**
5. **Contours are raw pixel chains**, so edges are stepped and small features drop out
   (freckles, catchlights, the 'L'). → **Part 1 (smoothing).**
6. **Routing is naive** — 718 jumps / 13 objects on the badge, and hundreds of sub-0.5 mm
   stitches per fixture. Real machines break thread on this. → cross-cutting.

## 6. What "better" has to mean

Re-run `python scripts/run_quality_bench.py --tag v2-<part>` and compare against
`v1-baseline-summary.json`. Part N is an improvement only if:

- **no regression** in the objective table (colors preserved, jumps down, no stitch > 12.7 mm,
  no new sub-0.5 mm stitches), **and**
- the targeted fixtures move up on the 1–5 scale, graded from **stitch geometry** rather than
  from the preview bitmap (see §3), **and**
- at least one fixture reaches an "accept" verdict by Part 3. Today that count is **0 / 10**.

**Headline baseline: mean 1.2 / 5 across all criteria, 0 of 10 fixtures acceptable to a
customer.** The pipeline is fast (2.2 s for ten designs), crash-free, warning-free, and emits
no stitch beyond the machine limit — the engineering is sound. What it cannot yet do is decide
*what* to stitch and *how* to stitch it.
