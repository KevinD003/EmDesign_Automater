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
    # The stitch-count proxy died in v2 Part 15: the ring earns TWO satin
    # borders (outer + hole rim) where the disc earns one, offsetting the
    # carved fill. Assert the property itself instead: no penetration lands
    # deep inside the hole (the rim border may legally reach 0.6mm in).
    pen = [(st.x, st.y) for st in ring.stitches if st.command == "STITCH"]
    cx = (min(x for x, _ in pen) + max(x for x, _ in pen)) / 2.0
    cy = (min(y for _, y in pen) + max(y for _, y in pen)) / 2.0
    hole = next(o.holes[0] for o in ring.objects if o.holes)
    # min radius, not max: the traced hole is not perfectly round, and the rim
    # border legally reaches ~0.6mm inside the contour it runs along.
    hole_r = min(((pp.x - cx) ** 2 + (pp.y - cy) ** 2) ** 0.5 for pp in hole)
    deep = sum(1 for x, y in pen if ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 < hole_r - 1.0)
    assert deep == 0, f"{deep} penetrations deep inside the hole"


def test_rebuild_preserves_holes():
    """The hole's interior must stay empty of penetrations after a rebuild.

    Asserted directly rather than via the old stitch-count proxy
    (`ring < disc * 0.9`): Part 25's travel routing sends row connections
    AROUND the hole along its edge instead of trimming at every crossing, which
    adds legitimate stitches to the ring and broke the proxy while the property
    it stood for — the hole is still carved — held. The disc control proves the
    probe region would be full if the hole were lost.
    """
    ring = rebuild_design(digitize_image(_ring_image(), "cotton", "100x100", max_colors=2))
    disc = rebuild_design(digitize_image(_disc_image(), "cotton", "100x100", max_colors=2))

    def centre_hits(design, radius_mm=10.0):
        xs = [s.x for s in design.stitches if s.command == "STITCH"]
        ys = [s.y for s in design.stitches if s.command == "STITCH"]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        return sum(
            1 for s in design.stitches
            if s.command == "STITCH" and (s.x - cx) ** 2 + (s.y - cy) ** 2 < radius_mm ** 2
        )

    assert centre_hits(disc) > 50, "control: a solid disc must fill its centre"
    assert centre_hits(ring) == 0, "the hole was stitched over after rebuild"


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
    _ok, buf = cv2.imencode(".png", img)
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


# ── Letter tracking (letter_spacing_mm) — Tier 2 launch gap ────────────────────


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_default_path_unchanged_by_tracking_feature():
    """spacing=0 must run the pre-tracking single-draw path: the composed bitmap is
    byte-identical to the v1 composition, and the digitized design has the same
    stitch_count as the v1 pipeline produces from that bitmap."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    from app.services import lettering as lt

    text, height_mm = "HI", 20.0
    font = ImageFont.truetype(lt.find_font(None), size=160)

    # v1 composition, verbatim from the pre-tracking code
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = max(right - left, 1), max(bottom - top, 1)
    margin = 12
    old = Image.new("RGB", (tw + 2 * margin, th + 2 * margin), "white")
    ImageDraw.Draw(old).text((margin - left, margin - top), text, font=font, fill="black")

    new_img, new_th = lt._compose_text_image(text, font, 0.0, height_mm)
    assert (new_img.size, new_th) == (old.size, th)
    assert new_img.tobytes() == old.tobytes()

    # v1 pipeline end-to-end: same hoop math, same digitizer args → same count
    mm_per_px = height_mm / th
    iw, ih = old.size
    hoop = f"{max(iw * mm_per_px / 0.9, 1):.1f}x{max(ih * mm_per_px / 0.9, 1):.1f}"
    buf = io.BytesIO()
    old.save(buf, format="PNG")
    baseline = digitize_image(
        buf.getvalue(), "cotton", hoop, max_colors=2, min_region_mm2=0.5, text_mode=True
    )
    assert generate_lettering(text, height_mm).stitch_count == baseline.stitch_count


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_positive_tracking_widens_design():
    base = generate_lettering("HI", 20)
    wide = generate_lettering("HI", 20, letter_spacing_mm=3.0)
    assert wide.width_mm > base.width_mm + 1.5  # one 3mm gap in "HI"
    assert abs(wide.height_mm - base.height_mm) < 2.0  # tracking must not change height


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_zero_tracking_matches_default_output():
    base = generate_lettering("HI", 20)
    explicit = generate_lettering("HI", 20, letter_spacing_mm=0.0)
    assert explicit.stitch_count == base.stitch_count
    assert explicit.width_mm == base.width_mm


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_negative_tracking_narrows_design():
    base = generate_lettering("HI", 20)
    narrow = generate_lettering("HI", 20, letter_spacing_mm=-2.0)
    assert narrow.width_mm < base.width_mm - 1.0


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_lettering_endpoint_passes_tracking_and_font_path_through():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.lettering import find_font

    client = TestClient(app)
    base = client.post("/api/lettering", json={"text": "HI", "heightMm": 20})
    wide = client.post(
        "/api/lettering",
        json={"text": "HI", "heightMm": 20, "letterSpacingMm": 3.0, "fontPath": find_font()},
    )
    assert base.status_code == 200 and wide.status_code == 200
    assert wide.json()["widthMm"] > base.json()["widthMm"] + 1.5
