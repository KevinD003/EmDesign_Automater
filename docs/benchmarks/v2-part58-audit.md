# v2 Part 58 — cross-colour ordering is worth 0.9%. Decline it.

**Date:** 2026-08-04 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** measure whether cross-colour ordering is a real, safe cost target,
and define the narrowest version worth building — or decline it. Measurement only.

**Answer: no. Decline.** Reordering colour stops can only move the jumps *between*
stops, and those are **2.2–7.4%** of all jump travel. Solved optimally, the entire
available saving is **0.47 m out of 50.99 m — 0.9%** — and **trims do not change at
all**, by construction.

At jump speeds, 0.47 m is under a second of machine time across three designs. The
same three designs spend **roughly 76 minutes** on trims.

**The residual machine cost is trims, and trims are one per object.** Part 57 closed
the object count as content. That is not a gap in the analysis; it is the analysis
finishing.

---

## 1. The opportunity, measured

`scripts/measure_cross_colour.py` walks the stream, splits every jump into
intra-stop (Part 48's territory) and inter-stop (all that colour reordering can
touch), then solves the stop order exactly — brute force over permutations at ≤8
stops, best-of-all-starts greedy above that, so the figure is a floor on the
optimum and cannot overstate the win.

| design | stops | trims | travel | intra | **inter** | inter % | best inter | **saving** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A01 peacock | 15 | 364 | 12.23 m | 11.33 | **0.90** | 7.4% | 0.61 | **0.29 m** |
| A02 neckline black | 18 | 796 | 20.50 m | 20.05 | **0.46** | 2.2% | 0.41 | **0.04 m** |
| A03 panel | 18 | 663 | 18.26 m | 17.55 | **0.71** | 3.9% | 0.57 | **0.14 m** |

**A03 reproduces Part 48 exactly** — 663 trims, 18.26 m — from a different code
path, which is what makes the rest of the table worth reading.

Total reachable: **0.47 m of 50.99 m = 0.9%.**

## 2. Why trims cannot move

Part 48 established it and it holds here: reordering removes no trims. Every
object needs one transition into it, so the trim count is bounded below by the
object count minus whatever the `TRIM_MIN_GAP_MM` gate can carry as thread.
Rearranging *which order* the objects are sewn in changes the distance between
them, never the number of them.

So the trim cost — 364, 796, 663 — is a function of the object count. Part 57
measured three independent levers on that count and refuted all three.

## 3. The cost comparison that settles it

| | A01 | A02 | A03 |
|---|---:|---:|---:|
| trims × 2.5 s | **15.2 min** | **33.2 min** | **27.6 min** |
| entire reachable travel saving | 0.29 m | 0.04 m | 0.14 m |
| …as machine time, at ~1 m/s | ~0.3 s | ~0.04 s | ~0.14 s |

The optimisation on the table is four orders of magnitude smaller than the cost
that dominates these designs. There is no threshold, no policy and no
implementation quality that changes that ratio.

## 4. Risk taxonomy — recorded even though the recommendation is decline

The brief asked for it, and it is worth having written down so a future attempt is
bounded rather than re-derived:

**Clearly unsafe.** Any reorder that moves a stop across one it is layered with.
The engine already encodes real layering dependencies: clusters are sewn
darkest-first, and Part 14's hole absorption plus Part 16's detail deferral both
depend on `stitch_rank` — a fill may absorb a hole *only* because the detail in it
is sewn later. Reordering stops silently invalidates those decisions, which were
made against the original rank.

**Plausibly safe.** Two stops that are spatially disjoint (no object of one lies
inside or adjacent to an object of the other) and that neither defers detail into
nor absorbs a hole from the other. These could be swapped freely.

**Ambiguous, needs a conservative fallback.** Stops that are spatially interleaved
but not overlapping — the common case on a photograph. Whether light-under-dark
matters depends on thread coverage and fabric, which nothing here measures.

The taxonomy has a cost of its own worth naming: implementing it means threading
layering constraints through `_plan`, `stitch_rank`, deferral and hole absorption
— a change touching the parts of the pipeline with the most measured history —
to chase 0.9%.

## 5. Interleaving objects across colours: worse, and quantifiably so

