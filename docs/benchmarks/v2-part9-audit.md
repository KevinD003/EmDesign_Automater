# v2 Part 9 Audit — closing the floor regression the mitre introduced

**Date:** 2026-07-29 · **Tag:** `v2-part9` · graded against [`v2-part8`](./v2-part8-summary.json)

**Penetration-floor violations: 5 → 3.** Back to the pre-mitre count, with coverage on all ten
fixtures unchanged to one decimal. The cost is 27 extra sub-0.5mm stitches, reported in §2.

---

## 1. Task 1 — the regression, located and closed

**Exactly where the 5 were**, per fixture, per object, and whether underlay or column:

```
07_circular_badge   Satin 1 (#122854)    UNDERLAY  0.1828mm   pre-existing since Part 5
07_circular_badge   Satin 13 (#122854)   UNDERLAY  0.0000mm   pre-existing since Part 5
07_circular_badge   Satin 13 (#122854)   column    0.0618mm   <- introduced by the Part 8 mitre
07_circular_badge   Satin 13 (#122854)   column    0.2659mm   <- introduced by the Part 8 mitre
08_mascot_detail    Satin 16 (#de6c26)   column    0.2519mm   pre-existing since Part 7
```

Part 7's three were the first, second and fifth. Part 8 added exactly two, both columns in
`Satin 13` — matching the brief.

**The mechanism, confirmed by experiment rather than asserted.** Running fixture 07 four ways:

| | violations |
|---|---|
| mitre ON, coalescing ON (Part 8 as shipped) | **4** |
| mitre ON, coalescing **disabled** | **2** |
| mitre OFF, coalescing ON | 2 |
| mitre OFF, coalescing disabled | 2 |

Disabling `_coalesce_short` alone removes both new violations. So the interaction is real and is
exactly where Part 8 §6 said it was.

**A first attempt that did not work, reported rather than quietly dropped.** Part 8 guarded the
*outgoing* path step from a mitred point (`|mid[i] − other[i]| ≥ MIN_STITCH_MM`). I added the
*incoming* step (`|mid[i] − other[i−1]|`) on the theory that the collapse was adjacent to the mitre.
**It changed nothing — still 5.** The short step that triggers coalescing is not adjacent to the
mitred point; coalescing cascades, because each drop re-bases the comparison for the next point and
shifts which points survive across the whole run.

**What worked:** `_coalesce_short` never drops a mitred endpoint, nor the point immediately after
one. Coalescing changes *which* points survive, and that shift is what breaks the strict A-B-A-B
alternation `_enforce_floor` depends on. Two variants measured:

| protection | violations | sub-0.5mm stitches |
|---|---|---|
| none (v2-part8) | 5 | 6 |
| mitred point only | 4 | 25 |
| **mitred point + the one after it (shipped)** | **3** | **33** |

## 2. The cost, stated plainly

**Sub-0.5mm stitches go 6 → 33** across the corpus. That is a different machine constraint —
`MIN_STITCH_MM` exists because short penetrations break thread and strike needles — so this trades
one safety property against another rather than getting something for nothing.

The brief is explicit that the penetration floor is "the one hard machine-safety guarantee in this
project since Part 6", so it is the one that wins here. But the trade is real and a reviewer may
reasonably want the reverse. **A narrower fix that would avoid it** — restore only the specific
dropped point that causes a violation, instead of protecting every mitred point — is the obvious
follow-up and was not attempted in the time available.

## 3. Task 2 — no joined/butt signal exists in the topology

The brief suggested a discriminator: whether the boundary either side of the stall belongs to a
single continuous medial-axis branch or to two branches meeting. **Measured, that difference does not
exist**:

```
butt-jointed V (two cv2.line calls)   branches=3   sample counts [166, 169,   9]
letter probe apex_V (joined)          branches=3   sample counts [207,   8, 205]
```

Both are two arms plus a short apex spur. Identical topology.

A gate was implemented anyway — excluding stations within `4 × pitch` of a branch end that
`_free_ends` reports as a junction — and **measured inert**: fixture `apex_M` edge band 92.1 → 92.2,
nothing else moved, and the butt joint still went 97.3 → 95.1. **It was removed rather than kept as
decoration.**

The real difference is in the **outline at the tip** — a butt joint has a concave notch where a
joined apex is convex. That is a shape test, not a topology test, and is not cheap. **No clean signal
found; saying so rather than forcing one**, as the brief allowed.

## 4. Task 3 — `MITRE_MIN_STALLED` sensitivity

| value | corpus interior / edge band / violations | letter probe int / band | curvature probe int / band |
|---|---|---|---|
| 2 | 97.41 / 94.06 / **3** | 96.33 / 91.05 | 94.72 / 85.08 |
| **3 (shipped)** | **97.59 / 94.20 / 3** | **97.08 / 92.17** | **95.48 / 85.90** |
| 4 | 97.54 / 94.05 / **3** | 97.20 / 92.10 | 95.46 / 85.12 |
| off | 96.71 / 93.54 / **3** | 97.08 / 92.30 | 93.80 / 81.88 |

3 is the best or joint-best on the corpus and the curvature probe, and within 0.12 of the best on the
letter probe (4 edges it on letter interior, 97.20 vs 97.08, and loses on everything else). Notably
**violations are 3 at every setting now** — with the coalescing fix in, the floor no longer depends
on this constant, which it did before.

## 5. Task 4 — the incorrect comment

