# Verified triage of the external 50-problem critique

**Date:** 2026-08-03 · Every row checked against the repo at commit `85fe223`, not against
memory. The source critique appears to predate v2 Parts 24–41 — **28 of its 50 items are
already built and tested**, several of its facts are wrong in our favour, and a few are
wrong against us (one is 7× worse than it says).

Work the **OPEN** and **PARTIAL** rows. Ignore the DONE rows or you will spend the
session re-solving finished work.

---

## Where the critique is factually wrong

| Claim | Reality |
|---|---|
| "Export format coverage unclear/limited vs competitors' 22+" (P007) | **47 read formats, 19 write formats** (`dst pes jef exp vp3 pec pmv u01 xxx tbf col edr inf csv json png svg gcode txt`). This is competitive, not a gap |
| "Naive background removal, corner-pixel compare, no ML" (P001) | U2-Net/rembg matte with a measured ink-recall plausibility gate and a classical fallback ladder (Parts 22, 27, 32, 34) |
| "Raw findContours with zero smoothing" (P002) | Douglas-Peucker + Chaikin, and the strength was **swept and proven already optimal** (Part 37) |
| "Entire pipeline classical OpenCV, no ML anywhere" (P005) | The segmentation stage is a neural matte. Fair as written about the *stitch* stage |
| "digitizer.py (686+ lines) needs modularization" (P026) | It was **4,731 lines** — the item is right and **7× understated**. **Closed in Part 42**: ten modules, strict layering, streams byte-identical |
| "Monolithic … in-browser rendering never visually verified" (P004) | Verified repeatedly this session via Playwright, but those scripts live in a scratchpad, **not committed**. Genuine gap, wrong reason |

## The one finding worth acting on immediately

`StitchType` declares **23 members**; the auto-digitizer emits **four**:
`SATIN`, `TATAMI`, `RUNNING_SINGLE`, `CONTOUR_FILL`. Three more
(`SPIRAL_FILL`, `RADIAL_FILL`, `APPLIQUE`) work only on **rebuild**, i.e. when a user
manually assigns them. The remaining sixteen — `CROSS_STITCH`, `PHOTO_STITCH`,
`GRADIENT_BLEND`, `CHENILLE`, `MOTIF_FILL`, `E_STITCH`, `BACKSTITCH`, `STEMSTITCH`,
`REDWORK`, `LAYDOWN`, `ZIGZAG`, `ACCORDION_FILL`, `RUNNING_DOUBLE`, `RUNNING_TRIPLE`,
`MOTIF_RUN`, `MANUAL` — are **enum members with no generator behind them**.

That is worse than a missing feature: the type system advertises capability the engine
does not have, and it is invisible until someone selects one. Either implement or remove.

---

## The 50, verified

### Already DONE (28) — do not re-solve

| ID | Item | Evidence |
|---|---|---|
| P001 | ML background removal | `services/segmentation.py`, Parts 22/27/32/34 |
| P002 | Contour smoothing | `_smooth_contour`; strength swept, at optimum |
| P006 | Curve over-packing | `MIN_PENETRATION_MM` + `_enforce_floor`; **0 violations** measured corpus-wide |
| P007 | Export formats | 47 read / 19 write |
| P008 | Pre-export QA | `/api/export/validate`, quality score + findings |
| P009 | Lettering | `services/lettering.py`, arc baselines, UI dialog |
| P012 | Auth / cloud | Supabase + local accounts, roles, plans, email reset (Part 35) |
| P014 | 3D preview | `TrueView3D` |
| P015 | Hoop enforcement | `_parse_hoop`, hoop-fit blocks export |
| P016 | Underlay types | centre-walk / edge-walk / zigzag / parallel, per-object selectable |
| P017 | Dashboard UI | rebuilt Part 35, light+dark, validated palette |
| P019 | Design library | `/api/designs` CRUD + local saves |
| P021 | SVG import | Part 25, exact double-render masks |
| P022 | Manual stitch editing | Part 36 stitch (DST) editor |
| P023 | Thread brand matching | catalogue + Lab nearest + custom charts (Part 36) |
| P024 | Production pack | `/api/export/package` ZIP |
| P027 | Error handling | typed HTTP errors, sanitised 500/422 |
| P028 | Visual benchmark | angle-fair coverage, penetration, density (better than SSIM here) |
| P029 | Documentation | 40+ measured audits in `docs/` |
| P030 | Public API | FastAPI, OpenAPI |
| P033 | Transform elements | `transform_range` (translate/scale/rotate) |
| P034 | Mirror / duplicate | `mirrorX` / `mirrorY` |
| P035 | Undo / redo | `designStore` history, 50 deep |
| P036 | Layers panel | `ColorObjectList` |
| P037 | Keyboard shortcuts | Ctrl/Cmd+Z, Shift+Z, Y, Esc |
| P042 | Analytics | `lib/analytics.ts` + dashboard |
| P045 | Stitch playback | `StitchPlayer` |
| P046 | Image preprocessing | Part 36 image editor (crop/levels/posterize/denoise/bg) |

