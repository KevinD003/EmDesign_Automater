"""Tests for the classical-CV auto-digitizer (Phase 3)."""

from __future__ import annotations

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
    assert d.objects[0].stitch_count > 0
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
