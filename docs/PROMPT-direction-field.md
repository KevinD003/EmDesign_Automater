# Scoping brief — R004-impl: a coherent direction field

**Status:** not started. This is the scope, the evidence it rests on, and the gates it has
to pass. It is deliberately not a task list to hand to a single session.

**Read first:** `docs/benchmarks/v2-part46-audit.md` — the measurement that defines this
work, and the four explanations it rules out.

---

## 1. Why this exists, in one paragraph

Our stitch directions disagree with a professional sew-out by a mean of **49.9°**, where
45° is a coin flip. That number is real: it survives a global-offset sweep (no convention
bug), it is flat across object size (not fragmentation), it is the same for satin and
tatami (not satin-specific), and it barely moves when the comparison is restricted to
segments that are provably looking at the same element (not misregistration). It is also
**not** for want of shape analysis — `_fill_angle` has computed each region's principal
axis from central image moments since Part 24, and the bench shows 41 distinct angles with
per-fixture spread up to 67.5°.

The angles vary. They are simply not the angles a digitizer would choose.

## 2. The hypothesis this work tests

A professional does not derive direction from a region's principal axis. They derive it
from what the shape *is*: petals radiate from a centre, a leaf follows its vein, lettering
follows the stroke, a border follows its edge. Crucially, **neighbouring regions that
belong to one visual element share a flow** — and a per-object angle cannot express that,
however well each individual angle is computed. Our regions are decided by colour
clustering, which cuts a single visual element into several objects that then each pick
their own axis independently.

So: replace *an angle per object* with *a direction field over the design*, and have every
generator sample it rather than carry a scalar.

The reviewer supplied the supporting literature, and it points the same way: Zhenyuan et
al. (2023), *Directionality-Aware Design of Embroidery Patterns*, generates stitches from
direction and density fields and extracts sources and sinks from the field's divergence;
Vaxman et al. (2016), *Directional Field Synthesis, Design, and Processing*, is the survey
that establishes direction fields as the standard abstraction for coherent flow over a
surface. Professional tools expose the same model from the user's side — eXPerience's
Stitch Flow, and the equivalents in Wilcom and Hatch, let the user draw several direction
lines and interpolate a field between them rather than setting one angle per region.

**These are references, not a design.** Nobody on this project has read those
implementations, and no code from them will be used. The claim being borrowed is only the
abstraction: field, not per-region scalar.

## 3. Why it is multi-part

Because it changes the interface between four things that currently only agree by accident:

1. **The field itself** — how it is represented, solved, and stored.
2. **Every generator** — `_scanline_fill`, `_contour_fill`, `_spiral_fill`, `_radial_fill`
   and the satin column pacing each currently take an angle or derive their own.
3. **`rebuild_design`** — a user editing an object today sets `stitch_angle`. If direction
   comes from a field, what does that control mean, and what happens to designs that
   already carry one?
4. **The measurement** — 49.9° is measured against one photographed sew-out. That is enough
   to prove the current approach is at its ceiling; it is not enough to *steer* a field
   solver. This needs its own instrument before the engine work starts.

Any one of those shipped alone leaves the pipeline in a worse state than it is now.

## 4. Suggested sequence

**D0 — the instrument.** Before any engine change. A direction score that can rank two
candidate fields on the same artwork, not just report one number. It needs more than one
reference sew-out; one photograph cannot distinguish "wrong flow" from "different but
equally valid flow". Gate: the instrument self-tests on synthetic fields of known shape,
the way `measure_stitch_direction.py --self-test` already does for stripes.

**D1 — the field, solved and visualised, consuming nothing.** Build the field over the
foreground and render it as a quiver plot beside the artwork. Ship no stitch change at all.
Gate: the picture is defensible to a digitizer's eye on all ten bench fixtures, and the
four stream locks are untouched because nothing consumes it yet. This is the step where the
approach is cheap to abandon.

**D2 — fills consume the field.** Tatami first, because scanline rows follow a single angle
today and are the clearest before/after. Gate: interior coverage holds within noise, the
Part 44 contact sheet shows the change on all ten fixtures, and the direction instrument
from D0 improves.

**D3 — satin consumes the field.** Column pacing already runs perpendicular to the medial
axis, which is usually right; the field should refine it near junctions rather than
override it. Gate: penetration floor stays at zero violations, satin pitch stays in band.

**D4 — the user-facing control.** What `stitch_angle` means once a field exists, and the
migration for stored designs that carry one. Gate: an old design still rebuilds to
something sensible.

## 5. Standing constraints

- **Every stage renders before it measures.** Parts 39, 40, 41 and 45 each caught a defect
  by looking at a picture that no metric flagged; Part 44's harness exists for exactly this
  and will show a direction change plainly.
- **Coverage is not allowed to pay for direction.** Interior and edge-band coverage, the
  penetration floor, and the machine stitch limit are gates, not trade-offs.
- **Fields are expensive.** A 771-object panel is the working size, and a solver that takes
  a minute per design is not shippable. Measure the cost at D1, before anything depends
  on it.
- **Do not tune to the 0.7 correlation target.** It came from a brief written before any of
  the Part 46 measurements. Set the target from what D0's instrument shows is achievable.

## 6. What would make this not worth doing

Stated in advance, so the answer is honest if it comes:

- If D1's field is not visibly better than the current per-object axes on a digitizer's
  eye, stop. The measurement in Part 46 says the current approach is at its ceiling; it
  does not promise the field clears that ceiling.
- If the solve cost cannot be brought under a few seconds on the panel, stop. The feature
  is not worth a pipeline that is too slow to use.
- If D2 improves the direction score but coverage or the floor regresses, revert. That
  trade has been offered before — Part 37 measured two changes that improved every metric
  while flooding a lattice — and it has always been the wrong one.
