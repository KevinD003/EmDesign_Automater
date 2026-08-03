# STITCHIQ FAQ

Short answers to the questions that come up most. If you want the guided walkthrough
instead — toolbar tour, digitizing, editing, the Quality panel, lettering and export —
read [the User Guide](./USER-GUIDE.md) first and come back here for the edge cases.

Everything below was checked against the code in this repository, not against marketing
copy. Where the honest answer is "not verified yet", it says so.

## Formats

### What image formats can I digitize?

**`.png` · `.jpg` · `.jpeg` · `.bmp` · `.webp`**

That is the exact list the **Digitize** button's file picker accepts
(`ACCEPT_IMG` in `apps/frontend/src/components/toolbar/Toolbar.tsx`). Anything else —
`.gif`, `.tif`, `.svg`, `.pdf`, `.heic`, a camera RAW — is not offered and is not
supported.

Practical notes:

- **Flat colour beats photographs.** Digitizing quantizes the image to your
  **Max colors** setting (2–8) with k-means, then traces each colour region. Logos,
  icons and vector art exported to PNG give clean regions; a gradient-heavy photo gives
  banded blobs.
- **Transparency is not a cutout tool.** A PNG alpha channel is not treated as
  "leave this unstitched" — flatten onto the background colour you actually want before
  importing.
- **Bigger source, better edges.** Contour tracing runs on the pixels you give it, so a
  200 px logo blown up to a 100 mm design will show its staircase.

### What embroidery formats can I open?

Two different things open through the **Open** button:

| Kind | Extensions | Parsed by |
|---|---|---|
| Machine files | `.dst` `.pes` `.pec` `.jef` `.exp` `.vp3` `.vip` `.xxx` `.sew` `.u01` | Backend, via pyembroidery |
| STITCHIQ masters | `.stiq.json` (and plain `.json`) | The browser, no server round-trip |

**Important caveat, measured on this build:** the file picker advertises `.vip`, but the
installed pyembroidery has no VIP *reader*, so opening one fails with
`Unsupported embroidery format: .vip`. The same check shows `.hus` **is** readable even
though the picker does not list it — choose "All files" in the OS dialog and a `.hus`
will open. Both are library facts (`_supported_read_exts()` in
`apps/backend/app/services/embroidery_io.py`), not settings you can change.

**An imported machine file is a stitch stream, not a design.** DST, PES and friends store
needle coordinates — the objects, contours and stitch parameters that produced them are
not in the file and cannot be recovered. So after opening one you can view it, play it,
run **Check**, run **Quality** and re-export it, but you **cannot** edit it
object-by-object; the manual tools refuse with:

> Manual tools need a blank or digitized canvas — imported files aren't editable object-by-object.

Colour is also format-dependent on import. DST, EXP and U01 store no thread table at all,
so the stops come back named `Color 1 (file has no color data)` with filler swatches you
should re-assign from the Thread Palette.

To keep full editability, save a **Master** (`.stiq.json`) alongside your machine file —
that one *does* round-trip objects and contours.

### What formats can I export?

The toolbar's format dropdown offers five: **`.DST` `.PES` `.JEF` `.EXP` `.VP3`**.
Both **Export** (single file) and **Package** (ZIP) use the selection.

The API is slightly wider than the UI. `GET /api/formats` advertises
`dst, pes, pec, jef, exp, vp3, xxx, u01, csv` — that list is the intersection of the
formats STITCHIQ chooses to advertise with the writers pyembroidery actually has, so it
can never name a format that would 415 at export time. PEC, XXX, U01 and CSV are
reachable through the API but are deliberately not in the dropdown.

Honest testing status (`docs/LAUNCH-READINESS-GAPS.md`, B4 and B9):

- **DST and PES have software round-trip tests** — written, re-read, compared.
- **JEF, EXP, VP3 and XXX are written through pyembroidery but have no round-trip tests.**
- **No exported file has ever been loaded onto a physical embroidery machine.** See
  "Have these fabric settings been tested on real fabric?" below — the same warning applies
  to formats.

