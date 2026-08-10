# P1 — the Zhang-Suen parity bug: fixed, and the no-axis arm split

**Your ruling accepted in full, and the premise I got wrong is retracted in place** — see the
retraction block now at the head of `docs/CTO-CLASSIFICATION-MECHANISM.md`. I asserted a population
of "letter-gap slivers that genuinely are satin" from a sector-median table without ever measuring
run lengths. Three judges measured them three ways and the population does not exist. My coverage
claim was worse: I reported 100% on an object shipping 6.96% bare fabric, because my metric
(0.35mm at 6px/mm) is too coarse to resolve a comb of radial slots.

This report covers **sequencing item 1 only**. The A>cap veto is item 2 and is not started.

---

## 1. The bug, and why the comment made it durable

`skeleton.py :: _thin_state` returned parity as:

```python
return win, padded, idx, ((row + col + y0 + x0) % 2).astype(np.uint8)
```

under a comment stating: *"Parity keys off ABSOLUTE (y + x), so the crop origin MUST be added back —
otherwise an odd-offset region thins differently from the same region uncropped."*

**The goal was right and the means were exactly backwards.** `_zhang_suen_thin` walks parities in a
fixed order (`for parity in (0, 1)`), so keying to absolute `(y + x)` means shifting a shape one
pixel swaps every pixel's checkerboard colour and reverses the erosion schedule.

The comment is why this survived: it reads as a considered decision with a stated reason, so anyone
looking at the line found an argument already made. The argument was false — **crop-relative parity
delivers both invariants**. `_fg_window` derives the crop from the foreground, so the same region
cropped or uncropped yields the same `(row, col)` for every pixel — exactly the property the absolute
term was reaching for — while a translation moves `y0`/`x0` and leaves `(row, col)` untouched.

Fix: drop the origin term. One line.

## 2. Measured, before and after

24 bars spanning the 4.5mm cap (2.0–5.0mm wide × 6–24mm long), each at four offsets, through
`spine_satin`:

| | bars changing `stitch_type` under a one-pixel shift |
|---|---:|
| before | **13 of 24** |
| after | **0 of 24** |

Every `median_w` is now identical across all four offsets to two decimal places. Before, the
shortest bars swung between **0.00mm and 2.86mm** — not a different axis but **no axis at all**,
sending the object down the no-axis arm.

The signature was diagnostic: `(0,0)` and `(+1,+1)` always agreed with each other, `(+1,0)` and
`(0,+1)` always agreed with each other. Nothing but a checkerboard produces that.

**One self-correction.** My first harness reported 1 of 24 surviving after the fix, on a `dy`-only
pattern that no parity effect can produce. It was the harness: 24mm bars are 319px, starting at y=100
on a 400px canvas, so they ran off the bottom and the shift changed how much was clipped. On a 700px
canvas it is 0 of 24. The test now asserts no bar is clipped rather than trusting the constant.

### Corpus effect — neutral, as a determinism fix should be

| | before | after |
|---|---:|---:|
| digitize stitches | 65,004 | 65,018 (+0.02%) |
| machine-minutes | 85.54 | 85.47 |
| coverage, all ten, both paths | 99.2–100% | 99.2–100% |

Per-fixture swings are ±2.7% in both directions and net to nothing. **This bought correctness, not
cost** — and I am not going to present it as a saving.

### The width survey re-run on the stable skeleton

You asked whether the four flagged objects change. **They do not.** All four remain SATIN with the
same `areaW/judged` ordering:

| fixture | seq | judged (was) | areaW | ratio |
|---|---:|---:|---:|---:|
| 08_mascot_detail | 2 | 3.00 (3.00) | 4.88 | 1.63× |
| 08_mascot_detail | 1 | 3.70 (3.70) | 5.61 | 1.52× |
| 03_gradient_soft_subject | 1 | **2.93** (3.12) | 4.06 | 1.39× |
| 07_circular_badge | 3 | 3.62 (3.62) | 4.92 | 1.36× |

Individual judged widths and branch counts moved a little (03 seq 2 went from 6 branches to 16), so
the fix is doing something — it just does not rescue any of the four. The A>cap veto still has the
same four targets.

## 3. The no-axis arm, split

`generation.py` had one arm for "no medial axis at all", labelled *"a freckle, a catchlight, a
punctuation dot"*, with **no size test**. It zeroes both `median_w` and the sample count, so every
width-based statistic — the classifier's median and any detector built on it — is structurally blind
to everything on it.

Now two reasons, decision unchanged (never satin, either way):

- `no_medial_axis` — under `NO_AXIS_SPECK_MM2`, a genuine speck
- `compact_no_axis` — over it, a shape whose medial axis honestly is a point, i.e. a disc

`NO_AXIS_SPECK_MM2 = 25.0`. Measured interval: the corpus's real specks are 2.6 and 5.2mm², the one
compact region is 168mm². 25 is roughly mid-gap on a log scale — chosen mid-interval rather than at
an edge, the same discipline you set for the veto threshold.

**09 seq 1 confirmed as your false alarm**, and it was my false alarm to raise: a 14.6mm disc sewing
correctly at 100% coverage, reported as an anomaly only because it shared a reason string with
punctuation dots. It now reads `compact_no_axis`.

**One trap caught while doing it.** `pipeline.py` excluded exactly `"no_medial_axis"` from its
tatami-FALLBACK counter. Splitting the arm would have started counting every disc as "satin was tried
and failed" — a silently corrupted diagnostic, in the same commit meant to make diagnostics
trustworthy. Both reasons now live in one shared `NO_AXIS_REASONS` tuple used by both modules. The
structural test that pins this **caught it**, and has been strengthened rather than relaxed: it now
asserts the exclusion goes through the tuple and that the literal comparison has not returned.

## 4. Gates

| | |
|---|---|
| New | `tests/test_skeleton_is_intrinsic.py` — 27 cases: all 24 shift combinations, raw-skeleton translation invariance, a behavioural guard that parity does not read the canvas, and **a test that crop-invariance is preserved** rather than traded away (the property the old comment wanted) |
| Strengthened | `test_the_reasons_are_the_ones_the_classifier_expects`, plus a new `test_a_disc_is_distinguished_from_a_speck` |
| Locks / baselines | re-pinned through the STEP 3d band gate |
| Lint | clean on every file touched |

## 5. Carried forward, unchanged

- **The dissent stays on the record.** A>cap separates perfectly on **N=4 positives over ten
  synthetic fixtures from one generator script**, and this corpus contains no legitimate wide satin
  by design. I will log the statistic for every object from day one so the margin is watched, and I
  will treat the first real-artwork wide satin as a test of the rule.
- **The knockout-policy finding is recorded and not acted on** — that 1.5mm gold lettering should be
  sewn on top of a solid band rather than knocked out of it, because ±0.3mm registration drift eats a
  1.5mm letter.
- **5c stays open.** The parity fix does not explain it and the veto will not either.

## 6. Next

Item 2: the area-over-cap veto, with **coverage as the acceptance criterion, not machine-minutes** —
corpus +7.5% and badge ~22.6 → 25.1 are expected and are the price. Landing with per-object
bare-fabric measurement as the evidence, human eyes on 03/07/08 before re-pinning, and a regression
asserting `A>cap == 0.000000` on the 13 known-good satins.

Then 3e-i, strictly after and not overlapping. Then 1c. B2 continues in parallel.
