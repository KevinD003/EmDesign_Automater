# Capturing a sew-out reference that can judge stitch direction

**Why this exists.** Every direction number in this project since Part 38 has been
scored against one photograph. Part 53 measured that the photograph **cannot see
thread** on structures narrower than about 2 mm, and 77% of the design's satin is
narrower than that. On those regions the structure tensor reports the *column's
own axis* instead of the thread lying across it, so a correctly sewn satin column
is scored as ~90° wrong and any contour-parallel field is scored as right.

Until a better reference exists, no satin or fill direction change can be judged
numerically. This is how to capture one.

Everything below is derived by measurement, not by rule of thumb — reproduce it
with `scripts/reference_protocol.py --spec`.

---

## The number

| | |
|---|---|
| **Capture at** | **≤ 0.074 mm per pixel** |
| equivalently | ≥ 5 px across a 0.4 mm thread |
| relative to the current panel | **2.5× the linear resolution** (6× the pixels) |
| the panel we have | 0.186 mm/px — crossover at 2.0 mm, **23% of satin usable** |

Part 53 estimated "roughly 0.05 mm/px" from arithmetic. The measured figure is
**0.074**, so that estimate was in the right place but was never a measurement;
this one is, and it is derived below.

**Treat 0.074 as a floor to aim past, not a threshold to hit.** It extrapolates
below the range that could be measured, so shoot finer if it is free.

## How the number was derived

Downsample the reference we already have, re-measure the column width at which
the reading flips from edges to thread, and read off the law. Real thread, real
optics, no simulation:

| mm/px | frame | crossover | satin usable |
|---:|---:|---:|---:|
| **0.186** (the panel) | 736×1689 | 2.0 mm | **23%** |
| 0.219 | 625×1435 | 2.0 mm | 22% |
| 0.266 | 515×1182 | 2.2 mm | 15% |
| 0.338 | 404×928 | 2.2 mm | 14% |
| 0.413 | 331×760 | 2.2 mm | 14% |
| 0.531 | 257×591 | 3.0 mm | 2% |

In pixels the crossover runs 10.8, 9.1, 8.3, 6.5, 5.3, 5.6 — it drifts because
two limits are in play: the analysis window (fixed in pixels) binds at fine
scales, thread pitch (fixed in millimetres) binds at coarse ones. The
extrapolation therefore uses the **finest** point measured (10.8 px), which is
both the relevant regime and the conservative choice. The panel's narrowest satin
is ~0.8 mm (5th percentile 0.73 mm), so 0.8 mm ÷ 10.8 px ≈ **0.074 mm/px**.

*A simulation was built first and thrown away.* A synthetic thread pattern near
the sampling limit aliases to zero 3-tap gradient response — Sobel over
`[a, b, a]` is 0 — so it reported "edges" at every width and every blur, and
calibrating it back to reality would have needed two free parameters fitted to
one observation. The downsample law needs none.

## What it buys

Projected from the panel's own satin width distribution:

| capture | crossover | satin usable | tatami usable |
|---:|---:|---:|---:|
| 0.186 mm/px (today) | 2.0 mm | 23% | 32% |
| 0.120 mm/px | 1.3 mm | 84% | 77% |
| **0.074 mm/px** | **0.8 mm** | **95%** | **86%** |

Even 0.120 mm/px — 1.5× the current resolution — takes satin from 23% to 84%.
If the full spec is impractical, that is a large gain for a modest one.

## How to shoot it

**One frame will not do it.** At 0.074 mm/px a 360×350 mm hoop is roughly
4800×4700 px of *usable detail*, which is beyond an ordinary camera once optics
and motion are accounted for. So:

1. **Shoot close crops**, not the whole panel. Pick 5–10 regions that between
   them cover the cases that matter: a thin satin border, a wide satin element, a
   curved or tapering column, a junction where two columns meet, a large tatami
   fill, and a ring or letter bowl.
2. **Include the whole of each region plus a margin**, so the crop can be located
   in the full panel.
3. **Also shoot one whole-panel frame** at any resolution. It is the anchor every
   crop is registered against.
4. **Keep the fabric flat and the sensor parallel to it.** The registration
   recovers translation, rotation and scale — not perspective. A tilted shot
   introduces a scale gradient that no similarity transform removes.
5. **Diffuse, raking light.** Thread direction is legible because thread has
   relief. Flat-on flash removes exactly the shadowing that makes it visible.
   Light from one side at a shallow angle, diffused.
6. **Focus on the thread, not the fabric.** Stop down enough that the whole
   region is within depth of field; a 0.4 mm thread out of focus is a smooth
   patch and its direction is gone.
7. **Do not sharpen, denoise or upscale.** Every one of those invents or destroys
   the local gradients this is measured from. Straight out of the camera.
8. **Record the scale.** Photograph a ruler in one frame, or note the hoop size
   and frame the whole hoop once. Without a millimetre scale none of the checks
   below can run.

## Before scoring anything on it

Run these in order. Any failure means the photograph is not usable yet, and
finding that out now is the entire point of this document.

```
scripts/reference_protocol.py --selftest
scripts/reference_protocol.py --validate <new-photo> --mm-per-px <scale>
scripts/measure_field_headroom.py --image <new-photo> --validity
```

The third is the one that matters. It reports, for the new photograph, the width
at which the reading flips and what share of satin sits above it. **A reference is
usable for satin direction only when its crossover is at or below the narrowest
satin it has to judge.**

To place a macro crop in the design's frame, `reference_protocol.register_crop`
returns a similarity transform from crop pixels to full-panel pixels; compose it
with the panel's own registration. It is self-tested against known transforms at
2×, 3× and 4× upscale and lands within ~0.5 px.

## If a better photograph is not possible

Then stop scoring stitch direction against this panel and say so. See
`docs/benchmarks/v2-part53-audit.md` and `v2-part54-audit.md` for what the current
reference can and cannot still answer, and for the alternative evaluation axis.
