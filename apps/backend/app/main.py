"""STITCHIQ API entrypoint.

Scaffold: routers are registered with correct typed signatures but their bodies
are stubs (HTTP 501). Run: ``uvicorn app.main:app --reload --port 8000``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    convert,
    designs,
    digitize,
    export,
    files,
    threads,
    worksheet,
)

app = FastAPI(
    title="STITCHIQ API",
    version="0.1.0",
    description="AI embroidery design platform — backend scaffold (endpoints stubbed).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


for module in (files, convert, digitize, worksheet, export, threads, designs):
    app.include_router(module.router, prefix="/api")
