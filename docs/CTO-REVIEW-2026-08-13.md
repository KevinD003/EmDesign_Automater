# CTO review pack — the INSTRUMENT tranche, 2026-08-13

**Repository:** `KevinD003/EmDesign_Automater`, branch `main`
**Base:** `98ef7d6` → **Head:** `fb79f7b`
**Four commits, 1,248 lines added, 1 deleted.**

This is the work done under the ruling of 2026-08-13, which put the INSTRUMENT tranche ahead of
SH2. It is written to be reviewed against the ruling item by item. Every number in it carries the
command that produces it and the key it is read from.

---

## 0. Verdict in one page

| ruling item | status | evidence |
| --- | --- | --- |
| **P0 DET2** — `emitted_mask` after pass B, with hole subtraction | **Landed** | `3e20a1f`. Prediction met: 03 rose 0.00 % → 13.32 %. Stop condition not triggered. |
| **P0 TRACE** — shipped script, one command + one key | **Landed** | `480b6c6`. `scripts/trace.py`, `docs/TRACE.md`. |
| **P1 INSTRUMENT-2** — the 90 penetrations, identity pinned | **Landed, premise corrected** | `1b9bb8f`. The 90 was not a count of penetrations. 56 assertions on 14 fixtures. |
| **P1 INSTRUMENT-1** — identify the flake, report the spread | **In progress** | Six hypotheses refuted. Four runs on `main` executing. One scope objection below, §5. |
| **P2 SH2 D1/D2** | **Not started**, correctly gated behind INSTRUMENT-1 | — |

**One self-inflicted failure, disclosed.** `1b9bb8f` was pushed before its lanes finished and
broke one test — the facade re-export guard. Both lanes returned exactly one failure, the same
one, and it is fixed in `fb79f7b`. Details in §6.

**Three of my own prior numbers are corrected in this tranche**, each with the mechanism:
the "90 unattributed penetrations" (§3), fixture 08's index-space gap of 79 (§2), and SH2's
"0 of 14 fixtures cross 0.19" (§1.5).

---

## 1. P0 DET2 — coverage counts thread, not intentions

**Commit `3e20a1f`.** `apps/backend/app/services/digitizer/pipeline.py`,
`apps/backend/scripts/coverage_audit.py`, `tests/test_det2_coverage_is_measured_after_sewing.py`,
`docs/DET2-COVERAGE-2026-08-13.md`.

### 1.1 The defect

`emitted_mask` is the only record of which artwork the pipeline believes it sewed. Two consumers
read it: `uncovered_px`, which gates the photographic-texture rescue and is the only automatic
detector of wholesale loss; and the element-level `lost_share` behind the user-facing
*"too small or too faint to sew"* warning.

The write sat in **pass A**, immediately after the minimum-area test:

```python
cv2.drawContours(emitted_mask, [contour], -1, 255, thickness=cv2.FILLED)
```

Pass A does not sew — it decides which regions are worth sewing. So the mask recorded an
*intention*, filled to the outer contour, and that stood in for an *outcome*. It over-counted:

1. **knocked-out hole interiors** — letter counters, donut holes, ring interiors that the fill
   explicitly does not cross;
2. **regions pass A accepted and pass B abandoned** — a feature thinner than the thread, a
   generator returning fewer than two points, an empty fill.

Both errors push the same way. A coverage metric that cannot go down is not a metric.

### 1.2 The fix

The pass-A write is deleted. The mask is written once, in pass B, after the object exists:

```python
objects[-1].params_hash = object_params_hash(objects[-1])
emitted_mask[region > 0] = 255
```

`region` is the mask the generators were handed — the smoothed contour minus every surviving
hole, plus any small hole the fill absorbed — so hole subtraction is a property of the thing
recorded, not a second step. `region` rather than `top_region`: pull compensation lays thread
outside the region by design, and crediting that would reintroduce the same optimism in a
smaller dose.

**Not counted, and named as such:** the dark-linework overlay, which emits objects after this
loop. Those are thin runs on top of fills that are already marked, so the residual is an
*under*-estimate of coverage — the safe direction for a loss detector. Fixing it means deciding
what footprint a 0.4 mm run claims, which is the physical-units question.

### 1.3 The falsifiable prediction

> *"03_gradient_soft_subject's pipeline-reported `uncovered_px` MUST RISE from 0.00 % toward the
> 11.96 % that SH2-FINDINGS measured independently."*

