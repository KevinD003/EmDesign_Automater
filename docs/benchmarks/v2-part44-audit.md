# v2 Part 44 — R003: a committed visual-regression harness, and the two defects it found immediately

**Date:** 2026-08-03 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** rank 3 of the reviewer's plan — *"Commit visual-regression harness
(SSIM + pixel diff). Scratchpad scripts caught 4 real defects but were never committed."*

The harness is committed and green. Within an hour of existing it found **two real
defects that every existing test and metric scored as fine** — one of them a content-loss
regression I introduced two parts ago. That is the whole argument for R003, made by R003.

---

## 1. What shipped

**`app/services/stitch_render.py`** — a deterministic picture of what a design *sews*.
Pure function of the `Design`: same input, byte-identical PNG. It draws the stitch
**stream**, not the object contours, because the stream is what the machine receives — a
region whose contour is perfect but whose fill never got emitted looks correct in a
contour drawing and blank here.

Thread is laid as a swept band rather than `cv2.line(..., thickness)`, whose covered width
depends on segment angle (5.00px axis-aligned vs 4.25px at 45° for the same nominal
width). Without that, an honest change of fill angle would read as a coverage change.

**`scripts/visual_regression.py`** — render, compare to committed baselines, write a diff
strip, and accept intended changes.

```
scripts/visual_regression.py                 # check
scripts/visual_regression.py --update        # accept as baseline
scripts/visual_regression.py --contact-sheet # all ten in one image
```

SSIM is implemented on OpenCV/NumPy (11×11 Gaussian, Wang et al.) rather than pulling in
scikit-image for one twenty-line function that every future install would pay for.

**`tests/test_visual_regression.py`** (14 tests + 1 xfail) puts it in the default suite.
**`tests/visual/baselines/`** — ten committed PNGs, ~700KB total.
**`run_quality_bench.py`** now reports the visual diff after the numbers (`--no-visual` to
skip). The numbers have always said how much thread went down; they have never said
whether it looks right.

**`tools/visual/app-screenshots.mjs`** — the browser half, also committed. It drives the
real app in Chromium and captures 7 pages × light/dark, failing on uncaught JS errors.

## 2. On the 0.85 threshold — measured, and it would not work

The plan proposed *"fail on SSIM < threshold (0.85 configurable)"*. Measured, that gate
catches nothing here.

Because the renderer is a pure function, an **unchanged pipeline scores SSIM 1.000000
exactly** on all ten fixtures. So the question is what a *real* change scores. Disabling
the penetration floor — a genuine pipeline change — gives:

| Fixture | SSIM |
|---|---:|
| 05_wordmark_caps | 0.909 |
| 06_wordmark_script | 0.924 |
| 07_circular_badge | 0.956 |
| 08_mascot_detail | 0.951 |
| 03_gradient_soft_subject | 0.979 |
| 01_flat_2color_logo | 0.988 |
| 10_low_contrast_subject | 0.993 |
| 04_thin_line_outline | 0.993 |
| 09_nonuniform_background | size changed |

Nine of ten detected — and **every one of them scores above 0.85**. A 0.85 gate would have
passed the entire change silently. The gate here is **0.995**: on a deterministic renderer
there is no noise to allow for, and a loose threshold on a deterministic instrument is how
a harness gets ignored. `test_the_gate_is_tight_enough_to_catch_a_real_change` pins the
argument in code, including the assertion that the change really does score above 0.85.

## 3. Defect one — the auth pages ignored light mode (fixed)

The browser pass captured every page in both themes, and the light and dark PNGs for
sign-in, sign-up and forgot-PIN were **byte-identical**, both dark. Mean pixel value 15.8
in each, against the dashboard's 247.5 light / 21.0 dark.

Cause: `.dz-root` carries the light/dark token set, selected by a `data-theme` attribute.
`DashShell` stamps it. `AuthPages` rendered `<div className="dz-root dz-auth-root">` with
no attribute, so it always resolved to the dark default — a light-mode user went from a
white dashboard to a black sign-in page. The resolver was private to `DashShell`, so the
auth pages had no way to reach it even if someone had thought to.

Fixed by extracting `lib/theme.ts` (`initialTheme`, `saveTheme`, injectable `ThemeEnv` so
it is testable in node) and using it in both. Verified in the browser afterwards: auth now
reads 247.0 light / 15.8 dark, tracking the dashboard.

