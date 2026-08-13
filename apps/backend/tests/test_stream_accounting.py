"""Every entry in the stream has exactly one source (INSTRUMENT-2).

The starting point was a claim: "90 penetrations on fixture 08 belong to no
object; they are lock stitches." The number was arrived at by subtracting
`sum(object.stitch_count)` from `design.stitch_count`, and **that subtraction is
not well formed**. The two operands live in different spaces:

  * `object.stitch_count` is `len(stitches) - obj_start` — a STREAM SPAN. It
    counts the JUMPs and TRIMs emitted inside that object, and it is computed
    before `_lock_stream` runs, so it excludes every tie-off.
  * `design.stitch_count` counts STITCH entries alone, after locking.

Their difference is not a count of unattributed penetrations. It is a number
with no referent, and the explanation attached to it was never tested — which is
the point of the exercise: an instrument nobody can check is not an instrument.

These tests state the identity separately in each space, on all fourteen
fixtures, from a census the pipeline takes at the three points where the stream
is rewritten. Categories are NAMED, and nothing is folded into "objects" to make
the arithmetic close.

STREAM SPACE — every entry belongs to exactly one of six categories:

    stream_length == object_spans        # entries inside an object's own span
                   + stop_separators     # one per colour-stop boundary
                   + linework_lead_in    # the TRIM and JUMP before each dark-line run
                   + end_markers         # the terminating END
                   + merge_inserted      # JUMPs added when two same-thread stops merged
                   + lock_inserted       # tie-offs and their trims

PENETRATION SPACE — every needle penetration has one of two sources:

    penetrations == penetrations_in_object_spans + lock_penetrations

There is no third source. If one appears, one of these tests fails and the next
person finds out what it is instead of inheriting a folklore number.
"""

from __future__ import annotations

import cv2
import pytest

from app.services.digitizer import digitize_image, pipeline

# `scripts/` is on sys.path from conftest. Imported rather than retyped: the
# fourteen and their conditions are defined once, in the instrument that
# measures them, and a second copy here would drift the way the bench table and
# the visual-regression table drifted before they were unified.
from coverage_audit import fixtures as _fourteen  # noqa: E402
from run_quality_bench import RNG_SEED  # noqa: E402

FOURTEEN = _fourteen()


@pytest.fixture(scope="module", params=FOURTEEN, ids=[n for n, _, _ in FOURTEEN])
def run(request):
    name, path, params = request.param
    if not path.exists():
        # SKIP, not ERROR. A FileNotFoundError raised out of a fixture is
        # reported as an error per parametrised case — 16 of them took CI red
        # on run 31658769064 while the local suite read green, and the wall of
        # tracebacks buried the one real failure underneath it. A skip with the
        # path in it says the same thing in one line.
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
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing; there is no stream to account for")

    named = (acc["object_spans"] + acc["stop_separators"] + acc["linework_lead_in"]
             + acc["end_markers"] + acc["merge_inserted"] + acc["lock_inserted"])
    assert acc["stream_length"] == len(design.stitches)
    assert named == acc["stream_length"], (
        f"{name}: {acc['stream_length'] - named} stream entries belong to no named "
        f"category. Categories: {  {k: acc[k] for k in ('object_spans', 'stop_separators', 'linework_lead_in', 'end_markers', 'merge_inserted', 'lock_inserted')} }"
    )


def test_every_penetration_is_an_object_or_a_lock(run):
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")

    assert acc["penetrations"] == design.stitch_count, (
        "the census disagrees with the model's own count — one of them is wrong"
    )
    assert acc["penetrations_in_object_spans"] + acc["lock_penetrations"] == acc["penetrations"], (
        f"{name}: penetrations do not decompose. in-span "
        f"{acc['penetrations_in_object_spans']}, lock {acc['lock_penetrations']}, "
        f"total {acc['penetrations']}"
    )
    assert acc["lock_penetrations"] >= 0, "the lock pass cannot remove penetrations"
    # Three per tie, by construction in `_tie_triangle`. If this stops holding,
    # the lock recipe changed and the accounting above needs re-reading, not
    # patching.
    assert acc["lock_penetrations"] % 3 == 0, (
        f"{name}: {acc['lock_penetrations']} lock penetrations is not a whole "
        "number of three-point ties"
    )


def test_the_merge_pass_adds_no_penetrations(run):
    """It rewrites a COLOR_CHANGE into a TRIM and may add a JUMP. Never a stitch."""
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")
    assert acc["census_pre_lock"]["STITCH"] == acc["penetrations_in_object_spans"]


def test_the_two_index_spaces_are_not_interchangeable(run):
    """The gap between them is real and must not be quoted as an anomaly.

    Reported as a number, not asserted to be small: on 01_flat_2color_logo it is
    11 and on 08_mascot_detail it is 82, and both are correct. What is wrong is
    calling either one 'unattributed penetrations'.
    """
    name, design, acc = run
    if not design.stitches:
        pytest.skip(f"{name} emitted nothing")
    gap = acc["stream_length"] - acc["penetrations"]
    non_stitch = sum(v for k, v in acc["census_post_lock"].items() if k != "STITCH")
    assert gap == non_stitch, (
        f"{name}: stream minus penetrations is {gap} but there are {non_stitch} "
        "non-STITCH entries — the two spaces differ by exactly the non-penetrating "
        "commands, nothing else"
    )
