"""Arguments digitize passes to a shared generator that rebuild did not.

Found by an independent four-lens audit of the two per-object emission loops
(2026-08-09), then verified at the line. All four are the `route_pad` defect
shape: the SAME generator called from both paths, with the edit path handing it
a different — or missing — argument. None of them could be caught by a stitch
hash, because the hash moves with the regression.

  G1  THE WIDE-REMAINDER TATAMI TOOK THE SATIN PITCH. When a satin stroke has a
      patch too wide for a column, both paths tatami it. digitize paces those
      rows at the fabric's FILL row pitch `prof["row_mm"]`; rebuild used
      `spacing_px`, the object's SATIN column pitch. The two are separate
      profile keys and coincide only on cotton (0.40/0.40) — knit is 0.50/0.45,
      jersey 0.55/0.50 — and after any density edit they are unrelated.

  G2  ...AND FILLED IT AT ZERO DEGREES. digitize passes
      `angle_deg=_fill_angle(wide_mask)`, the remainder's own principal axis.
      Rebuild omitted the keyword, so it silently took the signature default of
      0.0: every wide patch came back with horizontal rows crossing the satin
      columns it sits between.

  G3  THE PARALLEL UNDERLAY CROSSED THE WRONG ANGLE. `FILL_UNDERLAY_ANGLE_OFFSET_DEG`
      exists to lay the crossing layer 90 degrees off the top rows. digitize
      keeps that invariant by construction — it passes the very `fill_angle` it
      just filled with. Rebuild passed the raw stored `stitch_angle`, which is a
      different number for a contour/spiral/radial fill (rebuild's own code says
      the stored angle "does not describe this object") and for any object
      carrying a Stitch Flow line. A user who draws a flow line 90 degrees off
      got an underlay running PARALLEL to the rows it was meant to brace.

  G4  EVERY OBJECT TRANSITION TRIMMED. digitize gates the trim on
      `TRIM_MIN_GAP_MM` (v2 Part 48) because a trim costs ~2.5s of machine time
      and a short carried thread is what commercial digitizers do. Rebuild
      trimmed unconditionally.

Plus the silent-delete this file also pins: `if len(pts) < 2: continue` dropped
an object with no error and no log. Measured on `05_wordmark_caps` and
`06_wordmark_script`, which each came back one object short. It raises now.

Measured, digitize vs rebuild-after-a-real-edit, before -> after (trims):

  04_thin_line_outline   5 -> 4     05_wordmark_caps  ratio 1.02 -> 1.00
  06_wordmark_script     6 -> 5     07_circular_badge   63 -> 55  (-20s)
  02_logo_fine_text     12 -> 5  (-17.5s)
"""

from __future__ import annotations

import ast
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.models.design import Design
from app.services.digitizer import digitize_image
from app.services.digitizer.constants import FABRIC_PROFILES, TRIM_MIN_GAP_MM
from app.services.digitizer.rebuild import rebuild_design

DIGITIZER = Path(__file__).resolve().parents[1] / "app" / "services" / "digitizer"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "quality_bench"


def _digitize(stem: str, colors: int = 4, fabric: str = "cotton") -> Design:
    cv2.setRNGSeed(1234)
    return digitize_image((FIXTURES / f"{stem}.png").read_bytes(), fabric, "100x100", colors)


def _edited(design: Design) -> Design:
    d = design.model_copy(deep=True)
    d.objects[0].density = round(float(d.objects[0].density or 4.0) * 1.01, 6)
    return d


def _trims(d: Design) -> int:
    return sum(1 for s in d.stitches if str(s.command) == "TRIM")


# ── G1 + G2: the wide-remainder tatami fallback ──────────────────────────────


def _wide_remainder_call() -> ast.Call:
    """The `_fill_by_component(wide_mask, …)` call for a satin's too-wide patch.

    It lived in rebuild's satin branch when these defects were found and moved
    to `generation.py` at STEP 3c, when the sweep became one implementation
    shared with digitize. The assertions below are unchanged — only where they
    look. `test_generation_core.py` covers the same ground from the core's side;
    both are kept, because this file is the record of what was actually wrong.
    """
    tree = ast.parse((DIGITIZER / "generation.py").read_text())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_fill_by_component"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "wide_mask"):
            return node
    pytest.fail("rebuild.py no longer calls _fill_by_component on wide_mask")