**0.00 % → 13.32 %.** Met. It sits 1.36 points above SH2's independent figure, which is the
expected direction: SH2 measured *unowned* foreground (`labels == -1`), this measures *unsewn*
foreground, and the two differ by the pixels smoothing and the width gate shave off every shape.

**Stop condition not triggered** — 03 did not stay at 0.00 %, and did not land below 2 %.

### 1.4 All fourteen fixtures

Ten bench fixtures plus the four corpus100 images SH2 measured, at SH2's configuration.

| fixture | conditions | before | after | delta | objects | stitches |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 01_flat_2color_logo | cotton @ 100×100 | 0.00 % | 0.34 % | +0.34 | 2 → 2 | 6,165 → 6,165 |
| 02_logo_fine_text_3color | cotton @ 130×180 | 0.11 % | 0.37 % | +0.26 | 16 → 16 | 8,437 → 8,437 |
| **03_gradient_soft_subject** | cotton @ 130×180 | **0.00 %** | **13.32 %** | **+13.32** | 4 → 4 | 8,399 → 8,399 |
| **04_thin_line_outline** | cotton @ 100×100 | **2.42 %** | **31.59 %** | **+29.17** | 10 → 10 | 1,855 → 1,855 |
| 05_wordmark_caps | cotton @ 130×180 | 0.95 % | 3.37 % | +2.42 | 6 → 6 | 1,802 → 1,802 |
| 06_wordmark_script | cotton @ 130×180 | 5.84 % | 9.46 % | +3.62 | 7 → 7 | 1,796 → 1,796 |
| 07_circular_badge | cotton @ 130×180 | 0.19 % | 3.33 % | +3.14 | 22 → 22 | 17,174 → 17,174 |
| 08_mascot_detail | cotton @ 130×180 | 0.66 % | 2.04 % | +1.38 | 20 → 20 | 8,024 → 8,024 |
| 09_nonuniform_background | cotton @ 130×180 | 0.00 % | 1.09 % | +1.09 | 2 → 2 | 3,090 → 3,090 |
| 10_low_contrast_subject | cotton @ 130×180 | 0.00 % | 0.66 % | +0.66 | 4 → 4 | 8,170 → 8,170 |
| C24_many_colours | cotton @ 130×180 | 12.53 % | 17.95 % | +5.42 | 26 → 26 | 19,784 → 19,784 |
| C11_many_colours | cotton @ 130×180 | 2.66 % | 6.94 % | +4.28 | 23 → 23 | 19,377 → 19,377 |
| C05_gradient_field | cotton @ 130×180 | 0.00 % | 0.10 % | +0.10 | 1 → 1 | 2,711 → 2,711 |
| C18_gradient_field | cotton @ 130×180 | 0.00 % | 0.10 % | +0.10 | 1 → 1 | 2,744 → 2,744 |

**Stitch and object counts are identical on all fourteen.** The change is diagnostic only — it
moves no thread. That is what separates "the metric was wrong" from "the pipeline was wrong."

**Every fixture moved up. None moved down.** That is what a one-directional over-count looks like
when it is removed, and it is the reason to distrust the direction of every coverage figure
quoted in this repo before this commit.

**Configuration note, which is itself a labelling correction.** The four corpus images run at
`max_colors=4` — SH2's setting, not `run_corpus100.py`'s `max_colors=12`. C24 reads **12.53 %** at
4 colours and **1.05 %** at 12. Taking the corpus runner's default would have silently replaced
SH2's baseline with a different measurement under the same name. Verified by reproducing SH2's
12.53 % and 2.66 % exactly before pinning the constant in the script.

### 1.5 What the honest mask surfaced

**04_thin_line_outline loses a fifth of the drawing.** The fixture is a wheel: thick outer ring,
thin inner ring, eight spokes, hub. The inner ring measures **0.21 mm** across — under
`MIN_FEATURE_W_MM` — so pass B correctly refuses it:

```
{'seq': 11, 'region_median_w_mm': 0.21, 'reason': 'sub_thread_feature', 'decision': 'SKIPPED'}
```

**55.9 mm², 9,936 px, 20.00 % of the owned foreground, one connected component, zero objects.**
Rasterising the emitted stitch path at a 0.4 mm thread width puts **35 px of thread inside it —
0.35 % of its area**. It is not partially sewn. It is not sewn.

