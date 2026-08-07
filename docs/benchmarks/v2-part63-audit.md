# v2 Part 63 — divided Stitch Flow: two regions, two directions, one divide line

**Date:** 2026-08-07 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** extend Part 62's single direction line to a divided flow model
that is materially better on curved fills — the smallest truthful version, not
a flow-field editor. Hard constraints: tatami only, no satin consumption, no
direction-field reopening, no legacy regressions, and the richer flow must
change real stitches.

**Shipped: the brief's preferred minimal implementation.** A `TATAMI` object
can carry one optional **divide line** (`flow_divide`) that splits it into two
half-plane flow regions, plus a second direction line (`flow_line_b`). At
rebuild each side sews at the angle of the direction line whose **midpoint
lies on that side**; a side no line claims sews at the automatic angle. No
divide → exactly Part 62, byte-identical, with `flow_line_b` ignored — all
pinned by tests.

---

## 1. The model, and why the rules are the ones tests can state

Two new persisted fields on `DesignObject` (JSON `flowDivide`, `flowLineB`,
both default `None` so every earlier design loads and rebuilds untouched).
The consumption rules, each chosen because it is *decidable and testable*:

- **Half-planes, not polygon surgery.** The divide's endpoints define an
  infinite line; the region mask is split by cross-product sign
  (`_split_mask_by_line`). Pixels exactly on the line go to the positive side,
  so the two masks **partition** the region — no gap, no overlap (asserted).
  Each side is scanline-filled at its own angle; each generator's first point
  is already a jump, so concatenation is safe, and the existing `_route_travel`
  routes the crossing through the object.
- **Sides are claimed by midpoint.** `flow_line` then `flow_line_b` each claim
  the side its midpoint is on; first claim wins; a midpoint exactly on the
  divide claims nothing (silence beats a coin flip); an unclaimed side falls
  back to `stitch_angle`. Same code shape on the frontend (`flowSideAngles`,
  `flowLineSlot` in `lib/flow.ts`), unit-tested against the same fixtures so
  the two sides cannot drift silently.
- **A divide that misses the object degrades gracefully**: the whole object is
  one side and the result equals the Part 62 single-line build (asserted
  byte-identical).
- **Removing the divide removes the second line with it** (a side line is
  meaningless without its divide) and restores the exact Part 62 stream —
  possible because, as in Part 62, no override ever writes `stitch_angle`.

## 2. Backend evidence

`tests/test_part63_divided_flow.py`, **14 tests** (48.5 s): six on the helpers
(side assignment, first-claim, on-divide ambiguity, degenerate divides, mask
partition), five on rebuild (per-side row angles land within 10° of each
side's line on a synthetic rectangle; unclaimed side at automatic; missed
divide ≡ single line; `flow_line_b` alone is a no-op; set-then-remove ≡
Part 62), three on persistence (camel-name round trip; Part-62-shaped saves
rebuild unchanged; a real digitized design without the new fields rebuilds
byte-identically).

Two measurements worth recording beyond the gates:

- **Coverage is preserved.** On the crescent demo, sewn coverage of the object
  mask is **1.000 for both** the plain and the divided build (measured at
  0.19 mm tolerance). The divide seam does not open a gap — the two masks
  partition exactly and each side's fill reaches the shared edge.
- **Stitch counts move with row geometry, not coverage.** The same crescent
  sews 1,901 plain and 1,078 divided at identical spacing: at 0° its rows run
  *along* the wide body (long chords, interior penetrations every max-step),
  at 40°/140° they run *across* the band (short chords, endpoint-dense). Same
  territory, different chord structure — expected scanline behaviour, verified
  by the coverage number above.

## 3. Visual evidence — automatic vs one line vs divided

`scripts/visualize_divided_flow.py` digitizes three synthetic curved shapes
where one straight direction is visibly inadequate, and renders each three
ways with the controls overlaid (teal = direction lines, orange = divide):

- **`part63-divided-crescent.png`** — automatic 0° runs along the body; one
  line at 40° fixes the left horn and turns the right horn streaky; divided
  40°/140° puts rows across the band on **both** horns.