`test_mitre_closes_a_sharp_apex_without_breaking_the_floor` said the letter-probe comparison was
"apex_M 96.6 → 97.9, apex_V 98.1 → 98.7". The correct figures are **96.6 → 97.3** and
**98.1 → 97.8**. The wrong pair came from an intermediate build taken before the `MIN_STITCH_MM`
guard was added; the audit had the shipped numbers, the comment did not. Fixed, with the provenance
noted in the comment so the discrepancy is not mysterious later.

## 6. Corpus — precisely what moved

| Fixture | interior p8 → p9 | edge band p8 → p9 | spill p8 → p9 | stitches |
|---|---|---|---|---|
| 01 | 98.7 → 98.7 | 94.6 → 94.6 | 2.1 → 2.1 | 1,632 → 1,632 |
| 02 | 99.0 → 99.0 | 97.1 → 97.1 | 3.7 → 3.7 | 3,714 → **3,724** |
| 03 | 97.9 → 97.9 | 92.6 → 92.6 | 7.7 → 7.7 | 3,228 → 3,228 |
| 04 | — | 99.9 → 99.9 | 47.1 → 47.1 | 1,861 → 1,861 |
| 05 | 95.3 → 95.3 | 89.5 → 89.5 | 11.1 → 11.1 | 1,492 → 1,492 |
| 06 | 97.7 → 97.7 | 92.3 → 92.3 | 21.0 → 21.0 | 1,219 → **1,227** |
| 07 | 97.9 → 97.9 | 95.5 → 95.5 | 4.8 → 4.8 | 7,804 → **7,817** |
| 08 | 96.7 → 96.7 | 92.3 → 92.3 | 4.0 → 4.0 | 5,004 → **5,012** |
| 09 | 99.0 → 99.0 | 93.3 → 93.3 | 3.9 → 3.9 | 1,006 → 1,006 |
| 10 | 98.6 → 98.6 | 94.4 → 94.4 | 3.0 → 3.0 | 2,389 → 2,389 |

**No coverage number moved on any fixture, to one decimal.** The only things that moved are stitch
counts on 02 (+10), 06 (+8), 07 (+13) and 08 (+8) — the protected points that coalescing previously
removed. That is the whole footprint of this part.

**Probes.** Letter: `apex_M` 97.3 / 92.1, `apex_U` (control) 96.9 / 91.2, `apex_V` 97.8 / 95.1,
`apex_narrow` 96.3 / 90.3 — `apex_M`'s edge band moved 92.2 → 92.1, everything else identical to
v2-part8. Curvature: `r8w` 99.3 / 94.6, `r4w` 98.2 / 91.0, `r2w` 94.1 / 82.8, `r1.25w` 86.5 / 72.8 —
**all identical**. Junction: `equal_30deg` 97.7 / 94.7, `hairline_30deg` 99.5 / 98.1,
`hairline_60deg` 99.7 / 97.8, `medium_30deg` 99.3 / 98.3 — **all identical**. Violations 0 on the
letter and curvature probes, 1 on `hairline_30deg` (unchanged, pre-existing).

## 7. Verification

```
pytest — WITH rembg:     115 passed, 1 warning in 27.83s
pytest — WITHOUT rembg:  115 passed, 1 warning in  9.11s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

floor violations:                                   v2-part8  5  ->  v2-part9  3
classification (stitch_types + all 96 verdicts):    identical to v2-part8
stitches over the 12.7mm machine limit:             0
colour / segmentation / filled area:                identical on all ten
sub-0.5mm stitches:                                 6 -> 33   (the cost, §2)
```

Two tests added: coalescing must not drop a mitred endpoint, and the module-level mitred register
must not leak between objects.

| §1 Coverage (floor 80%) | Cover |
|---|---|
| `app/services/digitizer.py` | **94%** |
| `scripts/measure_stitch_quality.py` | **95%** |
| `scripts/run_quality_bench.py` | 65% ⚠ pre-existing, untouched |

**§3 Size.** `_mitre_one_side` reached 71 lines and `_revert_bad_mitres` was split out of it; nothing
added by this part exceeds 50. Pre-existing over-limit: `digitize_image` 336, `rebuild_design` 129,
`_skeleton_branches` 76, `_skeleton_satin` 55. `digitizer.py` 2,081 lines, the standing exception.

**§4 Security.** Secrets scan clean. No new constants; `MITRE_JUNCTION_MARGIN` was added for the
rejected gate in §3 and removed with it. **§1 Lint.** `ruff` 14 findings, all pre-existing.

**One design note worth challenging:** `_MITRED_POINTS` is module-level mutable state, cleared per
object in `_satin_columns`. Threading the flag through `_column_ends → _emit_columns →
_skeleton_satin → digitize_image` would have meant four signature changes to carry one bit. The file
already sets this precedent with `_CLASSIFICATION_LOG`, and a test pins the no-leak property — but it
is state, and state is how bugs hide.

## 8. What to attack

1. §2 — 3 floor violations bought with 27 extra sub-0.5mm stitches. Right trade? The narrower fix
   (restore only the point that causes a violation) is unattempted.
2. §3 — no topology signal for butt joints. Is the outline-notch test worth building, or should the
   mitre simply be accepted as slightly wrong on butt joints?
3. `_MITRED_POINTS` as module state (§7). Worth the four signature changes to remove?
4. The three remaining violations are 2 underlay + 1 column, unchanged since Part 7. The underlay
   double-back has now survived five parts as a known, unfixed producer.
