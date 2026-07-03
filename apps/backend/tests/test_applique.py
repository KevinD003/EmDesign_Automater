"""Tests for appliqué (spec §4.3) + satin-zigzag hardening — Phase 3."""

from __future__ import annotations

import cv2
import numpy as np

from app.services import embroidery_io
from app.services.digitizer import digitize_image, rebuild_design


def _square(px: int = 120) -> bytes:
    img = np.full((200, 200, 3), 255, np.uint8)
    off = (200 - px) // 2
    cv2.rectangle(img, (off, off), (off + px, off + px), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _as_applique(design):
    return design.model_copy(
        update={"objects": [o.model_copy(update={"stitch_type": "APPLIQUE"}) for o in design.objects]}
    )


def test_applique_rebuild_produces_outline_and_border():
    d = digitize_image(_square(), "cotton", "100x100", max_colors=2)
    ap = rebuild_design(_as_applique(d))
    assert ap.stitch_count > 100
    assert all(o.stitch_type == "APPLIQUE" for o in ap.objects)
    assert ap.stitches[-1].command == "END"


def test_applique_stream_is_machine_valid():
    d = digitize_image(_square(), "cotton", "100x100", max_colors=2)
    ap = rebuild_design(_as_applique(d))
    prev = None
    for s in ap.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert ((s.x - prev.x) ** 2 + (s.y - prev.y) ** 2) ** 0.5 <= 12.7
        prev = s


def test_applique_exports_to_dst():
    d = digitize_image(_square(), "cotton", "100x100", max_colors=2)
    ap = rebuild_design(_as_applique(d))
    again = embroidery_io.read_embroidery(embroidery_io.write_embroidery(ap, "dst"), "dst")
    assert again.stitch_count > 0


def test_wide_region_forced_satin_stays_machine_valid():
    """Hardening: a wide region mis-set to SATIN must not emit >12.7mm cross stitches."""
    d = digitize_image(_square(px=140), "cotton", "100x100", max_colors=2)
    wide_satin = d.model_copy(
        update={"objects": [o.model_copy(update={"stitch_type": "SATIN"}) for o in d.objects]}
    )
    r = rebuild_design(wide_satin)
    prev = None
    for s in r.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert ((s.x - prev.x) ** 2 + (s.y - prev.y) ** 2) ** 0.5 <= 12.7
        prev = s
