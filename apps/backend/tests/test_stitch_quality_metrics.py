"""Tests for the committed stitch-quality measurement (v2 Part 5).

The metrics grade the pipeline, so a wrong metric is worse than no metric: it
would silently move every audit number. These pin the definitions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from measure_stitch_quality import coverage_metrics, penetration_metrics, same_side_spacings

from app.services.digitizer import MIN_PENETRATION_MM, digitize_image, set_penetration_floor


@pytest.fixture(autouse=True)
def _restore_penetration_floor():
    """Never let a test leak the module-level floor into the next one.

    Without this, a test that disabled the floor in a `finally` left the whole
    rest of the session running unenforced — which is how the first version of
    `test_floor_is_enforced_by_default` failed.
    """
    from app.services.digitizer import MIN_PENETRATION_MM

    yield
    set_penetration_floor(MIN_PENETRATION_MM)


class _S:
    """Minimal stitch stand-in: the metrics only read x, y and command."""

    def __init__(self, x, y, command="STITCH"):
        self.x, self.y, self.command = x, y, command


def _satin_path(pitch: float, width: float, n: int) -> list[_S]:
    """A0 B0 A1 B1 ... — a textbook satin zigzag with a known same-side pitch."""
    out = []
    for i in range(n):
        out.append(_S(i * pitch, 0.0))
        out.append(_S(i * pitch, width))
    return out


def test_same_side_spacing_equals_the_pitch():
    gaps = same_side_spacings(_satin_path(pitch=0.4, width=3.0, n=20))
    assert gaps, "a satin zigzag must yield same-side pairs"
    assert all(abs(g - 0.4) < 1e-9 for g in gaps)


def test_running_stitch_is_not_counted_as_satin():
    """A line of penetrations advancing along one path has no same-side pairs."""
    run = [_S(i * 2.0, 0.0) for i in range(20)]
    assert same_side_spacings(run) == []


def test_tatami_rows_are_not_counted_as_satin():
    """Scanline points advance ALONG a row, so no triple zigzags."""
    rows = []
    for r in range(6):
        y = r * 0.45
        xs = range(20) if r % 2 == 0 else reversed(range(20))
        rows += [_S(x * 0.5, y) for x in xs]
    assert same_side_spacings(rows) == []


def test_jump_breaks_a_run():
    path = _satin_path(0.4, 3.0, 5) + [_S(50.0, 50.0, "JUMP")] + _satin_path(0.4, 3.0, 5)
    # Two independent runs: neither contributes a pair spanning the jump.
    assert all(abs(g - 0.4) < 1e-9 for g in same_side_spacings(path))


def test_tight_curve_packs_penetrations_below_the_pitch():
    """The defect the metric exists to catch, on a synthetic concave arc.

    Outer side paced at the nominal pitch; inner side on a radius half as large
    therefore advances half as far between columns.
    """
    outer_r, inner_r, pitch = 8.0, 4.0, 0.4
    steps = 30
    path = []
    for i in range(steps):
        a = i * pitch / outer_r          # angle advance set by the OUTER boundary
        path.append(_S(outer_r * np.cos(a), outer_r * np.sin(a)))
        path.append(_S(inner_r * np.cos(a), inner_r * np.sin(a)))
    gaps = sorted(same_side_spacings(path))
    assert gaps[0] < pitch * 0.6, f"inner side should pack up, got {gaps[0]:.3f}"


def _ring_bytes(radius_px: int, stroke_px: int = 16) -> bytes:
    img = np.full((320, 320, 3), 255, np.uint8)
    cv2.circle(img, (160, 160), radius_px, (30, 30, 40), thickness=stroke_px)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_penetration_floor_removes_violations_on_a_tight_ring():
    """A ring has no terminals, so this isolates curvature. Floor off vs on."""
    art = _ring_bytes(radius_px=32)
    try:
        set_penetration_floor(None)
        loose = digitize_image(art, "cotton", "100x100", max_colors=2)
        before = penetration_metrics(loose, 0.4, 0.30)

        set_penetration_floor(0.30)
        tight = digitize_image(art, "cotton", "100x100", max_colors=2)
        after = penetration_metrics(tight, 0.4, 0.30)
    finally:
        set_penetration_floor(MIN_PENETRATION_MM)

    assert before.get("satin_objects"), "a 16px-wide ring must digitize as satin"
    assert before["below_floor"] > 0, "the tight ring must violate the floor when unenforced"
    assert after["below_floor"] == 0, f"floor left {after['below_floor']} violations"
    assert after["min_spacing_mm"] >= 0.30 - 1e-6


def test_floor_is_enforced_by_default():
    """v2 Part 6 turned enforcement on; the shipped default must honour the floor."""
    from app.services import digitizer

    assert digitizer._PENETRATION_FLOOR_MM == MIN_PENETRATION_MM
    design = digitize_image(_ring_bytes(radius_px=32), "cotton", "100x100", max_colors=2)
    pen = penetration_metrics(design, 0.4, MIN_PENETRATION_MM)
    assert pen["satin_objects"], "a 16px-wide ring must digitize as satin"
    assert pen["below_floor"] == 0, f"default build left {pen['below_floor']} violations"


def test_enforcement_does_not_change_which_objects_are_satin():
    """The floor removes columns; it must never flip a classification verdict."""
    art = _ring_bytes(radius_px=48)
    try:
        set_penetration_floor(None)
        loose = digitize_image(art, "cotton", "100x100", max_colors=2)
        set_penetration_floor(MIN_PENETRATION_MM)
        tight = digitize_image(art, "cotton", "100x100", max_colors=2)
    finally:
        set_penetration_floor(MIN_PENETRATION_MM)
    assert [o.stitch_type for o in loose.objects] == [o.stitch_type for o in tight.objects]
    assert tight.stitch_count < loose.stitch_count, "the floor should remove columns"


def test_coverage_metrics_on_a_fully_stitched_shape():
    """Interior/edge-band/spill are percentages in range, and a real fill scores high."""
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (160, 160), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    design = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    cov = coverage_metrics(design)
    assert 0.0 <= cov["edge_band_pct"] <= 100.0
    assert 0.0 <= cov["spill_pct"] <= 100.0
    assert cov["interior_pct"] is not None and cov["interior_pct"] > 80.0


def test_interior_is_none_for_a_shape_thinner_than_the_erosion():
    """A hairline has no interior; reporting 0% would read as a coverage failure."""
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.line(img, (20, 100), (180, 100), (40, 40, 40), thickness=2)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    design = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    assert coverage_metrics(design)["interior_pct"] is None


def test_measure_cli_runs_and_writes_json(tmp_path, monkeypatch, capsys):
    """The committed script must be runnable as-is — that is the point of committing it."""
    import measure_stitch_quality as msq

    out = tmp_path / "metrics.json"
    monkeypatch.setattr(
        sys, "argv",
        ["measure_stitch_quality.py", "--fixture", "04_thin_line_outline", "--json", str(out)],
    )
    assert msq._main() == 0
    printed = capsys.readouterr().out
    assert "04_thin_line_outline" in printed
    assert "edge band" in printed

    payload = __import__("json").loads(out.read_text())
    rec = payload["04_thin_line_outline"]
    assert rec["coverage"]["edge_band_pct"] > 90.0
    # 10 of the fixture's 11 satin objects yield same-side pairs; the hub circle
    # is too short to produce a zigzag triple, and is skipped rather than counted
    # as a zero-penetration object.
    assert rec["penetration"]["satin_objects"] == 10


def test_measure_cli_rejects_an_unknown_fixture(monkeypatch):
    import measure_stitch_quality as msq

    monkeypatch.setattr(sys, "argv", ["measure_stitch_quality.py", "--fixture", "nope"])
    assert msq._main() == 2


def test_bench_records_coverage_and_penetration(tmp_path):
    """The harness carries the metrics into the per-fixture JSON, via the shared module."""
    import run_quality_bench as bench

    fixture = bench.FIXTURE_DIR / "04_thin_line_outline.png"
    result = bench.run_fixture(fixture, tmp_path)
    assert result.ok and not result.error
    assert result.coverage["edge_band_pct"] > 90.0
    assert result.penetration["satin_objects"] == 10
    assert result.penetration["nominal_pitch_mm"] == 0.4
    # The safety number must be present even when nothing violates the floor.
    assert "min_spacing_mm" in result.penetration
