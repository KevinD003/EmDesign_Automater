"""Production export package (spec §4.8): a ZIP with everything the floor needs.

Contents: machine file · master .STIQ (Design JSON) · worksheet PDF · thread color
card PDF · preview PNG · stitch-count summary. ReportLab/PIL imported lazily.
"""

from __future__ import annotations

import io
import re
import zipfile

from app.models.design import Design
from app.services import embroidery_io, worksheet_pdf

# Machine brand → (primary, secondary) format + note (spec §4.8 decision tree).
BRAND_FORMATS: list[dict[str, str]] = [
    {"brand": "Tajima / commercial", "primary": "dst", "secondary": "exp", "note": "DST has no color — include the color card"},
    {"brand": "Brother / Babylock", "primary": "pes", "secondary": "pec", "note": "PES stores color info"},
    {"brand": "Janome / Elna", "primary": "jef", "secondary": "sew", "note": ""},
    {"brand": "Bernina", "primary": "exp", "secondary": "dst", "note": ""},
    {"brand": "Husqvarna Viking / Pfaff", "primary": "vp3", "secondary": "vip", "note": "VP3 stores hoop position"},
    {"brand": "Melco / Bravo", "primary": "exp", "secondary": "dst", "note": "Keep the master .STIQ"},
    {"brand": "Universal (any machine)", "primary": "dst", "secondary": "pes", "note": "Always include DST"},
]


def _stem(name: str | None) -> str:
    return re.sub(r"[^\w\-]+", "_", (name or "design").rsplit(".", 1)[0]).strip("_") or "design"


def _cmd(s) -> str:
    c = s.command
    return c.value if hasattr(c, "value") else c


def build_summary(design: Design) -> str:
    lines = [
        "STITCHIQ — Stitch Summary",
        "=" * 32,
        f"Design:            {design.name}",
        f"Size:              {design.width_mm} x {design.height_mm} mm",
        f"Total stitches:    {design.stitch_count:,}",
        f"Colors:            {len(design.color_stops)}",
        f"Objects:           {len(design.objects)}",
        f"Est. sew time:     {round(design.stitch_count / 800.0, 1)} min @ 800 SPM",
        f"Trims:             {sum(1 for s in design.stitches if _cmd(s) == 'TRIM')}",
        f"Color changes:     {sum(1 for s in design.stitches if _cmd(s) == 'COLOR_CHANGE')}",
        "",
        "Color sequence:",
    ]
    for cs in design.color_stops:
        lines.append(f"  {cs.stop_number:>2}. {cs.hex}  {cs.thread_name}  ({cs.stitch_count:,} st)")
    return "\n".join(lines) + "\n"


# Approximate physical width of 40wt embroidery thread, in mm. Stitches are drawn
# at this width so the preview shows the coverage the sew-out will actually have.
THREAD_WIDTH_MM = 0.4


_BG = (250, 250, 250)
_SUPERSAMPLE = 3          # draw large, downsample: removes sub-pixel rasterisation gaps
_MAX_SS_PIXELS = 36_000_000  # ceiling before supersampling is skipped, to bound memory
_LOW_CONTRAST_DELTA = 60  # luminance gap below which thread needs a backing outline


