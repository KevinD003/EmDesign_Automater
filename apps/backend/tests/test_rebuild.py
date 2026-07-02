"""Tests for rebuild_design — object-level parameter edits (Phase 3)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.digitizer import digitize_image, rebuild_design


def _image() -> bytes:
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (30, 30), (170, 170), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _digitized():
    return digitize_image(_image(), "cotton", "100x100", max_colors=2)


def test_digitizer_stores_contours():
    d = _digitized()
    assert d.objects and all(o.contour for o in d.objects)
    # contour is in mm, inside the hoop
    assert all(0 <= p.x <= 100 and 0 <= p.y <= 100 for o in d.objects for p in o.contour)


def test_rebuild_unchanged_roughly_preserves_design():
    d = _digitized()
    r = rebuild_design(d)
    assert abs(r.width_mm - d.width_mm) < 3.0
    assert abs(r.height_mm - d.height_mm) < 3.0
    assert len(r.color_stops) == len(d.color_stops)
    assert len(r.objects) == len(d.objects)
    assert r.stitches[-1].command == "END"


def test_rebuild_lower_density_means_fewer_stitches():
    d = _digitized()
    half = d.model_copy(
        update={"objects": [o.model_copy(update={"density": o.density / 2}) for o in d.objects]}
    )
    r = rebuild_design(half)
    assert 0 < r.stitch_count < d.stitch_count * 0.75  # half the rows → clearly fewer


def test_rebuild_angle_change_produces_valid_stream():
    d = _digitized()
    rot = d.model_copy(
        update={"objects": [o.model_copy(update={"stitch_angle": 45.0}) for o in d.objects]}
    )
    r = rebuild_design(rot)
    assert r.stitch_count > 50
    prev = None
    for s in r.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert ((s.x - prev.x) ** 2 + (s.y - prev.y) ** 2) ** 0.5 <= 12.7
        prev = s


def test_rebuild_rejects_contourless_design():
    d = _digitized()
    bare = d.model_copy(update={"objects": [o.model_copy(update={"contour": None}) for o in d.objects]})
    with pytest.raises(ValueError):
        rebuild_design(bare)
    with pytest.raises(ValueError):
        rebuild_design(d.model_copy(update={"objects": []}))
