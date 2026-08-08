"""Competitor benchmark + training-data pipeline (v2 Part 64).

What must hold for the pipeline to be trustworthy:

1. stream metrics are exact on a hand-built stream;
2. block splitting and the run/satin/fill inference recover the TRUE types of
   STITCHIQ's own generators after a DST round trip — the one population where
   ground truth is known, which is what calibrates the heuristic;
3. every extracted training row passes the schema and carries a declared
   provenance; machine-file rows are marked inferred, with unobservable fields
   null rather than guessed;
4. the benchmark case runner produces the honest shape: fixture cases have no
   competitor numbers, machine-file cases no STITCHIQ numbers.
"""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

from bench_competitor import (
    block_features,
    infer_block_type,
    run_case,
    split_blocks,
    stream_metrics,
)
from extract_training_rows import (
    rows_from_machine_file,
    rows_from_stitchiq,
    validate_row,
)

from app.models.design import (
    ColorStop,
    ConnectMethod,
    Design,
    DesignObject,
    Point,
    Stitch,
    StitchType,
    UnderlayType,
)
from app.services.digitizer import rebuild_design
from app.services.embroidery_io import read_embroidery, write_embroidery


def _obj(seq, contour, st, angle=0.0, density=2.0):
    return DesignObject(
        sequence_order=seq, name=f"o{seq}", stitch_type=st, color_stop=1,
        density=density, stitch_angle=angle, underlay_type=UnderlayType.NONE,
        pull_compensation=0.0, connect_method=ConnectMethod.TRIM,
        stitch_count=0, contour=contour,
    )


def _known_types_design() -> Design:
    """A run path, a narrow satin bar and a broad tatami rect — truth known."""
    run = [Point(x=0, y=0), Point(x=30, y=0), Point(x=30, y=18), Point(x=0, y=18)]
    satin = [Point(x=40, y=0), Point(x=43, y=0), Point(x=43, y=25), Point(x=40, y=25)]
    fill = [Point(x=50, y=0), Point(x=80, y=0), Point(x=80, y=25), Point(x=50, y=25)]
    return Design(
        name="t", width_mm=80, height_mm=25, stitch_count=0, version=1,
        status="digitized",
        color_stops=[ColorStop(stop_number=1, thread_brand="M", catalog_number="1",
                               thread_name="a", hex="#223344", stitch_count=0)],
        objects=[_obj(1, run, StitchType.RUNNING_SINGLE),
                 # angle 90 = the bar's true column axis (it is vertical).
                 # 0.0 was fine while rebuild ignored the field; since CTO A5
                 # honors it, 0 would walk ACROSS the bar and sew 25mm rungs
                 # that classify as fill — the exact no-op this fixture
                 # predates.
                 _obj(2, satin, StitchType.SATIN, angle=90.0, density=4.0),
                 _obj(3, fill, StitchType.TATAMI)],
        stitches=[],
    )


# ── stream metrics ────────────────────────────────────────────────────────────


def test_stream_metrics_are_exact_on_a_hand_built_stream():
    d = Design(
        name="s", width_mm=10, height_mm=10, stitch_count=3, version=1, status="draft",
        color_stops=[], objects=[],
        stitches=[
            Stitch(x=0, y=0, command="STITCH"),
            Stitch(x=3, y=4, command="STITCH"),     # 5mm stitch, not travel
            Stitch(x=3, y=4, command="TRIM"),
            Stitch(x=6, y=8, command="JUMP"),       # 5mm jump
            Stitch(x=6, y=8, command="COLOR_CHANGE"),
            Stitch(x=9, y=12, command="JUMP"),      # 5mm jump
            Stitch(x=9, y=12, command="STITCH"),
            Stitch(x=9, y=12, command="END"),
        ],
    )
    m = stream_metrics(d)
    assert m["stitch_count"] == 3
    assert m["trim_count"] == 1
    assert m["jump_count"] == 2
    assert abs(m["jump_travel_mm"] - 10.0) < 1e-6
    assert m["color_stop_count"] == 2


