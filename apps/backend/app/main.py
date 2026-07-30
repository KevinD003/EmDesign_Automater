"""STITCHIQ API entrypoint.

Scaffold: routers are registered with correct typed signatures but their bodies
are stubs (HTTP 501). Run: ``uvicorn app.main:app --reload --port 8000``.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware.body_limit import BodySizeLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.routers import (
    auth,
    auth_local,
    convert,
    designs,
    digitize,
    export,
    files,
    lettering,
    optimize,
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

# Registered after CORSMiddleware so CORS stays outermost (middleware added
# later wraps closer to the app in Starlette).
app.add_middleware(RequestLoggingMiddleware)

# Innermost of the three: oversized uploads are rejected with 413 after CORS
# and access logging have done their bookkeeping.
app.add_middleware(BodySizeLimitMiddleware)

error_logger = logging.getLogger("stitchiq.error")


def _request_id(request: Request) -> str | None:
    """Correlation id set by RequestLoggingMiddleware, if the request has one."""
    return getattr(request.state, "request_id", None)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn any uncaught exception into a sanitized JSON 500.

    The full traceback goes to the 'stitchiq.error' log only — the response
    body must never contain str(exc) or traceback text, which can leak paths,
    SQL, or user data to clients.
    """
    request_id = _request_id(request)
    error_logger.error(
        "Unhandled exception [%s] %s %s",
        request_id,
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "requestId": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return FastAPI's usual 422 shape minus the 'input'/'url' echo fields,
    so large or sensitive request payloads are never reflected back."""
    detail = [{"loc": list(err.get("loc", ())), "msg": err.get("msg", "")} for err in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"detail": detail, "requestId": _request_id(request)},
    )


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


for module in (auth, files, convert, digitize, lettering, worksheet, export, threads, designs, optimize, auth_local):
    app.include_router(module.router, prefix="/api")
