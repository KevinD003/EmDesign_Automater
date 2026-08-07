# v2 Part 64 — competitor benchmark and training-data pipeline

**Date:** 2026-08-07 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** benchmark/dataset infrastructure — a repeatable comparison of
STITCHIQ against competitor-grade output, and a trainable data foundation. No
new stitch feature, no new quality claim, no R004 reopening.

*Bookkeeping: the brief was titled "Part 63", but Part 63 (divided Stitch
Flow) had already shipped on this branch; this work is recorded as Part 64.*

**Delivered: a pipeline, not screenshots.** A rerunnable harness
(`scripts/bench_competitor.py`) that measures 8 cases and generates the
report + visual pack; a training-data schema (`docs/TRAINING-DATA-SPEC.md`)
with a four-level provenance taxonomy; an extractor
(`scripts/extract_training_rows.py`) that produced the first **85
schema-validated rows**; and 10 tests that pin the metrics, the inference
calibration, and the schema. Plus the requested test of the angelfish photo —
which turned out to be the most diagnostic case in the set.

---

## 1. The benchmark population, honestly

| tier | cases | what is measurable |
|---|---|---|
| STITCHIQ fixtures | 5 (flat logo, lettering, badge, photo-derived, small-detail) | full object + stream metrics; **no competitor output exists for this artwork** |
| Foreign machine files | 2 (`sample.dst`, `sample.pes`) | stream metrics exact; block types inferred; **no artwork → no matched STITCHIQ side**; both are trivial test patterns (26 stitches) |
| Competitor render | 1 (angelfish, royal-present.ru marketing photo) | **matched artwork**: STITCHIQ digitizes the same image; competitor numerics unavailable (no stitch file); comparison is visual |

**What is missing, stated plainly:** no Wilcom/Hatch native design files, and
no competitor machine files for artwork we can also digitize. Every numeric
cross-comparison in the generated report is therefore marked *not measurable
from the files available* — the harness refuses to flatten this into a score.
The generated report (`docs/benchmarks/competitor-bench/report.md`) carries
this framing; competitor-sourced inputs live in the gitignored
`apps/backend/data/competitor/` so the scripts skip-with-a-note rather than
fail when an input is absent.

## 2. What the harness measures