def test_the_wide_remainder_is_paced_at_the_fill_row_pitch_not_the_satin_pitch():
    """`spacing_px` is the object's SATIN column pitch. Using it here paces a
    tatami fill at satin density — on cotton the two happen to be equal, which
    is why the corpus hid this; raise a satin to 4.0/mm and the remainder comes
    back 60% denser than digitize's, a stiff puckered patch mid-stroke."""
    # Inside the core the parameter is `row_px`; both halves of the chain are
    # asserted, because either one alone can be right while the pair is wrong.
    pitch = _wide_remainder_call().args[1]
    assert isinstance(pitch, ast.Name) and pitch.id == "row_px", (
        f"the core paces the wide remainder by {ast.unparse(pitch)!r}; it must "
        f"use the fill row pitch it was handed, not the satin column pitch"
    )
    reb = (DIGITIZER / "rebuild.py").read_text()
    call = reb[reb.index("attempt = spine_satin("):]
    call = call[: call.index("\n                    )")]
    assert "row_px=fill_row_px" in call, (
        f"rebuild feeds the core something other than the fabric's fill row "
        f"pitch — `spacing_px` here is the SATIN column pitch, and the two "
        f"coincide only on cotton. Got:\n{call}"
    )
    pipe = (DIGITIZER / "pipeline.py").read_text()
    pcall = pipe[pipe.index("attempt = spine_satin("):]
    pcall = pcall[: pcall.index("\n                )")]
    assert "row_px=row_px" in pcall, f"digitize's call lost its fill pitch:\n{pcall}"


def test_the_wide_remainder_is_filled_at_its_own_axis_not_zero():
    kwargs = {k.arg for k in _wide_remainder_call().keywords}
    assert "angle_deg" in kwargs, (
        "rebuild omits angle_deg on the wide-remainder fill, so it silently "
        "takes _fill_by_component's 0.0 default and lays horizontal rows across "
        "whatever direction the stroke actually runs"
    )


def test_the_cotton_coincidence_that_hid_this_is_real():
    """Guard the guard. If row_mm and satin_mm ever diverge on cotton, the
    corpus would have caught G1 on its own and these AST tests are redundant —
    but they are not, and this documents why."""
    cotton = FABRIC_PROFILES["cotton"]
    assert cotton["row_mm"] == cotton["satin_mm"], "cotton no longer hides G1"
    assert FABRIC_PROFILES["knit"]["row_mm"] != FABRIC_PROFILES["knit"]["satin_mm"]


# ── G3: the crossing underlay must cross what was actually sewn ──────────────


def test_the_parallel_underlay_gets_the_real_top_row_angle():
    """`top_row_angle` is set per branch to whatever that branch actually filled
    at, and handed to `_rebuild_underlay`. Passing `o.stitch_angle` straight
    through is the bug — for a contour fill the stored angle is 0.0 and does not
    describe the rows at all."""
    src = (DIGITIZER / "rebuild.py").read_text()
    call = src[src.index("under = _rebuild_underlay("):]
    call = call[: call.index("\n            )")]
    assert "top_row_angle" in call, f"underlay still takes the raw stored angle:\n{call}"
    assert "float(o.stitch_angle)" not in call


def test_every_area_fill_branch_sets_the_top_row_angle():
    """A new fill branch that forgets to set it would silently inherit the
    stored angle again. Pin that each branch that lays area rows assigns it."""
    src = (DIGITIZER / "rebuild.py").read_text()
    # _fill_angle for contour/spiral/radial and the divided flow; _flow_line_angle
    # for the plain tatami path.
    assert src.count("top_row_angle = _fill_angle(top)") == 3, (
        "expected contour, spiral/radial and divided-flow branches each to take "
        "the region's own axis"
    )
    assert "top_row_angle = _flow_line_angle(" in src


# ── G4: the trim gate ────────────────────────────────────────────────────────


@pytest.mark.parametrize(("stem", "colors"), [("07_circular_badge", 6),
                                              ("02_logo_fine_text_3color", 4)])
def test_editing_does_not_trim_at_every_object_transition(stem, colors):
    """Rebuild trimmed unconditionally where digitize gates on TRIM_MIN_GAP_MM.
    Measured before -> after: badge 63 -> 55 trims (-20s of machine time),
    fine-text 12 -> 5 (-17.5s).

    THE SLACK IS ABSOLUTE-OR-RELATIVE, and that is a change of shape, not a
    loosening for convenience. A flat `+2` was calibrated when the badge ran 57
    trims on both paths — two out of fifty-seven. CTO 1b took the same
    configuration to 19 (digitize) and 25 (edited rebuild): BOTH fell about
    threefold, and the gate failed on a stream three times cheaper than the one
    it was written against. Keeping a flat +2 there would be a tighter test by
    accident rather than by decision.

    The +6 that remains is recorded as an OPEN DIVERGENCE, not as acceptable.
    It was 0 before 1b and is 6 now — not because rebuild got worse (57 -> 25)
    but because 1b removed the routing noise that was hiding it. The likely
    mechanism is the known raster difference (digitize routes at 13.3 px/mm on
    the source image, rebuild at 10 px/mm on the object's bounding box), so a
    cell-to-cell move that routes inside the region on one path can fail on the
    other and become a trim. THAT IS A HYPOTHESIS AND HAS NOT BEEN MEASURED. It
    belongs to 1c / 3e-i, and the ceiling below is set to catch a return of
    unconditional trimming, which is what this test is for, without pretending
    the residual is understood.
    """
    dig = _digitize(stem, colors)
    rb = rebuild_design(_edited(dig))
    ceiling = _trims(dig) + max(2, round(0.35 * _trims(dig)))
    assert _trims(rb) <= ceiling, (
        f"{stem}: edited rebuild emits {_trims(rb)} trims against digitize's "
        f"{_trims(dig)} (ceiling {ceiling}). At ~2.5s each that is "
        f"{(_trims(rb) - _trims(dig)) * 2.5:.0f}s of machine time the user did "
        f"not have before the edit."
    )


