"""Format conversion endpoint (spec §4.8): any supported format → any other."""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, HTTPException

from app.models.design import ConvertRequest, ConvertResponse
from app.services import embroidery_io

router = APIRouter(tags=["convert"])

# Formats that store no thread colors — converting INTO them loses color data.
_COLORLESS = {"dst", "exp", "dsb", "dsz", "tap", "u01"}


@router.post("/convert", response_model=ConvertResponse)
def convert(req: ConvertRequest) -> ConvertResponse:
    """Convert an embroidery file between machine formats.

    Reads via pyembroidery into the Design model, writes back out — so anything
    parse/export supports, convert supports.
    """
    try:
        data = base64.b64decode(req.input_file_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="input_file_base64 is not valid base64") from exc
    if not data:
        raise HTTPException(status_code=400, detail="Empty input file")

    try:
        design = embroidery_io.read_embroidery(data, req.from_format)
        out = embroidery_io.write_embroidery(design, req.to_format)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Conversion failed: {exc}") from exc

    warnings: list[str] = []
    if req.to_format.lower().lstrip(".") in _COLORLESS:
        warnings.append(
            f".{req.to_format.lower()} stores no thread colors — include a color card with the file."
        )
    if req.from_format.lower().lstrip(".") in _COLORLESS:
        warnings.append(f".{req.from_format.lower()} carries no color data; colors shown are placeholders.")

    return ConvertResponse(
        output_file_base64=base64.b64encode(out).decode("ascii"),
        stitch_count=design.stitch_count,
        colors=len(design.color_stops),
        warnings=warnings,
    )
