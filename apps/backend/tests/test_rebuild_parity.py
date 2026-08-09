"""CTO B1.5 — rebuild must not damage what the user did not edit.

C6: rebuild re-rasters the whole design, so every Apply and every Optimize
roughened every edge and repeated edits accumulated the damage. A8 raised the
raster to DST's own 0.1mm grid, which shrinks the damage but cannot remove it —
regenerating from a contour APPROXIMATES coordinates, it cannot reproduce them.

The fix is to notice there is nothing to do: each object carries a fingerprint
of the parameters that produced its stitches (`params_hash`), and a design
whose objects all still match, in the order they were made, is returned
untouched.

WHAT THIS FILE PINS, in both directions — a pass-through that fires when it
should not is data loss, and one that never fires is the original defect.
"""

from __future__ import annotations

import math

import pytest

from app.models.design import StitchType
from app.services.digitizer import rebuild_design
from app.services.digitizer.provenance import is_unedited, object_params_hash


@pytest.fixture(scope="module")
def digitized():
    from helpers import digitized_fixture

    return digitized_fixture()


def _stream(design):
    return [(str(s.command), s.x, s.y) for s in design.stitches]


# ── the pass-through fires ───────────────────────────────────────────────────


@pytest.mark.needs_rebuild_passthrough
def test_unedited_rebuild_is_byte_identical(digitized):
    r = rebuild_design(digitized)
    assert _stream(r) == _stream(digitized)


def test_repeated_rebuilds_never_accumulate_damage(digitized):
    """C6: each rebuild must not roughen what the last one produced.

    This test used to run five UN-forced rebuilds, every one of which
    short-circuited and returned the input object, so it compared `d` to `d`
    five times over and proved nothing about the generators (CTO verdict V2).
    The property it was named for is real and worth having, so it is now asked
    where it can fail: with the pass-through OFF, `force=True` every time.

    Measured on the fixture: digitize 8,903 -> first regeneration 9,664, and
    then BIT-IDENTICAL for every pass after that. Rebuild reaches a fixed point
    in one step, which is the actual C6 guarantee — the raster is driven by the
    stored contours, and rebuild never rewrites those. The 8,903 -> 9,664 step
    is the digitize/rebuild gap, banded separately by P6.
    """
    first = rebuild_design(digitized.model_copy(deep=True), force=True)
    prev = first
    for i in range(2, 6):
        cur = rebuild_design(prev.model_copy(deep=True), force=True)
        assert _stream(cur) == _stream(prev), (
            f"regeneration {i} differs from {i - 1}: rebuild has no fixed "
            f"point, so every edit a user makes degrades the design further"
        )
        prev = cur
    assert _stream(prev) == _stream(first)


@pytest.mark.needs_rebuild_passthrough
def test_recolour_and_rename_still_pass_through(digitized):
    # Neither changes a single stitch, so neither may trigger a re-raster.
    edited = digitized.model_copy(update={
        "objects": [o.model_copy(update={"name": f"renamed {i}"})
                    for i, o in enumerate(digitized.objects)],
    })
    r = rebuild_design(edited)
    assert _stream(r) == _stream(digitized)
    assert [o.name for o in r.objects] == [f"renamed {i}" for i in range(len(r.objects))]


# ── the pass-through does NOT fire ───────────────────────────────────────────


@pytest.mark.parametrize("field,value", [
    ("density", 0.5),
    ("stitch_angle", 33.0),
    ("pull_compensation", 0.9),
    ("stitch_type", StitchType.TATAMI),
])
def test_any_generator_parameter_edit_regenerates(digitized, field, value):
    first = digitized.objects[0]
    if getattr(first, field) == value:
        pytest.skip(f"fixture already has {field}={value}")
    edited = digitized.model_copy(update={
        "objects": [first.model_copy(update={field: value}), *digitized.objects[1:]],
    })
    r = rebuild_design(edited)
    assert _stream(r) != _stream(digitized), f"editing {field} was silently ignored"


def test_reordering_objects_regenerates_even_though_no_object_changed(digitized):
    # The subtle one. `object_params_hash` deliberately ignores sequence_order
    # (a reorder changes no stitch OF an object), so every object still reads
    # as unedited — but the STREAM must be re-emitted in the new order. This is
    # exactly what Optimize does, and returning the design untouched here would
    # make Optimize a silent no-op.
    if len(digitized.objects) < 2:
        pytest.skip("needs at least two objects")
    reordered = list(reversed(digitized.objects))
    renumbered = [o.model_copy(update={"sequence_order": i + 1})
                  for i, o in enumerate(reordered)]
    r = rebuild_design(digitized.model_copy(update={"objects": renumbered}))
    assert _stream(r) != _stream(digitized)


