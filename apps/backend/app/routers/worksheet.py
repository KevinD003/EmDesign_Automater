"""Production worksheet endpoints (spec §4.9)."""

from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.design import Design, Worksheet
from app.services import worksheet_pdf

router = APIRouter(tags=["worksheet"])


@router.post("/worksheet", response_model=Worksheet)
async def build_worksheet(design: Design) -> Worksheet:
    """Build the production worksheet as structured JSON."""
    return worksheet_pdf.build_worksheet(design)


@router.post("/worksheet/pdf")
async def worksheet_pdf_download(design: Design) -> StreamingResponse:
    """Render the production worksheet to a downloadable PDF (spec §4.9)."""
    worksheet = worksheet_pdf.build_worksheet(design)
    try:
        data = worksheet_pdf.render_pdf(worksheet)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PDF render failed: {exc}") from exc
    stem = (design.name or "design").rsplit(".", 1)[0]
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{stem}-worksheet.pdf"'},
    )
