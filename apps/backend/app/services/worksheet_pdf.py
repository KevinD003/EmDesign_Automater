"""Production worksheet builder + PDF render (spec §4.9).

``build_worksheet`` is pure Python. ``render_pdf`` uses ReportLab (lazy-imported so the
module still imports if ReportLab is absent).
"""

from __future__ import annotations

import io

from app.models.design import Design, Worksheet, WorksheetColorRow

_DEFAULT_SPM = 800.0  # stitches per minute, for the sew-time estimate


def _cmd(stitch) -> str:
    c = stitch.command
    return c.value if hasattr(c, "value") else c


def build_worksheet(design: Design) -> Worksheet:
    """Derive the worksheet view from a Design (spec §4.9)."""
    color_sequence = [
        WorksheetColorRow(
            stop=cs.stop_number,
            thread_brand=cs.thread_brand,
            catalog_number=cs.catalog_number,
            color_name=cs.thread_name,
            hex=cs.hex,
            objects="",
            stitch_count=cs.stitch_count,
        )
        for cs in design.color_stops
    ]

    trims = sum(1 for s in design.stitches if _cmd(s) == "TRIM")
    color_changes = sum(1 for s in design.stitches if _cmd(s) == "COLOR_CHANGE")

    flags: list[str] = []
    if design.width_mm > 200 or design.height_mm > 200:
        flags.append("Design exceeds a typical 200mm hoop — confirm hoop size.")
    if design.stitch_count == 0:
        flags.append("No stitches found in design.")

    return Worksheet(
        design_name=design.name,
        design_id=design.id,
        version=design.version,
        width_mm=design.width_mm,
        height_mm=design.height_mm,
        hoop_size=design.hoop_size,
        estimated_stitch_count=design.stitch_count,
        estimated_sew_minutes=round(design.stitch_count / _DEFAULT_SPM, 1),
        fabric_type=design.fabric_type,
        color_sequence=color_sequence,
        total_trims=trims,
        total_color_changes=color_changes,
        quality_flags=flags,
    )


def render_pdf(worksheet: Worksheet) -> bytes:
    """Render the worksheet to a downloadable PDF (spec §4.9)."""
    from reportlab.lib.colors import HexColor, black, grey
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    left = 20 * mm
    right = page_w - 20 * mm
    y = page_h - 20 * mm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(left, y, "STITCHIQ — Production Worksheet")
    y -= 9 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(grey)
    c.drawString(left, y, f"{worksheet.design_name}   ·   v{worksheet.version}")
    c.setFillColor(black)
    y -= 12 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Dimensions & Production")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    for line in (
        f"Size:  {worksheet.width_mm} x {worksheet.height_mm} mm",
        f"Estimated stitches:  {worksheet.estimated_stitch_count:,}",
        f"Estimated sew time:  {worksheet.estimated_sew_minutes} min @ 800 SPM",
        f"Trims:  {worksheet.total_trims}     Color changes:  {worksheet.total_color_changes}",
        f"Fabric:  {worksheet.fabric_type or '—'}     Hoop:  {worksheet.hoop_size or '—'}",
    ):
        c.drawString(left, y, line)
        y -= 5.5 * mm
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Color Sequence")
    y -= 7 * mm
    cols = {"stop": left, "swatch": left + 13 * mm, "brand": left + 22 * mm,
            "catalog": left + 55 * mm, "name": left + 80 * mm, "hex": left + 122 * mm}
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols["stop"], y, "Stop")
    c.drawString(cols["brand"], y, "Brand")
    c.drawString(cols["catalog"], y, "Catalog")
    c.drawString(cols["name"], y, "Color")
    c.drawString(cols["hex"], y, "Hex")
    c.drawRightString(right, y, "Stitches")
    y -= 3 * mm
    c.setStrokeColor(grey)
    c.line(left, y, right, y)
    y -= 5 * mm

    c.setFont("Helvetica", 9)
    for row in worksheet.color_sequence:
        if y < 25 * mm:
            c.showPage()
            y = page_h - 20 * mm
            c.setFont("Helvetica", 9)
        c.drawString(cols["stop"], y, str(row.stop))
        try:
            c.setFillColor(HexColor(row.hex))
        except Exception:  # noqa: BLE001 - bad hex → grey swatch
            c.setFillColor(grey)
        c.rect(cols["swatch"], y - 1 * mm, 6 * mm, 4 * mm, fill=1, stroke=0)
        c.setFillColor(black)
        c.drawString(cols["brand"], y, (row.thread_brand or "")[:16])
        c.drawString(cols["catalog"], y, (row.catalog_number or "")[:12])
        c.drawString(cols["name"], y, (row.color_name or "")[:22])
        c.drawString(cols["hex"], y, row.hex)
        c.drawRightString(right, y, f"{row.stitch_count:,}")
        y -= 6 * mm

    if worksheet.quality_flags:
        y -= 4 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, y, "Quality Flags")
        y -= 6 * mm
        c.setFont("Helvetica", 9)
        for flag in worksheet.quality_flags:
            c.drawString(left, y, f"•  {flag}")
            y -= 5 * mm

    c.showPage()
    c.save()
    return buf.getvalue()
