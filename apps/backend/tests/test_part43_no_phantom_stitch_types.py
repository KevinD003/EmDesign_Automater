"""Every StitchType must produce its own stitch stream (v2 Part 43, R002).

The enum declared 23 members and the engine produced **nine distinct streams**.
Eleven of them — CROSS_STITCH, CHENILLE, PHOTO_STITCH, GRADIENT_BLEND, MOTIF_FILL,
MOTIF_RUN, STEMSTITCH, ZIGZAG, E_STITCH, ACCORDION_FILL, LAYDOWN — fell through
`rebuild_design`'s final `else` and came back as a byte-identical tatami fill.
BACKSTITCH was byte-identical to RUNNING_DOUBLE, REDWORK to RUNNING_SINGLE.

Nothing surfaced it. The UI never offered those options, so it only showed through
the public API, where picking cross-stitch got you tatami and no warning.

These tests are the standing guard: a member with no generator now fails here
rather than shipping the wrong stitch.
"""

from __future__ import annotations

import hashlib

import cv2
import numpy as np
import pytest

from app.models.design import LEGACY_STITCH_TYPES, DesignObject, StitchType
from app.services.digitizer import digitize_image, rebuild_design

# MANUAL is provenance, not a generator: it marks a path the user placed by hand
# so rebuild runs along it instead of re-deriving a fill. Producing the same
# stream as RUNNING_SINGLE is the intended behaviour, not a phantom.
ALIASES_BY_DESIGN = {StitchType.MANUAL: StitchType.RUNNING_SINGLE}


def _bar_design():
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.rectangle(img, (60, 110), (240, 190), (30, 30, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)


def _stream_hash(design) -> str:
    return hashlib.sha256("\n".join(
        f"{s.command}|{s.x:.4f}|{s.y:.4f}" for s in design.stitches).encode()).hexdigest()


def _rebuild_as(base, stitch_type: StitchType):
    d = base.model_copy(deep=True)
    for o in d.objects:
        o.stitch_type = stitch_type
    return rebuild_design(d)


@pytest.fixture(scope="module")
def base():
    return _bar_design()


@pytest.fixture(scope="module")
def hashes(base):
    return {t: _stream_hash(_rebuild_as(base, t)) for t in StitchType}


@pytest.mark.parametrize("stitch_type", list(StitchType))
def test_every_stitch_type_rebuilds_without_falling_through(stitch_type, base):
    """No member may hit the `no generator` guard, and none may sew nothing."""
    out = _rebuild_as(base, stitch_type)
    assert out.stitch_count > 0, f"{stitch_type} produced an empty stream"


def test_no_two_stitch_types_produce_the_same_stream(hashes):
    """The property that failed before: 23 names, 9 behaviours."""
    by_hash: dict[str, set[str]] = {}
    for t, h in hashes.items():
        by_hash.setdefault(h, set()).add(t.value)

    unexplained = []
    for names in by_hash.values():
        remaining = set(names)
        for alias, target in ALIASES_BY_DESIGN.items():
            if {alias.value, target.value} <= remaining:
                remaining.discard(alias.value)
        if len(remaining) > 1:
            unexplained.append(sorted(remaining))

    assert not unexplained, (
        f"stitch types that are different names for the same stream: {unexplained}. "
        f"Either give each its own generator or remove it from the enum."
    )


def test_the_removed_members_are_gone(hashes):
    """Re-adding one without a generator is the regression this guards."""
    declared = {t.value for t in StitchType}
    for gone in LEGACY_STITCH_TYPES:
        assert gone not in declared, (
            f"{gone} is back in StitchType. It was removed because it had no "
            f"generator; only re-add it once one exists."
        )


def test_a_design_saved_with_a_removed_type_still_loads():
    """Rejecting old data would 422 a design that used to open."""
    for legacy, expected in LEGACY_STITCH_TYPES.items():
        obj = DesignObject(
            sequence_order=1, name="legacy", stitch_type=legacy, color_stop=1,
        )
        assert obj.stitch_type == expected.value, (
            f"{legacy} must migrate to {expected.value}, the stream it really produced"
        )


def test_an_unknown_stitch_type_fails_loudly_instead_of_sewing_tatami(base):
    """The whole defect in one test: no silent catch-all fill."""
    d = base.model_copy(deep=True)
    for o in d.objects:
        # Bypass validation the way stored JSON or a future enum member would.
        object.__setattr__(o, "stitch_type", "NOT_A_REAL_STITCH")
    with pytest.raises(ValueError, match="no generator for stitch type"):
        rebuild_design(d)


def test_the_fill_family_still_produces_genuinely_different_fills(hashes):
    """Guard the positive side: the four fills must not converge."""
    fills = [StitchType.TATAMI, StitchType.CONTOUR_FILL,
             StitchType.SPIRAL_FILL, StitchType.RADIAL_FILL]
    assert len({hashes[f] for f in fills}) == len(fills)
