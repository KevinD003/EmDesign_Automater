# v2 Part 48 — R006: the gaps were long because the order was wrong

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** R006 — *"837 trims. Nearest-neighbour or TSP sequencing within each colour
layer, short-jump (<3mm) conversion to running stitches, and cross-colour optimisation."*

**844 → 663 trims (−21.4%)** and **36.20 m → 18.26 m of jump travel (−49.6%)** on the
reference panel, with coverage identical and every visual baseline still above the gate.

The brief's third lever was measured and dropped: only **2.6%** of trims spanned under 3mm,
so converting short jumps to running stitches would have touched 22 of 844.

---

## 1. What the 844 trims actually were

Measured before changing anything — the distribution of how far the needle jumps across
each trim on the panel:

| | value |
|---|---:|
| median gap | **27.05 mm** |
| p90 | 89.34 mm |
| max | 217.47 mm |
| under 3 mm | 22 (2.6%) |
| under 6 mm | 69 (9.2%) |

A 27mm median says the needle was crossing the design between neighbours. `findContours`
returns regions in raster scan order, so a colour's regions were sewn top-to-bottom
regardless of where the last one ended. Objects inside one colour stop can be sewn in any
order without adding a colour change, so that ordering was free to fix.

## 2. Two changes, and they do different things

This is the part worth reading, because the obvious attribution is wrong:

| configuration | trims | jump travel |
|---|---:|---:|
| raster order, always trim (before) | 844 | 36.20 m |
| raster order + 6mm gate | 775 (−8.2%) | 36.20 m |
| nearest-neighbour, always trim | **844** | 18.26 m (−49.6%) |
| **nearest-neighbour + 6mm gate** | **663 (−21.4%)** | **18.26 m (−49.6%)** |

**Reordering cannot remove a single trim on its own.** There is still one transition per
object, so the count is unchanged at 844 — it halves the distance instead. **The gate is
what removes trims**, and on its own it is worth only 8.2%. Together they give 21.4%,
because putting neighbours next to each other is what makes short gaps common: after
reordering, 28.6% of inter-object gaps fall under 6mm, against 9.2% before.

Reported this way because I nearly reported it the other way. The first sensitivity sweep
showed the gate having *no* effect at any threshold — which was the test being wrong, not
the code: `TRIM_MIN_GAP_MM` is imported by value, so patching it on `constants` never
reached the call site. That is the same live-binding trap Part 42 documented for
`_PENETRATION_FLOOR_MM`. Re-run against `pipeline`'s own binding, the sweep is real.

## 3. The threshold, and why it is not tuned to the target

| `TRIM_MIN_GAP_MM` | 0 | 3 | **6** | 10 | 15 |
|---|---:|---:|---:|---:|---:|
| trims | 844 | 813 | **663** | 485 | 485 |

**10mm would have hit the brief's target of "<586".** It is not taken. This digitizer
writes files for arbitrary machines, and a file that assumes an aggressive auto-trimmer
leaves a centimetre of loose thread on every machine that has none. 6mm is the conservative
end of the range commercial machines auto-trim at, and picking a looser default to land on
a target number would be choosing the number over the output. The curve is in the code
comment and in a test, so raising it later is a one-line change with its cost visible.

## 4. Scope — geometry is untouched

Routing changes the order regions are sewn in and how they are joined. It must not change
what gets sewn, and it does not:

| Fixture | trims | interior coverage |
|---|---|---|
| 01_flat_2color_logo | 85 → 85 | 100.0 → 100.0 |
| 07_circular_badge | 193 → 185 | 99.1 → 99.1 |
| 08_mascot_detail | 28 → 22 | 97.3 → 97.3 |
| 10_low_contrast_subject | 128 → 128 | 99.6 → 99.6 |

**Interior coverage is identical on every fixture.** All ten visual baselines stay above
the SSIM gate (lowest 0.998768), and object counts are unchanged.

**Across the whole 100-design corpus:**

| | before | after |
|---|---:|---:|
| trims | 33,969 | **27,927 (−17.8%)** |
| stitches | 2,573,251 | 2,534,859 (−1.5%) |
| interior coverage, median | 98.60 | **98.70** |
| zero-stitch designs | 8 | **7** |
| errors | 0 | 0 |

Coverage went *up* a tenth of a point rather than down, and one design that had produced
nothing now produces something — neither was aimed at, and neither is large enough to claim
as a result beyond "this did not cost quality".

The bench fixtures gain little — 539 → 528 overall, 2.0%. That is honest and expected: they
are small designs with few regions per colour, and the simulation said so in advance (the
badge had 0% headroom, the mascot 42%). The gain is concentrated in complex many-object
work, which is exactly where trims cost real money.

