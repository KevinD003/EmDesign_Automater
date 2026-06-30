"""Production worksheet endpoint (spec §4.9)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.design import Design, Worksheet

router = APIRouter(tags=["worksheet"])


@router.post("/worksheet", response_model=Worksheet)
async def build_worksheet(design: Design) -> Worksheet:
    """Build the full production worksheet for a design.

    TODO: derive dimensions, color sequence, trim/jump map, quality flags from the
    Design; render a downloadable PDF (ReportLab) with the TrueView image embedded.
    """
    raise HTTPException(status_code=501, detail="worksheet not implemented (scaffold stub)")
