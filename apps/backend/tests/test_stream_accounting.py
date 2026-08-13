"""Every entry in the stream has exactly one source (INSTRUMENT-2).

The starting point was a claim: "90 penetrations on fixture 08 belong to no
object; they are lock stitches." The number came from subtracting
`sum(object.stitch_count)` from `design.stitch_count`, and **that subtraction is
not well formed**. The operands live in different spaces:

  * `object.stitch_count` is `len(stitches) - obj_start` — a STREAM SPAN. It
    counts the JUMPs and TRIMs emitted inside that object, and it is fixed
    before `_lock_stream` runs, so it excludes every tie-off.
  * `design.stitch_count` counts STITCH entries alone, after locking.

Their difference is not a count of unattributed penetrations. It has no
referent, and the explanation attached to it was never testable.

## What would make each of these fail

The first version of this file shipped four "identities", three of which could
not say no — a check that cannot fail reads in the diff as a safety assertion
and is worse than no check. Each test below names the input that breaks it. If
one cannot be named, it is not an identity and does not belong here.

| test | falsified by |
| --- | --- |
| stream entries decompose | any emission site that appends outside a span and outside the five named categories — the state before `merge_inserted` and `linework_lead_in` were found |
| penetrations decompose | any code path appending a STITCH between objects, or a lock recipe that stops emitting three-point ties |
| the merge adds no penetrations | a merge that inserts a STITCH rather than a JUMP; measured against `census_pre_merge`, which is why that census is stored |
| the census describes the returned stream | any mutation of `stitches` after the census is taken — a new post-lock pass would go unaccounted |
| no unrecognised commands | a new `StitchType`/command reaching the stream; `_stream_census` counts it into `other` instead of silently absorbing it |
"""

from __future__ import annotations

import cv2
import pytest

from app.services.digitizer import digitize_image, pipeline
from app.services.digitizer.accounting import _STREAM_COMMANDS

# `scripts/` is on sys.path from conftest. Imported rather than retyped: the
# fourteen and their conditions are defined once, in the instrument that
# measures them.
from coverage_audit import fixtures as _fourteen  # noqa: E402
from run_quality_bench import RNG_SEED  # noqa: E402

FOURTEEN = _fourteen()

#: Census keys that are counts. `other_commands` is a list of names, not a count.
COUNT_KEYS = (*_STREAM_COMMANDS, "other")


@pytest.fixture(scope="module", params=FOURTEEN, ids=[n for n, _, _ in FOURTEEN])
def run(request):
    name, path, params = request.param
    if not path.exists():
        # SKIP, not ERROR. A FileNotFoundError raised out of a fixture is
        # reported as an error per parametrised case — 16 of them took CI red
        # on run 31658769064 while the local suite read green, and the wall of
        # tracebacks buried the one real failure underneath it.
        #
        # The skip is only safe because `test_corpus_baseline_fixtures.py`
        # asserts all fourteen are present: on its own, skipping would let the
        # suite quietly measure ten fixtures and still report green.
        pytest.skip(
            f"fixture {path} is missing, so {name} was not measured. It should "
            f"be tracked; see the .gitignore exceptions for the C-tier baselines."
        )
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        path.read_bytes(),
        fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    return name, design, dict(pipeline._LAST_STREAM_ACCOUNTING)


def test_every_stream_entry_has_exactly_one_source(run):
    """STREAM SPACE. Six named categories, nothing folded in to make it close.

        stream_length == object_spans + stop_separators + linework_lead_in
                       + end_markers + merge_inserted + lock_inserted

    Falsified by: any emission site that appends outside an object's span and
    outside these categories. This is the identity that found two of them —
    `_merge_adjacent_same_hex` inserting a JUMP, and the dark-linework pass
    setting `obj_start` after its lead-in instead of before.

    ITS LIMIT, stated so it is not over-read. `merge_inserted` and
    `lock_inserted` are MEASURED DELTAS (`len` after minus `len` before), so
    this identity absorbs whatever those two passes insert and cannot police
    them — verified by injection: a merge that appends a real STITCH still
    satisfies this test. Policing those two passes is what
    `test_the_merge_pass_adds_no_penetrations` and
    `test_every_penetration_is_an_object_or_a_lock` are for, and both do fail
    under that injection. The live domain here is the emission sites in the
    main loop and the dark-linework pass, which is where it earned its place.
    """
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing; there is no stream to account for")

    parts = ("object_spans", "stop_separators", "linework_lead_in",
             "end_markers", "merge_inserted", "lock_inserted")
    named = sum(acc[k] for k in parts)
    assert named == len(design.stitches), (
        f"{name}: {len(design.stitches) - named} stream entries belong to no "
        f"named category. Categories: { {k: acc[k] for k in parts} }"
    )


def test_every_penetration_is_an_object_or_a_lock(run):
    """PENETRATION SPACE. Two sources, and `in_object_spans` is measured.

        penetrations == penetrations_in_object_spans + lock_penetrations

    `penetrations_in_object_spans` is accumulated as each span is emitted, by
    counting STITCH entries between `obj_start` and the end of the span. It is
    NOT `pre_lock["STITCH"]`; that was the previous definition and it made this
    assertion `x == x`.

    Falsified by: a code path appending a STITCH between objects (the left side
    grows, the right does not), or a lock recipe that stops emitting three-point
    ties.
    """
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")

    assert acc["penetrations"] == design.stitch_count, (
        "the census disagrees with the model's own count — one of them is wrong"
    )
    assert acc["penetrations_in_object_spans"] + acc["lock_penetrations"] == acc["penetrations"], (
        f"{name}: penetrations do not decompose. measured in-span "
        f"{acc['penetrations_in_object_spans']}, lock {acc['lock_penetrations']}, "
        f"total {acc['penetrations']}. A penetration was emitted outside every "
        f"object span and outside the lock pass."
    )
    assert acc["lock_penetrations"] >= 0, "the lock pass cannot remove penetrations"
    assert acc["lock_penetrations"] % 3 == 0, (
        f"{name}: {acc['lock_penetrations']} lock penetrations is not a whole "
        "number of three-point ties"
    )


