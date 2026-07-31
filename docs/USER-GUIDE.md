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
  dropdown** (.DST / .PES / .JEF / .EXP / .VP3), **Save**, **Saved (n)** —
  the count is how many designs this browser has stored — **Check**,
  **Quality**, **Optimize**, **Export**, **Package**, **Worksheet**, **Master**.
- **☁ Save / ☁ Open** — appear only when you're signed in; they save to and
  open from your cloud account.

Most action buttons are disabled until a design is loaded — Open or Digitize
something first.

**Below the toolbar** — a **Studio** / **Dashboard** switch (Studio is the
editor described in this guide) and the sign-in bar. Sign in only if you want
cloud saves; everything else works signed out.

**Canvas** — the middle of the screen. Your design renders here; this is where
you select objects and place points for the manual drawing tools. A **2D /
TrueView 3D** toggle sits above it and the stitch player along the bottom.

**Left panel**:

- **Color · Object List** — every color stop in stitch order, with a digitized
  design's objects nested under each stop.

**Right-hand panels**, top to bottom:

- **Thread Palette** — catalog threads you can snap a color stop to.
- **Properties** — settings for whatever is selected (color and order for a
  stop; density, angle, underlay, pull compensation for an object).
- **Quality** — the design's 0–100 quality score and its findings.

## Digitize an image

This is the headline feature: turn a picture into stitches.

1. Click **Digitize** in the toolbar and pick an image — **PNG, JPG/JPEG, BMP,
   or WebP**. Logos and other flat-color artwork digitize best; try the sample
   images in `apps/backend/tests/fixtures/quality_bench/` if you don't have one
   handy.
2. The **Digitize "your-file-name"** dialog opens and asks three questions:

   - **Fabric** — `cotton` (the default), `polo/knit`, `denim`, `fleece`,
     `cap`, or `towel`.
     This is not cosmetic: the fabric choice drives per-fabric **pull
     compensation** (0.15–0.5 mm per side), fill and satin **density**, the
     **underlay** step, and the edge **inset**. A design digitized for fleece
     comes out visibly different from the same image digitized for cotton —
     pick the fabric you'll actually stitch on.
   - **Hoop (mm)** — `100x100` (the default), `130x180`, `200x200`, or
     `260x160`. The design
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
  under each stop, with the object's sequence number, name, and stitch count.
  Digitized objects are named `Fill 3 (#1c4f8b)` / `Satin 7 (#1c4f8b)` — type,
  sequence number, and the stop's hex; hand-drawn ones are `Run 4`, `Satin 5`,
  `Fill 6`. Click one to select it. Imported machine files have no objects, so
  they only show color stops.

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
  Until you select one, the panel says *"Select a color stop, then click a
  thread."* and the swatches are disabled; with a stop selected it reads
  *"Applying to stop 2."* Hover a swatch for its `name · catalog number`.
- Or click **↳ Nearest catalog thread to `#rrggbb`** — the server finds the
  closest real thread by **CIE Lab color distance** (perceptual, not raw RGB)
  and applies it in one click. If the lookup fails the color is left alone and
  a *"Thread match failed"* toast explains why.

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
client-side. That's why this only works for objects that have a contour; on a
contour-less object the button is disabled and the panel says *"No contour
stored — object is not regenerable."* The rebuild is recorded in history, so
**Undo** restores the previous stitches.

Two guards run before the request, and their message appears right under the
button: *"Density must be > 0; angle must be a number."* and *"Pull
compensation must be 0–2 mm."* A server-side failure shows the same way (plus
a toast) and leaves your design untouched.

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
a fresh `Color 1` default on a blank canvas). It arrives with sensible
starting settings — Satin at 3.5 lines/mm with center-walk underlay, Fill at
1.4 lines/mm with edge-walk underlay, Run with neither — which you then tune
in **Properties** like any other object. One constraint: manual tools need a
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
below. The score is 100 minus fixed penalties, so it is never a mystery:
long stitches cost 5 + one per offending stitch (max 30), tiny stitches cost
one per two offenders (max 20), too many color changes and too many jumps cost
10 each, and a design that overflows its hoop costs 25.