Before this commit the pipeline reported 2.42 % uncovered and **emitted no warning at all**. It
now reports 31.59 % and emits *"About 20% of the artwork is too small or too faint to sew at this
size and was left out. A larger hoop keeps more detail."* — true, correctly worded for this
failure, and new. The refusal itself is right; 0.21 mm cannot be sewn with 40wt thread. What
changed is that the customer is told.

**A consequence flagged, not fixed.** At 31.59 % fixture 04 crosses `TEXTURE_RETRY_UNCOVERED`
(0.19) with a 55.9 mm² chunk, so the photographic rescue now fires there. It is rejected and the
returned design is unchanged; the cost is one wasted digitize.

> **Correction to SH2-FINDINGS.** It recorded *"0 of 14 fixtures cross 0.19"* under every rule
> variant. That was measured against the inflated mask and **is now false: 1 of 14 crosses.**

`TEXTURE_RETRY_UNCOVERED` is **deliberately untouched** in this commit, per the ruling's
separation requirement. Its comment cites a 0.228 worst case that no longer means what it meant.
The re-derivation now has what it needs: fourteen honest before/after figures and a shipped
script that regenerates them.

### 1.6 Tests

`tests/test_det2_coverage_is_measured_after_sewing.py`:

1. **Behavioural** — digitizing 04 at bench configuration produces the `sub_thread_feature` skip,
   `uncovered_px >= 0.10`, and the warning. Asserted against a **floor**, not the measured
   31.59 %, so it does not become a tripwire for smoothing changes it is not about.
2. **Structural** — parses `pipeline.py` and asserts every `emitted_mask` mutation inside
   `digitize_image` lies within pass B's loop. Deliberately an **AST property, not a string
   match**: this repo has already shipped one test that pinned a defect as contract by asserting
   on the literal source text of the line it guarded.

---

## 2. P0 TRACE — one command, one key

**Commit `480b6c6`.** `apps/backend/scripts/trace.py`, `docs/TRACE.md`.

```
cd apps/backend
.venv/bin/python scripts/trace.py 08_mascot_detail --key design.penetrations
.venv/bin/python scripts/trace.py --all --json trace.json
```

Each document carries the input's `sha256`, the conditions label, `code.head`, `code.dirty`, the
toolchain versions, both halves of machine time as well as the total, `coverage.uncovered_px`
read from the pipeline rather than recomputed, and the two index spaces. The fixture table, the
RNG seed and the machine model are **imported** from `run_quality_bench.py` and
`coverage_audit.py`, never retyped.

### 2.1 Index spaces, named and convertible

| space | counts | used by |
| --- | --- | --- |
| **stream index** | position in `design.stitches` — STITCH, JUMP, TRIM, COLOR_CHANGE | slicing the stitch list; `_lock_stream` inserts tie-offs here |
| **penetration index** | position among STITCH entries alone | `design.stitch_count`; machine-time estimate; what the needle does |

Measured at `3e20a1f`: `01_flat_2color_logo` 6,176 vs 6,165, gap **11**; `08_mascot_detail`
8,106 vs 8,024, gap **82**. `--stream-index` and `--penetration-index` convert and print the
entry; a non-STITCH entry is reported as having **no** penetration index rather than being given
one.

> **Correction.** An earlier report put 08's gap at **79**. That was correct *on the parity tree*,
> where 08 ran 8,091 penetrations; the parity fix moved it to 8,024 and the gap with it. Neither
> number was wrong — one was quoted without the tree it belonged to. Hence `code.head` in every
> document. This is the worked example in `docs/TRACE.md`.

### 2.2 The rule this establishes

**Every headline number in a StitchIQ report carries its command and its key. If it cannot, it
does not go in the report.** The three errors that motivated it — the "22.65 machine-minutes"
that was one fixture near the top of an 18.78–22.64 range, the jersey number reported as fleece
and then corrected with the wrong hoops, and the tie-off located at the wrong stream index — are
all the same error.

---

## 3. P1 INSTRUMENT-2 — the stream accounts for itself

**Commit `1b9bb8f`.** `pipeline.py`, `tests/test_stream_accounting.py`,
`docs/INSTRUMENT-2-STREAM-ACCOUNTING-2026-08-13.md`.

### 3.1 The premise was wrong, and that is the finding

