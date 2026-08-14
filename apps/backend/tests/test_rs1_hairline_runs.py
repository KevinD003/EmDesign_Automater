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

THE GATE: sewability (spur pruning + length >= one pitch, both derived)
decides what the customer gets; assertability (penetrations >= 1/band) is a
property of our test arithmetic and lives in the band tests, never here. On
top of both sits THE SINGLE-BRANCH BOUNDARY, which has its own history: the
first RS1 build sewed fixture 09's refused region, the visual harness showed
three stray dashes 24 mm from the design, and looking at the source proved the
region is background noise — no ink. Three derived noise-vs-ink criteria were
measured and all three refuted (see `hairline_runs`' docstring for the
numbers), so the ruling's authorised fallback applies: only single-branch
pruned skeletons run — 11 of the corpus's 14 refused regions. That refuses
the verified noise and, as a NAMED COST, also refuses 07's two short real
strokes and C11's 4-branch network until a derived criterion exists.

IT IS A PROXY, NOT A DETECTOR. 09's noise reached the render with spur
pruning already in place; single-branch excluded it only because that noise
happened to fragment into several branches. A noise sliver that prunes to one
branch would be sewn and nothing numeric would object. See `hairline_runs`.
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


def test_the_noise_region_is_refused_at_the_single_branch_boundary():
    """Fixture 09's refused region is BACKGROUND NOISE — verified by looking at
    the source: quantisation slivers of the noise texture, no ink. The first
    RS1 build sewed it as three stray dashes 24mm from the design; the VISUAL
    harness caught what every numeric gate passed, which is Parts 39-41's
    lesson repeating on schedule.

    Three derived noise-vs-ink criteria were measured and refuted (spur
    dominance separates but only via a fitted threshold; colour coherence is
    INVERTED — noise averages to its own cluster centre; substrate distance
    does not separate: 64.8 noise vs 61.4 real). So the boundary is the one
    the ruling authorised for exactly this outcome: only single-branch pruned
    skeletons run. 09 (3 branches) and 07 (2 branches) are refused — 07's two
    short strokes are REAL artwork, a named cost carried until a derived
    criterion exists; C11's 4-branch network likewise.

    WHAT THIS TEST DOES NOT PROVE: that noise is detected. The boundary caught
    09 because 09's noise fragments; it is a proxy that excluded the one noise
    instance in this corpus, not a detector. This test passing on a future
    input is not evidence that input's noise was caught.

    Falsified by: 09 emitting any run object (the noise regression returns),
    or the boundary quietly widening without a derivation.
    """
    design, log = _digitize("09_nonuniform_background", "130x180", 4)
    runs = [o for o in design.objects
            if str(getattr(o.stitch_type, "value", o.stitch_type)) == "RUNNING_SINGLE"]
    assert not runs, "09's background noise must not be sewn"
    assert any(e["decision"] == "SKIPPED" for e in log)

    design7, _ = _digitize("07_circular_badge", "130x180", 4)
    assert not any("Hairline" in o.name for o in design7.objects), (
        "07's region prunes to TWO branches; sewing it means the boundary "
        "widened — that needs a derived criterion, not a silent change"
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
