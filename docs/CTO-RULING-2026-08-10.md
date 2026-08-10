# CTO ruling — 2026-08-10

Rules the open decisions in `docs/CONSOLIDATED-REPORT-2026-08-10.md` PART 5, and sets the
priority order for the 31 confirmed quality defects. Companion to
[`CTO-VERDICT-2026-08-09.md`](./CTO-VERDICT-2026-08-09.md), which remains the governing verdict.

**Verified independently before ruling** (at `ba4fb28`): tier-A "real" corpus is exactly three
photographs — `A01`/`A02`/`A03` — with the remaining `A_fixture_*` being copies of the synthetic
bench set, as reported. UP1 confirmed at the line: `generation.py:91` passes `(pull_mm / 2.0)` for
satin while `geometry.py:110` applies the full `pull_mm` for fills, from the same stored number whose
docstring says "per side"; the `round()` on that same line confirms SZ4/UP4. CP1's determinism suite
passes 5/5.

---

## 1. RULING on 5.1 — the parity trade-off: **ACCEPT. Land it.**

`git revert` is not the answer. Reasoning:

- **What the fix buys is categorical.** 13 of 24 bars changing `stitch_type` on a one-pixel shift
  means the same customer artwork, cropped or re-exported one pixel differently, becomes a different
  product. That is the same family as the canvas-centre rotation (STEP 3a) and the unseeded k-means
  (CP1), and it is the one remaining member of that family that is understood and has a fix in hand.
- **What it costs is bounded and localised.** Peak local density 23 → 26 at **one** cell, on **one**
  fixture, with p99 unchanged and `flagged_cells` still 0. That is not a density shift; it is one
  site moving.
- **The site is a lock.** A tie-off is by construction two or three small stitches in a tight
  cluster — locally dense on purpose. A 13% peak rise at a lock site is at least as consistent with
  correct behaviour as with a defect, and the probe that would have settled it (a ±0.25 mm box that
  caught one stitch) is measuring the wrong thing.

**Do not block a determinism fix on an unverified density question at a single site.** Land the
parity fix; open the lock-site question as its own item with a probe built around the lock geometry
rather than a fixed box. If that probe later shows a real general density rise, it is a separate fix
on a stable base — which is strictly easier than the reverse.

## 2. RULING on priority — the order for the next tranche

1. **5.1 parity fix.** First, because every classification and width measurement downstream is taken
   on the skeleton it stabilises. Re-run the classification width survey afterwards: the four flagged
   objects may change.
2. **UP1** — satin receives half the per-side pull compensation a fill receives from the same number.
   Small, contained, and wrong by 2× on every satin object in every design.
3. **DET3** — highest customer-visible impact of anything remaining. Artwork is deleted as "the
   garment" on the basis of the image's border colour, which is never an input; the deletion is
   subtracted from both loss bases so no channel can report it. Fires on 51–53/100 designs, 14 losing
   ≥20% of foreground silently, and **every transparent PNG is exposed** because alpha is composited
   onto white — the single most common real digitizing input. Make the substrate an input, report
   removed area as its own channel, and disable the rule entirely for alpha-declared input.
4. **SH2** — bare-fabric moats, up to 443 mm² at a 200 mm hoop. Ship with `TEXTURE_RETRY_UNCOVERED`
   re-derived, per the report's own warning.
5. **The physical-units contract (report item #4: SZ1/SZ3/SZ4/UP1/UP2/UP3/UP4)** as its own tranche,
   after the above. It touches every generator and will move the whole bench; do not interleave it
   with anything else. **Re-pin at a hoop above 133 mm** — at 100×100 and 130×180 the bench
   structurally cannot see SF1, SZ2 or half of this contract.

Deferred, unchanged: the area-over-cap veto (5.3) after the parity fix and its survey re-run; 1c;
3e-i, which must not overlap a change that alters either path's stream.

## 3. What stays open, and must not be quietly absorbed

- **5.2** — the +6 digitize/rebuild trim divergence. Mechanism still a hypothesis.
- **5.4** — the knockout-policy finding (1.5 mm lettering should not be knocked out of a band).
- **5.5** — the standing dissent on the veto: it separates perfectly on N=4 over ten synthetic
  fixtures, and this corpus contains no legitimate wide satin by design.

---

## 4. The binding constraint is now evidence, not engineering

Three facts from the report, taken together, are the most important thing in it:

- **There are three real photographs in the entire test suite.** Every headline number, defect
  incidence rate and acceptance threshold in this engagement rests on them plus synthetic fixtures
  from one generator script.
- **There is no measured comparison against commercial output anywhere in this work or the repo.**
  Every "worse than commercial" judgement is reasoning from craft first principles.
- **Nothing has ever been sewn.** All coverage and bare-fabric numbers are synthetic thread rasters.
  Puckering, pull-in and registration were reasoned about, never observed on fabric.

The engine has improved enormously against what it could measure — badge machine time is down 61%,
travel plumbing that was 31% of all corpus stitches is gone, and the same upload now yields the same
design. But further blind improvement has falling returns, and several of the 31 defects have
acceptance criteria that **cannot be honestly set** without real artwork: the veto's threshold, the
substrate rule's default, `MIN_FEATURE_W_MM`, `TEXTURE_RETRY_UNCOVERED`, and every fabric-profile
value.

**The owner already possesses the matched benchmark this work has been missing.** A production shop
paying for manual digitizing generates, every day, exactly the artefact pair nobody has been able to
construct here: a customer's original image and the finished machine file an expert produced from it.
That corpus is simultaneously the missing test set, the missing commercial baseline, and the training
data for any future learned work. Nothing in the codebase substitutes for it.

**Required of the owner, in order of value:**

1. **20–50 real customer jobs** — original image plus the designer's final machine file, ideally with
   the fabric and hoop used. This replaces three photographs as the evidence base and gives every
   remaining defect a real incidence rate.
2. **One stitch-out.** Take one current output to an actual machine and sew it. Every coverage number
   in this engagement is a raster approximation with a stated ~4% floor; one physical sample tells us
   more about puckering, pull-in and registration than any further synthetic measurement.
3. **A designer's verdict on 20 outputs** — usable as-is / usable after edits / redo from scratch.
   That single number decides how much of the manual workload is addressable today.

---

*CTO ruling. Every claim verified against the code at `ba4fb28` in this session unless stated.*
