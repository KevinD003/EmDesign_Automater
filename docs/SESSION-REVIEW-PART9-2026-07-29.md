# STITCHIQ v2 — Part 9 Work Report for Independent Review

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part9-audit.md`](./benchmarks/v2-part9-audit.md)

> **Penetration-floor violations: 5 → 3.** Back to the pre-mitre count, with **no coverage number
> moving on any of the ten fixtures**. The cost is 27 extra sub-0.5mm stitches — §2.

---

## 1. Task 1 — closed, including the attempt that failed

The five, located exactly:

```
07  Satin 1    UNDERLAY  0.1828mm   pre-existing (Part 5)
07  Satin 13   UNDERLAY  0.0000mm   pre-existing (Part 5)
07  Satin 13   column    0.0618mm   <- Part 8 mitre
07  Satin 13   column    0.2659mm   <- Part 8 mitre
08  Satin 16   column    0.2519mm   pre-existing (Part 7)
```

**Mechanism confirmed by experiment, not assertion** — fixture 07 run four ways: mitre on +
coalescing on → **4**; mitre on + coalescing **disabled** → **2**; mitre off → 2 either way.
Disabling `_coalesce_short` alone removes both new violations.

**The attempt that did not work, reported rather than dropped.** Part 8 guarded the *outgoing* path
step from a mitred point; I added the *incoming* one, on the theory that the collapse was adjacent to
the mitre. **No change — still 5.** The short step is not adjacent: coalescing *cascades*, because
each drop re-bases the comparison for the next point and shifts which points survive across the run.

**What worked:** `_coalesce_short` never drops a mitred endpoint or the point right after one.

| protection | violations | sub-0.5mm stitches |
|---|---|---|
| none (v2-part8) | 5 | 6 |
| mitred point only | 4 | 25 |
| **mitred + following (shipped)** | **3** | **33** |

## 2. The cost

**Sub-0.5mm stitches 6 → 33.** That is a *different* machine constraint — `MIN_STITCH_MM` exists
because short penetrations break thread and strike needles — so this trades one safety property
against another. The brief makes the penetration floor the hard guarantee, so it wins here, but the
trade is real. **The narrower fix** — restore only the specific dropped point that causes a
violation, rather than protecting every mitred point — would avoid it and was not attempted in the
time available.

## 3. Task 2 — no signal exists, and I am not forcing one

The suggested discriminator was single-continuous-branch vs two-branches-meeting. Measured:

```
butt-jointed V        branches=3   sample counts [166, 169,   9]
letter probe apex_V   branches=3   sample counts [207,   8, 205]
```

**Identical topology** — two arms plus a short apex spur, both cases. I built the gate anyway
(excluding stations within 4 pitches of a junction end) and it measured **inert**: `apex_M` edge band
92.1 → 92.2, nothing else moved, butt joint still 97.3 → 95.1. **Removed rather than kept as
decoration.** The real difference is the outline at the tip — concave notch vs convex — which is a
shape test, not a topology test, and is not cheap.

## 4. Task 3 — `MITRE_MIN_STALLED` sensitivity

| value | corpus int / band / viol | letter int / band | curvature int / band |
|---|---|---|---|
| 2 | 97.41 / 94.06 / 3 | 96.33 / 91.05 | 94.72 / 85.08 |
| **3 (shipped)** | **97.59 / 94.20 / 3** | **97.08 / 92.17** | **95.48 / 85.90** |
| 4 | 97.54 / 94.05 / 3 | 97.20 / 92.10 | 95.46 / 85.12 |
| off | 96.71 / 93.54 / 3 | 97.08 / 92.30 | 93.80 / 81.88 |

3 is best or joint-best on the corpus and curvature probe; 4 edges it only on letter interior
(97.20 vs 97.08). Note **violations are 3 at every setting now** — with the coalescing fix in, the
floor no longer depends on this constant, which it did before.

## 5. Task 4 — comment corrected

The test comment said "apex_M 96.6 → 97.9, apex_V 98.1 → 98.7". Correct: **96.6 → 97.3** and
**98.1 → 97.8**. The wrong pair came from an intermediate build taken before the `MIN_STITCH_MM`
guard; the audit had the shipped numbers, the comment did not. Fixed, with the provenance noted in
the comment.

## 6. What moved

**No coverage number moved on any fixture, to one decimal.** The only changes are stitch counts on
02 (+10), 06 (+8), 07 (+13), 08 (+8) — the protected points coalescing previously removed.
Curvature and junction probes are **byte-identical**; the letter probe moved only `apex_M`'s edge
band, 92.2 → 92.1.

## 7. Verification

```
pytest — WITH rembg:     115 passed, 1 warning in 27.83s
pytest — WITHOUT rembg:  115 passed, 1 warning in  9.11s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

floor violations:      5 -> 3        classification: identical to v2-part8
over 12.7mm:           0             colours / segmentation / area: identical
sub-0.5mm stitches:    6 -> 33  (the cost, §2)

digitizer.py 94%   measure_stitch_quality.py 95%   run_quality_bench.py 65% (pre-existing)
```

`_mitre_one_side` hit 71 lines and `_revert_bad_mitres` was split out; nothing added exceeds 50.
`ruff` 14 findings, all pre-existing. Secrets clean. No net new constants.

**Worth challenging:** `_MITRED_POINTS` is module-level mutable state cleared per object. Threading
the flag properly would have meant four signature changes to carry one bit, and the file already sets
that precedent with `_CLASSIFICATION_LOG` — but it is state, and a test pins the no-leak property
precisely because state is how bugs hide.

## 8. What to attack

1. 3 violations bought with 27 sub-0.5mm stitches. Right trade? The narrower fix is unattempted.
2. No topology signal for butt joints. Build the outline-notch test, or accept the mitre as slightly
   wrong there?
3. `_MITRED_POINTS` as module state — worth four signature changes to remove?
4. The remaining 3 are 2 underlay + 1 column, unchanged since Part 7. The underlay double-back has
   now survived five parts as a known, unfixed producer.