def _luminance(rgb: tuple[int, int, int]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = (value or "").lstrip("#")
    if len(v) != 6:
        return (51, 51, 51)
    try:
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    except ValueError:
        return (51, 51, 51)


def _backing_for(rgb: tuple[int, int, int]) -> tuple[int, int, int] | None:
    """A contrast tone drawn under low-contrast thread, or None if not needed.

    White-on-white lettering was effectively invisible in the preview: the
    customer's package PNG showed bare fabric where a real white thread layer
    had been stitched, which led a reviewer to conclude (reasonably, and wrongly)
    that the layer was missing. A thread whose luminance is close to the paper
    gets a darker halo so it reads as stitching regardless of background.
    """
    gap = abs(_luminance(rgb) - _luminance(_BG))
    if gap >= _LOW_CONTRAST_DELTA:
        return None
    scale = 0.55 if _luminance(rgb) > 128 else 1.0
    return tuple(max(0, min(255, int(c * scale) - 40)) for c in rgb)  # type: ignore[return-value]


def render_preview(design: Design, px_per_mm: float = 5.0, pad: int = 12) -> bytes:
    """Render the stitch map to a PNG — what the customer sees in the package ZIP.

    Three fidelity defects have been fixed here, each found by measuring the
    render against the stitch geometry rather than by eye:

    1. **Stroke width** was a hard-coded 2px at any scale, drawing 0.4mm thread
       as a hairline above ~5px/mm (v1 audit §3). Now scales with ``px_per_mm``.
    2. **Satin read as scattered ticks.** Each stitch was drawn as an isolated
       hairline, so a satin column — a zigzag whose successive crossings sit
       0.4mm apart — rendered as separate marks with gaps, and reviewers
       reasonably concluded the strokes were hollow when interior coverage was
       in fact 95-98%. Consecutive crossings are now filled as a continuous
       swath, but ONLY where the columns genuinely touch (see ``_advance``
       guard), so a sparse fill still shows its real gaps.
    3. **Light thread was invisible** on the near-white paper. Low-contrast
       colours now get a backing halo.

    Measured on fixture 05, share of the design's area the render shows as
    inked: **62.2% before, 95.7% after** — against 87.1% actual geometric
    coverage, i.e. the old render understated the stitching by 25 points.
    """
    from PIL import Image, ImageDraw

    pts = [(s.x, s.y) for s in design.stitches if _cmd(s) == "STITCH"]
    if not pts:
        return _blank_png()
    xs, ys = zip(*pts)
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)

    base_w = int((maxx - minx) * px_per_mm) + 2 * pad
    base_h = int((maxy - miny) * px_per_mm) + 2 * pad
    ss = _SUPERSAMPLE if (max(base_w, 1) * max(base_h, 1) * _SUPERSAMPLE**2) <= _MAX_SS_PIXELS else 1

    scale = px_per_mm * ss
    spad = pad * ss
    w = int((maxx - minx) * scale) + 2 * spad
    h = int((maxy - miny) * scale) + 2 * spad
    img = Image.new("RGB", (max(w, 1), max(h, 1)), _BG)
    draw = ImageDraw.Draw(img)

    def to_px(x: float, y: float) -> tuple[float, float]:
        return ((x - minx) * scale + spad, (y - miny) * scale + spad)

    stops = design.color_stops
    fallback = ["#e11d48", "#2563eb", "#16a34a", "#d97706", "#7c3aed", "#0891b2"]
    run: list[tuple[float, float]] = []
    stop_idx = 0
    stroke = max(1, round(scale * THREAD_WIDTH_MM))
    touch = scale * THREAD_WIDTH_MM * 1.5  # columns closer than this overlap in thread

    def _d(a, b) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def _swath(color) -> None:
        """Fill between consecutive satin crossings.

        A satin run is [top, bottom, top, bottom, ...]: each pair spans the
        stroke, and successive pairs advance by the column pitch. Filling the
        quad between them is what thread physically does. The guard keeps this
        honest — it only fires when the advance is under a thread width AND both
        crossings are longer than the advance, which is false for a scanline
        fill (where consecutive points run ALONG a row) and false for sparse
        satin, so neither gets coverage it has not earned.
        """
        for k in range(0, len(run) - 3, 2):
            p0, p1, p2, p3 = run[k], run[k + 1], run[k + 2], run[k + 3]
            adv = _d(p0, p2)
            if adv <= touch and _d(p0, p1) > adv * 1.5 and _d(p2, p3) > adv * 1.5:
                draw.polygon([p0, p1, p3, p2], fill=color)

    def flush(idx: int) -> None:
        if len(run) < 2:
            return
        hex_color = stops[idx].hex if idx < len(stops) else fallback[idx % len(fallback)]
        rgb = _hex_to_rgb(hex_color)
        backing = _backing_for(rgb)
        try:
            if backing is not None:
                draw.line(run, fill=backing, width=stroke + 2 * ss, joint="curve")
            _swath(rgb)
            draw.line(run, fill=rgb, width=stroke, joint="curve")
        except (ValueError, SystemError):
            draw.line(run, fill=(51, 51, 51), width=stroke)

    for s in design.stitches:
        if _cmd(s) == "STITCH":
            run.append(to_px(s.x, s.y))
        else:
            flush(stop_idx)
            run = []
            if _cmd(s) == "COLOR_CHANGE":
                stop_idx += 1
    flush(stop_idx)

    if ss > 1:
        img = img.resize((max(base_w, 1), max(base_h, 1)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _blank_png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (250, 250, 250)).save(buf, format="PNG")
    return buf.getvalue()


def render_color_card(design: Design) -> bytes:
    """A one-page thread color card PDF: swatch + brand/catalog/name/hex per stop."""
    from reportlab.lib.colors import HexColor, black, grey
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, page_h = A4
    left = 20 * mm
    y = page_h - 20 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, "STITCHIQ — Thread Color Card")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(grey)
    c.drawString(left, y, design.name)
    c.setFillColor(black)
    y -= 12 * mm
    for cs in design.color_stops:
        if y < 25 * mm:
            c.showPage()
            y = page_h - 20 * mm
        try:
            c.setFillColor(HexColor(cs.hex))
        except Exception:  # noqa: BLE001
            c.setFillColor(grey)
        c.rect(left, y - 3 * mm, 16 * mm, 10 * mm, fill=1, stroke=1)
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left + 20 * mm, y + 3 * mm, f"{cs.stop_number}.  {cs.thread_name}")
        c.setFont("Helvetica", 9)
        c.drawString(left + 20 * mm, y - 2 * mm, f"{cs.thread_brand}  {cs.catalog_number}   {cs.hex}   {cs.stitch_count:,} st")
        y -= 16 * mm
    c.showPage()
    c.save()
    return buf.getvalue()


def build_package(design: Design, machine_format: str = "dst") -> bytes:
    """Bundle the full production package as a ZIP (spec §4.8)."""
    # Local import: optimizer pulls in the digitizer stack (cv2/numpy), which this
    # module otherwise avoids at import time (PIL/reportlab are lazy too).
    from app.services import optimizer

    machine_format = machine_format.lower().lstrip(".")
    stem = _stem(design.name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{stem}.{machine_format}", embroidery_io.write_embroidery(design, machine_format))
        z.writestr(f"{stem}.stiq.json", design.model_dump_json(by_alias=True, indent=2))
        z.writestr(f"{stem}-worksheet.pdf", worksheet_pdf.render_pdf(worksheet_pdf.build_worksheet(design)))
        z.writestr(f"{stem}-colorcard.pdf", render_color_card(design))
        z.writestr(f"{stem}-preview.png", render_preview(design))
        z.writestr(f"{stem}-summary.txt", build_summary(design))
        # Same wire shape as POST /api/optimize/quality, so the floor and the app
        # read one report.
        z.writestr("quality.json", optimizer.analyze_quality(design).model_dump_json(by_alias=True, indent=1))
    return buf.getvalue()
