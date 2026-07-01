"""Embroidery file I/O endpoints (spec §4.8)."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.design import Design
from app.services import embroidery_io

router = APIRouter(tags=["files"])


@router.post("/files/parse", response_model=Design)
async def parse_file(file: UploadFile = File(...)) -> Design:
    """Decode an uploaded embroidery file (.DST/.PES/.JEF/...) into a Design."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        design = embroidery_io.read_embroidery(data, ext)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}") from exc
    if filename:
        design.name = filename
    return design
