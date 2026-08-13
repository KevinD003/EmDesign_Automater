# CTO review pack — response to the ruling of 2026-08-14

**Repository:** `KevinD003/EmDesign_Automater`, branch `main`
**Base:** `f5ace88` → **Head:** `1cb48b7` · five commits

Written to be checked item by item against the ruling. Every number carries the command and key
that produce it. **"CI green" carries its run ID and its conclusion from the GitHub API**, per the
new report rule — no local pytest line is offered as evidence of a green suite anywhere in this
document.

---

## 0. Verdict

| ruling item | status | evidence |
| --- | --- | --- |
| **P0-A** CI red; track the four baselines | **Landed, CI-verified** | `2c6ac6e` → run **31662318585**, conclusion **success** |
| **P0-B** three identities cannot fail | **Landed, verified by injection** | `04e7cdc` |
| **P1** worksheet semantics / three `stitch_count` fields | **Landed** | `187f117`; fixture 08 gap −94 → **0** |
| **P1** INSTRUMENT-1 close-out | **Not done** | needs 4 runs on a tree I am not editing; see §5 |
| **P2** RS1 mechanism | **Landed, mechanism only** | `1cb48b7` |
| **P2** `TEXTURE_RETRY_UNCOVERED` | **Not started** | §7 |
| **P3** SH2 D1/D2 | Not started, correctly gated | — |

You were right on all four things I did not report. Three were the same failure the tranche was
built to prevent, and I am not going to argue with any of them.

---

## 1. P0-A — CI was red, and my "fix" had not fixed it

### What I got wrong

My §6 last time quoted `1 failed, 1322 passed` as the failure, said `fb79f7b` fixed it, and moved
on. From the API:

| run | commit | conclusion |
| --- | --- | --- |
| 31658135314 | `480b6c6` (TRACE) | **success** — last green before the break |
| 31658769064 | `1b9bb8f` (INSTRUMENT-2) | **failure** — 1 failed + **16 errors** |
| 31661244629 | `fb79f7b` (my "fix") | **failure** — still red |
| 31661533667 | `f5ace88` (docs only) | **failure** — still red |
| **31662318585** | **`2c6ac6e`** | **success** |

`fb79f7b` addressed the 1 failure and never touched the 16 errors. I reported a fix I had not
verified at the surface that reported the break. The local suite read green because
`build_corpus100.py` had been run on this machine — **a green suite measured under a condition it
did not state**, which is exactly the failure mode TRACE exists for. The rule binds on "the suite
passed" as much as on a stitch count.

### The fix

`.gitignore` keeps excluding the generated corpus and now un-ignores four files, with the reason in
the file: the stated justification — *generated, regenerated with a fixed seed* — is right for a
**corpus** and wrong for a **baseline**. These four are cited by name in DET2's table, carry SH2's
12.53 % / 2.66 % reference figures, and C24 is the fixture the D1/D2 decision turns on.

**179 KB total, not the ~1 MB estimated:**

| file | bytes | sha256 (first 16) |
| --- | ---: | --- |
| C05_gradient_field.png | 53,988 | `0b485f5b49b55b34` |
| C11_many_colours.png | 23,952 | `5f28c0da66bb6599` |
| C18_gradient_field.png | 76,698 | `130bab06c7a69969` |
| C24_many_colours.png | 24,237 | `5effb8a85b574b86` |

`tests/test_corpus_baseline_fixtures.py` pins all four. Its failure message says to **re-measure
the DET2 and SH2 tables and update the hash in the same commit** — explicitly not to update the
hash alone.

**I am not arguing for CI generating the corpus.** A baseline that regenerates is not a baseline,
and I have no byte-stability evidence to put against that.

### So the class cannot recur

* A missing fixture now **skips with the path in the message**. Sixteen per-case `FileNotFoundError`
  errors buried the one real failure under a wall of tracebacks.
* `test_all_fourteen_fixtures_are_present` asserts the fourteen exist. A skip is not a failure, so
  without it the suite can shrink to ten and report exactly as green. **The skip above is only safe
  because that test exists**, and the skip's own comment says so.
* A guard on the guard: `CORPUS_EXTRA` and the hash table must agree, so a fifth baseline cannot be
  added that passes locally and errors in CI.

---

## 2. P0-B — three of four identities could not say no

Reproduced by injection rather than by reading. My own words from DENSITY-LOCK-SITE apply: *a check
that cannot say no is worse than no check, because it reads in the diff as a safety assertion.*

