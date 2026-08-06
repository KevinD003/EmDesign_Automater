# v2 Part 59 — two measured facts become product behaviour

**Date:** 2026-08-06 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** make the `max_colors` cap explicit to the user; expose the
Part 48 trim tradeoff as an opt-in, machine-aware export setting; change no
default.

**Both shipped.** The colour-cap warning appends to `Design.warnings` through
the existing machinery and changes no stitch — pinned by a test that compares
the streams. The trim profile is an export-time filter: `conservative` (the
default) is provably a no-op — it returns the same object — and `aggressive`
removes **10.8–17.0%** of trims on the tier-A designs while leaving every
stitch, jump and colour change untouched, which the measurement script asserts
loudly rather than assumes.

**And one number needed explaining before it shipped: the panel gives 559 trims
at aggressive, not Part 48's 485.** Both are correct. They measure different
quantities, the difference is exactly 74 trims, and the filter's quantity is the
physically right one. §3.

---

## 1. The `max_colors` warning

`pipeline.py` planned `min(max_colors, 8)` behind a bare literal since the
planner landed; Part 57 measured requests above 8 as inert and Part 58 decided:
keep the cap, say so. Now:

- the literal is a named constant, `PLAN_MAX_COLORS = 8` (`constants.py`, with
  the Part 57 measurement in its comment; re-exported by the facade);
- a request past the cap appends, via the **existing** `user_warnings` list —
  no parallel path:

> Colour limit: 12 colours were requested, but colour planning uses at most 8 —
> this design was planned with 8. Values above 8 do not change the result.

The message reports `k_plan`, not the bare cap, because the outline-check retry
can legitimately plan more than 8; the text stays true in that case too.

Tests: the warning appears exactly once at `max_colors=12` and not at 8 or 2 —
and the k=12 and k=8 **stitch streams are identical**, so Part 57's byte-identity
finding is now a pinned regression test, not a one-off measurement.

## 2. The trim profile

`app/services/trim_profiles.py`, applied in `/api/export` and
`/api/export/package` via `?trim_profile=`:

| profile | behaviour |
|---|---|
| `conservative` (default) | the stream exactly as generated at `TRIM_MIN_GAP_MM = 6.0`. Returns the **same object** — the no-op is structural, not asserted. |
| `aggressive` (opt-in) | for machines with an auto-trimmer: every TRIM whose **carried thread** is under 10 mm is dropped. 10 mm is Part 48's measured point, not a tunable. |

Named profiles rather than a numeric knob, deliberately: a number invites
tuning, and the two situations that exist — "I don't know the machine" and "I
know it auto-trims" — are what the names say. An unknown name is a 422 naming
the valid options. `TRIM_MIN_GAP_MM` itself is untouched.

Why export-time rather than a generation parameter: the trim decision never
influences geometry — the engine emits the same stitches and the same jump
either way, only the TRIM command is conditional — so the threshold is a fact
about the *target machine*, not the design. Filtering at export means one
digitize serves any machine, and the default path cannot drift.

## 3. 559 vs 485 — two rules, 74 trims apart, reconciled exactly

Part 48 measured 485 panel trims at a 10 mm threshold. The aggressive profile
leaves **559**. Chased before shipping, and it decomposes exactly:

- The engine's gate tests the **entry gap** — the straight line from the last
  stitch to the next object's first point. 178 panel trims have an entry gap in
  [6, 10) mm; re-generating at 10 mm drops all of them: 663 − 178 = **485**,
  Part 48's figure reproduced.
- The profile walks the **needle path** from the trim to the next actual
  penetration, through any travel jumps the next object opens with — because
  that is where the un-trimmed thread would physically lie. **74 of those 178
  trims carry ≥ 10 mm of real thread** despite their short entry gap.
  663 − 178 + 74 = **559**.

