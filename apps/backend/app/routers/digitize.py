"""Auto-digitizing endpoint — image to stitches (spec §4.2)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.design import Design
from app.services import digitizer

router = APIRouter(tags=["digitize"])


@router.post("/digitize", response_model=Design)
async def digitize(
    file: UploadFile = File(...),
    fabric_type: str = Form("cotton"),
    hoop_size: str = Form("100x100"),
    max_colors: int = Form(6),
) -> Design:
    """Auto-digitize an uploaded image into an embroidery Design (classical CV v1)."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        design = digitizer.digitize_image(data, fabric_type, hoop_size, max_colors)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Digitizer dependency missing: {exc.name}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Digitizing failed: {exc}") from exc
    if file.filename:
        design.name = file.filename.rsplit(".", 1)[0]
    return design
