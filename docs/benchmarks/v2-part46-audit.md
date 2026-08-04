# v2 Part 46 — R004: five hypotheses for the 49.9°, four of them mine, all refuted

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** R004 — *"Stitch direction carries no information (49.9° median). No shape
analysis at all. The fix is shape-aware: PCA or minimum-area bounding rectangle per region,
angle perpendicular to the long axis for fills and to the centerline for satins."*

**Two of that brief's three premises are false, and the third survives every attempt I made
to explain it away.** This part does not ship a direction change. It establishes what the
number is and is not, fixes two real defects in the instrument that produced it, and says
plainly what the remaining work actually is.

---

## 1. "No shape analysis at all" — false, it shipped in Part 24

`_fill_angle` computes each region's principal axis from **central image moments**, and the
choice of moments over `minAreaRect` is deliberate and documented: a plus sign, a ring and
a star all share a square hull, so `minAreaRect` hands them an arbitrary angle while the
moment axis correctly reports them as isotropic and falls back to the default.

Measured across the ten bench fixtures — **41 distinct angles**, per-fixture standard
deviation up to **67.5°**:

| Fixture | objects | angle sd | sample of distinct angles |
|---|---:|---:|---|
| 07_circular_badge | 22 | 48.1 | −90, −87.4, −83, −75.1, −60.3, −49.4 |
| 09_nonuniform_background | 2 | 67.5 | −87, 48 |
| 08_mascot_detail | 20 | 45.3 | −90, −78.7, −78.4, −63.4, −46.2, −42 |
| 05_wordmark_caps | 6 | 1.4 | −90, −88.9, −86.3 |

Satin columns already run perpendicular to the medial axis by construction, and contour
fill already follows the outline. Items 1–3 of the brief are built. This is the third
consecutive part where the proposed fix was already shipped, and the reviewer has since
identified the cause on their side — tracking from conversation history rather than the repo.

## 2. "45° uniform fills" — false, and the real number is worse than that

The brief expects "uniform 45° fills regardless of shape". The actual distribution has 41
values. The problem is not that the angles are constant; it is that **the varied angles do
not agree with a professional's**.

## 3. The 49.9° — reproduced exactly, then attacked from four directions

Instrument validated first, as this repo requires: the self-test recovers stripes at known
angles to within **1.4°**. Reproduced: **mean 49.9°, median 54.1°, 33,837 segments**, where
45° is a coin flip.

Then four hypotheses, each cheap, each measured, **each refuted**:

**(a) A convention bug — a flipped perpendicular somewhere.** A mean *worse* than chance is
not what noise looks like, so I swept a global rotation applied to our directions:

| offset | 0° | 30° | 60° | 90° | 100° | 130° | 170° |
|---|---:|---:|---:|---:|---:|---:|---:|
| mean error | 49.48 | 48.73 | 44.27 | 40.52 | **40.04** | 42.60 | 48.59 |

A convention bug gives a deep minimum near 0 — say 10–15°. This is a shallow bowl bottoming
at 40° around a ~100° offset. There is a weak, roughly perpendicular bias, and no bug.

**(b) Fragmentation.** With a median of 19 stitches per object, a stub's principal axis
should be meaningless. If that were the cause, error would fall as objects grow. It does not:

| stitches/object | 0–10 | 10–25 | 25–50 | 50–100 | 100–250 | 250+ |
|---|---:|---:|---:|---:|---:|---:|
| mean error | 54.33 | 49.86 | 48.57 | 46.00 | 47.01 | **51.25** |
| segments | 137 | 4,616 | 2,421 | 3,701 | 4,968 | 19,070 |

The largest objects — carrying 55% of all segments — score **worse** than mid-size ones.
Flat, not a trend. **R005 will not fix the direction number.**

**(c) Satin-specific.** No: SATIN 49.7 over 30,216 segments, TATAMI 50.0 over 3,621.
Identical, and identically bad.

