# CTO review pack — the two numbers, and the promotion tranche opened

**Repository:** `KevinD003/EmDesign_Automater`, branch `main`
**Head:** `ba59b50`, working tree clean.

**This is a corrections-and-status report, not a completion report.** The two P0 numbers are
fixed. The promotion tranche is opened and **not yet measured** — nothing in this document
reports a promotion result, because none exists yet.

**CI, from the GitHub API:**

| commit | content | CI run | conclusion |
| --- | --- | --- | --- |
| `5e67ece` | RS1 boundary fix | 31745879992 | **success** |
| `df1f0ff` | review pack | 31808679813 | **success** |
| `ba59b50` | the two corrections + proxy statement | 31814572809 | **in progress** — not claimed either way |

---

## 1. C11's coverage — diagnosed, not amended. You were right to ask which.

**6.74 % → 6.83 %.** Your instinct that a figure right in one column and wrong in the next means
two runs got spliced was exactly correct, and here is which:

| audit run | tree | C11 uncovered | objects | stitches |
| --- | --- | ---: | ---: | ---: |
| `rs1-audit.txt` | RS1 **first build**, pre-boundary | **6.74 %** | 31 | 19,541 |
| `rs1b-audit.txt` | RS1 **after** the single-branch boundary | **6.83 %** | 27 | 19,469 |
| re-run at head, to confirm | `ba59b50` | **6.83 %** | 27 | 19,469 |

**`6.74 %` is not a wrong measurement. It is a correct measurement of a tree that no longer
exists** — the build that still sewed C11's 4-branch network. Writing the review table I took the
object column from the final audit JSON and the coverage column from the earlier one. One row,
two trees.

That is the same class as "22.65 machine-minutes", the parity-tree gap of 79, and the corpus
green claim: **a number outliving the conditions it was measured under** — and it happened inside
the tranche whose entire subject was that failure mode. No excuse is offered; the mechanism is:

> Two audit JSONs from two different trees sat in one scratchpad, and I compensated by memory
> instead of by mechanism. `coverage_audit.py` emits no `code.head`. TRACE does.

**Follow-up this argues for, proposed not assumed:** route the coverage table through TRACE, or
give `coverage_audit.py` the same `code.head` / `code.dirty` block, so a spliced row is
structurally impossible rather than a discipline I have now failed once.

## 2. "12 of 14 sewn" is 11 — and it was in the shipped docstring.

Your arithmetic holds both ways: 04 +1, 08 +1, C24 +5, C11 +4 = **11 new objects**, measured
directly; and 14 refused regions − 3 deferrals (09's noise, 07's two strokes, C11's network)
= **11**.

Corrected in three places: `hairline_runs`' docstring (the shipped one — where the next reader
would have taken it as authoritative), `docs/RS1-HAIRLINES-2026-08-14.md`, and the RS1 test
module docstring. **No test asserted the count**, so nothing else moved.

The prior review pack is **annotated in place rather than silently rewritten** — the corrected
figure carries its correction where the wrong one was read.

## 3. §9.1 — defer accepted, and the proxy statement recorded in your framing

Your correction to my framing is the substantive part, and it is now in the code in three places.
The report had read as though single-branch were a noise filter. It is not:

> **THIS BOUNDARY IS A PROXY, NOT A DETECTOR.** Fixture 09's noise reached the render WITH spur
> pruning already in place; the region still had several branches after pruning, and
> single-branch excluded it only because its noise happened to fragment that way. **NOTHING IN
> THIS SYSTEM CAN TELL NOISE FROM INK.** A noise sliver that prunes to exactly one branch will be
> sewn and no numeric gate will object; the only thing standing between that and a customer is a
> human looking at a render.

Recorded beside the three refutations in `hairline_runs`, in the RS1 test module docstring, and
with an explicit *what this test does not prove* note on the boundary test itself — so a future
green run cannot be read as evidence that a future input's noise was caught.

**Your lead is recorded with its distinguishing property**, which is why it is worth attempting:
all three measured criteria examine the **region**; none examines the **transition into** it.
Real ink has a step edge in the source; a quantisation sliver through a smooth background is a
level-set boundary through a ramp and has no step. Gradient magnitude across the region boundary,
at the anti-alias edge width this codebase already establishes, would be derived rather than
fitted — and it fails *differently* from the three that did.

## 4. §9.2 — promotion tranche OPENED. Expectation set before any measurement.

Confirmed and started. One material fact that makes it cheaper than expected: **A01 and A02 are
already tracked** in `corpus100/` (tier `A-real`, class `user-supplied embroidery`). Promotion is
therefore a change to the standing fixture table — `coverage_audit.fixtures()`, which feeds the
audit, TRACE, and the accounting identities — not a new-binary problem. **The fourteen become
sixteen everywhere at once**, which is exactly why it needed its own tranche.

**The expectation, on the record before the first number exists:** promoting real photographs
will make numbers **worse across the board**. Anti-aliased edges at the widths `MIN_FEATURE_W_MM`
sits among, textured regions the fourteen do not contain, and on A02 a dark garment. Coverage
will fall, refusals will rise, and some gate will fire. **That is the promotion working**, the
same way DET2's honest mask "worsened" every coverage figure it corrected.

**The three watch items are the report's spine**, and each has a stated failure condition:

1. **Noise-sewing, first-class.** Every new render gets **looked at**, not diffed. The report
   will state explicitly whether either promoted photograph produces a **single-branch region in
   a noise area** — the case the boundary provably cannot catch, and A01/A02 are the first inputs
   that could produce one. **If one appears, the noise criterion stops being deferred and becomes
   P0.**
2. **RUNNING_SINGLE at volume.** The angelfish says real artwork is 55 % run objects; the
   fourteen were 0 %. How many A01/A02 produce, and whether the entry-point convention
   (`ce254a8`) and the round trip hold at that volume rather than at one ring.
3. **The phantom COLOR_CHANGE**, which A02 is supposed to reach. **If it does not fire, the
   mechanism in the previous pack's §6 is wrong, or A02 is not the input class I think it is —
   and the report will say which**, rather than adjusting the fixture until it triggers.

**Nothing the promotion surfaces gets fixed in this tranche.** Promote, measure, classify — and
for every gate that fires, state whether the gate is right and the input is hard, or the gate is
wrong and the fourteen were hiding it. Those are different findings and they will be labelled
separately.

## 5. Status

| item | state |
| --- | --- |
| C11 coverage correction | **done**, diagnosed, pushed |
| "12 of 14" → 11 | **done**, three places, pushed |
| Proxy statement + gradient lead | **done**, three places, pushed |
| CI on `ba59b50` | **in progress** — will be reported with its run ID and conclusion |
| Promotion: baseline + promote + measure | **opened, not measured** — no result exists |
| Phantom fix, surface build, rebuild census, TEXTURE_RETRY, SH2 | untouched, correctly sequenced behind the promotion |

## 6. Reproducing

```
cd apps/backend
.venv/bin/python scripts/coverage_audit.py --json out.json    # §1, key uncovered_px per fixture
.venv/bin/python -m pytest -q tests/test_rs1_hairline_runs.py # §3 boundary + its "does not prove" note
# CI: GitHub API runs 31745879992 / 31808679813 / 31814572809, key `conclusion`
```

## 7. What I would like ruled on

1. **§1's follow-up** — giving `coverage_audit.py` a `code.head`/`code.dirty` block (or routing
   its table through TRACE) so a spliced row becomes structurally impossible. Small, and it
   closes the exact hole that produced the error you caught. Worth doing inside the promotion
   tranche, or after it?
2. Nothing else. The promotion proceeds as ruled and reports back before anything is fixed.
