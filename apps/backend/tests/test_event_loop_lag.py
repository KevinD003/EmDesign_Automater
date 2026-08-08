"""CTO B1/X1 — CPU work must not freeze the event loop.

WHAT THE REVIEW GOT RIGHT AND WRONG. X1 claimed the CPU-heavy endpoints "run
synchronously inside `async def` handlers" and that the first fix is a one-word
`async def` → `def`. Measured against this tree, the premise is stale: digitize,
rebuild, lettering, convert, package, export, worksheet and the stitch/image
editors are ALL already `def`, so FastAPI already runs them in the threadpool.
The freeze the review observed is real, but its mechanism is the GIL — a worker
thread doing pure-Python work (building tens of thousands of pydantic Stitch
models) holds the interpreter lock, and the loop thread cannot run meanwhile.
Measured 2026-08-08: one digitize = 5,747ms request, **1,198ms worst loop
stall**, with the handler already in the threadpool. The queue with separate
worker PROCESSES is therefore the actual fix, not a nice-to-have.

What this file pins is the part that was genuinely on the loop and is now off
it: the `designs` router awaited nothing for its file reads and rendered PNG
thumbnails inline (preview measured a 174ms stall; a plain GET, 50ms).

WHY TWO OF THESE CARRY `@pytest.mark.timing`. They pass standalone and fail
inside a full `pytest tests` run — the suite loads the machine enough that
scheduling delay stops measuring the application. They are therefore
deselected by default (see pyproject) and run with `pytest -m timing` on an
idle machine. Loosening the ratio until they could not fail was the other
option and was rejected: a timing guard that cannot fail proves nothing. The
structural guard below has no such problem and is what actually prevents a
regression.

MEASUREMENT NOTE. Per-request latency cannot see a blocked loop — a blocked
loop simply never schedules the poller, so the stall falls between samples.
The instrument is scheduling delay: tick every 5ms and record how late each
tick fires. Assertions are RELATIVE (lag as a fraction of the request's own
duration), because absolute milliseconds are a property of the machine: before
the fix lag/duration ≈ 1.0 (the loop is frozen for the whole request), after it
is ~0.2 on the same hardware.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time

import httpx
import pytest

TICK_S = 0.005
# Ratio of (worst loop stall) / (request duration). 1.0 means the loop was dead
# for the entire request; the pre-fix preview sat at ~1.0. 0.6 leaves room for
# GIL contention from the threadpool worker without admitting a frozen loop.
MAX_LAG_RATIO = 0.6


async def _lag_during(client: httpx.AsyncClient, method: str, url: str) -> tuple[float, float, int]:
    """(worst_lag_ms, request_ms, status) while `method url` is in flight."""
    lags: list[float] = []
    stop = asyncio.Event()

    async def ticker() -> None:
        while not stop.is_set():
            t = time.perf_counter()
            await asyncio.sleep(TICK_S)
            lags.append((time.perf_counter() - t - TICK_S) * 1000)

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)  # let the ticker settle
    t0 = time.perf_counter()
    resp = await client.request(method, url)
    request_ms = (time.perf_counter() - t0) * 1000
    stop.set()
    await task
    assert lags, "ticker never ran"
    return max(lags), request_ms, resp.status_code


@pytest.fixture()
def saved_design(tmp_path, monkeypatch):
    """A real 17k-stitch design in an isolated local store."""
    from helpers import digitized_fixture

    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(tmp_path / "designs"))
    from app.services import local_store

    return local_store.create_design(digitized_fixture(), "local-dev")


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.timing
@pytest.mark.skipif(os.environ.get("CI") == "true",
                    reason="scheduling-delay measurement; shared CI runners add "
                           "their own jitter and the ratio stops meaning anything")
def test_thumbnail_render_does_not_freeze_the_loop(saved_design):
    # The B8 library grid fires one of these per tile. Rendering inline meant N
    # thumbnails = N sequential freezes with /health stuck behind them.
    from app.main import app

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t", timeout=60) as c:
            await c.get("/health")  # warm the import path
            return await _lag_during(c, "GET", f"/api/designs/{saved_design.id}/preview")

    lag_ms, req_ms, status = _run(go())
    assert status == 200
    assert lag_ms / req_ms < MAX_LAG_RATIO, (
        f"preview froze the loop for {lag_ms:.0f}ms of a {req_ms:.0f}ms request "
        f"(ratio {lag_ms / req_ms:.2f}) — is render_preview back on the loop?"
    )


@pytest.mark.timing
@pytest.mark.skipif(os.environ.get("CI") == "true",
                    reason="scheduling-delay measurement; see above")
def test_design_fetch_does_not_freeze_the_loop(saved_design):
    # local_store reads a JSON file and parses a full design; inline that is
    # tens of milliseconds of dead loop on every library call.
    from app.main import app

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t", timeout=60) as c:
            await c.get("/health")
            return await _lag_during(c, "GET", f"/api/designs/{saved_design.id}")

    lag_ms, req_ms, status = _run(go())
    assert status == 200
    assert lag_ms / req_ms < MAX_LAG_RATIO, (
        f"design GET froze the loop for {lag_ms:.0f}ms of {req_ms:.0f}ms "
        f"(ratio {lag_ms / req_ms:.2f}) — is local_store back on the loop?"
    )


def test_every_cpu_heavy_handler_is_off_the_loop():
    """Structural guard, no timing: a CPU-heavy route is either a plain `def`
    (FastAPI threadpools it) or an `async def` whose body hands the work to
    `run_in_threadpool`. This is what stops someone "tidying" a handler into
    `async def` and silently re-freezing the app."""
    import ast
    import pathlib

    heavy = {
        "digitize.py": {"digitize"},
        "lettering.py": {"create_lettering"},
        "convert.py": {"convert"},
        "export.py": {"export_design", "export_package"},
        "worksheet.py": {"build_worksheet", "worksheet_pdf_download"},
        "optimize.py": {"optimize_path", "quality"},
        "stitch_edit.py": {"edit"},
        "image_edit.py": {"edit", "analyze"},
        "designs.py": {"rebuild", "design_preview"},
    }
    routers = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
    offenders = []
    for filename, names in heavy.items():
        tree = ast.parse((routers / filename).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef) or node.name not in names:
                continue
            body = ast.dump(node)
            if "run_in_threadpool" not in body:
                offenders.append(f"{filename}:{node.name}")
    assert not offenders, (
        f"async handlers doing CPU work on the event loop: {offenders}. Make them "
        f"`def`, or await run_in_threadpool(...) around the heavy call."
    )


def test_measurement_instrument_detects_a_real_stall():
    """The instrument must be able to FAIL. A deliberately blocking endpoint
    has to trip the same ratio the guards above rely on — otherwise a green
    result proves nothing."""
    from fastapi import FastAPI

    blocker = FastAPI()

    @blocker.get("/block")
    async def block() -> dict:
        # Blocking on purpose — this endpoint IS the negative control. ASYNC251
        # is exactly the defect being simulated, so the lint is silenced here
        # and nowhere else.
        time.sleep(0.3)  # noqa: ASYNC251 - deliberate: never yields to the loop
        return {"ok": True}

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=blocker),
                                     base_url="http://t", timeout=30) as c:
            return await _lag_during(c, "GET", "/block")

    lag_ms, req_ms, status = _run(go())
    assert status == 200
    assert lag_ms / req_ms >= MAX_LAG_RATIO, (
        f"instrument failed to detect a 300ms hard block "
        f"(lag {lag_ms:.0f}ms of {req_ms:.0f}ms) — the guards above are worthless"
    )
    assert statistics.median([lag_ms]) > 100  # sanity: the stall is real, not noise
