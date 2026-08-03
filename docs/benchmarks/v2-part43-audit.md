# v2 Part 43 — R002: the enum stops advertising stitches the engine cannot sew

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** rank 2 of the reviewer's plan — *"Audit & delete 16 phantom StitchType enum
members. Type system lies about capabilities."* Also gap #5 of the industry-comparison deck.

---

## 1. The measurement, before any opinion

Both the reviewer and the deck asserted the count from reading the code. Reading it is how
you get the number wrong. The honest test is to **rebuild the same design under every enum
member and hash the resulting stitch stream**:

```
23 enum members  →  9 distinct outputs

  ed07c61881d1  n=598    12x  TATAMI, STEMSTITCH, CROSS_STITCH, ZIGZAG, E_STITCH,
                              MOTIF_FILL, MOTIF_RUN, ACCORDION_FILL, LAYDOWN,
                              PHOTO_STITCH, GRADIENT_BLEND, CHENILLE
  2464faa8cc87  n=28      3x  RUNNING_SINGLE, MANUAL, REDWORK
  1f9e62c47b10  n=53      2x  RUNNING_DOUBLE, BACKSTITCH
  ad3b6fa09fac  n=718     1x  SATIN
  b9773741285d  n=78      1x  RUNNING_TRIPLE
  6442279ef4dd  n=2974    1x  CONTOUR_FILL
  cccae8cfd184  n=4284    1x  SPIRAL_FILL
  285b4dc4a9c8  n=1494    1x  RADIAL_FILL
  6b40235faeb5  n=748     1x  APPLIQUE
```

So the real shape of the defect:

- **Eleven members produced a byte-identical tatami fill.** They fell through
  `rebuild_design`'s final `else`, which was a catch-all `_scanline_angled`. Ask for
  chenille, get tatami, no warning, no log line.
- **`BACKSTITCH` was byte-identical to `RUNNING_DOUBLE`** — a backstitch is not a double
  run, so the name was simply wrong.
- **`REDWORK` was byte-identical to `RUNNING_SINGLE`** — redwork is a *style*, not a stitch.
- **Nine behaviours were genuinely distinct**, and the ones the product sells (satin, the
  four fills, appliqué, the running family) all work.

**Two corrections to the record, including my own.** I previously reported "16 phantoms,
4 real". The measured answer is **13 names that do not mean what they say, 9 real
behaviours**. And the deck's "nothing surfaces it until someone picks one" is wrong about
the app: the properties panel only ever offered TATAMI / CONTOUR_FILL / SPIRAL_FILL /
RADIAL_FILL / SATIN / APPLIQUE. The phantoms were reachable **only through the public API
and the OpenAPI schema** — narrower than claimed, still a documented capability that
silently substituted a different stitch.

## 2. What shipped

**Deleted 13 members.** `StitchType` now declares exactly what the engine produces:

| Kept | Why |
|---|---|
| `SATIN`, `TATAMI`, `CONTOUR_FILL`, `SPIRAL_FILL`, `RADIAL_FILL`, `APPLIQUE` | distinct generators |
| `RUNNING_SINGLE`, `RUNNING_DOUBLE`, `RUNNING_TRIPLE` | distinct pass counts (1 / 2 / 3) |
| `MANUAL` | **not a generator — provenance.** It marks a path the user placed by hand so rebuild runs along it instead of re-deriving a fill. Producing the same stream as `RUNNING_SINGLE` is the intent, and the test records it as a declared alias rather than pretending it is distinct |

**Removed the catch-all.** `rebuild_design`'s final `else` no longer sews tatami — it
raises, naming the object and the type. This is the actual fix: the eleven phantoms existed
*because* that branch would silently accept anything, and deleting the names without
closing the branch would leave the next added member free to do the same thing.

**Legacy data still loads.** A design saved while those names existed would have 422'd on
open. `LEGACY_STITCH_TYPES` maps each removed name to the stream it really produced
(eleven → `TATAMI`, `BACKSTITCH` → `RUNNING_DOUBLE`, `REDWORK` → `RUNNING_SINGLE`), applied
by a `field_validator(mode="before")` on `DesignObject`. Old designs open and rebuild
**identically to before**; nothing new can be created with one, because the enum no longer
has them.

**Frontend enum mirrored**, with the same rule written down: do not add a name before the
generator exists.

## 3. Tests — `tests/test_part43_no_phantom_stitch_types.py` (15)

The guard has to be a property, not a list, or it rots the moment someone adds a member:

- **no two stitch types may produce the same stream** — the exact property that failed,
  parameterised over the whole enum, with `MANUAL → RUNNING_SINGLE` declared as the one
  intentional alias;
- every member rebuilds to a non-empty stream (nothing hits the new guard);
- an unknown type **raises** instead of sewing tatami;
- every removed name still loads and migrates to the stream it used to produce;
- the four fills stay genuinely different from each other.

## 4. Verification

| Gate | Before | After |
|---|---|---|
| Backend suite | 788 passed, 2 xfailed | **803 passed, 2 xfailed** (+15) |
| Frontend tests | 127 passed | **127 passed** |
| `tsc --noEmit` | clean | **clean** |
| `ruff check app` | 12 | **12** |
| Stitch stream locks | 4 pass | **4 pass, unchanged** |
| Distinct behaviours / declared names | 9 / 23 | **9 / 10** |

The stream locks matter here too: they cover `digitize_image`, which only ever assigned
four types, so removing the other nineteen must not — and did not — move a single stitch.

## 5. What this does *not* do

It does not implement cross-stitch, chenille, photo-stitch, motif fill or the rest. Those
are real features and several are genuinely wanted; they are now honestly **absent**
instead of dishonestly **present**. Re-adding any one is a one-line enum change once its
generator exists, and the new test will refuse it until then.

## 6. Files

- `apps/backend/app/models/design.py` — enum reduced to 10, `LEGACY_STITCH_TYPES`, migration validator
- `apps/backend/app/services/digitizer/pipeline.py` — catch-all `else` replaced by an explicit failure
- `apps/frontend/src/types/design.ts` — mirrored
- `apps/backend/tests/test_part43_no_phantom_stitch_types.py` — new
- `docs/EVALUATION-industry-comparison-verified.md` — triage of the deck this came from
