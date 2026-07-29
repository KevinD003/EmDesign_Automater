# Physical fabric test protocol — validating the pipeline's safety constants

**Status: NOT YET EXECUTED.** This document exists because v2 Part 12's brief asked for physical
test-stitch results, and no prior part of this project has ever produced any. Nothing in this
repository can run an embroidery machine: every safety constant below is asserted from practice,
carried honestly as such since Part 6, and stays asserted until a human executes this protocol.
Writing fictional results would violate the honesty rules in `docs/ENGINEERING_STANDARDS.md`;
writing the protocol is the largest step toward validation this environment can take.

## What is being validated

| Constant | Value | What it claims | Carried since |
|---|---|---|---|
| `MIN_STITCH_MM` | 0.5 | below this stitch length, thread break / needle strike risk | Phase 4 |
| `MIN_PENETRATION_MM` | 0.30 | same-side penetrations packed tighter than this perforate the fabric | Part 5 (enforced Part 6) |
| `DENSITY_FLAG_PER_CELL` | 14 per 0.5mm cell | pile-up above this damages fabric / builds a thread callus | Part 12 |
| `PULL_BY_FABRIC` | 0.15–0.5mm/side | per-fabric pull compensation values produce true-to-art widths | Phase 8 |
| `MAX_STITCH_MM` | 6.0 (limit 12.7) | machine-safe stitch length ceiling | Phase 4 |

Note on the industry 0.5mm running-stitch rule: it is a stitch-length rule and maps to
`MIN_STITCH_MM = 0.5` — already the cited value. `MIN_PENETRATION_MM = 0.30` bounds a different
quantity (same-side spacing). The protocol tests both independently.

## Equipment

- Single- or multi-needle embroidery machine (any of Tajima, Brother PR, Janome MB, Melco) with
  75/11 sharp and 75/11 ballpoint needles.
- 40wt polyester thread (the pipeline's `THREAD_WIDTH_MM = 0.4` assumption), 60wt bobbin.
- Fabrics, minimum one hooping each: **(a)** standard woven cotton ~150gsm, **(b)** knit/performance
  piqué, **(c)** anti-pill fleece, **(d)** terry towel or sherpa (high pile). Optional: leather/vinyl.
- Stabilizers per fabric: cutaway 75gsm for knits/fleece, tearaway for wovens, water-soluble topping
  for terry.
- Loupe or macro phone camera; calipers.

## Test pieces

Generate the machine files from the repo (each writes a DST via the export path, so this also
exercises the writer):

1. **Penetration-spacing ladder.** Satin bars whose same-side spacing steps
   0.50 / 0.40 / 0.35 / 0.30 / 0.25 / 0.20 / 0.10mm. Produce by digitizing the curvature probe with
   the floor disabled (`set_penetration_floor(None)`) and enabled, exporting both.
2. **Stitch-length ladder.** Running-stitch rows at 1.0 / 0.7 / 0.5 / 0.4 / 0.3mm stitch length.
3. **Density pile-up patch.** A 10×10mm square digitized normally, then the same square stitched
   2×, 3×, 4× over itself (the editor's duplicate-object path) — cells reach ~14, ~21, ~28
   penetrations per 0.5mm cell.
4. **The real corpus.** Fixtures 05 (wordmark), 07 (badge), 08 (mascot) at production settings for
   each fabric, using the fabric's `PULL_BY_FABRIC` value.

## Procedure (per fabric)

1. Hoop with the fabric-appropriate stabilizer; note machine, needle, speed (≤800spm for the ladders).
2. Sew piece 1. **Record per rung:** thread breaks, visible fabric perforation when held against
   light, bobbin show-through, and whether the bar edge is clean or serrated.
3. Sew piece 2. **Record per rung:** thread breaks, needle strikes, whether stitches resolve or bury.
4. Sew piece 3. **Record per layer count:** hand feel (callus?), fabric distortion around the patch,
   any needle deflection sounds, holes on removal from hoop.
5. Sew piece 4. **Record:** measured column widths vs the design's mm (calipers) → validates
   `PULL_BY_FABRIC`; overall registration; any of the ladder failure modes appearing in real designs.
6. Photograph everything front and back, against light for the perforation shots.

## Acceptance / adjustment rules

- If perforation or serration appears at 0.30mm on fabric (a) or (b): **raise
  `MIN_PENETRATION_MM`** to the smallest clean rung and re-run the Part 6 floor sweep to re-measure
  the coverage cost at the new value.
- If 0.25mm and below are clean on all fabrics: the floor stays 0.30 with margin, and the Part 6
  "asserted, not measured" caveat can finally be removed from the code comment.
- If the 2× pile-up (≈14/cell) shows damage: **lower `DENSITY_FLAG_PER_CELL`**; if 4× is clean on
  all fabrics, raise it and say so in the audit — the flag is provisional in both directions.
- If measured satin widths deviate >0.15mm from design width on any fabric: adjust that fabric's
  `PULL_BY_FABRIC` entry; the table's values have the same asserted-not-measured status as the floor.
- Every change lands as one constant + one audit section with the sew-out photos, per the
  established per-part format.

## Recording template

```
fabric: ____________  stabilizer: ____________  machine: ____________  needle: ____
piece 1 (spacing):  0.50 __  0.40 __  0.35 __  0.30 __  0.25 __  0.20 __  0.10 __
piece 2 (length):   1.0 __   0.7 __   0.5 __   0.4 __   0.3 __
piece 3 (pile-up):  2x __    3x __    4x __
piece 4 widths mm:  design ____ measured ____   breaks: ____  notes: ____________
(marks: OK / S=serrated / P=perforated / B=thread break / N=needle strike)
```
