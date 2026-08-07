# v2 Part 66 — consolidation: one copy of everything, nothing weakened

**Date:** 2026-08-07 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** production-readiness consolidation — merge the duplicated code
that sixty-odd parts accumulated, keep the best implementation of each piece,
delete what is unnecessary. Not going live; the safety net must not shrink.

**Delivered: net −165 lines with zero behaviour change on locked streams.**
Every duplicated helper now has exactly one home; the diff is 97 insertions
against 262 deletions across app, scripts and tests, and the suite is
**greener and faster** (the four newest test files run in 66 s where they
took over 125 s, from a digitize cache).

---

## 1. What was duplicated, measured first

| duplication | copies before | after | canonical home |
|---|---:|---:|---|
| enum `.value if hasattr` dance | 8 (6 services, router, pipeline) | **1** | `app/models/design.py::enum_str` |
| `sys.path` shim in test files | 20 | **1** | `tests/conftest.py` (old shims left in place — idempotent and harmless; new files need none) |
| stitch-stream comparator `_stream` | 5 | **1** + 2 kept | `tests/helpers.py::stream_of` (part36's same-named function is a stream *builder*, a different thing; scripts keep `stream_metrics`, a metrics reducer) |
| doubled-angle row instrument | 4 | **2** | `tests/helpers.py::row_angle` for tests; `bench_competitor.block_features` for scripts — tests deliberately do not import the code they measure |
| label bar / panel stack / fit | 3 | **1** | `scripts/_viz.py` |
| largest-tatami / object crop / segment overlay | 2 each | **1** | `scripts/_viz.py` |
| seeded fixture digitize in tests | 12 files re-digitizing | cached | `tests/helpers.py::digitized_fixture` (lru-cached, returns deep copies so no test can poison another) |

## 2. The one engine-relevant fact found on the way

`use_enum_values=True` on `CamelModel` means **every enum field on a validated
model is already a plain string** — verified against construction and JSON
round-trip, not assumed. All eight `v.value if hasattr(v, "value")` dances
were dead defensive code; they now delegate to one `enum_str` (which still
accepts raw enum members, because pyembroidery constants and hand-built
objects do pass through some of these paths). Behaviour-identical by
construction and by the lock suite.

## 3. Proof the consolidation changed nothing it shouldn't

- **Locks, baselines and IO paths**: 184 targeted tests (stream locks, visual
  regression, embroidery IO, export, worksheet, package, trim profiles) green
  before the full suite.
- **Regenerated evidence, pixel-compared against the committed versions**:
  the Part 62/63 flow panels differ only in one overlay strip of ≤470 px —
  the OLD code drew the drawn-line overlay without the crop's edge clamp, so
  on clamped crops the control line sat a few pixels off; the shared helper
  places it correctly. The stitched renders beneath are pixel-identical.
  The benchmark visuals differ only in their 30-px caption bars (one label
  style everywhere now); every rendered pixel below the captions is
  identical.
- **Migrated tests unmodified in what they assert**: the four newest files
  plus part59 swap local helper copies for the shared ones; every assertion
  line is untouched.

## 4. What was deliberately NOT merged, with reasons

- **Historical per-part test files were not merged into one file.** They are
  the executable spec of sixty parts of measured decisions; merging them
  would lose their per-part documentation headers, serialize what pytest
  runs in parallel, and make future bisection harder. Production-ready means
  one copy of each *helper*, not one file of all *tests*.
- **The 25 measurement scripts stay separate.** Each is a documented
  "reproduce" path in an audit or the state snapshot; several are the
  instruments the R-list's numbers came from. Their shared visual code is
  now in `_viz.py`; their distinct measurement logic is distinct on purpose.
- **`bench_competitor`'s analysis functions were not promoted into `app/`**:
  no application code consumes them; scripts and tests already import the
  one copy.
- **`scripts/split_digitizer.py`** stays per Part 42's recorded provenance
  decision (re-affirmed in Part 65).

## 5. Gates

| Gate | Result |
|---|---|
| Duplication inventory measured before editing | ✅ table in §1, from grep counts |
| One canonical home per helper | ✅ enum_str / conftest / helpers.py / _viz.py |
| No behaviour change on locked streams | ✅ 4/4 locks, 10/10 baselines, 184 targeted tests pre-suite |
| Evidence regenerated and pixel-verified | ✅ renders identical; only caption style and one overlay-clamp fix differ |
| Net deletion, not motion | ✅ 97 insertions / 262 deletions (−165 lines) |
| Suite faster | ✅ four newest files 125 s → 66 s via the digitize cache |
| Backend suite (final tree) | ✅ **947 passed, 2 xfailed** in 1175.02 s (wall-clock inflated by a container restart mid-part; the count is the gate) |
| `ruff check app` | ✅ 12, the standing baseline; all touched scripts/tests clean |
| Frontend | ✅ untouched (nothing duplicated there — orphan scan Part 65) |

## 6. Files

- `apps/backend/app/models/design.py` — `enum_str` (the one enum normaliser)
- 6 services + 1 router + pipeline — delegate to it
- `apps/backend/tests/conftest.py` — owns sys.path for the suite
- `apps/backend/tests/helpers.py` — `stream_of`, `row_angle`, `angle_err`,
  `digitized_fixture` (cached)
- `apps/backend/scripts/_viz.py` — label/stack/crop/overlay/largest-tatami
- Slimmed: `visualize_flow_line.py`, `visualize_divided_flow.py`,
  `bench_competitor.py`, `extract_training_rows.py`, tests part62/63/64/65/59
