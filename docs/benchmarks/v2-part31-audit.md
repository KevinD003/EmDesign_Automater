# v2 Part 31 — gradient-band recovery: the teal comes back

**Date:** 2026-08-01 · Executes fix #1 of the Part 30 comparison's remainder
list (gradient colours), scoped by an observation that changes the problem: the
source is EMBROIDERY, so its "gradients" are literally discrete thread bands.
Recovering the dropped colours as bands is faithful rendering, not an
approximation of blending.

## Mechanism

`_split_bimodal_clusters` (textured input only): after k-means assignment, each
cluster's members are probed with a k=2 sub-clustering; when the two modes are
≥30 BGR apart AND each owns ≥30mm², the cluster is two threads the colour cap
merged — split, capped at 3 recovered shades ranked by separation × size, each
half re-centred on its own median.

## Two diagnosed blockers before it worked

1. **The ambiguous-blend cut was swallowing the teal.** On flat artwork a pixel
   equidistant from two palette colours is an anti-aliasing halo and rightly
   dropped; on a photograph it is a real transition thread. The peacock's whole
   teal band went to −1 before the split scan could see it — the instrumented
   scan only found teal (`#507064`, 3,221px, gap 49.8 inside the BROWN cluster,
   of all places) with the cut off. The cut is now skipped for textured input.
2. **Threshold off by 3.** Mint|pale measured gap 32.8 against a 36 threshold;
   lowered to 30 with the measured pairs recorded at the constant.

**Honestly unrecoverable at this stage:** the deep-navy tail shadow
(`#122b4f`, 35 from its partner) is merged by mean-shift itself (colour radius
52) before any downstream stage sees it; recovering it would re-shatter the
fills that radius exists to heal. Recorded, not hidden.

## Result

| | Part 30 | Part 31 |
|---|---|---|
| Distinct threads | 8 | **10** |
| Teal (source `#4e7164`) | ✗ absent | **✓ `#4f7064`** — one hex unit off the source thread |
| Eye iris | single olive | **two-tone olive** (`#9fa042` / `#b7b347`), matching the source's ringed iris |
| Wing quills | outlined mass | clean separated gold bars — best yet |
| Interior / spill | 97.5 / 9.1 | **97.8** / 10.9 |
| Floor / density flags | 0/0 | **0/0** |
| Warnings | — | "+2 extra shades recovered from colour gradients" — explained, not silent |

Corpus: untouched (every new path gated on `is_textured`); stream locks green.

## Gates
pytest **733 + 2 xfailed** (2 new split tests) · ruff **19** baseline · floor 0.
