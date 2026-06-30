"""Embroidery file I/O endpoints (spec §4.8). FIRST feature to implement."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.design import Design

router = APIRouter(tags=["files"])


@router.post("/files/parse", response_model=Design)
async def parse_file(file: UploadFile = File(...)) -> Design:
    """Decode an uploaded embroidery file (.DST/.PES/.JEF/...) into a Design.

    TODO: read ``await file.read()`` with ``app.services.embroidery_io.read_embroidery``
    (pyembroidery) and map stitches + thread list into the Design model.
    """
    raise HTTPException(status_code=501, detail="files/parse not implemented (scaffold stub)")
