"""Design persistence (CRUD) endpoints (spec §8).

Backed by Supabase/Postgres when configured (``db/schema.sql`` applied + service key
in the env), scoped to the authenticated user (see deps.current_user). Falls back to
the local_store service when Supabase isn't wired: JSON files under
``data/designs/<user>/`` (or ``STITCHIQ_DESIGNS_DIR``) in normal runs, an in-memory
dict under pytest — so the app and the offline test suite still run keyless.
"""

from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field

from app.deps import current_user
from app.models.design import CamelModel, Design
from app.services import digitizer, local_store, supabase_store

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


# Hard cap on a design name — mirrors local_store._MAX_NAME_LEN and shields the
# cloud path, whose rename_design does no validation of its own.
MAX_NAME_LEN = 200


class RenamePayload(CamelModel):
    name: str


class ActivityItem(CamelModel):
    id: str
    name: str
    stitch_count: int = 0
    saved_at: str = ""


class DesignStats(CamelModel):
    design_count: int = 0
    total_stitches: int = 0
    total_colors: int = 0
    recent: list[ActivityItem] = Field(default_factory=list)


@router.post("/designs/rebuild", response_model=Design)
def rebuild(design: Design) -> Design:
    """Regenerate all stitches from object contours + current parameters.

    Used by object-level editing: change density/angle/stitch-type on an object,
    then rebuild. Only digitized designs (objects with contours) are regenerable.
    """
    try:
        return digitizer.rebuild_design(design)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# Legacy alias: tests/test_designs.py clears this between cases to reset the
# pytest-mode fallback store. It points at local_store's in-memory dict (only
# used when running under pytest without STITCHIQ_DESIGNS_DIR) — never rebind.
_DESIGNS = local_store._MEMORY


@router.get("/designs", response_model=list[Design])
async def list_designs(user_id: str = Depends(current_user)) -> list[Design]:
    """List the caller's saved designs (metadata). Cloud when configured, else local files."""
    if supabase_store.is_enabled():
        try:
            return await supabase_store.list_designs(user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    return local_store.list_designs(user_id)


@router.get("/designs/stats", response_model=DesignStats)
async def stats(user_id: str = Depends(current_user)) -> DesignStats:
    """Dashboard aggregates for the caller (design count, total stitches/colors, recent)."""
    if supabase_store.is_enabled():
        try:
            return DesignStats.model_validate(await supabase_store.design_stats(user_id))
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    return DesignStats.model_validate(local_store.design_stats(user_id))


async def _fetch_design(design_id: str, user_id: str) -> Design:
    """Load one design for the caller or raise 404/502. Shared by GET and GET /preview."""
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
        design = local_store.get_design(design_id, user_id)
    if design is None:
        raise HTTPException(status_code=404, detail="design not found")
    return design


@router.get("/designs/{design_id}", response_model=Design)
async def get_design(design_id: str, user_id: str = Depends(current_user)) -> Design:
    return await _fetch_design(design_id, user_id)


# Library thumbnails render at a coarser scale than package.render_preview's 5.0 px/mm
# default: a thumb is shown at ~200px, so the extra pixels are only bytes on the wire.
THUMB_PX_PER_MM = 2.0


@router.get("/designs/{design_id}/preview")
async def design_preview(design_id: str, user_id: str = Depends(current_user)) -> Response:
    """PNG thumbnail of a saved design's stitch map, for the library grid."""
    design = await _fetch_design(design_id, user_id)
    # render_preview falls back to a 2x2 blank PNG when no STITCH points exist; that
    # is a useless thumbnail, so surface the empty design as a client error instead.
    if not design.stitches:
        raise HTTPException(status_code=422, detail="design has no stitches to preview")
    # Lazy import: app.services.package pulls pyembroidery (and PIL on first render)
    # at import time — cost the design routes shouldn't pay just to be registered.
    from app.services.package import render_preview

    png = render_preview(design, px_per_mm=THUMB_PX_PER_MM)
    # no-store: autosave overwrites a design in place under the same id, so any cached
    # thumbnail would be stale the moment the user saves.
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/designs", response_model=Design, status_code=201)
async def create_design(design: Design, user_id: str = Depends(current_user)) -> Design:
    """Persist a new design for the caller (+ a full-fidelity version snapshot)."""
    if supabase_store.is_enabled():
        try:
            return await supabase_store.create_design(design, user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    # Local fallback: local_store assigns a fresh uuid4 hex when the id is absent
    # or unsafe, so ids are never reused after a delete.
    return local_store.create_design(design, user_id)


@router.put("/designs/{design_id}", response_model=Design)
async def update_design(
    design_id: str, design: Design, user_id: str = Depends(current_user)
) -> Design:
    """Overwrite an existing design (autosave/save).

    404 if it doesn't exist for the caller — clients then POST to create.
    """
    if supabase_store.is_enabled():
        if not _is_uuid(design_id):
            raise HTTPException(status_code=404, detail="design not found")
        try:
            updated = await supabase_store.update_design(design_id, design, user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
    else:
        updated = local_store.update_design(design_id, design, user_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="design not found")
    return updated


def _clean_name(name: str) -> str:
    """Strip + length-check a rename; 422 on empty or over-long (never silently truncate)."""
    cleaned = (name or "").strip()
    if not cleaned or len(cleaned) > MAX_NAME_LEN:
        raise HTTPException(
            status_code=422, detail=f"name must be 1..{MAX_NAME_LEN} characters"
        )
    return cleaned


@router.patch("/designs/{design_id}")
async def rename_design(
    design_id: str, payload: RenamePayload, user_id: str = Depends(current_user)
) -> dict[str, str]:
    """Rename a design in place. Both backends answer {"id", "name"} so clients match."""
    name = _clean_name(payload.name)
    if supabase_store.is_enabled():
        if not _is_uuid(design_id):
            raise HTTPException(status_code=404, detail="design not found")
        try:
            renamed = await supabase_store.rename_design(design_id, name, user_id)
        except httpx.HTTPError as exc:
            raise _storage_error(exc) from exc
        if not renamed:
            raise HTTPException(status_code=404, detail="design not found")
    else:
        try:
            design = local_store.rename_design(design_id, name, user_id)
        except ValueError as exc:  # defense in depth: _clean_name already rejects blanks
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if design is None:
            raise HTTPException(status_code=404, detail="design not found")
    return {"id": design_id, "name": name}


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
        local_store.delete_design(design_id, user_id)