### PARTIAL (10) — real work remains

| ID | Item | What is missing |
|---|---|---|
| P003 | Satin edge crispness | Generator is sound (pitch 0.450–0.454 on synthetics); degrades only on fragmented photographic regions |
| P005 | ML in the stitch stage | Segmentation is neural; stitch generation is entirely classical |
| P010 | Colour fidelity | Gradient-band recovery exists; deep-navy-class merges still unrecoverable |
| P011 | Sequencing | Nearest-neighbour only; **837 trims** on one panel is far above professional |
| P013 | Gradient fills | Band recovery yes; true blended gradient fill no |
| P031→P039 | Monetization | Plans + gating shipped; **no payment processor** |
| P038 | Mobile | Dashboard responsive; Studio is desktop-only |
| P041→P044 | Machine profiles | Format capabilities yes; per-machine hoop/limit database no |
| P049 | Accessibility | aria-labels and roles present; no audit, no keyboard-only pass |
| P026 | Modularity | ~~**4,731-line `digitizer.py`**~~ **DONE, Part 42** — split into a ten-module package. Residual: `digitize_image` is still 822 lines |

### OPEN (12) — genuinely not built

| ID | Item | Note |
|---|---|---|
| P004 | Committed visual-regression harness | Screenshots are ad-hoc in scratchpad; make it a repo script + baseline images |
| P018 | Batch digitizing | Nothing |
| P020 | Text-prompt-to-design | Nothing |
| P025 | Parallel digitizing | Only the corpus runner is parallel; a single digitize is sequential |
| P031 | AI copilot | Nothing |
| P032 | Canvas snapping / alignment | The only "snap" is thread-colour snapping — different feature |
| P039 | Payments | Plans exist, billing does not |
| P040 | Collaboration | Nothing |
| P041 | Version history | Nothing |
| P043 | Marketplace | Nothing |
| P048 | Cross-stitch mode | Enum member only |
| P050 | i18n | Nothing (the grep hit was a false positive) |

---

## What is missing from the critique entirely

The critique cannot see the defects our own measurements found, and these outrank most
of its P2/P3 list:

1. **Stitch direction carries no information** — mean **49.9°** error against a real
   sew-out where 45° is a coin flip, spread evenly across satin/tatami/running. This is
   the largest quality gap in the product. Plan: `docs/PROMPT-graph-stitch-engine.md`.
2. **Fragmentation** — 768 objects at a **median of 16 stitches** on one panel; a bar
   that should be one satin column is stitched as a run of stubs.
3. **Missing bead-chain ornament** — a signature dot-row in the test design is dropped
   entirely by the speck filters (Part 40 review).
4. **Sixteen declared-but-unimplemented stitch types** (above).
5. **Nine corpus designs still digitize to zero stitches**, all thin-stroke classes.

## Suggested order

1. ~~`P026` split `digitizer.py`~~ — **done, Part 42** (`docs/benchmarks/v2-part42-audit.md`).
2. The unimplemented-stitch-type audit — implement or delete; stop advertising phantoms.
3. `P004` commit the visual-regression harness — the last four parts each caught a defect
   only by looking at a render; that should not be manual.
4. The direction/fragmentation work (items 1–2 above).
5. `P011` sequencing — 837 trims is a real production cost.
6. Then the OPEN feature list by business need.
