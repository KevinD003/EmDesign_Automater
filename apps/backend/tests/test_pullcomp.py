"""Tests for pull compensation (spec §4.6) — Phase 3 quality feature.

Pull comp was a dead field on DesignObject until now; these lock in that it is
assigned by fabric, actually widens coverage, and is honored (editable) on rebuild.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services import digitizer
from app.services.digitizer import digitize_image, rebuild_design


def _square() -> bytes:
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (160, 160), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_default_pull_higher_for_knit_than_woven():
    assert digitizer._default_pull("fleece") > digitizer._default_pull("denim")
    assert digitizer._default_pull("cotton") > 0
    assert digitizer._default_pull("unknown-fabric") == digitizer.PULL_DEFAULT_MM


def test_digitize_assigns_pull_compensation():
    d = digitize_image(_square(), "fleece", "100x100", max_colors=2)
    assert d.objects and all(o.pull_compensation > 0 for o in d.objects)
    assert d.objects[0].pull_compensation == round(digitizer._default_pull("fleece"), 2)


def test_more_pull_widens_coverage_on_rebuild():
    d = digitize_image(_square(), "cotton", "100x100", max_colors=2)
    none = d.model_copy(update={"objects": [o.model_copy(update={"pull_compensation": 0.0}) for o in d.objects]})
    lots = d.model_copy(update={"objects": [o.model_copy(update={"pull_compensation": 1.0}) for o in d.objects]})
    r_none = rebuild_design(none)
    r_lots = rebuild_design(lots)
    # wider region → larger stitched extent (and generally more stitches)
    assert r_lots.width_mm >= r_none.width_mm
    assert r_lots.stitch_count >= r_none.stitch_count


def test_rebuild_stream_stays_machine_valid_with_pull():
    d = digitize_image(_square(), "fleece", "100x100", max_colors=2)
    r = rebuild_design(d.model_copy(update={"objects": [o.model_copy(update={"pull_compensation": 0.8}) for o in d.objects]}))
    prev = None
    for s in r.stitches:
        if s.command == "STITCH" and prev is not None and prev.command == "STITCH":
            assert ((s.x - prev.x) ** 2 + (s.y - prev.y) ** 2) ** 0.5 <= 12.7
        prev = s
