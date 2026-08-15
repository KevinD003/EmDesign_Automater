# The substrate gate, fixed — and the promotion's value, finally measured

**Ruling of 2026-08-25 executed: the tranche ends with a fix, not a prerequisite.**
Base → Head **`9e62310..0c5d70f`**, on `main`. Every headline carries the command that
reproduces it.

---

## 0. LEAD WITH THE REFUTATIONS

**R1 — the CIEDE2000 JND would have failed twice, and both of us had reasoned from it.**
The obvious threshold was CIEDE2000's unit JND. Measured: A02's `#080808` reads **1.263**, so
at 1.0 the defect is **not fixed**; and fixture 02's `#fafafa` page reads **1.092**, so at 1.0
it would newly be **kept** and 15,893 px of page sewn as artwork. The near-white regression
predicted two rulings ago appears at last — as a *cost* of the metric change.

**R2 — my "expect a point or two" prediction about branch coverage is refuted, badly.** One
message before measuring I said the promotion would move coverage barely and its value would
have to rest on what it found. Measured on one tree, fourteen against sixteen:
`planning.py` **+37**, `underlay.py` **+30**, `pipeline.py` **+9**, total **+7**. Two fixtures,
12.5 % of the set.

**R3 — the comparison the ruling asked for cannot be made, and saying so is the finding.**
"Branch coverage after the promotion" implies today's numbers against 2026-08-18's
(90 / 71 / 50). Those are **different trees** — RS1, the accounting split, DET2, the substrate
log and `colordiff` all changed the denominators. Reading 90 → 88 as a promotion effect is the
C11 two-tree splice that `coverage_audit._gate_comparison` now refuses outright. The
attributable comparison is fourteen vs sixteen on ONE tree, which is what R2 reports.

**R4 — my §4a mechanism survived the challenge, but the challenge was right about the code it
read.** `hairline_runs` does store the dense arc, exactly as the ruling said. A01 does not use
`hairline_runs`. Settled in `dc7f5f1`; summarised in §5.

**R5 — DET3 caught my refactor and the test was not edited.** A first draft hoisted
`declared_mask is None` into a `_gated` variable. Behaviour identical; but
`test_a_declaration_is_the_foreground_not_merely_an_exemption` pins that guard **at the
branch**, because this rule deletes artwork and a declaration must visibly exempt it there.
Lane 1 went red, the literal form was restored, and the assertion was left alone.

---

## 1. The fix

    scripts/measure_substrate_metric.py --sweep --json out.json
    scripts/trace.py A02_real_neckline_black --key machine.minutes_net_of_trim

`SUBSTRATE_DELTA = 12.0` (Euclidean BGR) → **`SUBSTRATE_DE2000 = 2.0`** (CIEDE2000), at both
decision sites: the substrate rule and the dark-linework suppression.

**The argument leads with invariance, not the threshold.** A perceptual metric is invariant to
the pipeline's own preprocessing; a BGR constant is not. Ablating the textured mean-shift moves
A02's cluster from BGR **8.2** (gated in, deleted) to **13.3** (sewn) — the verdict flipped
because of *our* smoothing — while dE2000 goes 1.67 → 2.05 and never crosses.

**Why 2.0 and not the JND.** Unit dE2000 is "a trained observer under controlled viewing can
just tell these apart". This rule asks whether **a customer looking at the garment sees thread
on cloth** — the "perceptible at a glance" level. Derived from the use, and after R1, a better
derivation than the JND was.

**The plateau, which makes the choice inside it inconsequential.** Ranked by dE2000:

| cluster | fixture | BGR | dE76 | **dE2000** |
| --- | --- | ---: | ---: | ---: |
| `#ffffff` ×3 | 04, 05, 06 | 0.000 | 0.000 | 0.000 |
| `#fafafa` (the page) | 02 | 8.660 | 1.892 | **1.092** |
| `#080808` ×2 (**the defect**) | A02 | 13.856 | 2.185 | **1.263** |
| `#f8f4e8` (real cream artwork) | 07 | 26.439 | 7.407 | **5.986** |

Every threshold in **[1.263, 5.986)** — width **4.723** — gives identical verdicts on all 82
clusters. 2.0 sits with 0.74 below and 3.99 above. **The caveat travels with the number:** that
plateau is a property of THESE SIXTEEN, which is why the intake spec asks for light-garment
artwork with a near-white element.

## 2. The verification, before anything depended on it

`app/services/digitizer/colordiff.py`, hand-written rather than imported: scikit-image ships
`deltaE_ciede2000` and IS importable here, but **nothing in `requirements*.txt` names it** and
this repository already declined that dependency once, for `ssim`.

`tests/test_colordiff.py` — **14 passed**:

* four Sharma, Wu & Dalal pairs asserted **directly**, chosen for the two traps every
  implementation gets wrong (zero chroma on one side; the h′ wrap and the R_T rotation);
* **1,200 random Lab pairs** across the whole gamut cross-checked against skimage, worst
  disagreement **< 1e-6** — random over the gamut on purpose, because a hue-rotation error
  shows up in saturated colours, the region dE76 could not speak to;
* symmetry and identity asserted rather than assumed.

**The chain, stated as what it is:** verified against an implementation that is itself verified
against Sharma upstream — not a first-hand Sharma verification, and not described as one.

