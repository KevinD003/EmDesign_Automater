# STITCHIQ v2 — Part 1 Post-Review Fix Report
**Date:** 2026-07-28 · **Branch:** `claude/code-quality-improvements-hyu6dg` · **Commit:** `4e7c861`

> Response to the reviewer's blocker: a failing test that the Part 1 report claimed was passing.
> The reviewer was right. This documents what was wrong, why I did not see it, and the fix.

---

## 1. The reviewer was right, and the failure mode is worse than one test

The Part 1 report's §7 claimed `pytest tests -q` → **88 passed**. The reviewer installed the deps,
ran it, and got **1 failed, 87 passed**.

Both numbers were real. The difference is the environment:

| Environment | Result |
|---|---|
| With optional `rembg` installed (mine) | 88 passed |
| **Documented install** — `requirements.txt` + `requirements-dev.txt`, no rembg (theirs, and CI's) | **87 passed, 1 failed** |

Reproduced deliberately with `STITCHIQ_DISABLE_REMBG=1`. So the suite was **environment-dependent**,
and I verified it in one environment and reported the number as if it held everywhere. That is the
substantive error — not a typo, and not a stale number. The gated review process caught exactly what
it exists to catch.

## 2. Root cause — the bug was already in my own audit, unconnected

`docs/benchmarks/v2-part1-audit.md` §6.3 already recorded fixture 05 gaining "a spurious colour…
a light halo at Δ21.4 from white: too far to trip the substrate rule, too close to be a real layer."

That is the *same bug* as the failing test. I logged it as a cosmetic open item on one fixture and
did not connect it to a previously-passing regression test. The reviewer's instinct — that it "will
keep resurfacing anywhere anti-aliased edges meet a near-white/near-background colour" — was correct.

**Mechanism.** Rendering and rescaling leave a 1–2px anti-aliased band wherever two colours meet.
Those pixels are *blends*, not design colours. They were fed to k-means as ordinary samples, so
given a 2-colour budget on one-colour artwork, the second centroid landed on the halo. Black text
came back as `{black, near-white halo}` = two thread stops.

## 3. The fix — at root, not special-cased for lettering

Both changes are in `digitize_image` and apply to every input, per the reviewer's instruction not to
patch the lettering path.

1. **The palette is learned from the foreground's interior.** `cv2.erode` the foreground mask before
   clustering, so only colours that own real area can seed a centroid. Every foreground pixel is
   then assigned to the nearest palette entry — the halo is *absorbed* into a real colour rather
   than *promoted* to its own.
2. **Ambiguous blend pixels are left unassigned.** The first change alone regressed three other
   tests: assigning each blend pixel to its nearer centroid grew every shape by ~1px per side, which
   pushed a 3.6mm satin bar over the 4mm satin/tatami threshold and silently reclassified it as a
   fill. A pixel whose two nearest palette distances are within √0.5 of each other now belongs to
   neither layer.

The substrate/enclosure logic that fixed fixtures 02, 07, 08 and 09 is **untouched**, as required.

### A third defect found while fixing this
Chasing the satin-width regression showed U2-Net emits a *soft matte*, and the 50% level of that
ramp sits **outside** the true object edge — so `alpha > 128` was fattening every shape. Measured on
a bar of true width 3.60 mm:

| alpha threshold | measured width |
|---|---|
| > 128 (was) | 4.45 mm |
| > 192 | 4.14 mm |
| > 224 (**now**) | **3.82 mm** |

This was mis-sizing satin-vs-tatami classification on **every** rembg-segmented input, not only in
tests. Found only because the reviewer's blocker forced the investigation.

## 4. Verification — exact output, both environments

```
########## pytest — WITH rembg installed ##########
90 passed, 1 warning in 18.71s

########## pytest — WITHOUT rembg (documented install / CI path) ##########
90 passed, 1 warning in 5.46s

########## pytest — collected count ##########
90 tests collected in 0.44s

########## vitest ##########
 Test Files  9 passed (9)
      Tests  57 passed (57)

########## typecheck ##########
> tsc --noEmit          (no output = clean)
```

90 collected, 90 passed, zero failures, on **both** segmentation backends.

**A new parametrised regression test** (`test_single_color_text_is_one_stop_on_every_segmentation_tier`)
pins both tiers explicitly, so a machine that happens to have the optional dependency can never
again hide a failure from one that does not. That is the durable fix for the *process* error, as
distinct from the code error.

## 5. Bench re-run (`--tag v2-part1-fix`) — Part 1 wins intact

| Fixture | colours: ask / v1 / part1 / **fix** | jumps part1→fix |
|---|---|---|
| 01 flat_2color_logo | 2 / 2 / 2 / **2** | 63→63 |
| 02 logo_fine_text_3color | 3 / 2 / 3 / **3** | 167→171 |
| 03 gradient_soft_subject | 4 / 3 / 4 / **4** | 513→452 |
| 04 thin_line_outline | 2 / 1 / 1 / **1** | 286→285 |
| 05 wordmark_caps | 2 / 1 / 2 / **1** ← fixed | 186→174 |
| 06 wordmark_script | 2 / 1 / 1 / **1** | 119→101 |
| 07 circular_badge | 4 / 2 / 3 / **3** | 868→866 |
| 08 mascot_detail | 5 / 3 / 5 / **5** | 385→385 |
| 09 nonuniform_background | 4 / 4 / 2 / **2** | 41→41 |
| 10 low_contrast_subject | 4 / 3 / 3 / **3** | 140→150 |

- **02, 07, 08, 09 unchanged** — the substrate/enclosure wins survived, as required.
- **Fixture 05 now returns exactly 1 colour** (reviewer's question 3: yes).
- Jumps improved **2,768 → 2,688**; sub-0.5 mm stitches 3 across all ten; **0** over the 12.7 mm limit.

## 6. One honest consequence you should weigh

**"Colours matching the request" now reads 4/10, down from 5/10.** That looks like a regression and
is not one: fixture 05 returns 1 colour where it previously returned 2, and 1 is *correct* —
"SUMMIT" is a single ink colour, and the 2 was the bug just fixed.

This exposes a flaw in the acceptance criterion itself. The brief asks for "requested == returned
for fixtures 01, 02, 05, 07, 08", but **05's artwork contains one ink colour and 07's contains
three**. Satisfying a request for 2 and 4 on those would require emitting duplicate thread stops —
i.e. reintroducing exactly this defect. Measured against *true design colours* rather than the
requested number, 01/02/05/07/08 are now all correct.

Suggest scoring future parts on true-colour fidelity rather than request-matching. I have not
changed `FIXTURE_PARAMS` to make the metric look better, since that would break like-for-like
comparison with the v1 baseline.

## 7. Documentation corrected

`docs/benchmarks/v2-part1-audit.md` §7's false "88 passed" claim is **corrected in place with the
correction left visible** (a blockquote stating what was claimed, what was actually true, and that
the reviewer caught it) rather than silently edited. §8 documents the fix. `STATUS.md` is at v36.

## 8. What to re-verify

```bash
git checkout claude/code-quality-improvements-hyu6dg && git pull
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # deliberately NO rembg
python tests/make_fixtures.py
python -m pytest tests -q                                  # expect: 90 passed
python scripts/run_quality_bench.py --tag v2-part1-fix
```
Then optionally `pip install -r requirements-features.txt` and re-run — expect **90 passed** again.
That second run is the check that actually matters, since it is the one I got wrong last time.
