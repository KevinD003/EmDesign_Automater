"""Image preparation endpoints (v2 Part 36) — the editor in front of digitizing.

- POST /api/image/analyze  (multipart) -> measured suggestions for this image
- POST /api/image/edit     (multipart + form params) -> edited PNG stream

Both are plain `def` (threadpool) because OpenCV work on a full-size upload is
CPU-bound; an `async def` here would freeze the event loop exactly as it did
for digitizing before v2 Part 25.
"""

from __future__ import annotations

import io

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.services.image_edit import EditParams, apply_edits, suggest

router = APIRouter(prefix="/image", tags=["image"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _decode(data: bytes):
    import cv2
    import numpy as np

    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 25MB")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=415, detail="Could not decode image")
    return img


@router.post("/analyze")
def analyze(file: UploadFile = File(...)) -> dict:  # noqa: B008 - FastAPI idiom
    """Measure the upload and suggest fixes (each with the number behind it)."""
    return suggest(_decode(file.file.read()))


@router.post("/edit")
def edit(
    file: UploadFile = File(...),  # noqa: B008 - FastAPI idiom
    crop_x: float = Form(0.0),
    crop_y: float = Form(0.0),
    crop_w: float = Form(1.0),
    crop_h: float = Form(1.0),
    rotate_deg: float = Form(0.0),
    flip_h: bool = Form(False),
    flip_v: bool = Form(False),
    scale: float = Form(1.0),
    brightness: float = Form(0.0),
    contrast: float = Form(0.0),
    auto_levels: bool = Form(False),
    gamma: float = Form(1.0),
    saturation: float = Form(0.0),
    hue_shift: int = Form(0),
    sharpen: float = Form(0.0),
    denoise: float = Form(0.0),
    posterize: int = Form(0),
    remove_background: bool = Form(False),
    threshold_bw: bool = Form(False),
) -> StreamingResponse:
    import cv2

    img = _decode(file.file.read())
    cropping = (crop_x, crop_y, crop_w, crop_h) != (0.0, 0.0, 1.0, 1.0)
    params = EditParams(
        crop=(crop_x, crop_y, crop_w, crop_h) if cropping else None,
        rotate_deg=rotate_deg,
        flip_h=flip_h,
        flip_v=flip_v,
        scale=scale,
        brightness=brightness,
        contrast=contrast,
        auto_levels=auto_levels,
        gamma=gamma,
        saturation=saturation,
        hue_shift=hue_shift,
        sharpen=sharpen,
        denoise=denoise,
        posterize=posterize,
        remove_background=remove_background,
        threshold_bw=threshold_bw,
    )
    try:
        out = apply_edits(img, params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ok, buf = cv2.imencode(".png", out)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not encode the edited image")
    return StreamingResponse(
        io.BytesIO(buf.tobytes()),
        media_type="image/png",
        headers={"Content-Disposition": 'inline; filename="edited.png"'},
    )