The path is never shorter than the entry gap, so the filter only ever **keeps**
trims the entry-gap rule would drop — never the reverse. It is conservative
relative to the engine's own rule, and the 74 are trims a 10 mm-comfort machine
genuinely wants. A test pins the direction (`carried ≥ entry gap` on every trim
of a real design). My first docstring claimed the two rules were equivalent;
that was wrong, and both the docstring and the test were corrected to the
measured truth.

## 4. The product effect, measured

Same seed, same hoops; the script *asserts* stream identity outside trims:

| design | profile | trims | jumps | stitches | travel | ~trim min |
|---|---|---:|---:|---:|---:|---:|
| A01 peacock | conservative | 364 | 745 | 37,285 | 12.23 m | 15.2 |
| | **aggressive** | **302** (−17.0%) | 745 | 37,285 | 12.23 m | **12.6** |
| A02 neckline black | conservative | 796 | 1,891 | 56,095 | 20.50 m | 33.2 |
| | **aggressive** | **710** (−10.8%) | 1,891 | 56,095 | 20.50 m | **29.6** |
| A03 panel | conservative | 663 | 1,754 | 54,070 | 18.26 m | 27.6 |
| | **aggressive** | **559** (−15.7%) | 1,754 | 54,070 | 18.26 m | **23.3** |

Jump travel does not change — removing a TRIM removes the cut, not the move —
so the saving is trim cycles: roughly **10.5 minutes of machine time across the
three designs**, at the cost of carrying threads of 6–10 mm, which is exactly
what the opt-in label says the machine can handle.

No product-quality claim is made from these numbers (the Part 58 constraint):
the designs sew identically. This is machine time only.

## 5. Scope safety

- The engine change is **one appended warning string**. The 4 stream locks and
  10 visual baselines pass untouched; the k=12/k=8 stream-identity test double-
  locks it.
- The corpus runner digitizes at `max_colors=12`, so corpus designs now carry
  the warning — as data. Warning-content tests were checked one by one: all are
  substring `any()`/`not any()` checks and none collides with the new text.
- The default export path returns the identical object; the aggressive path is
  reachable only by explicit query parameter.
- No R004 work, no fragmentation work, no cross-colour ordering, no default
  changed.

## 6. Gates

| Gate | Result |
|---|---|
| Warning via existing machinery, no stitch change | ✅ pinned by stream-identity test |
| Exact warning text in the audit | ✅ §1, verbatim |
| Default trim behaviour unchanged | ✅ `conservative` returns the same object |
| Aggressive is opt-in and labelled | ✅ query param + description; 422 on unknown names |
| Effect measured on panel + tier-A | ✅ §4; stream-diff asserted trim-only |
| Tests for both paths | ✅ 9 tests: warning ×2, synthetic ×5, real-design equivalence, endpoint |
| Backend suite | ✅ **909 passed, 2 xfailed** in 678.55 s (900 + 9 new) |
| Stream locks / visual baselines | ✅ 4 and 10/10 |
| `ruff check app` | ✅ 12, the standing baseline |

## 7. Files

- `apps/backend/app/services/digitizer/constants.py` — `PLAN_MAX_COLORS`
- `apps/backend/app/services/digitizer/pipeline.py` — the cap warning
- `apps/backend/app/services/trim_profiles.py` — profiles + `carried_thread_mm`
- `apps/backend/app/routers/export.py` — `trim_profile` on both export endpoints
- `apps/backend/tests/test_part59_trim_profiles.py` — 9 tests
- `apps/backend/scripts/measure_trim_profiles.py` — the §4 table, with the
  trim-only stream diff asserted

## 8. Honest residuals

- The UI does not yet surface `trim_profile`; it is API-level. Wiring a control
  into the export dialog is frontend work worth its own small change.
- `aggressive`'s 10 mm applies to *imported* streams too, where the carried-path
  walk is exactly what makes it safe on DST jump chains — but no imported-file
  measurement was run in this part; the export tests cover the mechanism, not a
  corpus of foreign files.
- Part 48's corpus-wide trim figures were not re-run here; the three tier-A
  designs are the measured population, per the brief.