### Confirmed mechanisms

* `penetrations_in_object_spans` was **defined as** `pre_lock["STITCH"]`, so the decomposition
  asserted `x == x` and never saw the merge pass.
* `lock_penetrations` is **defined as** `post − pre`, so that half is algebra.
* `_stream_census` used `out.get(key, 0) + 1`, admitting any command and therefore always summing
  to `len(stitches)`.

### The four changes

1. **`penetrations_in_object_spans` is measured**, accumulated as each span is emitted by counting
   STITCH entries from `obj_start`. The name now asserts a property something checks.
   `penetrations_pre_lock` is kept separately, labelled as what it is.
2. **`census_pre_merge` is stored**, and the merge claim is asserted across the merge — the only
   span in which it has content.
3. **`_stream_census` counts against a closed `_STREAM_COMMANDS` tuple**, with anything else in a
   named `other` bucket listed in `other_commands`. Counted, not rejected — raising inside
   `digitize_image` turns a new command type into a production outage instead of a red test — and
   `other == 0` is asserted at all three census points.
4. **Every identity's docstring names the input that falsifies it.** One that cannot name one does
   not belong in the file.

### Verified by injection

Patching the merge pass to append a real `STITCH`:

```
before   all three passed
after    "the merge adds no penetrations"  FAILS
         "penetrations decompose"          FAILS
```

### The limit I have to state rather than let you infer

**Identity 1 still cannot police the merge or lock passes.** `merge_inserted` and `lock_inserted`
are measured deltas (`len` after minus `len` before), so it absorbs whatever those passes insert —
the injected merge STITCH does **not** break it. That is now written in its own docstring. Its live
domain is the emission sites in the main loop and the dark-linework pass, which is where it earned
its place by finding two of them.

So the honest count is: **six identities × fourteen fixtures**, of which identity 1 is live over two
emission sites and the other five are live end to end. Not "84 assertions" as a headline.

---

## 3. P1 — the defect that produced the "90" was still shipping

### What the operator saw

`worksheet_pdf.py:51` printed each colour row's **stream span** in a column labelled *stitch count*,
beside a thread length, under a header computed from `design.stitch_count` — the other space.

```
08_mascot_detail [cotton @ 130x180], before
  header (design.stitch_count)   8024
  rows   (sum of stop spans)     7930
  GAP                             -94    (-1.17 %)
```

Three fields named `stitch_count`, two counting stream entries and one counting penetrations.

### Semantics, not arithmetic

`ColorStop` and `DesignObject` now carry:

* **`penetration_count`** — needle penetrations. What an operator means by "stitches", what the
  machine-time estimate divides.
* **`stream_span`** — entries attributed to the row, jumps and trims included. Diagnostic.

Neither is called `stitch_count`. **`Design.stitch_count` keeps its name**: it was already
penetrations, and renaming the correct field to match two incorrect ones is the wrong direction.

### Closing the gap honestly

Colour-stop counts are recomputed **from the final stream**, partitioned on its `COLOR_CHANGE`
entries, so the **162 tie-offs** the lock pass adds belong to the thread that sewed them instead of
to nobody. That is what closes the gap; fixing the arithmetic alone would not have.

```
08_mascot_detail, after
  header 8024   rows 8024   gap 0
  stop stream_spans sum to 8106 == len(design.stitches)
```

Verified the same way on 07 (17,174) and 01 (6,165), and asserted on all fourteen.

Object spans stay pre-lock — their boundaries do not survive locking, by design — so the object
identity remains `sum(penetration_count) + lock == design.stitch_count`.

**A case that is recorded rather than papered over:** when the stream's colour partition does not
match the stop count — a `COLOR_CHANGE` emitted for a stop that produced nothing, which the
dark-linework pass can do when its chains are dropped as garment-coloured — the counts are left
alone and `stops_partition_matches` goes false. Zipping the shorter list would misattribute every
stop after it. A separate assertion names that case so the two failures stay distinguishable.

### Moved together, as required

| site | change |
| --- | --- |
| `routing.py:121` merge | sums **both** spaces |
| `rebuild.py:540,564` | builds both on the rebuild path |
| `embroidery_io.py` importer | sets both; an imported block is needle positions, so its length is the penetration count |
| `supabase_store.py` | persists penetrations into the existing column, which already meant penetrations at design level |
| `package.py`, `worksheet_pdf.py` | print penetrations |
| frontend `design.ts` + 2 components | `penetrationCount`; `streamSpan` optional, nothing in the UI reads it |

