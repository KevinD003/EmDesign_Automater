"""Production worksheet builder + PDF render (spec §4.9).

Scaffold stub. ReportLab is imported lazily inside the render function.
"""

from __future__ import annotations

from app.models.design import Design, Worksheet


def build_worksheet(design: Design) -> Worksheet:
    """Derive the worksheet view from a Design (color sequence, trims, flags).

    TODO: aggregate color_stops + objects; estimate sew time from stitch_count.
    """
    raise NotImplementedError("build_worksheet — scaffold stub (spec §4.9)")


def render_pdf(worksheet: Worksheet) -> bytes:
    """Render the worksheet to a downloadable PDF.

    TODO:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        # lay out header, dimensions, color table, sequence map, TrueView image
    """
    raise NotImplementedError("render_pdf — scaffold stub (spec §4.9)")
