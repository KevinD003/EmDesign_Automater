# STITCHIQ User Guide

STITCHIQ turns images and text into machine-ready embroidery files, right in your
browser. This guide walks you through the whole workflow: opening the app,
digitizing an image, editing the result, reading the quality report, adding
lettering, and exporting a file your embroidery machine can stitch.

New here? Start with [Getting started](#getting-started), then
[Digitize an image](#digitize-an-image) — that's the five-minute path from a
PNG to a `.dst` file.

## Table of contents

- [Getting started](#getting-started)
- [Digitize an image](#digitize-an-image)
- [Editing your design](#editing-your-design)
- [The Quality panel](#the-quality-panel)
- [Lettering (Text)](#lettering-text)
- [Export, save & share](#export-save--share)

## Getting started

With both servers running (see the [README Quickstart](../README.md)), open
**http://localhost:5173** in your browser. The frontend talks to the API at
`http://localhost:8000`; interactive API docs live at
`http://localhost:8000/docs` if you ever want to poke the backend directly.

### The screen at a glance

**Top toolbar** — everything you can do lives here, left to right:

- **🧵 STITCHIQ** — the brand mark.
- **↶ / ↷** — Undo (Ctrl+Z) and Redo (Ctrl+Shift+Z). Every edit is undoable.
- **Tool buttons** — **Select** (select / pan, the default), then the manual
  drawing tools **Run**, **Satin**, and **Fill**. While drawing, extra
  **Finish ✓** / **⌫** (undo last point) / **Cancel** buttons appear.
  (**Lettering**, **Appliqué**, and **Shape** are visible but greyed out —
  they're coming in a later phase; use the **Text** action for lettering today.)
- **Action group** — **Open**, **Digitize**, **Text**, the export **format
  dropdown** (.DST / .PES / .JEF / .EXP / .VP3), **Save**, **Saved**, **Check**,
  **Quality**, **Optimize**, **Export**, **Package**, **Worksheet**, **Master**.
- **☁ Save / ☁ Open** — appear only when you're signed in; they save to and
  open from your cloud account.

Most action buttons are disabled until a design is loaded — Open or Digitize
something first.

**Canvas** — the middle of the screen. Your design renders here; this is where
you select objects and place points for the manual drawing tools.

**Right-hand panels**:

- **Quality** — the design's 0–100 quality score and its findings.
- **Properties** — settings for the selected object (density, underlay, pull
  compensation, and so on).
- **Color · Object List** — every object in stitch order, grouped by color.
- **Thread Palette** — the thread colors used by the design.

## Digitize an image

This is the headline feature: turn a picture into stitches.

1. Click **Digitize** in the toolbar and pick an image — **PNG, JPG/JPEG, BMP,
   or WebP**. Logos and other flat-color artwork digitize best; try the sample
   images in `apps/backend/tests/fixtures/quality_bench/` if you don't have one
   handy.
2. The **Digitize "your-file-name"** dialog opens and asks three questions:

   - **Fabric** — `cotton`, `polo/knit`, `denim`, `fleece`, `cap`, or `towel`.
     This is not cosmetic: the fabric choice drives per-fabric **pull
     compensation** (0.15–0.5 mm per side), fill and satin **density**, the
     **underlay** step, and the edge **inset**. A design digitized for fleece
     comes out visibly different from the same image digitized for cotton —
     pick the fabric you'll actually stitch on.
   - **Hoop (mm)** — `100x100`, `130x180`, `200x200`, or `260x160`. The design
     is sized to fit; hoop-fit is also checked later at validation (**Check**
     and **Export** both run it).
   - **Max colors** — 2–8, default 6. The image's colors are reduced to at most
     this many threads via k-means color separation. Fewer colors means fewer
     thread changes at the machine.

3. Click **Digitize** in the dialog. After a moment the result loads on the
   canvas.

### What you get

The digitizer produces **re-editable objects with real contours**, not a flat
stitch dump:

- **Tatami fills** for large regions, **satin columns** for narrow shapes,
  with **underlay** underneath.
- Letter counters (the holes in "A", "O", "e"…) are carved out, not stitched
  over.
- Each object keeps its outline, so you can reshape, restyle, and reorder it
  afterwards — see [Editing your design](#editing-your-design).

The design is **auto-scored** the moment it loads: check the **Quality** panel
on the right for the 0–100 score and any findings (details in
[The Quality panel](#the-quality-panel)).

### Opening existing files (Open)

**Open** loads two kinds of file, and the difference matters:

- **Machine formats** — `.dst`, `.pes`, `.pec`, `.jef`, `.exp`, `.vp3`, `.vip`,
  `.xxx`, `.sew`, `.u01`. These are raw stitch streams: you can view them,
  validate, optimize, and re-export them, but they are **not object-editable**.
  If you try a manual drawing tool on one, the app tells you: *"Manual tools
  need a blank or digitized canvas — imported files aren't editable
  object-by-object."* A sample to try:
  `apps/backend/tests/fixtures/sample.dst`.
- **STITCHIQ masters** — `.stiq.json` files (made with the **Master** button).
  These keep all objects and contours, so they reopen **fully editable**.
  Rule of thumb: save a Master alongside every machine-format export.

## Editing your design

A digitized (or manually drawn) design is a list of **color stops**, each
containing **objects** with real contours — so everything below is a
non-destructive edit, and every step is undoable.

### Selecting things

The left panel, **Color · Object List**, shows the stitching sequence:

- **Color stops** — one row per thread, in stitch order, with a color swatch,
  stop number, thread name, and stitch count. Click a row to select the stop;
  click it again to deselect.
- **Objects** — digitized designs additionally list their vector objects
  under each stop (e.g. `Fill 3`, `Satin 7`). Click one to select it.
  Imported machine files have no objects, so they only show color stops.

You can also click a stitch run on the 2D canvas to select its color stop
(the other colors dim); clicking empty canvas deselects.

What you selected decides what the **Properties** panel shows.

### Recolor, rename, reorder (color stops)

Select a color stop and the **Properties** panel offers:

- **Color** — a color picker; changes apply to the whole stop immediately.
- **Name** — rename the thread (e.g. "Sky blue" instead of "Color 2").
- **Order** — **▲ Up** / **▼ Down** move the stop earlier or later in the
  stitching sequence.
- **Catalog** and **Stitches** — read-only info for the stop.

This works for *every* design, including imported machine files.

### Snap a color to a real thread (Thread Palette)

Hand-picked colors are rarely threads you can buy. The **Thread Palette**
panel fixes that:

- Select a color stop, then **click any swatch** in the grid to apply that
  catalog thread (its color, name, brand, and catalog number) to the stop.
- Or click **↳ Nearest catalog thread to `#rrggbb`** — the server finds the
  closest real thread by **CIE Lab color distance** (perceptual, not raw RGB)
  and applies it in one click.

### Restyle an object (Properties)

Select an object in the left panel and the **Properties** panel switches to
object mode:

- **Stitch type** — the object's fill type, plus **Appliqué** (an appliqué
  object can be reverted to TATAMI or SATIN).
- **Density (lines/mm)** — 0.2–5; higher = denser coverage.
- **Angle (°)** — the fill direction. Disabled for satin objects: satin
  columns follow the shape's axis.
- **Underlay** — **None**, plus **Center walk** (satin) or **Edge walk**
  (fills).
- **Pull comp (mm)** — 0–2 mm of pull compensation per side.

Hit **Apply (rebuild)**: the server **regenerates the object's stitches from
its stored contour** with the new settings — nothing is nudged or faked
client-side. That's why this only works for objects that have a contour; a
contour-less object shows *"No contour stored — object is not regenerable."*
The rebuild is recorded in history, so **Undo** restores the previous
stitches.

### Undo ↶ / Redo ↷

Every edit — recolor, rename, reorder, rebuild, optimize, manual draw — goes
through the history stack. Use the **↶** / **↷** toolbar buttons or
**Ctrl+Z** / **Ctrl+Shift+Z** (Ctrl+Y also redoes; use Cmd on macOS).

### Manual digitizing (Run / Satin / Fill)

You can draw objects by hand:

1. Click **Select** first if you're mid-something, then pick a tool:
   **Run** (a running-stitch line, open), **Satin** (a column, closed shape),
   or **Fill** (a tatami-filled region, closed shape).
2. **Click points on the canvas.** Run needs at least 2 points; Satin and
   Fill need at least 3. A live polyline previews the shape.
3. Finish with the buttons that appear in the toolbar: **Finish ✓** commits
   the object (the server rebuilds it into stitches), **⌫** removes the last
   point, **Cancel** (or the Escape key) abandons the draw.

The new object joins the currently selected color stop (or the last stop, or
a fresh default color on a blank canvas). One constraint: manual tools need a
**blank or digitized** canvas. Try one on an imported `.dst`/`.pes` and the
app refuses: *"Manual tools need a blank or digitized canvas — imported files
aren't editable object-by-object."*

### 2D, TrueView 3D, and the stitch player

Above the canvas is a view toggle:

- **2D** — the working view: color-grouped stitch lines at physical thread
  width. Scroll to zoom, drag to pan, click a run to select its color stop.
- **TrueView 3D** — a realistic preview that renders stitches as lit thread
  tubes on a fabric plane. Drag to rotate, scroll to zoom.

Along the bottom, the **stitch player** animates the stitching sequence:
**▶ Play** runs the needle through the design, the slider scrubs to any
point (the counter shows e.g. `4,213 / 12,800 stitches`), and **↺ Reset**
shows the full design again. Great for checking the stitch *order* — what
gets sewn first, where the jumps happen — before you commit to a sew-out.

## The Quality panel

The **Quality** panel (right side) is a rule-based, honest report on how well
the design will stitch. It fills in **automatically** after every Digitize or
Text run; refresh it anytime with the **Quality** toolbar button (and it
re-scores itself after an Optimize that changed the design).

### The score

A **0–100 score with a letter grade**: ≥90 = A, ≥80 = B, ≥70 = C, ≥60 = D,
below that F. The number is color-coded — green at 90+, amber at 70+, red
below. Penalties come from the findings listed underneath, so the score is
never a mystery.

### The metrics grid

| Row | What it means |
| --- | --- |
| **Stitches** | Total stitch count. |
| **Jumps** | Jump count, plus the rate per 1,000 stitches when reported. |
| **Travel** | Total needle travel across jumps, in mm — dead machine time. |
| **Color changes** | Thread swaps at the machine. |
| **Trims** | Thread trims (each costs machine time). |
| **Max stitch** | Longest single stitch, in mm. |
| **Mean stitch** | Average stitch length, in mm. |

A `—` means the backend didn't report that value (typical for older saved
reports).

### Hoop fit and findings

Below the grid, a hoop line reads **Hoop fit: OK**, **Hoop fit: OVERFLOWS**
(the design is bigger than its declared hoop), or **Hoop: no hoop set**.

Then the itemized findings, each color-coded by severity:

- **Long stitches** over 12.7 mm (0.5") — thread-break / skip risk on most
  machines (error).
- **Tiny stitches** under 0.3 mm — thread shredding and needle wear (warning).
- **Too many color changes** (over 15) — long run-time at the machine
  (warning).
- **Jump rate** — jumps per 1,000 stitches, always reported for context:
  every trimmed jump costs machine seconds, so lower is faster to run (info).

No problems? You get a green **"No findings."**

### Check — pre-export validation

The **Check** toolbar button runs the pre-export sanity checks and pops a
report card: **✓ Ready to stitch** or **⛔ Issues found**.

- **Blocking issues (⛔)** — the design physically can't be stitched as-is:
  it has no stitches, or it **does not fit its declared hoop**.
- **Warnings (⚠)** — worth fixing but not fatal: more than 15 color changes,
  stitches over the machine maximum (thread-break risk), or a design over
  200 mm when no hoop is set.

**Export** runs the same validation and shows you the report, but it is
advisory there — the file still downloads, so run **Check** yourself when you
want a verdict before committing.

### Optimize — cut travel and trims

The **Optimize** toolbar button reorders objects **within each color block**
(color order never changes, so no extra thread swaps) using a
nearest-neighbour tour, to minimize needle travel and trims. The report card
shows exactly what it bought you:

> ✓ Path optimized — Travel 412 mm → 268 mm (−144 mm) · 3 fewer trims

The reorder is **applied with full undo support** — "Applied — Undo (↶)
reverts." — and the Quality panel re-scores against the new order. If there's
nothing to gain, it says **"Path already optimal"** and changes nothing.

## Lettering (Text)

_Section coming below._

## Export, save & share

_Section coming below._
