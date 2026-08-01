"""Phase 8 optimization endpoints — path optimization + quality analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.design import Design, OptimizeResult, QualityReport
from app.services import optimizer

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/path", response_model=OptimizeResult)
def optimize_path(design: Design) -> OptimizeResult:
    """Reorder objects within each color (nearest-neighbour) to cut travel/jumps.

    Returns the improved design + a before/after report. Non-regenerable designs
    come back unchanged with ``report.reordered = false``.
    """
    try:
        optimized, report = optimizer.optimize_path(design)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OptimizeResult(design=optimized, report=report)


@router.post("/quality", response_model=QualityReport)
def quality(design: Design) -> QualityReport:
    """Score the design (0..100) + itemized quality findings."""
    return optimizer.analyze_quality(design)
