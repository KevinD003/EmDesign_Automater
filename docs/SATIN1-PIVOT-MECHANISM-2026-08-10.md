# `Satin 1`'s column-end pivot — mechanism

**Mechanism only. No fix proposed here, and none written.** The site has been listed in three
progress reports without being investigated; this is the investigation. Fixture `08_mascot_detail`,
**cotton @ 130×180**, shipped code at `67d1679`, seeded with `run_quality_bench.RNG_SEED`.

## What it is

`Satin 1 (#de6c26)` — 3,905 stitches — puts **25 penetrations into one 0.5 mm disc** centred on
(35.93, 65.03) in design mm. That is the larger part of the corpus's densest neighbourhood
(`max_per_disc` 26), and it is present identically before and after the parity fix, so nothing in
this engagement caused it.

Measured on the emitted stream, in design millimetres:

| quantity | value |
| --- | --- |
| penetrations inside the 0.5 mm disc | **25** |
| column ends landing in the disc | **42** |
| distinct far ends of those columns | **31** |
| angular span of the columns | **175.6°** |
| column length | 0.707 – 6.946 mm |

Forty-two satin columns converge on one 0.5 mm spot from a **175.6° fan** — very nearly a half turn —
with their far ends spread across 31 distinct positions. This is not a stroke that happens to be
dense. It is a **pivot**: the columns rotate about this point while their outer ends sweep an arc.

## Why the existing mitre does not prevent it

The codebase already names this failure. `_mitre_stalled_side`:

> At a sharp vertex the two boundaries are in direct conflict: the OUTER arc sweeps right around the
> corner and needs a column every pitch to cover it, while every one of those columns wants its INNER
> end on the reflex point, so the inner penetrations pile into a spot far tighter than the floor
> allows. […] A hand digitizer resolves this with a mitre: the inner ends are laid along the corner's
> BISECTOR instead of into its point.

So a mitre exists, and the description matches this site exactly. Instrumented on the shipped
`_mitre_one_side` — counting which of its five guards declines, across the whole fixture:

| outcome | stations |
| --- | --- |
| `run_too_short` (`run < MITRE_MIN_STALLED`) | **4,731** |
| `axis_not_advancing` | 548 |
| `step_from_partner_short` | 6 |
| `step_to_partner_short` | 5 |
| **mitred** | **258** |

with `floor_px` 3.077 and `min_len_px` 5.0 over 5,698 stations, 1,329 of them stalled.

**The mitre fires on 258 of 1,329 stalled stations — 19%.** The dominant refusal by an order of
magnitude is `run_too_short`: the mitre only acts inside a run of `MITRE_MIN_STALLED` *consecutive*
stalled stations, and 4,731 stations that are stalled or adjacent to stalling never reach that
threshold.

## What is NOT established, and why

**Whether this pivot is one branch or several.** The natural hypothesis — that the mitre is a
per-branch pass (`_mitre_one_side` only ever sees one branch's endpoint array) and therefore
structurally blind to columns arriving from *different* branches at the same point — **is untested.**

The test was attempted and abandoned as unsound. Column endpoints are produced by
`_skeleton_satin_hires` in an **upscaled** pixel space, not the work grid, so locating the site among
them requires a scale conversion. A validation check comparing converted endpoint extents against the
design's own stitch extents refuted the conversion outright: endpoints mapped to x 27.49–279.14 mm on
a design that spans 26.95–93.05 mm. The factor is also not uniform (279/93 = 3.00, but
223/91.5 = 2.44), because the hi-res upscale is chosen per call from the stroke width. A branch count
computed through that conversion would have been fiction, so it is discarded rather than reported.

Everything in the tables above is measured in **design millimetres on the emitted stream** and does
not depend on that conversion.

## Fixture limits

- One site, one object, one fixture, **cotton @ 130×180**. `08_mascot_detail` is a synthetic flat
  mascot design, not a photograph and not customer artwork. Whether real logos produce pivots of this
  severity is unknown — no real artwork has been measured.
- The mitre statistics are **design-wide**, across all of fixture 08's satin objects. They establish
  that `run_too_short` dominates overall; they do **not** establish which guard declined at this
  particular site, because that needs the branch attribution above.
- `max_per_disc` at this site is 26 against a flag of 14 on the grid measure — but the flag was
  calibrated on `max_per_cell`, and the two are not interchangeable (see
  `DENSITY-LOCK-SITE-2026-08-10.md`).

## What would settle it

1. Capture the hi-res scale factor **per `_column_ends` call** — it is chosen inside
   `_skeleton_satin_hires` from `stroke_mm / mm_per_px` — and redo the branch attribution properly.
   That single number decides between "the mitre declined here" (fixable by relaxing
   `MITRE_MIN_STALLED`, cheap, and testable) and "the mitre cannot see this" (needs a cross-branch
   pass, which is a design change).
2. Only then propose a fix.

Reporting the mechanism before the fix, as directed. The honest state is: **the pivot is confirmed
and characterised; its cause within the mitre is narrowed to one of two possibilities and not yet
decided.**
