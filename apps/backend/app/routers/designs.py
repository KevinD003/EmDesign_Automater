"""Design persistence (CRUD) endpoints (spec §8).

Backed by Supabase/Postgres when configured (``db/schema.sql`` applied + service key
in the env), scoped to the authenticated user (see deps.current_user). Falls back to
a process-local in-memory dict (keyed by the LOCAL_USER sentinel) when Supabase isn't
wired, so the app and the offline test suite still run keyless.
"""

from __future__ import annotations

import itertools
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.deps import current_user
from app.models.design import CamelModel, Design
from app.services import digitizer, supabase_store

router = APIRouter(tags=["designs"])
logger = logging.getLogger("stitchiq.designs")


def _storage_error(exc: Exception) -> HTTPException:
    """502 without leaking the internal URL / query / uuids in the response body."""
    logger.warning("supabase storage error: %s", exc)
    return HTTPException(status_code=502, detail="storage backend error")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class ActivityItem(CamelModel):
    id: str
    name: str
    stitch_count: int = 0
    saved_at: str = ""


class DesignStats(CamelModel):
    design_count: int = 0
    total_stitches: int = 0
    total_colors: int = 0
    recent: list[ActivityItem] = []


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
# Keyed by user so scoping semantics match the cloud path.
_DESIGNS: dict[tuple[str, str], Design] = {}
# Monotonic id source — NEVER derive ids from len(_DESIGNS) (a delete would let the next
# create collide with a still-live id and clobber it).
_MEM_SEQ = itertools.count(1)


@router.get("/designs", response_model=list[Design])
async def list_designs(user_id: str = Depends(current_user)) -> list[Design]:
    """List the caller's saved designs (metadata). Cloud when configured, else in-memory."""
    if supabase_store.is_enabled():
        try:
            return await supabase_store.list_designs(user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    return [d for (uid, _), d in _DESIGNS.items() if uid == user_id]


@router.get("/designs/stats", response_model=DesignStats)
async def stats(user_id: str = Depends(current_user)) -> DesignStats:
    """Dashboard aggregates for the caller (design count, total stitches/colors, recent)."""
    if supabase_store.is_enabled():
        try:
            return DesignStats.model_validate(await supabase_store.design_stats(user_id))
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    designs = [d for (uid, _), d in _DESIGNS.items() if uid == user_id]
    return DesignStats(
        design_count=len(designs),
        total_stitches=sum(d.stitch_count for d in designs),
        total_colors=sum(len(d.color_stops) for d in designs),
        recent=[
            ActivityItem(id=d.id or "", name=d.name, stitch_count=d.stitch_count) for d in designs[:8]
        ],
    )


@router.get("/designs/{design_id}", response_model=Design)
async def get_design(design_id: str, user_id: str = Depends(current_user)) -> Design:
    if supabase_store.is_enabled():
        # Cloud ids are uuids; a non-uuid path can't exist → 404 (and avoids a PostgREST
        # 400 that would otherwise surface as a 502).
        if not _is_uuid(design_id):
            raise HTTPException(status_code=404, detail="design not found")
        try:
            design = await supabase_store.get_design(design_id, user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    else:
        design = _DESIGNS.get((user_id, design_id))
    if design is None:
        raise HTTPException(status_code=404, detail="design not found")
    return design


@router.post("/designs", response_model=Design, status_code=201)
async def create_design(design: Design, user_id: str = Depends(current_user)) -> Design:
    """Persist a new design for the caller (+ a full-fidelity version snapshot)."""
    if supabase_store.is_enabled():
        try:
            return await supabase_store.create_design(design, user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    # In-memory fallback: synthesize a monotonic id (never reused after a delete).
    new_id = design.id or f"mem-{next(_MEM_SEQ)}"
    stored = design.model_copy(update={"id": new_id})
    _DESIGNS[(user_id, new_id)] = stored
    return stored


@router.delete("/designs/{design_id}", status_code=204)
async def delete_design(design_id: str, user_id: str = Depends(current_user)) -> None:
    if supabase_store.is_enabled():
        if not _is_uuid(design_id):
            return  # nothing to delete; a non-uuid id can't exist in the cloud store
        try:
            await supabase_store.delete_design(design_id, user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    else:
        _DESIGNS.pop((user_id, design_id), None)
