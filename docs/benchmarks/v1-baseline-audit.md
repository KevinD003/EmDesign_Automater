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
