"""Tests for underlay generation (spec §4.6) — Phase 3 final item."""

from __future__ import annotations

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
    fill = digitize_image(_square_image(), "cotton", "100x100", max_colors=2)
    assert all(o.underlay_type == "EDGE_WALK" for o in fill.objects)
    satin = digitize_image(_bar_image(), "cotton", "100x100", max_colors=2)
    satins = [o for o in satin.objects if o.stitch_type == "SATIN"]
    assert satins and all(o.underlay_type == "CENTER_WALK" for o in satins)


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
