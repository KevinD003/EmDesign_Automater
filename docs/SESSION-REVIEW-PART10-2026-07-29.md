# STITCHIQ v2 — Part 10 Work Report for Independent Review

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part10-audit.md`](./benchmarks/v2-part10-audit.md)

> **Floor violations 3 → 2. Sub-0.5mm stitches 33 → 9.** Both machine-safety numbers improve at once
> and no coverage number moves. The narrower fix Part 9 flagged as unattempted works, and beat the
> target on both axes.

---

## 0. Housekeeping — and why it needed doing twice

The comment still read `apex_M 96.6 -> 97.9, apex_V 98.1 -> 98.7`. **Part 9's audit reported this
corrected; the edit never landed.** Part 9 applied it with a Python `str.replace` whose search string
said *"the opposite direction to the letter probe's…"* while the file says *"the opposite of the
letter probe's…"*. A `replace` that matches nothing returns the string unchanged and raises nothing,
so the no-op was silent and I wrote the audit from intent instead of from the file.

Fixed, and **verified by diffing**:

```
-    # (apex_M 96.6 -> 97.9, apex_V 98.1 -> 98.7). The shape is pinned here so the
+    # (apex_M 96.6 -> 97.3, apex_V 98.1 -> 97.8). The shape is pinned here so the
```

The comment now also records where the wrong figures came from and that the earlier correction
silently failed, so nobody has to rediscover it.

## 1. The narrower fix

Part 9 protected **every** mitred endpoint from `_coalesce_short` — paying a short stitch per mitre
whether or not that mitre would ever have caused a violation.

The new rule inverts the order: **coalesce first, then restore only the points whose absence actually
breaks the floor.** `_coalesce_short` records what it drops after each survivor; `_restore_for_floor`
scans for a same-side pair under the floor — using the *same* zigzag test the metric uses, so an
underlay can't trigger a spurious restore — and re-inserts one dropped point from the offending span.
Any point in that span restores the A-B-A-B alternation, so the repair is minimal by construction.
The floor is passed only for satin; tatami rows never zigzag and stay byte-identical.

## 2. Result

| | part 8 | part 9 (blanket) | **part 10 (targeted)** |
|---|---|---|---|
| floor violations | 5 | 3 | **2** |
| sub-0.5mm stitches | 6 | 33 | **9** |

The extra violation closed is fixture 08 `Satin 16` at 0.2519mm — **pre-existing and unfixed since
Part 7** — because the repair doesn't care how a violation arose, only that one exists.

**Both remaining violations are in the running-stitch underlay:**

```
07  Satin 1    UNDERLAY  0.1828mm   pre-existing (Part 5)
07  Satin 13   UNDERLAY  0.0000mm   pre-existing (Part 5)
```

For the first time since Part 6 there are **zero satin-column violations anywhere in the corpus**.

**Sub-0.5mm, from actual stitch coordinates** (cross-checked against the bench JSON, both give 9):
`01:0 02:0 03:0 04:2 05:0 06:0 07:4 08:2 09:1 10:0`. Three of those nine predate the mitre entirely
(04:2, 09:1 — and 09 has no satin at all), so **the mitre's true residual cost is 6 short stitches,
not 27.**

## 3. What moved

**No interior, edge-band or spill figure moved on any fixture, to one decimal.** The only movement is
stitch counts on 02 (−10), 06 (−8), 07 (−11), 08 (−7) — exactly the four fixtures Part 9's blanket
protection had inflated, each shedding the short stitches it had forced. **All three probes are
byte-identical to v2-part9.**

## 4. It let me delete the thing Part 9 asked about

`_MITRED_POINTS` — the module-level register Part 9 introduced and flagged in its own §7 as "state,
and state is how bugs hide" — became **write-only** once the repair moved downstream. Deleted, with
`_mitre_key` and the two tests that pinned it. Part 9 §8 asked whether it was worth four signature
changes to remove; the answer is that the right fix needed **none of them**.

## 5. Verification

```
pytest — WITH rembg:     116 passed, 1 warning in 29.56s
pytest — WITHOUT rembg:  116 passed, 1 warning in 11.78s
vitest:                  Test Files 9 passed (9) / Tests 57 passed (57)

floor violations   3 -> 2        sub-0.5mm stitches   33 -> 9
classification identical · 0 over 12.7mm · colours/segmentation/area identical

digitizer.py 94%   measure_stitch_quality.py 95%   run_quality_bench.py 65% (pre-existing)
```

Three tests replace the two removed. `_coalesce_short` 30 lines, `_restore_for_floor` 31 — both
inside the limit. `ruff` 14 findings, all pre-existing. Secrets clean. Two constants added
(`COALESCE_ZIGZAG`, `COALESCE_REPAIR_PASSES`), two constants and one register removed.

## 6. What to attack

1. `COALESCE_ZIGZAG = 0.9` duplicates a constant that also lives in the metric script. The pipeline
   now carries a copy of a metric's definition — shared constant, or lesser evil?
2. The repair restores the *first* dropped point in the span. Any works for the alternation; not all
   are equally good geometrically. Does the choice matter?
3. Both remaining violations are the underlay double-back — a running stitch, not satin. Does the
   floor even apply to it, or should the metric exclude it and report 0?
4. §0 — a silent `str.replace` no-op produced a false claim in an audit. Should edits to tracked
   files be diff-verified as routine rather than trusted?
