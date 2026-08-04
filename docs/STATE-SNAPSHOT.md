# STITCHIQ — current state, for the reviewer

**Generated at STATUS v91, latest part 53.** Paste this alongside any
audit. It exists because four of the last five review briefs were built on state that had
moved: the fix proposed was already shipped, or the number quoted came from an old run.

---

## Where the R-list stands

| ID | Item | Status |
|---|---|---|
| R001 | Split `digitizer.py` | **Done, Part 42** — 11 modules, layering test-enforced |
| R002 | Phantom `StitchType` members | **Done, Part 43** — 23 members → **10**, catch-all `else` removed |
| R003 | Visual-regression harness | **Done, Part 44** — SSIM 0.995 gate, 10 committed baselines, in `pytest` |
| R011 | Fixture 02 wordmark lost in Part 41 | **Done, Part 45** |
| R004 | Stitch direction | **BLOCKED ON THE REFERENCE, Part 53.** Architecture done (Part 52). But the sew-out photo cannot resolve thread on structures under ~2 mm, which is 77% of the design, so it scores correct satin as wrong and rewards contour-parallel answers. **Needs a macro sew-out at ~0.05 mm/px before any consumer work** |
| R007 | Zero-stitch corpus designs | **Done, Part 47** — premise was wrong; the real fix was 422-instead-of-200 |
| R006 | Trim count | **Done, Part 48** — corpus-wide 33,969 → 27,927 |
| R005 | Fragmentation | Open. **Part 46 proved it will not fix the direction number** |
| R008 | Bead-chain ornament | **Re-scoped, Part 49.** Measured and stopped: the dropped specks do not separate from noise (no knee in the sweep, longest run 10 beads). Needs motif-along-a-path detection at the mask stage — comparable in size to the direction field |

## Things already built that briefs have proposed building

Checked by running the code, not by reading it. Each was proposed as missing:

- **Pull compensation** — since v1, fabric-aware since Part 13. 0.15–0.50 mm/side across 16
  fabrics; finished width 55.20 → 55.80 mm cotton vs fleece.
- **Fabric-aware density** — `FABRIC_PROFILES`, 16 fabrics × 5 parameters. Same bar: denim
  1,462 stitches vs fleece 886.
- **Shape-aware fill direction** — `_fill_angle`, principal axis from central image moments,
  since Part 24. 41 distinct angles across the bench, per-fixture sd up to 67.5°.
- **Path optimisation** — `_route_travel` since Part 25; proximity ordering added Part 48.
- **ML segmentation** — U2-Net matte with a plausibility gate and a classical fallback.
- **Export breadth** — 47 read / 19 write formats.

## Numbers that are current

| | value | measured at |
|---|---|---|
| Backend tests | **888 passed, 2 xfailed** | Part 53 |
| Frontend tests | 131 passed, `tsc` clean | Part 48 |
| `ruff check app` | 12 (the standing baseline) | Part 53 |
| Stitch-stream locks | **4** fixtures, sha256 of the whole stream | — |
| Visual baselines | 10, gate SSIM ≥ 0.995 | Part 44 |
| Corpus | 100 designs, **0 errors**, **7** zero-stitch, interior median **98.70** | Part 48 |
| Reference panel | 663 trims, 18.26 m jump travel | Part 48 |
| Direction error | **49.9°** — but see Part 53: partly an instrument artifact | Part 46 |
| `digitize_image` | 822 lines inside `pipeline.py` (1,131) | Part 42 |

Two figures that circulated and are **wrong**: "9 zero-stitch designs" (it is 7, and one of
the nine was a blank fixture) and "16 phantom stitch types" (it was 13 misleading names
behind 9 real behaviours).

## What is genuinely open

