# v2 Part 57 — R005 is not a colour-count decision. Close it.

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** test the content hypothesis directly — vary `max_colors` on the
three tier-A photographs against the same four gates. Controlled test, no engine
change.

**Answer: neither of the two outcomes the brief anticipated. Halving the colour
count does not reduce the object count at all** — it stays flat or *rises*, while
coverage barely moves. The best result anywhere in the sweep is **−6%** against a
30% gate, and two of the three designs end with **more** objects than they started.

**Recommendation: close R005 as working-as-intended on quality grounds.** Three
independent levers have now been measured and all three are refuted — post-contour
merging (Part 55, 2–4%), label-map smoothing (Part 56, fails on coverage), and
colour count (this part, no effect). What remains is a machine-cost question, not
a fragmentation defect.

**And one thing worth reporting on its own: `max_colors` above 8 does nothing.**
k=12 and k=8 produce **byte-identical** results on all three photographs, because
`pipeline.py:257` caps the planner at `min(max_colors, 8)`. The product accepts up
to 12 and silently plans 8.

---

## 1. The sweep

Same seed, same hoops, coverage from the corpus runner's own metric:

| design | k | objects | median st | ≤25 st | stitches | trims | interior | edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A01 peacock | **12** | 336 | 30 | 46% | 38,409 | 364 | 95.80 | 94.40 |
| A01 | 8 | 336 | 30 | 46% | 38,409 | 364 | 95.80 | 94.40 |
| A01 | 6 | 342 | 28 | 48% | 38,352 | 368 | 95.40 | 94.40 |
| A01 | 4 | **347** | 25 | 50% | 39,069 | 379 | 95.00 | 93.70 |
| A02 neckline black | **12** | 834 | 20 | 57% | 58,800 | 796 | 95.90 | 93.10 |
| A02 | 8 | 834 | 20 | 57% | 58,800 | 796 | 95.90 | 93.10 |
| A02 | 6 | **929** | 19 | 61% | 61,614 | 914 | 96.10 | 93.70 |
| A02 | 4 | 840 | 26 | 48% | 64,073 | 789 | 96.10 | 94.00 |
| A03 panel | **12** | 771 | 18 | 64% | 56,505 | 663 | 97.00 | 94.00 |
| A03 | 8 | 771 | 18 | 64% | 56,505 | 663 | 97.00 | 94.00 |
| A03 | 6 | 725 | 22 | 62% | 55,081 | 586 | 96.60 | 92.60 |
| A03 | 4 | **724** | 22 | 57% | 55,650 | 571 | 97.10 | 93.90 |

## 2. Objects against coverage — the curve the brief asked for

Colour count on the left, object count relative to k=8, coverage beside it:

| design | k=8 | k=6 | k=4 | objects at k=4 | interior at k=4 |
|---|---:|---:|---:|---|---|
| A01 peacock | 336 | 342 | 347 | **+3.3%** | 95.80 → 95.00 (−0.80) |
| A02 neckline black | 834 | 929 | 840 | **+0.7%** | 95.90 → 96.10 (+0.20) |
| A03 panel | 771 | 725 | 724 | **−6.1%** | 97.00 → 97.10 (+0.10) |

**Coverage holds** — within ±0.8 everywhere, and it *improves* on two designs.
So this is not the "both fall together" case either. The lever simply has almost
no purchase on the object count, in either direction.

Gate 1 needed −30% on all three. The sweep's best is −6.1% on one design and
positive on the other two. **Gate 1 fails at every setting tested**, so the
remaining gates were not used to defend it.

## 3. Why fewer colours does not mean fewer objects

The object count is driven by how **spatially scattered** each cluster's territory
is, not by how many clusters there are. Merging two colour clusters does not merge
their regions — it produces one cluster whose pixels are interleaved across the
image, and interleaved pixels are *more* connected components, not fewer.

A02 at k=6 is the clean demonstration: **929 objects from 6 colours against 834
from 8**. Reducing the palette made the design more fragmented, and it cost 2,814
extra stitches and 118 extra trims to do it.

