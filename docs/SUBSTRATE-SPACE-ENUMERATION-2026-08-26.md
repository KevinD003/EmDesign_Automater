# The enumeration I skipped: every constant evaluated against the substrate space

**Required by my own standing rule and not run when it mattered most.** The rule is: *when a
field, unit or SPACE changes, list every calibrated constant evaluated against it and say per
constant whether it was re-derived or carried over.* I ran it for the fixture set (2026-08-21)
and for the penetration/stream spaces. The tranche that changed **Euclidean BGR → CIEDE2000**
— a metric *and* a space — shipped without one. Caught by the CTO, 2026-08-26.

---

## 0. WHY THIS IS NOT BOOKKEEPING: the regression test would have passed on A02

`tests/test_part41_no_background_thread.py` is the regression test for *"no thread is laid in
the garment colour"* — the exact defect the last tranche fixed. Its assertion read:

```python
assert _dist_to(stop.hex, (0, 0, 0)) >= SUBSTRATE_DELTA    # 12.0, Euclidean BGR
```

A02's `#080808` sits at BGR **13.856**. `13.856 >= 12.0`. **The test passes on a design sewing
4,638 stitches of black on black.** The test that exists to catch the defect shared the
constant that permitted it.

**And re-pointing it at `SUBSTRATE_DE2000` does not fix that** — it moves the tautology:

> A test that reads the same constant as the gate can catch the gate being **BYPASSED**. It can
> never catch the gate being **WRONG**. Both sides move together by construction.

So §3 adds an assertion that names no gate constant, and §0's failure is recorded in the
docstrings of both test files rather than quietly repaired.

---

## 1. The enumeration

Every site reading `SUBSTRATE_DELTA`, or computing a BGR distance to the substrate.

### Retired — moved to the perceptual space

| site | was | now | note |
| --- | --- | --- | --- |
| `pipeline.py:541-542` (substrate rule) | `\|\|c−s\|\|_BGR < 12.0` | `bgr_ciede2000 < 2.0` | the gate; shipped `0c5d70f` |
| `pipeline.py:1192` (linework suppression) | same | same | second decision site, moved with it |
| `test_part41…:53` | `>= SUBSTRATE_DELTA` | `>= SUBSTRATE_DE2000` | **§0** — the helper `_dist_to` now returns dE2000 |
| `test_part45…:115` | `< SUBSTRATE_DELTA` | `< SUBSTRATE_DE2000` | `_closest_stop_to` now returns dE2000 |
| `test_part45…:128` | `>= SUBSTRATE_DELTA` | `>= SUBSTRATE_DE2000` | **found by this enumeration** — the ruling named one assertion in this file; there are four |
| `test_part45…:144` | `>= SUBSTRATE_DELTA` | `>= SUBSTRATE_DE2000` | same |
| `test_part45…:174` | `< SUBSTRATE_DELTA` | `< SUBSTRATE_DE2000` | same |

### Retained deliberately — instrument input, not a live gate

| site | decision |
| --- | --- |
| `constants.py:311` `SUBSTRATE_DELTA = 12.0` | **RETAINED.** Exactly one legitimate reader; see §2. |
| `__init__.py` facade re-export | **RETAINED**, follows the constant. The facade contract requires every layer symbol to be re-exported, so removing this alone would break `test_facade_reexports_every_definition`. |
| `scripts/measure_substrate_metric.py` | **RETAINED and the reason the constant survives.** It exists to compare the two metrics and cannot print a before-column if the "before" is deleted. |
| `tests/test_substrate_gate.py` | **RETAINED.** It asserts the constant is *not* compared against anywhere in `app/` — a reader that enforces the retirement rather than depending on it. |

### Prose that named it and went stale

| site | action |
| --- | --- |
| `generation.py:277` — refuted noise criterion #3, *"substrate distance vs `SUBSTRATE_DELTA`"* | **corrected**: the refutation stands (64.8 noise vs 61.4 real, no separation) but the constant it cites is no longer the gate |
| `measure_substrate_metric.py` docstring | already states the rule in both spaces; unchanged |

### A SECOND CONSTANT IN THE SAME SPACE, which nobody had named

