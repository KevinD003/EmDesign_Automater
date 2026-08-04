# v2 Part 53 — neither. The reference cannot judge this question yet

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** decide by measurement whether the next field consumer should be
satin, tatami, or neither. Measurement only; no stitch-output change.

**Decision: neither, and the reason is not the one the brief anticipated.**

The brief asked whether satin's 0.15° aggregate was hiding a local win. It was
hiding something worse: **the 0.15° was never a measurement of satin.** And when
I built an instrument that does measure satin, it produced a spectacular apparent
win — **+16.98°** — which turned out to be the reference measuring the artwork's
outlines rather than its thread, on **77% of all satin segments**.

On the only satin the reference can actually resolve, **the field loses by 2.20°**.

No consumer is justified. The next R004 step is not a generator and not a
threshold — it is a reference photograph that can resolve thread on a 1.5 mm
column. Everything since Part 38 has been scored against one that cannot.

---

## 1. Two baselines, and Parts 50–52 used the wrong one for satin

Every field table since Part 50 compares candidates against
`per_object_field(o.stitch_angle)` — one angle per region.

For a **tatami** fill that is exactly right: the rows really are laid at one angle.

For a **satin** column it is not. `stitch_angle` is `cv2.minAreaRect(contour)[2]`,
a property of the bounding box, stored for the editor. What gets sewn is a column
swept perpendicular to the **medial axis**, changing direction along its length.
So "satin 37.90 today", the number that made satin's headroom look like 0.15°,
was scoring a quantity that is never sewn.

`scripts/measure_field_headroom.py` fixes that by comparing, **at the same
points**: the stitch segment's own direction, the field sampled there, and the
reference. Registration is the true uniform scale and is checked against the
pipeline's own seed before any score prints (IoU **0.872**).

Sanity check that the instrument is sound: over all 42,600 sewn segments it reads
**48.41°**, against Part 46's independently derived **49.9°**. Same quantity,
same ballpark, different code path.

## 2. The result that looked like a win

| territory | sewn | field | gain | n |
|---|---:|---:|---:|---:|
| all sewn segments | 48.41 | 31.58 | **+16.83** | 42,600 |
| satin | 48.26 | 31.28 | **+16.98** | 40,953 |
| tatami | 53.68 | 26.27 | **+27.41** | 4,624 |

A 17° gain would be the largest result in this entire line of work. Two things in
the same table said not to believe it.

**A constant beats what we sew.** Constant 90° scores **33.91** on satin and
**33.71** on tatami, against our sewn 48.26 and 53.68. Part 51 established that
any policy a constant matches is not evidence — and here a constant beats our
actual output by 14–20°.

**The width buckets reverse.** Thin columns show a huge field gain; the widest
show the field *losing*:

| satin column width | px wide | sewn | field | gain | n |
|---|---:|---:|---:|---:|---:|
| 0–1 mm | 2.7 | 47.36 | 31.55 | +15.81 | 2,245 |
| 1–2 mm | 8.1 | 50.18 | 27.09 | **+23.09** | 29,456 |
| **2–4 mm** | **13–19** | **42.34** | **44.54** | **−2.20** | **9,252** |

A real effect does not invert with the width of the thing it is measured on. An
instrument artifact does.

## 3. What the reference is actually reading

A structure tensor reports the dominant orientation **in its window**. On a satin
column narrower than that window, the strongest gradients are the column's own
two edges, so it reports the **column's axis** — which is perpendicular to the
thread lying there. A correctly sewn column then looks ~90° wrong, and a
contour-parallel field — which is exactly what `direction_field.solve` produces —
looks right.

Tested directly, by asking which the reference agrees with:

| satin column width | px | vs SEWN | vs AXIS | it is reading |
|---|---:|---:|---:|---|
| 0–1 mm | 2.7 | 47.36 | **42.64** | edges |
| 1–2 mm | 8.1 | 50.18 | **39.82** | edges |
| 2–3 mm | 13.4 | **42.40** | 47.60 | thread |
| 3–4 mm | 18.8 | **41.76** | 48.24 | thread |

The crossover sits where the geometry says it must, and **it is not the window's
fault** — the verdict holds at windows 5, 9, 15 and 21:

| window | satin 1–2 mm | | satin 2–4 mm | |
|---|---:|---:|---:|---:|
| | vs SEWN | vs AXIS | vs SEWN | vs AXIS |
| 5 | 50.13 | **39.87** | **42.60** | 47.40 |
| 9 | 50.18 | **39.82** | **42.34** | 47.66 |
| 15 | 51.47 | **38.53** | **42.16** | 47.84 |
| 21 | 51.88 | **38.12** | **42.28** | 47.72 |

The mechanism is pinned by tests on synthetic artwork with known truth — a band
full of horizontal threads reads as *vertical* when the window outgrows the band,
and as *horizontal* when it does not.

**The panel's scale makes this unavoidable.** At **0.186 mm per source pixel**, a
1.5 mm column is **8 px** and satin's ~0.4 mm thread pitch is **2.1 px** — at the
sampling limit. There is no window, and no field, that recovers thread direction
from 2 pixels per thread.

