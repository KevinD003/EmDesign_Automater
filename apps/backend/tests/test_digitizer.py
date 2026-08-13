"""Tests for the classical-CV auto-digitizer (Phase 3)."""

from __future__ import annotations

from itertools import pairwise

import cv2
import numpy as np
import pytest

from app.services import embroidery_io
from app.services.digitizer import digitize_image


def _test_image() -> bytes:
    """White background with a red square and a dark-blue circle (no copyright)."""
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (90, 90), (40, 40, 200), thickness=-1)   # red-ish (BGR)
    cv2.circle(img, (140, 140), 40, (150, 60, 20), thickness=-1)          # dark blue (BGR)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_digitize_produces_design_with_objects():
    d = digitize_image(_test_image(), "cotton", "100x100")
    assert d.stitch_count > 100
    assert len(d.color_stops) == 2           # background dropped, 2 shapes kept
    assert len(d.objects) >= 2               # one object per region
    assert d.objects[0].stitch_type == "TATAMI"
    assert d.objects[0].penetration_count > 0
    assert 0 < d.width_mm <= 100 and 0 < d.height_mm <= 100
    assert d.stitches[-1].command == "END"
    # darkest color stitches first (spec §4.2)
    assert d.color_stops[0].stop_number == 1


def test_digitize_stitch_stream_is_machine_valid():
    d = digitize_image(_test_image(), "cotton", "80x80")
    # exactly one COLOR_CHANGE between the two stops
    assert sum(1 for s in d.stitches if s.command == "COLOR_CHANGE") == 1
    # no stitch exceeds the machine limit
    prev = None
    for s in d.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert ((s.x - prev.x) ** 2 + (s.y - prev.y) ** 2) ** 0.5 <= 12.7
        prev = s


def test_digitized_design_exports_to_dst():
    d = digitize_image(_test_image(), "cotton", "100x100")
    data = embroidery_io.write_embroidery(d, "dst")
    again = embroidery_io.read_embroidery(data, "dst")
    assert again.stitch_count > 0
    assert abs(again.width_mm - d.width_mm) < 2.0


def test_digitize_rejects_garbage():
    with pytest.raises(ValueError):
        digitize_image(b"not an image", "cotton", "100x100")


def test_hoop_parsing_defaults_safely():
    d = digitize_image(_test_image(), "cotton", "not-a-hoop")
    assert d.width_mm <= 100  # fell back to 100x100


