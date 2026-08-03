# v2 Part 42 — R001: `digitizer.py` split into a layered package

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** the reviewer's revised plan, Rank 1 — *"Split digitizer.py (4,731 lines →
modules, each <400). Every subsequent change is safer in modular code. Pure refactor —
byte-identical output required."*

**Result:** one 4,731-line module became ten modules behind an unchanged import path.
Byte-identical output is **proven, not asserted**: the four stream locks sha256 the whole
stitch stream and all four are unchanged. Full suite back to its exact baseline, lint
neutral. The `<400` target is met by seven of ten modules and is honestly missed by three
— see §5, which says why and what it would cost to finish.

---

## 1. What shipped

| Module | Lines | Defs | Holds |
|---|---:|---:|---|
| `constants.py` | 760 | 1 | 100 tunables + the one setter that rebinds a runtime value |
| `geometry.py` | 561 | 25 | polylines, resampling, smoothing, mitres, hoop parsing |
| `skeleton.py` | 439 | 12 | Zhang-Suen thinning and the branch graph over it |
| `columns.py` | 467 | 14 | axis stations, boundary reach, pacing, the penetration floor |
| `fills.py` | 443 | 8 | scanline / contour / spiral / radial, and fill angle |
| `satin.py` | 298 | 6 | satin generators on top of the column geometry, plus borders |
| `underlay.py` | 262 | 8 | underlay generators and the walks they are built from |
| `routing.py` | 331 | 5 | travel, ties, trims, colour merging, stream locking |
| `planning.py` | 513 | 9 | clustering, palette planning, sketch-verify, texture, linework |
| `pipeline.py` | 1,131 | 2 | `digitize_image`, `rebuild_design` |
| `__init__.py` | 419 | — | facade: re-exports all **189** public names |

The layering is strict and bottom-up: **a module may import only from those above it in
that table.** `constants` imports nothing; `pipeline` may import anything.

Callers are untouched. `from app.services.digitizer import digitize_image` still works
because `__init__.py` re-exports the whole surface — 90 definitions and 100 constants.

## 2. How it was done, and why that matters

`scripts/split_digitizer.py` (committed) did the move. It is mechanical on purpose:

- it relocates **whole top-level definitions verbatim**, never editing a statement inside
  one, with each definition's comment block travelling with it;
- it derives each module's imports from the AST rather than by hand;
- it **refuses to write** if any import would point upward, printing the offending edges.

That last check earned its keep. The first run found nine back-edges from names that lie
about where they belong — `_run_along` reads like geometry and is underlay; `_fill_angle`
reads like planning and is a fill primitive; `_enforce_floor` reads like satin and
operates on column pairs. Each is an explicit entry in the tool's `OVERRIDE` map, so the
placement argument is recorded rather than inferred.

Three defects in the tool were caught **before** it wrote anything, by checks added for
exactly that purpose:

1. **An off-by-one in the comment-capture slice** would have pulled one stray line above
   every definition.
2. **`AnnAssign` was ignored**, which would have silently dropped `FABRIC_PROFILES` and
   the three runtime logs — a `NameError` at first call, not at import. The tool now
   asserts that **every non-blank line below the header lands in some module** (4,487 of
   them) and exits non-zero otherwise.
3. **Trailing comment blocks** — the Chaikin sweep under `SMOOTH_MIN_POINTS`, the
   outward-bias sweep under `UNDERLAY_REPAIR_PASSES` — belong to the constant *above*
   them and were attached to nothing. Three measured design rationales, gone. Now
   captured, checked by the same coverage assertion.

## 3. The one thing that could not be moved verbatim

`_PENETRATION_FLOOR_MM` is the only module-level name that is **rebound** at runtime
(`set_penetration_floor` uses `global`). A plain `from constants import
_PENETRATION_FLOOR_MM` snapshots it at import time, so the setter would still appear to
work and would silently stop affecting the 24 read sites in `pipeline.py` and `satin.py`.

Those 24 reads are routed through the module object instead (`constants._PENETRATION_FLOOR_MM`).
That is the **only** edit made inside any moved body, it is reported by the tool when it
runs, and `test_penetration_floor_stays_live_through_the_facade` fails if it regresses.

`_CLASSIFICATION_LOG` and `_DROP_LOG` needed no such treatment — they are only ever
`.clear()`ed and `.append()`ed, so every module shares the one list object. A test pins
that too, because a single stray reassignment would split them into per-module copies and
the classification log would quietly go empty.

## 4. A second, smaller extraction