Before you've scored anything the panel says *"Open or digitize a design to
see its quality score."*, or *"Hit Quality in the toolbar to score this
design."* once a design is loaded.

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

Then the itemized findings, each color-coded by severity — red for errors,
amber for warnings, grey for info — with a `(×N)` suffix when a finding covers
more than one stitch:

- **Long stitches** over 12.7 mm (0.5") — thread-break / skip risk on most
  machines (error).
- **Hoop overflow** — *"Design 120x95mm exceeds the 100x100 hoop."* The single
  biggest penalty: a design you can't hoop can't be stitched (error).
- **Tiny stitches** under 0.3 mm — thread shredding and needle wear (warning).
  The threshold is 0.3 mm, not 0.5 mm, on purpose: fills legitimately connect
  adjacent rows with one 0.4–0.45 mm pitch-length stitch, and flagging those
  would bury every well-digitized fill in false alarms.
- **Too many color changes** (over 15) — long run-time at the machine
  (warning).
- **Too many jumps** — raised when jumps exceed 20 *and* 10% of the stitch
  count: *"N jumps (X mm travel) — try Optimize to cut trims."* (warning).
- **Jump rate** — jumps per 1,000 stitches, always reported for context: each
  trimmed jump costs roughly 3–7 s of machine time, so lower is faster to run.
  It's an internal, comparable-over-time number, not an industry benchmark
  (info).

A design with nothing wrong still gets one info line — **"No quality issues
detected."** — alongside the jump rate. The green **"No findings."** appears
only when the report carries no findings at all.

### Check — pre-export validation

The **Check** toolbar button runs the pre-export sanity checks and pops a
report card: **✓ Ready to stitch** or **⛔ Issues found**.

- **Blocking issues (⛔)** — the design physically can't be stitched as-is:
  it has no stitches, or it **does not fit its declared hoop**.
- **Warnings (⚠)** — worth fixing but not fatal: more than 15 color changes,
  stitches over the 12.7 mm machine maximum (thread-break risk), or a design
  over 200 mm when no hoop is set.

A clean pass shows **"No problems detected."** Dismiss the card with its **×**.

**Export** runs the same validation and shows you the report, but it is
advisory there — the file still downloads, so run **Check** yourself when you
want a verdict before committing.

### Optimize — cut travel and trims

The **Optimize** toolbar button reorders objects **within each color block**
(color order never changes, so no extra thread swaps) using a
nearest-neighbour tour, to minimize needle travel and trims. It then rebuilds
the design server-side and measures the result, so the report card shows what
it actually bought you rather than an estimate:

```text
✓ Path optimized
Travel 412mm → 268mm (−144mm)
3 fewer trims
Applied — Undo (↶) reverts.
```

The reorder is **applied with full undo support**, and a Quality report that's
already on screen re-scores against the new order.

When there's nothing to gain the card reads **"Path already optimal"** and the
design is left exactly as it was, with a note saying which case you hit:

- *"Already near-optimal — no reorder applied."* — the tour didn't beat the
  current travel distance.
- *"Path optimization needs a digitized design with ≥2 contoured objects."* —
  most often an imported `.dst`/`.pes`, which has stitches but no objects to
  reorder. Optimize only works on digitized or hand-drawn designs.

## Lettering (Text)

Lettering lives on the **Text** button in the toolbar's action group. The
**Lettering** button in the *tools* row (next to Appliqué and Shape) is a
greyed-out stub — it is permanently disabled and does nothing in this release.
Use **Text**.

**Text** opens the **Lettering** dialog:

| Field | Range | Default | Notes |
| --- | --- | --- | --- |
| **Text** | 1–64 characters | empty | Placeholder shows `e.g. STITCHIQ`. |
| **Height (mm)** | 5–100 | `20` | Height of the letters as they will sew. |
| **Letter spacing (mm)** | −2 to 10, steps of 0.1 | `0` | Tracking. `0` keeps the font's own kerning; negative pulls letters together. |
| **Fabric** | cotton, polo/knit, denim, fleece, cap, towel | `cotton` | Same fabric profiles as Digitize — sets density, underlay and pull compensation. |

**Generate** stays disabled until the text is non-empty and both numbers are in
range; **Cancel** closes without changing anything.

### What Generate actually does

The server renders your text with a **system font** and pushes the resulting
bitmap through the same digitizer that handles images. Consequences worth
knowing before you commit:

- **There is no font picker.** The server walks a fixed preference list and
  takes the first font that exists — Arial, then Arial Bold, then Helvetica,
  then DejaVu Sans Bold / DejaVu Sans — falling back to a scan of the system
  font directories. Whatever the machine running the backend has installed,
  that is your font. (The API does expose a font list at
  `GET /api/lettering/fonts`, but v1's dialog doesn't offer it, and that
  listing has no effect on what Generate uses.)
- **Generate replaces the current design** — it does not add text to what's on
  the canvas. Save or export first if you want to keep the current design.
- The result arrives named `Text "YOUR TEXT"` with **one black color stop
  named "Lettering"**, and is scored automatically, so the Quality panel fills
  in straight away. Recolour it like any design: select the stop and pick a
  thread in the Thread Palette.
- The output is a **normal digitized design** — objects, contours and all — so
  Properties, Apply (rebuild), Optimize, Check and Export all work on it.

### Fill or satin? (the dialog's note is out of date)

The dialog prints *"v1 fills letters with tatami + edge-walk underlay; satin
strokes come later."* That note predates the current stitch-type classifier.
The classifier now decides per object from the **measured stroke width along
the shape's medial axis**, so anything thin enough — which is most lettering —
comes out as **satin columns with center-walk underlay**, and only genuinely
broad letterforms get a tatami fill. Measured: `ABC` at 20 mm height generates
three objects, all `Satin n (#000000)` / SATIN / CENTER_WALK.

Don't guess — open **Color · Object List** and read the object names. `Satin 1
(#000000)` is a satin column; `Fill 1 (#000000)` is tatami.

### Sizing: stay at or above 5 mm

The dialog's 5 mm floor is deliberate, and the backend refuses anything under
4 mm outright (*"text below 4mm cannot be embroidered legibly"*). Embroidery
thread is roughly 0.4 mm wide, so small letters run out of room for their own
counters — the holes in `a`, `e`, `o` close up, and thin strokes drop below one
thread width.

The stitch count shows the loss plainly: the same `ABC` is **966 stitches at
20 mm** but only **160 stitches at 5 mm**. Same three letters, a sixth of the
stitching. At small sizes prefer a bold, chunky face and expect to lose fine
detail — see the [FAQ](./FAQ.md) on small text.

### When Generate fails

- *"Unsupported characters for lettering: '…' — the font has no glyphs for
  them"* — the chosen system font can't draw a character you typed (common
  with emoji, or non-Latin scripts on a minimal Linux install). Stick to
  characters the server's font actually has.
- *"Text '…' produced no stitchable shapes (unsupported glyphs, or too
  small)"* — the render came through, but nothing survived digitizing. Raise
  the height.
