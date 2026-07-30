"""Export & validation endpoints (spec §4.8)."""

from __future__ import annotations

import io
import math

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.design import Design, ValidationReport
from app.services import embroidery_io
from app.services import package as package_svc
from app.services.optimizer import parse_hoop

router = APIRouter(tags=["export"])

# Machine formats we ADVERTISE for export, in recommendation order (spec §4.8).
# The endpoint intersects this with pyembroidery's actual writer table, so a format
# the library cannot write can never be advertised (advertising one is a guaranteed
# 415 at export time). "vip" and "hus" are deliberately absent: pyembroidery reads
# both but has writers for neither (HUS is import-only; VIP export is unsupported).
# Internal formats (json/svg/png/txt/gcode) are writable but stay unadvertised.
MACHINE_EXPORT_FORMATS: tuple[str, ...] = ("dst", "pes", "pec", "jef", "exp", "vp3", "xxx", "u01", "csv")


@router.get("/formats")
async def formats() -> dict[str, object]:
    """Supported export formats + machine-brand recommendation table (spec §4.8)."""
    writable = embroidery_io.supported_write_exts()
    return {
        "export": [f for f in MACHINE_EXPORT_FORMATS if f in writable],
        "brands": package_svc.BRAND_FORMATS,
    }


@router.post("/export/package")
async def export_package(design: Design, format: str = Query("dst")) -> StreamingResponse:
    """Bundle the full production package (machine file + master + worksheet + color card
    + preview + summary) as a ZIP (spec §4.8)."""
    fmt = format.lower().lstrip(".")  # normalize once: 'DST' / '.dst' → 'dst'
    try:
        data = package_svc.build_package(design, fmt)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Package build failed: {exc}") from exc
    stem = package_svc.safe_stem(design.name)
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
    fmt = format.lower().lstrip(".")  # normalize once: 'DST' / '.dst' → 'dst'
    try:
        data = embroidery_io.write_embroidery(design, fmt)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    # design.name is arbitrary user input; safe_stem strips header-breaking chars.
    filename = f"{package_svc.safe_stem(design.name)}.{fmt}"
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

    # If a hoop is specified, a design that doesn't fit is a BLOCKING issue (it can't be
    # stitched). Otherwise fall back to a generic 200mm warning.
    hoop = parse_hoop(design.hoop_size)
    if hoop is not None:
        hw, hh = hoop
        if design.width_mm > hw or design.height_mm > hh:
            issues.append(
                f"Design {design.width_mm}x{design.height_mm}mm does not fit the {design.hoop_size} hoop."
            )
    elif design.width_mm > 200 or design.height_mm > 200:
        warnings.append(f"Design {design.width_mm}x{design.height_mm}mm exceeds a typical 200mm hoop.")

    color_changes = sum(1 for s in design.stitches if _cmd(s) == "COLOR_CHANGE")
    if color_changes > 15:
        warnings.append(f"{color_changes} color changes — many thread changes will slow production.")

    long_stitches = 0
    prev = None
    for s in design.stitches:
        if (
            _cmd(s) == "STITCH"
            and prev is not None
            and math.hypot(s.x - prev[0], s.y - prev[1]) > _MAX_STITCH_MM
        ):
            long_stitches += 1
        prev = (s.x, s.y)
    if long_stitches:
        warnings.append(f"{long_stitches} stitches exceed {_MAX_STITCH_MM}mm (thread-break risk).")

    return ValidationReport(passed=not issues, issues=issues, warnings=warnings)