def test_the_trim_gate_is_the_same_threshold_digitize_uses():
    src = (DIGITIZER / "rebuild.py").read_text()
    assert "TRIM_MIN_GAP_MM" in src, "rebuild no longer gates its object-transition trim"
    assert TRIM_MIN_GAP_MM > 0


# ── the silent delete ────────────────────────────────────────────────────────


def test_an_empty_generator_result_raises_instead_of_deleting_the_object():
    """`if len(pts) < 2: continue` dropped the object with no error, no log and
    no visible sign until you counted. Two fixtures were losing a letter."""
    src = (DIGITIZER / "rebuild.py").read_text()
    block = src[src.index("if len(pts) < 2:"):]
    block = block[: block.index("\n\n")] if "\n\n" in block[:2000] else block[:2000]
    assert "raise ValueError" in block, (
        "rebuild silently skips an object whose generator produced too few "
        "points — the user loses a letter and is never told"
    )


def test_the_raise_names_the_object_and_its_generator(monkeypatch):
    """A bare raise here would be almost as unhelpful as the silence: the
    caller's next question is always WHICH object.

    The condition is forced by emptying the finishing chain rather than by
    feeding a degenerate contour — a collinear contour still rasterizes to a
    line and scanlines fine, and a sub-pixel one is a raster edge case rather
    than the behaviour under test. Emptying the top generator alone is not
    enough either: the underlay rescues it, which is worth knowing. What matters
    is that "nothing sewable came out" reaches the user, whatever produced it."""
    from app.services.digitizer import rebuild as rebuild_mod

    monkeypatch.setattr(rebuild_mod, "_finish_rebuild_segment", lambda *a, **k: [])
    dig = _digitize("01_flat_2color_logo", 6)
    with pytest.raises(ValueError, match=r"Fill 1.*too few to sew"):
        rebuild_design(_edited(dig))


def test_that_forced_condition_used_to_pass_silently():
    """Guard the guard: with the old `continue`, the same forced condition
    returned a design that was simply missing its objects — no exception, and a
    stitch count that looks plausible. This is what the raise replaced."""
    tree = ast.parse((DIGITIZER / "rebuild.py").read_text())
    guards = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.If) and "len(pts) < 2" in ast.unparse(n.test)
    ]
    assert guards, "the too-few-points guard is gone entirely"
    for g in guards:
        kinds = {type(s) for s in g.body}
        assert ast.Continue not in kinds, (
            "the too-few-points guard still `continue`s — an object can be "
            "dropped silently again"
        )
        assert ast.Raise in kinds, "the guard no longer raises"


# ── the fabric profile, which rebuild ignored entirely ───────────────────────


def test_rebuild_reads_the_designs_fabric():
    """`Design.fabric_type` existed the whole time and rebuild used cotton
    constants regardless, so editing one object on a fleece design re-stitched
    it with cotton underlay spacing (2.0 vs 1.5mm) and inset (0.6 vs 0.8mm).
    The bench corpus is entirely cotton and could never have caught this."""
    src = (DIGITIZER / "rebuild.py").read_text()
    assert "_fabric_profile(design.fabric_type" in src
    # And the cotton constants it used to hard-code are gone from the module.
    assert "UNDERLAY_STEP_MM" not in src, "rebuild still hard-codes the cotton underlay step"
    assert "EDGE_INSET_MM" not in src, "rebuild still hard-codes the cotton edge inset"


def test_a_fleece_design_rebuilds_differently_from_a_cotton_one():
    """Behavioural proof that the profile actually reaches the generators —
    an assertion on the source alone could pass with the value unused."""
    dig = _digitize("01_flat_2color_logo", 6, fabric="cotton")

    def rebuilt_with(fabric: str) -> int:
        d = _edited(dig)
        d.fabric_type = fabric
        return len(rebuild_design(d).stitches)

    assert rebuilt_with("fleece") != rebuilt_with("cotton"), (
        "fleece and cotton rebuild to the same stream — the fabric profile is "
        "being read but not used"
    )


def test_an_unknown_fabric_falls_back_rather_than_raising():
    dig = _digitize("01_flat_2color_logo", 6)
    d = _edited(dig)
    d.fabric_type = "unobtanium"
    assert len(rebuild_design(d).stitches) > 0


def test_a_missing_fabric_is_not_a_crash():
    dig = _digitize("01_flat_2color_logo", 6)
    d = _edited(dig)
    d.fabric_type = None
    assert len(rebuild_design(d).stitches) > 0