**The conversion is named**, since a verification depends on it: `srgb_to_lab` uses the sRGB
transfer function and D65, matching OpenCV `COLOR_BGR2Lab` on float32. It gives L\* = 2.193 for
sRGB(8,8,8) where OpenCV's float32 path gives 2.185. Immaterial inside a 4.7-wide plateau,
recorded rather than resolved.

## 3. What the change does to all sixteen

**Exactly two cluster verdicts move, both A02's `#080808`.** Fifteen fixtures are
byte-identical — same audit rows, renders at **SSIM 1.000000**, stream locks untouched.

| | before | after | Δ |
| --- | ---: | ---: | ---: |
| A02 objects | 306 | 214 | −92 |
| A02 penetrations | 22,079 | 17,447 | **−4,632** |
| A02 trims | 253 | 180 | −73 |
| **A02 machine-minutes** | **38.14** | **29.31** | **−8.83** |
| A02 uncovered | 20.15 % | 23.98 % | +3.83 pp |

**8.83 minutes back per garment — 23 % of run time**, larger than the 5.80 headline because the
invisible regions carried trims as well as penetrations. The uncovered rise is honest rather
than a regression: the deleted regions now count as artwork nobody sewed, which is what they
are.

**The render was looked at.** Flower centres are bare cloth and the interstitial black
fragments are gone — how a black-on-black neckline is actually sewn. One caveat: this is
correct *given* the pipeline's belief that the garment is black, and that belief comes from the
image border, which is the inference DET3 exists to warn about.

## 4. Branch coverage after the promotion — owed three tranches, and worth the wait

    scripts/measure_branch_coverage.py                   # the sixteen
    scripts/measure_branch_coverage.py --exclude-a-tier  # the fourteen, SAME TREE
    (each under: coverage run --branch --source=app/services/digitizer)

| module | 14 fixtures | 16 fixtures | Δ |
| --- | ---: | ---: | ---: |
| `planning.py` | 48 % | **85 %** | **+37** |
| `underlay.py` | 55 % | **85 %** | **+30** |
| `pipeline.py` | 79 % | **88 %** | **+9** |
| `rebuild.py` | 74 % | 75 % | +1 |
| `geometry.py` | — | 69 % | — |
| **TOTAL** | **77 %** | **84 %** | **+7** |

**The promotion's value is now measured rather than asserted**, and it is much larger than I
predicted (R2). The mechanism: the photographs are the only inputs that take the textured path,
and the only ones exercising underlay recipes and palette planning at 122 and 306 objects
against the fourteen's 1–31.

**`rebuild.py` at +1 is the honest counterweight** — the promotion barely touched the rebuild
path, and `geometry.py` at 69 % is now the lowest-covered module in the package.

The instrument is landed (`scripts/measure_branch_coverage.py`) with the two-tree trap written
into its docstring, so the next re-measure is cheap and cannot be spliced.

## 5. §4a settled (`dc7f5f1`)

The ruling read `generation.py:356-360` and found `path_mm` iterating `pts_px`, the dense
skeleton — **correct**, and A01 does not use that function. A01 contributes zero sub-thread
regions, so `hairline_runs` never runs on it; its 36 run objects come from the dark-linework
pass, which stores `_resample_open`'s samples as the contour.

| | contour_pts == pen | mean spacing | round-trip lossless |
| --- | ---: | ---: | ---: |
| RS1 runs (04, 08, C24, C11) | 0 / 11 | 0.088–0.113 mm | **10 / 11** |
| linework runs (A01) | **36 / 36** | 1.09–1.27 mm | 15 / 36 |

`round()` for `int()` in `to_px` recovers **1 penetration of 22** — real, not the mechanism.
**Two run emitters with two storage conventions, neither docstring mentioning the other**, is
the finding.

## 6. Verification

| lane | result | exit | time |
| --- | --- | ---: | ---: |
| `pytest -q` | 1441 passed, 2 skipped, 2 deselected, 3 xfailed | 0 | 23:44 |
| `STITCHIQ_NO_REBUILD_PASSTHROUGH=1 pytest -q` | 1435 passed, 8 skipped, 2 deselected, 3 xfailed | 0 | 23:47 |

Both on the exact tree pushed, both after the DET3 fix; the earlier run that went red is
reported in R5 rather than discarded. CI **31900577885** (#129) on `9e62310`:
`conclusion: success`, from the API. CI **31908105848** (#130) on `0c5d70f`: `status: completed`,
**`conclusion: success`** — the run that carries the gate change itself. Both read from the
GitHub API, not substituted from a local line.

## 7. What is NOT done

| item | state |
| --- | --- |
| CIEDE2000 against Sharma **first-hand** | **untouched** — four pairs direct, the rest via skimage |
| the saturated half of the near-white prediction | **untestable on this corpus** — window BGR 8.7–12.0 is empty |
| the linework emitter storing its arc | **named, not written** — the candidate fix from §5 |
| `rebuild(rebuild(d)) == rebuild(d)` as a test | **named, not written** |
| what moved R5's residue between 8.2 and 10.5 | **untouched** |
| surface metrics, phantom fix, rebuild census, TEXTURE_RETRY's second question, SH2 | **queued** |

## 8. Standing

Nothing has been sewn. The intake spec has two named asks, each justified by a measurement —
a flat-lit scan under `TEXTURE_SMOOTH_MIN` 6.0, and light-garment artwork with a near-white
element — and it is still empty. The second ask now has a fix riding on it: the plateau that
makes 2.0 safe is a property of sixteen fixtures, and one real light-garment job would tell us
whether it holds.
