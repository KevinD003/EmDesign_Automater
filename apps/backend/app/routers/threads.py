"""Thread color management endpoints (spec §4.4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.design import Thread

router = APIRouter(tags=["threads"])


@router.get("/threads", response_model=list[Thread])
async def list_threads(brand: str | None = Query(None)) -> list[Thread]:
    """List the thread catalogue, optionally filtered by brand (Madeira, Isacord, ...).

    TODO: load the thread database (see app/data/threads_madeira_sample.json, later
    a real table per spec §8) and filter.
    """
    raise HTTPException(status_code=501, detail="threads not implemented (scaffold stub)")


@router.post("/threads/match", response_model=Thread)
async def match_thread(hex_color: str = Query(..., alias="hex")) -> Thread:
    """Find the nearest catalogue thread to a target color.

    TODO: convert hex -> Lab, k-d tree (SciPy) nearest neighbour over the thread DB.
    """
    raise HTTPException(status_code=501, detail="threads/match not implemented (scaffold stub)")
