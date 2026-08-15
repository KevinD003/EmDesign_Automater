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