**Three of the four stream locks changed and were re-pinned.** This is a deliberate
behaviour change, not a refactor, so byte-identity was never the goal — the gates that
matter here are coverage and the visual baselines, and both held.

## 4a. A denial-of-service I introduced and had to bound

The ordering shipped without a size limit, and the full suite then **hung** on
`test_swarm_qa_fuzz_large.py::test_random_noise_palette_stress`. Nearest-neighbour is
O(n²) and its input is contours **before** the speck filter, so a pathological image sets
n far above anything a design reaches:

| input | contours in the busiest colour |
|---|---:|
| reference panel | **251** |
| 900×900 random noise | **70,516** |

70,516² in Python is hours. That is not a slow test — it is a request the public API accepts
and never returns from, and the fuzz suite exists to catch exactly this shape.

Bounded at `NN_MAX_REGIONS = 2000`, which is 8× above the real worst case and 35× below the
noise one, with a raster-order fallback above it — that being the order that shipped before
this part, so nothing gets worse than the status quo. The inner loop is also vectorised;
2000 points order in 0.09 s. Four tests pin the bound, the fallback, and the cost.

Worth recording plainly: the targeted tests, the stream locks, the visual baselines, the
100-design corpus and the frontend all passed before this surfaced. The full suite is what
caught it, and it caught it only because a fuzz test already existed for the case.

## 5. On the cited economics

At 2.5 s per trim, 181 fewer trims is about **7.5 minutes** of machine time per run of that
panel, not the 35 minutes the brief attributed to the whole 844 — that figure was the cost
of *all* trims, most of which are still needed because the regions are genuinely apart.
The travel saving is on top: 17.9 m less needle movement.

## 6. Tests — `tests/test_part48_trim_routing.py` (15)

- `_nearest_neighbour_order`: near-before-far, honours a start point, deterministic under
  ties, returns a permutation, handles empty/1/2-point inputs;
- reordering measurably shortens travel, checked against a raster-order control;
- no trim is ever emitted across a gap under the gate;
- **the regions themselves are untouched** — object count, colour stops and stitch count
  hold against a raster-order control;
- the gate stays in the conservative band, with the reason recorded;
- the ordering falls back past `NN_MAX_REGIONS`, still orders at it, leaves real
  designs well inside it, and costs under 3 s at a full cap.

## 6a. Verification

| Gate | Before | After |
|---|---|---|
| Backend suite | 834 passed, 2 xfailed | **849 passed, 2 xfailed** |
| Frontend tests | 131 passed | **131 passed** |
| `ruff check app` | 12 | **12** |
| Visual baselines | 10/10 | **10/10**, worst SSIM 0.998768 |
| Stitch stream locks | 4 pass | **4 pass**, three re-pinned deliberately |
| Corpus (100 designs) | 0 errors | **0 errors**, interior median 98.60 -> 98.70 |

## 7. What was not done

**Cross-colour optimisation.** Reordering *within* a colour is free; reordering *across*
colours changes the colour-stop sequence, which changes the thread-change order the
operator follows and can put a light colour under a dark one. That is a different change
with a different risk profile and it needs its own measurement.

**Exact TSP.** Greedy already takes travel from 36.20 m to 18.26 m. An optimal tour would
add a solver and non-determinism for a few percent more on a 771-object design.

## 8. Files

- `apps/backend/app/services/digitizer/routing.py` — `_nearest_neighbour_order`
- `apps/backend/app/services/digitizer/pipeline.py` — proximity order per colour stop; gap-gated trim
- `apps/backend/app/services/digitizer/constants.py` — `TRIM_MIN_GAP_MM`
- `apps/backend/tests/test_part48_trim_routing.py` — new
- `docs/benchmarks/v2-swarm/stitch-hashes.json` — three locks re-pinned

## 9. Also in this part — the R004 scoping brief

`docs/PROMPT-direction-field.md`, which the reviewer asked for. Five stages, each with its
own gate: the instrument first, then the field **visualised and consumed by nothing**, then
fills, then satin, then the user-facing control and the migration for designs that already
carry a `stitch_angle`. It also states in advance what would make the whole thing not worth
doing, so that answer stays available.

## 10. Next — R008, measured but not started

The bead-chain ornament. First measurement, so the scope is known rather than guessed: the
panel drops **768 specks**, median area **0.896 mm²** against the 2.0 mm² floor, and **766
of 768 are round**. That is the candidate set the bead chain lives in, and it confirms the
Part 40 diagnosis — a row of round beads is being filtered one bead at a time.

It is not simply a question of lowering the floor: most of those 768 are genuine noise, and
Part 36 measured that dropping the floor to 1.0 mm² "adds objects without recovering further
detail". The work is to recognise a *repeating row* of similar round regions as one element
and stitch it as a chain, which is a new generator rather than a tuning change. Starting it
clean is better than starting it here.