def test_the_merge_pass_adds_no_penetrations(run):
    """It rewrites a COLOR_CHANGE into a TRIM and may add a JUMP. Never a stitch.

    Measured across the merge — `census_pre_merge` against `census_pre_lock` —
    because an assertion spanning pre_lock to post_lock never sees the merge at
    all. The earlier version of this test did exactly that and would have passed
    a merge inserting five hundred stitches.

    Falsified by: a merge that inserts or removes a STITCH.
    """
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")
    assert acc["census_pre_merge"]["STITCH"] == acc["census_pre_lock"]["STITCH"], (
        f"{name}: the merge pass changed the penetration count from "
        f"{acc['census_pre_merge']['STITCH']} to {acc['census_pre_lock']['STITCH']}"
    )
    # It may add entries, but only non-penetrating ones.
    assert acc["merge_inserted"] >= 0


def test_the_census_describes_the_stream_the_caller_receives(run):
    """The census is a snapshot, and a snapshot can go stale.

    Recounted from `design.stitches` — independently of the census — so the two
    are separate measurements rather than one number compared with itself.

    Falsified by: any pass that mutates the stream after `_lock_stream`. There
    is none today; if one is added, this is what notices.
    """
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")

    recount = {k: 0 for k in COUNT_KEYS}
    for s in design.stitches:
        key = str(getattr(s.command, "value", s.command))
        recount[key if key in recount else "other"] += 1

    for key in COUNT_KEYS:
        assert acc["census_post_lock"][key] == recount[key], (
            f"{name}: census says {acc['census_post_lock'][key]} {key} entries, "
            f"the returned stream has {recount[key]}. The census was taken "
            f"before something else changed the stream."
        )
    # And the two index spaces differ by exactly the non-penetrating commands.
    gap = len(design.stitches) - design.stitch_count
    assert gap == sum(recount[k] for k in COUNT_KEYS if k != "STITCH"), (
        f"{name}: stream minus penetrations is {gap}, which the recount does "
        "not explain"
    )


def test_no_unrecognised_command_reaches_the_stream(run):
    """`_stream_census` counts an unknown command instead of absorbing it.

    An earlier census used `out.get(key, 0) + 1`, which admits any command and
    therefore always sums to `len(stitches)` — the identity built on it could
    not notice a new command type. Unknown commands now land in `other`, which
    the decomposition above includes and this asserts is empty.

    Falsified by: a new command reaching the digitized stream. That is a real
    event to hear about, not an error to raise inside `digitize_image` — hence a
    red test rather than an exception in production.
    """
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")
    for stage in ("census_pre_merge", "census_pre_lock", "census_post_lock"):
        assert acc[stage]["other"] == 0, (
            f"{name}: {acc[stage]['other']} entries at {stage} carry commands "
            f"the accounting does not know: {acc[stage]['other_commands']}. Add "
            f"them to _STREAM_COMMANDS and to a named category, or find out why "
            f"they are in the stream."
        )


def test_the_worksheet_rows_sum_to_its_own_header(run):
    """The operator's page must add up. It did not.

    `worksheet_pdf.py` printed each colour row's stream span in a column headed
    "stitch count", beside a thread length, under a header taken from
    `design.stitch_count` — the other space. Measured on 08_mascot_detail before
    this fix: rows 7,930 against a header of 8,024, a gap of -94 (-1.17 %).

    Fixing the arithmetic alone would have been wrong. The rows now carry
    `penetration_count`, and colour-stop counts are recomputed from the FINAL
    stream so the tie-offs `_lock_stream` adds belong to the thread that sewed
    them instead of to nobody.

    Falsified by: a row printing a span again; a stop count taken before
    locking (the lock penetrations reappear as a gap); or a COLOR_CHANGE emitted
    for a stop that produced no objects, which breaks the partition — asserted
    separately below so the two failures are distinguishable.
    """
    from app.services.worksheet_pdf import build_worksheet

    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")

    assert acc["stops_partition_matches"], (
        f"{name}: {acc['stop_segments']} colour segments in the stream but "
        f"{acc['stops']} colour stops. A COLOR_CHANGE was emitted for a stop "
        f"that produced nothing, so per-stop counts cannot be attributed."
    )
    ws = build_worksheet(design)
    rows = sum(r.stitch_count for r in ws.color_sequence)
    assert rows == ws.estimated_stitch_count, (
        f"{name}: worksheet rows sum to {rows} under a header of "
        f"{ws.estimated_stitch_count} — the operator's page does not add up"
    )
    assert rows == design.stitch_count


def test_a_colour_stop_owns_the_ties_sewn_in_its_thread(run):
    """Stop spans partition the whole stream, tie-offs included.

    Falsified by: computing stop counts before `_lock_stream`, which is what
    they were until 2026-08-14.
    """
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")
    assert sum(c.stream_span for c in design.color_stops) == len(design.stitches)
    assert sum(c.penetration_count for c in design.color_stops) == design.stitch_count
