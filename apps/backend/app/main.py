"""STITCHIQ API entrypoint.

Scaffold: routers are registered with correct typed signatures but their bodies
are stubs (HTTP 501). Run: ``uvicorn app.main:app --reload --port 8000``.
"""

from __future__ import annotations

import logging
import platform
import sys
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware.body_limit import BodySizeLimitMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.routers import (
    admin,
    auth,
    auth_local,
    convert,
    designs,
    digitize,
    export,
    files,
    image_edit,
    lettering,
    optimize,
    stitch_edit,
    thread_edit,
    threads,
    worksheet,
)

startup_logger = logging.getLogger("stitchiq.startup")


def _validate_production_config() -> None:
    """Fail-fast under APP_ENV=production (CTO A10/S1).

    The dev fallbacks — sentinel auth, in-memory per-process stores, open
    access — exist so a keyless checkout can run the suite and a single
    operator can work offline. In production the same fallbacks mean a typo'd
    SUPABASE_* var silently ships a fully unauthenticated app that mixes all
    users into one account and loses every design on restart. Production
    therefore refuses to BOOT rather than degrade: a crashed deploy is
    diagnosable, a fail-open one is a breach.
    """
    import os

    if settings.app_env.strip().lower() != "production":
        return
    missing = [name.upper() for name in
               ("supabase_url", "supabase_anon_key", "supabase_service_key")
               if not getattr(settings, name).strip()]
    if missing:
        raise RuntimeError(
            f"APP_ENV=production but {', '.join(missing)} is unset. Refusing to "
            f"boot: without Supabase the app falls back to sentinel auth and "
            f"per-process in-memory storage — fully unauthenticated, all users "
            f"in one account, data lost on restart. Set the missing keys or "
            f"run with APP_ENV=development."
        )
    if os.environ.get("STITCHIQ_OPEN_ACCESS") == "1":
        raise RuntimeError(
            "APP_ENV=production with STITCHIQ_OPEN_ACCESS=1: open access "
            "disables authentication entirely and is a dev-only switch. "
            "Unset it to boot in production."
        )


_validate_production_config()

# Uptime baseline for /health. Module import == process start under uvicorn,
# and monotonic() cannot go backwards when NTP or DST shifts the wall clock.
_STARTED_MONOTONIC = time.monotonic()

# Methods this API actually serves; PATCH/HEAD/TRACE are not exposed.
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

# Request headers the frontend sends. Anything else fails preflight rather
# than reaching a router.
CORS_ALLOW_HEADERS = ["Authorization", "Content-Type", "X-Request-ID"]

# Response headers the browser may read cross-origin: the correlation id from
# RequestLoggingMiddleware, the download filename from /api/export, and the
# backoff hint from RateLimitMiddleware's 429.
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Content-Disposition", "Retry-After"]

# Preflight cache lifetime in seconds. A 100-user LAN deployment talks to few
# origins, so caching OPTIONS for 10 minutes removes a round-trip per request.
CORS_MAX_AGE_SECONDS = 600

# The CORS spec forbids Access-Control-Allow-Origin: * together with
# Allow-Credentials: true — browsers reject such responses outright.
WILDCARD_ORIGIN = "*"

app = FastAPI(
    title="STITCHIQ API",
    version="0.1.0",
    description="AI embroidery design platform — backend scaffold (endpoints stubbed).",
)


def _cors_allow_credentials(origins: list[str]) -> bool:
    """False when origins contain '*', because credentialed wildcard CORS is
    invalid and would break every browser request instead of loosening one."""
    if WILDCARD_ORIGIN in origins:
        startup_logger.warning(
            "CORS_ORIGINS contains '*'; disabling allow_credentials because the "
            "CORS spec forbids credentialed requests against a wildcard origin. "
            "Set explicit origins to re-enable cookies/Authorization."
        )
        return False
    return True


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=_cors_allow_credentials(settings.cors_origins),
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS,
    max_age=CORS_MAX_AGE_SECONDS,
)

# Registered after CORSMiddleware so CORS stays outermost (middleware added
# later wraps closer to the app in Starlette).
app.add_middleware(RequestLoggingMiddleware)

# Innermost of the three: oversized uploads are rejected with 413 after CORS
# and access logging have done their bookkeeping.
app.add_middleware(BodySizeLimitMiddleware)

# Added last so it is the outermost middleware (Starlette inserts each new
# middleware at the front of the stack), letting a flood be refused before any
# body is read. Ordering is asserted empirically in
# tests/test_swarm_api_rate_limit.py rather than assumed.
#
# DISABLED UNDER PYTEST (v2 Part 20). The limiter keys on client IP, and every
# TestClient request presents the same one, so a fast suite trips the shared
# per-IP window and unrelated tests fail with 429 — observed as 27 failures on
# the no-rembg path only, because that path runs fast enough to fill the
# window while the slower rembg path does not. That makes it an ORDER- AND
# SPEED-DEPENDENT failure, the worst kind to debug later. Tests that exercise
# the limiter instantiate RateLimitMiddleware directly with their own bounds
# (tests/test_swarm_api_rate_limit.py), so coverage is unaffected.
#
# It stays WIRED under pytest (so the ordering assertions keep guarding the
# production stack) but with enforcement OFF; detection is `"pytest" in
# sys.modules`, evaluated at import, because PYTEST_CURRENT_TEST is only set
# once a test is RUNNING and this module is imported during collection.
app.add_middleware(RateLimitMiddleware, enabled="pytest" not in sys.modules)

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
def health() -> dict[str, str | int]:
    """Liveness probe: dependency-free, touches no I/O, and must never raise —
    a monitor that gets a 500 here cannot distinguish it from a dead process."""
    return {
        "status": "ok",
        "version": app.version,
        "uptimeSeconds": int(time.monotonic() - _STARTED_MONOTONIC),
        "pythonVersion": platform.python_version(),
    }


for module in (auth, files, convert, digitize, lettering, worksheet, export, threads, designs, optimize, auth_local, admin, image_edit, thread_edit, stitch_edit):
    app.include_router(module.router, prefix="/api")
