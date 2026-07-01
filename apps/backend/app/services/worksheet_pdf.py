"""Production worksheet builder + PDF render (spec §4.9).

``build_worksheet`` is pure Python (no deps). ``render_pdf`` needs ReportLab and is
still a stub (deferred — reportlab is in requirements-features.txt).
"""

from __future__ import annotations

from app.models.design import Design, Worksheet, WorksheetColorRow

_DEFAULT_SPM = 800.0  # stitches per minute, for sew-time estimate


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
    """Render the worksheet to a downloadable PDF.

    TODO (needs reportlab from requirements-features.txt):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        # header, dimensions, color table, sequence map, TrueView image
    """
    raise NotImplementedError("render_pdf — needs reportlab (deferred)")
