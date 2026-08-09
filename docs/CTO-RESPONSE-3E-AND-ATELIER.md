# Response to the two rulings of 2026-08-09

**STEP −1 → 3d approval and the B2 verification: received, thank you.**
Two items below. The first is a measurement disagreement I could not resolve on my own, so I
**stopped rather than build in the ruled direction**. The second is a process finding I accept in
part and correct in part.

---

## 1. STEP 3e — I cannot reproduce the numbers the ruling rests on

### What I measured

At the **canonical bench parameters** (`scripts/run_quality_bench.py :: FIXTURE_PARAMS` — the config
every other measurement in this series has used), digitize vs. forced regeneration. Coverage is the
share of object area (contours minus holes, rasterised at 6 px/mm) lying within 0.35 mm of a sewn
stitch segment.

| fixture | digitize st | regenerate st | ratio | machine-min d → r | coverage d / r |
|---|---:|---:|---:|---:|---|
| 01_flat_2color_logo | 8,963 | 8,993 | 1.00 | 13.95 → 13.99 | 100.0 / 100.0% |
| 02_logo_fine_text_3color | 9,982 | 10,719 | 1.07 | 12.77 → 13.90 | 100.0 / 100.0% |
| 03_gradient_soft_subject | 11,180 | 12,482 | 1.12 | 14.18 → 15.85 | 100.0 / 100.0% |
| 04_thin_line_outline | 1,861 | 1,869 | 1.00 | 2.66 → 2.67 | 100.0 / 100.0% |
| 05_wordmark_caps | 1,844 | 1,914 | 1.04 | 2.72 → 2.81 | 99.1 / 99.4% |
| 06_wordmark_script | 1,763 | 1,717 | 0.97 | 2.58 → 2.48 | 99.6 / 99.5% |
| **07_circular_badge** | **35,077** | **48,182** | **1.37** | **47.01 → 63.06** | 100.0 / 100.0% |
| 08_mascot_detail | 8,039 | 8,046 | 1.00 | 10.80 → 10.85 | 99.8 / 99.7% |
| 09_nonuniform_background | 4,029 | 4,198 | 1.04 | 5.08 → 5.33 | 100.0 / 100.0% |
| 10_low_contrast_subject | 14,852 | 15,331 | 1.03 | 18.65 → 19.33 | 100.0 / 100.0% |

### The contradiction, stated plainly

**Regeneration is more expensive than digitize on eight of ten fixtures.** On the badge it costs
**+13,105 stitches and +16.05 machine-minutes** — the opposite sign to the ruling, and roughly
three times the magnitude of the −6 minutes cited.

Coverage is 99.1–100% on **both** paths on **all ten** fixtures. There is no coverage difference to
trade against, in either direction.

### The configuration does not match either

|  | digitize | regenerated |
|---|---:|---:|
| Your badge figures | 15,703 st · 0.59% sub-0.3 mm · 63 trims · 20.96 min | 10,847 st · 0.50% · 53 trims · 14.83 min |
| Mine, bench params (4 colours, 130×180) | 35,077 st · 1.11% · 76 trims · 47.01 min | 48,182 st · 0.98% · 68 trims · 63.06 min |
| Mine, 6 colours, 100×100 | 10,806 st · 0.72% · 59 trims · 15.97 min | 11,141 st · 0.56% · 59 trims · 16.38 min |

Neither of my configurations produces 15,703 / 10,847, so **we are measuring different things**. I
would rather ask than guess which.

Worth noting: your acceptance target — *"badge digitize converges toward ~10.8k stitches at ≥99.4%
coverage and ≤15 machine-minutes"* — is **already met** by my 6-colour/100×100 run (10,806 st,
100.0% coverage, 15.97 min). That coincidence makes me more, not less, suspicious that the two of us
are looking at different runs.

### Why I stopped

3e as written closes the gap by moving digitize **down** to regeneration's behaviour. On my numbers
that would take the badge from 35,077 to 48,182 stitches — shipping a 16-minute-per-garment
regression. Your own instruction was to stop and report rather than re-pin if the measurements do
not support the change, so that is what I did. Nothing is in flight.

### What I did diagnose

The badge gap is **two objects, 95% of it**:

| seq | type | digitize | regenerate | delta |
|---|---|---:|---:|---:|
| 3 | SATIN | 12,354 | 21,215 | **+8,861** |
| 2 | CONTOUR_FILL | 12,386 | 15,962 | **+3,576** |
| 10 | TATAMI | 5,432 | 5,943 | +511 |
| 4 | SATIN | 1,952 | 2,166 | +214 |