> **The "90 unattributed penetrations" were never a count of penetrations.**

They came from `sum(object.stitch_count) − design.stitch_count`. That subtraction is malformed —
the operands are counted in different spaces:

| quantity | counts | fixed when |
| --- | --- | --- |
| `object.stitch_count` | `len(stitches) - obj_start` — a **stream span**, including the JUMPs and TRIMs inside the object | at emission, **before** `_lock_stream` |
| `design.stitch_count` | STITCH entries alone — a **penetration count** | after locking |

The difference folds three separate discrepancies into one figure and names it after one of them:
object spans contain non-penetrating entries (pushes it up), exclude every tie-off (pushes it
down), and entries belonging to no object at all are in neither operand.

On the current tree the same subtraction gives **94** on fixture 08. The actual lock-penetration
count is **162**. The old figure was not a poor estimate of the lock count; it was not an estimate
of it at all. Both original readings were exact — the arithmetic between them was not.

### 3.2 The identity, one space at a time

Censused at the three points where the stream is rewritten: before the same-hex merge, before
locking, after locking. Recorded, **not reconstructed** — a lock stitch is an ordinary `STITCH`
entry, and recognising one afterwards by its geometric signature is exactly the inference that
already located a tie-off at the wrong stream index.

**Stream space** — six named categories, nothing folded into "objects" to make it close:

```
stream_length == object_spans + stop_separators + linework_lead_in
               + end_markers + merge_inserted + lock_inserted
```

**Penetration space** — two sources, no third:

```
penetrations == penetrations_in_object_spans + lock_penetrations
```

**Fixture 08_mascot_detail [cotton @ 130×180]:**

```
8106 = 7930 + 3 + 0 + 1 + 0 + 172        difference from named: 0
8024 = 7862 + 162                        162 = 54 ties × 3
lock also inserted 10 TRIMs
```

`162 = 54 × 3` is `_tie_triangle`'s construction exactly — the check that the category is what it
claims to be rather than a residual with a label on it.

### 3.3 Two emission sites that had no name

Both found by writing the identity and watching it fail to close:

* **`_merge_adjacent_same_hex` inserts entries.** When it rewrites a `COLOR_CHANGE` into a `TRIM`
  it inserts a `JUMP` if the next entry is a `STITCH` — a repositioning the TRIM no longer
  implies. Zero on fixture 08, but not structurally zero, and nothing counted it.
* **The dark-linework pass sets `obj_start` after its lead-in.** The main loop sets it *before*
  its own TRIM and JUMP, so those land inside the span; the linework pass sets it *after*, so two
  entries per run fall outside every span.

### 3.4 A defect the identity caught the same hour

`_LAST_STREAM_ACCOUNTING` is module state and the photographic rescue calls `digitize_image`
recursively. The inner call overwrote the census, so a **rejected** retry left the module
describing a design nobody receives. It surfaced only because DET2 had just pushed fixture 04
over the 0.19 gate: the census read **1,179 penetrations** while the returned design had
**1,855**. Fixed by snapshotting and restoring across the retry, as `_LAST_UNCOVERED_PX`,
`_DROP_LOG` and `_CLASSIFICATION_LOG` already are.

**General rule now recorded: every module-level diagnostic must survive the retry branch or it
describes a design nobody receives.**

### 3.5 Tests

`tests/test_stream_accounting.py` — four identities × fourteen fixtures = **56 assertions**:

1. every stream entry belongs to exactly one named category;
2. every penetration is in an object span or a lock, and the lock count is a whole number of
   three-point ties;
3. the merge pass adds no penetrations;
4. stream length minus penetrations equals the number of non-STITCH entries — *exactly*, which is
   what makes the two spaces convertible rather than merely different.

Test 4 asserts the gap is **explained**, not that it is small.

### 3.6 Deliberate loose end

`trace.py`'s `accounting` block still reports `"unreconciled": true` — it carries the raw spans
without the census. Wiring it to `_LAST_STREAM_ACCOUNTING` is a one-line follow-up, left out so
the identity lands and is verified before the reporting surface depends on it.

---

## 4. P1 INSTRUMENT-1 — in progress

### 4.1 Six hypotheses refuted

