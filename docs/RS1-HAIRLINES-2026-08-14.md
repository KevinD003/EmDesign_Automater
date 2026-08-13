# RS1 — a hairline is not unsewable, it is uncolumnable

**Mechanism only. No fix in this change, and none in this session.**

Answering the ruling of 2026-08-14: `sub_thread_feature` refuses a region because it cannot carry
a satin column. `RUNNING_SINGLE` and `RUNNING_DOUBLE` are live `StitchType` members with
generators behind them. The question is whether the refused population could be run instead.

Three questions were asked. All three are answered below; one of them is answered "not measured",
and that is stated where it belongs rather than glossed.

Measured at `187f117`, cotton, each fixture at its bench hoop, `cv2.setRNGSeed(20260728)`.
Both probes are **read-only** — the classification log the pipeline already writes, and a list
subclass that captures the caller's `region` when an entry is refused. No pipeline edit, so
nothing here was measured on a tree that was being changed.

---

## 1. How many, and how wide?

`MIN_FEATURE_W_MM = 0.25`.

| fixture | regions | refused | refused widths (mm) |
| --- | ---: | ---: | --- |
| 01_flat_2color_logo | 2 | 0 | |
| 02_logo_fine_text_3color | 16 | 0 | |
| 03_gradient_soft_subject | 4 | 0 | |
| **04_thin_line_outline** | 11 | **1** | 0.21 |
| 05_wordmark_caps | 6 | 0 | |
| 06_wordmark_script | 7 | 0 | |
| 07_circular_badge | 23 | 1 | 0.20 |
| 08_mascot_detail | 21 | 1 | 0.20 |
| 09_nonuniform_background | 3 | 1 | 0.20 |
| 10_low_contrast_subject | 4 | 0 | |
| **C24_many_colours** | 31 | **5** | 0.23 ×5 |
| **C11_many_colours** | 28 | **5** | 0.23 ×5 |
| C05_gradient_field | 1 | 0 | |
| C18_gradient_field | 1 | 0 | |

**14 refused regions across 8 of the 14 fixtures — 8.9 % of all 158 regions.**

Width distribution of the refused population: **min 0.20, median 0.23, max 0.23.**
Histogram: `0.20 × 3, 0.21 × 1, 0.23 × 10`.

### The finding that matters

`MIN_FEATURE_W_MM`'s own comment records the two populations it was calibrated between:

> upscale phantom halos **0.15 mm**; fixture 04's REAL hairlines **0.30–0.33 mm** … 0.25 sits
> between the two measured populations

**Every refused region on these fourteen fixtures measures 0.20–0.23 mm.** Not one is at 0.15.
The gate is not currently separating halo from ink — the halo population does not appear in this
census at all. What it is separating is a band **80–92 % of the floor**, sitting between the two
calibration populations rather than at either of them.

That does not make the constant wrong. It makes the *refusal* wrong for this population: a
0.21 mm line cannot carry a satin column — a column narrower than the thread is not a column —
but 40wt thread is roughly 0.4 mm, so a single run **over-covers** a 0.21 mm line by about
two to one. Refusing it is the machine doing less than the person.

## 2. Does the skeleton already give a usable centreline?

**Yes, on every one of the fourteen. Thinning needs nothing it does not have.**

| fixture | w (mm) | area (mm²) | skeleton px | branches | centreline (mm) |
| --- | ---: | ---: | ---: | ---: | ---: |
| **04_thin_line_outline** | 0.21 | 44.6 | 1,750 | 2 | **153.5** |
| 07_circular_badge | 0.20 | 2.9 | 88 | 3 | 9.8 |
| 08_mascot_detail | 0.20 | 4.1 | 107 | 1 | 11.3 |
| 09_nonuniform_background | 0.20 | 3.4 | 138 | **17** | 14.0 |
| C24_many_colours ×4 | 0.23 | 2.8 | 224 | 1 | 25.1 |
| C24_many_colours | 0.23 | 9.3 | 728 | 1 | 81.9 |
| C11_many_colours | 0.23 | 9.2 | 728 | 4 | 81.5 |
| C11_many_colours ×4 | 0.23 | 2.8 | 224 | 1 | 25.1 |