1. **R004 — the direction field. BLOCKED ON THE REFERENCE (Part 53).**

   **Read this before commissioning anything on R004.** The photographed sew-out
   every number since Part 38 is scored against **cannot see thread on a structure
   narrower than its own window**. On such a column the strongest gradients are the
   column's two edges, so the structure tensor reports the **column's axis** —
   perpendicular to the thread actually there. A correctly sewn satin column is
   scored ~90° wrong, and a contour-parallel field is scored right by construction.

   Measured, not inferred. Which does the reference agree with?

   | satin column width | px | vs SEWN | vs AXIS | it reads |
   |---|---:|---:|---:|---|
   | 0–1 mm | 2.7 | 47.36 | **42.64** | edges |
   | 1–2 mm | 8.1 | 50.18 | **39.82** | edges |
   | 2–3 mm | 13.4 | **42.40** | 47.60 | thread |
   | 3–4 mm | 18.8 | **41.76** | 48.24 | thread |

   The crossover holds at windows 5, 9, 15 and 21, so it is width, not tuning. At
   **0.186 mm/px** a 1.5 mm column is 8 px and satin's thread pitch is 2.1 px — at
   the sampling limit. **77% of satin segments sit below the threshold.**

   **Consequences.** A field consumer measured on this panel scores well by
   agreeing with outlines. Part 53 built the segment-level instrument, got a
   **+16.98°** apparent satin win, and traced it to exactly this. On the 23% the
   reference resolves, the field is **2.20° worse** than what we already sew.
   Tatami has nothing left either: the 384 px field (26.27) is already past the
   one-angle-per-region **oracle** (26.54), and finer solving lowers committed
   share (0.663 → 0.625) while costing 13× on noise.

   **Decision recorded: neither satin nor tatami is worth wiring.** Not "not yet
   worth it" — not measurable.

   **The unblocking step is not code.** A macro sew-out photograph at roughly
   **0.05 mm/px** (3–4× the linear resolution, or a close-up of one region rather
   than the whole panel) would put ~8 px on every thread. That is the cheapest
   thing in the entire R004 line and it needs a camera, not an engineer.

   **What still stands.** The field, the instrument, the two-pass architecture and
   Part 52's seed ranking are all unaffected — that ranking used one registration
   and one territory definition throughout. What does not stand is any absolute
   direction number measured on thin artwork, including the **49.9°** headline: on
   resolvable columns our sewn error is **42.3°**.

   Reproduce: `scripts/measure_field_headroom.py` (`--validity`, `--resolution`,
   `--cost`), `scripts/measure_two_pass_seed.py`, `scripts/measure_field_consumption.py`.

2. **R008 — bead-chain ornament.** Still real content loss, but **re-scoped by Part 49**.
   Grouping the dropped specks does not work: coverage rises smoothly 3.5% → 67% as the
   rules loosen, with no knee, and the longest run found is 10 beads. The cause is that
   529 of 771 objects are already ≤8 mm², so "small round region" describes flower centres
   and leaf dots too — and beads under ~4 px never reach the drop log at all. Recovery needs
   motif-along-a-path detection at the mask stage, before colour clustering cuts regions
   apart. Comparable in size to the direction field.
3. **R005 — fragmentation**, median 19 stitches/object. Worth doing on its own merits;
   Part 46 showed it will **not** move the direction number.
4. Cross-colour trim ordering, payments, batch digitizing, i18n, collaboration — see
   `EVALUATION-50-problems-verified.md` for the full open list.

## A standing hazard, twice hit

Part 48's brief said: *"do not introduce a routing-time blowup like Part 48's unbounded
nearest-neighbour pass; bound any grouping algorithm on pathological inputs."* Fair warning,
and Part 49 hit the same class anyway in a different form — a per-region full-image
operation rather than an unbounded loop.

The shape, now written down: **the contour loop runs once per region *before* the speck
filter**, so anything added inside it is multiplied by the *noise* count, not the design
count. The reference panel puts 251 contours in its busiest colour; a 900x900 random-noise
image puts 70,516. Both regressions were invisible to the targeted tests, the stream locks,
the visual baselines and ruff, and both were caught only by the fuzz suite — the second one
28 minutes into a full run. Cost tests now sit in the fast files.

## What would make a brief most useful

- **Ask for the measurement, not the fix.** Four briefs proposed a fix for something already
  built. A brief that says "show me X, and if it is bad, here is what I would try" survives
  contact with the code.
- **Do not set threshold targets in advance.** 0.85 SSIM, 8.0 mm², "<586 trims" and
  ">0.7 correlation" were all proposed before measurement and all turned out wrong or
  reachable only by making the output worse.
- **Assume this file is stale next time too.** Ask for a fresh one.
- **Ask what the instrument can resolve before asking what it says.** Part 53's
  biggest result was that three parts of scoring had been done against a reference
  that cannot measure the thing being optimised on most of the design.
- **Ask for the control, not just the score.** Part 51's D2 beat its target and was still
  wrong: a constant angle beat it on the same territory. A brief that says "and show me
  what a trivial baseline scores" would have caught it in one line.
