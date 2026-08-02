"""Stitch-editor endpoints (v2 Part 36) — edit the stream of any design.

- POST /api/stitches/edit    {design, ops[]} -> {design, notes[], stats}
- POST /api/stitches/stats   {design}        -> stream counters

Works on imported machine files that carry no objects at all, which is the
case object-level editing cannot serve. Plain `def`: transforming a 50k-stitch
stream is CPU-bound.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.design import CamelModel, Design
from app.services import stitch_edit

router = APIRouter(prefix="/stitches", tags=["stitches"])

MAX_OPS = 200


class EditRequest(BaseModel):
    design: Design
    ops: list[dict]


class EditResponse(CamelModel):
    design: Design
    notes: list[str] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)


@router.post("/edit", response_model=EditResponse)
def edit(req: EditRequest) -> EditResponse:
    if len(req.ops) > MAX_OPS:
        raise HTTPException(
            status_code=422, detail=f"At most {MAX_OPS} operations per request."
        )
    try:
        stitches, notes = stitch_edit.apply_ops(req.design.stitches, req.ops)
    except stitch_edit.EditError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    design = req.design.model_copy(update={"stitches": stitches})
    # Editing the stream can move the design's extent; keep the header honest.
    pts = [(s.x, s.y) for s in stitches]
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        design.width_mm = round(max(xs) - min(xs), 2)
        design.height_mm = round(max(ys) - min(ys), 2)
    design.stitch_count = sum(
        1 for s in stitches if stitch_edit._cmd(s).value == "STITCH"
    )
    return EditResponse(design=design, notes=notes, stats=stitch_edit.stream_stats(stitches))


@router.post("/stats")
def stats(design: Design) -> dict:
    return stitch_edit.stream_stats(design.stitches)
