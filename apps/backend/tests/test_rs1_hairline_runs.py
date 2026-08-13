"""A hairline is not unsewable, it is uncolumnable — and now it is run (RS1).

`sub_thread_feature` refuses a region because it cannot carry a satin column.
Before RS1 that refusal deleted the artwork: fixture 04's inner ring — 0.21 mm
wide, 55.9 mm², a fifth of the drawing — digitized to nothing, with (after
DET2) an honest 31.59 % uncovered and a warning. 40wt thread at ~0.4 mm
over-covers a 0.21 mm line two to one; a human digitizer sews it as a run
without thinking. The machine now does the same: thin to the centreline, prune
spurs at the repo's standing noise floor, and emit each surviving branch as a
RUNNING_SINGLE object through `_manual_run` — the same function rebuild's
RUNNING branch calls, so the round trip re-runs the stored path through the
code that produced it. (That only became possible when the entry-point
convention was unified in `ce254a8`; the defect fix deliberately shipped
first and alone.)

THE GATE, and why 09 is in this file: two criteria, deliberately separate.
Sewability (spur pruning + length >= one pitch, both derived) decides what the
customer gets. Assertability (penetrations >= 1/band) is a property of our
test arithmetic and lives in the band tests, never here. Fixture 09's refused
region is where they disagree: after pruning it yields three short trunks of
1.4–2.9 mm — sewable, so they are SEWN — each carrying 3–4 penetrations, far
too few for any percentage band. The RS1 mechanism doc predicted 09 would be
refused as spur noise; the measurement corrected the prediction, because
pruning at SPUR_MIN_MM eats the seventeen 0.8 mm hairs and what remains is
three real strokes. The disagreement is reported here as the ruling requires,
by pinning both halves: they exist, and no band test asserts on them.
"""

from __future__ import annotations

import cv2
import pytest

from app.services.digitizer import digitize_image, pipeline, rebuild_design

from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "quality_bench"
RNG_SEED = 20260728


def _digitize(stem: str, hoop: str, colors: int):
    cv2.setRNGSeed(RNG_SEED)
    d = digitize_image((FIXTURES / f"{stem}.png").read_bytes(),
                       fabric_type="cotton", hoop_size=hoop, max_colors=colors)
    return d, list(pipeline._CLASSIFICATION_LOG)


@pytest.fixture(scope="module")
def ring():
    return _digitize("04_thin_line_outline", "100x100", 2)


def test_the_refused_ring_becomes_a_run(ring):
    design, log = ring
    runs = [o for o in design.objects
            if str(getattr(o.stitch_type, "value", o.stitch_type)) == "RUNNING_SINGLE"]
    assert runs, "04's 0.21mm inner ring should be sewn as a run, not deleted"
    assert all("Hairline" in o.name for o in runs)
    # ~153.5mm of centreline at 1.4mm pitch — around 110 penetrations. A floor
    # of 80 catches the ring collapsing to a fragment without pinning the exact
    # resample count, which moves with smoothing.
    assert sum(o.penetration_count for o in runs) >= 80
    assert any(e["decision"] == "RUN" and e["reason"] == "sub_thread_run" for e in log)


def test_the_run_round_trips_within_the_fidelity_band(ring):
    """Digitize's emitter and rebuild's RUNNING branch share `_manual_run`, so
    the residual is pixel-grid requantisation — measured +2.75 % on this ring.
    Asserted against the 04 P6 band (0.10), not the measured value."""
    design, _ = ring
    reb = rebuild_design(design.model_copy(deep=True), force=True)
    b = {o.sequence_order: int(o.penetration_count or 0) for o in reb.objects}
    for o in design.objects:
        if "Hairline" not in o.name:
            continue
        drift = b[o.sequence_order] / o.penetration_count - 1.0
        assert abs(drift) <= 0.10, (
            f"{o.name}: {o.penetration_count} -> {b[o.sequence_order]} "
            f"({drift:+.2%}) — outside the fixture's own fidelity band"
        )


def test_sewable_but_not_assertable_branches_are_sewn(ring):
    """The two-criteria disagreement on fixture 09, pinned from both sides.

    Falsified by: the gate refusing short-but-real strokes again (objects
    vanish), or someone 'fixing' a band test to assert percentages on them.
    The second half is enforced structurally in the band tests via their
    min_pen exclusion; here we pin the first half plus the census view.
    """
    design, log = _digitize("09_nonuniform_background", "130x180", 4)
    runs = [o for o in design.objects
            if str(getattr(o.stitch_type, "value", o.stitch_type)) == "RUNNING_SINGLE"]
    assert runs, "09's pruned trunks are sewable and must be sewn"
    # Every one is below any band's assertability minimum — that is the point.
    assert all(o.penetration_count < 10 for o in runs)
    assert all(o.penetration_count >= 2 for o in runs), (
        "a run of fewer than 2 penetrations is not a line; the length gate "
        "(>= one pitch) should have refused it"
    )


def test_run_objects_keep_the_stream_accounting_honest(ring):
    """RS1 added an emission site inside pass B. The identity that found the
    two previously-unnamed sites must hold over the new one with NO new
    category — run objects set obj_start before their TRIM/JUMP exactly like
    the main loop, so their lead-in is in-span by construction."""
    design, _ = ring
    acc = dict(pipeline._LAST_STREAM_ACCOUNTING)
    # module state describes the LAST digitize in this module: re-digitize 04
    cv2.setRNGSeed(RNG_SEED)
    digitize_image((FIXTURES / "04_thin_line_outline.png").read_bytes(),
                   fabric_type="cotton", hoop_size="100x100", max_colors=2)
    acc = dict(pipeline._LAST_STREAM_ACCOUNTING)
    named = (acc["object_spans"] + acc["stop_separators"] + acc["linework_lead_in"]
             + acc["end_markers"] + acc["merge_inserted"] + acc["lock_inserted"])
    assert named == acc["stream_length"]
    assert acc["penetrations_in_object_spans"] + acc["lock_penetrations"] == acc["penetrations"]
