"""v2 Part 41 — the garment is not a thread.

Reported plainly: "We never do the thread for background. Its a black cloth.
Do only for the design."

Two independent paths were laying thread over bare fabric on a dark garment:
a colour cluster the same colour as the cloth (kept as "knocked-out detail"),
and the dark-linework pass, whose black-hat finds the GAPS BETWEEN elements
when nothing in the artwork is darker than the cloth. Measured on the black
neckline panel: 2,928 stitches, 5.1% of all sewing.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services.digitizer import DARK_CLOTH_LUM, SUBSTRATE_DELTA, digitize_image


def _png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _lum(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    return 0.299 * int(h[0:2], 16) + 0.587 * int(h[2:4], 16) + 0.114 * int(h[4:6], 16)


def _dist_to(hex_colour: str, bgr) -> float:
    h = hex_colour.lstrip("#")
    v = np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)
    return float(np.linalg.norm(v - np.asarray(bgr, np.float32)))


def _design_on_black():
    """Two separated bright elements on black cloth, with a gap between them.

    The gap is the garment, not an outline — nothing may be stitched there.
    """
    img = np.zeros((420, 420, 3), np.uint8)
    cv2.circle(img, (140, 210), 70, (40, 200, 220), -1)
    cv2.circle(img, (290, 210), 70, (40, 60, 220), -1)
    return img


def test_no_thread_is_laid_in_the_garment_colour():
    design = digitize_image(_png(_design_on_black()), "cotton", "120x120", 6)
    assert design.color_stops, "the design itself must still be stitched"
    for stop in design.color_stops:
        assert _dist_to(stop.hex, (0, 0, 0)) >= SUBSTRATE_DELTA, (
            f"stop {stop.hex} is the cloth's own colour — it must not be sewn"
        )


def test_dark_linework_is_skipped_on_dark_cloth():
    """The pass exists to stitch lines DARKER than the fabric. On black cloth
    nothing is, so it can only trace the gaps between elements."""
    design = digitize_image(_png(_design_on_black()), "cotton", "120x120", 6)
    kinds = {str(getattr(o.stitch_type, "value", o.stitch_type)) for o in design.objects}
    assert "RUNNING_SINGLE" not in kinds, (
        "dark linework on a dark garment traces bare fabric"
    )


def test_light_cloth_still_gets_its_linework():
    """The guard is about DARK cloth only: black line art on white must keep
    the outline pass that Part 30 added."""
    img = np.full((420, 420, 3), 255, np.uint8)
    cv2.circle(img, (210, 210), 120, (60, 180, 230), -1)
    for k in range(0, 360, 30):
        import math

        a = math.radians(k)
        cv2.line(
            img,
            (210, 210),
            (int(210 + 118 * math.cos(a)), int(210 + 118 * math.sin(a))),
            (20, 20, 20),
            3,
        )
    design = digitize_image(_png(img), "cotton", "120x120", 6)
    assert design.objects, "a design on light cloth must still stitch"
    # The substrate here is white, so the dark-cloth guard must not engage.
    assert _lum("#ffffff") >= DARK_CLOTH_LUM


def test_the_design_itself_is_untouched_on_dark_cloth():
    """Removing background thread must not remove artwork: both elements survive."""
    design = digitize_image(_png(_design_on_black()), "cotton", "120x120", 6)
    hexes = {s.hex for s in design.color_stops}
    assert len(hexes) >= 2, f"both coloured elements must be stitched, got {hexes}"
    sewn = sum(1 for s in design.stitches if str(getattr(s.command, "value", s.command)) == "STITCH")
    assert sewn > 500, "the elements themselves must still be filled"
