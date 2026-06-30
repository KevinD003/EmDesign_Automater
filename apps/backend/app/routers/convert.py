"""Format conversion endpoint (spec §4.8)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.design import ConvertRequest, ConvertResponse

router = APIRouter(tags=["convert"])


@router.post("/convert", response_model=ConvertResponse)
async def convert(req: ConvertRequest) -> ConvertResponse:
    """Convert an embroidery file from one machine format to another.

    TODO: base64-decode ``req.input_file_base64``, read as ``req.from_format`` and
    write as ``req.to_format`` via pyembroidery; return stitch/color counts + warnings.
    """
    raise HTTPException(status_code=501, detail="convert not implemented (scaffold stub)")