`digitize_image` contained `_plan`, a **224-line nested closure** doing the whole k-means
colour plan. Measured before touching it: it closes over exactly ten enclosing locals
(`img`, `fg_mask`, `fg_flat`, `flat_rgb`, `Z`, `ih`, `iw`, `up_f`, `is_textured`,
`mm_per_px`) and **assigns none of them**. A read-only closure is a function with implicit
arguments, so it moved to `planning.py` as `_plan_palette(k, *, …)` with those ten passed
explicitly, and `digitize_image` keeps a three-line adapter so every call site is
unchanged.

`digitize_image`: **1,032 → 822 lines**.

## 5. Where the `<400` target is missed, honestly

Three modules are over, for two different reasons.

**`constants.py` (760)** is a flat list of 100 tunables with their measured rationale in
comments. It has no control flow and one function. Splitting it would mean deciding which
half of a sweep result you have to go looking for; the line count is documentation, not
complexity. Left whole deliberately.

**`geometry.py` (561) and `planning.py` (513)** are mildly over and could be halved, but
neither is a maintainability risk at that size. Not worth the churn in the same change as
the big move.

**`pipeline.py` (1,131)** is the real miss, and it is one function's fault. After the
`_plan` extraction, `digitize_image` is still **822 lines**, dominated by a **412-line
loop** over colour clusters. That loop was measured for extractability before giving up on
it: it reads **18 mutable locals** from the enclosing scope and writes **7 names read after
it**, four of which are accumulators mutated across iterations (`stitches`, `objects`,
`color_stops`, `emitted_mask`, plus counters). Extracting it means introducing a carrier
object for that state — a **design change, not a move**, with a different risk profile and
its own verification. It is the right next step for this file and it is deliberately not
bundled into a refactor whose whole value is being provably inert.

## 6. Verification

| Gate | Before | After |
|---|---|---|
| Stitch stream locks (sha256, 4 fixtures) | 4 pass | **4 pass, hashes unchanged** |
| Backend suite | 772 passed, 2 xfailed | **788 passed, 2 xfailed** (+16 new) |
| `ruff check app` | 12 | **12** |
| Source lines carried into a module | — | **4,487 / 4,487**, tool-asserted |
| Import back-edges | n/a | **0**, tool-asserted and test-pinned |

The stream locks are the substance of the claim. They hash `command|x|y` for every stitch
of four fixtures at a pinned RNG seed; a single coordinate moving by 0.0001mm changes the
digest. Unchanged across the split, the `_plan_palette` extraction, and the lint pass.

**Three tests were updated, and both reasons are worth recording:**

- `test_part33_sketch_verify.py` monkeypatched `digitizer._verify_sketch` to spy on
  re-plans. A facade **cannot** forward monkeypatching: `digitize_image` resolves
  `_verify_sketch` in `pipeline`'s own globals, so rebinding the re-export spies on
  nothing — and the test failed loudly rather than passing vacuously, which is the right
  failure. It now patches `pipeline._verify_sketch`. Any future test patching a digitizer
  internal must patch the owning module.
- `test_verify_lint_claim.py` used the literal path `app/services/digitizer.py` as its
  sample file; that file no longer exists. Repointed at `digitizer/pipeline.py`.

## 7. New test — `tests/test_digitizer_package_layering.py` (16 tests)

The layering is only worth having if it cannot silently rot, and nothing in Python
enforces it. The new file parses every module and asserts:

- no module imports from its own layer or above (parametrised over all ten);
- the set of modules on disk exactly matches the declared layer list — a module outside
  the layering is a module with no rules;
- every definition in every module is reachable from the facade;
- `_PENETRATION_FLOOR_MM` stays live through the facade under `set_penetration_floor`;
- the two shared logs are the same object in every module;
- no module has grown back past 1,500 lines.

## 8. Files

- `apps/backend/app/services/digitizer/` — new package (10 modules + facade)
- `apps/backend/app/services/digitizer.py` — **removed**
- `apps/backend/scripts/split_digitizer.py` — the one-shot tool, kept as provenance
- `apps/backend/tests/test_digitizer_package_layering.py` — new
- `apps/backend/tests/test_part33_sketch_verify.py`, `tests/test_verify_lint_claim.py` — updated

## 9. Next, per the reviewer's plan

R002 (audit or delete the 16 phantom `StitchType` members) and R003 (commit the
visual-regression harness) are both unblocked and are now easier: the enum's four real
generators live in `satin.py`, `fills.py` and `underlay.py` rather than somewhere in a
4,700-line file. R004 (stitch direction, 49.9°) remains the largest quality gap.
