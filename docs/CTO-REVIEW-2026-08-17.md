# CTO review pack — the 2026-08-16 ruling executed, and RS1's first measurement

**Repository:** `KevinD003/EmDesign_Automater`, branch `main`
**Base:** `62b42b0` → **Head:** `5095790` · three commits, all green.

**CI, from the GitHub API — run ID and conclusion per commit, per the standing report rule:**

| commit | content | CI run | conclusion |
| --- | --- | --- | --- |
| `62b42b0` | (base — the band revert + size fix) | 31664684721 | **success** |
| `ab9b1e2` | docs: INSTRUMENT-1 close-out + surface spec | 31670366355 | **success** |
| `b29cd0f` | P0-A: nine bands in penetration space | 31670477833 | **success** |
| `5095790` | P0-B: `accounting.py` extraction | 31670591851 | **success** |

No local pytest line is offered as evidence of a green suite anywhere in this document.

---

## 1. P0-C — complete. INSTRUMENT-1 is closed with spread = 0.

| run | lane | container | result | failure set | porcelain after |
| --- | --- | --- | --- | --- | --- |
| 1 | default | cold | **1371 passed, 0 failed** | empty | empty |
| 2 | no-rebuild | warm | **1365 passed, 0 failed** | empty | empty |
| 3 | default | warm | **1371 passed, 0 failed** | empty | empty |
| 4 | no-rebuild | warm | **1365 passed, 0 failed** | empty | empty |

All four on head `62b42b0`, head recorded before run 1 and re-verified at each restart boundary,
porcelain snapshot after every run. **Failure-set diff, as ruled — sets, not counts: empty vs
empty on every pair. Observed run-to-run spread on the shipping tree: ZERO.** The within-lane
counts are identical; the 6-test between-lane difference is the pass-through suite the no-rebuild
lane skips (its 8 skipped).

Two infrastructure restarts killed the batch mid-flight twice; completed runs survived both
times. The accidental cold-vs-warm boundary adds a last refutation: the cold-container run is
outcome-identical to the warm ones, so cross-run filesystem state produces no difference on a
clean committed tree.

**Close-out as ruled:** mechanism most likely G (a dirty tree under source-reading tests), not
reproducible because the SH2 tree is unrecoverable, superseded by the dirty-tree control — every
SH2 measurement from a committed tree with `code.dirty: false`, evidenced by its TRACE document.
**The residual, plainly: we never identified a varying test, and we are choosing not to.** The
"no A/B decision on a delta smaller than the observed spread" rule is satisfiable with spread = 0.

## 2. P0-A — landed (`b29cd0f`, CI green). Decisions 1 and 2 both executed.

The nine bands, re-derived in penetration space with the headroom-preserving rule you verified by
hand: P6 `0.10 / 0.10 / 0.13 / 0.21 / 0.36 / 0.23`, PARITY `0.13 / 0.14 / 0.26`. Five tighten,
three loosen, one unchanged — re-basing, not regression, asserted from the mixed direction.

Your fixture-04 argument is in the commit message verbatim, and the band comment notes the
worst-object change 3 → 1 so the next reader knows the assertion changed subject. The commit also
records why only 07 went red when the space first changed: its headroom was 1.4 points, tightest
of the nine by an order of magnitude; the other five would have re-based silently.

Decision 2 executed: `bench_competitor.py` measures penetrations — the space a competitor DST can
supply — which keeps `median_stitches_per_object` honest without a rename. The three span-space
measurement scripts keep `stream_span` and now state their space in their docstrings.

## 3. P0-B — landed (`5095790`, CI green). The prediction was WRONG in a useful way.

`accounting.py` now holds `_STREAM_COMMANDS`, `_stream_census` and `attribute_stops_from_stream`,
layered directly above `constants`. LAYERS updated; the layering suite enforces it.

**The on-record prediction is corrected, not confirmed.** I predicted the rebuild census was "a
two-point census at rebuild's single `_lock_stream` site, instrument shared, own test file
needed." Reading rebuild rather than asserting: **the instrument is now free; the identity is
not.** Rebuild's stream decomposes differently — no dark-linework pass (no `linework_lead_in`),
no merge (stop separators carried over, not re-derived), regenerated object spans — so pipeline's
six-category identity does not transfer, and pinning it there would be a check that cannot say no
on the path it claims to cover. The rebuild census is its own small piece of work with that scope
named: two census calls, a rebuild-specific accounting dict, its own identity file stating
rebuild's actual categories.

## 4. RS1 step 1 — the measurement you required before any code. MY ARGUMENT IS REFUTED.

You wrote: *"That is a good argument and it is not a measurement."* Correct, and the measurement
killed the argument. Two findings, the second one bigger than RS1.

### 4.1 RUNNING_SINGLE has zero corpus coverage

