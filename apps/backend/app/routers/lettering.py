"""Lettering endpoint (spec §4.10): text → embroidery Design."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from app.models.design import CamelModel, Design
from app.services import lettering

router = APIRouter(tags=["lettering"])


class FontInfo(CamelModel):
    name: str
    path: str


class LetteringRequest(CamelModel):
    text: str = Field(min_length=1, max_length=64)
    height_mm: float = Field(default=20.0, gt=0, le=100)
    fabric_type: str = "cotton"
    # Tracking between characters; 0 keeps the font's native kerning (the classic
    # single-draw path). Bounded: beyond ±this range lettering is unusable.
    letter_spacing_mm: float = Field(default=0.0, ge=-10, le=50)
    # Server-local TTF/TTC path; None runs the system font search.
    font_path: str | None = None
    baseline: Literal["straight", "arc"] = "straight"
    # Arc circle radius; required when baseline == "arc". A radius below the letter
    # height is rejected by the service; 2000mm is beyond any hoop, so anything
    # larger is indistinguishable from straight text.
    arc_radius_mm: float | None = Field(default=None, ge=4, le=2000)


@router.get("/lettering/fonts", response_model=list[FontInfo])
def get_fonts() -> list[FontInfo]:
    """Fonts available for lettering on this server, sorted by display name."""
    try:
        return [FontInfo(**f) for f in lettering.list_fonts()]
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Lettering dependency missing: {exc.name}") from exc


@router.post("/lettering", response_model=Design)
def create_lettering(req: LetteringRequest) -> Design:
    """Generate TATAMI-filled lettering (edge-walk underlay) from text."""
    try:
        return lettering.generate_lettering(
            req.text,
            req.height_mm,
            req.fabric_type,
            font_path=req.font_path,
            letter_spacing_mm=req.letter_spacing_mm,
            baseline=req.baseline,
            arc_radius_mm=req.arc_radius_mm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Lettering dependency missing: {exc.name}") from exc