def _bar_image(diagonal: bool = False) -> bytes:
    """White background with one thin dark bar (~3.6mm wide at a 100mm hoop)."""
    img = np.full((200, 200, 3), 255, np.uint8)
    if diagonal:
        cv2.line(img, (30, 170), (170, 30), (120, 30, 30), thickness=8)
    else:
        cv2.rectangle(img, (20, 96), (180, 103), (120, 30, 30), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_narrow_bar_becomes_satin():
    d = digitize_image(_bar_image(), "cotton", "100x100", max_colors=2)
    satins = [o for o in d.objects if o.stitch_type == "SATIN"]
    assert satins, f"expected a SATIN object, got {[o.stitch_type for o in d.objects]}"
    # the zigzag must actually stitch (not degenerate to jumps)
    assert satins[0].penetration_count > 50
    # zig width stays within the machine stitch limit
    prev = None
    for s in d.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert ((s.x - prev.x) ** 2 + (s.y - prev.y) ** 2) ** 0.5 <= 12.7
        prev = s


def test_rotated_bar_becomes_satin_with_angle():
    d = digitize_image(_bar_image(diagonal=True), "cotton", "100x100", max_colors=2)
    satins = [o for o in d.objects if o.stitch_type == "SATIN"]
    assert satins
    assert satins[0].penetration_count > 50


def test_wide_square_stays_tatami():
    d = digitize_image(_test_image(), "cotton", "100x100")
    assert all(o.stitch_type == "TATAMI" for o in d.objects)


# ── v2 Part 4: edge-bounded satin ────────────────────────────────────────────


def _ring_image(thickness: int = 8) -> bytes:
    """An annulus — a stroke with NO terminals, the closed-loop case."""
    img = np.full((240, 240, 3), 255, np.uint8)
    cv2.circle(img, (120, 120), 80, (40, 40, 40), thickness=thickness)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_ring_satin_closes_without_a_seam():
    """A ring has no cap, so its columns must wrap all the way round."""
    d = digitize_image(_ring_image(), "cotton", "100x100", max_colors=2)
    satins = [o for o in d.objects if o.stitch_type == "SATIN"]
    assert satins, "an 8px annulus is a stroke and must be satin"
    # No stitch spans the ring's hole: the closed-loop path must not join across
    # the centre the way a bounding-rect midline would.
    for a, b in zip(d.stitches, d.stitches[1:]):
        if a.command == "STITCH" and b.command == "STITCH":
            assert ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5 <= 12.7


def test_closed_loop_branch_is_detected_and_wraps():
    """The ring special case fires, and covers one full turn."""
    from app.services.digitizer import (
        CLOSED_LOOP_TOL_PX,
        _assign_boundary,
        _axis_branches,
        _axis_frame,
        _boundary_points,
        _column_ends,
    )

    mask = np.zeros((240, 240), np.uint8)
    cv2.circle(mask, (120, 120), 80, 255, thickness=8)
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    _skel, branches = _axis_branches((mask > 0).astype(np.uint8), dist, 0.25)
    assert branches
    frames = [_axis_frame(b, dist) for b in branches]
    closed = [f for f in frames if float(np.hypot(*(f[0][0] - f[0][-1]))) <= CLOSED_LOOP_TOL_PX]
    assert closed, "a circle's medial axis must come back to where it started"
    owned = _assign_boundary(_boundary_points(mask), frames)
    pairs = _column_ends(frames[0], owned[0], 3.0, 20.0, 0.0)
    assert len(pairs) > 20
    # Both ends of every column sit on the annulus, not across its hole.
    for a, b in pairs:
        assert ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 < 40.0


def test_open_stroke_columns_reach_the_terminal_cap():
    """Column ends must cover a stroke's END, not stop a half-width short."""
    from app.services.digitizer import (
        _assign_boundary,
        _axis_branches,
        _axis_frame,
        _boundary_points,
        _column_ends,
    )

    mask = np.zeros((160, 160), np.uint8)
    cv2.line(mask, (30, 80), (130, 80), 255, thickness=9)
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    _skel, branches = _axis_branches((mask > 0).astype(np.uint8), dist, 0.25)
    frames = [_axis_frame(b, dist) for b in branches]
    owned = _assign_boundary(_boundary_points(mask), frames)
    pairs = _column_ends(frames[0], owned[0], 2.0, 20.0, 0.0)
    assert pairs
    xs = [x for pair in pairs for (x, _y) in pair]
    # The bar spans x=30..130; columns must reach within a pixel of both ends.
    assert min(xs) <= 31.0, f"left cap not reached: {min(xs)}"
    assert max(xs) >= 129.0, f"right cap not reached: {max(xs)}"


def test_raycast_fallback_still_produces_columns():
    """The per-branch fallback must keep stitching when a boundary cannot be paired."""
    from app.services.digitizer import _raycast_columns

    mask = np.zeros((60, 60), np.uint8)
    cv2.line(mask, (10, 30), (50, 30), 255, thickness=7)
    samples = [(x, 30) for x in range(12, 49, 2)]
    pairs = _raycast_columns((mask > 0).astype(np.uint8), samples, 10.0, 0.0)
    assert len(pairs) == len(samples)
    for a, b in pairs:
        assert 1.0 < ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 <= 21.0


def test_satin_path_has_no_along_edge_micro_stitches():
    """Every satin path step is a CROSSING; none is a sub-pitch hop along one edge.

    Emitting both ends of each column with an alternating lead put two
    penetrations one pitch apart back-to-back in the path — under the 0.5mm
    minimum, so they were coalesced away and each boundary lost half its
    penetrations.
    """
    d = digitize_image(_bar_image(), "cotton", "100x100", max_colors=2)
    satins = [o for o in d.objects if o.stitch_type == "SATIN"]
    assert satins
    runs = [s for s in d.stitches if s.command == "STITCH"]
    lengths = [((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5 for a, b in pairwise(runs)]
    assert lengths
    # A satin crossing is at least a millimetre; the defect showed up as a large
    # population of ~0.4mm steps.
    tiny = sum(1 for x in lengths if x < 0.5)
    assert tiny / len(lengths) < 0.05, f"{tiny}/{len(lengths)} sub-0.5mm steps"


# ── v2 Part 7: junction-aware boundary partition ─────────────────────────────


def _junction_image(thin_px: int = 4, stem_px: int = 24) -> bytes:
    """A hairline leaving a thick stem at 30° — the asymmetric junction of Part 4 §11.3.

    640px on a 100mm hoop keeps the 24px stem at 3.75mm, inside the satin cap, so
    the junction actually reaches the satin path this test is about.
    """
    import math

    img = np.full((640, 640, 3), 255, np.uint8)
    cx = 260
    cv2.line(img, (cx, 90), (cx, 550), (30, 30, 40), thickness=stem_px)
    joint = (cx, 340)
    rad = math.radians(30)
    tip = (int(joint[0] + 260 * math.sin(rad)), int(joint[1] - 260 * math.cos(rad)))
    cv2.line(img, joint, tip, (30, 30, 40), thickness=thin_px)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_thick_stem_boundary_is_not_handed_to_a_hairline_branch():
    """The adversarial junction: raw nearest-branch gives the stem's boundary away.

    A stem boundary pixel sits one stem half-width from the stem axis. With a
    6:1 thickness ratio that is also roughly its distance to the HAIRLINE axis,
    so a Voronoi split hands a tall run of stem boundary to the hairline, whose
    short axis then collapses it all onto one station. Subtracting the local
    medial radius makes the test scale-free: ~0 for the branch a point actually
    bounds, positive for any other.
    """
    from app.services.digitizer import (
        _assign_boundary,
        _axis_branches,
        _axis_frame,
        _boundary_points,
    )

    img = cv2.imdecode(np.frombuffer(_junction_image(), np.uint8), cv2.IMREAD_COLOR)
    mask = (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) < 128).astype(np.uint8) * 255
    binary = (mask > 0).astype(np.uint8)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    _skel, branches = _axis_branches(binary, dist, 0.3)
    frames = [_axis_frame(b, dist) for b in branches]
    assigned = _assign_boundary(_boundary_points(mask), frames)

    # The hairline is the branch with the smallest median radius.
    radii = [float(np.median(f[3])) for f in frames]
    thin = int(np.argmin(radii))
    assert radii[thin] < 4.0, f"expected a hairline branch, radii={radii}"

    owned = assigned[thin]
    assert len(owned["t"]), "the hairline must own its own boundary"
    # Points further than a few hairline-widths from the hairline axis are stem
    # boundary. Raw nearest-branch hands over 12 of them on this shape; the
    # radius-normalised rule leaves at most a couple around the fillet itself.
    reach = radii[thin] * 3.0
    axis = frames[thin][0]
    strays = sum(
        1 for pt in owned["pt"]
        if float(np.min(np.hypot(axis[:, 0] - pt[0], axis[:, 1] - pt[1]))) > reach
    )
    assert strays <= 3, f"hairline owns {strays} stem-boundary points (reach {reach:.1f}px)"


def test_junction_shape_still_classifies_and_stitches():
    """End to end: the junction shape stays satin and honours the penetration floor."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from measure_stitch_quality import penetration_metrics

    from app.services.digitizer import MIN_PENETRATION_MM

    d = digitize_image(_junction_image(), "cotton", "100x100", max_colors=2)
    assert [o for o in d.objects if o.stitch_type == "SATIN"], (
        f"expected satin, got {[o.stitch_type for o in d.objects]}"
    )
    pen = penetration_metrics(d, 0.4, MIN_PENETRATION_MM)
    assert pen["below_floor"] == 0, f"{pen['below_floor']} penetrations under the floor"
