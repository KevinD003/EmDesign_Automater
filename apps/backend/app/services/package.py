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


def render_preview(design: Design, px_per_mm: float = 5.0, pad: int = 12) -> bytes:
    """Render the stitch map to a PNG (color-grouped polylines on white)."""
    from PIL import Image, ImageDraw

    pts = [(s.x, s.y) for s in design.stitches if _cmd(s) == "STITCH"]
    if not pts:
        return _blank_png()
    xs, ys = zip(*pts)
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    w = int((maxx - minx) * px_per_mm) + 2 * pad
    h = int((maxy - miny) * px_per_mm) + 2 * pad
    img = Image.new("RGB", (max(w, 1), max(h, 1)), (250, 250, 250))
    draw = ImageDraw.Draw(img)

    def to_px(x: float, y: float) -> tuple[float, float]:
        return ((x - minx) * px_per_mm + pad, (y - miny) * px_per_mm + pad)

    stops = design.color_stops
    fallback = ["#e11d48", "#2563eb", "#16a34a", "#d97706", "#7c3aed", "#0891b2"]
    run: list[tuple[float, float]] = []
    stop_idx = 0

    def flush(idx: int) -> None:
        if len(run) >= 2:
            color = stops[idx].hex if idx < len(stops) else fallback[idx % len(fallback)]
            try:
                draw.line(run, fill=color, width=2, joint="curve")
            except (ValueError, SystemError):
                draw.line(run, fill="#333333", width=2)

    for s in design.stitches:
        if _cmd(s) == "STITCH":
            run.append(to_px(s.x, s.y))
        else:
            flush(stop_idx)
            run = []
            if _cmd(s) == "COLOR_CHANGE":
                stop_idx += 1
    flush(stop_idx)

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
    return buf.getvalue()
