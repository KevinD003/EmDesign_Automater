# v2 Part 29 — the peacock, iterated to done

**Date:** 2026-08-01 · Branch `claude/code-quality-improvements-hyu6dg`
Third pass on the photographed peacock patch, on the user's verdict that it was
still not right. Three textured-path mechanisms added, each measured, each gated
on `is_textured` so the flat-art corpus never touches them (stream locks green).

## The journey, in numbers

| | First run (Part 26 code) | Part 27–28 | **Part 29** |
|---|---|---|---|
| Composition | left branch **missing** | complete | complete |
| Objects | 86 | 128 | **113** |
| Sub-40-stitch confetti objects | — | 52 | fewer, absorbed into fills |
| Spill | 36.8% | 20.1% | **9.6%** |
| Interior | 99.0* | 97.4 | 97.6 |
| Floor / density flags | 0/0 | 0/0 | **0/0** |

*First-run interior was high only because most of the design was missing.

## What Part 29 added (all textured-path only)

1. **Speck absorption** (`_absorb_specks`, on the label map before objects
   exist). 52 of 128 objects were sub-40-stitch flecks of one colour inside
   another's fill — each a trim, a lock, and confetti. A component under 3mm²
   whose OWNED ring is ≥70% one other cluster joins that cluster; the fill grows
   over it with no knockout and no extra object. Three calibration lessons kept
   as tests: a boundary-straddling element keeps its vote (no dominant
   neighbour); elements over the cap survive; and the ring vote counts owned
   pixels only — counting background as a dissenting vote left flecks at every
   leaf edge while interior flecks absorbed.
2. **Mask solidify** — close 0.4mm then open 0.3mm per colour mask, healing the
   pinholes and shedding the fringe hairs a photographed thread edge carries.
3. **Seam fill.** On flat artwork, blend pixels (label −1) are anti-aliasing
   halos and deliberately unowned. On a photograph they are the BOUNDARIES
   between abutting regions — leaving them unowned drew a white pinhole seam
   wherever navy met green, everywhere, which no real sew-out has. Every unowned
   foreground pixel now joins its nearest cluster (`distanceTransformWithLabels`,
   with the pixel-id indexing verified on a toy case before use). Spill fell
   20.1 → 9.9 in this step alone.

Ring-share sweep recorded: 0.6 whole-ring (flecks at leaf edges survive) →
owned-ring 0.6 (leaves clean but tail cohesion dips, interior 97.7 → 97.0) →
**owned-ring 0.7** (both hold: interior 97.6, spill 9.6). The middle setting is
kept in history as the reason the final one exists.

## Honest remainder

* The tail-edge whiskers are partly FAITHFUL — the source patch has feather
  barbs there; ours are less ordered than the original digitizer's.
* The neck reads navy where the source fades green-to-blue; gradient rendering
  is the still-open A3 (photo-stitch) capability.
* A photograph of embroidery remains a reconstruction. This is now a *good*
  reconstruction; the vector path is still the clean one.

## Gates

pytest **729 passed + 2 xfailed** (4 new absorption tests) · ruff **19** baseline ·
stream locks green untouched (the gate is the proof the corpus never enters these
paths) · floor 0 · density flags 0.
