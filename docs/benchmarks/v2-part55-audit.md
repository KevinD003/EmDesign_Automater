# v2 Part 55 — next target: R005, but not the R005 anyone has proposed

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** R004 is paused. Compare R005 and R008, pick one, and do only the
scoping needed to start it correctly. No engine change.

**Decision: R005 fragmentation.** It is a real, general defect on the input class
the product exists for, and every instrument needed to judge it is one this
project already trusts — none of them touch the direction reference that Parts
53–54 disqualified.

**But the two obvious ways to implement it are already answered, and neither is
the fix.** Merging neighbouring same-colour regions has no knee and touches 2% of
objects at any defensible gap. Speck absorption **already exists and is wired**
(`_absorb_specks`, `planning.py:493`) — the sixth time a proposed fix has turned
out to be shipped. The scoping below says what is actually left, and §5 gives the
gate the implementation part must pass.

---

## 1. R005 vs R008

| criterion | **R005 fragmentation** | R008 motif recovery |
|---|---|---|
| product impact | 336–834 objects on real photographs, **46–64% of them ≤25 stitches**; each object costs a transition | real content loss, but bounded to ornament specks |
| measurability | object count, coverage, penetration, trims, stitch count, visual baselines, stream locks, corpus — **all trusted, none depend on the direction reference** | Part 49 measured it: **no knee anywhere**, coverage rises smoothly 3.5%→67% as rules loosen |
| is there a gate? | yes — see §5; coverage is the anti-cheat | **no.** Any recovery figure is threshold-picked, which Part 49 said in terms |
| implementation size | moderate; operates on machinery that exists | large; a new motif-along-a-path detector at the mask stage |
| regression risk | high (it changes what is sewn) but **caught** — locks, baselines, corpus | high, and nothing would catch a wrong answer |
| can the bench judge it? | **no, and that matters** — see §3 |  no |

R008's gate already fired negative in Part 49 and nothing since has changed the
evidence. Restarting it means building a detector whose success cannot be
measured. That is the definition of a part that would look like progress.

## 2. The fragmentation is real and general

Not one photograph's quirk:

| design | objects | median stitches/object | ≤25 stitches | stitches |
|---|---:|---:|---:|---:|
| A01 peacock patch photo | 336 | 30 | 46% | 38,409 |
| A02 neckline black | 834 | 20 | 57% | 58,800 |
| A03 neckline panel | 771 | 18 | 64% | 56,505 |

The panel's median of 18 confirms Part 46's "median 19" from a different code
path.

## 3. The bench cannot judge this, and that is the trap to avoid

The ten bench fixtures hold **93 objects between them** — about nine each —
against 336–834 for a single photograph. Flat artwork is not fragmented.

So an implementation must be measured on **tier-A photographs**, and a large
change to the flat-art visual baselines would be evidence the fix is hitting the
wrong population, not evidence that it works. This is the opposite of the usual
reading of those baselines and is easy to get backwards.

## 4. Both obvious levers, measured and set aside

**Merging neighbouring same-colour regions.** Within a colour stop, how many
objects sit close enough to another to be treated as one region:

| gap | panel: objects merged away | across 11 designs |
|---:|---:|---:|
| 0.0 mm | 0 | 0 (0%) |
| 0.4 mm | 7 | 21 (2%) |
| 0.8 mm | 16 | 35 (4%) |
| 1.5 mm | 56 | 89 (10%) |
| 3.0 mm | 143 | 183 (21%) |

**Smooth, no knee** — the same shape that stopped R008 in Part 49. At any gap a
digitizer would defend (at or under a thread width) it touches 2–4% of objects.
The tiny objects are not fragments of a shape cut apart; they are **isolated
colour islands**, which is why nothing merges at 0.0 mm.

**Speck absorption.** `_absorb_specks` already relabels sub-speck colour
components into the cluster surrounding them, before objects or holes exist, and
it is called at `planning.py:493`. The lever is built.

And raising its threshold is **not** the fix to reach for: Part 49 showed the
dropped-speck set contains real ornament, and Part 47 showed that "fix the
zero-stitch designs" would have meant sewing features narrower than the thread.
Losing content to make a count go down is the failure mode here.

## 5. What is left, and the gate for the next part

The measurement points upstream. The objects are isolated islands produced by
**colour quantisation of photographic texture**, so the lever is the label map
before contouring — fewer or spatially regularised clusters — not merging
afterwards.

**Gate for the R005 implementation part.** All measured on the three tier-A
photographs, not the bench:

1. **Object count falls by ≥30%** on all three.
2. **Interior coverage does not fall** on any of them (corpus interior median is
   currently 98.70). *This is the anti-cheat*: deleting content lowers the object
   count and the coverage together, and only a real fix moves one without the
   other.
3. **Stitch count falls or holds.** If objects fall while stitches rise, the
   change is buying fewer objects with more travel.
4. **Trim count falls** (panel baseline 663, Part 48).
5. **Visual baselines**: flat artwork should be nearly untouched. A large change
   there means the fix is not targeting the population it was scoped for — see §3.
6. **No new zero-stitch corpus designs** (currently 7) and **no new errors**
   (currently 0).
7. **Runtime on 1500×1500 noise does not regress** (Parts 48/49 hazard).

**Stop condition.** If the object count cannot fall 30% without coverage falling,
stop and report that the fragmentation is content rather than noise — exactly as
Part 49 stopped R008. Do not tune `SPECK_ABSORB_MAX_MM2` upward to hit the number.

## 6. A defect in my own scoping script, caught by its own test

The first version of the neighbour search called `np.where(labels == oid)` per
object — a full-frame scan multiplied by the object count, which on a fragmented
design is precisely the large number. That is the Parts 48/49 shape, in the
script written to study fragmentation. The cost test caught it (23× for a 25×
frame); bounding boxes now come from one pass. A second bug rode in with the fix
— the new loop used `k` as its index and shadowed the dilation kernel — and the
tests caught that too.

Two test expectations of mine were also wrong and were corrected rather than the
code: `gap_px` is a dilation radius, so it must reach across the whole clear span;
and one full-frame pass is legitimately linear in frame area, so the cost bound is
linear, not constant.

## 7. Gates

| Gate | Result |
|---|---|
| Decision named | ✅ **R005**, with R008 declined on Part 49's already-fired gate |
| Scoping sufficient to write the next prompt | ✅ §5 — target, population, seven numbered gates, stop condition |
| No R004 consumer work | ✅ none |
| No numeric optimisation against the panel | ✅ no direction score appears in this part |
| `app/` unchanged | ✅ **no file under `app/` changed** |
| Stream locks / visual baselines | ✅ 4 and 10/10 |
| Backend suite | ✅ **900 passed, 2 xfailed** in 765.54 s (894 + 6 new) |
| `ruff check app` | ✅ 12, the standing baseline |

## 8. Files

- `apps/backend/scripts/measure_fragmentation.py` — object-count and stitches-per-object
  distributions, and the same-colour-stop merge sweep
- `apps/backend/tests/test_part55_fragmentation.py` — 6 tests

## 9. Honest note on R008

Declining it is not a judgement that the content loss does not matter. It is that
**nothing available can tell us whether a fix worked.** If R008 becomes the
priority, the first part must build a ground truth — a handful of designs where
the ornament is labelled by hand — because Part 49 showed the data will not
separate on its own. That is a different and larger piece of work than the
detector itself.
