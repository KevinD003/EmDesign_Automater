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
    assert satins[0].stitch_count > 50
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
    assert satins[0].stitch_count > 50


def test_wide_square_stays_tatami():
    d = digitize_image(_test_image(), "cotton", "100x100")
    assert all(o.stitch_type == "TATAMI" for o in d.objects)


def _stroke_image(draw, size=(500, 800), thickness=22) -> bytes:
    """White canvas with a single dark stroke drawn by ``draw(canvas)``."""
    img = np.full((size[0], size[1], 3), 255, np.uint8)
    draw(img, thickness)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _types(design) -> list[str]:
    return [str(getattr(o.stitch_type, "value", o.stitch_type)) for o in design.objects]


def test_curved_column_becomes_satin_not_fill():
    """A curved stroke must be a satin column.

    Regression: classification used cv2.minAreaRect, so a 3mm-wide curved swoosh
    measured a 42mm bounding-box "width", failed the satin test, and was tatami-filled.
    """
    def draw(img, t):
        pts = np.array([(int(60 + 680 * s), int(400 - 260 * np.sin(np.pi * s)))
                        for s in np.linspace(0, 1, 200)], np.int32)
        cv2.polylines(img, [pts], False, (30, 30, 30), t)

    d = digitize_image(_stroke_image(draw), "cotton", "100x100")
    assert "SATIN" in _types(d)


def test_ring_becomes_satin_column():
    """A circular outline is a column whose rails are its outer and inner contours."""
    def draw(img, t):
        cv2.circle(img, (400, 250), 180, (30, 30, 30), t)

    d = digitize_image(_stroke_image(draw), "cotton", "100x100")
    assert "SATIN" in _types(d)


def test_branching_shape_is_not_satin():
    """A cross has more than two ends, so it is NOT one column.

    Regression: rail-pairing on a branching shape threw stitches straight across the
    artwork as a visible diagonal that is not in the source image.
    """
    def draw(img, t):
        cv2.line(img, (150, 250), (650, 250), (30, 30, 30), t)
        cv2.line(img, (400, 60), (400, 440), (30, 30, 30), t)

    d = digitize_image(_stroke_image(draw), "cotton", "100x100")
    assert "SATIN" not in _types(d)


def test_transparent_png_does_not_stitch_the_transparent_area():
    """Alpha must be honoured.

    Regression: IMREAD_COLOR dropped the alpha channel, so a dark logo on a transparent
    background became indistinguishable from the (also-black) transparent area and the
    whole canvas was stitched as one blob.
    """
    rgba = np.zeros((300, 300, 4), np.uint8)
    rgba[..., :3] = (30, 30, 30)          # dark artwork colour everywhere
    cv2.circle(rgba, (150, 150), 80, (30, 30, 30, 255), -1)  # opaque only in the middle
    ok, buf = cv2.imencode(".png", rgba)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "100x100")
    # The stitched extent must be the disc (~53mm at 90% of a 100mm hoop), not the canvas.
    assert d.width_mm < 70 and d.height_mm < 70


def test_subject_touching_corner_does_not_stitch_the_background():
    """Backdrop detection must survive a subject touching a corner.

    Regression: the backdrop was the average of the 4 corner pixels, so one subject in
    a corner poisoned it and the entire white background was stitched as a solid object.
    """
    img = np.full((500, 500, 3), 250, np.uint8)
    cv2.rectangle(img, (0, 0), (250, 250), (180, 40, 40), -1)
    cv2.circle(img, (350, 350), 110, (40, 170, 60), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "100x100")
    # Two artwork shapes, and no third object covering the backdrop.
    assert len(d.objects) == 2
    assert all("250" not in c.hex for c in d.color_stops)


def test_fill_rows_are_staggered():
    """Tatami rows must not all break on the same x (a visible split line)."""
    img = np.full((400, 400, 3), 255, np.uint8)
    cv2.rectangle(img, (60, 60), (340, 340), (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "100x100")
    xs = sorted({round(s.x, 1) for s in d.stitches if s.command == "STITCH"})
    assert len(xs) > 20  # staggered rows produce many distinct penetration positions
