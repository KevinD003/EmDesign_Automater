# What is actually blocking us from being competitive

**Date:** 2026-08-01 · Measured against the tree at `4fe8590` (v2 Part 24b).
Companion to [`COMPETITIVE-GAP-ANALYSIS.md`](./COMPETITIVE-GAP-ANALYSIS.md), which asked
*"why does the stitching look different?"*. This one asks the broader question across
**input, parameters, performance, usage, features and the stitch stream itself** — and
answers it with greps, timings and live runs rather than impressions.

Where a number appears, it was measured in this container today. Where something is
inferred rather than measured, it says so.

---

## 0. The short answer

Three things block us, and they are not the ones the output makes you look at first.

| Rank | Blocker | Why it outranks everything else |
|---|---|---|
| **1** | **We cannot read a vector file.** SVG, PDF, EPS, AI, CDR are all rejected at the decoder. | Every competitor digitizes from outlines. We digitize from a *guess at* outlines, recovered by segmenting a bitmap. Every "the shape isn't exact", "elements went missing", "text is fuzzy" complaint traces here. This is upstream of every stitch-quality fix we have shipped. |
| **2** | **The stream has no travel and no locks.** `ConnectMethod` declares TRIM / TRAVEL_RUN / JUMP; only **TRIM** is ever produced. There is no tie-off code anywhere (`grep` for `tie_off\|lock_stitch` returns nothing). | Travel is **7–27 %** of needle movement, the longest single jump measured is **87 mm**, and 6 of fixture 07's 20 thread cuts have no lock before them. This is what a production floor rejects a file for, and no coverage metric sees it. |
| **3** | **3 of 21 stitch types exist.** SATIN, TATAMI, CONTOUR_FILL. The other 18 are enum values. | Lettering, photo, motif, appliqué, cross-stitch and gradient blending are all "declared, not built". This is the feature-list gap, and it is the *least* urgent of the three because it is honest absence rather than silent wrongness. |

Everything below is the detail, by dimension.

---

## 1. Input — the root cause

| What | Measured | Competitor |
|---|---|---|
| Vector formats | **SVG / PDF / EPS all raise `ValueError: Could not decode image`** | Wilcom, Hatch, Embird all import AI/EPS/SVG/PDF/CDR and digitize from the true outline |
| Raster formats | PNG / JPEG / BMP / WebP | same |
| Working resolution | Capped at `_MAX_WORK_PX = 1200`. Detail **saturates at ~640px**: fixture 02 gives identical output at 640, 1200 and 2400px | Vector input has no resolution at all |
| Detail recovered vs input size | fixture 07 at 200 / 260 / 320 / 640 / 900 px → **10 / 15 / 16 / 21 / 23 objects** | n/a — outlines are exact |

The second row of that table is the whole argument. A customer's logo almost always exists
as vector. We throw that away and ask them for a PNG, then spend the entire pipeline —
rembg, k-means, `_reclaim_ink`, medial axis, classification — reconstructing what the vector
file already stated exactly. Parts 4 through 24 have been improving that reconstruction.
**Reading the vector directly removes the need for most of it.**

---

## 2. Parameters — a 4-knob product against a several-hundred-knob one

### What a user can set when digitizing

| Exposed | Value |
|---|---|
| `fabric_type` | 12 profiles |
| `hoop_size` | free text `WxH` |
| `max_colors` | integer |
| *(that is the entire surface)* | |

### `max_colors` does not do what it says — measured on fixture 08

| Asked for | Colour stops returned | Objects | Stitches |
|---|---|---|---|
| 2 | **3** | 8 | 5,148 |
| 4 | **5** | 21 | 5,865 |
| 6 | 4 | 20 | 5,787 |
| 10 | **4** | 10 | 6,026 |
| 16 | **4** | 10 | 6,026 |

Three separate defects in one table: asking for 2 returns **3**; asking for 10 or 16 returns
**4**; and object count is **non-monotonic** (21 at 4 colours, 10 at 10 colours). A customer
who asks for more colour detail gets *less* design. Competitors treat colour count as a
target that is honoured or a warning that is raised.