- **`part63-divided-bent-leaf.png`** — the chevron band: one line at 37° is
  perpendicular on the left limb and *parallel* on the right; divided 37°/143°
  crosses both limbs. The clearest of the three.
- **`part63-divided-bowl.png`** — a half-annulus with a **horizontal** divide:
  arms at 0°, base at 90° — a case a vertical divide could not serve, showing
  the divide is a real degree of freedom, not a hardcoded axis.

Honest limit, stated: two regions cannot serve a full ring (its ideal
direction turns continuously); that is the multi-segment future, not this
part. The three shapes above are exactly the shapes two regions do serve.

## 4. Frontend slice

- **`divide` tool**: same two-click capture as `flow` — no Finish step; Esc
  cancels; not a `MANUAL_TOOLS` member, so it never creates an object.
- **Canvas**: the divide renders as a dashed **orange** overlay, both
  direction lines in teal, all endpoints draggable (each drag one undoable
  step). Drawing a direction line on a divided object routes it to the slot
  for the side it was drawn on (`flowLineSlot`).
- **Panel**: shows `divided: 41° / 139°` (or `auto` per unclaimed side),
  with Draw side line / Redraw divide / Remove lines / Remove divide; the
  Angle input disables while any line is set. Removing the divide falls back
  to the Part 62 single-line display with the first line kept.
- **Live end-to-end proof** (`docs/benchmarks/v2-part63-ui/`, real backend +
  real app via Playwright): divide the crescent with two clicks → one line per
  side → panel reads *divided: 41° / 139°* → **Apply returns 200** and each
  side's rows follow its line (before/after is rebuild-vs-rebuild, Part 62's
  honesty rule) → Remove divide returns the panel to the single-line model.

## 5. Not done, deliberately

- No satin, contour, spiral or radial consumption; no multi-segment (>2)
  regions; no curved divide lines; no per-region density. Each is future work
  with its own measurement, not a checkbox.
- No R004 work: the divide is user intent, not a solved field.
- Nothing writes `stitch_angle`; no defaults moved; locks and baselines
  untouched by construction (both new fields default `None`).

## 6. Gates

| Gate | Result |
|---|---|
| Richer metadata persists save/load | ✅ camel round trip + localStorage → UI → rebuild live |
| No metadata → identical to Part 62 | ✅ byte-compared 4 ways (no fields, `flowLineB` alone, set+remove, Part-62-shaped dump); real digitized design included |
| Real stitch difference, rows follow per side | ✅ asserted within 10° per side; coverage preserved at 1.000 |
| Clear improvement on ≥2 curved cases | ✅ crescent, bent leaf, bowl — three-way panels, controls overlaid |
| Frontend set / modify / remove usable | ✅ two-click divide + per-side lines + draggable endpoints + remove; 10 new vitest cases; live screenshots |
| Backend suite | ✅ **933 passed, 2 xfailed** in 819.97 s (919 + 14 new) |
| Frontend suite / typecheck | ✅ **165 passed** (155 + 10 new), `tsc --noEmit` clean |
| Stream locks / visual baselines / ruff | ✅ in-suite 4/4 and 10/10; ruff 12 baseline, new files clean |

## 7. Files

- `apps/backend/app/models/design.py` — `flow_divide`, `flow_line_b`
- `apps/backend/app/services/digitizer/geometry.py` — `_flow_divide_valid`,
  `_flow_side`, `_flow_side_angles`, `_split_mask_by_line`
- `apps/backend/app/services/digitizer/pipeline.py` — divided TATAMI branch
- `apps/backend/tests/test_part63_divided_flow.py` — 14 tests
- `apps/backend/scripts/visualize_divided_flow.py` — three-way evidence
- `apps/frontend/src/lib/flow.ts` (+8 test cases), `src/types/design.ts`,
  `src/store/designStore.ts` (+2 store tests), `src/components/canvas/
  StitchCanvas.tsx`, `src/components/panels/PropertiesPanel.tsx`
- `docs/benchmarks/part63-divided-{crescent,bent-leaf,bowl}.png`,
  `v2-part63-ui/` (8 screenshots)
