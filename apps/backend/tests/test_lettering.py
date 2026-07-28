"""Tests for hole handling (donut fix) and the lettering engine (Phase 4)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.digitizer import digitize_image, rebuild_design
from app.services.lettering import find_font, generate_lettering

try:
    find_font()
    HAVE_FONT = True
except ValueError:
    HAVE_FONT = False


def _ring_image() -> bytes:
    """A donut: filled circle with a hole in the middle."""
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.circle(img, (100, 100), 70, (40, 40, 200), thickness=-1)
    cv2.circle(img, (100, 100), 35, (255, 255, 255), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _disc_image() -> bytes:
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.circle(img, (100, 100), 70, (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_donut_hole_is_not_filled():
    ring = digitize_image(_ring_image(), "cotton", "100x100", max_colors=2)
    disc = digitize_image(_disc_image(), "cotton", "100x100", max_colors=2)
    assert any(o.holes for o in ring.objects), "ring object should carry its hole"
    assert not any(o.holes for o in disc.objects)
    # the carved-out hole means clearly fewer stitches than the full disc
    assert ring.stitch_count < disc.stitch_count * 0.9


def test_rebuild_preserves_holes():
    ring = digitize_image(_ring_image(), "cotton", "100x100", max_colors=2)
    rebuilt = rebuild_design(ring)
    disc = rebuild_design(digitize_image(_disc_image(), "cotton", "100x100", max_colors=2))
    assert rebuilt.stitch_count < disc.stitch_count * 0.9  # hole still carved after rebuild


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_lettering_generates_design_at_requested_height():
    d = generate_lettering("HI", height_mm=20)
    assert d.stitch_count > 100
    assert d.objects and all(o.contour for o in d.objects)
    assert 16 <= d.height_mm <= 24  # ≈ requested 20mm
    assert d.name == 'Text "HI"'


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_lettering_letter_counters_have_holes():
    d = generate_lettering("O", height_mm=20)
    assert any(o.holes for o in d.objects), "the counter of 'O' should be a hole"


def test_lettering_rejects_empty_text():
    with pytest.raises(ValueError):
        generate_lettering("   ")


# ── Regression tests for review findings (all confirmed by reproduction) ──────

def test_no_phantom_color_stops():
    """A cluster that yields no objects must NOT create a color stop or a dangling
    COLOR_CHANGE (review #3 — was adding a spurious thread change to every design)."""
    # image with two real blocks + a sub-min-area speck (its own k-means cluster)
    img = np.full((200, 300, 3), 255, np.uint8)
    cv2.rectangle(img, (10, 10), (90, 190), (200, 40, 40), -1)
    cv2.rectangle(img, (110, 10), (190, 190), (40, 180, 40), -1)
    cv2.circle(img, (250, 100), 2, (10, 10, 10), -1)
    ok, buf = cv2.imencode(".png", img)
    d = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=4)
    assert all(c.stitch_count > 0 for c in d.color_stops), "no empty color stops"
    assert [c.stop_number for c in d.color_stops] == list(range(1, len(d.color_stops) + 1))
    # every object references a real stop; no COLOR_CHANGE directly before END
    stop_nums = {c.stop_number for c in d.color_stops}
    assert all(o.color_stop in stop_nums for o in d.objects)
    for i in range(len(d.stitches) - 1):
        if d.stitches[i].command == "COLOR_CHANGE":
            assert d.stitches[i + 1].command not in ("END", "COLOR_CHANGE")


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_single_color_text_is_one_stop():
    d = generate_lettering("GO", 25)
    assert len(d.color_stops) == 1  # black text = one thread (review #3)


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
@pytest.mark.parametrize("disable_rembg", [False, True], ids=["rembg-or-default", "no-rembg"])
def test_single_color_text_is_one_stop_on_every_segmentation_tier(monkeypatch, disable_rembg):
    """Single-colour text must yield ONE thread on every segmentation backend.

    This regression was environment-dependent and therefore invisible locally:
    with rembg installed the suite passed, and without it (the documented
    `requirements.txt` + `requirements-dev.txt` install, and what CI runs) the
    anti-aliased halo around the glyphs became a second near-white ink layer.
    Pinning both tiers means a machine that happens to have the optional
    dependency can no longer hide a failure from one that does not.
    """
    if disable_rembg:
        monkeypatch.setenv("STITCHIQ_DISABLE_REMBG", "1")
    else:
        monkeypatch.delenv("STITCHIQ_DISABLE_REMBG", raising=False)
    d = generate_lettering("GO", 25)
    assert len(d.color_stops) == 1, [c.hex for c in d.color_stops]


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_narrow_letter_reaches_full_height():
    """Tall-thin letters must not be cropped ~half by satin rotation (review #4/#5)."""
    d = generate_lettering("l", 12)
    assert d.height_mm >= 12 * 0.8


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_multi_char_text_keeps_detail():
    """Wide text must not collapse to almost nothing via the resolution cap (review #1)."""
    d = generate_lettering("ABCDEFGHIJ", 18)
    assert len(d.objects) >= 8
    assert d.stitch_count > 500


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_unsupported_glyphs_rejected():
    with pytest.raises(ValueError):
        generate_lettering("\U0001F600\U0001F680")  # emoji → no glyphs → empty (review #6)


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_mixed_supported_and_unsupported_rejected():
    """Tofu boxes must be rejected even when mixed with real glyphs — otherwise
    the design silently gains garbage rectangles of stitches. U+0378 is a
    permanently-unassigned codepoint, so no font can have a real glyph for it."""
    with pytest.raises(ValueError):
        generate_lettering("Hi͸")


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_small_lettering_keeps_the_dot_on_i():
    """The dot on 'i' is < 4mm² at small sizes; the lettering path must keep it
    (the image digitizer's speck filter would drop it)."""
    d = generate_lettering("i", height_mm=8)
    assert len(d.objects) >= 2, "expected stem AND dot as separate objects"