| # | hypothesis | verdict | how |
| --- | --- | --- | --- |
| A | shared-file race between concurrent lanes | refuted | earlier session; atomic diff write landed anyway (`ccd45a3`) |
| B | CPU contention | refuted | earlier session |
| C | ONNX / rembg nondeterminism | refuted | earlier session; inference pinned anyway (`ccd45a3`) |
| D | pytest test-order randomisation | **refuted** | `pytest-randomly` is **not installed** — plugins are `pytest 9.1.1` and `pytest-cov 7.1.0`. Order is deterministic. |
| E | hash randomisation | **refuted** | `PYTHONHASHSEED` 0 / 1 / 12345 × 3 fixtures, byte-identical results |
| F | test-level RNG | **refuted** | every RNG in the suite is explicitly seeded; `timing`-marked tests are deselected by `addopts` |

Hypothesis D carries a caveat worth recording: an earlier targeted run of mine used
`-p no:randomly` as a control. Pytest silently accepts disabling a plugin that is not installed,
so **that flag was a no-op** and should not be quoted as evidence of anything.

Evidence for E:

```
PYTHONHASHSEED=0      08:8024/20/8106  07:17174/22/17290  02:8437/16/8484
PYTHONHASHSEED=1      identical
PYTHONHASHSEED=12345  identical
```

### 4.2 Spread observed so far

Two full runs, different lanes, same tree, **identical failure sets** (both `1 failed`, the same
test — §6). Four runs on `main` at `fb79f7b` (2 default, 2 no-rebuild) are executing now, each
capturing its full failure list.

### 4.3 The scope objection — please rule

**The SH2 tree no longer exists.** Rule A was written, measured and reverted; it was never
committed. My reconstruction of it produced **15 identical failures across four runs**, not the
16-and-17 that produced the original observation. That divergence is itself the finding: the
reconstruction is not the tree that flaked. Running it four more times measures the
reconstruction's spread.

Cost as literally specified — 4 runs × 2 trees × 2 lanes × ~25 min — is **~6.7 hours**.

**What I am doing unless redirected:** 8 full runs, ~3.3 hours — 4 on `main` (2 per lane) and 4 on
a freshly reconstructed rule-A tree (2 per lane), with failure sets **diffed pairwise** rather
than counted. That answers the question that actually gates SH2 — *does any test's pass/fail flip
between identical runs* — and gives the spread on the tree that will ship. It cannot reproduce
the original 17-vs-16, and I will not present it as if it had.

A cheap prior worth stating: `main`'s spread is trivially zero unless a test flips, because it has
no failures. The informative variance lives on a tree where tests already fail, which is why the
reconstruction is in the plan at all.

### 4.4 On the bound you invited me to show

You wrote: *"If you think the flake is bounded small enough that it cannot flip an SH2 decision,
show me the bound and I'll re-order."*

I have a partial one and it is **weaker than what you asked for**. Four runs on the reconstructed
rule-A tree gave byte-identical 15-failure sets; two clean-tree runs gave identical `1265 passed`.
Zero observed spread over six runs — which, if it held, would mean the flake cannot flip a
stitch-count decision. But it is not the measurement you specified: I never ran the SH2 tree and
`main` side by side across both lanes with failure-set diffs, and a zero spread over six runs
bounds nothing about the seventh.

**I am not asking you to re-order on it.** INSTRUMENT-1 stands as specified.

---

## 5. What is NOT done, and why

| item | state |
| --- | --- |
| `TEXTURE_RETRY_UNCOVERED` re-derivation | Deliberately excluded from `3e20a1f` per the separation requirement. Now unblocked — the fourteen honest figures exist. |
| SH2 D1 / D2 | Not started. Correctly gated behind INSTRUMENT-1. |
| A>cap veto, physical-units contract, 1c, 3e-i | Not started; behind SH2 in the ruling's order. |
| Real-job-pair intake | Built and **ready-and-empty**. `tests/fixtures/corpus_real/` is empty, so the hard stop is not triggered. |
| `trace.py accounting` → census | One-line follow-up, deliberately deferred (§3.6). |
| Dark-linework coverage | Named in the DET2 comment as an under-estimate; needs the physical-units decision. |
| Rebuild path accounting | `rebuild.py` also calls `_lock_stream` and has no census. Identity unverified there. |

---

## 6. The failure I shipped, disclosed

`1b9bb8f` was pushed **before its lanes finished**. It broke one test:

