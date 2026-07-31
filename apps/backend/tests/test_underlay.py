"""Tests for underlay generation (spec §4.6) — Phase 3 final item."""

from __future__ import annotations

from itertools import pairwise

import cv2
import numpy as np

from app.services.digitizer import digitize_image, rebuild_design


def _square_image() -> bytes:
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (30, 30), (170, 170), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _bar_image() -> bytes:
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (20, 96), (180, 103), (120, 30, 30), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_digitize_assigns_underlay_types():
    """Underlay is SELECTED, not fixed (v2 Part 24).

    Up to Part 23 this asserted a constant: every fill EDGE_WALK, every satin
    CENTER_WALK, which was true because those were the only two values the
    generator could ever emit. It now asserts the rule instead — a big fill earns
    an edge run PLUS a tatami layer, a thin bar still gets a bare centre run —
    so a regression back to one-underlay-for-everything fails here.
    """
    fill = digitize_image(_square_image(), "cotton", "100x100", max_colors=2)
    # The square is ~49mm across, far past FILL_UNDERLAY_MIN_MM2.
    assert all(o.underlay_type in ("EDGE_WALK", "PARALLEL") for o in fill.objects)
    assert any(o.underlay_type == "PARALLEL" for o in fill.objects), (
        "a fill this large must get the tatami underlay layer, not the edge run alone"
    )
    satin = digitize_image(_bar_image(), "cotton", "100x100", max_colors=2)
    satins = [o for o in satin.objects if o.stitch_type == "SATIN"]
    # The bar measures 3.15mm across (contour y 43.20 -> 46.35), which is the
    # 2-4mm band, so it earns an edge run rather than the bare centre run every
    # satin object got before Part 24.
    assert satins and all(o.underlay_type == "EDGE_WALK" for o in satins)


def test_satin_underlay_follows_column_width():
    """The width bands actually select different underlays (v2 Part 24).

    Three bars of increasing width through the real pipeline: under 2mm a centre
    run, 2-4mm an edge run, over 4mm the double zigzag. Without this the wide
    branch is unreachable on the ten-fixture corpus — its widest satin column
    measures 3.78mm against a 4.5mm satin cap — and would ship untested.
    """
    # Bar half-heights in source px. At this fixture's scale a 200px image maps
    # to a 64mm design, i.e. ~0.5mm per source px, so these are columns of
    # roughly 1mm, 3mm and 4.5mm — one in each band. Above ~4.5mm the region
    # exceeds SATIN_MAX_W_MM and is classified TATAMI instead, which is why the
    # widest case sits just inside the cap rather than well past it.
    seen = {}
    for half_h, expect in ((1, "CENTER_WALK"), (3, "EDGE_WALK"), (4, "DOUBLE_ZIGZAG")):
        img = np.full((200, 200, 3), 255, np.uint8)
        cv2.rectangle(img, (20, 100 - half_h), (180, 100 + half_h), (120, 30, 30), thickness=-1)
        ok, buf = cv2.imencode(".png", img)
        assert ok
        d = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
        satins = [o for o in d.objects if o.stitch_type == "SATIN"]
        assert satins, f"half-height {half_h} produced no satin object"
        seen[expect] = {o.underlay_type for o in satins}
        assert seen[expect] == {expect}, f"half-height {half_h}: got {seen[expect]}, want {expect}"
    assert len(seen) == 3


def test_underlay_none_reduces_stitches_on_rebuild():
    d = digitize_image(_square_image(), "cotton", "100x100", max_colors=2)
    bare = d.model_copy(
        update={"objects": [o.model_copy(update={"underlay_type": "NONE"}) for o in d.objects]}
    )
    r_with = rebuild_design(d)
    r_without = rebuild_design(bare)
    assert 0 < r_without.stitch_count < r_with.stitch_count  # underlay adds stitches


def test_underlay_stream_stays_machine_valid():
    d = digitize_image(_square_image(), "cotton", "100x100", max_colors=2)
    prev = None
    for s in d.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert ((s.x - prev.x) ** 2 + (s.y - prev.y) ** 2) ** 0.5 <= 12.7
        prev = s


def test_zigzag_underlay_throws_are_stitches_not_jumps():
    """The cross-column throw IS the stitch (v2 Part 24).

    The first version of `_zigzag_underlay` derived its jump flag from the
    distance between consecutive points, which is what every OTHER generator in
    this module correctly does — but a zigzag's consecutive points are the two
    sides of the column, so every single throw came back flagged as a jump and
    the underlay was a sequence of jumps stitching nothing. Only a break in the
    medial axis may start a new run.
    """
    from app.services.digitizer import (
        MIN_PENETRATION_MM,
        _skeleton_satin,
        _zigzag_underlay,
    )

    img = np.zeros((200, 600), np.uint8)
    cv2.rectangle(img, (50, 70), (550, 130), 255, -1)  # a 6mm column at 0.1mm/px
    mm_per_px = 0.1
    _cand, median_w, _wide, axis = _skeleton_satin(img, mm_per_px, 4, 127, extra_half_px=0.0)
    assert median_w > 4.0, f"fixture must exceed the zigzag band, measured {median_w:.2f}mm"

    pts = _zigzag_underlay(img, axis, 2.0 / mm_per_px, 0.6 / mm_per_px, 30.0,
                           MIN_PENETRATION_MM / mm_per_px, 12.7 / mm_per_px)
    assert len(pts) > 10
    jumps = sum(1 for p in pts if p[2])
    assert jumps <= 2, f"{jumps} of {len(pts)} points are jumps — the throws are not stitching"

    # It alternates sides, i.e. it is a zigzag rather than a run down the middle.
    sides = [1 if p[1] < 100 else -1 for p in pts]
    flips = sum(1 for a, b in pairwise(sides) if a != b)
    assert flips >= len(sides) - 3

    # It stays inside the column and inside the machine limit.
    assert min(p[1] for p in pts) > 70 and max(p[1] for p in pts) < 130
    for a, b in pairwise(pts):
        if not b[2]:
            assert ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 * mm_per_px <= 12.7
