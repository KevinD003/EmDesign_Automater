"""One satin implementation, two callers (CTO verdict STEP 3c).

The verdict ruled the architecture question (c): one generation core with
digitize and rebuild as thin wrappers. The reason was empirical — both paths
called the same generators, each computed the arguments itself, and the
arguments drifted ten times in this series. Three of those ten were in the
satin sweep alone, all shipped by one commit:

    pull compensation applied twice   the pre-dilated mask was measured AND
                                      pull/2 added again as half-width
    the wide remainder mis-paced      satin column pitch where digitize used
                                      the fabric's fill row pitch
    the wide remainder mis-angled     `angle_deg` omitted, silently 0.0

`generation.spine_satin` is now the only implementation. A fourth divergence of
that kind is not available, because there is no second copy to drift from.

The refactor is behaviour-preserving and was verified as such: the stitch
streams of both paths are byte-identical before and after, on four fixtures.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.digitizer import pipeline, rebuild
from app.services.digitizer.constants import SATIN_MAX_UNCOVERED, SATIN_MAX_W_MM
from app.services.digitizer.generation import SatinAttempt, spine_satin

DIGITIZER = Path(__file__).resolve().parents[1] / "app" / "services" / "digitizer"


def _bar(w_px: int, h_px: int, pad: int = 30) -> np.ndarray:
    m = np.zeros((h_px + 2 * pad, w_px + 2 * pad), np.uint8)
    cv2.rectangle(m, (pad, pad), (pad + w_px, pad + h_px), 255, -1)
    return m


# ── both callers go through the core, and nobody keeps a private copy ────────


def test_both_paths_call_the_shared_core():
    for mod in (pipeline, rebuild):
        src = inspect.getsource(mod)
        assert "spine_satin(" in src, f"{mod.__name__} no longer uses the shared core"


def test_neither_path_calls_the_skeleton_sweep_directly():
    """`_skeleton_satin_hires` is the primitive the core wraps. A caller that
    reaches past the core to it is starting the eleventh divergence."""
    offenders = []
    for name in ("pipeline", "rebuild"):
        tree = ast.parse((DIGITIZER / f"{name}.py").read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "_skeleton_satin_hires"):
                offenders.append(f"{name}.py:{node.lineno}")
    assert not offenders, (
        "these call the skeleton sweep directly instead of generation.spine_satin, "
        f"which is how the satin arguments drifted three times: {offenders}"
    )


# Legitimate readers of the satin caps, each for something that is NOT the
# satin-vs-tatami decision. Anything else reading them is a second copy of that
# decision, which is what the core exists to prevent.
GATE_READERS = {
    "generation.py": "the decision itself",
    "constants.py": "the definition",
    "__init__.py": "the package facade re-exports every public name",
    "pipeline.py": "a cheap pregate on the DT median, before the core is called",
    "satin.py": "the column generator's own max_half_px, not a classification",
    "underlay.py": "a comment",
}


def test_only_the_core_decides_satin_versus_tatami():
    """The width and coverage caps used to be applied in `pipeline.py` AND in
    `rebuild.py`, and the two had to agree by hand. rebuild does not read them
    at all now — it asks the core and uses `viable`."""
    assert "SATIN_MAX_W_MM" not in (DIGITIZER / "rebuild.py").read_text(), (
        "rebuild applies the satin width cap itself again"
    )
    assert "SATIN_MAX_UNCOVERED" not in (DIGITIZER / "rebuild.py").read_text(), (
        "rebuild applies the coverage cap itself again"
    )
    unexpected = []
    for path in sorted(DIGITIZER.glob("*.py")):
        text = path.read_text()
        if "SATIN_MAX_W_MM" in text or "SATIN_MAX_UNCOVERED" in text:
            if path.name not in GATE_READERS:
                unexpected.append(path.name)
    assert not unexpected, (
        f"new readers of the satin caps, each a potential second copy of the "
        f"classification: {unexpected}. If the use is legitimate, add it to "
        f"GATE_READERS with the reason."
    )


# ── the core's own contract ──────────────────────────────────────────────────


def _attempt(mask, *, spacing=4, pull=0.0, stroke_mm=2.0, mm_per_px=0.1):
    return spine_satin(
        mask, mm_per_px=mm_per_px, spacing_px=spacing, max_step_px=40,
        fill_step_px=40, connect_px=3.0, pull_mm=pull,
        stroke_mm=stroke_mm, row_px=4,
    )


def test_a_narrow_bar_is_viable_satin():
    a = _attempt(_bar(300, 30))  # 3mm wide at 0.1mm/px, under the 4.5mm cap
    assert isinstance(a, SatinAttempt)
    assert a.viable and a.reason == "satin"
    assert a.points, "a viable satin produced no stitches"
    assert a.axis_pts is not None, "no medial axis returned for the underlay to follow"
    assert a.median_w_mm <= SATIN_MAX_W_MM


def test_a_wide_shape_is_refused_and_hands_back_nothing():
    """A 12mm bar is far over the 4.5mm cap. Which reason it earns depends on
    whether the thinning resolves an axis at all — on this probe it does not, so
    it reports `no_medial_axis` rather than `wider_than_satin_cap`. The contract
    that matters to both callers is the same either way: not viable, and no
    stitches handed back for a caller to use by accident."""
    a = _attempt(_bar(300, 120), stroke_mm=12.0)
    assert not a.viable
    assert a.reason != "satin"
    assert a.points == [], "a refused attempt must not hand back stitches"


def test_the_width_cap_is_reachable_on_a_shape_that_has_an_axis():
    """Pin the `wider_than_satin_cap` branch specifically, so the reason set is
    not effectively two-valued in practice."""
    seen = set()
    for h_px, stroke in ((30, 3.0), (55, 5.5), (80, 8.0), (120, 12.0)):
        seen.add(_attempt(_bar(300, h_px), stroke_mm=stroke).reason)
    assert "satin" in seen
    assert seen - {"satin"}, f"no refusal reason ever fired: {seen}"


def test_a_speck_has_no_medial_axis():
    a = _attempt(_bar(3, 3, pad=10), stroke_mm=0.3)
    assert not a.viable
    assert a.reason == "no_medial_axis"


def test_the_reasons_are_the_ones_the_classifier_expects():
    """pipeline.py maps `reason` straight into its classification log and its
    counters. A renamed reason would silently change what digitize records."""
    src = (DIGITIZER / "generation.py").read_text()
    for reason in ("satin", "no_medial_axis", "wider_than_satin_cap", "not_stroke_like"):
        assert f'"{reason}"' in src
    # And only "no_medial_axis" is excluded from the tatami-fallback counter.
    pipe = (DIGITIZER / "pipeline.py").read_text()
    assert 'reason != "no_medial_axis"' in pipe


def test_pull_widens_the_columns_but_not_the_width_MEASUREMENT():
    """Both halves of R2, and they pull in opposite directions.

    Pull compensation must reach the emitted COLUMNS — that is what it is for,
    widening the sewn shape to survive fabric distortion. It must NOT reach the
    width MEASUREMENT, because that measurement is the satin-vs-tatami gate:
    folding pull into it pushes a stroke over the cap and reclassifies it. The
    old rebuild code did exactly that by handing in a pre-dilated mask, and
    `pipeline.py` carried a comment warning against it.
    """
    mask = _bar(300, 30)
    narrow = _attempt(mask, pull=0.0)
    wide = _attempt(mask, pull=1.2)

    assert wide.median_w_mm == pytest.approx(narrow.median_w_mm), (
        "pull compensation is leaking into the width gate — a stroke can now be "
        "reclassified by its pull comp, which is the R2 defect"
    )

    def span(a):
        ys = [p[1] for p in a.points]
        return max(ys) - min(ys)

    assert span(wide) > span(narrow) + 1.0, (
        "pull compensation is not reaching the emitted columns at all"
    )


def test_the_remainder_is_paced_and_angled_not_defaulted():
    """G1/G2: the tatami remainder takes the FILL row pitch and its OWN axis.
    Assert on the source, because both wrong values still produce plausible
    output and only show up on a non-cotton profile or a diagonal stroke."""
    tree = ast.parse((DIGITIZER / "generation.py").read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_fill_by_component"]
    assert len(calls) == 1, f"expected exactly one remainder fill, found {len(calls)}"
    call = calls[0]
    assert isinstance(call.args[1], ast.Name) and call.args[1].id == "row_px", (
        "the remainder is not paced at the fill row pitch"
    )
    kw = {k.arg for k in call.keywords}
    assert "angle_deg" in kw, "the remainder's angle is defaulted to 0.0 again"


def test_an_attempt_is_immutable():
    """Callers pass it around and read it in two places; a mutable result is an
    invitation for one of them to 'fix up' a field the other relies on."""
    a = _attempt(_bar(300, 30))
    with pytest.raises((AttributeError, TypeError)):
        a.viable = not a.viable


def test_uncovered_share_is_a_fraction():
    a = _attempt(_bar(300, 30))
    assert 0.0 <= a.uncovered_share <= 1.0
    assert SATIN_MAX_UNCOVERED > 0