The variant that could beat 0.9% is interleaving objects rather than reordering
whole stops. It fails on arithmetic before it reaches safety.

Each switch back to a previous colour costs a **colour change**: a re-thread or a
needle index, on the order of **20 s**, against a trim's ~2.5 s. Saving the whole
0.47 m — under a second — while adding even one colour change is a net loss of
about 19 s. The policy would have to save several metres per added colour change
to break even, and there are only 0.47 m in total to win.

**Not close. Not a tuning question.**

## 6. Recommendation

**Decline cross-colour ordering.** Not "too risky to attempt yet" — too small to
be worth attempting at any risk level. The measurement is a ceiling, so no
implementation can beat it.

Two things I would say instead of proposing a smaller version:

1. **Part 48 already took this win.** Within-colour proximity ordering cut the
   panel's travel 36.20 m → 18.26 m. The remaining travel is 96–98% intra-stop and
   already optimised; the inter-stop remainder is what is left after the good idea
   was applied.
2. **If machine cost is the priority, the honest lever is the trim gate, not
   ordering.** `TRIM_MIN_GAP_MM` is 6.0 mm and Part 48 measured 10 mm giving 485
   trims against 663 — a **27%** cut, three orders of magnitude more than this
   part's 0.9%. Part 48 refused it on a stated principle: this writes files for
   arbitrary machines, and assuming an aggressive auto-trimmer leaves 1 cm of
   loose thread on every machine without one. That refusal was right and I am not
   overturning it here. But it is a **product** decision with a measured price
   tag, and it could be reopened as a per-machine or per-export setting rather
   than a global constant. That is where the next real cost win is, if one is
   wanted.

I would not commission (2) as an engine change. I would commission it as a
question to the user: *do you know what machine this is sewing on?* If the answer
can be known at export time, 27% is available. If it cannot, 6.0 mm is correct.

## 7. Separate decision: the `max_colors` cap

Part 57 found that `max_colors` above 8 is inert — k=12 and k=8 produce
byte-identical designs because `pipeline.py:257` caps the planner at
`min(max_colors, 8)`.

**Decision: clamp explicitly and tell the user. Do not raise the cap.**

- **Do not honour requests above 8.** Part 57 measured that more colours do not
  improve fragmentation, and nothing in this project has ever measured a quality
  gain from a larger palette. Raising a cap on no evidence is how a knob starts
  costing runtime for nothing.
- **Do tell the user**, because the current behaviour silently discards a
  parameter they set. The mechanism already exists and is already used for the
  opposite case: `user_warnings` carries "the first colour plan missed too many of
  the artwork's lines and was re-drawn with N colours" when the planner *raises*
  the count. There is no matching message when it *lowers* one. `Design.warnings`
  was introduced in Part 25 for exactly this class of thing, and its own docstring
  names "a colour count that could not be honoured" as an example — a case it does
  not currently cover.

The narrowest fix: when `int(max_colors) > 8`, append a warning saying the plan
used 8. Roughly four lines, using machinery that exists, no behaviour change to
the stitch stream. **Not implemented here** — this part is measurement-only and
the brief asked for the decision, not the code. It should be its own small part so
the warning text gets reviewed rather than slipped in beside a routing analysis.

## 8. Gates

| Gate | Result |
|---|---|
| Answers "is cross-colour ordering the next cost win?" | ✅ **no**, with a ceiling not an estimate |
| Opportunity table | ✅ §1, and A03 reproduces Part 48 |
| Risk taxonomy | ✅ §4 |
| Expected saving estimated | ✅ 0.9%, optimal |
| Explicit recommendation | ✅ decline |
| `max_colors` decision made separately | ✅ §7, not folded into routing |
| No R004 work | ✅ none |
| R005 not reopened | ✅ not reopened |
| No quality claim from trim reduction | ✅ no trim reduction is claimed; §2 says trims cannot move |
| `app/` unchanged | ✅ **no file under `app/` changed** |
| Stream locks / visual baselines | ✅ 4 and 10/10 |
| `ruff check app` | ✅ 12, the standing baseline |

## 9. Files

- `apps/backend/scripts/measure_cross_colour.py` — the intra/inter split and the
  exact stop-order optimum