Fixture 04's inner ring — the 55.9 mm² DET2 surfaced — thins to **1,750 skeleton pixels in 2
branches totalling 153.5 mm of centreline.** That is a clean, closed, run-ready path.

**The one case that would produce junk, and it must not be hidden in the average:**
`09_nonuniform_background` yields **17 branches over 14.0 mm** — about 0.8 mm per branch. That is
spur noise, not a line. So the viability test for this route is **not** "does a skeleton exist";
every refused region has one. It has to be a branch-structure test — a minimum branch length, or a
centreline-length-to-area ratio — and deriving one against 14 regions on synthetic fixtures is the
kind of second-threshold fitting that should not be done at the end of a session. Not attempted.

## 3. What would it cost?

Running every refused region as `RUNNING_SINGLE` at `RUN_PITCH_MM = 2.5`, plus two penetrations
per branch for entry and exit, no extra trims beyond one per region:

| fixture | penetrations | Δ | machine-minutes | Δ |
| --- | --- | ---: | --- | ---: |
| **04_thin_line_outline** | 1,855 → 1,920 | **+3.50 %** | 2.652 → 2.733 | **+0.081** |
| 07_circular_badge | 17,174 → 17,183 | +0.05 % | 22.634 → 22.645 | +0.011 |
| 08_mascot_detail | 8,024 → 8,030 | +0.07 % | 10.988 → 10.996 | +0.008 |
| 09_nonuniform_background | 3,090 → 3,129 | +1.26 % | 4.029 → 4.078 | +0.049 |
| C24_many_colours | 19,784 → 19,866 | +0.41 % | 25.730 → 25.832 | +0.102 |
| C11_many_colours | 19,377 → 19,465 | +0.45 % | 25.013 → 25.123 | +0.110 |

**The cost is negligible everywhere: at most +0.11 machine-minutes, and at most +3.50 % of
penetrations on the one fixture that is mostly hairlines.** 04 is the expensive case precisely
because the refused ring is a fifth of the drawing.

## 4. The rebuild fidelity band — NOT MEASURED

The ruling asked whether routing a refused region to `RUNNING_SINGLE` clears the 14 % band
(`tests/test_probes_three_paths.py`, max single-object loss). **I did not measure it, because
measuring it requires emitting the objects, and emitting the objects is the fix.**

What can be said without measuring, as an argument rather than a number:

* the digitize path **already emits `RUNNING_SINGLE` objects** — the dark-linework overlay does,
  storing the path as `contour` rather than an area;
* rebuild **already regenerates them**, at `rebuild.py:384`, via `_manual_run` along the stored
  open polyline;
* that pairing is already exercised by the existing fidelity probes.

So the machinery is end-to-end and the round trip is a re-run of a stored path, which is the
easiest case for fidelity there is. That is a reason to expect it to clear, **not evidence that it
does**, and it should be measured as the first step of the fix rather than assumed.

## 5. What a fix would have to decide

Listed so the next session starts from the questions, not from the design:

1. **The viability gate** (§2). Every refused region has a skeleton; not every skeleton is a line.
   Needs a branch-structure criterion, derived against more than 14 synthetic regions.
2. **Where the branch goes.** The refusal is a `continue` before `spine_satin` is called. A run
   route is a third outcome beside SATIN and TATAMI, and `_CLASSIFICATION_LOG`'s `decision` field
   currently admits three values.
3. **Pitch.** `RUN_PITCH_MM` is 2.5 (the pro default for a manual run); the dark-linework pass
   uses `OUTLINE_RUN_MM` 1.4 for traced lines. A refused hairline is closer to the second.
4. **Whether `MIN_FEATURE_W_MM` moves at all.** It probably should not. The floor is doing its job
   for satin; what changes is what happens *below* it.
5. **The warning.** *"About 20% of the artwork is too small or too faint to sew"* becomes false for
   any region that gets run instead, and must move with the behaviour.

## 6. Fixture limits

Fourteen synthetic images, cotton, two hoop sizes, 14 refused regions total — ten of which are the
same two generated shapes repeated across C24 and C11. The width band 0.20–0.23 is therefore
**four distinct shapes, not fourteen independent samples**, and real artwork with anti-aliased
edges is exactly where this population would look different. No photograph and no real artwork was
measured.

