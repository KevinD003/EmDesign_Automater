# What these fixtures are good for, and what they are blind to

A standing statement, required by the ruling of 2026-08-18, kept beside the fixtures it
describes. **Rewritten 2026-08-22, in the commit that promoted A01 and A02** — a standing
statement that has gone false is worse than none, and the promotion closed some of the gaps
this file used to name. The full enumeration with per-branch input classes is
`docs/CORPUS-COVERAGE-2026-08-18.md`; the set enumeration is
`docs/FIXTURE-SET-ENUMERATION-2026-08-21.md`; this is the summary a test author should read
before trusting a green suite.

## The standing set is SIXTEEN, in three tiers

Defined once, in `coverage_audit.fixtures()`. Everything that measures "all fixtures" —
`coverage_audit.py`, `trace.py --all`, `visual_regression.py`, `test_stream_accounting.py`,
`measure_hairline_census.py` — resolves it from there.

| tier | n | what | conditions |
| --- | ---: | --- | --- |
| bench | 10 | flat, hard-edged, vector-style artwork | per fixture, `FIXTURE_PARAMS` |
| C-tier | 4 | parametric corpus images SH2 measured | cotton @ 130x180, 4 colours |
| A-tier | 2 | **real photographs of finished embroidery** | cotton @ 100x100 / 130x180, 6 colours |

The A-tier parameters were **invented, not measured** — a photograph carries no scale, so its
physical size is a choice. They are argued in `coverage_audit.A_TIER_PARAMS` and chosen from
the hoops the product actually sells. Quote them with every A-tier number.

## Good for

On flat artwork the bench ten are genuinely strong: palette planning, satin/tatami
classification by measured width, the generation core, routing, locking, and the stream
accounting end to end. Nearly every defect this engagement found and fixed — the DET2 coverage
inflation, the space-collision behind the "90 penetrations", the worksheet rows-vs-header gap,
the parity fix — was findable there. For changes to the flat-artwork pipeline, a red means
something and a green is evidence.

The promotion adds, for the first time, two inputs on which the **textured** path runs end to
end (`_interior_texture` 7.43 and 10.20 against a 6.0 gate) and on which a **dark garment**
is present.

## Blind to — measured, not suspected

Branch coverage of the pre-promotion corpus through digitize + rebuild (2026-08-18):
pipeline.py 90 %, rebuild.py 71 %, underlay.py 50 %. **Not re-measured after the promotion** —
that is the honest state, and it is the first thing the next tranche should re-run.

Closed by the promotion:

* **Photographs and textured artwork.** The textured branches now fire on two fixtures.
* **Dark garments.** A02 is black cloth; the substrate rule and the dark-linework luminance
  guard both execute on it.
* **`RUNNING_SINGLE` at volume.** A01 emits 36 of 122 objects (29.5 %) as `RUNNING_SINGLE`,
  from the dark-linework pass. Against the one real competitor artwork on record (the
  angelfish, 55 of 100) that is the same order of magnitude, on our own output, for the first
  time. A02 emits ZERO — its substrate luminance is 0.0 against `DARK_CLOTH_LUM = 60.0`, so
  the linework pass never runs.

Still blind, and the list is shorter but not shorter than it looks:

* **Hairline runs on anything photographic.** `hairline_runs` was reached ZERO times by either
  photograph — their narrowest classified regions are 0.34 and 0.38 mm against
  `MIN_FEATURE_W_MM = 0.25`, none under 0.30. The candidate mechanism is the textured path's
  close-at-0.4 mm / open-at-0.3 mm on each cluster mask, which only a photograph takes. The
  emptiness is measured; the mechanism is inferred, and the naive open arithmetic would
  predict a 0.6 mm floor rather than the 0.34 mm observed — so no photographic width floor is
  claimed. The promotion did not widen RS1's evidence base by one image. See the re-measured
  census in `hairline_runs`' docstring.
* **The phantom `COLOR_CHANGE`.** Still never exercised, and the promotion showed WHY the
  expected fixture class cannot reach it: the phantom needs the dark-linework pass to run and
  then be suppressed, but a dark garment is excluded one guard earlier by `DARK_CLOTH_LUM`.
  The class that can reach it is a **mid-tone** garment — light enough to pass 60.0 luminance,
  with its darkest thread inside `SUBSTRATE_DELTA` of the cloth. The corpus has none.
* **Declared foregrounds** — transparent-PNG alpha and SVG inputs, the class DET3 exists for:
  every fixture is an opaque PNG, so the declaration path is covered only by constructed tests.
* **Oversized sources** — the `_MAX_WORK_PX` downscale path.
* **The texture RETRY.** It is guarded on `not is_textured`, so the two fixtures with the
  highest uncovered share in the whole set (A02 20.15 %, C24 17.75 %, A01 13.41 %) are the
  ones it can never fire on. Coherent by design; worth knowing before quoting it as a rescue.
* **Every editor-side stitch type on rebuild** — appliqué, spiral/radial fills, divided flow,
  forced satin. These are editor states, not uploads; constructed-design tests are the honest
  tool for them, and image fixtures would be coverage theatre.
* **Real customer jobs.** Nothing here has been sewn. Two photographs of finished embroidery
  are not a sew-out, and no number in this repository has been checked against thread.

## Known-bad output inside the standing set

A green suite does not mean these fixtures produce good work. Measured 2026-08-22 and
**deliberately not fixed** in the promotion tranche:

* **A02 lays 4,638 penetrations — 21.0 % of the design — in near-black thread on black
  cloth.** The `#080808` cluster sits 13.86 from the inferred substrate against
  `SUBSTRATE_DELTA = 12.0`, so it misses deletion by 1.86. Present at all four parameter
  blocks tried, including the corpus runner's own.
* **C24 renders a wholesale-deleted rectangle** (SH2's finding, visible in a baseline for the
  first time since 2026-08-22).

## The rule this implies

A green suite certifies the flat-vector pipeline, and now also says that two photographs
digitize without crashing and without moving any locked stream. It does not certify that their
output is sewable — 21 % of A02's stitches are thread on bare cloth and the suite is green.
Do not quote "the suite passed" against a class; quote a measurement, with its conditions.
