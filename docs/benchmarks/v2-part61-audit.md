# v2 Part 61 — the aggressive profile on imported streams: safe, and twice vindicated

**Date:** 2026-08-07 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** close Part 59's stated residual — is `trim_profile=aggressive`
safe on imported machine streams, not just STITCHIQ-generated ones? Measurement
and validation; no default change.

**Decision: safe for imported streams too. Advertise generally, with one
sentence of caveat.** The trim-only guarantee held on every stream measured —
asserted per stream, not sampled — and every foreign-stream hazard the brief
named actually appeared in the population and was handled the way the rule's
physics say it should be. Two findings go beyond "no harm found": on machine
formats, the carried-path rule is not defensive engineering but **load-bearing
on 39% of trims**, and on PES round-trips the profile actively **repairs**
encoding-inflated trim schedules (2,435 → 583 on the panel).

---

## 1. The population

The repo's true foreign files are two small samples, so the population is
two-tier:

- **Foreign**: `sample.dst`, `sample.pes` — files this engine never generated.
- **Round-trips**: two tier-A designs exported to **dst, pes, jef, exp, vp3**
  and re-imported. This is the honest way to get machine-format stream shapes
  at scale: DST really splits long moves into jump chains at write time, and
  each format re-encodes the stream its own way. The re-imported Design is
  exactly what a user who opens such a file holds.

## 2. The measurement

Trim-only diff **asserted** on all 12 streams; conservative asserted to be the
identity on all 12.

| stream | trims → after | removed | jumps | stitches | chains (max) | path>hop | rule-differs |
|---|---|---:|---:|---:|---:|---:|---:|
| sample.dst (foreign) | 14 → 14 | 0 | 45 | 26 | 14 (3) | 14 | 0 |
| sample.pes (foreign) | 2 → 2 | 0 | 2 | 26 | 0 | 0 | 0 |
| A01.dst | 364 → 301 | 63 | 1,431 | 37,285 | 299 (19) | 319 | 112 |
| A01.pes | **1,059** → 318 | 741 | 1,060 | 37,386 | 0 | 544 | 28 |
| A01.jef | 442 → 315 | 127 | 1,698 | 37,285 | 345 (19) | 414 | 107 |
| A01.exp | 364 → 301 | 63 | 1,704 | 37,285 | 319 (19) | 318 | 93 |
| A01.vp3 | 365 → 274 | 91 | **14** | 37,285 | 0 | 0 | 0 |
| A03.dst | 663 → 561 | 102 | 2,668 | 54,070 | 637 (17) | 660 | 258 |
| A03.pes | **2,435** → 583 | 1,852 | 2,436 | 54,366 | 0 | 1,268 | 81 |
| A03.jef | 915 → 579 | 336 | 3,299 | 54,070 | 800 (18) | 908 | 247 |
| A03.exp | 663 → 561 | 102 | 3,299 | 54,070 | 663 (18) | 660 | 229 |
| A03.vp3 | 664 → 478 | 186 | **17** | 54,070 | 0 | 0 | 0 |

*chains* = trims followed by more than one jump; *path>hop* = trims whose
carried path exceeds the first hop; *rule-differs* = trims a naive first-hop
rule would have decided differently from the carried-path rule.

## 3. What the hazards turned out to be

**Jump chains are the norm on machine formats, and the path rule is
load-bearing.** On A03.dst, 637 of 663 trims are followed by a chain (up to 17
jumps), the carried path exceeds the first hop on 660 of them, and a naive
first-hop rule would have decided **258 trims — 39% — differently**. Part 59
built the path walk for exactly this case on the strength of a synthetic test;
it is now measured as common on real machine encodings.

**PES round-trips inflate the trim schedule, and the profile repairs it.** The
PES writer/reader pair emits **1,435 consecutive double-trims** on the panel —
2,435 TRIMs where the original stream had 663 — essentially one per jump. The
aggressive profile takes it to **583**, within 4% of the native stream's 559.
The dropped trims are cuts the encoding invented on moves the original design
carried; removing them restores the design's intent. Double-trims decide
*together* (both measure the same carried thread), which is now pinned by a
test — a split decision would be an incoherent cut schedule.

**VP3 encodes almost no explicit jumps** (17 for the whole panel — one per
colour stop): the inter-object move is implied by displacement, so every trim's
carry is the straight-line distance. That is why VP3 removes more trims (186 vs
DST's 102): without travel encoded, some carries genuinely measure shorter.
The rule is still measuring the stream's own truth — the machine sewing that
file makes one direct move — so this is a property of the encoding, not an
error. It is also the one caveat worth a sentence when advertising.

**The unmeasurable case exists in real data and is kept.** Each VP3 round-trip
ends on a trailing trim with no following stitch; its carry is +inf and it is
never dropped. Pinned by a test.

**Trim-before-colour-change**: zero occurrences in all 12 streams; the guard
(carry = +inf, never dropped) remains covered by Part 59's synthetic test.

## 4. Decision

**Safe for imported streams. Advertise the feature generally.** The scoping
options the brief offered — "STITCHIQ-only for now" or "a narrower rule" — are
not supported by the measurements: no stream produced a drop that the carried-
thread physics does not justify, and the shapes our generator never emits
(chains, double-trims, trailing trims, jump-free encodings) are all handled and
now all pinned.

The one sentence of caveat for user-facing copy: *on formats that do not encode
travel explicitly (e.g. VP3), "under 10 mm" is measured over the machine's
direct move* — which is what that machine will actually do.

Not changed, deliberately: the default stays `conservative`; no UI change; no
routing work; no reopened lines.

## 5. Gates

| Gate | Result |
|---|---|
| Imported population measured | ✅ 2 foreign + 10 machine-format round-trips, all five formats |
| Trim-only diff on imports | ✅ **asserted** per stream, all 12 |
| Hazards specifically hunted | ✅ chains (max 19), double-trims (1,435), trailing trims, jump-free encodings, first-hop divergence (up to 39%) |
| Explicit scope decision | ✅ **general**, one-sentence caveat |
| Tests for discovered invariants | ✅ 3 new: trailing trim kept, double-trims decide together, DST round-trip trim-only + rule-exact |
| Backend suite | ✅ **912 passed, 2 xfailed** in 816.92 s (909 + 3 new) |
| No default change / stream locks / baselines | ✅ conservative is the identity; locks 4/4, baselines 10/10 |
| `ruff check app` | ✅ 12, the standing baseline |

## 6. Files

- `apps/backend/scripts/measure_import_trim_safety.py` — the population, the
  assertions, and the hazard scan
- `apps/backend/tests/test_part59_trim_profiles.py` — +3 imported-stream
  invariant tests (12 total in the file)
