"""Export & validation endpoints (spec §4.8)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.design import Design, ValidationReport

router = APIRouter(tags=["export"])


@router.post("/export/validate", response_model=ValidationReport)
async def validate(design: Design) -> ValidationReport:
    """Pre-export validation.

    TODO: check jumps within machine max (12.7mm), stitch count within memory, design
    fits hoop, tie-ups present before trims. Return passed + issues + warnings.
    """
    raise HTTPException(status_code=501, detail="export/validate not implemented (scaffold stub)")


@router.post("/export")
async def export_package(design: Design) -> dict[str, str]:
    """Generate the production package.

    TODO: machine file (.DST/.PES/...) + master .STIQ (Design JSON) + worksheet PDF +
    thread color card + TrueView PNG, bundled for download.
    """
    raise HTTPException(status_code=501, detail="export not implemented (scaffold stub)")