- **Stream metrics (exact, any source):** stitch/trim/jump counts, jump
  travel (previous-point-to-landing, Part 48's rule), colour stops, extent.
- **Object metrics (STITCHIQ side, observed):** object count, stitch-type
  distribution, holes, small objects (<8 mm², Part 49's boundary), distinct
  angles, median stitches/object.
- **Block inference (machine files, always labelled inferred):** blocks split
  at TRIM/COLOR_CHANGE (jumps do not split — fills jump across holes), then
  run/satin/fill from segment statistics. **Calibrated where truth is known:**
  STITCHIQ's own generators round-tripped through DST come back as themselves
  (pinned test). The discriminators: satin reverses direction on nearly every
  stitch; a run's thread length is ~1–3× its bbox diagonal while a fill's is
  ~50× (the coverage ratio is immune to the thin-bbox trap that makes
  per-area density lie on straight runs — a trap the first version of this
  heuristic fell into and a test caught).
- **Visual pack:** per case, artwork | STITCHIQ render (| competitor render),
  plus a like-for-like fractional crop row. 8 panels in
  `docs/benchmarks/competitor-bench/visual/`.

## 3. The angelfish test (requested)

STITCHIQ digitized the competitor's render at k=4 (canonical run), and k=6/8
as a fairness check. Results:

| | k=4 | k=6 | k=8 |
|---|---|---|---|
| objects | 30 | 27 | 27 |
| stitches | 5,957 | 2,993 | 2,974 |
| stitch types | **SATIN 30** | SATIN 27 | SATIN 27 |

Side-by-side (`visual/angelfish-royal-present.png`), human-judged and
labelled as such:

- **Worse — body-region recovery.** The yellow fish body is mostly unsewn;
  only the black stripes and fragments survived. Raising k makes it *worse*
  (2,993 stitches), so this is segmentation on a photographic, textured
  source — not the colour cap.
- **Worse — decorative run-work.** The competitor surrounds the fish with
  running-stitch swirls and bubbles; STITCHIQ drops them entirely. This is
  R008's motif-along-a-path territory, now visible on a real competitor piece.
- **Worse — noise robustness.** The watermark text digitized into grey blobs.
- **Different, not clearly worse — all-satin typing.** The competitor's fish
  body is itself long satin; STITCHIQ's 30-way satin fragmentation of what
  should be a few large regions is the actual gap (object formation, not the
  satin choice per se).
- **Caveat:** the "artwork" is a photo of sewn embroidery — the hardest
  possible input class — not the vector art the competitor digitized from.
  The verdicts stand as measurements of *robustness on photographic input*,
  not of the core digitizing path on clean art.

The badge fixture independently corroborates gap #2 below: "HARBOR CLUB" and
the ring text digitize into illegible blobs (`visual/07-badge.png`).

## 4. Answers the brief requires

**Top 3 measurable gaps** (from this population; each has a number attached):

1. **Region recovery on photographic sources** — angelfish body lost;
   measurable as sewn-coverage of artwork foreground (the Part 63 coverage
   instrument applies directly). *Lever: algorithm* (segmentation/matte path),
   with model assistance later.
2. **Small text fidelity** — badge text and fish watermark → blobs;
   measurable as legibility of artwork glyph regions vs sewn output. *Lever:
   algorithm + product default* (a text detector routing glyph regions to the
   existing lettering engine would beat pixel-tracing them); editor already
   allows manual replacement.
3. **Object formation / fragmentation on organic shapes** — 30 satin
   fragments where a competitor uses a few large objects; measurable as
   objects-per-region and the existing fragmentation metrics (R005's
   instruments). *Lever: model training eventually* — this is exactly the
   "should this be one object or many" decision the training schema targets —
   *editor controls* (merge/split) as the near-term bridge.

Decorative run-work loss is gap #4 and is already scoped: R008, mask-stage
motif detection, previously measured as direction-field-sized.

**Question 3 — is the competitor data good enough for supervised training?
No.** Level-4 rows (STITCHIQ's own decisions) teach imitation of the current
system; level-2 rows (machine-file inference) lose precisely the properties
worth learning (outlines, density, underlay). Supervision toward
competitor-grade decisions needs **native competitor design files (level 1)
for matched artwork, or a human labelling pass (level 3)** over STITCHIQ
outputs. The schema is identical across all four levels so those rows drop
into the same file when they arrive.

**Optional tiny baseline: deliberately skipped.** A stitch-type classifier
trained on level-4 rows would be scored against the system that generated its
labels — and the angelfish case shows those labels can be systematically
wrong (30/30 SATIN). The first meaningful baseline starts with level-1/3
rows; writing this down beat shipping a circular accuracy number.

## 5. The training dataset, as extracted today

`extract_training_rows.py` → `data/training/rows.jsonl`: **85 rows** (72
`stitchiq_generated` with contours, decisions, measured angles and 58 artwork
crops; 13 `machine_file_inference` with inferred types and nulls — never
guesses — for unobservable fields). Every row passes `validate_row`;
provenance is REQUIRED and a non-null label without `human_labeled`
provenance is a schema violation (pinned by tests). The dataset is derived
and gitignored; the spec, extractor and tests are the tracked artifacts.

## 6. Gates

| Gate | Result |
|---|---|
| Real matched set, not STITCHIQ-alone | ✅ 5 fixtures + 2 foreign files + 1 matched-artwork competitor render; gaps in the population stated, not papered over |
| Report separates worse / different / unmeasurable | ✅ framing section generated into the report; human-judged verdicts confined to this audit and labelled |
| Schema concrete enough to start training | ✅ field-by-field spec + working extractor + 85 validated rows |
| Every label has declared provenance | ✅ enum enforced by `validate_row`, pinned by tests |
| Scripts rerunnable | ✅ two scripts, config-driven, skip-with-note on missing inputs; 10 pinned tests |
| Backend suite | ✅ **943 passed, 2 xfailed** in 777.87 s (933 + 10 new) |
| No frontend changes | ✅ untouched this part (suite last measured Part 63: 165 passed) |
| `ruff check app` | ✅ 12, the standing baseline; all new files clean |

## 7. Files

- `apps/backend/scripts/bench_competitor.py` — harness (metrics, inference,
  visual pack, report)
- `apps/backend/scripts/extract_training_rows.py` — dataset extractor
- `apps/backend/tests/test_part64_benchmark.py` — 10 tests
- `docs/TRAINING-DATA-SPEC.md` — schema + provenance taxonomy
- `docs/benchmarks/competitor-bench/` — report.md, cases/*.json, visual/*.png
