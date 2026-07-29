# v2 Part 15 Audit — the fidelity loop, round two: edge truth and the pro finish

**Date:** 2026-07-29 · **Tag:** `v2-part15` · graded against [`v2-part14`](./v2-part14-summary.json)
**Strips:** [`01`](./v2-part15-fidelity-01.png) · [`02`](./v2-part15-fidelity-02.png) ·
[`07`](./v2-part15-fidelity-07.png) · [`08`](./v2-part15-fidelity-08.png) · [`10`](./v2-part15-fidelity-10.png)

Continuation of the input-vs-output loop on the user's direction ("repeat until it matches").
Two fixes this round, each diagnosed by painting before touching code, each checked visually after.

**Interior AND edge band hit 100.0 / 100.0 on every flat-colour fixture** (01, 02, 09, 10) — the
first 100s in this project's history — with **floor violations 0** under a *widened* metric and
classification identical.

LINT-VERIFY: findings=14 files=apps/backend/app/services/digitizer.py apps/backend/app/services/optimizer.py apps/backend/scripts/measure_stitch_quality.py apps/backend/tests/test_lettering.py apps/backend/tests/test_stitch_quality_metrics.py apps/backend/tests/test_fidelity.py

---

## 1. Fix 1 — the registration crescent: fills were losing every row's first stitch

Painting fixture 02's sun stitches over its region showed rows visibly receding from the edge on
one side. Mechanism: adjacent fill rows connect with a stitch of exactly one row pitch — 0.45mm on
cotton — which is **under `MIN_STITCH_MM = 0.5`**, so `_coalesce_short` deleted every row's first
point. On straight edges the replacement diagonal hugged the edge and hid the loss; on a curve the
diagonals cut the arc — the crescent. A 0.4–0.45mm row connection is *the industry-standard
practice* (it IS the pitch every density guide prescribes), so the threshold was wrong for fills:
they now keep stitches down to `FILL_ROW_CONNECT_KEEP = 0.95` of their own pitch.

**Consequence stated up front:** the corpus's `stitches_under_0_5mm` count goes **9 → 1,201**.
Those are the legitimate pitch-length connections that were previously being *deleted* — which was
precisely the defect. The quality report's tiny-stitch threshold moved 0.5 → **0.3mm** to match
(same grounding as the penetration floor, same protocol pending), so proper fills are no longer
penalised by hundreds of false findings.

## 2. Fix 2 — satin borders on fills: the difference between rows of thread and embroidery

Every professional digitizer finishes a filled logo shape with a narrow satin border over the
contour — it is most of the perceived quality gap to the competitor tools the user pointed at.
Implemented as `_fill_border` on the existing appliqué helper, with three hard lessons applied:

- **`_satin_border` carried the Part 4 alternating-lead bug** (per-station side swap → same-side
  pitch-length pairs → coalesce deletes half the penetrations). Fixed to strict A0 B0 A1 B1.
- **The floor is enforced at generation**: on a pixel-staircase contour the local normal swings
  station to station, and the first version emitted **830 sub-floor same-side pairs on fixture
  07's rings alone** (0.057mm). A station now waits until BOTH sides have advanced a full floor —
  the same both-boundaries rule Part 5 built for columns. Downstream repair could never have fixed
  830 without shredding the border, so generation-time was the only correct layer.
- **The safety metric was widened to ALL objects** (it skipped TATAMI before): fill borders zigzag,
  so tatami objects now carry satin-style pairs the floor must govern. The zigzag test still
  self-selects — plain rows and running stitch contribute nothing — so historical numbers remain
  comparable. **Corpus floor violations under the widened metric: 0.**

