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
    if design.stitch_count == 0:
        # An empty design is a failure, and it used to be returned as a success
        # (v2 Part 47). The caller got HTTP 200, a valid-looking Design and an
        # export that sews nothing — the warnings explaining why were easy to
        # miss and impossible to act on from a 200.
        #
        # This is NOT the filtering being wrong. Measured on the seven corpus
        # designs that hit it, every one is artwork whose strokes are thinner
        # than the 0.4mm thread at the requested hoop — the engine logs
        # `sub_thread_feature` at a median region width of 0.23mm and refuses,
        # correctly. Every one of them sews at a larger hoop (C14 0 -> 36,133,
        # C28 0 -> 18,250, C30 0 -> 4,618 going from 130x180 to 200x300), which
        # is exactly what the message tells the user to do.
        detail = "; ".join(design.warnings) if design.warnings else (
            "no stitchable regions were found in this image"
        )
        raise HTTPException(
            status_code=422,
            detail=f"Nothing could be sewn at hoop {hoop_size}: {detail}",
        )
    if file.filename:
        design.name = file.filename.rsplit(".", 1)[0]
    return design
