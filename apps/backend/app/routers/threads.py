"""Thread color management endpoints (spec §4.4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.design import Thread
from app.services import threads as threads_svc

router = APIRouter(tags=["threads"])


@router.get("/threads", response_model=list[Thread])
async def list_threads(brand: str | None = Query(None)) -> list[Thread]:
    """List the thread catalogue, optionally filtered by brand (Madeira, Isacord, ...)."""
    return threads_svc.list_threads(brand)


@router.post("/threads/match", response_model=Thread)
async def match_thread(hex_color: str = Query(..., alias="hex")) -> Thread:
    """Nearest catalogue thread by Lab color (spec §4.4). TODO: k-d tree (Phase 8)."""
    raise HTTPException(status_code=501, detail="threads/match not implemented (Phase 8)")
