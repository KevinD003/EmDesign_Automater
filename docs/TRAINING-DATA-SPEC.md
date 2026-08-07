# Training-data specification — embroidery object & stitch decisions (v1)

**Purpose.** Define the dataset a model can be trained on to predict better
embroidery-object and stitch-property choices (stitch type, angle/flow,
density/underlay presets, divide placement, split/merge, sequencing hints).
This version defines the schema and ships the extractor; it does **not** train
a model — see "Why no baseline yet" at the bottom.

**Format.** JSON Lines (`rows.jsonl`), one row per object/region, plus a
sibling `crops/` directory of source-image crops. Extractor:
`apps/backend/scripts/extract_training_rows.py` (rerunnable; output goes to
`apps/backend/data/training/`, which is gitignored — the dataset is derived,
the scripts and this spec are the tracked artifacts).

## Row schema (schema_version = 1)

| field | type | meaning |
|---|---|---|
| `schema_version` | int | always 1 for this spec |
| `row_id` | str | `<design_id>/<object_or_block_id>`, unique in the file |
| `design_id` | str | benchmark case id or file stem |
| `provenance` | enum | see Provenance levels below — REQUIRED on every row |
| `source.artwork_path` | str \| null | source image the design came from; null for machine files without artwork |
| `source.crop_path` | str \| null | PNG crop of the object's bbox from the artwork (+2 mm pad) |
| `source.bbox_mm` | [x0,y0,x1,y1] | object/block bounds in design mm |
| `source.contour_mm` | [[x,y]…] \| null | outline resampled to ≤64 points; null when only a stitch stream exists |
| `source.hole_count` | int \| null | interior holes; null = not observable |
| `source.region_mm2` | float | polygon area when contour exists, else bbox area |
| `context.n_objects_in_design` | int | sibling count |
| `context.color_stop` | int \| null | the object's colour stop |
| `context.palette_size` | int | colour stops in the design |
| `context.design_size_mm` | [w,h] | whole-design extent |
| `decision.stitch_type` | str | the choice made for this region (see decision_provenance) |
| `decision.angle_deg` | float \| null | stored angle (STITCHIQ) or measured dominant angle (machine file) |
| `decision.density` | float \| null | lines/mm; null when not observable |
| `decision.underlay` | str \| null | underlay type; null when not observable |
| `decision.pull_comp_mm` | float \| null | pull compensation; null when not observable |
| `decision.has_flow_line` / `has_flow_divide` | bool | Part 62/63 metadata present |
| `decision_provenance` | enum | how the decision fields were obtained (same enum) |
| `stats.stitch_count` | int | stitches actually sewn for the region |
| `stats.median_seg_mm` | float \| null | median stitch segment length |
| `stats.measured_angle_deg` | float \| null | doubled-angle mean of long segments, measured from the stream |
| `label` | object \| null | human correction (provenance `human_labeled`); **null everywhere today** |

**What the label is, per provenance.** For `stitchiq_generated` rows the
"label" is STITCHIQ's own decision — usable for imitation/pretraining only,
never as ground truth of what is *better*. For `machine_file_inference` rows
the decision is inferred from segment statistics and is explicitly lossy.
Only `native_competitor_object` and `human_labeled` rows can serve as
supervision for "better than STITCHIQ" — and none exist yet (see below).

## Provenance levels

| level | tag | meaning | trust |
|---|---|---|---|
| 1 | `native_competitor_object` | read from a competitor's native design file (e.g. Wilcom EMB) with real object outlines and properties | highest — none held today |
| 2 | `machine_file_inference` | inferred from a machine stitch file: blocks split at TRIM/COLOR_CHANGE, type from segment statistics | lossy — type/angle only, no contours, no density/underlay |
| 3 | `human_labeled` | a human corrected or annotated the decision | high — none held today |
| 4 | `stitchiq_generated` | STITCHIQ's own pipeline decision | abundant but circular: it can only teach imitation of the current system |

## Honest state of supervision (the Question-3 answer)

The data available today — STITCHIQ designs (level 4), two trivial foreign
machine files and any future machine files (level 2), and competitor renders
(no rows at all) — is **not sufficient for supervised training toward
"competitor-grade decisions"**. Level-4 rows teach the current system's
habits; level-2 rows lose exactly the properties we want to learn (object
outlines, density, underlay, and Wilcom-style native files are the ones that
retain object/stitch-angle semantics). Before training: acquire native
competitor design files (level 1) for matched artwork, or run a human
labelling pass (level 3) over STITCHIQ outputs marking wrong type/angle/split
decisions. The schema above is deliberately identical for all four levels so
those rows drop into the same file when they arrive.

## Why no baseline model yet

A stitch-type classifier trained on level-4 rows would be evaluated against
the same system that generated its labels — accuracy against STITCHIQ's own
choices, which the angelfish benchmark case shows can be systematically wrong
(30/30 SATIN on a fish body). A meaningful baseline starts with the first
level-1 or level-3 rows.
