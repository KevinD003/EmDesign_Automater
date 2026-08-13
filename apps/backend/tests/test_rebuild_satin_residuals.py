"""The three defects `250e850` left in rebuild's spine-satin path.

`250e850` moved rebuild's satin TOP LAYER onto the medial axis, matching
digitize. It left three things behind, all found by measuring rather than
reading:

  R1  THE UNDERLAY STAYED ON THE BOUNDING RECT. `_rebuild_underlay` called
      `_center_walk(mask, rect, …)`, a straight line through the centroid at
      the stored angle, while the column above it followed the spine. On a
      ring or an arc that line leaves the column entirely and the underlay is
      sewn on bare fabric. digitize never had this — `_satin_width_underlay`
      takes `axis_pts` precisely so the two layers agree.

  R2  PULL COMPENSATION WAS APPLIED TWICE. Rebuild measured the already
      `_dilate_pull`-ed mask AND passed `pull/2` again as the extra column
      half-width. `pipeline.py` warns about this at its own call site:
      "measuring the pre-dilated mask would fold pull comp into the width test
      and push a 3.66mm stem over the cap."

  R3  THE AUTO-ANGLE GATE WAS TIGHTER THAN ITS OWN NOISE FLOOR. The 0.15°
      tolerance compared a stored angle (rounded to 1dp, measured by digitize
      at 13.3px/mm) against a `minAreaRect` recomputed on the same contour
      requantized to rebuild's 10px/mm grid. Measured on a fresh digitize with
      NO edits at all — so every delta is pure requantization noise — the gate
      sent 5 of 7 untouched satin columns on `06_wordmark_script` to the
      bounding-rect sweep, the very path B1.5 moved them off.

Measured, digitize vs rebuild-after-a-real-1%-density-edit, before -> after:

  04_thin_line_outline  1,465 -> 1,477 st · worst -11.4% -> -10.1% · 6/6 objects survive
  05_wordmark_caps      1,058 -> 1,368 st · worst -86.6% ->  -6.8% · 5/6 -> 6/6 survive
  06_wordmark_script      733 -> 1,263 st · worst -85.0% -> -18.9% · 6/7 -> 7/7 survive

Note the survival columns: two fixtures were SILENTLY LOSING AN OBJECT, because
a rect sweep across a curved script stroke produced under two points and
`rebuild.py`'s `if len(pts) < 2: continue` dropped it without a word.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.models.design import Design
from app.services.digitizer import digitize_image
from app.services.digitizer.rebuild import (
    SATIN_ANGLE_AUTO_TOL_DEG,
    _angle_is_digitizes_own,
    rebuild_design,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "quality_bench"


def _digitize(stem: str, colors: int = 4) -> Design:
    cv2.setRNGSeed(1234)
    return digitize_image((FIXTURES / f"{stem}.png").read_bytes(), "cotton", "100x100", colors)


def _edited(design: Design) -> Design:
    """A REAL edit — 1% density on the first object, enough to defeat the
    provenance pass-through and force every object down the rebuild path."""
    d = design.model_copy(deep=True)
    d.objects[0].density = round(float(d.objects[0].density or 4.0) * 1.01, 6)
    return d


def _losses(dig: Design, rb: Design) -> list[float]:
    a = {o.sequence_order: int(o.stream_span or 0) for o in dig.objects}
    b = {o.sequence_order: int(o.stream_span or 0) for o in rb.objects}
    return sorted(b[k] / a[k] - 1.0 for k in a if k in b and a[k])


# ── R3: the auto-angle gate ──────────────────────────────────────────────────


class _Obj:
    """Minimal stand-in — `_angle_is_digitizes_own` only reads `params_hash`
    and whatever `object_params_hash` hashes."""

    def __init__(self, params_hash=""):
        self.params_hash = params_hash
        self.stitch_type = "SATIN"
        self.density = 4.0
        self.stitch_angle = 90.0
        self.underlay_type = "CENTER_WALK"
        self.pull_compensation = 0.2
        self.contour = []
        self.holes = []
        self.flow_line = []
        self.flow_line_b = []
        self.flow_divide = []


def test_an_unedited_object_takes_the_spine_whatever_the_raster_says():
    """The load-bearing case. An untouched object's stored angle IS digitize's
    own by definition, so requantization noise must not send it to the rect
    sweep — that is what cost 06_wordmark_script five of its seven columns."""
    from app.services.digitizer.provenance import object_params_hash

    obj = _Obj()
    obj.params_hash = object_params_hash(obj)
    # A rect axis 30 degrees away — far outside any tolerance. Provenance wins.
    rect = ((0.0, 0.0), (10.0, 2.0), 60.0)
    assert _angle_is_digitizes_own(obj, 90.0, rect)


def test_an_edited_object_with_a_real_angle_change_falls_back_to_the_rect():
    """P4's contract: an edited `stitch_angle` must change the stream. A spine
    has no single angle, so an explicit angle can only be honoured by the rect
    sweep."""
    obj = _Obj(params_hash="stale-hash-because-the-user-edited-something")
    rect = ((0.0, 0.0), (10.0, 2.0), 0.0)  # axis 0 deg
    assert not _angle_is_digitizes_own(obj, 77.0, rect)


def test_the_edited_fallback_still_absorbs_requantization_noise():
    obj = _Obj(params_hash="stale")
    rect = ((0.0, 0.0), (10.0, 2.0), 0.0)
    # Inside the band: still "auto", just re-rasterized.
    assert _angle_is_digitizes_own(obj, SATIN_ANGLE_AUTO_TOL_DEG * 0.5, rect)
    # Outside it: a real edit.
    assert not _angle_is_digitizes_own(obj, SATIN_ANGLE_AUTO_TOL_DEG * 3.0, rect)


def test_the_angle_band_wraps_at_180_degrees():
    """179.5 deg and 0 deg are half a degree apart, not 179.5. Without the
    wrap, every satin sitting just under 180 read as a deliberate edit."""
    obj = _Obj(params_hash="stale")
    rect = ((0.0, 0.0), (10.0, 2.0), 0.0)
    assert _angle_is_digitizes_own(obj, 179.5, rect)


def test_the_old_tolerance_would_fail_these():
    """Negative control. If someone restores 0.15 deg, the noise case breaks —
    pin that the band is doing real work rather than passing by luck."""
    assert SATIN_ANGLE_AUTO_TOL_DEG > 0.15


# ── R1 + R2 + R3 together: what a user actually gets ─────────────────────────


# (stem, colors, max acceptable single-object loss)
PARITY_BANDS = [
    ("04_thin_line_outline", 4, 0.15),
    ("05_wordmark_caps", 4, 0.15),
    ("06_wordmark_script", 4, 0.25),
]


@pytest.mark.parametrize(("stem", "colors", "max_loss"), PARITY_BANDS)
def test_editing_a_satin_design_keeps_every_object(stem, colors, max_loss):
    dig = _digitize(stem, colors)
    rb = rebuild_design(_edited(dig))
    assert rb is not dig, "the pass-through swallowed a real density edit"

    kept = {o.sequence_order for o in rb.objects}
    lost = sorted({o.sequence_order for o in dig.objects} - kept)
    assert not lost, (
        f"{stem}: rebuild dropped object(s) {lost} entirely. A rect sweep across "
        f"a curved stroke can yield under two points, and rebuild's "
        f"`if len(pts) < 2: continue` deletes the object without a word."
    )

    losses = _losses(dig, rb)
    assert losses, "no objects to compare"
    assert min(losses) >= -max_loss, (
        f"{stem}: worst object lost {min(losses):.1%} of its stitches against a "
        f"fresh digitize (band {max_loss:.0%}). Before the 250e850 residual "
        f"fixes the worst was -85.0% on this corpus."
    )


def test_the_wordmark_script_is_the_case_that_regressed():
    """The specific fixture the CTO named. Pinned on its own so a corpus-wide
    band cannot hide it: total stitches were 733 against digitize's 1,284."""
    dig = _digitize("06_wordmark_script")
    rb = rebuild_design(_edited(dig))
    ratio = len(rb.stitches) / max(len(dig.stitches), 1)
    assert ratio >= 0.90, (
        f"edited rebuild is {ratio:.1%} of digitize's stitch count "
        f"(was 57.1% before the residual fixes)"
    )