**VIP and HUS are import-only.** pyembroidery has readers but no writers for either, so
they are excluded from the advertised export list by design (the exclusion is enforced
in code, not just documented — `MACHINE_EXPORT_FORMATS` is filtered by the writer table
in `apps/backend/app/routers/export.py`).

Two more things worth knowing before you pick:

- **Colour survives only in some formats.** PES and VP3 keep your exact hex values; PEC
  and JEF keep colour but *snap* it to the machine brand's fixed palette, so hexes shift;
  DST, EXP and U01 carry no colour at all. When colour does not travel with the file, ship
  the colour card from **Package**.
- **VP3 has a size ceiling.** Above ~3270 mm the coordinate field wraps and the file
  corrupts, so STITCHIQ rejects the export with a 413 rather than writing a broken file.
  No other advertised format has a container limit worth reporting. This is a *file format*
  limit, not a hoop limit — hoop fit is checked separately.

### Which format should I pick for my machine?

This is the recommendation table STITCHIQ itself serves from `/api/formats`
(`BRAND_FORMATS` in `apps/backend/app/services/package.py`):

| Machine brand | Primary | Secondary | Note |
|---|---|---|---|
| Tajima / commercial | DST | EXP | DST has no colour — include the colour card |
| Brother / Babylock | PES | PEC | PES stores colour info |
| Janome / Elna | JEF | SEW | |
| Bernina | EXP | DST | |
| Husqvarna Viking / Pfaff | VP3 | VIP | VP3 stores hoop position |
| Melco / Bravo | EXP | DST | Keep the master `.stiq.json` |
| Universal (any machine) | DST | PES | Always include DST |

Read the *primary* column — that is the one to pick. Two secondaries are listed for
completeness but **cannot be exported from STITCHIQ**: `SEW` and `VIP` have no
pyembroidery writer. If your Janome or Husqvarna will not read the primary, use DST.

If you genuinely do not know what your machine takes, **DST** is the safest single answer
— it is the universal commercial format and every brand row above lists it as primary or
secondary. Pair it with the colour card, because DST will not carry your thread colours.

## Fabrics

### What fabrics are supported, and what does the fabric setting actually change?

The **Digitize** dialog offers six, defaulting to `cotton`:
**cotton · polo/knit · denim · fleece · cap · towel**.

The API accepts twelve — the six above plus **twill, poplin, canvas, knit, jersey, terry** —
so a request made directly to `POST /api/digitize` (or a future UI that offers more) can
reach all of them. Names are matched case-insensitively; **anything unrecognised silently
falls back to a middle-of-the-road default profile** rather than erroring, so a typo like
`"cottn"` will digitize, just not with cotton's numbers.

The fabric setting is not cosmetic. It selects a row of five stitch parameters
(`FABRIC_PROFILES`, `apps/backend/app/services/digitizer/constants.py`) that are applied while the
design is generated:

| Fabric | Pull comp (mm/side) | Tatami row pitch (mm) | Satin pitch (mm) | Underlay step (mm) | Edge inset (mm) |
|---|---|---|---|---|---|
| cotton | 0.20 | 0.45 | 0.40 | 2.0 | 0.6 |
| denim | 0.15 | 0.40 | 0.35 | 2.0 | 0.6 |
| twill | 0.15 | 0.40 | 0.35 | 2.0 | 0.6 |
| poplin | 0.15 | 0.40 | 0.35 | 2.0 | 0.6 |
| canvas | 0.15 | 0.40 | 0.35 | 2.0 | 0.6 |
| cap | 0.30 | 0.45 | 0.40 | 1.8 | 0.6 |
| polo/knit | 0.40 | 0.50 | 0.45 | 1.8 | 0.7 |
| knit | 0.40 | 0.50 | 0.45 | 1.8 | 0.7 |
| jersey | 0.45 | 0.55 | 0.50 | 1.8 | 0.7 |
| fleece | 0.50 | 0.55 | 0.50 | 1.5 | 0.8 |
| towel | 0.50 | 0.50 | 0.40 | 1.5 | 0.8 |
| terry | 0.50 | 0.50 | 0.40 | 1.5 | 0.8 |
| *(unrecognised)* | 0.25 | 0.45 | 0.40 | 2.0 | 0.6 |

