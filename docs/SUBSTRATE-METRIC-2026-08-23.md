# The substrate gate: is it the wrong number, or the wrong quantity?

**Ruling of 2026-08-23, executed. MECHANISM ONLY — no fix is written here**, which is the
ruling's own instruction and also the honest state: one prerequisite is missing and is named.

Every headline number carries the command and the JSON key that reproduce it.

---

## 0. LEAD WITH THE REFUTATIONS

**R1 — the ruling's falsifiable prediction is NOT borne out at the JND.** It predicted that if
Euclidean BGR under-states perceptual difference near black, it must over-state it near white
and in saturated colours, and therefore **delete** clusters a perceptual metric would keep.
Measured across 82 clusters in all sixteen fixtures: **zero flips in that direction.** Two
flips exist and both go the other way, and both are the same A02 cluster. Half the prediction
is refuted; the other half is **untested, not refuted** — see R2's limitation.

**R2 — dE76 is the wrong instrument for the saturated half, and this is stated before the
numbers rather than after.** CIEDE2000 is the metric that should ship and is **not computed
here**: writing forty lines of unverified colour-difference formula and putting a headline on
it is the failure mode this repository keeps paying for, and a verified implementation
(checked against Sharma et al.'s published pairs) is a prerequisite, not a detail. dE76 and
dE2000 agree closely for two NEAR-NEUTRAL colours, so the A02 case — the one that motivated
all of this — is well served. Saturated colours are exactly where dE76 is weakest.

**R3 — I named my own instrument's field wrongly, and caught it before it reached a report.**
The pipeline log recorded `deleted`. It is not: entering the substrate branch is not the end
of the decision, because flat artwork faces further tests inside it and can survive — fixture
02's `#fafafa` **page** cluster gates in while its white wordmark, whose deletion was a real
shipped defect, does not. Renamed `gated_in` through the pipeline, the constant and the
script, and **the whole survey was re-run** on the corrected tree rather than the numbers
relabelled.

**R4 — R5 is diagnosed, not merely re-measured, and the diagnosis strengthens the metric
argument instead of competing with it.** The mean-shift filter moved the cluster across the
BGR gate; in Lab it does not move it across the JND at all.

**R5 — P1's stated goal is NOT met, and the arithmetic says why.** Putting A01 through the
rebuild fidelity path was supposed to let a real fixture *hold* the run-object defect. It
exercises it and cannot assert on it: at the tightest band this repo uses, **2 of A01's 36
run objects are assertable**. A percentage band is the wrong instrument for a 5-penetration
object.

**R6 — my own `floor()` hypothesis is refuted, and so is the absolute-delta bound I proposed
in its place.** Added 2026-08-24 after running the test rather than naming it. The statistic
that would confirm a floor() flip — the fractional part of path length over step — **overlaps
between the two groups** (kept 0.033–0.663, lost 0.547–0.938). The real discriminator is
chord-versus-arc shortening of the *stored* path and it separates with **zero overlap**. And
because the loss is `k − (floor(L/step) + 2)`, it is **not bounded at 1**: the longest object
already loses 2. A `delta >= -1` bound would have been a number fitted to A01's short objects.
See §4.

**R7 — and my product framing was wrong too.** I was going to report that every traced line
erodes on every edit cycle. Measured across three generations: **215 → 193 → 193 → 193**, with
the stored path length constant at 202.219 mm. Rebuild regenerates stitches from the stored
contour without rewriting it, so the loss is a one-time deterministic gap, **not a ratchet**.

---

## 1. §6a, priced (P0)

    scripts/trace.py A02_real_neckline_black --key machine.minutes_net_of_trim   # 38.14
    4638 / SPM (800.0, run_quality_bench.py:52) = 5.7975

> **5.80 machine-minutes per garment sewing black thread onto black cloth**, on a design that
> takes 38.14 — **15 % of the run time.** Invisible thread, real thread cost, real needle
> wear, real machine time.

Never zero, at any parameter block measured:

| block | penetrations in cloth colour | share | **minutes** |
| --- | ---: | ---: | ---: |
| 130x180, 6 col (**the promoted block**) | 4,638 / 22,079 | 21.0 % | **5.80** |
| 130x180, 12 col | 4,500 / 21,932 | 20.5 % | 5.63 |
| 360x350, 12 col (**the corpus runner's own**) | 10,706 / 58,369 | 18.3 % | 13.38 |
| 100x100, 6 col | 1,179 / 8,519 | 13.8 % | 1.47 |

Landed on `SUBSTRATE_DELTA` in `constants.py`, beside the constant, not only in this file.

## 2. The metric survey (P0)

    scripts/measure_substrate_metric.py --sweep --json out.json
    keys: summary.lab_gates_in_more, summary.lab_gates_in_less, sweep[]

Read from `constants._SUBSTRATE_LOG`, written **at the decision site**. Deliberately not from
colour stops: a cluster gated in as substrate may never become a stop, so a stop-level survey
is structurally blind to the "BGR gates it in, dE would keep it" direction — exactly the half
of the prediction under test.

**82 clusters, 16 fixtures, 2 flips.**

| direction | clusters | px |
| --- | ---: | ---: |
| BGR keeps, dE76 says substrate | **2** | 68,903 |
| BGR says substrate, dE76 keeps | **0** | 0 |

Both flips are A02's `#080808`, in its two components (1,432 px and 67,471 px): BGR **13.856**
→ keep; dE76 **2.185** → substrate. sRGB(8,8,8) converts to `L* = 2.185, a* = 0, b* = 0`, so
the ruling's "L\* ≈ 2.2" is reproduced by the conversion rather than assumed.

### The threshold does not need fitting, and here is the evidence

Ranked by distance, there is **nothing between 13.856 and 26.439 in BGR**, and **nothing
between 2.185 and 7.407 in dE76**. The JND sits inside a **5.2-unit-wide plateau**, and the
sweep returns an identical answer at every threshold from 2.3 to 5.0:

| dE76 threshold | gates in MORE than BGR | gates in LESS |
| ---: | ---: | ---: |
| 1.0 | 0 | 1 |
| 1.5 | 0 | 1 |
| 2.0 | 0 | 0 |
| **2.3 (JND)** | **2** | **0** |
| 2.5 – 5.0 | 2 | 0 |

That is the opposite of a fitted number. **The caveat is real and belongs next to it:** the
plateau is a property of THESE SIXTEEN. Real artwork sitting 3–7 dE from the garment would
land inside it and the choice would start to matter.

### The nearest miss, which is the prediction's mechanism visible without a flip

`02_logo_fine_text_3color`'s `#fafafa` page against white: **BGR 8.660, dE76 1.892.** Both
metrics agree it is substrate, so it is not a flip — but BGR reports 4.6x the perceptual
figure. It only flips if the threshold drops to 1.5. Note which cluster this is: 02 is the
fixture whose white wordmark was once deleted wholesale by this rule. The wordmark is not what
gates in; the page is.

### What a single BGR constant actually means, perceptually

For the two clusters near the gate, the BGR-to-dE ratio differs: **6.34 near black**
(13.856 / 2.185), **4.58 near white** (8.660 / 1.892). So `SUBSTRATE_DELTA = 12.0` is
approximately dE 1.9 near black and dE 2.6 near white — **under the JND where it needs to be
strict and over it where it needs to be gentle.** Clusters far from the gate show ratios down
to ~2.0 (C24's `#460c20`), but those are far from the gate and extrapolating them to it would
be wrong; they are quoted only as evidence that the non-uniformity is larger over the full
space, not as evidence about where the gate belongs.

## 3. R5, diagnosed by ablation (P0)

The false claim: *"2,925 stitches (5.1 % of all sewing) went into near-black stops sitting
**10.5** from the substrate."* `2925 / 0.051 = 57,353` identifies the block as the corpus
runner's own (58,369 penetrations today, 1.7 % apart).

**Candidate tested, not argued:** the textured path's mean-shift filter (v2 Part 29) averages
each pixel with its neighbourhood, which should lift a near-black cluster off pure black. Run
with `cv2.pyrMeanShiftFiltering` made an identity:

| block | mean-shift | darkest cluster | BGR distance | gated in? | dE76 | objects |
| --- | --- | --- | ---: | --- | ---: | ---: |
| 360x350, 12 | **on** (today) | `#080708` | 13.304 | no — sewn | 2.050 | 834 |
| 360x350, 12 | off | `#040406` | **8.246** | **yes — deleted** | 1.666 | 1,786 |
| 130x180, 6 | **on** (today) | `#080808` | 13.856 | no — sewn | 2.185 | 306 |
| 130x180, 6 | off | `#040407` | **9.000** | **yes — deleted** | 1.389 | 414 |

**Diagnosed:** the rule was derived on an image that had not been mean-shifted, and smoothing
added afterwards moves the very cluster the rule exists to catch, in the one direction that
defeats it.

**Honest limit:** the ablation **brackets** 10.5 (8.2 filtered off, 13.3 on) rather than
reproducing it. Mean-shift accounts for crossing the gate; the residue belongs to other
movement since (palette planning, halo suppression, the 0.4/0.3 mm morphology) and is not
diagnosed here.

**And it argues the metric rather than the threshold.** Under the same ablation the perceptual
figure barely moves — 1.389 → 2.185, and 1.666 → 2.050 — staying under the JND on **both**
sides. BGR crosses the gate; dE does not. A perceptual metric is robust to the pipeline's own
preprocessing; a BGR constant is not, and nothing warned when the preprocessing landed.

The comment is replaced in `pipeline.py` with a pointer, and the full account — number, cause,
limit, and why the answer is the metric — now sits on `SUBSTRATE_DELTA` in `constants.py`,
where anyone about to change the number will read it.

## 4. A01 through the rebuild fidelity path — UNBANDED (P1)

    scripts/measure_rebuild_fidelity.py --json out.json     # A01, its own audit conditions

```
stream   5,776 -> 5,540   ratio 0.9591
objects  122 -> 122       set identical, no type changes
all              122 obj   4,805 -> 4,724 pen   exactly -1: 20   unchanged: 92
RUNNING_SINGLE    36 obj     215 ->   193 pen   exactly -1: 20   unchanged: 15
```

**Every "exactly −1" object in the design is a `RUNNING_SINGLE`** — 20 of 36, with 15
unchanged and one losing 2. Three SATIN objects lose 29, 21 and 18 penetrations (worst share
−24.0 %), which is the known satin-residual class rather than anything new.

**This is not `ce254a8` resurfacing.** That defect dropped a run object's first point and
would hit all 36 uniformly. The sizes refute a systematic cause too: lost-one objects are
5–10 penetrations (median 5), unchanged ones 4–9 (median 5) — fully overlapping.

### 4a. The `floor()` test, RUN (2026-08-24) — and it refutes the hypothesis it tested

The ruling required this before any bound was designed, and it was right to: the result
changes the answer.

**The hypothesis was wrong.** A floor() flip would show up in the fractional part of
length ÷ step. It does not separate the groups: kept **0.033–0.663**, lost **0.547–0.938**,
overlapping across 0.547–0.663.

**The mechanism is chord-versus-arc.** `_resample_open` walks the *arc length* of the traced
chain and emits a point every step — but the object stores the **chord polyline through those
samples**, which is shorter than the curve it came from. Rebuild can only see the chords, so
it resamples a shorter path. That predicts the rebuild count exactly:

    floor(L_chord_truncated / step_px_int) + 2   ==   actual rebuild penetrations   36 / 36

(The truncation is rebuild's own `to_px`, which is `int(...)`, not `round`. Using the
untruncated length predicts 35 of 36 — so both halves of the mechanism are load-bearing.)

And the shortening statistic separates perfectly, which the floor statistic did not:

| group | n | chord length vs the arc digitize walked |
| --- | ---: | --- |
| kept | 15 | −33.3 % … **−0.6 %** — all negative |
| lost 1 | 20 | **+2.0 %** … +13.9 % — all positive |
| lost 2 | 1 | +6.5 % |

**So the absolute-delta bound I proposed in §0-R5 is superseded.** The loss is
`k − (floor(L/step) + 2)`, which grows with accumulated shortening: seq 102 (17 points, the
longest and wiggliest) loses **2** at only 6.5 % shortening. `delta >= -1` would have been
fitted to A01's five-penetration objects and would fail on a longer traced line. Running the
test before designing the bound is the only reason that number is not now in the repository.

### 4b. It does not compound — three generations, measured

| generation | run objects | run penetrations | stored path | stream |
| --- | ---: | ---: | ---: | ---: |
| 0 (digitize) | 36 | **215** | 202.219 mm | 5,776 |
| 1 (rebuild) | 36 | **193** | 202.219 mm | 5,540 |
| 2 | 36 | 193 | 202.219 mm | 5,540 |
| 3 | 36 | 193 | 202.219 mm | 5,540 |

Rebuild regenerates stitches from the stored contour but does not rewrite it, so the chord
polyline is stable and the map is **idempotent after one application**.

**That yields the instrument the bound could not.** `rebuild(rebuild(d)) == rebuild(d)` is an
exact assertion needing no band and no fitted constant, and it is derived from this
measurement rather than chosen. It does not cover the digitize→rebuild gap, which is
representational: the stored contour is a lossy chord approximation of the traced curve, and
the honest fix is to store the arc or raise the sampling, not to widen a tolerance.

### 4c. The product reading, taken

**Twenty of A01's thirty-six traced lines are one stitch short in the rebuilt design, and one
is two short, at 1.4 mm pitch, on a real photograph.** That is a systematic shortfall at line
ends, exactly the class no numeric gate catches and the surface metrics would. It is bounded
and deterministic (§4b) rather than progressive — which lowers its severity without changing
that a customer who edits and rebuilds gets shorter lines than the design they approved.

**Why the P1 goal is not met.** The probe's assertability minimum is `min_pen =
max(2, round(1 / max_loss))`, derived from the band arithmetic itself:

| existing `max_loss` | `min_pen` | A01 run objects assertable |
| ---: | ---: | ---: |
| 0.10 | 10 | **2 of 36** |
| 0.13 | 8 | 4 of 36 |
| 0.21 | 5 | 33 of 36 |

A01's run objects carry 4–17 penetrations, median 5. **One penetration on a 5-penetration
object IS 20 %**, so any percentage band is either vacuous or knife-edge — a 0.21 band would
put 20 objects at exactly −20 % against a 21 % limit, which is a band fitted to this fixture.
**The right instrument for a 5-penetration object is an absolute delta bound, not a
percentage.** That is derived from the arithmetic, not from A01.

No band is added and no test is written; the observation is the deliverable, exactly as the
fixture-set enumeration of 2026-08-21 predicted it would have to be.

## 5. The intake spec gains its line (P1)

R2's structural finding — a photograph cannot reach `hairline_runs` at all — means promoting
more photographs will never exercise the hairline machinery, and the noise criterion deferred
on 2026-08-18 is deferred on a class that cannot reach the code.

`tests/fixtures/corpus_real/README.md` is new and is now the ask-list (it also makes that
deliberately-empty directory tracked). Section 2 is the added line: **at least one flat-lit
scan, not only photographs** — artwork scoring under `TEXTURE_SMOOTH_MIN` 6.0. "One such
input is worth more here than ten more photographs." `real_jobs.py`'s docstring points at it.

## 6. The TEXTURE_RETRY question, recorded where it will be read (P2)

Not answered here — the re-derivation is queued behind this — but written onto
`TEXTURE_RETRY_UNCOVERED` in `constants.py` so it cannot be missed when someone touches the
threshold:

> The retry is guarded on `not is_textured`, which is coherent — it rescues UNDETECTED
> texture. The consequence stands anyway: the three highest-uncovered fixtures in the set
> (A02 20.15 %, C24 17.75 %, A01 13.41 %) are precisely the ones it can never fire on. **The
> loss detector's only action is unavailable exactly where loss is greatest.** So the
> re-derivation must answer a second question beyond its threshold: what IS the response for a
> textured design at 20 % uncovered? Today it is nothing, and nothing is a choice that should
> be made deliberately rather than inherited from a guard clause.

## 7. What is deliberately NOT done

| item | state |
| --- | --- |
| any change to `SUBSTRATE_DELTA` or to the metric | **untouched** — mechanism first |
| CIEDE2000 | **untouched**, and it is the prerequisite: verify against Sharma et al. before any threshold moves |
| the saturated half of the prediction | **untested** — dE76 is weakest there; a null is not evidence of absence |
| the `floor()` hypothesis for A01's −1 objects | **measured-but-not-diagnosed** |
| an absolute-delta rebuild assertion for short run objects | **named, not written** |
| what moved the residue between 8.2 and 10.5 | **untouched** |
| branch coverage after the promotion | **untouched**, still owed from the last tranche |

## 7b. The near-white window is EMPTY, which converts the untested half into an ask

The ruling's sharpening, reproduced from the measurements: a flip in the predicted direction
needs BGR **under** 12.0 and dE **over** 2.3. At the measured near-white ratio (4.58, from
fixture 02's `#fafafa`: BGR 8.660 / dE76 1.892), BGR 12.0 corresponds to dE ≈ 2.6, so the
window is roughly **BGR 8.7 – 12.0**. Across all 82 clusters in the standing sixteen **nothing
falls in it** — the nearest point is that same `#fafafa` at 8.66, below the window.

The prediction was not merely untested; **no fixture we have could have tested it.** So it
becomes an intake ask rather than an open question, and it is now the second named line in
`tests/fixtures/corpus_real/README.md` §2b: **light-garment artwork with a near-white
element** — a white-on-white logo, a cream monogram on ivory, tone-on-tone lettering. Two
named inputs, each justified by a measurement rather than a preference.

## 7c. The metric argument now leads with invariance, not with the JND

Recorded on `SUBSTRATE_DELTA` in that order, because the ruling rated it the stronger form and
it explains R5 mechanically rather than re-measuring it:

> **A perceptual metric is invariant to the pipeline's own preprocessing; a BGR constant is
> not, and nothing warned when the preprocessing landed.**

Mean-shift off → BGR 8.2, gated in and deleted; on → BGR 13.3, sewn. Across the same change
dE76 moves 1.666 → 2.050 and stays under the JND on both sides. The gate's verdict flipped
because of *our* smoothing, not because the garment changed.

**The sRGB→Lab implementation is named**, since a Sharma et al. verification depends on which
one feeds it: OpenCV `cv2.cvtColor(..., COLOR_BGR2Lab)` on float32 in 0–1, giving true L* in
0–100. It returns **L\* = 2.185** for sRGB(8,8,8); the CIE formula by hand gives **2.193**. The
0.008 is immaterial inside a 5.2-wide plateau and is **not resolved here** — stated, not
picked.

## 8. Verification

**Base → Head: `444f623..9e62310`** (the instrument, the survey, the intake spec, the
standards rule). CI **run 31900577885** (`ci.yml` #129) — conclusion reported from the GitHub
API when it completes, not substituted from a local line.

Local lanes on `9e62310`, both run to completion before being reported:

| lane | result | exit | time |
| --- | --- | ---: | ---: |
| `pytest -q` | 1415 passed, 2 skipped, 2 deselected, 3 xfailed | 0 | 17:13 |
| `STITCHIQ_NO_REBUILD_PASSTHROUGH=1 pytest -q` | 1409 passed, 8 skipped, 2 deselected, 3 xfailed | 0 | 16:51 |

**The §4a/§4b/§7b/§7c material above is NOT in `9e62310`** — it is a later commit, and this
line exists because the previous pack asserted a repository state that was only true of my
working tree. Its Base → Head and CI run are reported when it lands.

## 8b. Process — the failure that produced this ruling

The previous pack was written, sent, and never pushed. `9e62310` sat local while the report
described it in the present tense, so §8's "the rule is now in ENGINEERING_STANDARDS §5,
binding" was false of the repository and every reproduction command in §1–§4 was unrunnable.
The missing Base → Head line, the missing CI section and the unverifiable commands were one
omission, not three.

The both-lanes rule from `ENGINEERING_STANDARDS.md` §5 was then broken on its first
application, by the instructed push that unblocked review. That is scoped explicitly rather
than left as a silent exception: **an instruction from review may unblock a push; a judgement
about risk may not.**

## 9. Process

The rule the ruling asked for is now in `docs/ENGINEERING_STANDARDS.md` §5, binding rather
than disclosed: **both lanes finish before the push.** It records why — three disclosed
pushes, each green, which is a pattern rather than an incident — and that disclosure was a
stopgap, not a substitute. This tranche follows it.

## 9. Standing

Nothing has been sewn. The intake spec is open, empty, and still the highest-value input on
the board — now with one more line in it, and with a reason for that line that is a
measurement rather than a preference.
