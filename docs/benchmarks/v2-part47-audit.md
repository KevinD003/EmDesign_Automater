# v2 Part 47 — R007: the zero-stitch designs were not the bug

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** R007 — *"Nine corpus designs produce zero stitches. Silent failures. Trace
the pipeline for each, identify common failure modes, add a guard that raises instead of
failing silently, add the nine as regression tests."*

The guard was the right call. Everything else in that brief rests on a premise that does
not survive measurement: **there was nothing wrong with the filtering, and one of the nine
was a blank image.**

---

## 1. The count is 8, not 9 — and it moved without anyone fixing it

Re-ran the full 100-design corpus at this commit: **8 zero-stitch, 0 errors**. The figure
of nine dates from Part 36; `C02_lattice_trellis` and `C15_lattice_trellis` have since
started working (C02 now sews 32,801 stitches) as a side effect of the Part 36 palette
recovery, and `C04_tiny_lettering` regressed into the set. Nobody noticed either way,
because the number was being quoted from an old run rather than re-measured.

## 2. One of them is a blank image

`C01_hairline_linework` has **zero pixels differing from its background**. Measured at four
thresholds; the image is empty.

The cause is in the corpus generator, not the engine. `hairline_linework` draws its only
ink in `pal[3]`, and `PALETTES[1][3]` is `(250, 250, 250)` on a `(255, 255, 255)` canvas.
The design was never drawn. Zero stitches is the correct answer, and this fixture has been
counted as a pipeline failure in every audit that mentioned the number.

Fixed two ways in `build_corpus100.py`: the palette is now ordered by contrast against the
canvas before use, and `_write` refuses to emit any fixture whose ink share is under 0.2%.
A stress corpus that can contain a blank is a corpus that manufactures phantom defects.

## 3. The other seven are the engine being right

Every one logs `sub_thread_feature` with a **median region width of 0.23 mm**, against a
0.4 mm thread. The pipeline is declining to sew features narrower than the thread it would
sew them with, and it says so:

> *"About 88% of the artwork is too small or too faint to sew at this size and was left
> out. A larger hoop keeps more detail."*

**That advice is true.** Same artwork, same settings, larger hoop:

| Design | 100×100 | 130×180 | 200×300 | 360×350 |
|---|---:|---:|---:|---:|
| C14_hairline_linework | 0 | 0 | **36,133** | 182,323 |
| C28_lattice_trellis | 0 | 0 | **18,250** | 79,396 |
| C30_tiny_lettering | 0 | 0 | **4,618** | 16,485 |
| C43_tiny_lettering | 0 | 14 | **4,621** | 15,883 |

So "fix the zero-stitch designs" would have meant weakening the sub-thread-width guard —
making the engine sew features narrower than its own thread. That is not a fix; it is the
defect the guard exists to prevent, and it would have shown up later as unsewable output on
real work.

This is the fourth consecutive brief whose proposed fix was refuted by measuring first.

## 4. What *was* broken: a correct refusal arrived as a success

`POST /api/digitize` returned **HTTP 200 with an empty `Design`**. The warnings explaining
why were present, easy to miss, and impossible to act on from a 200 — the caller got a
valid-looking design and an export that sews nothing.

It now returns **422** with the hoop named and the engine's own explanation:

```
Nothing could be sewn at hoop 100x100: About 88% of the artwork is too small or
too faint to sew at this size and was left out. A larger hoop keeps more detail.
```

The guard is at the **API boundary, not in the engine**, deliberately: the corpus runner
and the quality bench call `digitize_image` directly and need an empty result as *data* to
record, not an exception to catch. A test pins that split so a later refactor cannot
quietly move the raise inward and break both harnesses.

## 5. Tests — `tests/test_part47_no_empty_success.py` (6)

- an empty result is a 422, not a 200;
- the message names the hoop, because a 422 you cannot act on is barely better than a 200;
- **the same artwork succeeds at a larger hoop** — the advice in the message has to be
  true, or it is worse than nothing;
- `digitize_image` still returns an empty `Design` rather than raising, so the corpus
  runner and bench keep working;
- the generator's blank-fixture guard fires at 0% ink and passes at 5%.

## 6. Verification

| Gate | Before | After |
|---|---|---|
| Backend suite | 828 passed, 2 xfailed | **834 passed, 2 xfailed** |
| `ruff check app` | 12 | **12** |
| Stitch stream locks | 4 pass | **4 pass, unchanged** |
| Visual baselines | 10/10 SSIM 1.000000 | **10/10 SSIM 1.000000** |
| Corpus | 9 zero-stitch (stale) | **8 zero-stitch, 0 errors** (re-measured) |

No pipeline change, so the locks and baselines are unchanged by construction.

## 7. What is actually left here

The seven remaining designs are all tier **C — parametric synthetics**, generated
specifically as fine-detail stress cases, and they are unstitchable at the hoops the corpus
assigns them. The honest options are to raise those hoops in the corpus metadata so the
designs are testing something achievable, or to leave them as a standing demonstration that
the guard fires. Neither is a pipeline fix, and I would not spend engine work on them.

The real fine-detail question — how much detail survives at a *given* hoop — is measured
already by the bench's interior/edge-band coverage, on tier A and B artwork that is real.

## 8. Files

- `apps/backend/app/routers/digitize.py` — 422 on an empty result, with the reason
- `apps/backend/scripts/build_corpus100.py` — contrast-ordered palettes, blank-fixture guard
- `apps/backend/tests/test_part47_no_empty_success.py` — new

The re-measured corpus run is `apps/backend/scripts/corpus100-part47.json`, which is
gitignored like every other generated corpus result — the numbers quoted above are the
record, and `run_corpus100.py` reproduces them.

## 9. Next

**R006** — 837 trims, a real production cost, with `_route_travel` already proving the
mechanism. Then **R008** (the bead-chain ornament, genuine content loss). The direction
field (R004's implementation) remains its own multi-part project.
