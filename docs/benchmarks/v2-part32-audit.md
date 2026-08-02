# v2 Part 32 — the neckline test: an inverted matte, caught and gated

**Date:** 2026-08-01 · New user test: a dense floral neckline design on a BLACK
ground — ~25 flowers, hundreds of leaves, the classic gala-dress layout.

## The failure

First run: **1 object, 89 stitches** out of a design with hundreds of elements.
The mask told the story: U2-Net decided the *subject* of the image was the empty
black **neck opening** — the V of bare fabric between the flowered arms — kept
that (15.6% of frame, almost none of it ink), and discarded every flower.

`_reclaim_ink` could not repair it, correctly: the missed embroidery is one
35%-of-frame border-touching component, and both reclaim caps exist precisely to
refuse things with that signature.

## The fix: audit the matte against the ink evidence

The matte is now trusted only when it covers a minimum share of
strongly-non-substrate pixels. Calibrated across every fixture:

| Input | Matte ink-recall |
|---|---|
| 8 of 10 corpus fixtures | 0.92 – 1.00 |
| fixture 03 (gradient bg) | 0.709 |
| fixture 09 (photographic bg) | **0.407** — legitimately low: its backdrop counts as "ink" by colour distance |
| **neckline failure** | **0.004** |

Gate: **0.2** — far under the legitimate minimum, 50× above the failure. Below
it, the classical tiers (flood-fill from the border, built exactly for
uniform-substrate artwork) take over.

**The calibration run caught my own first draft:** 0.5 seemed safe until the
table showed fixture 09 at 0.407 — the gate would have caused the exact
regression it guards against. Pinned in the test's docstring.

## Result

| | Before | After |
|---|---|---|
| Objects | 1 | **330** |
| Stitches | 89 | **19,775** |
| Distinct threads | 1 | **9** — two-tone petals (magenta `#942041` + lavender `#985ca3`) and two greens (`#415c2d`/`#548c31`) recovered by Part 31's gradient split |
| Segmentation tier | rembg (inverted) | **floodfill** (fg 43.3%) |
| Interior / edge / spill | — | 97.8 / 93.5 / 14.9 |
| Floor / density flags | — | **0 / 0** |
| Runtime | 34.7s | 18.7s |

Black flower centres survive as knockouts — correct for a black garment, where
they are the base fabric showing. Every stitch-safety gate holds on a 330-object
design.

## Gates
pytest **734 + 2 xfailed** (1 new inverted-matte test) · ruff **19** · stream
locks + reclaim suite green (corpus recalls all far above the gate).
