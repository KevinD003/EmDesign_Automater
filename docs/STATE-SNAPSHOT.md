# STITCHIQ — current state, for the reviewer

**Generated at STATUS v89, latest part 51.** Paste this alongside any
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
| R004 | Stitch direction (49.9°) | **Part 46 investigation; D0+D1 Part 50; D2 measured and REVERTED Part 51.** A straight fill row cannot consume a field — see below. **D3 (satin) next, after a two-pass restructure** |
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
| Backend tests | **874 passed, 2 xfailed** | Part 51 |
| Frontend tests | 131 passed, `tsc` clean | Part 48 |
| `ruff check app` | 12 (the standing baseline) | Part 51 |
| Stitch-stream locks | **4** fixtures, sha256 of the whole stream | — |
| Visual baselines | 10, gate SSIM ≥ 0.995 | Part 44 |
| Corpus | 100 designs, **0 errors**, **7** zero-stitch, interior median **98.70** | Part 48 |
| Reference panel | 663 trims, 18.26 m jump travel | Part 48 |
| Direction error | **49.9°** mean vs a real sew-out (45° = coin flip) | Part 46, unchanged |
| `digitize_image` | 822 lines inside `pipeline.py` (1,131) | Part 42 |

Two figures that circulated and are **wrong**: "9 zero-stitch designs" (it is 7, and one of
the nine was a blank fixture) and "16 phantom stitch types" (it was 13 misleading names
behind 9 real behaviours).

## What is genuinely open

1. **R004 — the direction field. D2 was built, measured and reverted (Part 51).**
   Part 46 ruled out four explanations for the 49.9°. Part 50 built the instrument and a
   contour-parallel field scoring **33.91°** against the current **38.27°** on the
   photographed sew-out. **Part 51 wired it into tatami fills and took it back out.**

   Three findings decide what happens next, all measured on the panel:

   - **A straight row cannot use a field.** On tatami territory the field is worth
     **7.75°** per pixel (40.09 → 32.34). Collapsing it to the one angle a scanline fill
     accepts captures **4.26°**, or **55%**. The rest is unreachable by any threshold —
     over a ring the field runs all the way round and its doubled-angle mean cancels to
     zero, so no single angle is even approximately right.
   - **The seed mask is most of the field's quality.** Solved on the union of object
     contours: **32.34**. On each colour cluster: **35.31**. On the segmentation
     foreground silhouette: **38.84**. My first D2 used the last one and produced a change
     that a **constant 90° beat** (37.05 vs 38.32). That was my defect, not the field's.
   - **The bar cannot resolve a tatami-only change.** Tatami is **9.3%** of the panel's
     area. Field, constant and random all land within **0.7°** on the whole-panel number.
     Please do not gate a tatami change on the panel headline again — I did, and it passed.

   **The blocker is architectural, not a threshold.** The winning seed does not exist at
   any point where a fill is generated: object contours are produced inside the cluster
   loop, after the field would have to be solved. The seed that *is* available (per
   cluster) measures worse collapsed (38.94) than the one it would replace. Consuming the
   validated field needs `digitize_image` split into two passes — build all region masks,
   solve, then generate. That is the next thing to build and it is a prerequisite.

   **D3 is satin, and the reason is stronger than area.** Satin is **93.7%** of the panel
   against tatami's 9.3%, carries the same headroom (37.90 → **33.49** per pixel), and a
   satin column already varies its angle along its length — so it consumes a field with no
   regional collapse. Curved tatami rows are the other half and need their own scoping.

   Reproduce any of it: `scripts/measure_field_consumption.py`.
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
- **Ask for the control, not just the score.** Part 51's D2 beat its target and was still
  wrong: a constant angle beat it on the same territory. A brief that says "and show me
  what a trivial baseline scores" would have caught it in one line.
