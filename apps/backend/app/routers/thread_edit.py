"""Thread-editor endpoints (v2 Part 36) — custom threads and saved palettes.

Every route is per-user via ``current_user``: a shop's thread chart is its own
data, never global.

- GET/POST      /api/threads/custom            list / create a custom thread
- PATCH/DELETE  /api/threads/custom/{id}       edit / remove one
- GET/POST      /api/threads/palettes          list / save a palette
- DELETE        /api/threads/palettes/{id}     remove one
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.deps import current_user
from app.services.thread_store import ThreadStore, ThreadStoreError, get_store

router = APIRouter(prefix="/threads", tags=["threads"])

StoreDep = Annotated[ThreadStore, Depends(get_store)]
UserDep = Annotated[str, Depends(current_user)]


class CustomThreadIn(BaseModel):
    brand: str
    name: str
    code: str = ""
    hex: str


class CustomThreadPatch(BaseModel):
    brand: str | None = None
    name: str | None = None
    code: str | None = None
    hex: str | None = None


class PaletteColor(BaseModel):
    hex: str
    name: str = "Thread"
    brand: str = ""
    code: str = ""


class PaletteIn(BaseModel):
    name: str
    colors: list[PaletteColor]


@router.get("/custom")
def list_custom(store: StoreDep, user: UserDep) -> list[dict]:
    return store.list_threads(user)


@router.post("/custom", status_code=201)
def add_custom(req: CustomThreadIn, store: StoreDep, user: UserDep) -> dict:
    try:
        return store.add_thread(user, req.brand, req.name, req.code, req.hex)
    except ThreadStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/custom/{thread_id}")
def patch_custom(
    thread_id: str, req: CustomThreadPatch, store: StoreDep, user: UserDep
) -> dict:
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422, detail="Nothing to update.")
    try:
        return store.update_thread(user, thread_id, **fields)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown thread") from exc
    except ThreadStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/custom/{thread_id}", status_code=204)
def delete_custom(thread_id: str, store: StoreDep, user: UserDep) -> Response:
    if not store.delete_thread(user, thread_id):
        raise HTTPException(status_code=404, detail="Unknown thread")
    return Response(status_code=204)


@router.get("/palettes")
def list_palettes(store: StoreDep, user: UserDep) -> list[dict]:
    return store.list_palettes(user)


@router.post("/palettes", status_code=201)
def save_palette(req: PaletteIn, store: StoreDep, user: UserDep) -> dict:
    try:
        return store.save_palette(user, req.name, [c.model_dump() for c in req.colors])
    except ThreadStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/palettes/{palette_id}", status_code=204)
def delete_palette(palette_id: str, store: StoreDep, user: UserDep) -> Response:
    if not store.delete_palette(user, palette_id):
        raise HTTPException(status_code=404, detail="Unknown palette")
    return Response(status_code=204)
