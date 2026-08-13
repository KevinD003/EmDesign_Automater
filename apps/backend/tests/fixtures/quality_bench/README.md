# What these fixtures are good for, and what they are blind to

A standing statement, required by the ruling of 2026-08-18, kept beside the fixtures it
describes. The full enumeration with per-branch input classes is
`docs/CORPUS-COVERAGE-2026-08-18.md`; this is the summary a test author should read before
trusting a green suite.

## Good for

The ten bench fixtures (plus the four tracked C-tier baselines) are **flat, hard-edged,
vector-style artwork** — and on that class they are genuinely strong. They exercise palette
planning, satin/tatami classification by measured width, the generation core, routing, locking,
and the stream accounting end to end. Nearly every defect this engagement found and fixed —
the DET2 coverage inflation, the space-collision behind the "90 penetrations", the worksheet
rows-vs-header gap, the parity fix — was findable on these fourteen. For changes to the
flat-artwork pipeline, a red here means something and a green here is evidence.

## Blind to — measured, not suspected

Branch coverage of exactly this corpus through digitize + rebuild (2026-08-18): pipeline.py
90 %, rebuild.py 71 %, underlay.py 50 %. Every gap points the same direction — **the messy
real-world middle**:

* **Photographs and textured artwork** — the textured path, dark-linework tracing, sketch
  retries, the texture-retry-accepted branch: none fire on any of the fourteen.
* **`RUNNING_SINGLE`** — zero objects across the corpus, while the one real competitor artwork
  on record (the angelfish) is 55 of 100. A one-penetration-per-object rebuild defect shipped
  invisibly for exactly this reason (fixed `ce254a8`; pinned by constructed objects, still zero
  fixture reach).
* **Declared foregrounds** — transparent-PNG alpha and SVG inputs, the class DET3 exists for:
  every fixture is an opaque PNG, so the declaration path is covered only by constructed tests.
* **Dark garments** — the linework-suppression branch and the phantom COLOR_CHANGE it can leave
  behind (`stops_partition_matches` has never been exercised false by a fixture).
* **Oversized sources** — the `_MAX_WORK_PX` downscale path.
* **Every editor-side stitch type on rebuild** — appliqué, spiral/radial fills, divided flow,
  forced satin. These are editor states, not uploads; constructed-design tests are the honest
  tool for them, and image fixtures would be coverage theatre.

## The rule this implies

A green suite certifies the flat-vector pipeline. It does not certify behaviour on a photograph,
a transparent export, or a dark garment, and it says nothing about run-object round trips beyond
the constructed cases. Do not quote "the suite passed" against those classes — that is the same
error as quoting a stitch count without its fabric and hoop.