```
FAILED tests/test_digitizer_package_layering.py::test_facade_reexports_every_definition
E  defined but not re-exported by the facade: ['pipeline._stream_census']

default:    1 failed, 1322 passed, 2 skipped, 2 deselected, 3 xfailed
no-rebuild: 1 failed, 1316 passed, 8 skipped, 2 deselected, 3 xfailed
```

INSTRUMENT-2's census helper was reachable through `digitizer.pipeline` but not through
`digitizer` — precisely what that guard exists to catch, since it is how two callers end up
importing one function by two paths. Fixed in **`fb79f7b`**; the layering file passes 20/20.

`3e20a1f` and `480b6c6` were both verified green before pushing (default lane **1,267 passed,
exit 0**). The failure was in the third commit only.

Two process notes:

* I killed a no-rebuild lane at 90 % rather than report it, because I had edited `pipeline.py`
  during the run and two tests read source from disk via `inspect.getsource`. **A result I cannot
  fully attribute is not a result.**
* Total collected went 1,267 → 1,323. The +56 is the accounting assertions, which reconciles.

---

## 7. Reproducing everything in this document

```
cd apps/backend

# §1.4 — the coverage table
.venv/bin/python scripts/coverage_audit.py --json after.json
.venv/bin/python scripts/coverage_audit.py --compare before.json   # "before" from a worktree at 98ef7d6

# §2 — any headline number
.venv/bin/python scripts/trace.py 08_mascot_detail --key design.penetrations
.venv/bin/python scripts/trace.py 08_mascot_detail --key machine.minutes_net_of_trim
.venv/bin/python scripts/trace.py 08_mascot_detail --stream-index 8071

# §3 — the accounting identity
.venv/bin/python -m pytest -q tests/test_stream_accounting.py

# §1.6 — the DET2 pins
.venv/bin/python -m pytest -q tests/test_det2_coverage_is_measured_after_sewing.py

# both lanes
.venv/bin/python -m pytest -q tests/
STITCHIQ_NO_REBUILD_PASSTHROUGH=1 .venv/bin/python -m pytest -q tests/
```

| number | command | key |
| --- | --- | --- |
| 03 uncovered, after | `coverage_audit.py --json out.json` | `[fixture=03_gradient_soft_subject].uncovered_px` |
| 04 uncovered, after | same | `[fixture=04_thin_line_outline].uncovered_px` |
| 04's new warning | same | `[fixture=04_thin_line_outline].warnings` |
| 08 penetrations | `trace.py 08_mascot_detail` | `design.penetrations` |
| 08 index-space gap | same | `index_spaces.stream_minus_penetration` |
| machine minutes | same | `machine.minutes_net_of_trim` |
| tree the numbers came from | same | `code.head`, `code.dirty` |

---

## 8. Fixture limits — read before trusting any of the above

Fourteen synthetic images, all cotton, at two hoop sizes. **No photograph and no real artwork was
measured anywhere in this tranche.**

* The two fixtures carrying the largest DET2 corrections — 03's soft gradient and 04's hairlines —
  are exactly the classes where real exports differ most from synthetic ones. Real artwork carries
  anti-aliased edges at the widths `MIN_FEATURE_W_MM` sits among. The **direction** of the
  correction is not in doubt; its **magnitude on real artwork is unmeasured**.
* The stream-accounting identity is structural — arithmetic over the pipeline's own emission
  sites — so it should hold on any input. It is unverified on real artwork, on the rebuild path,
  and on designs that emit nothing (the tests skip those rather than assert about them).
* Hypothesis E was refuted on **three** fixtures at stitch-count granularity, not on all fourteen
  and not at stream-position granularity.

---

## 9. What I would like reviewed most

1. **§4.3** — the INSTRUMENT-1 scope call. Is 8 runs the right spend, given the SH2 tree is
   unrecoverable?
2. **§1.5** — is the fixture-04 warning the *right* outcome, or should a 0.21 mm feature under
   `MIN_FEATURE_W_MM` trigger something stronger than a warning? The refusal is correct; whether
   silence-turned-warning is a sufficient product response is a call above my level.
3. **§1.2** — `region` versus `top_region` for the coverage mask. I chose the conservative one.
   If pull-compensated thread should count as coverage, the numbers in §1.4 move down.
4. **§3.1** — I corrected a number that came from the ruling itself. If the "90" had a different
   derivation than the one I reconstructed, my correction is aimed at the wrong target and I would
   like to know.