### What a user can edit per object

| Exposed in the UI | Not exposed, and competitors have it |
|---|---|
| Stitch type, density, angle, underlay, pull compensation, colour, name, order | Min/max stitch length · random factor / edge-walk variance · tie-in & tie-off style · per-axis pull compensation · short-stitch rules on curves · split lines · per-object fabric override · start/end point placement · lock-stitch length |

**A drift I introduced and should name:** the UI underlay dropdown still offers only
`None / Center walk / Edge walk`. Part 24 added `DOUBLE_ZIGZAG` and `PARALLEL` to the
generator, so an object can now carry an underlay the properties panel cannot display or
round-trip. That is a real inconsistency shipped in the last two commits.

---

## 3. Performance — one measured defect that matters more than all the rest

### The event loop is blocked for the whole of every digitize

`app/routers/digitize.py` declares `async def digitize(...)` and then calls the CPU-bound
`digitizer.digitize_image(...)` synchronously inside it. FastAPI runs `async def` handlers
**on the event loop**, so nothing else in the process can proceed.

Measured by firing `/health` every 250 ms during one digitize of fixture 07:

| | Probes that completed during a 12.58 s digitize | `/health` latency |
|---|---|---|
| **As shipped** | **0** | — (never returned) |
| With `async` removed (diagnostic only, reverted) | **37** | max 951 ms |

The launch runbook specifies `--workers 1`. So today, **one person digitizing freezes the
server for every other user for 5–13 seconds** — including the health check a load balancer
uses to decide the box is alive. For the stated goal of 100 users on a LAN, this is the
single highest-value fix in this document and it is a one-keyword change.

*(I first tested this with a fast fixture and a single probe, and it wrongly came back
"responsive" — the probe landed during the `await file.read()` window before the blocking
work began. The result above uses a slow fixture and repeated probes.)*

### Other timings

| Measurement | Value | Note |
|---|---|---|
| Cold start penalty | **+5.2 s** on the first request of a fresh worker | U2-Net model load |
| Warm digitize | 1.6 – 12.6 s depending on fixture | fixture 07 is the worst |
| Whole 10-fixture corpus | ~47 s | |
| Throughput implied | **~5–12 designs/minute per worker**, serialized | inferred from the above, not load-tested |

---

## 4. The stitch stream — what a production floor would reject

| Property | Measured across the 10-fixture corpus | Industry expectation |
|---|---|---|
| Jumps | **1,216** over 45,589 stitches (12.7 – 36.0 per 1,000) | as few as possible; travel hidden under later stitching |
| Trims | 54 | < 1 per colour block |
| Travel as a share of needle movement | **7.2 % – 27.1 %** (fixture 07 worst) | single digits |
| Longest single jump | **87 mm** | anything over ~10 mm should be a trim, not a jump |
| Tie-off / lock stitches | **No implementation exists.** 14 of fixture 07's 20 cuts happen to be preceded by short stitches as an artifact of dense satin ends; **6 have nothing** | a deliberate lock at every start and every end |
| Avoidable colour changes | **5** across 10 fixtures — the same thread hex mounted twice in one design | 0; same-colour blocks are merged |
| Penetration floor / over-limit / density flags | **0 / 0 / 0** | ✅ we are ahead here |

The last row is worth keeping in view: our machine-safety measurement is genuinely better
than anything the competitors publish. The rows above it are the ones that lose a job.

---

## 5. Features — reachability, not intention

Counted by grepping for each enum member being assigned anywhere in the generator.

| Enum | Reachable | Dead |
|---|---|---|
| `StitchType` | **3 / 21** — SATIN, TATAMI, CONTOUR_FILL | RUNNING_×3, BACKSTITCH, STEMSTITCH, CROSS_STITCH, ZIGZAG, E_STITCH, MOTIF_FILL, MOTIF_RUN, ACCORDION_FILL, LAYDOWN, MANUAL, PHOTO_STITCH, GRADIENT_BLEND, APPLIQUE, CHENILLE, REDWORK |
| `UnderlayType` | **4 / 6** — CENTER_WALK, EDGE_WALK, DOUBLE_ZIGZAG, PARALLEL | NONE, CONTOUR |
| `ConnectMethod` | **1 / 3** — TRIM | TRAVEL_RUN, JUMP |

