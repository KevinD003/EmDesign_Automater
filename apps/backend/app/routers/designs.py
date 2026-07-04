"""Design persistence (CRUD) endpoints (spec §8).

Backed by Supabase/Postgres when configured (``db/schema.sql`` applied + service key
in the env). Falls back to a process-local in-memory dict when Supabase isn't wired,
so the app and the offline test suite still run. See services/supabase_store.py.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from app.models.design import Design
from app.services import digitizer, supabase_store

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


# In-memory fallback for when Supabase isn't configured (offline dev / CI).
_DESIGNS: dict[str, Design] = {}


@router.get("/designs", response_model=list[Design])
async def list_designs() -> list[Design]:
    """List saved designs (metadata). Cloud when configured, else in-memory."""
    if supabase_store.is_enabled():
        try:
            return await supabase_store.list_designs()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Supabase error: {exc}") from exc
    return list(_DESIGNS.values())


@router.get("/designs/{design_id}", response_model=Design)
async def get_design(design_id: str) -> Design:
    if supabase_store.is_enabled():
        try:
            design = await supabase_store.get_design(design_id)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Supabase error: {exc}") from exc
    else:
        design = _DESIGNS.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="design not found")
    return design


@router.post("/designs", response_model=Design, status_code=201)
async def create_design(design: Design) -> Design:
    """Persist a new design (+ a full-fidelity version snapshot)."""
    if supabase_store.is_enabled():
        try:
            return await supabase_store.create_design(design)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Supabase error: {exc}") from exc
    # In-memory fallback: synthesize an id.
    new_id = design.id or f"mem-{len(_DESIGNS) + 1}"
    stored = design.model_copy(update={"id": new_id})
    _DESIGNS[new_id] = stored
    return stored


@router.delete("/designs/{design_id}", status_code=204)
async def delete_design(design_id: str) -> None:
    if supabase_store.is_enabled():
        try:
            await supabase_store.delete_design(design_id)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Supabase error: {exc}") from exc
    else:
        _DESIGNS.pop(design_id, None)