def test_a_design_without_provenance_regenerates(digitized):
    # Every design saved before B1.5 and every imported machine file has no
    # fingerprint. Those must behave exactly as they did before — regenerate —
    # rather than being trusted by default.
    legacy = digitized.model_copy(update={
        "objects": [o.model_copy(update={"params_hash": None}) for o in digitized.objects],
    })
    r = rebuild_design(legacy)
    assert _stream(r) != _stream(digitized)


def test_a_tampered_fingerprint_regenerates(digitized):
    # A hash that does not match its own object is not evidence of anything.
    tampered = digitized.model_copy(update={
        "objects": [digitized.objects[0].model_copy(update={"params_hash": "0" * 32}),
                    *digitized.objects[1:]],
    })
    assert _stream(rebuild_design(tampered)) != _stream(digitized)


# ── provenance is maintained, so the NEXT rebuild can also pass through ──────


def test_regenerated_objects_are_restamped(digitized):
    # Without re-stamping, one edit would leave every object unfingerprinted
    # and every subsequent rebuild would regenerate the whole design forever.
    edited = digitized.model_copy(update={
        "objects": [digitized.objects[0].model_copy(update={"density": 0.7}),
                    *digitized.objects[1:]],
    })
    once = rebuild_design(edited)
    assert all(is_unedited(o) for o in once.objects), "objects came back unfingerprinted"
    twice = rebuild_design(once)
    assert _stream(twice) == _stream(once), "second rebuild re-rastered a settled design"


def test_digitize_stamps_every_object(digitized):
    assert digitized.objects
    for o in digitized.objects:
        assert o.params_hash, f"{o.name} has no fingerprint"
        assert is_unedited(o)


# ── the fingerprint itself ───────────────────────────────────────────────────


def test_fingerprint_ignores_what_cannot_change_stitches(digitized):
    o = digitized.objects[0]
    same = o.model_copy(update={
        "name": "x", "id": "abc", "sequence_order": 99, "color_stop": 7,
        "stitch_count": 1, "connect_method": o.connect_method,
    })
    assert object_params_hash(same) == object_params_hash(o)


def test_fingerprint_tracks_geometry(digitized):
    o = next(ob for ob in digitized.objects if ob.contour)
    moved = o.model_copy(update={
        "contour": [p.model_copy(update={"x": p.x + 1.0}) for p in o.contour],
    })
    assert object_params_hash(moved) != object_params_hash(o)


@pytest.mark.needs_rebuild_passthrough
def test_fingerprint_survives_a_json_round_trip(digitized):
    # A design that goes to the cloud and comes back must still pass through;
    # float repr through JSON must not read as an edit.
    from app.models.design import Design

    reloaded = Design.model_validate_json(digitized.model_dump_json(by_alias=True))
    assert all(is_unedited(o) for o in reloaded.objects)
    assert _stream(rebuild_design(reloaded)) == _stream(digitized)


def test_float_noise_below_a_thread_width_is_not_an_edit(digitized):
    # 1e-5 mm is a hundredth of the rounding grid and far below the 0.1mm
    # criterion: it cannot change a stitch, so it must not force a re-raster.
    o = next(ob for ob in digitized.objects if ob.contour)
    jittered = o.model_copy(update={
        "contour": [p.model_copy(update={"x": p.x + 1e-5}) for p in o.contour],
    })
    assert object_params_hash(jittered) == object_params_hash(o)


def test_a_real_but_tiny_move_is_an_edit(digitized):
    # ...but 0.01mm is a real move at the 0.1mm criterion and must be caught.
    o = next(ob for ob in digitized.objects if ob.contour)
    moved = o.model_copy(update={
        "contour": [p.model_copy(update={"x": p.x + 0.01}) for p in o.contour],
    })
    assert object_params_hash(moved) != object_params_hash(o)


@pytest.mark.needs_rebuild_passthrough
def test_fidelity_criterion_holds_verbatim(digitized):
    """The review's own wording: "rebuild of an unedited design changes no
    coordinate by >0.1mm".

    THIS HOLDS FOR THE SHIPPED PATH AND ONLY THAT PATH, and it is honest to say
    so rather than quietly reinterpret the criterion. An unedited design passes
    through untouched, so the worst move is exactly 0.0mm — the criterion is met
    because nothing is regenerated, not because regeneration is faithful.
    REGENERATION DOES NOT MEET IT: forcing a rebuild of the same fixture moves
    the stitch count 8,903 -> 9,664, so "no coordinate moves by >0.1mm" is not
    even well-defined there. That gap is real, measured, and banded as P6 in
    test_probes_three_paths.py rather than hidden behind this assertion.
    """
    r = rebuild_design(digitized)
    assert len(r.stitches) == len(digitized.stitches)
    worst = max(math.hypot(a.x - b.x, a.y - b.y)
                for a, b in zip(digitized.stitches, r.stitches))
    assert worst == 0.0, f"worst move {worst:.4f}mm"
