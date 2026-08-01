# v2 Part 30 — the outline pass: linework recovered from the image

**Date:** 2026-08-01 · Executes root cause #2 of the Part 29b detail comparison —
the one it marked *"buildable now"*. The source patch edges nearly every element
in dark stem stitch (petal boundaries, leaf veins, quill separations, crest
stripes); none of it survived segmentation, because a ~0.5mm dark line between
two colour fields quantizes into whichever field is nearest.

## Mechanism

The linework is recovered from the IMAGE, not the labels:

1. **Black-hat transform** (0.6mm kernel) responds exactly to thin-dark-on-lighter
   structure — and to nothing else.
2. A **half-width cap** (0.7mm) cuts anything thicker before thinning: a dark
   REGION is a colour field, not drawing, and without the cap the tracer would
   draw a spine down the navy tail (pinned by test).
3. The same **medial-axis branch tracer** that routes satin turns the response
   into ordered polylines; chains under 4mm are discarded as noise.
4. Sewn as a final **running-stitch pass (1.4mm) in the palette's darkest
   thread** — the top layer, exactly where a hand digitizer sews outlines.
   Emitted before the lock/merge passes, so every line gets ties and the trims
   are real. Each line is a `RUNNING_SINGLE` object whose stored contour is the
   PATH — rebuild's running branch re-stitches it along the line, not as a fill.

Textured input only. Flat artwork's dark lines are their own colour regions and
already digitize as objects — the corpus never enters this path (locks green).

## Measured on the peacock

| | Part 29 | Part 30 |
|---|---|---|
| Objects | 113 | 174 (**61 recovered line objects**) |
| Petal boundaries | ✗ lost — blooms read as blobs | ◐→✓ navy outlines separate petals again |
| Leaf veins | ✗ | ◐ partially drawn |
| Quill separations on the saddle | ◐ | ✓ drawn |
| Spill | 9.6% | **9.1%** |
| Interior | 97.6 | 97.5 |
| Floor / density flags | 0 / 0 | **0 / 0** (max cell 8) |
| Stitches | 12,762 | 13,561 (+6%) |

`StitchType.RUNNING_SINGLE` is now the **seventh** enum value the generator can
produce (was 3 of 21 at the blockers audit; now SATIN, TATAMI, CONTOUR_FILL,
SPIRAL_FILL, RADIAL_FILL, RUNNING_SINGLE + APPLIQUE via rebuild).

## Still open from the comparison (unchanged verdicts)

Gradient colours (deep navy / mint / teal) need A3 photo-stitch blending; the
body's scale motif needs MOTIF_FILL; in-object curved grain needs guided fill;
sub-millimetre separations (crest stripes, beak joint) need edge-aware
segmentation. Each remains honestly ✗.

## Gates

pytest **731 passed + 2 xfailed** (2 new linework tests) · ruff **19** baseline ·
stream locks green untouched · floor 0 · density flags 0.