- *"No TrueType font found on this system — supply a font path"* — the backend
  host has no usable font. Install one system-wide (on Linux, a
  `fonts-dejavu` / `ttf-mscorefonts` package puts one in `/usr/share/fonts`);
  the render path only searches system font locations.

## Export, save & share

### Choosing a format

The **format dropdown** in the action group offers **.DST · .PES · .JEF ·
.EXP · .VP3**, and drives both **Export** and **Package**. It's disabled until
a design is loaded.

| Your machine | Pick |
| --- | --- |
| Tajima / commercial | **.DST** |
| Brother / Babylock | **.PES** |
| Janome / Elna | **.JEF** |
| Bernina, Melco / Bravo | **.EXP** |
| Husqvarna Viking / Pfaff | **.VP3** |
| Not sure / any machine | **.DST** |

**.DST carries no color information** — it's stitches only. If you export DST,
take the thread color card with you (it's in the **Package** ZIP), or you'll be
guessing at the machine.

### The four download buttons

- **Export** — downloads the machine file as `<design-name>.<ext>`. It runs the
  pre-export validation first and always shows you the report card, but that
  report is **advisory only: the file downloads either way**, even with
  blocking issues. If you want a go/no-go verdict, press
  [**Check**](#check--pre-export-validation) before exporting.
- **Package** — the production ZIP, `<design-name>-package.zip`. Everything the
  floor needs in one download:

  | Entry | What it is |
  | --- | --- |
  | `<name>.<ext>` | The machine file, in the format the dropdown is set to. |
  | `<name>.stiq.json` | The editable master (see below). |
  | `<name>-worksheet.pdf` | Operator worksheet: size, color sequence, stitch count and **thread length in metres per color**. |
  | `<name>-colorcard.pdf` | Printable thread color card — pair this with a DST. |
  | `<name>-preview.png` | Rendered stitch preview. |
  | `<name>-summary.txt` | Plain-text summary: size, total stitches, colors, objects, trims, color changes, estimated sew time at 800 SPM, and the color sequence. |
  | `quality.json` | The same quality report the Quality panel shows. |

- **Worksheet** — the operator worksheet PDF on its own,
  `<design-name>-worksheet.pdf`.
- **Master** — the editable master on its own, `<design-name>.stiq.json`.

### The master file (.stiq.json)

A machine file is stitches; the master is the **design**. It keeps your objects
and their contours, so re-opening one with **Open** restores full editability —
you can change density, angle, underlay or pull compensation and press **Apply
(rebuild)**. Re-open a `.dst` or `.pes` instead and you get a stitch stream you
can view and export but not edit object-by-object.

**Keep the master for anything you might revise.** Masters are parsed in the
browser (no server round-trip); a file that isn't one is rejected with *"Missing
stitches / colorStops / objects — not a STITCHIQ master (.stiq.json)."*

### Save, Saved (n) — this browser only

**Save** stores the design in this browser's `localStorage` and confirms with
*"Saved to this browser"*. Saving the same design again overwrites its entry
rather than piling up copies.

**Saved (n)** opens the list — `n` is how many designs this browser holds. Each
row shows the name and stitch count with **Load** and **✕** (delete) buttons;
an empty list reads *"Nothing saved in this browser yet."*

This is **local convenience, not backup**. It lives in one browser profile on
one machine, and clearing site data deletes it. For anything you care about,
download the **Master** or a **Package**.

### ☁ Save, ☁ Open — cloud

The **☁ Save** and **☁ Open** buttons appear only when you're **signed in**
(use the sign-in bar under the toolbar). They store designs per user, so you
can pick a design back up from another browser or machine. ☁ Save confirms with
*"Saved to cloud"*; ☁ Open lists your cloud designs with **Open** and **✕**,
and reads *"No cloud designs yet — hit ☁ Save."* when empty.

Cloud storage is backed by Supabase. **In a development install with no
Supabase keys configured, the backend falls back to in-memory storage — your
cloud designs vanish when the server restarts.** If cloud saves need to
survive, make sure the deployment has real Supabase credentials configured.

### Honest limits — read before you sew

- **.DST and .PES** are the best-supported formats: both are round-tripped in
  the automated test suite (write, read back, compare).
- **.JEF, .EXP and .VP3** are written through the same library (pyembroidery)
  but are less battle-tested here. Treat the first file you send to a machine
  in one of these formats as an experiment.
- **.VIP and .HUS cannot be exported** — the library has no writers for them,
  so they're deliberately absent from the dropdown. On the read side the file
  picker lists `.vip`, but the pyembroidery build shipped here has no `.vip`
  reader either and will report *"Unsupported embroidery format: .vip"*; `.hus`
  does open, even though the picker doesn't list it (choose "All files" in the
  file dialog).
- **No STITCHIQ file has been verified on a physical embroidery machine yet.**
  Round-tripping in software is not the same as sewing. **Test-stitch on scrap
  fabric first**, on the same fabric and stabilizer as the real job, and check
  the sew-out before you commit a garment.