# ── R2 specifically: pull comp must not be counted twice ─────────────────────


def test_the_skeleton_measures_the_undilated_mask():
    """Reading the source is the only way to catch this one: both the dilated
    and undilated masks produce plausible output, and the difference only shows
    up on a stem near the satin width cap. Pin that the width test is taken on
    `mask`, never on the pull-dilated `top`."""
    root = Path(__file__).resolve().parents[1] / "app" / "services" / "digitizer"

    # STEP 3c moved the sweep into `generation.spine_satin`, so the claim now
    # has two halves and both must hold.
    #
    # 1. rebuild hands the core the UNDILATED mask, not the pull-dilated `top`.
    reb = (root / "rebuild.py").read_text()
    call = reb[reb.index("attempt = spine_satin("):]
    call = call[: call.index("\n                    )")]
    assert "mask," in call and "top," not in call, (
        f"rebuild passes the pull-dilated mask to the satin core, so pull "
        f"compensation is counted twice. Got:\n{call}"
    )
    # 2. the core adds pull to the column half-width itself, which is the other
    #    half of the double-count.
    #
    # Asserted through the AST, on WHICH ARGUMENT carries pull, rather than by
    # matching the expression's source text. The literal form pinned here used
    # to be `"(pull_mm / 2.0) / mm_per_px"`, which made the test a guard on UP1
    # — satin receiving half the per-side compensation a fill receives from the
    # same stored number — instead of a guard on the double-count it is named
    # for. Correcting the halving failed this test, which is precisely backwards.
    # The claim that belongs here is "pull reaches the half-width argument at
    # all"; how much of it does is UP1's question and is measured behaviourally
    # in test_generation_core.py.
    import ast

    tree = ast.parse((root / "generation.py").read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_skeleton_satin_hires"]
    assert len(calls) == 1, f"expected one sweep call in the core, found {len(calls)}"
    extra_arg = calls[0].args[4]           # the extra half-width, per side
    assert "pull_mm" in {n.id for n in ast.walk(extra_arg) if isinstance(n, ast.Name)}, (
        "the core no longer adds pull compensation to the column half-width: "
        f"argument 5 of the sweep is {ast.unparse(extra_arg)!r}"
    )


def test_double_dilation_would_actually_change_the_width_verdict():
    """Guard the guard: show the two masks differ enough to matter, so the test
    above is not pinning a distinction without a difference."""
    from app.services.digitizer.geometry import _dilate_pull

    mask = np.zeros((80, 200), np.uint8)
    cv2.rectangle(mask, (20, 34), (180, 46), 255, -1)  # a 12px-wide bar
    top = _dilate_pull(mask, 0.4, 0.1)  # 0.4mm pull at 0.1mm/px

    def median_w(m):
        dt = cv2.distanceTransform((m > 0).astype(np.uint8), cv2.DIST_L2, 5)
        return float(np.median(dt[dt > 0])) * 2.0 * 0.1

    assert median_w(top) > median_w(mask) * 1.10, (
        "pull dilation barely moves the measured width on this probe, so the "
        "source assertion above would not be protecting anything"
    )


# ── R1 specifically: the underlay follows the same axis as the column ────────


def test_underlay_walks_the_spine_when_the_column_does():
    """With an axis the underlay runs along it; without one it falls back to
    the rect midline. A ring is the case that exposed this: its rect midline
    crosses the open counter."""
    from app.services.digitizer.underlay import _rebuild_underlay

    ring = np.zeros((240, 240), np.uint8)
    cv2.circle(ring, (120, 120), 90, 255, -1)
    cv2.circle(ring, (120, 120), 66, 0, -1)
    rect = ((120.0, 120.0), (2.0, 1.0), 0.0)

    # Axis samples are (x, y, is_jump), the shape `_skeleton_satin_hires` returns.
    spine = [(120.0 + 78.0 * float(np.cos(t)), 120.0 + 78.0 * float(np.sin(t)), False)
             for t in np.linspace(0, 2 * np.pi, 96)]

    with_axis = _rebuild_underlay(
        "SATIN", "CENTER_WALK", ring, rect, 0.0, 4, 20, 3.0, 40, 0.1,
        0.0, 40.0, 6, 4.0, 2.0, 2.0, 45.0, axis_pts=spine,
    )
    without = _rebuild_underlay(
        "SATIN", "CENTER_WALK", ring, rect, 0.0, 4, 20, 3.0, 40, 0.1,
        0.0, 40.0, 6, 4.0, 2.0, 2.0, 45.0,
    )
    assert with_axis, "no underlay produced from the medial axis"

    def outside_the_band(pts):
        return sum(1 for x, y, *_ in pts
                   if not (66 <= np.hypot(x - 120.0, y - 120.0) <= 90))

    assert outside_the_band(with_axis) == 0, (
        "the spine-driven underlay left the ring's band — it should follow the "
        "same path the satin column does"
    )
    # And the rect midline demonstrably does not, which is the whole defect.
    assert outside_the_band(without) > 0, (
        "the rect-midline fallback stayed inside the ring on this probe, so "
        "this test is not demonstrating the defect it was written for"
    )