Borders run the outer contour AND kept holes (fixture 02's sun rim), centered on the contour,
area-gated (`FILL_BORDER_MIN_MM2 = 30`) so specks aren't double-stitched, width
`FILL_BORDER_MM = 1.2` from the 1–2mm range in digitizing guides. The floor backstop after
coalescing is now unconditional (it was satin-only; borders zigzag inside tatami objects).

## 3. Corpus effect — the trade, stated plainly

| Fixture | interior | edge band | spill | stitches |
|---|---|---|---|---|
| 01 | 98.7 → **100.0** | 94.6 → **100.0** | 2.1 → 4.5 | 1,632 → 3,663 |
| 02 | 99.1 → **100.0** | 94.0 → **100.0** | 1.6 → 3.9 | 3,406 → 5,729 |
| 03 | 97.9 → 99.3 | 92.6 → 95.1 | 7.7 → 11.6 | 3,228 → 5,105 |
| 07 | 97.8 → **99.1** | 95.3 → **98.1** | 4.8 → 6.2 | 7,825 → 13,036 |
| 08 | 96.4 → 97.1 | 91.8 → **95.6** | 4.0 → 4.0 | 5,037 → 6,470 |
| 09 | 99.0 → **100.0** | 93.3 → **100.0** | 3.9 → 6.8 | 1,006 → 2,157 |
| 10 | 98.6 → **100.0** | 94.4 → **100.0** | 3.0 → 4.7 | 2,389 → 5,386 |
| 04/05/06 | unchanged (satin objects — no fill borders) | | | |

Costs: stitch counts rise 30–125% on bordered fixtures (borders are real thread; a 95mm badge at
13k stitches is inside the range commercial badge designs run), spill rises ~2–4pp **by design**
(the border is centered on the contour, so half its width lies outside the segmented outline — that
is it covering the artwork edge the segmentation traced), jumps +3–12 per fixture (one hop per
border ring). Floor 0, over-limit 0, density flagged 0, classification identical.

Visual: fixture 10 is now unmistakably its input (circle, rounded square, legible LC); 01's
triangle-in-circle is crisp; 02 reads as the actual logo; **07's HARBOR CLUB is legible for the
first time** — the letter-hole rims outline the text. The honest remainder: 07's small circular
ring text is still mush and 08's ear/head fill texture is patchy — both are the small-lettering /
small-region ceiling already ranked the top competitive gap.

## 4. Also fixed on the way

`test_donut_hole_is_not_filled`'s stitch-count proxy died (a ring now earns two borders and
out-stitches the disc); rewritten to assert the property itself — zero penetrations deep inside the
hole (min-radius bound, since the traced hole isn't perfectly round and the rim border legally
reaches ~0.6mm in). First rewrite used the max-radius bound and failed against the border's own
inner edge — the 45 "violations" were all at exactly rim depth, i.e. the test was wrong, not the
stitches; both bounds are recorded here so the next reader doesn't re-derive them.

## 5. Verification

```
pytest — WITH rembg:     170 passed   ·   WITHOUT rembg: 170 passed
vitest: 64 passed · typecheck clean
ruff over touched files: 14, all pre-existing in digitizer.py (LINT-VERIFY above, machine-checked)
secrets scan: clean
sizes: _satin_border 43 lines, _fill_border 22 — under the limit
constants added: FILL_ROW_CONNECT_KEEP, FILL_BORDER_MM, FILL_BORDER_MIN_MM2 (all grounded);
TINY_STITCH_MM 0.5 → 0.3 (grounded against the floor; fabric protocol pending as ever)
```

## 6. What to attack

1. Small lettering remains THE ceiling (07 ring text, 08 texture) — satin quality on sub-4mm
   glyphs, the same top gap as the competitor comparison. Everything else visible is now detail.
2. Spill's meaning changed: half a border width lies outside the traced contour by design. Should
   the metric's outline be dilated by `FILL_BORDER_MM/2` for bordered objects, or should spill keep
   flagging it so the trade stays visible?
3. `stitches_under_0_5mm` is no longer a defect count (it now counts standard row connections).
   Rename/re-band the bench field (e.g. under-0.3) or keep for cross-part comparability?
4. Border wobble on rough contours: the rim follows the smoothed trace, but a curvature-adaptive
   station step would tighten it further.
