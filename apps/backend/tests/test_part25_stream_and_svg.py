"""v2 Part 25 — travel runs, lock stitches, stop merging, warnings, SVG input.

Each test pins one of the measured defects from docs/COMPETITIVE-BLOCKERS.md:
1,206 jumps with 638 untrimmed past the machine limit; no tie-off code at all;
5 avoidable colour changes; a 40x40mm hoop deleting 81% of a design silently;
and SVG uploads rejected at the decoder.
"""

from __future__ import annotations

import math
from itertools import pairwise

import cv2
import numpy as np
import pytest

from app.services.digitizer import (
    MIN_PENETRATION_MM,
    TRIM_JUMP_MM,
    ZIGZAG_RATIO,
    _lock_stream,
    _merge_adjacent_same_hex,
    digitize_image,
)


def _two_blobs_far_apart() -> bytes:
    """One colour, two islands 60mm apart: forces a long cross-fabric move."""
    img = np.full((400, 400, 3), 255, np.uint8)
    cv2.circle(img, (70, 70), 45, (40, 40, 200), -1)
    cv2.circle(img, (330, 330), 45, (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _floor_violations(design) -> int:
    """Same triple rule as scripts/measure_stitch_quality.py, self-contained."""
    bad = 0
    run: list[tuple[float, float]] = []
    runs = []
    for s in design.stitches:
        if s.command == "STITCH":
            run.append((s.x, s.y))
        else:
            if len(run) >= 3:
                runs.append(run)
            run = []
    if len(run) >= 3:
        runs.append(run)
    for run in runs:
        for a, b, c in zip(run, run[1:], run[2:]):
            gap = math.dist(a, c)
            if gap < ZIGZAG_RATIO * min(math.dist(a, b), math.dist(b, c)) and gap < MIN_PENETRATION_MM:
                bad += 1
    return bad


def test_every_thread_cut_is_preceded_by_a_lock():
    """Before Part 25 there was no tie-off code at all: 6 of the badge's 20
    cuts had nothing before them, and the 14 that looked locked were an
    accident of dense satin ends."""
    d = digitize_image(_two_blobs_far_apart(), "cotton", "130x180", max_colors=2)
    stitched = 0
    for i, s in enumerate(d.stitches):
        if s.command not in ("TRIM", "COLOR_CHANGE", "END"):
            continue
        prev = [p for p in d.stitches[max(0, i - 4):i] if p.command == "STITCH"]
        if len(prev) < 4:
            continue  # a cut straight after a jump has nothing to lock
        stitched += 1
        # The three lock penetrations live within ~2mm of the anchor.
        anchor = prev[-1]
        assert all(math.hypot(p.x - anchor.x, p.y - anchor.y) < 2.5 for p in prev[-3:]), (
            f"cut at stream index {i} has no lock cluster before it"
        )
    assert stitched >= 1


def test_long_cross_fabric_jumps_are_trimmed():
    """638 corpus jumps exceeded the 12.7mm machine limit with no trim — a
    thread trail dragged across the design, cut by hand afterwards."""
    d = digitize_image(_two_blobs_far_apart(), "cotton", "130x180", max_colors=2)
    prev = None
    last_cmd = None
    for s in d.stitches:
        if s.command == "JUMP" and prev is not None and last_cmd == "STITCH":
            assert math.hypot(s.x - prev.x, s.y - prev.y) <= TRIM_JUMP_MM, (
                "a long jump left stitching without a TRIM before it"
            )
        last_cmd = s.command
        prev = s


def test_locks_and_travel_respect_the_penetration_floor():
    """The first tie design put 92 same-side pairs under the 0.30mm floor and
    the first travel router added 11 more at out-and-back turnarounds. Both
    fixes are behavioural, so this guards them end-to-end."""
    d = digitize_image(_two_blobs_far_apart(), "cotton", "130x180", max_colors=2)
    assert _floor_violations(d) == 0


def test_adjacent_same_hex_stops_merge():
    """5 of 10 corpus fixtures mounted a thread the machine already had."""
    from app.models.design import ColorStop, DesignObject, Point, Stitch, StitchType

    stitches = [
        Stitch(x=0, y=0, command="STITCH"), Stitch(x=1, y=0, command="STITCH"),
        Stitch(x=1, y=0, command="COLOR_CHANGE"),
        Stitch(x=5, y=5, command="JUMP"),
        Stitch(x=5, y=5, command="STITCH"), Stitch(x=6, y=5, command="STITCH"),
        Stitch(x=6, y=5, command="COLOR_CHANGE"),
        Stitch(x=9, y=9, command="JUMP"),
        Stitch(x=9, y=9, command="STITCH"), Stitch(x=9, y=8, command="STITCH"),
    ]
    stops = [
        ColorStop(stop_number=1, thread_brand="A", catalog_number="", thread_name="Color 1", hex="#111111", penetration_count=2),
        ColorStop(stop_number=2, thread_brand="A", catalog_number="", thread_name="Color 2", hex="#111111", penetration_count=2),
        ColorStop(stop_number=3, thread_brand="A", catalog_number="", thread_name="Color 3", hex="#222222", penetration_count=2),
    ]
    objs = [
        DesignObject(sequence_order=i + 1, name=f"o{i}", stitch_type=StitchType.TATAMI,
                     color_stop=i + 1, entry_point=Point(x=0, y=0), exit_point=Point(x=1, y=1))
        for i in range(3)
    ]
    merged = _merge_adjacent_same_hex(stitches, stops, objs)
    assert merged == 1
    assert [s.stop_number for s in stops] == [1, 2]
    assert [s.hex for s in stops] == ["#111111", "#222222"]
    assert stops[0].penetration_count == 4
    assert [o.color_stop for o in objs] == [1, 1, 2]
    # The removed COLOR_CHANGE became a TRIM; one colour change remains.
    assert sum(1 for s in stitches if s.command == "COLOR_CHANGE") == 1
    assert sum(1 for s in stitches if s.command == "TRIM") == 1


def test_non_adjacent_same_hex_stops_do_not_merge():
    """Layering: the deferred detail pass must stay AFTER the fill that covers
    its holes, so a same-hex stop with another colour between stays separate."""
    from app.models.design import ColorStop, Stitch

    stitches = [
        Stitch(x=0, y=0, command="STITCH"), Stitch(x=1, y=0, command="STITCH"),
        Stitch(x=1, y=0, command="COLOR_CHANGE"),
        Stitch(x=2, y=0, command="STITCH"), Stitch(x=3, y=0, command="STITCH"),
        Stitch(x=3, y=0, command="COLOR_CHANGE"),
        Stitch(x=4, y=0, command="STITCH"), Stitch(x=5, y=0, command="STITCH"),
    ]
    stops = [
        ColorStop(stop_number=1, thread_brand="A", catalog_number="", thread_name="Color 1", hex="#111111", penetration_count=2),
        ColorStop(stop_number=2, thread_brand="A", catalog_number="", thread_name="Color 2", hex="#222222", penetration_count=2),
        ColorStop(stop_number=3, thread_brand="A", catalog_number="", thread_name="Color 3", hex="#111111", penetration_count=2),
    ]
    assert _merge_adjacent_same_hex(stitches, stops, []) == 0
    assert len(stops) == 3


def test_small_hoop_warns_instead_of_failing_silently():
    """The measured silent failure: badge into 40x40mm lost 17 of 21 objects
    with nothing said. Detection is the fine-detail scale heuristic — the loss
    happens in colour segmentation, which no post-hoc filter accounting sees."""
    img = np.full((640, 640, 3), 255, np.uint8)
    cv2.circle(img, (320, 320), 280, (60, 60, 160), -1)
    cv2.circle(img, (320, 320), 200, (240, 244, 248), -1)
    for a in range(0, 360, 30):  # fine radial ticks: detail a 40mm hoop cannot hold
        x0 = int(320 + 210 * math.cos(math.radians(a)))
        y0 = int(320 + 210 * math.sin(math.radians(a)))
        x1 = int(320 + 260 * math.cos(math.radians(a)))
        y1 = int(320 + 260 * math.sin(math.radians(a)))
        cv2.line(img, (x0, y0), (x1, y1), (20, 200, 220), 3)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    big = digitize_image(buf.tobytes(), "cotton", "130x180", max_colors=3)
    small = digitize_image(buf.tobytes(), "cotton", "40x40", max_colors=3)
    assert not any("px across" in w for w in big.warnings)
    assert any("px across" in w for w in small.warnings), small.warnings


def test_colour_count_mismatch_is_explained():
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.circle(img, (150, 150), 100, (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=6)
    assert any("colour" in w for w in d.warnings), d.warnings


SVG_BADGE = b"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">
  <circle cx="200" cy="200" r="170" fill="#1e3a5f"/>
  <circle cx="200" cy="200" r="135" fill="#f5f0e0"/>
  <circle cx="200" cy="200" r="95" fill="#1e3a5f"/>
  <rect x="150" y="285" width="100" height="16" rx="8" fill="#d7a52d"/>
</svg>"""


def test_svg_digitizes_with_exact_source_colours():
    """SVG was rejected at the decoder before Part 25. The colours must come
    back as the EXACT source hexes — vector input has no anti-aliased blends to
    estimate through."""
    d = digitize_image(SVG_BADGE, "cotton", "100x100", max_colors=4)
    assert d.objects, "SVG produced no objects"
    assert {s.hex for s in d.color_stops} == {"#1e3a5f", "#f5f0e0", "#d7a52d"}


def test_svg_white_artwork_on_white_page_survives():
    """The case every raster heuristic gets wrong by definition: a white
    element on a white page is invisible to substrate-colour rules and neural
    mattes alike, but the vector file states it explicitly. Measured: the
    substrate rule deleted exactly this until it was gated off for vector."""
    svg = b"""<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300">
      <circle cx="150" cy="150" r="100" fill="#ffffff"/>
      <circle cx="150" cy="150" r="55" fill="#c03030"/>
    </svg>"""
    d = digitize_image(svg, "cotton", "100x100", max_colors=2)
    assert {s.hex for s in d.color_stops} == {"#ffffff", "#c03030"}


def test_svg_stream_is_machine_valid():
    d = digitize_image(SVG_BADGE, "cotton", "100x100", max_colors=4)
    assert _floor_violations(d) == 0
    for a, b in pairwise(d.stitches):
        if a.command == "STITCH" and b.command == "STITCH":
            assert math.hypot(b.x - a.x, b.y - a.y) <= 12.7


def test_garbage_bytes_still_rejected():
    with pytest.raises(ValueError):
        digitize_image(b"<html><body>not an image</body></html>")
    with pytest.raises(ValueError):
        digitize_image(b"\x00\x01\x02garbage")


def test_lock_stream_empty_and_tiny_inputs():
    from app.models.design import Stitch

    assert _lock_stream([]) == []
    one = [Stitch(x=0, y=0, command="STITCH"), Stitch(x=0, y=0, command="END")]
    out = _lock_stream(one)
    assert out[-1].command == "END"