Several of the dead `StitchType` values are cheap: RUNNING_SINGLE/DOUBLE/TRIPLE and
BACKSTITCH already have a generator (`_manual_run`) reachable through `rebuild_design` —
they are simply never *chosen* by the digitizer. E_STITCH plus the existing appliqué path is
a genuine appliqué workflow. Those are days, not months. PHOTO_STITCH and a real lettering
engine are months.

---

## 6. Usage — where a user hits a wall

| Workflow | Us | Competitor |
|---|---|---|
| Import a vector logo | ✖ rejected | ✔ core path |
| Reshape an outline / move nodes | ✖ | ✔ |
| Manual / freehand digitizing | ✖ (`MANUAL` exists in rebuild only) | ✔ |
| Edit the sew sequence | reorder objects only | ✔ full sequencing, branching |
| Stitch-level edit | ✖ | ✔ |
| Split a design across hoops | ✖ | ✔ |
| Lettering | system TrueType rasterised | 62–250 digitized fonts, 9 baselines |
| **Small hoop** | **silently destroys the design** | warns |

That last row is a live user-facing defect. Fixture 07 into successively smaller hoops:

| Hoop | Design size | Objects | Warnings raised |
|---|---|---|---|
| 130×180 | 106×106 mm | **21** | 0 |
| 100×100 | 73×73 mm | 16 | 0 |
| 50×50 | 37×37 mm | **5** | 0 |
| 40×40 | 29×29 mm | **4** | **0** |

A customer who picks a 40 mm hoop loses **81 % of their logo's objects and is told nothing**.
The mechanism is legitimate — scaled-down features fall under `MIN_FEATURE_W_MM` /
`MIN_REGION_MM2` and cannot be sewn — but silence is not. The pipeline already knows exactly
which regions it dropped and why (`_CLASSIFICATION_LOG`); none of it reaches the user.

---

## 7. What I would do, in order

Ordered by **user-visible improvement per unit of risk**, not by size.

| # | Item | Effort | Why here |
|---|---|---|---|
| **1** | Drop `async` from the digitize/lettering/export handlers | **minutes** | Measured 0 → 37 concurrent requests served. Blocks the 100-user goal today. |
| **2** | Surface what was dropped: hoop-too-small warning, colour-count honoured or explained, dropped-region list | **hours** | Turns three silent failures into three explained ones. `_CLASSIFICATION_LOG` already has the data. |
| **3** | Tie-off / lock stitches at every start and end; convert long jumps to trims | **~1 day** | The clearest "this file is not production-ready" tell we have. |
| **4** | Fix the UI underlay dropdown drift; expose min/max stitch length | **hours** | A defect I shipped in the last two commits. |
| **5** | **SVG import → digitize from real outlines** | **~1 week** | The root cause. Removes the segmentation guesswork the last 20 parts have been compensating for. Biggest single quality jump available. |
| **6** | `TRAVEL_RUN` + branching: one entry, one exit, travel hidden under later stitching | **~1 week** | Attacks the 27 % travel and the 87 mm jump directly. |
| **7** | Same-colour block merging | **~1 day** | 5 avoidable colour changes across 10 fixtures. |
| **8** | Lettering engine (glyph outlines → satin, kerning, baselines) | **months** | Largest feature gap; do after the vector path exists, since it needs the same outline machinery. |
| **9** | Photo / gradient digitizing | **months** | New category, independent of the rest. |

Items 1–4 are roughly two days of work and remove three silent failure modes plus the
scalability blocker. Item 5 is the one that changes what the product *is*.

**Guardrail, unchanged:** the 10-fixture corpus must stay byte-identical or better, with
floor violations, over-limit stitches and flagged density cells all at 0 — the bar that
reverted a bad optimization in Part 20, passed a good one in Part 21, and killed the satin
cap change in Part 24b.