Frontend: **tsc clean, 186 vitest tests pass**, and CI's frontend job was green on the run that
carried the earlier half of this work.

### Two new identities, all fourteen fixtures

1. worksheet rows sum to the header;
2. stop stream spans partition the whole stream.

### Still open, stated rather than implied

**`rebuild.py` calls `_lock_stream` and has no census**, so none of these identities is verified on
the rebuild path. Deferred, not done. Same answer to your explicit question: it does **not** land
here.

---

## 4. P2 RS1 — a hairline is not unsewable, it is uncolumnable

Mechanism only, no fix, no fix in this session. Full detail in
`docs/RS1-HAIRLINES-2026-08-14.md`.

### How many, and how wide

**14 refused regions across 8 of the 14 fixtures — 8.9 % of all 158 regions.**
Widths: **min 0.20, median 0.23, max 0.23.** Histogram `0.20×3, 0.21×1, 0.23×10`.

`MIN_FEATURE_W_MM = 0.25`, and its own comment records the two populations it sits between:
phantom halos at **0.15**, fixture 04's real hairlines at **0.30–0.33**.

**Not one refused region is at 0.15.** The gate is not separating halo from ink on these fixtures —
it is refusing a band at **80–92 % of the floor**. That does not make the constant wrong; it makes
the *refusal* wrong for this population. A 0.21 mm line cannot carry a satin column — a column
narrower than the thread is not a column — but 40wt thread is ~0.4 mm, so a single run
**over-covers** it about two to one.

### Does the skeleton already give a centreline

**Yes, on every one of the fourteen.** 88 to 1,750 skeleton pixels. Fixture 04's inner ring — the
55.9 mm² DET2 surfaced — thins to **1,750 px in 2 branches totalling 153.5 mm** of clean,
run-ready centreline. Thinning needs nothing it does not have.

**The one case that would produce junk, named rather than averaged away:**
`09_nonuniform_background` yields **17 branches over 14.0 mm** — 0.8 mm each. Spur noise, not a
line. So the viability test cannot be "does a skeleton exist"; all of them do. It needs a
branch-structure criterion, and fitting one against 14 synthetic regions at the end of a session is
how a constant gets tuned to noise. **Not attempted.**

### Cost

| fixture | penetrations | Δ | machine-min | Δ |
| --- | --- | ---: | --- | ---: |
| 04_thin_line_outline | 1,855 → 1,920 | **+3.50 %** | 2.652 → 2.733 | **+0.081** |
| 09_nonuniform_background | 3,090 → 3,129 | +1.26 % | 4.029 → 4.078 | +0.049 |
| C11_many_colours | 19,377 → 19,465 | +0.45 % | 25.013 → 25.123 | +0.110 |
| C24_many_colours | 19,784 → 19,866 | +0.41 % | 25.730 → 25.832 | +0.102 |
| 08_mascot_detail | 8,024 → 8,030 | +0.07 % | 10.988 → 10.996 | +0.008 |
| 07_circular_badge | 17,174 → 17,183 | +0.05 % | 22.634 → 22.645 | +0.011 |

**At most +0.11 machine-minutes anywhere.** 04 is the expensive case because the refused ring is a
fifth of the drawing.

### The band — NOT MEASURED

Measuring it means emitting the objects, and emitting the objects is the fix. What is known:
the digitize path **already emits `RUNNING_SINGLE`** (the dark-linework overlay, path stored as
`contour`), and **`rebuild.py:384` already regenerates it** through `_manual_run`. The round trip is
a re-run of a stored path — the easiest fidelity case there is. **That is a reason to expect it
clears, not evidence that it does**, and it should be the first step of the fix.

---

## 5. P1 INSTRUMENT-1 — and hypothesis G demonstrated itself

**Accepted in full. G is better than any of my six** and I would not have found it, because it
lives in my own process rather than in the code.

Then it happened again, in this session, and I am reporting it because it is the strongest evidence
either of us has:

> Four runs on `main` were executing when the ruling arrived. Run 1 returned `1323 passed`, clean.
> Runs 2–4 were still going while I edited `pipeline.py`, `rebuild.py` and `models/design.py` for
> the P1 refactor. **I contaminated my own flake experiment with a dirty tree**, in exactly the way
> G describes. I stopped them and discarded the results.

