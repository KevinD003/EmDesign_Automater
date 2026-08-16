# What to send us — the real-job-pairs intake spec

**This directory is deliberately empty.** The instrument shipped before the material
(`scripts/real_jobs.py`), so that when real work arrives the first question is what the
comparison says, not what it can be made to say. Nothing in this repository has been sewn.
Everything below is what would change that, in priority order.

Run `python scripts/real_jobs.py` at any time to list and validate what is present.

---

## 1. Job pairs — the highest-value input on the board

One directory per job. Both halves are required; half a pair cannot be compared and is an
error, not a skip.

    tests/fixtures/corpus_real/<job-name>/
        artwork.png     the customer's file, exactly as they supplied it
        expert.dst      what a professional digitizer produced from it
        job.json        optional: fabric, hoop, colours, provenance

`artwork` may be `.png .jpg .jpeg .bmp .webp .svg`; `expert` may be any format
pyembroidery reads (`.dst .pes .exp .jef .vp3 .xxx .pec .sew`). One file of each per
directory, so there is never a question which one a number came from.

**Send the artwork UNMODIFIED.** Not cleaned up, not re-exported, not cropped. The messy
input is the input.

## 2. At least one FLAT-LIT SCAN, not only photographs

Added 2026-08-23, and it is not a nicety — it is a structural gap the A01/A02 promotion
measured:

> `hairline_runs` — the whole RS1 machinery for sewing a line too thin to hold a satin
> column — **cannot be reached by a photograph at all.** A photograph takes the textured
> path (`_interior_texture` >= `TEXTURE_SMOOTH_MIN` 6.0), which mean-shift-filters the
> image and then closes and opens each colour mask at 0.4 / 0.3 mm. The census that feeds
> RS1 only sees regions under `MIN_FEATURE_W_MM` 0.25 mm. Both promoted photographs
> contributed **zero** regions, and not narrowly — their narrowest were 0.34 and 0.38 mm.

So promoting more photographs will never exercise the hairline machinery, and the noise
criterion deferred on 2026-08-18 is deferred on a class of input that cannot reach the code.

**What reaches it:** artwork whose interior texture scores **under 6.0** — a flat-lit scan
or a clean vector export rather than a phone photograph of cloth. Practically:

* a scanner, or even lighting with no visible thread sheen or shadow;
* the design flat, not on a garment, not at an angle;
* the original artwork file if it exists at all — a `.ai`, `.eps`, `.svg` or a flat `.png`
  export beats any photograph of the finished piece.

One such input is worth more here than ten more photographs. If you can send only one thing,
send this.

## 2b. LIGHT-GARMENT ARTWORK WITH A NEAR-WHITE ELEMENT

Added 2026-08-24, for the same kind of reason and from the same kind of measurement.

The substrate rule deletes a colour cluster that is close to the garment's colour. Euclidean
BGR is not perceptually uniform, so a single threshold is stricter near black than near white —
measured, `SUBSTRATE_DELTA = 12.0` is about dE 1.9 near black and about dE 2.6 near white.
The predicted consequence is that near white the rule should delete artwork it ought to keep,
which is the direction that costs a customer their design rather than their machine time.

**It could not be tested.** That failure needs BGR under 12.0 *and* dE over the ~2.3 JND, so
the window is roughly **BGR 8.7 to 12.0** — and across all 82 colour clusters in the standing
sixteen, **the window is empty.** The nearest point is fixture 02's `#fafafa` page at BGR
8.66. The prediction is untested, not refuted, and no fixture we have can change that.

**What closes it:** artwork on a white or cream garment carrying an element that is nearly but
not exactly the garment colour — a white-on-white logo, a cream monogram on ivory, tone-on-tone
lettering. One such job would test the half of the substrate question that sixteen fixtures
cannot reach.

## 2c. A MID-TONE OR DARK GARMENT WITH TONE-ON-TONE ARTWORK

Added 2026-08-27, and it is the first ask justified by **two independent measurements**.
It unblocks two queued items at once.

**Reason one — the phantom `COLOR_CHANGE`.** It needs the dark-linework pass to run and then
be suppressed. On a truly dark garment the pass is skipped one guard earlier
(`substrate_lum >= DARK_CLOTH_LUM`, 60.0), so the phantom is unreachable; the class that can
reach it is a mid-tone garment, light enough to clear 60.0 with its darkest thread inside the
substrate distance. The corpus has none.

**Reason two — `_INK_DELTA`.** `segmentation._reclaim_missed_ink` rescues artwork the matte
dropped when it is at least 60.0 in **Euclidean BGR** from the garment. Measured across the
sixteen, that single number spans **dE2000 7.4 to 20.4 — a 2.77x spread**, monotone in
substrate luminance: dE 7.4 on white, dE 20.4 on black. So the darker the garment, the more
perceptually distinct artwork must be before it will be rescued. What the corpus cannot answer
is whether that ever discards something real, because its dark fixtures (A02, C24) carry
high-contrast florals — nothing near their own cloth's tone.

**What closes it:** a job on a royal-blue polo, a heather-grey tee, a tan cap — with an
element close to the garment's own tone. A navy monogram on navy, a tonal crest, a grey-on-grey
logo. That is where both mechanisms live.

## 3. Metadata worth having, if it is cheap

In `job.json`, or just in an email:

| field | why it matters |
| --- | --- |
| fabric | changes underlay and pull compensation; a number without it has been wrong here twice |
| hoop | **decides the scale.** A photograph carries no ruler, so without this the physical size is invented — see `coverage_audit.A_TIER_PARAMS` |
| colours | what was actually ordered, not what we would guess |
| what the customer paid / how long it took | the only route to a business-currency comparison |

## 4. What we do NOT need

* Files cleaned up for us.
* Anything under NDA or with identifying customer detail — a job pair is useful with the
  brand removed.
* More generated or parametric corpus material. There is plenty; it is not the gap.

---

## What is already here, and why it is not enough

The standing sixteen (`coverage_audit.fixtures()`) are ten synthetic bench fixtures, four
parametric corpus images, and two real photographs **of** finished embroidery. Two
photographs of a sew-out are not a sew-out. No number in this repository has been checked
against thread.
