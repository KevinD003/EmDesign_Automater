"""Tests for pull compensation (spec §4.6) — Phase 3 quality feature.

Pull comp was a dead field on DesignObject until now; these lock in that it is
assigned by fabric, actually widens coverage, and is honored (editable) on rebuild.
"""

from __future__ import annotations

import itertools

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


# ── v2 Part 13: full fabric profiles (density/underlay), not just pull ──────


def test_cotton_profile_is_exactly_the_old_globals():
    """The all-cotton bench corpus must be untouched by fabric profiles."""
    p = digitizer._fabric_profile("cotton")
    assert p == {"pull_mm": 0.2, "row_mm": 0.45, "satin_mm": 0.4, "under_mm": 2.0, "inset_mm": 0.6}


def test_unknown_fabric_gets_the_default_profile():
    assert digitizer._fabric_profile("no-such-fabric") == digitizer.FABRIC_DEFAULT
    assert digitizer._fabric_profile("") == digitizer.FABRIC_DEFAULT


def _fill_row_pitch(design) -> float:
    """Median gap between distinct fill-row y's, measured in the central x band
    so edge-walk underlay and outline stitches don't pollute the row set.
    (Raw stitch COUNT is not a valid density proxy across fabrics: fleece's
    larger pull comp widens the region, adding stitches while rows get sparser.)
    """
    xs = [s.x for s in design.stitches if s.command == "STITCH"]
    cx = (min(xs) + max(xs)) / 2.0
    ys = sorted({round(s.y, 2) for s in design.stitches
                 if s.command == "STITCH" and abs(s.x - cx) < 5.0})
    gaps = sorted(b - a for a, b in itertools.pairwise(ys) if b - a > 0.05)
    return gaps[len(gaps) // 2]


def test_fleece_fill_rows_are_sparser_than_cotton():
    """High-loft profile opens the row pitch (0.55 vs 0.45mm) — density is now
    fabric-aware, not just pull. Values provisional per docs/FABRIC_TEST_PROTOCOL.md.

    Needs a hi-res source: at 200px on a 100mm hoop a pixel is 0.45mm, so both
    pitches would quantize to the same 1px row and the comparison measures
    nothing. At 640px a pixel is ~0.14mm and the two pitches resolve to 3 vs 4px.
    """
    img = np.full((640, 640, 3), 255, np.uint8)
    cv2.rectangle(img, (120, 120), (520, 520), (40, 40, 200), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    cotton = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    fleece = digitize_image(buf.tobytes(), "fleece", "100x100", max_colors=2)
    assert _fill_row_pitch(fleece) > _fill_row_pitch(cotton)
    assert fleece.objects[0].density < cotton.objects[0].density


def test_seeded_density_makes_rebuild_fabric_aware():
    """digitize seeds per-object density from the profile, so rebuild_design
    keeps the fabric's spacing with zero rebuild changes."""
    fleece = digitize_image(_square(), "fleece", "100x100", max_colors=2)
    assert fleece.objects[0].density == 1.0 / digitizer._fabric_profile("fleece")["row_mm"]
