"""Auto-digitizing endpoint — image to stitches (spec §4.2)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.design import Design

router = APIRouter(tags=["digitize"])


@router.post("/digitize", response_model=Design)
async def digitize(
    file: UploadFile = File(...),
    fabric_type: str = Form("cotton"),
    hoop_size: str = Form("100x100"),
) -> Design:
    """Auto-digitize an uploaded image into an embroidery Design.

    TODO: classical OpenCV pipeline first (region detect -> stitch-type assign ->
    color sequence -> path plan), AI models (SAM, CNN classifier) later. See spec §4.2.
    """
    raise HTTPException(status_code=501, detail="digitize not implemented (scaffold stub)")