**Consequence for Q1:** the aggregate was not hiding a local win. Every satin
bucket that looks like a win — coherence, position along the column, curvature,
junction proximity — is dominated by the 77% of segments the reference cannot
resolve. Restricted to the 23% it can, the field is **2.20° worse** than what we
already sew.

## 4. Q2 — the tatami ceiling is not resolution-limited

| field solve | solve s | committed | field err | oracle |
|---|---:|---:|---:|---:|
| 384 px, 24 iters | 0.055 | 0.663 | 26.27 | 26.54 |
| 768 px, 24 iters | 0.119 | 0.611 | 23.77 | 26.54 |
| 768 px, 48 iters | 0.194 | 0.644 | 23.72 | 26.54 |
| 1152 px, 72 iters | 0.554 | 0.625 | 22.97 | 26.54 |

**Committed share does not improve — it drifts down, 0.663 → 0.625.** A finer
field does not make ring and border interiors more directional; the washout Part
50 measured is a property of boundary-seeded diffusion, not of resolution. The
apparent error improvement is the same circularity as §3: a finer field tracks
outlines more closely, and on thin tatami the reference *is* outlines.

The **oracle** column is the best score any one-angle-per-region policy could
achieve, chosen against the reference itself and therefore unreachable: **26.54**.
The 384 px field already sits at 26.27 — past it, because a field varies per pixel
while the oracle may not. So there is no headroom left for a smarter *angle
chooser*; only for a generator that varies direction within a region, which Part
51 already showed a scanline fill cannot do.

## 5. Cost gate

| input | 384/24 | 768/24 | 768/48 | 1152/72 |
|---|---:|---:|---:|---:|
| panel seed | 0.055 s | 0.119 | 0.194 | 0.554 |
| 900×900 noise | 0.463 s | 1.841 | 2.395 | 4.133 |
| 1500×1500 noise | 0.486 s | 1.908 | 2.428 | **6.519** |

Raising the working resolution **does** reintroduce growth on pathological input —
**13×** on the 1500 px noise case. The 384 px bound is doing real work, and since
§4 shows a finer field buys nothing trustworthy, there is no reason to pay it.

## 6. Decision table

| candidate | measured potential gain | runtime cost | structural blocker |
|---|---|---|---|
| **satin** | **−2.20°** (i.e. worse) on the only columns the reference resolves; the +16.98° aggregate is an instrument artifact over 77% of segments | none — field already solved | the reference cannot see thread on 1–2 mm columns, which is most of the design |
| **tatami** | none left for an angle chooser: the field (26.27) is already past the one-angle oracle (26.54) | none | Part 51's collapse ceiling — a scanline fill takes one angle; recovering more needs curved rows |
| **neither** | — | — | — |

**Neither is justified.** Not "not yet worth the effort" — *not measurable* with
the reference we have.

## 7. Gates

| Gate | Result |
|---|---|
| Decision gate | ✅ explicit: **neither** |
| Measurement gate | ✅ six bucketings, a width crossover, a four-window sweep, controls, an oracle bound |
| Cost gate | ✅ panel and two noise cases, §5 |
| Behaviour gate | ✅ **no file under `app/` changed**; 4 stream locks and 10 visual baselines pass |
| Backend suite | ✅ **888 passed, 2 xfailed** in 791.34 s (883 + 5 new) |
| `ruff check app` | ✅ 12, the standing baseline |
| No threshold tuned to produce a winner | ✅ the only threshold here (2 mm) comes from the reference's own resolution, and it produces a **loss** |

## 8. Files

- `apps/backend/scripts/measure_field_headroom.py` — segment-level instrument;
  sections `--validity`, `--resolution`, `--cost`
- `apps/backend/tests/test_part53_field_headroom.py` — 5 tests pinning the
  artifact on synthetic artwork with known truth, plus the oracle bound

## 9. What to do instead

**Get a reference that can resolve thread.** The panel is 0.186 mm/px; satin
thread pitch is ~0.4 mm. Two or three pixels per thread is not enough for a
structure tensor. A macro photograph at roughly **0.05 mm/px** — 3–4× the linear
resolution, or a close-up of one region rather than the whole panel — would put
~8 px on every thread and make the satin question answerable for the first time.
This is the cheapest unblocking step in the whole R004 line and it needs no code.

Two things worth stating plainly while that is outstanding:

- **The 49.9° headline is partly this artifact.** It has driven R004 since Part 38.
  On the columns the reference can resolve, our sewn error is **42.3°**, not 50°.
  Still poor, but the gap to a coin flip is smaller than the headline implies, and
  some of the remaining 50° is the instrument scoring correct satin as wrong.
- **Nothing built in Parts 50–52 is wasted.** The field, the instrument and the
  two-pass architecture all stand; Part 52's seed ranking used one registration
  and one territory definition throughout, so it is unaffected by §3. What changes
  is that the *consumer* question cannot be settled on this photograph.

If a better reference is not available, the honest fallback is to stop scoring
direction against this panel and judge R004 on a different axis entirely — a
sew-out comparison by eye, or a corpus-level structural metric — rather than
continue optimising against a number that rewards contour-parallel answers on
thin artwork.
