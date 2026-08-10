"""STEP 0: digitize and rebuild finish a segment with the SAME parameters.

CTO verdict 2026-08-09. `digitize_image` and `rebuild_design` call the same
finishing generators — `_coalesce_short`, then `_route_travel` — but each
computed the arguments inline, and they had drifted:

  * `route_pad`  digitize `(FILL_BORDER_MM/2 + pull)/mm_per_px` -> 8px
                 rebuild  `pull/mm_per_px`                      -> 2px
  * coalesce     digitize clamps a FILL's minimum to its own row pitch
                 (`FILL_ROW_CONNECT_KEEP`) and passes the penetration floor
                 for satin; rebuild did neither.

Measured cost of the pad divergence on P1's own ring, rebuilt after a real
1% density edit: **98 needle paths straight across the open counter**, against
0 for a fresh digitize of the same artwork. C2 was closed on the digitize path
and open on every edit — which the §8 probes could not see, because they only
ever exercise digitize (that blindness is STEP 1's job).

These tests pin the fix from both directions: the behaviour (the ring), and the
STRUCTURE (nobody re-derives these numbers inline). The structural test is the
load-bearing one — duplication is what caused the drift in the first place, so
a test that only checked today's values would pass again the moment someone
copied the constant back.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.models.design import Design
from app.services.digitizer import digitize_image
from app.services.digitizer.constants import (
    FILL_BORDER_MM,
    FILL_ROW_CONNECT_KEEP,
    MIN_STITCH_MM,
)
from app.services.digitizer.rebuild import rebuild_design
from app.services.digitizer.routing import coalesce_params, travel_route_pad_px

DIGITIZER = Path(__file__).resolve().parents[1] / "app" / "services" / "digitizer"


# ── the shared functions themselves ──────────────────────────────────────────


def test_route_pad_includes_the_border_overhang():
    """The whole point of the pad: border satin sits astride the outline, so a
    connection endpoint is legitimately outside the region by half the border
    width plus pull comp. Omitting the border term is what left rebuild at 2px."""
    mm_per_px = 0.1
    assert travel_route_pad_px(0.2, mm_per_px) == round((FILL_BORDER_MM / 2 + 0.2) / mm_per_px)
    # ... and it is strictly more than the pull-only version rebuild used.
    assert travel_route_pad_px(0.2, mm_per_px) > max(2, round(0.2 / mm_per_px))
    # Floor of 2px survives for a zero-pull object on a coarse raster.
    assert travel_route_pad_px(0.0, 10.0) == 2
    # Never negative, whatever a stored object carries.
    assert travel_route_pad_px(-5.0, 0.1) == round((FILL_BORDER_MM / 2) / 0.1)


def test_coalesce_clamps_fills_to_their_row_pitch_and_nothing_else():
    mm_per_px = 0.1
    row_px = 0.40 / mm_per_px  # a 0.40mm cotton row pitch

    # A fill keeps its row-to-row connection, which IS one pitch long.
    fill_min, fill_floor = coalesce_params(mm_per_px, is_satin=False, fill_row_px=row_px)
    assert fill_min == pytest.approx(row_px * FILL_ROW_CONNECT_KEEP)
    assert fill_min < MIN_STITCH_MM / mm_per_px
    assert fill_floor == 0.0, "a tatami row never zigzags; the floor repair cannot fire"

    # Satin gets the flat minimum AND the penetration floor.
    sat_min, sat_floor = coalesce_params(mm_per_px, is_satin=True)
    assert sat_min == pytest.approx(MIN_STITCH_MM / mm_per_px)
    assert sat_floor > 0.0

    # A RUN's 1/density spacing is NOT a row pitch. Passing it would lower the
    # minimum for running stitch, which is the opposite of what the clamp is
    # for — so callers pass None and get the flat floor.
    run_min, _ = coalesce_params(mm_per_px, is_satin=False, fill_row_px=None)
    assert run_min == pytest.approx(MIN_STITCH_MM / mm_per_px)

    # The clamp only ever LOWERS toward the pitch; a coarse fill does not get a
    # minimum above the needle-safety floor.
    coarse, _ = coalesce_params(mm_per_px, is_satin=False, fill_row_px=5.0 / mm_per_px)
    assert coarse == pytest.approx(MIN_STITCH_MM / mm_per_px)


# ── the structural guard ─────────────────────────────────────────────────────


# Each derived quantity has exactly ONE owning module. Anywhere else is a copy.
DERIVATION_OWNERS = {
    "border overhang (travel_route_pad_px)": "routing.py",
    "border sweep width (fill_border_width_px)": "satin.py",
    "fill row clamp (coalesce_params)": "routing.py",
}


def _inline_derivations(path: Path) -> list[tuple[str, str]]:
    """Find code that re-derives a finishing parameter instead of calling the
    shared function. Returns (quantity, "file:line") pairs.

    The three quantities are recognisable in the AST: `FILL_BORDER_MM / 2` (the
    routing overhang), `FILL_BORDER_MM / <anything else>` (the border sweep
    width) and a multiply by `FILL_ROW_CONNECT_KEEP` (the fill row clamp).
    """
    tree = ast.parse(path.read_text())
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp):
            continue
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        # `node.left` must be the constant ITSELF, not merely contain it —
        # otherwise the enclosing `(FILL_BORDER_MM / 2 + pull) / mm_per_px`
        # inside travel_route_pad_px matches twice, once per division.
        direct = isinstance(node.left, ast.Name) and node.left.id == "FILL_BORDER_MM"
        if direct and isinstance(node.op, ast.Div):
            halved = isinstance(node.right, ast.Constant) and node.right.value == 2
            what = ("border overhang (travel_route_pad_px)" if halved
                    else "border sweep width (fill_border_width_px)")
            hits.append((what, f"{path.name}:{node.lineno}"))
        if "FILL_ROW_CONNECT_KEEP" in names and isinstance(node.op, ast.Mult):
            hits.append(("fill row clamp (coalesce_params)", f"{path.name}:{node.lineno}"))
    return hits


def test_no_module_re_derives_a_quantity_another_one_owns():
    """The regression this file exists to prevent is not a wrong number — it is
    a SECOND copy of the number. Each quantity has one owner; a copy anywhere
    else is how digitize and rebuild came apart in the first place."""
    offenders = []
    for path in sorted(DIGITIZER.glob("*.py")):
        for what, where in _inline_derivations(path):
            if DERIVATION_OWNERS[what] != path.name:
                offenders.append(f"{where} re-derives {what}")
    assert not offenders, (
        "call the shared function instead of re-deriving:\n  " + "\n  ".join(offenders)
    )


def test_every_owned_quantity_is_actually_found_by_the_matcher():
    """A source-scanning test that matched nothing would pass forever. Assert
    the matcher finds each quantity exactly where it is supposed to live."""
    for what, owner in DERIVATION_OWNERS.items():
        found = [w for w, _ in _inline_derivations(DIGITIZER / owner)]
        assert what in found, (
            f"the AST matcher no longer finds {what} in its owner {owner} — "
            f"either it moved (update DERIVATION_OWNERS) or the matcher is dead"
        )


def test_both_paths_call_the_shared_functions():
    pipeline = (DIGITIZER / "pipeline.py").read_text()
    rebuild = (DIGITIZER / "rebuild.py").read_text()
    routing = (DIGITIZER / "routing.py").read_text()
    assert "travel_route_pad_px(" in pipeline
    assert "travel_route_pad_px(" in rebuild
    assert "coalesce_params(" in pipeline
    # rebuild reaches coalesce_params through _finish_rebuild_segment.
    assert "coalesce_params(" in routing
    assert "fill_border_width_px(" in pipeline
    assert "fill_border_width_px(" in (DIGITIZER / "satin.py").read_text()


# ── the behaviour: P1's ring, on the path the probes cannot see ──────────────


@pytest.fixture(scope="module")
def ring() -> Design:
    """P1's fixture verbatim: a letter-'o'-class ring with an open counter."""
    img = np.full((600, 600, 3), 255, np.uint8)
    cv2.circle(img, (300, 300), 200, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (300, 300), 110, (255, 255, 255), -1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    cv2.setRNGSeed(1234)
    return digitize_image(buf.tobytes(), "cotton", "100x100", 2)


def _counter_crossings(design: Design) -> int:
    """P1's metric verbatim — needle paths through the counter's open area."""
    hole = next((o.holes[0] for o in design.objects if o.holes), None)
    assert hole is not None, "ring digitized without its counter"
    poly = np.array([[p.x, p.y] for p in hole], np.float32)
    cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
    shrunk = ((poly - [cx, cy]) * 0.93 + [cx, cy]).astype(np.float32)
    crossings, prev = 0, None
    for s in design.stitches:
        if str(s.command) in ("STITCH", "JUMP") and prev is not None:
            n = max(2, int(math.dist(prev, (s.x, s.y)) / 0.3))
            for i in range(1, n):
                t = i / n
                x = prev[0] + (s.x - prev[0]) * t
                y = prev[1] + (s.y - prev[1]) * t
                if cv2.pointPolygonTest(shrunk, (float(x), float(y)), False) >= 0:
                    crossings += 1
                    break
        prev = (s.x, s.y)
    return crossings


def _edited(design: Design) -> Design:
    """A REAL edit — 1% density on the first object. Anything less and the
    provenance pass-through returns the design untouched and the rebuild path
    is never exercised at all."""
    d = design.model_copy(deep=True)
    d.objects[0].density = round(float(d.objects[0].density or 4.0) * 1.01, 6)
    return d


def test_editing_the_ring_does_not_reopen_the_counter(ring):
    """98 -> 1, measured. The residual one is a single connection the router
    still declines; it is pinned rather than rounded to zero so a return of the
    old behaviour is unmistakable."""
    edited = rebuild_design(_edited(ring))
    assert edited is not ring, "the pass-through swallowed a real density edit"
    crossings = _counter_crossings(edited)
    assert crossings <= 2, (
        f"{crossings} needle paths cross the ring's open counter after an edit "
        f"(was 98 with rebuild's 2px route_pad; digitize is 0) — has route_pad "
        f"dropped the border-overhang term again?"
    )


def test_the_crossing_probe_would_catch_a_regression(ring):
    """Guard the guard: with BOTH defenses removed, the counter reopens.
    Without this, a probe that silently stopped measuring would read as a pass.

    THERE ARE NOW TWO DEFENSES, AND THIS CONTROL HAS TO DISABLE BOTH.
    Originally there was one — `travel_route_pad_px` — and forcing it back to
    rebuild's old pull-only value produced 98 crossings. CTO 1b added a second,
    upstream: `_boustrophedon_cells` stops the fill from ever emitting a
    left-run-to-right-run connection across the counter, so the router is never
    asked to bridge the hole and a too-generous pad has almost nothing to route
    through it. With only the pad forced, this control now reads **2**.

    That is not the probe going blind — it is the defect it was written for
    having largely ceased to exist upstream. But accepting the 2 would have
    quietly retired the control, so it now also restores the pre-1b emission
    order: one cell holding every run in row-major order, which is exactly what
    `_scanline_fill` used to produce. The assertion again means what it says.
    """
    from app.services.digitizer import fills as fills_mod
    from app.services.digitizer import rebuild as rebuild_mod

    original_pad = rebuild_mod.travel_route_pad_px
    original_cells = fills_mod._boustrophedon_cells
    rebuild_mod.travel_route_pad_px = lambda pull_mm, mm_per_px: max(
        2, round(float(pull_mm) / mm_per_px)
    )
    fills_mod._boustrophedon_cells = lambda rows: [
        [(y, seg) for y, segs in rows for seg in segs]
    ]
    try:
        regressed = _counter_crossings(rebuild_design(_edited(ring)))
    finally:
        rebuild_mod.travel_route_pad_px = original_pad
        fills_mod._boustrophedon_cells = original_cells
    assert regressed > 20, (
        f"forcing the old 2px pad AND the old row-major fill order produced "
        f"only {regressed} crossings — the probe is no longer sensitive to the "
        f"defect it was written for"
    )
