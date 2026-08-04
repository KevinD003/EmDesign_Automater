# Verified triage: the "STITCHIQ vs Industry" comparison

**Date:** 2026-08-03 · Every claim checked by running the code at commit `303cd4f`, not
by reading it. The source deck lists **five critical gaps**. Three are real and already on
the plan. **Two are flatly false**, and they are the two it ranks #1 and #2.

---

## The two claims that are wrong

### ❌ "STITCHIQ has zero pull compensation. Every satin column and fill will be undersized."

Pull compensation has shipped since v1 and has been fabric-aware since v2 Part 13. It is
applied on both paths — `_dilate_pull()` widens fill regions, `extra_half_px` widens satin
columns — stored per object as `pull_compensation`, honoured and user-editable through
`rebuild_design`, and pinned by `tests/test_pullcomp.py` (8 tests).

Measured just now, same 180×80px bar, five fabrics:

| Fabric | Pull per side | Finished width |
|---|---:|---:|
| denim | 0.15 mm | 55.20 mm |
| cotton | 0.20 mm | 55.20 mm |
| polo/knit | 0.40 mm | 55.20 mm |
| fleece | 0.50 mm | **55.80 mm** |
| towel | 0.50 mm | **55.80 mm** |

The compensation is applied and it changes the finished geometry. The claim is not
"understated" — it is the opposite of what the code does.

### ❌ "STITCHIQ has zero fabric awareness — every design uses uniform settings regardless of whether it's going on a t-shirt or a thick towel."

`FABRIC_PROFILES` covers **16 fabrics × 5 parameters** (`pull_mm`, `row_mm`, `satin_mm`,
`under_mm`, `inset_mm`) — the same axes the deck credits Hatch's Auto-Fabric with. It was
built in v2 Part 13 specifically because density, underlay step and edge inset used to be
global constants, which was then the largest gap against every competitor.

Same bar, same hoop, different fabric — the output is not uniform:

| Fabric | Row pitch | Stitches |
|---|---:|---:|
| denim | 0.40 mm | **1,462** |
| cotton | 0.45 mm | 1,139 |
| towel | 0.50 mm | 1,194 |
| fleece | 0.55 mm | **886** |

A 65% swing in thread laid down, chosen by fabric. "Zero fabric awareness" is false.

### ⚠️ "0/5 on path optimization" — overstated, but the underlying number is real

`_route_travel()` does replace trims with in-region travel runs, and it is load-bearing:
Part 25 measured a rebuilt donut carrying **63 hole-crossing trims** without it. So it is
not zero. But object sequencing is by **colour luminance rank, not nearest-neighbour**,
and the corpus panel really does produce **837 trims**. The score is wrong; the problem it
points at is real and is R006 on the plan.

---

## The three claims that are right

| # | Claim | Verified |
|---|---|---|
| 3 | Stitch direction is effectively random — median 49.9°, where 45° is a coin flip | **Yes.** Measured against a real sew-out. Ours, not theirs — it is not in the original 50-item list. R004, and the largest quality gap in the product |
| 4 | Fragmentation (16 stitches/object) and 837 trims | **Yes**, both measured on the neckline panel. R005 and R006 |
| 5 | The enum advertises stitch types the engine does not have | **Yes, and it was worse than stated.** See below |

### Gap 5 was worse than the deck says, and is now fixed

The deck says "23 members, only 4 have generators, 16 are phantoms". Measured properly —
by rebuilding the same design under every member and hashing the stream — **23 names
produced 9 distinct outputs**:

- **11 members returned a byte-identical tatami fill** (CROSS_STITCH, CHENILLE,
  PHOTO_STITCH, GRADIENT_BLEND, MOTIF_FILL, MOTIF_RUN, STEMSTITCH, ZIGZAG, E_STITCH,
  ACCORDION_FILL, LAYDOWN) — they fell through `rebuild_design`'s final `else`.
- **BACKSTITCH was byte-identical to RUNNING_DOUBLE**, and **REDWORK to RUNNING_SINGLE**.
- Genuinely distinct: SATIN, TATAMI, RUNNING_SINGLE/DOUBLE/TRIPLE, CONTOUR_FILL,
  SPIRAL_FILL, RADIAL_FILL, APPLIQUE.

One correction to the deck's framing, in our favour: it says "nothing surfaces it until
someone picks one". The shipped UI **never offered** the phantom types — the properties
panel lists only TATAMI / CONTOUR / SPIRAL / RADIAL / SATIN / APPLIQUE. The lie was in the
**public API and OpenAPI schema**, not the app. Still a lie, still fixed.

**Fixed in Part 43** — see `docs/benchmarks/v2-part43-audit.md`.

---

## Where the deck is right about our strengths

Confirmed as stated: 47 read / 19 write formats, browser-based, U2-Net segmentation with a
plausibility gate, cloud-native, open Python architecture.

## What the deck cannot see

The same blind spot as the previous critique: it is reasoning from architecture
descriptions, not from benchmark data. It misses that **nine corpus designs still digitize
to zero stitches** (R007) and that the **bead-chain ornament is dropped entirely** by the
speck filters (R008) — both content-loss defects that outrank most of its list.

## Net effect on the plan

The deck proposes a "Phase 2" starting with pull compensation and fabric profiles. **Both
are already built**, so that phase starts two items in. The ranked plan is unchanged:

1. ~~R001 split `digitizer.py`~~ — **done, Part 42**
2. ~~R002 phantom stitch types~~ — **done, Part 43**
3. ~~R003 commit the visual-regression harness~~ — **done, Part 44**; it immediately found a light-mode bug and a Part 41 content-loss regression
4. R004 stitch direction (49.9°) — the real #1
5. R005 fragmentation · 6. ~~R006 trims (837)~~ — **done, Part 48**: 844 → 663 on the panel, corpus-wide 33,969 → 27,927 (−17.8%) · 7. ~~R007 zero-stitch designs~~ — **done, Part 47**: 8 not 9, one is a blank fixture, the rest are correct sub-thread refusals; the real defect was 200-with-empty-design, now 422 · 8. R008 bead-chain · ~~**R011: the Part 41 substrate rule deletes white type on a white page**~~ — **done, Part 45**