That is twice in two days that a source-reading test met a tree being edited mid-run — once when I
killed a lane at 90 % for the same reason, once by accident here. G is not merely the most likely
mechanism; the conditions for it recur naturally in how I work.

**Accepting the close-out as ruled:** mechanism identified as most likely (G), not reproducible
because the tree is unrecoverable, superseded by the dirty-tree control —

> **Every SH2 measurement comes from a committed tree with `code.dirty: false`, evidenced by the
> TRACE document that produced it.**

**Residual, stated plainly: we never identified a varying test, and we are choosing not to.**

**Still owed:** the four `main` runs on a tree I am not editing, reported with failure-set diffs.
Not run yet, because every window since the ruling has had me editing the tree. They go first in
the next session, before anything that touches a file.

---

## 6. What is NOT done

| item | state |
| --- | --- |
| INSTRUMENT-1's four clean runs | not run (§5) |
| `TEXTURE_RETRY_UNCOVERED` re-derivation | not started (§7) |
| SH2 D1/D2 | not started, correctly gated |
| Rebuild-path census | deferred; `rebuild.py` calls `_lock_stream` with no census |
| RS1 fix | deliberately not written this session |
| Local both-lane run on `187f117` | in progress at the time of writing; **not** offered as evidence |
| CI on `04e7cdc`, `187f117`, `1cb48b7` | queued/in progress; only `2c6ac6e` is reported as green |

---

## 7. `TEXTURE_RETRY_UNCOVERED` — the argument I expect to make

Not started, so this is a prediction and labelled as one. The substance of your note is already
supported by RS1's census: **fixture 04 is a hairline drawing, not a photograph.** Firing a
*smoothing* retry at it is the wrong response whatever the number is — smoothing cannot recover a
0.21 mm line; it removes it. The 31.59 % that trips the gate comes from a population RS1 shows is
0.20–0.23 mm ink, not photographic texture.

So I expect to report that **the gate needs a second condition, not a different number**, and if the
measurement says otherwise I will say that instead. What I will not do is tune the number until 04
stops crossing.

---

## 8. Fixture limits

Fourteen synthetic images, cotton, two hoop sizes. **No photograph and no real artwork anywhere in
this tranche.**

* RS1's 0.20–0.23 band is **four distinct shapes, not fourteen samples** — ten of the fourteen
  refused regions are the same two generated shapes repeated across C24 and C11.
* The stream-accounting identities are structural (arithmetic over the pipeline's own emission
  sites), so they should hold on any input — but they are unverified on real artwork, on the
  rebuild path, and on designs that emit nothing, which the tests skip rather than assert about.
* The worksheet identity is verified on the digitize path only.

---

## 9. Reproducing

```
cd apps/backend
.venv/bin/python -m pytest -q tests/test_corpus_baseline_fixtures.py     # §1
.venv/bin/python -m pytest -q tests/test_stream_accounting.py            # §2, §3
.venv/bin/python scripts/trace.py 08_mascot_detail --key accounting      # §3
.venv/bin/python scripts/coverage_audit.py --json out.json               # DET2 table
```

| number | source | key |
| --- | --- | --- |
| CI green on `2c6ac6e` | GitHub API run **31662318585** | `conclusion` |
| 08 worksheet header/rows | `pytest tests/test_stream_accounting.py` | `test_the_worksheet_rows_sum_to_its_own_header` |
| 08 lock penetrations = 162 | `trace.py 08_mascot_detail` | `accounting.lock_penetrations` |
| 08 stop penetrations = 8024 | same | `accounting.sum_stop_penetrations` |
| tree the numbers came from | same | `code.head`, `code.dirty` |

---

## 10. What I would like reviewed

1. **§2's limit.** Identity 1 cannot police the merge or lock passes. I chose to state the boundary
   rather than build a seventh identity that could. If you want one, it needs per-pass expected
   insert types, which is more machinery than the defect currently justifies.
2. **§3's partition fallback.** When a phantom `COLOR_CHANGE` breaks the partition I leave the
   counts alone and flag it. The alternative is to fix the phantom `COLOR_CHANGE` — a real defect I
   found and did not fix, because it is not what P1 asked for.
3. **§4's viability gate.** I declined to derive a branch-structure criterion from 14 synthetic
   regions. If you would rather have a provisional one measured now, say so.
4. **§5.** I am accepting a close-out on a question we never answered. That is the right call on
   your reasoning, and I want it on the record that it is a deliberate unanswered residual rather
   than a solved problem.
