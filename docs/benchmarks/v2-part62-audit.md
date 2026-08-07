# v2 Part 62 — Stitch Flow: a persisted direction line that fills actually obey

**Date:** 2026-08-07 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** ship one vertical slice of a competitor-gap editing feature —
a per-object **direction line** for fill objects that persists with the design,
that rebuild consumes, and that the user can add, move and delete in the UI.
Hard constraints: no R004 numeric work, no trim-profile or satin changes, no
legacy regressions, and no UI-only fake — the line must change the stitches.

**Shipped.** A `TATAMI` object can carry a two-point `flow_line` (JSON:
`flowLine`) in design mm. At rebuild, the line's angle replaces the automatic
`stitch_angle` for that object only; no line means byte-identical behaviour to
before this part. The frontend draws, drags and removes the line, and the whole
loop — draw → Apply → rows follow the line — runs against the real backend and
is photographed below.

---

## 1. The design decision that keeps it honest

The override **never overwrites `stitch_angle`**. The stored angle stays what
the digitizer computed; the line is a separate field consulted at generation
time (`_flow_line_angle(o.flow_line, fallback=o.stitch_angle)`). That buys
three properties the tests pin:

- **Removing the line restores the exact original stream** — set + remove +
  rebuild is byte-identical to never having set it.
- **Legacy designs are untouched** — every design saved before this part
  simply has no field (`None` default on a pydantic `CamelModel`), and a
  pinned test loads a pre-Part-62-shaped dump and asserts the stream matches.
- **The angle has one definition on both sides**: fold to [0, 180),
  head/tail symmetric, degenerate line → fall back (backend) / show automatic
  (frontend, `flowAngleDeg` in `src/lib/flow.ts`, unit-tested to the same
  contract).

Scope note: rebuild consumes the line only on the `TATAMI` branch, and the UI
offers the control only on tatami objects with a contour — no dead controls on
satin/contour/spiral/radial objects. Extending to the curved fills is future
work, not a half-shipped checkbox.

## 2. Backend evidence: the rows really follow the line

`tests/test_part62_flow_line.py`, 7 tests, all passing (55.9 s standalone):

| contract | how it is proven |
|---|---|
| line → real stitch change, rows along it | set a line at +90° to the current row direction; stream differs AND the length-weighted doubled-angle mean of the object's row segments lands within 10° of the requested angle |
| no line → identical | rebuild(d) == rebuild(d), and set+remove == never-set, byte-compared |
| neighbours untouched | stitches outside the target object's bbox identical before/after |
| persistence | JSON round-trip under the camel name `flowLine`; pre-Part-62 dumps load with `flow_line=None` and rebuild identically |
| angle semantics | 0/90/45°, reversed line same angle, degenerate → fallback |

