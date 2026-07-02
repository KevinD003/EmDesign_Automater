"""Design persistence (CRUD) endpoints (spec §8).

In-memory placeholder only — real persistence is Supabase/Postgres (db/schema.sql).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.design import Design
from app.services import digitizer

router = APIRouter(tags=["designs"])


@router.post("/designs/rebuild", response_model=Design)
async def rebuild(design: Design) -> Design:
    """Regenerate all stitches from object contours + current parameters.

    Used by object-level editing: change density/angle/stitch-type on an object,
    then rebuild. Only digitized designs (objects with contours) are regenerable.
    """
    try:
        return digitizer.rebuild_design(design)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

# TODO: replace with Supabase-backed storage.
_DESIGNS: dict[str, Design] = {}


@router.get("/designs", response_model=list[Design])
async def list_designs() -> list[Design]:
    """List designs (empty until persistence is wired)."""
    return list(_DESIGNS.values())


@router.get("/designs/{design_id}", response_model=Design)
async def get_design(design_id: str) -> Design:
    design = _DESIGNS.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="design not found")
    return design


@router.post("/designs", response_model=Design, status_code=201)
async def create_design(design: Design) -> Design:
    """Persist a new design.

    TODO: write to Supabase + design_versions snapshot. Stubbed for the scaffold.
    """
    raise HTTPException(status_code=501, detail="design persistence not implemented (scaffold stub)")
