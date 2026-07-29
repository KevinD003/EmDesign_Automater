"""Lettering endpoint (spec §4.10): text → embroidery Design."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import Field

from app.models.design import CamelModel, Design
from app.services import lettering

router = APIRouter(tags=["lettering"])


class LetteringRequest(CamelModel):
    text: str = Field(min_length=1, max_length=64)
    height_mm: float = Field(default=20.0, gt=0, le=100)
    fabric_type: str = "cotton"
    # Tracking between characters; 0 keeps the font's native kerning (the classic
    # single-draw path). Bounded: beyond ±this range lettering is unusable.
    letter_spacing_mm: float = Field(default=0.0, ge=-10, le=50)
    # Server-local TTF/TTC path; None runs the system font search.
    font_path: str | None = None


@router.post("/lettering", response_model=Design)
async def create_lettering(req: LetteringRequest) -> Design:
    """Generate TATAMI-filled lettering (edge-walk underlay) from text."""
    try:
        return lettering.generate_lettering(
            req.text,
            req.height_mm,
            req.fabric_type,
            font_path=req.font_path,
            letter_spacing_mm=req.letter_spacing_mm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Lettering dependency missing: {exc.name}") from exc