"""Embroidery file I/O endpoints (spec §4.8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.deps import current_user
from app.models.design import Design
from app.services import embroidery_io

router = APIRouter(tags=["files"], dependencies=[Depends(current_user)])

# Real machine files are well under 1 MB, so 10 MB is a generous ceiling. It sits
# below the global 25 MB body cap (app/middleware/body_limit.py) so an oversized
# upload gets this endpoint-specific message instead of the blanket one.
MAX_EMBROIDERY_FILE_BYTES = 10 * 1024 * 1024

# Divisor for the human-readable byte count in the 413 detail.
BYTES_PER_MIB = 1024 * 1024

# Parser text is attacker-influenced (it can echo bytes from the uploaded file),
# so it is clipped before it enters a response body — never reflect an
# attacker-controlled string back at full length.
MAX_ERROR_DETAIL_CHARS = 200

# Named in the 415 so a user who uploaded a .jpg knows what to send instead.
COMMON_EXTENSIONS = "dst, pes, jef, exp, vp3, xxx"


def _safe_name_and_ext(filename: str) -> tuple[str, str]:
    """Split a client-supplied filename into a bare basename and lowercase extension.

    The filename is client-controlled and must never carry path components, so
    both separators are collapsed and only the last segment is kept. Returns an
    empty extension when the basename has none.
    """
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    ext = basename.rsplit(".", 1)[-1].lower() if "." in basename else ""
    return basename, ext


def _clip(text: str) -> str:
    """Bound third-party error text before it is interpolated into a detail."""
    return text[:MAX_ERROR_DETAIL_CHARS]


@router.post("/files/parse", response_model=Design)
def parse_file(file: Annotated[UploadFile, File()]) -> Design:
    """Decode an uploaded embroidery file (.DST/.PES/.JEF/...) into a Design."""
    basename, ext = _safe_name_and_ext(file.filename or "")
    if not ext:
        raise HTTPException(
            status_code=415,
            detail=(
                "Upload must be named with an embroidery file extension "
                f"(e.g. {COMMON_EXTENSIONS})"
            ),
        )
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_EMBROIDERY_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Embroidery file too large: limit is "
                f"{MAX_EMBROIDERY_FILE_BYTES // BYTES_PER_MIB} MB"
            ),
        )
    try:
        design = embroidery_io.read_embroidery(data, ext)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=_clip(str(exc))) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse file: {_clip(str(exc))}"
        ) from exc
    if basename:
        design.name = basename
    return design