That also explains why Part 55's merge sweep found nothing at a 0 mm gap. The
tiny objects were never fragments of one shape that quantisation split; they are
separate pieces of the photograph, and re-quantising re-cuts them differently
without joining them.

## 4. `max_colors` above 8 is inert

k=12 and k=8 are identical in every column, on all three photographs — same object
count, same stitch count, same trims, same coverage to two decimals.

`pipeline.py:257`: `k_plan = min(int(max_colors), 8)`. The comment calls it "the
former hard cap; retries may exceed it", and the sketch-coverage retry can raise
`k_plan` — but on these three photographs it never fires, so the request for 12
colours is planned as 8 and the user is never told.

This is not an R005 finding and I am not fixing it here — this part changes no
code. It is worth its own decision: either honour the request, or say in the API
what the effective cap is. Flagging it because it silently limits a user-facing
parameter, and because anyone reading a `max_colors=12` result until now was
reading an 8-colour plan.

## 5. Visuals

`docs/benchmarks/v2-part57-colors/` — one strip per photograph, the rendered
design at k=12, 8, 6 and 4 side by side with object and stitch counts. The k=12
and k=8 panels are pixel-identical, which is §4 made visible.

## 6. Flat art

No engine change ships, so the flat-art baselines cannot move — 10/10 hold and 4
stream locks pass. On the hypothetical of a photographic-only colour default: the
bench fixtures each pass an explicit `colors` parameter, so a default that applied
only when the caller did not specify one would not reach them. That question is
moot given §2, and is recorded only so the next brief does not have to re-derive it.

## 7. Decision

The brief offered three outcomes. Taking them in turn:

- **Better photographic default** — *rejected*. There is no setting in the sweep
  that reduces objects meaningfully, and the two lower settings make two of three
  designs worse on stitches and trims.
- **Optional "simplify photo" mode** — *rejected on this evidence*. A mode is only
  worth building if the knob it exposes does something; this one does not. If such
  a mode is wanted for *aesthetic* reasons — fewer thread changes, a poster look —
  that is a legitimate product feature, but it should be scoped and judged as one,
  not justified by fragmentation numbers it does not move.
- **Close R005 as working-as-intended** — **this is the conclusion.**

R005 opened as "median 19 stitches per object". That statistic is real and it is
still true. What three parts of measurement have established is that it is not a
defect anyone can remove without removing content:

| lever | part | result |
|---|---|---|
| merge neighbouring same-colour regions | 55 | knee-less; 2–4% at any defensible gap |
| smooth the label map | 56 | gentlest possible filter fails gates 1–3; −56% on one design costs 0.90 coverage and 26% of stitches |
| reduce the colour count | 57 | no effect; objects flat or rising |

**The residual value is real but it is a cost problem, not a quality one.** Even
Part 56's failed filter cut trims on all three designs, and this sweep cut A03's
trims 663 → 571 at k=4. If the objects are genuinely there, the win is in how they
are sewn — Part 48's territory, extended to the cross-colour ordering Part 48
deliberately declined. That is a scoped, measurable piece of work with an
instrument that already exists.

## 8. Gates on this part

| Gate | Result |
|---|---|
| Answers a product question | ✅ yes, and it answers "no" |
| No new spatial filter | ✅ none |
| No post-contour merge path | ✅ none |
| Speck absorption untouched | ✅ untouched |
| No R004 work | ✅ none |
| No success claimed from fewer objects | ✅ no setting produced fewer objects to claim |
| `app/` unchanged | ✅ **no file under `app/` changed** |
| Stream locks / visual baselines | ✅ 4 and 10/10 |
| `ruff check app` | ✅ 12, the standing baseline |

## 9. Files

- `apps/backend/scripts/measure_r005_gates.py` — gains `--colors` for the sweep
- `docs/benchmarks/v2-part57-colors/` — three comparison strips