| constant | value | status |
| --- | ---: | --- |
| `segmentation._INK_DELTA` | **60.0** | **CARRIED OVER, NOT RE-DERIVED.** Euclidean BGR distance from the substrate, used to reclaim components U²-Net dropped. Its own comment says *"same threshold family as `_corner_mask`'s 40"*, so there are in fact **three** BGR-to-substrate numbers (12.0, 60.0, 40.0) and only one has moved. |

`_INK_DELTA` is a **different decision** — "is this component unmistakably ink?" rather than "is
this cluster the cloth?" — and is therefore not in scope for the gate change. But it is in the
retired space, its threshold family is shared with a constant that was just shown to be
perceptually non-uniform, and **nothing has measured what it does near black or near white.**
Named here, not touched: that is a measurement, not a patch, and it belongs in its own tranche.

## 2. `SUBSTRATE_DELTA`'s fate, decided rather than left

**RETAINED, as instrument input only.** Not "kept in case". The comparison instrument is an
ongoing need — the next threshold question will want the same before-and-after — and deleting
the constant to tidy a name would cost that. What makes retention safe rather than sloppy is
that the retirement is *enforced*: `test_the_superseded_bgr_constant_is_not_compared_against_
anywhere` scans all of `app/` and fails on any live comparison. Written onto the constant.

## 3. The assertion that shares no constant with the gate

`tests/test_substrate_gate.py::test_a02_sews_nothing_in_its_garment_colour`.

It states the product requirement directly — *a real photograph of a black garment must not
come back with stitches in thread the customer cannot distinguish from the cloth* — and
measures **penetrations**, because penetrations are what cost machine time. Its threshold is
`INVISIBLE_ON_CLOTH_DE2000 = 3.0`, deliberately **looser than the live gate** so that raising
`SUBSTRATE_DE2000` toward it cannot silently satisfy it.

The 3.0 is justified independently of the gate: the render examined on 2026-08-22 showed those
regions **invisible in the sew-out preview**, and the nearest real artwork anywhere in the
corpus (07's cream, dE2000 5.986) sits at twice it.

**Verified to bite, not assumed to.** Re-run with `SUBSTRATE_DE2000` forced to 1.0 — the unit
JND that both the CTO and I first reasoned toward:

```
SUBSTRATE_DE2000=1.0:  invisible penetrations= 4638  (5.80 min)  -> FAILS
SUBSTRATE_DE2000=2.0:  invisible penetrations=    0  (0.00 min)  -> passes
```

So it catches the original defect **and** the threshold choice that would have shipped it.
That is strictly more than the gate-constant family can do.

## 4. P1, both written

**`rebuild(rebuild(d)) == rebuild(d)`** — `tests/test_rebuild_idempotence.py`, exact, no band,
no fitted constant. Parametrised over 04 (an RS1 run object, the emitter that stores the arc)
and A01 (36 linework run objects, the emitter that stores samples), so if the two conventions
ever diverge in round-trip behaviour they diverge here. It asserts object count, per-object
penetration counts and the full stream. Its docstring states what it does **not** cover: the
digitize→gen-1 gap, which is representational.

**The two run emitters now cross-reference each other**, in both directions, because "neither
docstring mentions the other" is how the divergence stayed invisible for three tranches.
`hairline_runs` stores the dense arc and round-trips 10/11 lossless (04 *gains* 3, which only a
preserved arc allows); the dark-linework pass stores resampled chords and round-trips 15/36.
**Aligning them is named, not written** — it changes stitch output on a real fixture and
belongs in a tranche that can measure it.

## 5. What this enumeration found that the named list would not

The ruling named two assertions. The enumeration found **five** (four in `test_part45`, not
one), plus `_INK_DELTA` — a second constant in the retired space, in a different decision, with
a comment revealing a **third** (`_corner_mask`'s 40.0). One of three BGR-to-substrate numbers
has been shown non-uniform and moved; the other two have not been looked at.

That is the same pattern as the fixture-set enumeration, which found three sites by asking
which ones mention *neither* the count nor the set: **the sites that bite are the ones nobody
lists.**
