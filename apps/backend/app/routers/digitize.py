"""Auto-digitizing endpoint — image to stitches (spec §4.2)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.models.design import Design
from app.services import digitizer, plans

router = APIRouter(tags=["digitize"])


# Deliberately a plain `def`, NOT `async def` (v2 Part 25) — and the same choice
# is made in every CPU-bound router (lettering, export, convert, worksheet,
# optimize, files, designs.rebuild). FastAPI runs an `async def` handler ON the
# event loop, so a synchronous CPU-bound call inside one freezes the whole
# process; a plain `def` is dispatched to the threadpool instead. Measured by
# probing /health every 250ms during a 12.58s digitize of the badge fixture:
# as `async def`, ZERO probes completed for the entire duration; as `def`, 37
# completed (max latency 951ms). With the runbook's --workers 1, that was the
# difference between one user digitizing and every other user being frozen out.
@router.post("/digitize", response_model=Design)
def digitize(
    file: UploadFile = File(...),
    fabric_type: str = Form("cotton"),
    hoop_size: str = Form("100x100"),
    max_colors: int = Form(6),
    authorization: str | None = Header(default=None),
) -> Design:
    """Auto-digitize an uploaded image into an embroidery Design (classical CV v1)."""
    hoop_w, hoop_h = digitizer._parse_hoop(hoop_size)
    plans.check_hoop_allowed(authorization, hoop_w, hoop_h)
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        design = digitizer.digitize_image(data, fabric_type, hoop_size, max_colors)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Digitizer dependency missing: {exc.name}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Digitizing failed: {exc}") from exc
    if file.filename:
        design.name = file.filename.rsplit(".", 1)[0]
    return design
