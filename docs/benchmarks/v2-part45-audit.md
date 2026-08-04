# v2 Part 45 — R011: knocked-out artwork is not the page

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** R011, ranked #1 by the reviewer — *"content loss, Claude's own regression
from Part 41. The fix needs to satisfy both fixture 02 (keep enclosed text) and the
neckline panel (drop enclosed bare cloth) simultaneously."*

Fixed. The wordmark is back with **more thread than it ever had**, the panel still leaves
the cloth bare, and **nine of ten bench fixtures are byte-identical** — the tenth is the
one that was broken.

---

## 1. What was wrong

Part 41 made a substrate-coloured cluster never stitch on raster input. That was right for
the case it was measured on: a photograph of a black garment, where the cloth showing
between the design's elements was being sewn in black thread.

It was applied to flat artwork as well, and there the "substrate" is the **page**. On
fixture 02 the white wordmark sits inside a green card on a white page, matched the
substrate, and was deleted whole.

## 2. The two discriminators I measured first, and why both failed

The reviewer and I both expected enclosure to be the answer. It is not.

| Feature | fixture 02 (must keep) | neckline panel (must drop) |
|---|---:|---:|
| Enclosed by foreground | **99.9%** | **92.8%** |
| Enclosed area in blobs ≥0.30mm half-width | 85.9% | 88.5% |

Both cases are overwhelmingly enclosed, and the panel's gaps are *wider* than the
wordmark's glyphs (max half-width 1.51mm against 0.84mm). Neither enclosure nor thickness
separates them. This is why Part 44 stopped rather than guessing — the obvious hypothesis
was wrong, and shipping it would have re-broken the black panel.

Measuring these needed the real clustering, not a stand-in. The first probe reimplemented
k-means and reproduced neither case. What made it possible was Part 42: `_plan` became the
module-level `_plan_palette`, so the actual palette stage could be spied on.

## 3. What does separate them: the input class

A photograph of a garment is cloth. A flat export is a page. `_interior_texture` already
distinguishes them, and the margin is wide:

| Input | texture |
|---|---:|
| Flat bench fixtures (10) | **0.00 – 4.10** |
| Photographs of cloth | **8.41 – 10.90** |

against an existing threshold of 6.0. So:

- **Textured input (a photograph of fabric)** — unchanged from Part 41. The whole
  substrate-coloured cluster is left unstitched. The instruction that produced Part 41 is
  preserved exactly.
- **Flat artwork** — a substrate-coloured component is the page when it **reaches** the
  page, or when it is **too large to be knocked-out detail**. Otherwise it is artwork and
  it gets stitched.

## 4. The size half, which the harness forced me to add

My first version kept every enclosed component on flat art. It restored the wordmark — and
**filled fixture 04's ring with 176 white stitches on white fabric**. The interior of an
outline ring is enclosed by the ring and is still the page.

The visual harness from Part 44 caught that in one run, on its second fixture. That is the
second time in two parts it has caught something no metric did, this time catching *my own
fix* rather than an old one.

Measured share of foreground per enclosed component:

| Component | area | share | verdict |
|---|---:|---:|---|
| fixture 02 wordmark glyphs (28) | ≤17.6 mm² | ≤0.33% | **keep** |
| fixture 04 ring hub | 97.6 mm² | 2.1% | drop |
| fixture 06 script counter | 48.1 mm² | 7.4% | drop |
| fixture 04 ring interiors | 1512 / 2546 mm² | 32.5% / 54.7% | drop |

Two gates, both restored in spirit from the pre-Part-41 rule that Part 41 deleted:

- `SUBSTRATE_ENCLOSED_MAX_SHARE = 0.05` — 15× above the wordmark, 6.5× below the ring.
- `SUBSTRATE_ENCLOSED_MAX_MM2 = 40.0` — 2.3× above the wordmark, 2.4× below the hub.

