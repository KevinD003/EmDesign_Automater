"""Production worksheet endpoint (spec §4.9)."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.design import Design, Worksheet
from app.services import worksheet_pdf

router = APIRouter(tags=["worksheet"])


@router.post("/worksheet", response_model=Worksheet)
async def build_worksheet(design: Design) -> Worksheet:
    """Build the full production worksheet for a design (JSON; PDF render TBD)."""
    return worksheet_pdf.build_worksheet(design)
