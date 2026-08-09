"""A fill must be a property of the object, not of where it sits on the canvas.

CTO verdict 2026-08-09, STEP 3. `_scanline_angled` rotated the mask about the
CANVAS centre — `_warp_fit(region, (w/2, h/2), angle)` — and `_warp_fit` then
offsets the fitted output by `(nw - w)/2`, which depends on the canvas
dimensions as well. Both terms leak the canvas into the row grid.

Measured on a 120x80 rectangle at 30 degrees, before the fix:

    canvas 300x300 -> 300x420, region unmoved    every stitch up to  0.83px off
    region translated +100px, canvas unchanged   every stitch up to 35.16px off

35px is a different row phase entirely. Three consequences, in ascending order
of seriousness:

  * digitize rasters at 13.3px/mm on the source image and rebuild at 10px/mm on
    the bounding box of every object, so the two paths could never agree on the
    grid even in principle — part of the residual P6 gap.
  * adding or deleting an unrelated object changes the design's bounding box,
    and therefore re-phases the fill of every object that was left alone.
  * B2 is move/scale/rotate. Moving one object would have silently restitched
    it, which is the opposite of what a transform means.

The fix crops to the region's own foreground window and rotates about the
centre of THAT, so the fitted size, the rotation centre and the row phase all
depend on nothing but the region's own pixels. `_skeleton_satin_hires` already
worked this way.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.digitizer.fills import _scanline_angled

ANGLES = [15.0, 30.0, 47.5, 90.0, 120.0, 175.0]


def _bar(canvas_h: int, canvas_w: int, ox: int, oy: int,
         bw: int = 120, bh: int = 80) -> np.ndarray:
    m = np.zeros((canvas_h, canvas_w), np.uint8)
    cv2.rectangle(m, (ox, oy), (ox + bw, oy + bh), 255, -1)
    return m


def _worst(a, b, dx: float = 0.0, dy: float = 0.0) -> float:
    """Largest coordinate difference after undoing an expected translation."""
    assert len(a) == len(b), (
        f"point counts differ ({len(a)} vs {len(b)}) — the row grid moved, "
        f"which is the defect itself"
    )
    return max(max(abs(p[0] + dx - q[0]), abs(p[1] + dy - q[1]))
               for p, q in zip(a, b))


@pytest.mark.parametrize("angle", ANGLES)
def test_growing_the_canvas_does_not_move_a_single_stitch(angle):
    """The region is untouched; only the empty space around it changes. Nothing
    about the fill may respond to that. Measured 0.83px before the fix."""
    a = _scanline_angled(_bar(300, 300, 60, 60), angle, 5, 40, 3.0)
    b = _scanline_angled(_bar(300, 420, 60, 60), angle, 5, 40, 3.0)
    assert a, "probe produced no stitches"
    assert _worst(a, b) < 1e-6, (
        f"{angle} deg: growing the canvas moved stitches — the fill is still "
        f"reading the canvas, not the region"
    )


@pytest.mark.parametrize("angle", ANGLES)
def test_translating_the_object_translates_its_fill_and_nothing_else(angle):
    """The property B2 depends on: move a shape and its stitches move with it,
    unchanged. Measured 35.16px of re-phasing before the fix."""
    a = _scanline_angled(_bar(400, 400, 60, 60), angle, 5, 40, 3.0)
    b = _scanline_angled(_bar(400, 400, 160, 90), angle, 5, 40, 3.0)
    assert a, "probe produced no stitches"
    assert _worst(a, b, dx=100.0, dy=30.0) < 1e-6, (
        f"{angle} deg: translating the object changed its fill pattern"
    )


@pytest.mark.parametrize("angle", ANGLES)
def test_the_jump_flags_travel_with_the_object_too(angle):
    """Coordinates matching while the jump pattern differs would still mean two
    different stitch-outs — same needle positions, different trims."""
    a = _scanline_angled(_bar(400, 400, 60, 60), angle, 5, 40, 3.0)
    b = _scanline_angled(_bar(400, 400, 160, 90), angle, 5, 40, 3.0)
    assert [p[2] for p in a] == [p[2] for p in b]


def test_an_empty_region_yields_nothing_rather_than_raising():
    """The crop is taken from the foreground window, which does not exist for an
    empty mask. Fills are called on masks that can legitimately be empty (a hole
    knocked out everything, a side of a divided flow), so this must return
    rather than blow up."""
    assert _scanline_angled(np.zeros((50, 50), np.uint8), 30.0, 5, 40, 3.0) == []


def test_the_shallow_angle_shortcut_is_still_position_independent():
    """Below 0.5 degrees `_scanline_angled` delegates to `_scanline_fill`, which
    never rotated and so never had the bug. Pin it anyway — the shortcut is a
    second code path and 'the other branch is fine' is how the first one got
    missed."""
    a = _scanline_angled(_bar(400, 400, 60, 60), 0.0, 5, 40, 3.0)
    b = _scanline_angled(_bar(400, 400, 160, 90), 0.0, 5, 40, 3.0)
    # _scanline_fill lays rows on the canvas grid, so a translation that is a
    # whole number of row pitches is the honest thing to compare.
    assert a and b
    assert _worst(a, b, dx=100.0, dy=30.0) < 1e-6


def test_the_probe_would_have_caught_the_old_behaviour():
    """Guard the guard: reproduce the canvas-centre rotation inline and show
    these assertions reject it. Without this the tests above could be passing
    for some unrelated reason."""
    from app.services.digitizer.geometry import _warp_fit
    from app.services.digitizer.fills import _scanline_fill

    def old(region, angle_deg, row_px, max_step_px, connect_px):
        h, w = region.shape
        rot, Minv = _warp_fit(region, (w / 2.0, h / 2.0), angle_deg)
        out = []
        for x, y, jump in _scanline_fill(rot, row_px, max_step_px, connect_px):
            X = Minv[0, 0] * x + Minv[0, 1] * y + Minv[0, 2]
            Y = Minv[1, 0] * x + Minv[1, 1] * y + Minv[1, 2]
            out.append((float(X), float(Y), jump))
        return out

    a = old(_bar(400, 400, 60, 60), 30.0, 5, 40, 3.0)
    b = old(_bar(400, 400, 160, 90), 30.0, 5, 40, 3.0)
    if len(a) == len(b):
        assert _worst(a, b, dx=100.0, dy=30.0) > 1.0, (
            "the old canvas-centre rotation looks position-independent on this "
            "probe, so the tests above are not demonstrating the fix"
        )


# ── STEP 3b: the raster digitize used is recorded, and rebuild honours it ────


def test_digitize_stamps_the_raster_it_used():
    """Every generator in the package is a raster operation, so the grid is part
    of what produced a design's stitches. Rebuild had no way to know it and
    picked its own, a third coarser."""
    from pathlib import Path

    from app.services.digitizer import digitize_image

    fixtures = Path(__file__).resolve().parent / "fixtures" / "quality_bench"
    cv2.setRNGSeed(1234)
    d = digitize_image((fixtures / "01_flat_2color_logo.png").read_bytes(),
                       "cotton", "100x100", 6)
    assert d.source_mm_per_px, "digitize did not record its raster"
    # 0.075 mm/px on this corpus. Band, not an exact value: the raster follows
    # the source image and the hoop.
    assert 0.02 <= d.source_mm_per_px <= 0.30, d.source_mm_per_px


def test_rebuild_uses_the_stamped_raster():
    from app.models.design import ColorStop, Design, DesignObject, Point, StitchType, UnderlayType
    from app.services.digitizer import rebuild_design

    def design_with(mm_per_px):
        obj = DesignObject(
            id="x", name="Fill 1", sequence_order=1, color_stop=1,
            stitch_type=StitchType.TATAMI, underlay_type=UnderlayType.NONE,
            density=2.5, stitch_angle=0.0, pull_compensation=0.0,
            contour=[Point(x=0, y=0), Point(x=40, y=0), Point(x=40, y=30), Point(x=0, y=30)],
        )
        return Design(
            name="t", width_mm=40, height_mm=30,
            color_stops=[ColorStop(stop_number=1, thread_brand="M", catalog_number="1",
                                   thread_name="a", hex="#112233")],
            objects=[obj], stitches=[], source_mm_per_px=mm_per_px,
        )

    fine = len(rebuild_design(design_with(0.05)).stitches)
    coarse = len(rebuild_design(design_with(0.20)).stitches)
    assert fine != coarse, (
        "the stamped raster is stored but not reaching the generators — "
        "rebuild produced the same stream at 0.05 and 0.20 mm/px"
    )


def test_a_design_without_a_stamp_still_rebuilds():
    """Older saves and imported stitch files have no raster. They must fall back
    to the previous behaviour, not crash and not produce nothing."""
    from pathlib import Path

    from app.services.digitizer import digitize_image, rebuild_design

    fixtures = Path(__file__).resolve().parent / "fixtures" / "quality_bench"
    cv2.setRNGSeed(1234)
    d = digitize_image((fixtures / "05_wordmark_caps.png").read_bytes(),
                       "cotton", "100x100", 4)
    legacy = d.model_copy(deep=True)
    legacy.source_mm_per_px = None
    assert len(rebuild_design(legacy, force=True).stitches) > 0


def test_an_absurd_stamp_cannot_blow_up_the_canvas():
    """A stored raster is data, and data can be wrong or hostile. The 2000px
    canvas cap must still bound the allocation."""
    from pathlib import Path

    from app.services.digitizer import digitize_image, rebuild_design

    fixtures = Path(__file__).resolve().parent / "fixtures" / "quality_bench"
    cv2.setRNGSeed(1234)
    d = digitize_image((fixtures / "05_wordmark_caps.png").read_bytes(),
                       "cotton", "100x100", 4)
    hostile = d.model_copy(deep=True)
    hostile.source_mm_per_px = 1e-6  # a million px per mm
    out = rebuild_design(hostile, force=True)
    assert len(out.stitches) > 0


def test_the_stamp_survives_a_rebuild():
    """A second edit must land on the same grid as the first, or every edit
    re-rasters the design slightly differently — the C6 failure mode wearing a
    different hat."""
    from pathlib import Path

    from app.services.digitizer import digitize_image, rebuild_design

    fixtures = Path(__file__).resolve().parent / "fixtures" / "quality_bench"
    cv2.setRNGSeed(1234)
    d = digitize_image((fixtures / "05_wordmark_caps.png").read_bytes(),
                       "cotton", "100x100", 4)
    once = rebuild_design(d.model_copy(deep=True), force=True)
    assert once.source_mm_per_px == d.source_mm_per_px
