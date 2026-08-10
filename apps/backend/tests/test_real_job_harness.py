"""The instrument for real artwork, tested before the artwork exists.

A harness that has never run cannot be trusted on the day the first real job pair
lands — and that day is the worst possible time to discover that its difference
image was measuring an offset, or that its ink test called the whole canvas ink.
Both of those were real bugs in the first version of `_render_pair`, found by its
own self-test, and both are pinned below.

WHAT THIS DELIBERATELY DOES NOT TEST: whether our output is good. There is no
real artwork yet, nothing here is tuned against any, and the harness reports
differences without grading them. These tests check that the instrument reads
correctly, nothing more.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND / "scripts"))

from compare_expert import _blocks, _design_metrics, _match_blocks, _render_pair, compare
from real_jobs import DEFAULT_PARAMS, TIER, RealJobError, load_jobs

from app.services.digitizer import digitize_image


@pytest.fixture(scope="module")
def badge():
    from run_quality_bench import RNG_SEED

    cv2.setRNGSeed(RNG_SEED)
    return digitize_image(
        (BACKEND / "tests" / "fixtures" / "quality_bench" / "07_circular_badge.png")
        .read_bytes(), "cotton", "100x100", 6,
    )


# ── the loader keeps real jobs out of the corpus100 tiers ────────────────────


def test_the_real_tier_cannot_be_averaged_into_corpus100():
    """`corpus100`'s own docstring warns that a tier-C average must never be read
    as a real-world score. Real job pairs are the only material that can answer
    "is this competitive", so they must not share a tier label with anything."""
    corpus_tiers = {"A-real", "B-real-derived", "C-parametric"}
    assert TIER not in corpus_tiers, f"{TIER} collides with a corpus100 tier"


def test_an_empty_root_is_a_normal_state(tmp_path):
    """The instrument ships before the material. No jobs is not an error."""
    assert load_jobs(tmp_path) == []
    assert load_jobs(tmp_path / "does-not-exist") == []


def test_half_a_pair_is_an_error_not_a_skip(tmp_path):
    """The failure mode `build_corpus100.py` just had: a source goes missing and
    the corpus silently becomes a different, smaller corpus."""
    job = tmp_path / "artwork-only"
    job.mkdir()
    (job / "artwork.png").write_bytes(b"not really a png")
    with pytest.raises(RealJobError, match="no machine file"):
        load_jobs(tmp_path)

    other = tmp_path / "expert-only"
    other.mkdir()
    (other / "expert.dst").write_bytes(b"")
    (job / "expert.dst").write_bytes(b"")
    with pytest.raises(RealJobError, match="no artwork file"):
        load_jobs(tmp_path)


def test_two_artworks_in_one_job_is_ambiguous(tmp_path):
    job = tmp_path / "two"
    job.mkdir()
    (job / "a.png").write_bytes(b"")
    (job / "b.png").write_bytes(b"")
    (job / "expert.dst").write_bytes(b"")
    with pytest.raises(RealJobError, match="artwork files"):
        load_jobs(tmp_path)


def test_an_unknown_job_json_key_is_refused(tmp_path):
    """Silently ignoring a key means a job digitized at settings its own metadata
    says it was not — and the numbers would be filed under those settings."""
    job = tmp_path / "j"
    job.mkdir()
    (job / "artwork.png").write_bytes(b"")
    (job / "expert.dst").write_bytes(b"")
    (job / "job.json").write_text(json.dumps({"fabrik": "fleece"}))
    with pytest.raises(RealJobError, match="unknown keys"):
        load_jobs(tmp_path)


def test_job_json_overrides_only_what_it_names(tmp_path):
    job = tmp_path / "j"
    job.mkdir()
    (job / "artwork.png").write_bytes(b"")
    (job / "expert.dst").write_bytes(b"")
    (job / "job.json").write_text(json.dumps({"fabric": "fleece", "notes": "knit polo"}))
    [j] = load_jobs(tmp_path)
    assert j.params["fabric"] == "fleece"
    assert j.params["hoop"] == DEFAULT_PARAMS["hoop"]
    assert j.notes == "knit polo"
    assert j.tier == TIER


# ── the comparison reads correctly ──────────────────────────────────────────


def test_comparing_a_design_with_itself_reports_nothing(badge):
    """Any non-zero here is a bug in the harness, not a finding about stitching.
    It is the only check that can distinguish the two."""
    res = compare(badge, badge, "identity")
    nonzero = {k: v for k, v in res["design"].items() if v["delta"] != 0}
    assert not nonzero, f"identity comparison reported differences: {nonzero}"

    m = res["blocks"]
    assert not m["ours_unmatched"] and not m["expert_unmatched"]
    assert m["matched"], "no blocks matched at all"
    for p in m["matched"]:
        assert p["stitch_delta"] == 0
        assert p["colour_distance"] == 0.0


def test_blocks_come_from_the_stream_not_from_objects(badge):
    """The expert side has NO objects — a DST carries none and a PES carries
    colour blocks only. A block reader that consulted `design.objects` would work
    on our design and return nothing on theirs, which is the whole reason the
    per-object comparison was abandoned."""
    import ast
    import inspect
    import textwrap

    import compare_expert

    # On the AST, not on the source text: the first version of this test matched
    # the substring ".objects" and failed on the function's own DOCSTRING, which
    # explains why objects are not used. A prose mention is not an access.
    tree = ast.parse(textwrap.dedent(inspect.getsource(compare_expert._blocks)))
    reads = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "objects" not in reads, (
        "block extraction reads design.objects, which the expert side does not have"
    )
    assert "stitches" in reads, "block extraction does not read the stream"
    assert _blocks(badge), "no blocks extracted from a design that has four"


def test_a_removed_block_is_seen(badge):
    """The instrument must report a difference that is really there."""
    from measure_stitch_quality import _cmd

    limit = len(_blocks(badge)) - 1
    kept, seen = [], 0
    for s in badge.stitches:
        if _cmd(s) == "COLOR_CHANGE":
            seen += 1
            if seen >= limit:
                break
        kept.append(s)
    short = badge.model_copy(deep=True)
    short.stitches = kept
    short.color_stops = list(badge.color_stops)[:limit]

    res = compare(short, badge, "one block removed")
    assert res["design"]["stitches"]["delta"] < 0
    assert res["design"]["colour_blocks"]["delta"] < 0
    assert res["blocks"]["expert_unmatched"], "the removed block was not reported"


def test_machine_minutes_matches_the_bench_formula(badge):
    """The headline the series is graded on. Recomputed from the bench's OWN
    constant rather than trusting that two files agree — they have drifted before,
    and a harness reporting a different minute than the bench is worse than one
    reporting none."""
    from run_quality_bench import TRIM_SECONDS

    m = _design_metrics(badge)
    expected = round(m["est_minutes"] + m["trims"] * TRIM_SECONDS / 60.0, 2)
    assert m["machine_minutes"] == expected


# ── the difference image, where both bugs were ──────────────────────────────


def test_ink_is_measured_against_the_fabric_not_against_white(tmp_path, badge):
    """BUG 1, pinned. The canvas is FABRIC_BGR (222, 228, 232) — every channel
    below 250 — so an ink test of `< 250` calls the entire canvas ink and the
    difference image is uniformly 'both'. Two identical designs must share every
    ink pixel and have none unique to either."""
    r = _render_pair(badge, badge, tmp_path / "same.png")
    assert r["ours_only_px"] == 0 and r["expert_only_px"] == 0
    assert r["both_px"] > 0, (
        "no ink detected at all — the ink test is not seeing the thread"
    )
    sheet = cv2.imread(str(tmp_path / "same.png"))
    assert sheet is not None and sheet.size > 0


def test_a_pure_translation_is_not_reported_as_a_difference(tmp_path, badge):
    """BUG 2, pinned, and the one that cost a wrong decision.

    Registering the two renders on ABSOLUTE millimetres is the obvious move and
    is wrong here: a DST stores coordinates relative to its own origin, so where
    an expert placed the design in the hoop is a property of their file, not of
    their stitching. Measured on a shared mm frame, translating this fixture 7mm
    produced 23.6% disagreement — the outline drawn twice, a picture of nothing.

    Aligned on content, the same translation must vanish.
    """
    moved = badge.model_copy(deep=True)
    for s in moved.stitches:
        s.x += 7.0
        s.y += 3.0

    r = _render_pair(badge, moved, tmp_path / "shifted.png")
    total = r["both_px"] + r["ours_only_px"] + r["expert_only_px"]
    disagree = (r["ours_only_px"] + r["expert_only_px"]) / max(total, 1)
    assert disagree < 0.02, (
        f"a pure translation produced {disagree:.1%} disagreement — the renders "
        f"are being registered on absolute coordinates, which are not comparable "
        f"between our design and a machine file"
    )


def test_a_real_shape_difference_still_shows(tmp_path, badge):
    """Guard the guard. Content alignment must not be so forgiving that it hides
    the differences the harness exists to find — otherwise the test above is
    satisfied by an image that always agrees."""
    from measure_stitch_quality import _cmd

    limit = len(_blocks(badge)) - 1
    kept, seen = [], 0
    for s in badge.stitches:
        if _cmd(s) == "COLOR_CHANGE":
            seen += 1
            if seen >= limit:
                break
        kept.append(s)
    short = badge.model_copy(deep=True)
    short.stitches = kept
    short.color_stops = list(badge.color_stops)[:limit]

    r = _render_pair(short, badge, tmp_path / "missing.png")
    assert r["expert_only_px"] > 0, (
        "a whole colour block was removed and the difference image shows nothing"
    )


def test_the_difference_image_is_three_panels(tmp_path, badge):
    r = _render_pair(badge, badge, tmp_path / "sheet.png")
    sheet = cv2.imread(str(tmp_path / "sheet.png"))
    assert sheet.shape[1] > 2 * sheet.shape[0] // 2, "expected ours | expert | diff"
    assert "difference" in r["layout"]


# ── block matching ──────────────────────────────────────────────────────────


def test_blocks_match_by_colour_before_position():
    """An expert splitting one colour across two blocks where we used one is a
    real and expected difference; a navy block matched to a gold one is not."""
    navy = {"index": 0, "stitches": 100, "x_mm": 0, "y_mm": 0, "w_mm": 10, "h_mm": 10,
            "hex": "#142850"}
    gold = {"index": 1, "stitches": 50, "x_mm": 0, "y_mm": 0, "w_mm": 10, "h_mm": 10,
            "hex": "#dcaa28"}
    # Same geometry, swapped order: colour must decide, not position.
    m = _match_blocks([gold, navy], [navy, gold])
    by_expert = {p["expert_index"]: p for p in m["matched"]}
    assert by_expert[0]["ours_hex"] == "#142850"
    assert by_expert[1]["ours_hex"] == "#dcaa28"
    assert not m["ours_unmatched"] and not m["expert_unmatched"]


def test_an_extra_expert_block_is_reported_not_dropped():
    a = {"index": 0, "stitches": 100, "x_mm": 0, "y_mm": 0, "w_mm": 10, "h_mm": 10,
         "hex": "#142850"}
    b = {"index": 1, "stitches": 40, "x_mm": 20, "y_mm": 0, "w_mm": 5, "h_mm": 5,
         "hex": "#dcaa28"}
    m = _match_blocks([a], [a, b])
    assert m["expert_unmatched"] == [1], (
        '"the expert used a colour we did not" is exactly what this must surface'
    )


def test_matching_survives_a_missing_hex():
    """An imported machine file need not carry a usable colour for every block."""
    a = {"index": 0, "stitches": 10, "x_mm": 0, "y_mm": 0, "w_mm": 1, "h_mm": 1,
         "hex": None}
    m = _match_blocks([a], [dict(a, stitches=12)])
    assert len(m["matched"]) == 1
    assert m["matched"][0]["stitch_delta"] == -2


def test_no_thresholds_are_baked_into_the_harness():
    """It reports differences; deciding which are defects needs the real pairs,
    and they have not arrived. A pass/fail here would be tuned against nothing."""
    import inspect

    import compare_expert

    src = inspect.getsource(compare_expert)
    for word in ("PASS", "FAIL_IF", "TOLERANCE", "MAX_DELTA"):
        assert word not in src, f"a grading threshold ({word}) crept into the harness"


def test_coverage_is_run_over_both_streams(badge):
    """Our coverage measure was built to grade our stitching. Pointing it at a
    professional's file is the only way to learn what it reads on work that is
    known to be good — so it must be computed for the expert side too."""
    res = compare(badge, badge, "identity")
    assert res["coverage"]["ours"], "no coverage measured for our side"
    assert res["coverage"]["expert"], "coverage was not run over the expert stream"
    assert res["coverage"]["ours"] == res["coverage"]["expert"]


def test_a_numpy_array_never_reaches_the_json(badge, tmp_path):
    """The result is written with `json.dumps`; a stray numpy scalar raises there
    and would only be discovered on the first real job."""
    res = compare(badge, badge, "identity", render_to=tmp_path / "s.png")
    json.dumps(res)  # must not raise


def test_pixel_counts_are_plain_ints(badge, tmp_path):
    r = _render_pair(badge, badge, tmp_path / "s.png")
    for k in ("ours_only_px", "expert_only_px", "both_px"):
        assert isinstance(r[k], int) and not isinstance(r[k], np.integer)
