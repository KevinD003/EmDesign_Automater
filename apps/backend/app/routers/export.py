"""Export & validation endpoints (spec §4.8)."""

from __future__ import annotations

import io
import math

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.design import Design, ValidationReport
from app.services import embroidery_io, package as package_svc

router = APIRouter(tags=["export"])


@router.get("/formats")
async def formats() -> dict[str, object]:
    """Supported export formats + machine-brand recommendation table (spec §4.8)."""
    return {
        "export": ["dst", "pes", "jef", "exp", "vp3", "pec", "xxx", "vip", "csv"],
        "brands": package_svc.BRAND_FORMATS,
    }


@router.post("/export/package")
async def export_package(design: Design, format: str = Query("dst")) -> StreamingResponse:
    """Bundle the full production package (machine file + master + worksheet + color card
    + preview + summary) as a ZIP (spec §4.8)."""
    try:
        data = package_svc.build_package(design, format)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Package build failed: {exc}") from exc
    stem = package_svc._stem(design.name)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{stem}-package.zip"'},
    )

_MAX_STITCH_MM = 12.7  # machine limit (0.5")


def _cmd(stitch) -> str:
    c = stitch.command
    return c.value if hasattr(c, "value") else c


@router.post("/export")
async def export_design(design: Design, format: str = Query("dst")) -> StreamingResponse:
    """Encode a Design to a machine file and stream it back."""
    try:
        data = embroidery_io.write_embroidery(design, format)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    stem = (design.name or "design").rsplit(".", 1)[0]
    filename = f"{stem}.{format.lower()}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/validate", response_model=ValidationReport)
async def validate(design: Design) -> ValidationReport:
    """Pre-export sanity checks (spec §4.8)."""
    issues: list[str] = []
    warnings: list[str] = []

    if design.stitch_count == 0 and not design.stitches:
        issues.append("Design has no stitches.")
    if design.width_mm > 200 or design.height_mm > 200:
        warnings.append(f"Design {design.width_mm}x{design.height_mm}mm exceeds a typical 200mm hoop.")

    long_stitches = 0
    prev = None
    for s in design.stitches:
        if _cmd(s) == "STITCH" and prev is not None:
            if math.hypot(s.x - prev[0], s.y - prev[1]) > _MAX_STITCH_MM:
                long_stitches += 1
        prev = (s.x, s.y)
    if long_stitches:
        warnings.append(f"{long_stitches} stitches exceed {_MAX_STITCH_MM}mm (thread-break risk).")

    return ValidationReport(passed=not issues, issues=issues, warnings=warnings)
