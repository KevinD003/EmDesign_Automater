# Peacock vs source — updated comparison after the outline pass (Part 30)

**Date:** 2026-08-01 · Output = tree at `c9f59b1` (61 recovered line objects).
Same method as the Part 29b audit: seven aligned crop pairs re-inspected.
Column "Δ" marks what the outline pass changed; unchanged verdicts carry over.

## Region verdicts, updated

### Head, crest, beak
| Detail | 29b | Now | Δ |
|---|---|---|---|
| Beak | ✗ detached, wrong angle | ✗ still detached — but now navy-OUTLINED like the source's edged beak | edge ✓, position still wrong |
| Crest plumes striping | ✗ one dark mass | ◐ an internal drawn line now splits the mass | improved |
| Crest tufts | ◐ merged blob | ◐ unchanged | — |
| Head→neck gap | ◐ white break | ◐ break remains; the neck's left edge now carries a drawn outline | partial |

### Neck and body
| Detail | 29b | Now | Δ |
|---|---|---|---|
| Neck gradient (green→teal→navy) | ✗ | ✗ unchanged — needs A3 blending | — |
| Body outline | (not scored) | ✓ navy rim drawn around most of the oval, matching the source's edging | **new** |
| Body scale texture | ✗ flat tatami | ✗ still flat — needs MOTIF_FILL | — |
| Body shape/size | ✓ (~10% wide) | ✓ same | — |

### Wing saddle and talons
| Detail | 29b | Now | Δ |
|---|---|---|---|
| Quill separation | ◐ yellow mass | ✓ **drawn dividing lines restore the fanned-quill read** | **fixed** |
| Quill outlines | ✗ | ✓ present | **fixed** |
| Talon toes | ◐ merged | ◐ outlines help; toes still not fully separable | improved |

### Tail
| Detail | 29b | Now | Δ |
|---|---|---|---|
| Eye ring edges | ✗ hard blobs | ◐ navy outline rings around most eyes — closer to the source's ringed eyes | improved |
| Eye structure (ring/iris/pupil) | ◐ | ◐ same colours; outlines add definition | improved |
| Centre stems | ◐ patchy | ◐ patchy still; a few stems gained drawn spines | slight |
| Field direction / two-tone navy | ◐ / ✗ | unchanged — needs guided fill / A3 | — |
| Pinholes | ◐ few | ◐ few (spill 9.6 → 9.1) | slight |

### Flowers and leaves (both branches)
| Detail | 29b | Now | Δ |
|---|---|---|---|
| Petal boundaries | ✗ blobs | ✓ **navy outlines separate petals on every bloom** | **fixed** |
| Flower outlines | ✗ | ✓ | **fixed** |
| Leaf veins | ✗ | ◐ drawn in roughly half the leaves | improved |
| Leaf outlines | ✗ | ◐ partial | improved |
| Buds on stalks | ◐ detached | ✓ stalk lines now connect them | **fixed** |
| Flower centres | ◐ specks | ◐ unchanged | — |

## Stitch-level, updated
| Property | 29b | Now |
|---|---|---|
| Stitch vocabulary | 2 idioms (satin, tatami) | **3** — running-stitch linework joins (61 objects, darkest thread, sewn last like a hand digitizer) |
| Objects / stitches | 113 / 12,762 | 174 / 13,561 |
| Spill / interior | 9.6 / 97.6 | **9.1** / 97.5 |
| Floor / over-limit / density flags | 0/0/0 | **0/0/0** |

## Scorecard, before → after
| Dimension | 29b | Now |
|---|---|---|
| Composition & inventory | 9/10 | 9/10 |
| Shapes & proportions | 7/10 | 7/10 |
| Colour fidelity | 7/10 | 7/10 (gradient trio still flattened) |
| Fill solidity | 8/10 | 8/10 |
| **Texture & stitch artistry** | 3/10 | **5/10** — outlining, the source's signature idiom, is present; motif/long-short/flow still absent |
| **Fine detail** | 4/10 | **6/10** — petals, quills, stalks, half the veins recovered |
| Machine safety | 10/10 | 10/10 |

## What still separates us from the source, in fix order
1. **A3 gradient blending** — the teal neck, two-tone navy, two-green eye rings.
2. **MOTIF_FILL** — the body's feather-scale crescents.
3. **Guided/curved fill grain** — tail stitches flowing along the sweep.
4. **Edge-aware segmentation** — beak attachment, crest stripe whites.
