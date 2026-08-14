"""A coverage comparison refuses to span two trees (the C11 splice, closed).

On 2026-08-20 C11's coverage was reported as 6.74 % beside an object count of
27. Both figures were correct measurements — of DIFFERENT TREES. 6.74 % came
from the pre-boundary RS1 build, whose single-branch boundary did not yet
exist, so C11's 4-branch network still emitted four objects: 23 base + 4
single-branch + 4 network = 31 objects at 6.74 %. The boundary removed all four
network objects at once, giving 27 at 6.83 %. Each row was internally
consistent with its own tree; the reported row was assembled from both.

The instinct at the time was "emit `code.head` like TRACE does". That is only
half a fix, and the CTO's ruling of 2026-08-21 named the missing half:

    Emitting the field still requires a human to look at it. Refusing the
    comparison does not.

So these tests pin the REFUSAL, not the field. Three conditions are one
condition — you cannot tell which code produced the numbers:

  * the two documents name different heads;
  * either document was written from a dirty tree (its head does not describe
    it);
  * either document predates the provenance block entirely.

And the override exists because a legitimate cross-tree diff is a real need —
comparing a promotion against its pre-promotion baseline is exactly that — so
it is available, explicit, and self-announcing.
"""

from __future__ import annotations

import json

import pytest

import coverage_audit as ca
from _provenance import attributable, describe


CLEAN_A = {"head": "a" * 40, "dirty": False}
CLEAN_B = {"head": "b" * 40, "dirty": False}
DIRTY_A = {"head": "a" * 40, "dirty": True}
NO_HEAD = {"head": "", "dirty": False}


def test_the_same_clean_tree_compares_without_complaint():
    ca._gate_comparison(CLEAN_A, dict(CLEAN_A), override=False)  # must not raise


@pytest.mark.parametrize(
    ("before", "after", "why"),
    [
        (CLEAN_A, CLEAN_B, "different heads — two trees, the C11 case exactly"),
        (DIRTY_A, CLEAN_A, "before was dirty, so its head does not describe it"),
        (CLEAN_A, DIRTY_A, "after is dirty"),
        (NO_HEAD, CLEAN_A, "git could not name the head"),
        (None, CLEAN_A, "legacy document, written before provenance existed"),
    ],
)
def test_a_cross_tree_comparison_is_refused(before, after, why):
    with pytest.raises(SystemExit) as exc:
        ca._gate_comparison(before, after, override=False)
    msg = str(exc.value)
    assert "REFUSING TO COMPARE" in msg, why
    # The refusal must NAME both trees; a refusal you cannot act on is a wall.
    assert describe(before) in msg and describe(after) in msg


def test_the_override_permits_it_and_says_so(capsys):
    ca._gate_comparison(CLEAN_A, CLEAN_B, override=True)  # must not raise
    out = capsys.readouterr().out
    assert "COMPARING ACROSS TREES" in out
    assert "explicitly requested" in out
    # Both trees printed, so the reader knows what the deltas span.
    assert describe(CLEAN_A) in out and describe(CLEAN_B) in out


def test_a_legacy_document_still_loads(tmp_path):
    """Refusing to COMPARE an old document is right; failing to READ it is not.

    Every audit JSON written before 2026-08-21 is a bare list of rows. They
    must still open — otherwise the fix destroys the very baselines it exists
    to protect.
    """
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps([{"fixture": "x", "uncovered_px": 0.1,
                                   "objects": 1, "stitches": 2, "warnings": []}]))
    rows, code = ca.load(legacy)
    assert rows[0]["fixture"] == "x"
    assert code is None and not attributable(code)


def test_a_new_document_round_trips_with_its_tree(tmp_path):
    rows = [{"fixture": "x", "uncovered_px": 0.1, "objects": 1,
             "stitches": 2, "warnings": [], "conditions": "cotton @ 100x100"}]
    doc = ca.document(rows)
    assert set(doc["code"]) == {"head", "dirty"}
    # The fixture SET travels, not just its size: the A01/A02 promotion changes
    # the set, and a set change is a different event from a code change.
    assert doc["fixture_set"] == ["x"]
    p = tmp_path / "doc.json"
    p.write_text(json.dumps(doc))
    back_rows, back_code = ca.load(p)
    assert back_rows == rows and back_code == doc["code"]


def test_trace_and_the_audit_share_one_provenance_implementation():
    """Two copies of "which tree is this" is the drift this repo has been
    punished for twice (the pull-comp expression, the coalesce parameters)."""
    import trace as trace_script

    from _provenance import code_provenance

    assert trace_script._git is code_provenance
