# Launch-readiness gap assessment — Part B determinations and ranked plan

**Date:** 2026-07-29 · produced with [`v2-part12-audit.md`](./benchmarks/v2-part12-audit.md)
**Method:** seven parallel read-only code investigations, every claim carrying a file:line that was
actually read. Verdicts are about the live request path, not about parameters that exist but gate
nothing.

## The headline corrections to the brief

The brief assumed several items "don't exist yet or have never been audited." Three of them
**exist and are tested**, which materially changes the launch picture:

1. **Pull compensation exists and is fabric-aware** — the brief's item 3 asked "confirm whether this
   pipeline implements pull compensation anywhere"; it does, end-to-end, with a per-fabric table.
2. **Multi-format machine export exists and is round-trip tested** — DST and PES are written via
   pyembroidery, streamed to the user, and re-parsed in tests; the customer package ZIP contains the
   machine file, worksheet PDF, thread card, and preview.
3. **A composite quality score exists in the product** — `/api/optimize/quality` returns a 0–100
   score with findings (long/tiny stitch, jumps, colors), surfaced behind a toolbar button.

The audits never mentioned these because Parts 0–11 deliberately audited one subsystem — stitch
*generation* — and these live in other services. That scoping was correct per-part and misleading
cumulatively; this document is the correction.

## Per-item determinations

| # | Item | Verdict | Anchor evidence |
|---|---|---|---|
| B1 | Fabric-aware profiles | **partial** | `PULL_BY_FABRIC` (digitizer.py:129): 12 fabrics, 0.15–0.5mm/side, wired frontend→API→digitize→rebuild, tested in `tests/test_pullcomp.py`. But density (`ROW_SPACING_MM=0.45`, `SATIN_SPACING_MM=0.4`), underlay step/type, and edge inset are fabric-independent globals; no fleece/terry nap-crushing underlay despite the product spec calling for it (AI-Embroidery-Software-Prompt.md:71,476) |
| B2 | 0.30mm vs industry 0.5mm | **reconciled, documented** | The 0.5mm industry rule is a *stitch-length* rule → `MIN_STITCH_MM = 0.5` (digitizer.py:669), exactly the cited value, enforced in both digitize and rebuild. `MIN_PENETRATION_MM = 0.30` bounds a *different* quantity (same-side spacing) industry guides don't measure. The pipeline is not more permissive than the guidance — it enforces the guidance plus one additional check. Now stated at the constant's definition |
| B3 | Pull compensation | **exists** | `_default_pull` → `_dilate_pull` widens tatami tops (digitizer.py:451-452) and satin columns via `extra_half_px` (:484); stored per-object, honored and user-editable in `rebuild_design` (:2112); tested |
| B4 | Machine-format export | **exists** (with two blemishes) | `app/services/embroidery_io.py` over pyembroidery; writers dst/pes/pec/jef/exp/vp3/xxx live at `/api/export`, `/api/convert`; DST+PES round-trip tested. Blemishes: `/api/formats` hardcodes **"vip" which pyembroidery cannot write** (export.py:21 — a 415 waiting to happen), HUS is import-only, and JEF/EXP/VP3/XXX have no round-trip tests |
| B5 | Composite quality report | **partial** | `/api/optimize/quality` → 0–100 score, grade, jump/trim/travel metrics + findings (routers/optimize.py:27); hoop-fit check exists only in `/api/export/validate` (export.py:81-116), advisory, never blocking. Not persisted, not in the package ZIP, not auto-run; bench-only metrics (density/mm², coverage, penetration, over-limit counts) have no product surface |
| B6 | Lettering/kerning | **partial** (rasterize-then-digitize) | `/api/lettering` renders text with a system TTF via PIL and feeds the PNG through `digitize_image` (lettering.py:96-129). No kerning, tracking, baseline, or font selection (the `font_path` param is never passed by the router). **`text_mode` inside `digitize_image` is dead** — signature plus a stale comment, gates nothing since Part 3 unified classification. Frontend has a working "Text" dialog plus a permanently disabled "Lettering" stub |
| B7 | Jump/pathing optimization | **partial**, wrong layer | Color grouping is real (darkest-first, one COLOR_CHANGE per cluster — fixture 07 has just 2). An opt-in nearest-neighbor object reorder exists (`optimizer.optimize_path`) but is structurally irrelevant: **964 of fixture 07's 979 jumps are WITHIN objects** — 831 from `_scanline_fill`'s >3mm row-connection rule (435 of those from per-segment tatami fallback inside two ring objects), 122 from hash-set-ordered satin branch starts, 61 from underlay branch breaks. No pass anywhere reduces them |
| B8 | Corpus breadth | **absent** (documented reason) | 23 fixture PNGs, all PIL-drawn by checked-in generators; the generator states no photograph could be sourced license-cleanly. Zero real-world artwork in the repo |
| B9 | Machine compatibility testing | **absent, impossible from here** | Format writers are exercised in software round-trips only; no file has ever been loaded on physical hardware. Same standing as fabric validation — see `docs/FABRIC_TEST_PROTOCOL.md` |