For both large objects I checked and **ruled out** the obvious causes — they are identical across
the two paths:

- row/column pitch: 4 px on both (`source_mm_per_px` 0.0975, profile pitch 0.4 mm)
- stored density 2.5, pull compensation 0.2
- holes are present and stored (Satin 3 carries 3, Fill 2 carries 1)

The remaining suspect is that **the stored contour is a lossy polygon of the region digitize
actually swept** — Satin 3's contour is 1,080 points approximating a 3-holed ring band. A slightly
thicker or differently-shaped band yields materially more medial-axis columns. That is a model gap
rather than an argument mismatch, and it is not something 3e as specified would fix.

### What I need, and what I can do meanwhile

**Need:** the configuration behind 15,703 / 10,847 — colours, hoop, fabric, text mode. With it I can
either reproduce your result and proceed as ruled, or show precisely why the bench parameters
disagree.

**Can do now, direction-neutral:** the second half of your acceptance criterion — *ratio within 5%
on every bench fixture* — is a good target regardless of which way the gap closes. Eight of ten
already pass. Badge (1.37), 03 (1.12) and 02 (1.07) do not. On my measurements the supported
direction is bringing **regeneration down**, not digitize down. Say the word and I will take that.

**Also still true and unaffected:** the structural half of 3e — one shared emission core for fills
as well as satin, with classification staying in `pipeline.py` — is correct whichever way the
numbers move, because it removes the divergence *risk*. I have not started it, because doing so
while the target direction is unsettled risks encoding the wrong one.

---

## 2. Atelier P1/P2 — accepted in part, corrected in part

### Accepted

**The reporting failure is real and it is mine.** Atelier belonged in the execution report
regardless of scope, and it was not there. Fixed: it now has its own section listing both commits,
what each changed, and the gate results — in
`docs/CTO-VERDICT-EXECUTION-REPORT.md` and in the shared page at the same URL.

**The rule I am adopting:** every workstream gets a line in every report, whatever its scope, and
regardless of how low-risk I judge it. No exceptions for "it was only CSS".

### Corrected

**It was not undisclosed, and the distinction matters for how it is weighed against `250e850`.**
The owner directed it in writing:

> *"I have also updated the frontend so add that new frontend prepared by Claude Design and remove
> the old one."*

He then supplied the design handoff bundle (now committed at `docs/design/ATELIER-HANDOFF.md` with
its reference comp) and confirmed continuing to P2–P5. Each phase was reported to him as it landed.

`250e850` was different in kind: I shipped work that had been formally deferred, and said nothing.
Here the work was requested, and my failure was one of *report routing* — I scoped the CTO report to
the verdict and left owner-directed work out of it. Same corrective either way; different severity,
and I would rather be precise than accept a harsher characterisation than the record supports.

### Status

**P3–P5 are halted** pending the owner's confirmation, per your ruling. P1 and P2 are shipped and
have not been reverted — say if you want them backed out.

For the record, what they did:

| | |
|---|---|
| **P1** `56f5709` | Token layer, fonts, `data-theme` moved from `.dz-root` to `<html>`. Colour literals in `index.css` 74 → 8 by repointing token *definitions*, not editing consumers. Studio themable for the first time. Caught two latent breakages: a `.dz-root[data-theme='light']` block that could never match again, and a startup path that would have brought the Studio up light. |
| **P2** `ad76331` | ⌘K palette and mobile tab bar. Found a cascade bug in the *shipped design file* — the tab bar could never appear at any width, because its `display: none` sat after the media query setting `display: flex`. Verified with twelve browser checks. |

Both: tsc clean, vitest 186 passed, build clean. **No backend code touched by either.**

---

## 3. Noted for B2

Your three constraints are recorded and I will not start B2 until 3e is settled:

1. **Rotation must rotate `stitch_angle`** or the fill re-flows against the new geometry (+19.9%
   measured on fixture 01). Semantics to be decided and documented explicitly, not left implicit.
2. **Scaling must re-apply size-dependent rules** — density, pull compensation, satin width limits,
   the minimum-feature gate. The judgement a human digitizer re-makes on every resize.
3. **The transform probe goes into the bench**: for each of translate / scale / rotate, assert
   untouched objects change by 0.0% and coverage stays ≥99%.

On the last point — the STEP 3d pattern (the write path refuses a re-pin that fails its bands)
extends naturally here, and I intend to keep applying it: a gate that can be silently overridden is
not a gate.