## 7. Reproducing

Both probes are read-only and live in the session scratchpad rather than the repo, because they
capture a private local through a list subclass — a legitimate way to measure without editing the
pipeline, and not a thing to ship. The census in §1 needs no probe at all:

```
cd apps/backend
.venv/bin/python - <<'PY'
import sys; sys.path[:0] = [".", "scripts"]
import cv2
from coverage_audit import fixtures
from run_quality_bench import RNG_SEED
from app.services.digitizer import digitize_image, pipeline
for name, path, p in fixtures():
    cv2.setRNGSeed(RNG_SEED)
    digitize_image(path.read_bytes(), fabric_type=p.get("fabric", "cotton"),
                   hoop_size=p["hoop"], max_colors=p["colors"],
                   text_mode=p.get("text", False))
    skipped = [e for e in pipeline._CLASSIFICATION_LOG if e["decision"] == "SKIPPED"]
    if skipped:
        print(name, [e["region_median_w_mm"] for e in skipped])
PY
```

---

## 8. ADDENDUM 2026-08-18 — the fix landed, and one prediction above was wrong

The fix shipped after this document's mechanism work, in the order the ruling set: the
entry-convention defect first (`ce254a8`, its own commit), then the emitter.

**§2's prediction about fixture 09 is corrected by measurement.** This document said 09's
17 branches over 14.0 mm were "spur noise, not a line" and would need a branch-structure
criterion to refuse. Wrong, in a useful direction: `_prune_spurs` at the repo's standing
`SPUR_MIN_MM = 0.8` noise floor — the gate's first step — eats the seventeen 0.8 mm hairs, and
what survives is **three real trunks of 1.4–2.9 mm**. They are sewable (each ≥ one pitch) and
they are sewn: three `Hairline` objects of 3–4 penetrations each. No branch-structure criterion
was ever needed; the repo already owned the noise definition, and deriving a second one would
have been the fitted constant §2 refused to fit.

Those three objects are also the ruling's **two-criteria disagreement, observed**: sewable but
far under any band's assertability minimum (penetrations ≥ 1/band = 10 for the 0.10 bands). Per
the ruling they are sewn and excluded from percentage assertions — the exclusion is implemented
in the band tests themselves with its derivation, and `test_rs1_hairline_runs.py` pins the
disagreement from both sides.

**The gate as shipped** (`generation.hairline_runs`): spur pruning at `SPUR_MIN_MM`, then branch
length ≥ one pitch — a running stitch exists between two penetrations, so a branch that cannot
hold two cannot hold a line. Both constants pre-existed or derive from definitions; nothing
fitted.

**Pitch, measured through the real path and chosen:** `HAIRLINE_RUN_PITCH_MM = OUTLINE_RUN_MM`
(1.4). Round-trip drift on 04's ring: +2.75 % at 1.4 mm (109→112), +3.17 % at 2.5 mm (63→65) —
pixel-grid requantisation, inside every band, not separating the pitches. The visual-class
argument decides: a hairline is a fine drawn stroke, the same class as traced linework, not a
user-drawn manual path. §3's constructed-probe claim of exact zero at 2.5 mm did not survive the
real path — the probe's mm-space resample was cleaner than rebuild's pixel grid, and the honest
numbers are the ones above.

**DET2's fourteen, before → after (the first coverage movement for a real reason):**
04 **31.59 % → 16.69 %** with its warning gone; 07 3.33 → 3.29; 08 2.04 → 1.92;
09 1.09 → 0.93 (and its colour warning honestly moves from "2 distinguishable" to "3" — the
hairline cluster now produces real objects); C24 17.95 → 17.75; C11 6.94 → 6.74; the other
eight unchanged. Object gains: 04 +1, 07 +2, 08 +1, 09 +3, C24 +5, C11 +8. 04's remaining
16.69 % is anti-alias fringe and edge shaving — honest, and back under the 0.19 texture-rescue
gate, so the rescue stops firing on a drawing **for the right reason** (input to the
TEXTURE_RETRY re-derivation, as the ruling anticipated).