The proxy I proposed — existing dark-linework Line objects — **does not exist**: zero
`RUNNING_SINGLE` objects anywhere in the fourteen at bench conditions. That is the third instance
of the pattern this engagement keeps finding (C-tier baselines, phantom COLOR_CHANGE, now this):
a live code path nothing exercises. The measurement was therefore constructed — the refused
regions' own captured skeleton centrelines, built into `RUNNING_SINGLE` objects exactly the way
the fix would build them, fed through `rebuild_design(force=True)` so every object goes down
rebuild's real RUNNING branch.

### 4.2 The round trip does NOT clear the bands as-is — and the loss decomposes

Worst per-object loss, penetration space, scratchpad probe on the committed tree:

| source of centrelines | at 1.4 mm pitch | at 2.5 mm pitch |
| --- | ---: | ---: |
| 04_thin_line_outline (2 branches) | **−50.00 %** | **−50.00 %** |
| 07_circular_badge (3) | −50.00 % | −50.00 % |
| 08_mascot_detail (1) | −20.00 % | −16.67 % |
| C24_many_colours (5) | −5.26 % | −16.67 % |
| C11_many_colours (8) | −7.69 % | −12.50 % |

−50 % is outside every re-derived band. But the loss is not mush — it decomposes into two named
mechanisms, and the decomposition was confirmed by a second probe variant:

1. **A real, pre-existing defect: the entry-point convention differs between emitters.** The
   dark-linework emitter jumps to `path[0]` and then stitches **every** path point including
   `path[0]` — N penetrations. Rebuild's RUNNING branch (`_manual_run`) returns the first point
   as the JUMP and stitches the rest — **N−1 penetrations. Exactly one penetration per run object
   is lost on every rebuild**, today, on any design that carries a Line object. Invisible until
   now because of §4.1, and catastrophic in percentage terms only on tiny branches, where 2 → 1
   reads as −50 %. The per-object integer signatures match across the whole table (10 → 9 is
   exactly −10 %, 6 → 5 exactly −16.67 %).
2. **Pitch re-quantisation in pixel space** — rebuild recomputes the step as
   `max(1, round(pitch_mm / mm_per_px))` and resamples in raster coordinates: a few percent
   either way on long paths (04's big ring: −7 % at 1.4 mm).

My first hypothesis — chord-shortening from double resampling — was **refuted** by the variant
probe (storing the fine centreline and emitting through `_manual_run` itself changed totals but
not the worst loss), which is what forced the correct mechanism into view.

### 4.3 What this fixes about the RS1 design, before a line is written

* The RS1 emitter and rebuild's RUNNING branch must share one entry-point convention. Since (1)
  is a defect for existing linework objects too, the convention gets unified once, for both.
* The ruling's requirement that the viability gate be **derived, not fitted** now has a second,
  independent derivation: a minimum branch length also culls the tiny branches whose one-point
  integer effects make any percentage band meaningless. A threshold expressed as
  "enough penetrations for a per-object percentage to mean something" is derived from the
  arithmetic of the assertion itself, not from the fourteen.
* Pitch stays an open question to be measured through the real path once the convention is
  unified — the current numbers conflate the convention defect with the pitch difference.

## 5. Scorecard

| item | state |
| --- | --- |
| P0-C / INSTRUMENT-1 | **closed** — spread = 0, evidence above |
| P0-A bands + Decisions 1, 2 | **landed, CI green** (`b29cd0f`) |
| P0-B extraction | **landed, CI green** (`5095790`); rebuild census scoped, deferred |
| RS1 step 1 (measure first) | **done — argument refuted, mechanisms named** (§4) |
| RS1 steps 2–5 (the fix) | next: unify the entry-point convention, derived gate, pitch, warning, DET2 fourteen |
| P2 phantom COLOR_CHANGE fixture | after RS1's convention fix — same emitter is involved |
| P2 surface metrics | spec landed (`ab9b1e2`); build gated behind RS1 |
| P3 TEXTURE_RETRY → SH2 | sequenced behind RS1, untouched |

## 6. Reproducing

```
cd apps/backend
# CI verdicts:      GitHub API, runs 31670366355 / 31670477833 / 31670591851, key `conclusion`
# bands:            pytest -q tests/test_probes_three_paths.py tests/test_rebuild_satin_residuals.py
# P0-C evidence:    scratchpad flake2/ — four result files + four empty dirty-*.txt snapshots + TREE.txt
# §4 probes:        scratchpad rs1_roundtrip.py (as-emitted) and rs1_roundtrip_b.py (variant B)
```

## 7. What I would like ruled on

1. **§4.2(1)** — the one-penetration defect exists on `main` today for any Line object. Fix it
   inside RS1's first commit (the convention must be unified there anyway), or as its own
   preceding commit? My recommendation: its own commit, with a constructed-object regression test,
   so the defect fix is not entangled with a feature.
2. **§4.3** — the "enough penetrations for a percentage to be meaningful" derivation for the
   viability gate: acceptable as the derived threshold, or do you want the thread-width version
   as well, with both reported?