## Ranked gap-closure plan

**Tier 1 — physical-safety validation (affects real garments; nothing else is truly "launch-ready" until this).**

1. **Execute `docs/FABRIC_TEST_PROTOCOL.md`** (human + machine required; cannot be done from this
   environment). Validates/adjusts `MIN_PENETRATION_MM`, `MIN_STITCH_MM` margins,
   `DENSITY_FLAG_PER_CELL`, and every `PULL_BY_FABRIC` entry in one session of sew-outs. Everything
   below inherits its constants from this.
2. **Fabric-profile table** (B1): generalize `PULL_BY_FABRIC` into `FABRIC_PROFILES` carrying
   `{pull_mm, row_spacing_mm, satin_spacing_mm, underlay_step_mm, edge_inset_mm}`, resolved once in
   `digitize_image`, substituted at the five constant-use sites (digitizer.py:391, 450, 467, 536,
   543) and seeded into per-object fields so `rebuild_design` needs zero changes. ~30 lines plus
   tests; the density values themselves come from tier-1 sew-outs, not from citations.
   Fabric-specific underlay *type* (double-zigzag for fleece/cap/terry) is a new generator — second
   step, after the table.

**Tier 2 — feature parity (decision points; see below).**

3. **Quality report consolidation** (B5): fold the hoop-fit check into `analyze_quality`, add
   max/mean stitch and density-per-mm² (code exists in the bench), auto-run after digitize, write
   the report JSON into the package ZIP. Composes existing pieces; no new architecture.
4. **Export hardening** (B4): derive `/api/formats` from the writer registry (kills the false "vip"
   advertisement), document HUS as import-only, add one parametrized round-trip test over
   jef/exp/vp3/xxx/pec. ~15 lines.
5. **Lettering** (B6): decide scope first (below). Cheap increments if in scope: delete dead
   `text_mode`, pass `font_path` through, add tracking via per-character rendering with PIL
   `textlength` advances. True satin lettering with editable text objects is a phase, not an item.

**Tier 3 — production efficiency and QA breadth.**

6. **Jump reduction at the emitters** (B7), in measured order of yield on fixture 07: fill the
   wide-mask tatami fallback per connected component (~435 jumps), NN-order skeleton branches before
   `_emit_columns` (~122, also makes branch order deterministic instead of hash-set order), route
   ring-fill hole hops (~396). Each is a local change to one emitter; re-bench after each.
7. **Real-world corpus** (B8): 3–5 CC0/public-domain logos + photos under `tests/fixtures/real_world/`
   with a PROVENANCE.md, benched under a separate tag so the ten-fixture regression baseline keeps
   its meaning.
8. **Machine sew-outs of exported files** (B9): human + hardware; piggybacks on the tier-1 protocol
   session (piece 4 is exported DST).

## Decision points — explicitly not assumed

Per the brief, none of these are implemented until the user rules them in scope:

- **Lettering**: ship the current rasterize-digitize text tool as-is for launch (it works, it is
  honest about what it is), or invest in tracking/kerning first? The disabled "Lettering" stub
  button in the toolbar suggests the product intent, but that is a product call.
- **Additional export formats**: JEF/EXP/VP3/XXX are written but untested; HUS/VIP are impossible
  with pyembroidery. Test-and-advertise the four, or trim the advertised list to DST/PES for launch?
- **Fabric-specific underlay type** (double-zigzag for high-loft): new generator + enum + renderer
  implications — in or out for launch?
- **Auto-running path optimization** after digitize: nearly free to call, but pointless until the
  within-object emitters (tier 3 item 6) are fixed; sequence accordingly.

## What was NOT determined here

Whether any of the "exists" verdicts hold up on real hardware (B9), and whether the pipeline's
output quality on real-world artwork (B8) matches its synthetic-corpus numbers — the two items that
require a human, a machine, and fabric. The verification pass of 2026-07-29 (§6b) already flagged
that coverage percentages grade fill against the *segmented* contour, not against the source
artwork, so corpus breadth (B8) is also the test of the segmentation stage that Parts 0–11 never
audited.