Rendered proof (Part 44's renderer, object crop, drawn line overlaid in teal):

- `part62-flow-01.png` — fixture 01's blue disc: automatic 45° → line at 90°
  (rows vertical) → line at 135° (rows diagonal the other way).
- `part62-flow-07.png` — fixture 07's badge fill: automatic 82° → 127° → 172°,
  same story on a ring-with-star shape.

Reproduce: `.venv/bin/python scripts/visualize_flow_line.py` from `apps/backend`.

## 3. Frontend slice

- **Store** (`designStore.ts`): new tool `'flow'`; `MANUAL_TOOLS` now names the
  three draw tools explicitly so flow mode is *not* treated as object drawing
  (Toolbar's finish/undo UI, min-point logic and canvas draw preview all gate
  on it).
- **Canvas** (`StitchCanvas.tsx`): flow mode captures exactly two clicks —
  no Finish step, a direction needs two points — commits
  `updateObject(seq, { flowLine })` and drops back to select. The committed
  line renders as a dashed teal overlay with draggable endpoints; dragging an
  endpoint replaces the line in one undoable step.
- **Properties panel** (`PropertiesPanel.tsx`): a Stitch Flow row on eligible
  objects showing `automatic (45°)` or `line at 90°`, with Draw/Redraw/Cancel/
  Remove; the Angle input disables while a line is set (tooltip says why); the
  existing Apply → `/api/designs/rebuild` path carries the line because the
  rebuild request spreads the patched object.
- Every edit (set, move, remove) goes through the store's history — undo/redo
  work — pinned by `src/store/flowTool.test.ts`; a stale flow mode cannot leak
  onto a freshly loaded design (existing `setDesign` reset, now tested).

**Live end-to-end evidence** (`docs/benchmarks/v2-part62-ui/`, real backend,
real Vite app, Playwright): panel at automatic 45° → two clicks draw a vertical
line → panel reads *line at 90°* → **Apply returns 200 and the disc's rows
turn vertical** (`2-canvas-before.png` vs `5-canvas-after-apply.png`, a
rebuild-vs-rebuild pair) → Remove returns the panel to *automatic (45°)*.

One measurement made the before/after pair honest: the first Apply on a
freshly digitized design changes the stitch count **with or without a line**
(4,820 → 2,298 with no line at all on the demo design) — rebuild regenerates
plain fills from contours and always has. The screenshot pair therefore
compares rebuild against rebuild, so the only variable is the line. That
digitize-vs-rebuild gap is pre-existing, out of scope here, and worth its own
brief.

## 4. Not done, deliberately

- No satin/contour/spiral/radial consumption, no multi-segment curved flow
  lines, no per-region fields — this is the two-point tatami slice.
- No R004 reopening: the line is user intent, not a measured direction field;
  nothing here touches the blocked reference work.
- No change to `stitch_angle` semantics, defaults, or any existing stream:
  locks and baselines were never in danger by construction (the field defaults
  to `None`) and the suite confirms it.
- One environment fix that is not a feature: `@types/node` is now an explicit
  frontend devDependency. It was only ever an optional peer of vite, so a
  fresh `npm install` produced a `tsc --noEmit` failure in `theme.test.ts`
  (`node:fs` untyped) before any Part 62 change — reproduced at HEAD. The
  `build`/`typecheck` scripts depend on it; now it is guaranteed.

## 5. Gates

| Gate | Result |
|---|---|
| Line changes stitches, rows follow it | ✅ asserted within 10°, plus rendered + live-UI proof |
| Objects without a line rebuild identically | ✅ byte-compared, including set-then-remove |
| Legacy designs load + rebuild unchanged | ✅ pre-Part-62-shaped dump pinned |
| Frontend add / move / delete, undoable | ✅ 12 new vitest cases; live screenshots |
| Persists save/load under `flowLine` | ✅ round-trip test + localStorage → UI → rebuild in the live run |
| Backend suite | ✅ **919 passed, 2 xfailed** in 749.85 s (912 + 7 new) |
| Frontend suite / typecheck | ✅ **155 passed** (143 + 12 new), `tsc --noEmit` clean |
| Stream locks / visual baselines | ✅ in-suite, 4/4 and 10/10 |
| `ruff check app` | ✅ 12, the standing baseline; new script/test files clean |

## 6. Files

- `apps/backend/app/models/design.py` — `flow_line` field
- `apps/backend/app/services/digitizer/geometry.py` — `_flow_line_angle`
- `apps/backend/app/services/digitizer/pipeline.py` — TATAMI branch consumes it
- `apps/backend/tests/test_part62_flow_line.py` — 7 tests
- `apps/backend/scripts/visualize_flow_line.py` — rendered evidence
- `apps/frontend/src/lib/flow.ts` (+ test), `src/types/design.ts`,
  `src/store/designStore.ts` (+ `flowTool.test.ts`), `src/components/canvas/
  StitchCanvas.tsx`, `src/components/toolbar/Toolbar.tsx`,
  `src/components/panels/PropertiesPanel.tsx`
- `docs/benchmarks/part62-flow-01.png`, `part62-flow-07.png`,
  `v2-part62-ui/` (7 screenshots)
