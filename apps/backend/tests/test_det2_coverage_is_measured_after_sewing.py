"""Coverage counts thread, not intentions (DET2).

`emitted_mask` is the only record of which artwork the pipeline believes it
sewed. Two consumers read it: `uncovered_px`, which decides whether to re-trace
a photograph, and the element-level `lost_share`, which is what the user is told
about detail that did not make it. Both were being lied to.

The write sat in pass A, immediately after the minimum-area test — before any
generator had run. So it recorded "this region is worth sewing", filled to its
outer contour, and that stood in for "this region became thread". It counted:

  * the interior of every knocked-out hole, which no thread crosses; and
  * every region pass A accepted that pass B then abandoned — a feature thinner
    than the thread itself, a generator returning under two points, an empty
    fill.

Measured consequence, on the two fixtures that carry it:

  * 03_gradient_soft_subject — SH2 measured 11.96 % of the foreground owned by
    nobody while `uncovered_px` read 0.00 %. The corrected mask reads 13.32 %.
  * 04_thin_line_outline — the artwork's inner hairline ring is 0.21 mm wide,
    under `MIN_FEATURE_W_MM`, and is correctly skipped as unsewable. 55.9 mm²,
    a fifth of the drawing, silently vanished: `uncovered_px` read 2.42 % and no
    warning was emitted. It now reads 31.59 % and the user is told.

A coverage metric that cannot go down is not a metric. These tests pin the two
halves: the mask is written where the sewing happens, and a feature the pipeline
refuses to sew is reported as unsewn.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import cv2
import pytest

from app.services.digitizer import digitize_image, pipeline

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "quality_bench"
# The bench configuration for 04, restated rather than imported: `scripts/` is
# not on the path under pytest, and the point of the test is that THIS
# configuration produces this loss.
BENCH_04 = {"fabric_type": "cotton", "hoop_size": "100x100", "max_colors": 2}
RNG_SEED = 20260728  # scripts/run_quality_bench.py's pin, so the bench numbers apply


@pytest.fixture(scope="module")
def outline_run():
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image((FIXTURES / "04_thin_line_outline.png").read_bytes(), **BENCH_04)
    return design, float(pipeline._LAST_UNCOVERED_PX), list(pipeline._CLASSIFICATION_LOG)


def test_the_hairline_is_sewn_and_the_coverage_stays_honest(outline_run):
    """History of this assertion, because it changed subject twice for real
    reasons: before DET2 the pipeline reported 2.42 % uncovered and no warning
    while a fifth of the drawing was unsewn (the metric was lying). After DET2
    it reported 31.59 % WITH the too-small warning (the metric was honest, the
    refusal stood). After RS1 the ring is SEWN as a run, so the warning is gone
    BECAUSE THE ARTWORK IS NO LONGER LOST — the warning moved with the
    behaviour, which is what the DET2 rule requires of it.
    """
    design, uncovered, log = outline_run

    runs = [e for e in log if e["decision"] == "RUN"]
    assert runs, "expected the 0.21mm inner ring to be routed to a run (RS1)"
    assert all(e["reason"] == "sub_thread_run" for e in runs)
    assert any("Hairline" in o.name for o in design.objects)

    # Floors and ceilings, not the measured 16.69 %: the honest remainder is
    # anti-alias fringe and edge shaving, which must neither vanish (that would
    # be DET2's inflation back again) nor stay above the photographic-rescue
    # gate (04 is a drawing; the rescue firing on it was the wrong response).
    assert 0.05 <= uncovered < 0.19, (
        f"04's coverage reads {uncovered:.2%} — below 0.05 suggests the mask is "
        f"over-claiming again; at or above 0.19 the texture rescue misfires"
    )
    assert not any("too small or too faint" in w for w in design.warnings), (
        "the ring is sewn now; a loss warning for sewn artwork is a false claim"
    )


def test_the_coverage_mask_is_written_only_where_sewing_happens():
    """Structural, and deliberately not a string match.

    An earlier test in this repo pinned a defect as contract by asserting on the
    literal source text of the line it was meant to guard. This asserts the
    property instead: every mutation of `emitted_mask` inside `digitize_image`
    lies within pass B's loop over the planned clusters. Pass A may not touch
    it, whatever the mutation is spelled like.
    """
    tree = ast.parse(inspect.getsource(pipeline))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "digitize_image")

    pass_b = next(
        n for n in ast.walk(fn)
        if isinstance(n, ast.For) and isinstance(n.iter, ast.Attribute)
        and n.iter.attr == "clusters" and isinstance(n.iter.value, ast.Name)
        and n.iter.value.id == "plan"
    )
    lo, hi = pass_b.lineno, max(d.lineno for d in ast.walk(pass_b) if hasattr(d, "lineno"))

    def _is_mask(node) -> bool:
        return isinstance(node, ast.Name) and node.id == "emitted_mask"

    mutations = []
    for node in ast.walk(fn):
        # `emitted_mask[...] = ...`
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and _is_mask(t.value):
                    mutations.append(node.lineno)
                elif _is_mask(t) and node.lineno > pass_b.lineno:
                    mutations.append(node.lineno)  # rebinding it inside pass B
        # `cv2.drawContours(emitted_mask, ...)` and friends — OpenCV writes into
        # its first argument in place.
        if isinstance(node, ast.Call) and node.args and _is_mask(node.args[0]):
            mutations.append(node.lineno)

    assert mutations, "no write to emitted_mask found — has it been renamed?"
    early = [ln for ln in mutations if not lo <= ln <= hi]
    assert not early, (
        f"emitted_mask is written outside pass B (lines {early}; pass B spans "
        f"{lo}-{hi}). Coverage recorded before the generators run counts regions "
        f"that were never sewn — that is the DET2 defect."
    )
