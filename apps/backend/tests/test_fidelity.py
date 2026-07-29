"""v2 Part 14 — fidelity-loop regression tests.

Each test pins one of the root causes found by diffing the drawn preview
against the stitch stream (which was correct the whole time for the first).
"""

from __future__ import annotations

import cv2
import numpy as np

from app.models.design import ColorStop, Design, Stitch
from app.services.digitizer import _open_preserving_detail, digitize_image
from app.services.package import render_preview


def _png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_render_draws_the_segment_after_a_jump():
    """The renderer lost the first span after every JUMP since v1.

    A JUMP entry's coordinates are the needle's landing point — the first
    penetration of the next segment. `run = []` discarded it, so 2-point
    segments vanished outright: fixture 02's fill dashes around the sun.
    """
    d = Design(
        name="jumped", width_mm=50, height_mm=10, stitch_count=4,
        color_stops=[ColorStop(stop_number=1, hex="#204080", thread_brand="Generic",
                               catalog_number="0", thread_name="Navy")],
        stitches=[
            Stitch(x=0.0, y=5.0, command="STITCH"),
            Stitch(x=10.0, y=5.0, command="STITCH"),
            Stitch(x=30.0, y=5.0, command="JUMP"),
            Stitch(x=40.0, y=5.0, command="STITCH"),
        ],
        status="digitized",
    )
    img = cv2.imdecode(np.frombuffer(render_preview(d, px_per_mm=5.0), np.uint8), cv2.IMREAD_COLOR)
    w = img.shape[1]
    # The post-jump segment (30..40mm) must be inked: sample its middle band.
    band = img[:, int(w * 0.80):int(w * 0.92)]
    assert (band.reshape(-1, 3).min(axis=1) < 200).any(), "post-jump segment was not drawn"


def test_small_covered_hole_is_absorbed_by_the_fill():
    """A small white dot inside a dark fill: white stitches AFTER dark, so the
    fill sews solid and the dot lands on top — no knockout, no fill crossings."""
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (260, 260), (60, 40, 20), -1)
    cv2.circle(img, (150, 150), 12, (250, 250, 250), -1)   # ~4.9mm dot at 100mm hoop
    d = digitize_image(_png(img), "cotton", "100x100", max_colors=2)
    dark = max(d.objects, key=lambda o: o.stitch_count)
    assert not dark.holes, f"small covered hole should be absorbed: {len(dark.holes or [])} holes kept"


def test_large_hole_keeps_its_knockout(monkeypatch):
    # Pinned on the deterministic segmentation path: U2-Net happens to reject
    # this particular synthetic square as all-background, which is a property
    # of the neural model, not of the hole rule under test.
    monkeypatch.setenv("STITCHIQ_DISABLE_REMBG", "1")
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (260, 260), (60, 40, 20), -1)
    cv2.circle(img, (150, 150), 60, (250, 250, 250), -1)   # ~24mm hole >> 50mm2
    d = digitize_image(_png(img), "cotton", "100x100", max_colors=2)
    dark = max(d.objects, key=lambda o: o.stitch_count)
    assert dark.holes, "a feature-scale hole must stay knocked out"


def test_small_dark_detail_is_deferred_on_top_of_the_light_fill():
    """v2 Part 16 sequencing: a SMALL dark detail embedded in a later-stitched
    fill no longer stitches first (where the fill would have to keep an
    uncrossable knockout around it) — it is deferred to a pass AFTER the fill,
    the fill sews solid beneath, and the detail lands on top."""
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (260, 260), (200, 200, 190), -1)      # light square
    cv2.circle(img, (150, 150), 12, (40, 30, 20), -1)                  # small DARK dot (~70mm2? no: ~4.4mm r -> 60mm2 edge)
    d = digitize_image(_png(img), "cotton", "100x100", max_colors=2)
    light = max(d.objects, key=lambda o: o.stitch_count)
    dark = min((o for o in d.objects if o.stitch_count > 0), key=lambda o: o.stitch_count)
    assert not light.holes, "the fill should sew solid beneath a deferred detail"
    assert dark.sequence_order > light.sequence_order, "the detail must stitch AFTER the fill"


def test_large_dark_detail_keeps_the_knockout(monkeypatch):
    """The burial guard still protects what deferral does not cover: a detail
    too large to defer stitches first, so the fill must keep its knockout.
    Deterministic segmentation path: U2-Net drops this synthetic's light square
    as background, which is a property of the model, not of the rule under test."""
    monkeypatch.setenv("STITCHIQ_DISABLE_REMBG", "1")
    img = np.full((340, 340, 3), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (320, 320), (200, 200, 190), -1)      # light square
    cv2.circle(img, (170, 170), 60, (40, 30, 20), -1)                  # BIG dark disc (~1000mm2)
    d = digitize_image(_png(img), "cotton", "100x100", max_colors=2)
    light = max(d.objects, key=lambda o: o.stitch_count)
    assert light.holes, "a non-deferrable earlier detail must keep its knockout"


def test_open_preserving_detail_restores_thin_type_but_not_dust():
    mask = np.zeros((100, 200), np.uint8)
    cv2.line(mask, (20, 50), (80, 50), 255, 1)     # thin stroke: 61px, would be erased
    mask[10, 150] = 255                            # 1px dust
    cv2.rectangle(mask, (100, 20), (140, 80), 255, -1)  # coarse area (keeps guard honest)
    out = _open_preserving_detail(mask, mm_per_px=0.18)
    assert out[50, 50] > 0, "a thin-but-real stroke must survive the opening"
    assert out[10, 150] == 0, "dust must still be removed"
