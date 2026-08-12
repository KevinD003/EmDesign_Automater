# SH2 — three candidate rules measured, none shippable yet

**No code landed. `main` is unchanged.** This records what was built, what each variant measured,
and why each was rejected, so the next attempt starts from evidence rather than from the design.

All numbers: **ran the shipped code**, cotton at each fixture's own bench hoop, "before" from a
`git worktree` at `22d1dbb`.

## The defect, confirmed

`planning.py` runs the ambiguous-blend cut only `if not is_textured`, while the Part 29 seam fill
that would re-own those `-1` pixels sits inside `if is_textured:` — unreachable on exactly the path
that creates the damage. Measured, using the pipeline's own label map:

| fixture | unowned foreground | pipeline's `uncovered_px` |
| --- | --- | --- |
| 03_gradient_soft_subject | **11.96 %** | **0.00 %** |
| C24_many_colours | **15.60 %** | 12.53 % |
| C11_many_colours | 6.30 % | 2.66 % |

Fixture 03 loses 11.96 % of its foreground to nobody while the pipeline reports 0.00 % uncovered.
**That gap is DET2's inflated `emitted_mask`, measured directly** — the damage is invisible to the
gate that is supposed to catch it.

## Three rules, three refutations

The fix extracts the seam fill into `_own_thick_blend` and runs it unconditionally. What varies is
which `-1` pixels earn ownership.

| rule | 01 (hard-edged) | 05_wordmark_caps | 03 unowned | C24 unowned |
| --- | --- | --- | --- | --- |
| baseline (no fix) | 6,165 | 1,802 | 11.96 % | 15.60 % |
| **A** thickness ≥ 0.4 mm (one thread) | 6,221 (+56) | 1,914 (**+6.2 %**) | **0.81 %** | **0.22 %** |
| **B** thickness ≥ 1 anti-alias px | 6,268 | 1,881 | 0.00 % | 0.22 % |
| **C** thickness ≥ 0.4 mm **and** ≥2 distinct owned neighbours | **6,165 — identical** | 1,827 (+1.4 %) | **0.81 %** | 15.33 % — **lost** |

**A** closes both moats but grows glyphs: 05 is a ONE-colour wordmark whose halo borders ink on one
side and background on the other, and owning it drove the rebuild fidelity probe to an **18.4 %
object loss against a 14 % band**. Growing shapes by a pixel per side is the precise effect the
ambiguous cut was written to prevent.

**B** was tried on a reasoning error of mine — I assumed a smaller threshold would be *less*
aggressive. It is the opposite: the threshold is a MINIMUM THICKNESS TO OWN, so 1 px owns more than
4 px. The measurement refuted me (08: 8,024 → 7,694; 07: 17,174 → 17,656, both worse than A).

**C** enforces the cut's own definition — a blend is between TWO colours — and fixes 01 exactly and
05 nearly. **It loses C24**, because C24's unowned region is not a thin band at all: it is a WHOLE
RECTANGLE deleted wholesale, bordered by background, so it has no second owned neighbour.

## What the three results jointly say

The population is not one thing, and no single scalar separates it:

* a **halo** around a glyph — thin, one owned neighbour — must stay unowned;
* a **transition band** between two inks — thick, two owned neighbours — must be owned;
* a **wholesale-deleted region** (C24) — large area, possibly one owned neighbour — must be owned.

A rule combining thickness with either "two owned neighbours" **or** "area over a floor" would cover
all three, but fitting a second threshold against ten synthetic fixtures at the end of a session is
how a constant gets tuned to noise. Not attempted.

## Also established

* **No classification flipped** under rule A (`satin_share` identical on all ten fixtures), and the
  corpus cost was +1.8 % machine-minutes `[cotton @ per-fixture hoop]`.
* The defect doc's claim that this fix "leaves hard-edged flat art bit-identical" is **inherited and
  false for rule A**: `01_flat_2color_logo` is hard-edged (3 distinct source colours) and moved
  6,165 → 6,221. It IS true for rule C.
* **`TEXTURE_RETRY_UNCOVERED` was not re-derived** and cannot be until DET2 is corrected. Under every
  variant, 0 of 14 fixtures cross 0.19, so none of them mis-fires the photographic rescue — but that
  is a narrower statement than the derivation the ruling asked for.
* **One test is flaky**: two full runs of the same tree gave 17 and 16 failures over an identical
  1,265 total. Not identified.

## Fixture limits

Ten synthetic flat fixtures plus four parametric corpus images, all cotton, at 100×100 and 130×180.
No photograph and no real artwork was measured. Real exports carry anti-aliased edges at widths this
threshold sits directly among, so the halo-versus-transition boundary is exactly where real artwork
is most likely to behave differently from these fixtures.

**CORRECTION.** This section previously dismissed C24, the case that drove rule A, as "a
generated rectangle grid with no real-world analogue in the corpus". That conflated its
APPEARANCE with its MECHANISM, and only the appearance is synthetic. A flat region deleted
because its colour fell midway between two palette centres is what happens whenever artwork
carries more distinct colours than the palette budget — and CB2 measured **38 of 100 corpus
designs exceeding the stop bound at the default request**. The wholesale-deletion case is
real, which is why the stricter two-owned-neighbours variant that loses C24 is insufficient
rather than merely conservative.