def test_blocks_split_at_trims_and_color_changes_not_at_jumps():
    d = Design(
        name="s", width_mm=10, height_mm=10, stitch_count=6, version=1, status="draft",
        color_stops=[], objects=[],
        stitches=[
            Stitch(x=0, y=0, command="STITCH"), Stitch(x=1, y=0, command="STITCH"),
            Stitch(x=5, y=0, command="JUMP"),   # in-block travel: no split
            Stitch(x=5, y=0, command="STITCH"), Stitch(x=6, y=0, command="STITCH"),
            Stitch(x=6, y=0, command="TRIM"),
            Stitch(x=0, y=5, command="STITCH"), Stitch(x=1, y=5, command="STITCH"),
            Stitch(x=1, y=5, command="COLOR_CHANGE"),
            Stitch(x=0, y=9, command="STITCH"), Stitch(x=1, y=9, command="STITCH"),
        ],
    )
    blocks = split_blocks(d)
    assert [len(b) for b in blocks] == [4, 2, 2]


# ── the inference, calibrated where truth is known ────────────────────────────


def test_inference_recovers_generator_truth_after_a_dst_round_trip():
    built = rebuild_design(_known_types_design())
    imported = read_embroidery(write_embroidery(built, "dst"), "dst")
    inferred = [infer_block_type(block_features(b)) for b in split_blocks(imported)]
    # Underlay-free run, satin bar and tatami rect come back as themselves.
    assert "run" in inferred, f"no run recovered: {inferred}"
    assert "satin" in inferred, f"no satin recovered: {inferred}"
    assert "fill" in inferred, f"no fill recovered: {inferred}"


def test_satin_zigzag_has_high_reversal_rate():
    zig = []
    for i in range(40):
        zig.append((i * 0.5, 0.0 if i % 2 else 3.0))
    f = block_features(zig)
    assert f["reversal_rate"] > 0.6
    assert infer_block_type(f) == "satin"


def test_a_sparse_path_reads_as_run():
    path = [(i * 2.5, 40.0 + (i % 3)) for i in range(30)]
    f = block_features(path)
    assert infer_block_type(f) == "run"


# ── training rows ─────────────────────────────────────────────────────────────


def test_stitchiq_rows_validate_and_carry_generated_provenance():
    built = rebuild_design(_known_types_design())
    rows = rows_from_stitchiq(built, "unit", artwork_path=None)
    assert len(rows) == 3
    for r in rows:
        assert validate_row(r) == []
        assert r["provenance"] == "stitchiq_generated"
        assert r["decision_provenance"] == "stitchiq_generated"
        assert r["label"] is None
        assert r["source"]["contour_mm"]  # STITCHIQ rows keep the outline


def test_machine_file_rows_are_marked_inferred_with_nulls_not_guesses():
    built = rebuild_design(_known_types_design())
    imported = read_embroidery(write_embroidery(built, "dst"), "dst")
    rows = rows_from_machine_file(imported, "unit-dst", Path("unit.dst"))
    assert rows
    for r in rows:
        assert validate_row(r) == []
        assert r["provenance"] == "machine_file_inference"
        assert r["source"]["contour_mm"] is None
        assert r["source"]["hole_count"] is None
        assert r["decision"]["density"] is None
        assert r["decision"]["underlay"] is None


def test_schema_rejects_missing_provenance_and_stray_labels():
    built = rebuild_design(_known_types_design())
    row = rows_from_stitchiq(built, "unit", artwork_path=None)[0]
    bad = dict(row)
    bad["provenance"] = "guessed"
    assert validate_row(bad)
    bad2 = dict(row)
    bad2["label"] = {"stitch_type": "SATIN"}  # label without human provenance
    assert validate_row(bad2)


# ── the case runner's honest shape ────────────────────────────────────────────


def test_machine_file_case_has_competitor_side_only(tmp_path):
    r = run_case({"id": "unit-dst", "kind": "machine_file",
                  "file": BACKEND_ROOT / "tests/fixtures/sample.dst"},
                 out_dir=tmp_path)
    assert r["stitchiq"] is None
    assert r["competitor"]["stitch_count"] > 0
    assert r["competitor"]["provenance"] == "machine_file_inference"
    assert r["notes"]


def test_missing_input_becomes_a_note_not_a_crash():
    r = run_case({"id": "gone", "kind": "machine_file",
                  "file": BACKEND_ROOT / "does-not-exist.dst"})
    assert r["stitchiq"] is None and r["competitor"] is None
    assert any("SKIPPED" in n for n in r["notes"])