**(d) Misregistration — my strongest hypothesis, and the one I most expected to be right.**
The instrument's own registration check reports a mean per-stop colour distance of **35.9**,
and its single largest stop — 12,801 samples, 38% of everything scored — sits at **100.2**.
The script's docstring already says the comparison is meaningless for such points. So I
gated per segment on the source colour under each stitch matching the thread we laid there:

| colour gate | segments kept | mean error |
|---|---:|---:|
| none | 100% | 49.48 |
| ≤90 | 57.8% | 48.27 |
| ≤45 | 34.1% | 47.13 |
| ≤20 | 13.7% | **45.80** |

Keeping only the best-matched **13.7%** moves the number by 3.7°, to 45.8° — still a coin
flip. **Misregistration is ruled out.** The error is real and it is uniform.

## 4. Two real defects in the instrument, found by auditing it

**The per-type breakdown never worked.** It read `stitch_type.value`, but `Design` sets
`use_enum_values=True`, so the field is already a plain string and `getattr(..., "value",
"ALL")` returned the default for every object. Every run since it was written collapsed
into a single `ALL` bucket. Fixed — the breakdown in §3(c) is the first real one.

I should note this cuts against something I reported earlier in this session: a
satin-vs-tatami segment split of "30,332 vs 3,794". The corrected instrument gives 30,216
vs 3,621, so the shape of that claim held, but it was not produced by the code path I
believed it was.

**A bad score had no way to defend itself.** The registration check existed but was opt-in,
printed separately, and scored per colour stop rather than per segment. The score now
always reports the well-registered subset alongside the headline, so "the registration must
be off" is answered in the same output instead of being an untested excuse:

```
  mean |error|   49.9 deg
    SATIN            n= 30216 mean= 49.7
    TATAMI           n=  3621 mean= 50.0
  well-registered subset (source colour within 45 of our thread):
    33.6% of segments, mean 47.5 deg
```

## 5. What the remaining work actually is

Not PCA — that is built and it is at the ceiling of what per-region principal axes can give.
The error is uniform across size, across type, and across registration quality, which is
what you would expect if the *approach* is wrong rather than the *implementation*.

A professional does not choose direction from a region's principal axis. They choose it from
what the shape represents: petals radiate from a centre, a leaf follows its vein, lettering
follows the stroke. Neighbouring regions that belong to one visual element share a flow.
Our per-object independent axes cannot express that, however well each one is computed —
which is exactly the case `docs/PROMPT-graph-stitch-engine.md` already makes for a coherent
direction **field** over the design rather than an angle per object.

So R004 is not a day's work with a bounding rectangle, and the >0.7 shape correlation the
brief targets is not reachable by the route it proposes. That is worth knowing before
spending the week.

## 6. What shipped

- `scripts/measure_stitch_direction.py` — per-type breakdown fixed; per-segment registration
  gate added and always reported
- `tests/test_part46_direction_instrument.py` (4 tests) — pins the self-test, the type
  breakdown against the `.value` regression, the presence of the qualified subset, and that
  tightening the gate actually removes segments

No pipeline change, so **all four stream locks and all ten visual baselines are unchanged**.

## 7. Verification

| Gate | Before | After |
|---|---|---|
| Backend suite | 824 passed, 2 xfailed | **828 passed, 2 xfailed** |
| `ruff check app` | 12 | **12** |
| Stitch stream locks | 4 pass | **4 pass, unchanged** |
| Visual baselines | 10/10 SSIM 1.000000 | **10/10 SSIM 1.000000** |
| Instrument self-test | ≤1.4° | **≤1.4°** |

## 8. Next

The direction field from `PROMPT-graph-stitch-engine.md`, sized as its own multi-part piece
of work rather than a threshold change — with the Part 44 harness giving before/after
contact sheets across all ten fixtures, which is the visual proof the brief rightly asks for.

Cheaper items that are genuinely available in the meantime: **R007** (nine corpus designs
still produce zero stitches — content loss, and the same class of defect as R011),
**R006** (837 trims), **R008** (the bead-chain ornament).
