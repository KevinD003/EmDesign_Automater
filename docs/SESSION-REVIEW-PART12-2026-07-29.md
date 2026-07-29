# Session review — v2 Part 12

**Date:** 2026-07-29 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Full audit:** [`docs/benchmarks/v2-part12-audit.md`](./benchmarks/v2-part12-audit.md)
**Launch assessment:** [`docs/LAUNCH-READINESS-GAPS.md`](./LAUNCH-READINESS-GAPS.md)

## Headline

Part 11's five open questions all have real answers, the corpus is **byte-identical** on every
stitch stream, and the launch-readiness research corrected the brief in three places: **pull
compensation, machine-format export, and a composite quality score already exist and are tested** —
they live in subsystems Parts 0–11 never audited, which is why the audits never mentioned them.

## Part A scorecard

| Item | Outcome |
|---|---|
| A1 discriminator evidence | `scripts/discriminator_search.py` committed with tests. **100% of violating reversals (590/590 sampled + both real fixture-07 cases) are satin-realizable as the same coordinates** — individual-triple separation is impossible, constructively. Distributional caveat measured and stated |
| A2 side preference | Measured: fixed return-preference loses 49.5% of asymmetric turnarounds (mean excess 0.58mm). **Shipped adaptive** (smaller merged stitch wins, ties keep return → corpus byte-identical, confirmed by bench). Losing case pinned as a regression test |
| A3 unwired paths | `_edge_walk` **wired** and proven against an adversarial spike sweep (raw: violations at 2 of 21 lengths; wired: zero). `_center_walk` **proven structurally unable to violate** (monotone advance + isometry → pairs ≥ 2·step ≈ 4mm) and left unwired with a property test instead of dead code |
| A4 fabric testing | **Cannot be executed from this environment and was not faked.** `docs/FABRIC_TEST_PROTOCOL.md` committed: fabrics, ladders, pile-up patch, acceptance rules per constant. The 0.30-vs-0.5mm reconciliation is resolved: industry 0.5mm is a stitch-length rule = `MIN_STITCH_MM = 0.5` exactly; 0.30mm bounds a different quantity. Documented at the constant |
| A5 metric successor | `density_metrics`: penetrations per 0.5mm cell, order-independent — catches stacked objects, repeat passes, and the contour-seam same-hole pair the triple test is structurally blind to (blind spot discovered while building A3's adversarial case). Flag at 14 = 2× healthy-corpus max, provisional, tied to the protocol. In the bench JSON as a new additive field |
| A6 lint-claim CI | `scripts/verify_lint_claim.py` + CI step: audits embed `LINT-VERIFY: findings=N files=...`, CI re-runs ruff and fails on mismatch. This audit carries the first marker (15 over eight files), verified before commit. Research also found CI ran **no lint at all** before this |

## Part B — determinations (full table with file:line evidence in LAUNCH-READINESS-GAPS.md)

exists: pull compensation (fabric-aware, tested) · machine export (DST/PES round-trip tested)
partial: fabric profiles (pull only — density/underlay are global constants) · quality report
(0–100 score exists, not persisted/auto-run; hoop-fit advisory only) · lettering (rasterize-then-
digitize; no kerning; `text_mode` is dead code) · pathing (color grouping real; 964/979 of fixture
07's jumps are *within* objects, which no existing optimizer touches)
absent: real-world corpus (documented licensing reason) · physical machine testing

Notable bugs surfaced by the research, left as plan items per the brief's scope rule:
`/api/formats` advertises "vip" which pyembroidery cannot write; `text_mode` and a stale comment in
`digitize_image`; JEF/EXP/VP3/XXX writers have no tests.

## Decision points flagged (not assumed)

Lettering scope for launch · untested export formats (test or trim the advertised list) ·
fabric-specific underlay type · when to auto-run path optimization. And the standing one, now
sharpened by audit §9.5: tier 1 of the plan (fabric sew-outs) requires a human with a machine —
every constant-validation item funnels through it.

## Verification

```
pytest — WITH rembg:     141 passed   (was 123; 18 added)
pytest — WITHOUT rembg:  141 passed
vitest:                  57 passed
corpus:                  every stitch stream byte-identical to v2-part11; only addition: `density`
floor violations:        0 (corpus + all three probes)
coverage:                digitizer 95% · measure 95% · discriminator 98% · verify_lint 93% · bench 65% (pre-existing)
lint:                    LINT-VERIFY: 15 over eight touched files, machine-verified; 8 introduced findings fixed pre-commit
secrets:                 clean
```
