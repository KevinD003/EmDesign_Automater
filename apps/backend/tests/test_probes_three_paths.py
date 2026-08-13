"""Every §8 acceptance probe, run on all THREE paths a design can reach.

CTO verdict 2026-08-09, STEP 1. The probes in `test_cto_probes.py` only ever
exercised `digitize_image`. That was already a gap, and B1.5's provenance
pass-through turned it into a blind spot:

    if rebuild_is_a_noop(design, objs):
        return design

An unedited design rebuilds to *the very same object*, so P6 — "does rebuilding
an unedited design reproduce its stream?" — compared a design to itself and
passed by identity, no matter how far the two code paths had drifted. Five more
probes were hollowed out the same way. Measured while restoring the signal: with
the short-circuit disabled, the regenerated stream differs from digitize's by
up to 8% overall and up to 36% on a single object. None of that was visible.

THE THREE PATHS
    digitize          `digitize_image` — the reference
    rebuild-unedited  `rebuild_design(..., force=True)` — the same objects
                      regenerated. force= is what makes this a measurement
                      rather than a tautology; `test_the_passthrough_is_real`
                      below separately pins that the UN-forced call really does
                      short-circuit, because that is a correctness property in
                      its own right.
    rebuild-edited    a real 1% density edit, which is what a user actually
                      does and the only path that runs the generators in anger.

Bands here are BANDS, per the verdict — set from measured values with headroom,
not exact hashes. A hash moves with the regression; that is how a 2-pixel travel
floor manufactured 70.8% of a fixture's stitches with every gate green.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from app.models.design import Design
from app.services.digitizer import digitize_image, rebuild_design
from app.services.embroidery_io import read_embroidery, write_embroidery

PATHS = ("digitize", "rebuild-unedited", "rebuild-edited")


def _real_edit(design: Design) -> Design:
    """The smallest edit a user can make that is genuinely an edit: 1% density
    on the first object. Anything less and the fingerprint still matches."""
    d = design.model_copy(deep=True)
    d.objects[0].density = round(float(d.objects[0].density or 4.0) * 1.01, 6)
    return d


def _three_paths(dig: Design) -> dict[str, Design]:
    return {
        "digitize": dig,
        "rebuild-unedited": rebuild_design(dig.model_copy(deep=True), force=True),
        "rebuild-edited": rebuild_design(_real_edit(dig)),
    }


# ── the fixtures the §8 probes use, each carried down all three paths ────────


def _ring_image() -> bytes:
    img = np.full((600, 600, 3), 255, np.uint8)
    cv2.circle(img, (300, 300), 200, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (300, 300), 110, (255, 255, 255), -1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _two_color_image() -> bytes:
    """Two separated SAME-colour blobs plus a third colour — same-colour
    separation is what forces explicit TRIMs, which is what P2 needs."""
    img = np.full((500, 900, 3), 255, np.uint8)
    cv2.circle(img, (180, 250), 120, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (720, 250), 120, (40, 60, 160), -1, cv2.LINE_AA)
    cv2.circle(img, (450, 250), 90, (150, 60, 40), -1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


@pytest.fixture(scope="module")
def ring_paths() -> dict[str, Design]:
    cv2.setRNGSeed(1234)
    return _three_paths(digitize_image(_ring_image(), "cotton", "100x100", 2))


@pytest.fixture(scope="module")
def two_color_paths() -> dict[str, Design]:
    cv2.setRNGSeed(1234)
    return _three_paths(digitize_image(_two_color_image(), "cotton", "100x100", 3))


# ── the pass-through itself, pinned as the correctness property it is ────────


@pytest.mark.needs_rebuild_passthrough
def test_the_passthrough_is_real_and_force_defeats_it():
    """Both halves matter. The un-forced call MUST short-circuit — re-stitching
    an object the user did not touch is the defect B1.5 fixed. And force= must
    actually regenerate, or every probe below is measuring the short-circuit
    again."""
    cv2.setRNGSeed(1234)
    dig = digitize_image(_ring_image(), "cotton", "100x100", 2)

    assert rebuild_design(dig) is dig, (
        "an unedited design no longer passes through — untouched objects are "
        "being re-stitched"
    )
    forced = rebuild_design(dig.model_copy(deep=True), force=True)
    assert forced is not dig, "force=True still returned the input object"
    assert forced.stitches is not dig.stitches
    assert len(forced.stitches) > 0


def test_a_real_edit_is_not_swallowed():
    cv2.setRNGSeed(1234)
    dig = digitize_image(_ring_image(), "cotton", "100x100", 2)
    edited = rebuild_design(_real_edit(dig))
    assert edited is not dig, "a 1% density edit read as 'unedited'"


# ── P1 on all three paths ────────────────────────────────────────────────────


def _counter_crossings(design: Design) -> int:
    """P1's metric verbatim: needle paths through the counter's open area, with
    the hole shrunk 7% so segments that merely kiss the rim do not count."""
    hole = next((o.holes[0] for o in design.objects if o.holes), None)
    assert hole is not None, "ring digitized without its counter"
    poly = np.array([[p.x, p.y] for p in hole], np.float32)
    cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
    shrunk = ((poly - [cx, cy]) * 0.93 + [cx, cy]).astype(np.float32)
    crossings, prev = 0, None
    for s in design.stitches:
        if str(s.command) in ("STITCH", "JUMP") and prev is not None:
            n = max(2, int(math.dist(prev, (s.x, s.y)) / 0.3))
            for i in range(1, n):
                t = i / n
                x, y = prev[0] + (s.x - prev[0]) * t, prev[1] + (s.y - prev[1]) * t
                if cv2.pointPolygonTest(shrunk, (float(x), float(y)), False) >= 0:
                    crossings += 1
                    break
        prev = (s.x, s.y)
    return crossings


# digitize is held at zero; the two rebuild paths carry the measured residual.
P1_BANDS = {"digitize": 0, "rebuild-unedited": 2, "rebuild-edited": 2}


@pytest.mark.parametrize("path", PATHS)
def test_probe1_ring_counter_stays_open_on_every_path(ring_paths, path):
    """C2 was closed on digitize and open on every edit: before STEP 0 the
    edited path put 98 needle paths straight across the counter while the probe
    reported 0, because the probe only ever looked at digitize."""
    got = _counter_crossings(ring_paths[path])
    assert got <= P1_BANDS[path], (
        f"P1 on {path}: {got} needle paths cross the ring's open counter "
        f"(band {P1_BANDS[path]}). Was 98 on the edited path before STEP 0."
    )


# ── P2 on all three paths ────────────────────────────────────────────────────


# P2's lock criterion is IMPORTED, not re-stated. Re-stating it is how the two
# paths' finishing constants drifted apart in the first place (STEP 0), and
# writing it out here immediately produced a stricter rule than P2's own — one
# that failed all three paths including digitize, which P2 passes.
from test_cto_probes import _lockish


@pytest.mark.parametrize("path", PATHS)
def test_probe2_every_thread_end_is_locked_on_every_path(two_color_paths, path):
    """A tie-off missing on the edit path is exactly as bad as one missing on
    digitize — the thread pulls out of the garment either way."""
    design = two_color_paths[path]
    sts = read_embroidery(write_embroidery(design, "dst"), "dst").stitches

    trim_idx = [i for i, s in enumerate(sts) if str(s.command) == "TRIM"]
    assert trim_idx, f"P2 on {path}: probe needs at least one trim to be meaningful"
    for i in trim_idx:
        pts = [(s.x, s.y) for s in sts[max(0, i - 5):i] if str(s.command) == "STITCH"]
        assert len(pts) >= 3 and _lockish(pts), f"P2 on {path}: trim at {i} has no tie-off"

    starts, in_block = [], False
    for i, s in enumerate(sts):
        c = str(s.command)
        if c in ("TRIM", "COLOR_CHANGE"):
            in_block = False
        elif c == "STITCH" and not in_block:
            starts.append(i)
            in_block = True
    assert starts
    for i in starts:
        pts = [(s.x, s.y) for s in sts[i:i + 6] if str(s.command) == "STITCH"]
        assert len(pts) >= 3 and _lockish(pts), (
            f"P2 on {path}: block start at {i} has no tie-in "
            f"({'stream start' if i == starts[0] else 'post-cut'})"
        )


# ── P6, restored: the fidelity signal the pass-through was answering for ─────
#
# Measured 2026-08-09 with the short-circuit disabled, digitize vs the
# regenerated stream. The second pair of columns is after STEP 3b gave rebuild
# the grid digitize actually used (`Design.source_mm_per_px`) instead of letting
# it pick 0.1 mm/px from the object bounding box — digitize runs at 0.075 on
# this corpus, a third finer, so the two paths were measuring stroke widths and
# laying rows on different grids:
#
#                             rebuild @ own grid   rebuild @ digitize's grid
#   fixture                    ratio  worst object   ratio  worst object
#   01_flat_2color_logo         1.08        -4.4%     1.06        +0.5%
#   04_thin_line_outline        0.94       -10.1%     1.00        -5.1%
#   05_wordmark_caps            1.00        -7.1%     1.00        -8.3%
#   06_wordmark_script          0.98       -18.9%     1.00       -13.5%
#   07_circular_badge           0.96       -36.2%     1.03       -25.5%
#   02_logo_fine_text_3color    0.95       -23.1%     1.08       -20.0%
#
# Worst-object improves on five of six. 05 goes slightly the other way
# (-7.1% -> -8.3%), and 02's TOTAL ratio gets worse (0.95 -> 1.08) even as its
# worst object improves. Mean |ratio - 1| 0.042 -> 0.028, mean worst-object loss
# 16.6% -> 12.0%: a clear net gain, but not a uniform one, and the bands record
# where each fixture actually landed rather than one flattering summary.
#
# The badge's -25.5% and fine-text's -20.0% are the remaining real gap. They are
# outstanding work, not certified. Bands hold the line where it now is and are
# deliberately not loose enough to absorb another regression of the size
# STEP -1 fixed.

from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "quality_bench"

# (stem, colours, min total ratio, max total ratio, max single-object loss)
FIDELITY_BANDS = [
    ("01_flat_2color_logo", 6, 0.95, 1.12, 0.10),
    ("04_thin_line_outline", 4, 0.95, 1.06, 0.12),
    ("05_wordmark_caps", 4, 0.95, 1.06, 0.14),
    ("06_wordmark_script", 4, 0.95, 1.06, 0.20),
    # 0.32 -> 0.34 for UP1 (satin receiving the full per-side pull compensation
    # a fill receives from the same stored number, instead of half). Measured by
    # running the shipped code on this tree and on a worktree at the parent
    # commit a95df3e; both numbers below are from digitize + rebuild, not a
    # probe or a re-derivation:
    #
    #                     digitize      rebuild       loss
    #   Satin 15            43 -> 46     35 -> 31    -18.6% -> -32.6%
    #   Satin 16            33 -> 36     27 -> 27    -18.2% -> -25.0%
    #   Satin 5             26 -> 29     18 -> 25    -30.8% -> -13.8%
    #   TOTAL stream ratio                            1.0217 -> 1.0153
    #
    # The AGGREGATE moved toward parity; one 46-stitch object moved away from it.
    # This is not a pull-comp path split: instrumenting rebuild shows all 14 of
    # the badge's satin objects going through `generation.spine_satin` and all 14
    # viable, so both paths receive the correction. The residual is the contour
    # round trip — digitize rasterises the source image, rebuild rasterises the
    # STORED POLYGON — and on a 46-stitch object a few pixels of polygon
    # approximation is +-7%. That is 3e-i's subject, and the ruling of 2026-08-10
    # holds it back from any change that alters either path's stream, which this
    # one does. Widened by the measured 0.6 points plus 1.4 of headroom, not to a
    # round number that would absorb a future regression unnoticed.
    ("07_circular_badge", 6, 0.95, 1.10, 0.34),
    ("02_logo_fine_text_3color", 4, 0.95, 1.15, 0.27),
]


@pytest.mark.parametrize(("stem", "colors", "lo", "hi", "max_loss"), FIDELITY_BANDS)
def test_probe6_regenerating_reproduces_the_design(stem, colors, lo, hi, max_loss):
    """P6 with the pass-through OFF. This is the parity number; the identity
    assertion it replaced could not fail."""
    cv2.setRNGSeed(1234)
    dig = digitize_image((FIXTURES / f"{stem}.png").read_bytes(), "cotton", "100x100", colors)
    reb = rebuild_design(dig.model_copy(deep=True), force=True)

    ratio = len(reb.stitches) / max(len(dig.stitches), 1)
    assert lo <= ratio <= hi, (
        f"P6 on {stem}: regenerated stream is {ratio:.2f}x digitize's "
        f"({len(reb.stitches):,} vs {len(dig.stitches):,}), band [{lo}, {hi}]"
    )

    a = {o.sequence_order: int(o.penetration_count or 0) for o in dig.objects}
    b = {o.sequence_order: int(o.penetration_count or 0) for o in reb.objects}
    assert set(a) == set(b), (
        f"P6 on {stem}: regenerating changed the object set — "
        f"missing {sorted(set(a) - set(b))}, extra {sorted(set(b) - set(a))}"
    )
    losses = {k: b[k] / a[k] - 1.0 for k in a if a[k]}
    worst_k = min(losses, key=losses.get)
    assert losses[worst_k] >= -max_loss, (
        f"P6 on {stem}: object {worst_k} lost {losses[worst_k]:.1%} of its "
        f"stitches on regeneration (band {max_loss:.0%})"
    )


def test_probe6_bands_are_not_vacuous():
    """A band wide enough to admit anything is not a probe. Pin that each one
    would reject a design half or double the reference size."""
    for stem, _c, lo, hi, max_loss in FIDELITY_BANDS:
        assert lo > 0.5 and hi < 2.0, f"{stem}: total-ratio band is too wide to mean anything"
        assert max_loss < 0.5, f"{stem}: per-object band admits losing half the object"


# ── P4 and P5: the paths that exist, and the one that does not ──────────────
#
# P4 (an edited angle changes the stream) and P5 (appliqué emits STOPs) already
# live on the rebuild path — they build synthetic objects and rebuild them. Two
# things were missing.
#
# P5 has NO digitize path and that is by design: `digitize_image` never
# classifies a region as APPLIQUE, because appliqué is a fabric-layering
# decision a user makes, not something inferable from pixels. Saying so here is
# better than inventing a third case to make a table symmetrical.


def _satin_bar_design(angle: float):
    from test_cto_probes import _satin_bar

    from app.models.design import StitchType

    return _satin_bar(StitchType.SATIN, angle)


def test_probe4_an_unedited_satin_keeps_its_direction_through_a_forced_rebuild():
    """The counterpart P4 never had. P4 pins that an EDITED angle changes the
    stream; this pins that an UNEDITED one does not drift — the failure mode the
    v131 provenance short-circuit introduced a risk of, since it lets an
    untouched satin take the medial-axis path instead of the stored frame."""
    from test_cto_probes import _dominant_seg_angle

    from app.services.digitizer.provenance import object_params_hash

    d = _satin_bar_design(0.0)
    d.objects[0].params_hash = object_params_hash(d.objects[0])

    before = _dominant_seg_angle(rebuild_design(d.model_copy(deep=True), force=True))
    after = _dominant_seg_angle(rebuild_design(d.model_copy(deep=True), force=True))
    assert before == pytest.approx(after), "a forced rebuild is not deterministic"

    edited = d.model_copy(deep=True)
    edited.objects[0].stitch_angle = 77.0
    moved = _dominant_seg_angle(rebuild_design(edited))
    delta = abs(moved - before) % 180.0
    assert min(delta, 180.0 - delta) > 5.0, (
        f"a 77 degree angle edit moved the sewn direction by only "
        f"{min(delta, 180.0 - delta):.1f} degrees — P4's contract, on the "
        f"provenance path"
    )


@pytest.mark.parametrize("forced", [False, True])
def test_probe5_applique_emits_its_stops_on_both_rebuild_paths(forced):
    """Appliqué has no digitize path (see the note above), so 'all three paths'
    is two here. Both must pause the machine for the operator."""
    from test_cto_probes import _satin_bar

    from app.models.design import StitchType

    built = rebuild_design(_satin_bar(StitchType.APPLIQUE, 0.0), force=forced)
    stops = sum(1 for s in built.stitches if str(s.command) == "STOP")
    assert stops >= 2, (
        f"appliqué (force={forced}) emitted {stops} STOPs; the operator needs "
        f"one after placement and one after tackdown"
    )


def test_digitize_really_never_emits_applique():
    """Pin the claim above rather than asserting it in a comment. If digitize
    ever learns to classify appliqué, P5 gains a third path and this fails to
    say so."""
    import inspect

    from app.services.digitizer import pipeline

    src = inspect.getsource(pipeline)
    assert "APPLIQUE" not in src, (
        "pipeline.py now mentions APPLIQUE — if digitize can classify it, P5 "
        "needs a digitize path too"
    )


# ── the second CI lane, and the escape hatch it needs ────────────────────────
#
# `STITCHIQ_NO_REBUILD_PASSTHROUGH=1` runs the whole suite with the
# short-circuit off. Seven tests failed the first time it was switched on; five
# of them legitimately have the pass-through as their SUBJECT and now carry
# `@pytest.mark.needs_rebuild_passthrough`, and two were hiding real properties
# and were rewritten to ask them where they can fail.
#
# The marker is an escape hatch, and an escape hatch that nobody watches becomes
# the way every awkward test gets silenced. These two tests watch it.

ALLOWED_PASSTHROUGH_TESTS = {
    # the pass-through IS the assertion in each of these
    "test_probe6_an_unedited_design_passes_through_untouched",
    "test_the_passthrough_is_real_and_force_defeats_it",
    "test_unedited_rebuild_is_byte_identical",
    "test_recolour_and_rename_still_pass_through",
    "test_fingerprint_survives_a_json_round_trip",
    "test_fidelity_criterion_holds_verbatim",
}


def test_the_passthrough_marker_is_not_a_dumping_ground():
    """Every test carrying the skip marker must be on the list above, with a
    reason recorded in this file. Adding a marker to silence an inconvenient
    failure means editing this set, which is a visible act in review."""
    import ast

    here = Path(__file__).resolve().parent
    marked = set()
    for path in sorted(here.glob("test_*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                if "needs_rebuild_passthrough" in ast.unparse(dec):
                    marked.add(node.name)
    unexpected = marked - ALLOWED_PASSTHROUGH_TESTS
    assert not unexpected, (
        "these tests were excused from the no-pass-through lane without being "
        f"recorded: {sorted(unexpected)}. If the pass-through really is the "
        f"subject, add them to ALLOWED_PASSTHROUGH_TESTS with a reason; if not, "
        f"they are hiding a real failure."
    )
    stale = ALLOWED_PASSTHROUGH_TESTS - marked
    assert not stale, f"listed but no longer marked: {sorted(stale)}"


def test_ci_runs_the_no_passthrough_lane():
    """The lane only protects anything if CI actually runs it."""
    ci = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
    assert ci.is_file(), ci
    text = ci.read_text()
    assert "STITCHIQ_NO_REBUILD_PASSTHROUGH=1" in text, (
        "CI no longer runs the suite with the pass-through disabled — the "
        "probe-gaming class of defect can return unnoticed"
    )


def test_the_switch_actually_switches():
    """Guard the mechanism itself: with the variable set, an unedited rebuild
    must regenerate rather than pass through. Read straight from conftest so a
    renamed variable cannot leave the lane silently inert."""
    import conftest

    from app.services.digitizer import rebuild as rebuild_mod

    if conftest.NO_PASSTHROUGH:
        cv2.setRNGSeed(1234)
        dig = digitize_image(_ring_image(), "cotton", "100x100", 2)
        assert rebuild_design(dig) is not dig, (
            "the lane is set but rebuild still short-circuits"
        )
    else:
        assert rebuild_mod.rebuild_is_a_noop.__module__.endswith("provenance"), (
            "the pass-through is patched out in the DEFAULT lane — the normal "
            "suite is no longer testing shipped behaviour"
        )


def test_probe6_would_catch_the_step_minus_one_regression():
    """The regression that started all this — a travel resampler manufacturing
    70.8% of a fixture's stitches — must be outside every band. It was a 1.95x
    inflation on fixture 01 (17,078 against 8,749)."""
    band_hi = {s: hi for s, _c, _lo, hi, _m in FIDELITY_BANDS}
    assert 17078 / 8749 > band_hi["01_flat_2color_logo"]