The old rule's absolute cap was **8.0 mm²** and is deliberately not reused: it was
calibrated for catchlights (a mascot's is ~4 mm²) and would have kept only the smaller half
of the wordmark's letters, which is worse than dropping all of it. This remains a heuristic
over a genuine ambiguity — knocked-out type and a glyph counter are the same shape,
separable only by scale — and the pre-Part-41 code said so too.

## 5. Result

| Fixture 02 | before Part 41 | Part 41–44 (broken) | now |
|---|---:|---:|---:|
| Colour stops | 4 | 3 | **4** |
| Objects | 7 | 6 | **16** |
| Stitches | 6,221 | 6,185 | **6,895** |

Note the wordmark is **not merely restored**: pre-Part-41 it carried only 31 white stitches,
because the old blanket rule was already eating most of it. It now sews properly.
"NORTHFIELD" is legible in the render. The smaller second line ("EST. 1974 · SUPPLY CO.")
is still lost to the speck filters — a pre-existing limitation, not part of this defect.

**Scope, measured rather than asserted this time:**

- **All 4 stitch-stream locks byte-identical.**
- **9 of 10 visual baselines at SSIM 1.000000**; only fixture 02 changed, and it was the
  broken one. Its baseline is updated.
- **Corpus tier A: 13 designs, 0 errors, 0 empty.**
- Both neckline panels: closest colour stop to the cloth is **13.9** and **110.9**, against
  a `SUBSTRATE_DELTA` of 12.0 — nothing cloth-coloured is stitched.
- `tests/test_part41_no_background_thread.py` passes unchanged.

## 6. Tests — `tests/test_part45_knockout_vs_page.py` (6)

The both-sides check whose absence let the original defect through. All three behaviours
the rule has to get right at once:

- flat art **keeps** type knocked out of a solid shape;
- flat art **does not stitch** the page inside an outline ring (the case my first fix broke);
- a photograph of cloth **still never** stitches the cloth — using the real committed panel,
  because a synthetic stand-in scored 0.0 on `_interior_texture` and would have read as flat
  art, quietly testing the wrong branch;
- the thresholds keep their measured margins, so a later edit cannot narrow them silently;
- and both real bench fixtures land on the correct side.

`test_fixture_02_still_stitches_its_wordmark` is no longer an xfail.

## 7. Honest residual

`_interior_texture` measures texture, not provenance, so a **rotated or rescaled flat
logo** scores as textured (resampling noise) and keeps Part 41's blanket behaviour — its
knockouts would still be dropped. That is not a regression: it is what ships today for
every input. A better "is this a photograph of fabric" signal would fix it, and it is worth
doing when something else needs that signal too.

## 8. Files

- `apps/backend/app/services/digitizer/pipeline.py` — the substrate rule, split by input class
- `apps/backend/app/services/digitizer/constants.py` — `SUBSTRATE_ENCLOSED_MAX_SHARE`, `SUBSTRATE_ENCLOSED_MAX_MM2`
- `apps/backend/tests/test_part45_knockout_vs_page.py` — new
- `apps/backend/tests/test_visual_regression.py` — xfail flipped to a passing assertion
- `apps/backend/tests/visual/baselines/02_logo_fine_text_3color.png` — updated
- `docs/benchmarks/v2-part45-contact-sheet.png`

## 9. Verification

| Gate | Before | After |
|---|---|---|
| Backend suite | 817 passed, 3 xfailed | **824 passed, 2 xfailed** |
| Frontend tests | 131 passed | **131 passed** |
| `ruff check app` | 12 | **12** |
| Stitch stream locks | 4 pass | **4 pass, unchanged** |
| Visual baselines | 10/10 | **10/10** (1 intentionally updated) |

## 10. Next

R004 — stitch direction at 49.9°, the largest remaining quality gap, and the first change
the Part 44 harness will show in before/after form across all ten fixtures.

*(One correction to the reviewer's queue: R001, the `digitizer.py` split, was completed in
Part 42 — ten modules, layering test-enforced. It is listed there as still pending.)*