Guarded by `lib/theme.test.ts`. A DOM test would be the natural check, but the frontend
has no jsdom and no testing-library, and adding both to catch one missing attribute is a
poor trade — so it scans the source for `.dz-root` render sites without `data-theme`.
Checked against the pre-fix source: it flags it. Against the fixed source: it passes.

## 4. Defect two — fixture 02 lost its wordmark in Part 41 (**not** fixed, deliberately)

The contact sheet shows `02_logo_fine_text_3color` as a green card with a yellow dot and
**no text at all**. The source artwork reads "NORTHFIELD / EST. 1974 · SUPPLY CO." in
white.

Bisected against `c62bf33`, the commit before Part 41:

| | before Part 41 | now |
|---|---|---|
| Colour stops | 4, including **`#fafafa` with 31 stitches** | 3 |
| Objects | 7 | 6 |
| Stitches | 6,221 | 6,185 |

Part 41 made a garment-coloured cluster never stitch on raster input, to stop thread being
laid on bare cloth between a design's elements. Here the white type sits inside a green
card and the page behind the card is also white, so the type reads as substrate and is
dropped whole.

**Two things about this are worth recording plainly.**

First, my Part 41 audit said *"All 10 byte-identity stream locks are unchanged... the
flat-art corpus is bit-for-bit identical."* The locks cover fixtures 04, 05, 06 and 07.
Fixture 02 is not among them. The claim was true and the conclusion drawn from it was
wrong — four locked fixtures are not "the corpus", and I wrote it as though they were.

Second, no metric caught it, and none could have: coverage is scored against the objects
that *were* emitted, so deleting an object improves every score it touches.

**Not fixed in this part, on purpose.** The obvious discriminator — keep a
substrate-coloured region that is *enclosed by other foreground* rather than contiguous
with the background — has to hold on the black neckline panel too, where the enclosed
regions between petals really are bare cloth and must stay unstitched. I probed that
hypothesis and could not reproduce the clustering conditions outside the full pipeline, so
I cannot yet measure both sides of the change. Shipping a rule I can only validate on one
side is exactly how the original defect got in, and the instruction that produced Part 41
("we never do the thread for background") is not one to regress by guessing.

It is recorded instead as `test_fixture_02_still_stitches_its_wordmark`, a **strict xfail**
carrying the measured before/after — so the committed baseline PNG cannot be mistaken for
approval of the current output. Tracked as **R011**.

## 5. What the harness does and does not cover

| | Python harness | Browser script |
|---|---|---|
| Runs in `pytest` | yes | no — needs both servers |
| Deterministic to the pixel | yes (SSIM 1.000000) | no; fonts and AA vary by machine |
| Gates a change | **yes** | no, screenshots are for looking at |
| Checks | the stitch stream the machine gets | the Konva canvas a user sees |

They answer different questions and neither replaces the other. Pixel-gating the browser
would produce failures that mean nothing, so it is not wired into `npm test`; it exits
non-zero on uncaught JS errors, which do mean something. A 401 while signed out is normal
and is filtered — a check that is red on every clean run gets muted within a week.

## 6. Verification

| Gate | Before | After |
|---|---|---|
| Backend suite | 803 passed, 2 xfailed | **817 passed, 3 xfailed** (+14, +1 recorded defect) |
| Frontend tests | 127 passed | **131 passed** (+4) |
| `tsc --noEmit` | clean | **clean** |
| `ruff check app` | 12 | **12** |
| Stitch stream locks | 4 pass | **4 pass, unchanged** |
| Visual baselines | — | **10/10 at SSIM 1.000000** |

## 7. Files

- `apps/backend/app/services/stitch_render.py` — new
- `apps/backend/scripts/visual_regression.py` — new
- `apps/backend/scripts/run_quality_bench.py` — reports the visual diff; `--no-visual`
- `apps/backend/tests/test_visual_regression.py`, `tests/visual/baselines/*.png` — new
- `tools/visual/app-screenshots.mjs` — new
- `apps/frontend/src/lib/theme.ts`, `theme.test.ts` — new; `DashShell.tsx`, `AuthPages.tsx` — fixed
- `docs/benchmarks/v2-part44-contact-sheet.png`

## 8. Next

R011 (the Part 41 substrate regression) now sits above the rest of the queue: it is
content loss, it is mine, and it is measured. Then R004 — stitch direction at 49.9°, which
the reviewer and I agree is the largest quality gap, and which this harness will finally
make visible in before/after form.
