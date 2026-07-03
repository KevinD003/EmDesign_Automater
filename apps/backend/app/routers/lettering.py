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


@router.post("/lettering", response_model=Design)
async def create_lettering(req: LetteringRequest) -> Design:
    """Generate TATAMI-filled lettering (edge-walk underlay) from text."""
    try:
        return lettering.generate_lettering(req.text, req.height_mm, req.fabric_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Lettering dependency missing: {exc.name}") from exc