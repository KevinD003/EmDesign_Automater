# STITCHIQ — current state, for the reviewer

**Generated at commit `8bcf218`, STATUS v87, latest part 49.** Paste this alongside any
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
| R004 | Stitch direction (49.9°) | **Investigation done, Part 46.** Implementation not started — see `PROMPT-direction-field.md` |
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
| Backend tests | **854 passed, 2 xfailed** | Part 49 |
| Frontend tests | 131 passed, `tsc` clean | Part 48 |
| `ruff check app` | 12 (the standing baseline) | Part 49 |
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

1. **R004 implementation — the direction field.** The largest remaining quality gap.
   Part 46 ruled out four explanations for the 49.9° (convention bug, fragmentation,
   satin-specific, misregistration) and showed per-region PCA is at its ceiling. Scope is
   in `docs/PROMPT-direction-field.md`. Multi-part.
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