What each column does:

- **Pull compensation** — every column and fill edge is widened by this much *per side* to
  cancel the fabric pulling in under thread tension. Stretchy, lofty fabrics get more
  (0.5 mm for fleece and terry); stable wovens get least (0.15 mm for denim, twill,
  poplin, canvas). Get this wrong and either your shapes come out narrow with fabric
  showing at the seams (too little) or bloated and overlapping (too much).
- **Tatami row pitch** — the gap between fill rows. Larger pitch = fewer rows = a softer,
  lighter fill that will not stiffen a knit into a plastic patch. Note the direction:
  stretchy/lofty fabrics get *looser* fills, stable wovens *tighter* ones.
- **Satin pitch** — the same idea for satin zigzag columns.
- **Underlay step** — running-stitch length of the underlay laid down before the top
  stitching. High-pile fabrics get a shorter step (1.5 mm on fleece and terry) so the
  underlay actually tacks the nap down instead of skipping over it.
- **Edge inset** — how far inside the shape the edge-walk underlay runs. Deeper on lofty
  fabrics (0.8 mm) so it stays hidden once the pile springs back.

So choosing `fleece` versus `cotton` for the same artwork produces a visibly different
design: wider shapes, looser fill, shorter and deeper underlay. This is chosen at
**digitize** time — changing your mind means re-digitizing, or editing individual objects
in the Properties panel (which exposes density, angle, underlay and pull comp per object).

One caveat about **terry vs. fleece**: terry is set *denser* than fleece
(0.50 mm rows, not 0.55), because terry-specific digitizing guidance calls for tighter
stitching so the loops cannot separate the stitches, while loft-generic guidance groups it
with fleece. Those sources conflict, and the tiebreaker is a physical sew-out that has not
happened yet.

### Have these fabric settings been tested on real fabric?

**No. Be honest with yourself about this before you sew anything you care about.**

Precisely where things stand:

- **Cotton is the validated baseline — in software.** The cotton row is byte-identical to
  the constants the ten-fixture quality regression corpus was built on, so cotton output is
  pinned by automated tests and cannot silently drift. That is a *regression* guarantee, not
  a fabric guarantee.
- **Every non-cotton row is provisional.** Those numbers come from published industry
  digitizing guidance (wovens 0.35–0.45 mm, knits 0.45–0.5, fleece 0.5–0.6, terry 0.5–0.7 —
  citations in `docs/COMPETITOR-COMPARISON.md`), not from measurement. They are a reasonable
  starting point, not a tested result.
- **Nothing in this repository has ever been stitched on a physical machine.** No fabric
  test, no format test, no sew-out. Nothing here can drive an embroidery machine, so the
  safety constants — minimum stitch length, minimum penetration spacing, density ceiling,
  pull compensation, maximum stitch length — are all asserted from practice and carried
  honestly as unvalidated. `docs/FABRIC_TEST_PROTOCOL.md` is the written procedure that
  would validate them; its own header says **NOT YET EXECUTED**.

What to do about it:

1. **Test-stitch on a scrap of the actual fabric first**, with the actual stabilizer,
   needle and thread weight you plan to use. Every time, until you have your own numbers.
2. **Check the result with a loupe** for thread breaks, needle-strike perforation and
   fabric distortion — the three failure modes the untested constants are supposed to
   prevent.
3. **If shapes come out narrow with fabric showing through the joins**, increase pull
   compensation on the affected objects in the Properties panel (0–2 mm range) and re-run.
   If they come out fat and overlapping, decrease it.
4. **Write down what worked** for your machine, fabric and thread. Right now your notes are
   better evidence than these defaults.

If you do run a sew-out, `docs/FABRIC_TEST_PROTOCOL.md` lists the exact test pieces and
measurements that would turn these provisional numbers into validated ones.

<!-- MORE-FAQ-BELOW -->
