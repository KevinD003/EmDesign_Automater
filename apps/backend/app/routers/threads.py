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
async def match_thread(hex_color: str = Query(..., alias="hex"), brand: str | None = Query(None)) -> Thread:
    """Nearest catalogue thread to a target color, by CIE Lab distance (spec §4.4)."""
    try:
        return threads_svc.nearest_thread(hex_color, threads_svc.list_threads(brand))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
