"""The two Part 59 product decisions: the colour-cap warning and trim profiles.

Both exist to surface a measured fact instead of a silent behaviour:

* `max_colors` above 8 has been silently discarded since the planner landed —
  Part 57 measured it inert (k=12 and k=8 byte-identical) and Part 58 decided
  keep-the-cap-and-say-so. The warning must appear for capped requests, must
  not appear otherwise, and must not change a single stitch.
* `TRIM_MIN_GAP_MM=6.0` stays the engine default for unknown machines; the
  aggressive export profile applies Part 48's measured 10 mm point to machines
  known to auto-trim. Its whole safety argument is that the trim decision never
  influences geometry, so these tests assert stream equivalence rather than
  trusting the docstring.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.design import Design, Stitch
from app.services.digitizer import PLAN_MAX_COLORS, TRIM_MIN_GAP_MM, digitize_image
from app.services.trim_profiles import (
    TRIM_PROFILES,
    apply_trim_profile,
    carried_thread_mm,
)

FIXTURE = BACKEND_ROOT / "tests/fixtures/quality_bench/01_flat_2color_logo.png"


def _digitize(max_colors: int) -> Design:
    cv2.setRNGSeed(1234)
    return digitize_image(FIXTURE.read_bytes(), "cotton", "100x100", max_colors)


def _stream(design: Design):
    return [(str(s.command), round(s.x, 4), round(s.y, 4)) for s in design.stitches]


# ── the colour-cap warning ────────────────────────────────────────────────────


def test_a_request_past_the_cap_gets_a_warning_and_identical_stitches():
    capped = _digitize(12)
    at_cap = _digitize(PLAN_MAX_COLORS)

    hits = [w for w in capped.warnings if "Colour limit" in w]
    assert len(hits) == 1, capped.warnings
    assert f"at most {PLAN_MAX_COLORS}" in hits[0]
    assert "12 colours were requested" in hits[0]

    # The warning is the ONLY difference: Part 57's byte-identity, now pinned.
    assert _stream(capped) == _stream(at_cap)


def test_a_request_at_or_below_the_cap_is_not_warned_about():
    for k in (PLAN_MAX_COLORS, 2):
        d = _digitize(k)
        assert not any("Colour limit" in w for w in d.warnings), d.warnings


# ── trim profiles: the synthetic cases ────────────────────────────────────────


def _design(stitches) -> Design:
    return Design(name="t", stitches=list(stitches))


def _s(cmd, x, y) -> Stitch:
    return Stitch(x=x, y=y, command=cmd)


def test_conservative_is_the_same_object_not_merely_an_equal_one():
    d = _design([_s("STITCH", 0, 0), _s("TRIM", 0, 0), _s("JUMP", 8, 0), _s("STITCH", 8, 0)])
    assert apply_trim_profile(d, "conservative") is d


def test_unknown_profile_is_rejected_by_name():
    d = _design([_s("STITCH", 0, 0)])
    with pytest.raises(ValueError, match="fastest"):
        apply_trim_profile(d, "fastest")


def test_aggressive_drops_short_carries_and_keeps_long_ones():
    d = _design([
        _s("STITCH", 0, 0),
        _s("TRIM", 0, 0), _s("JUMP", 8, 0), _s("STITCH", 8, 0),      # 8 mm  -> dropped
        _s("TRIM", 8, 0), _s("JUMP", 20, 0), _s("STITCH", 20, 0),    # 12 mm -> kept
    ])
    out = apply_trim_profile(d, "aggressive")
    cmds = [str(s.command) for s in out.stitches]
    assert cmds.count("TRIM") == 1
    # Everything that is not a TRIM survives, in order, untouched.
    assert [c for c in cmds if c != "TRIM"] == \
           [str(s.command) for s in d.stitches if str(s.command) != "TRIM"]
    assert d.stitches[1] not in out.stitches or cmds.count("TRIM") == 1


def test_carried_thread_follows_the_jump_chain_not_the_first_hop():
    """The imported-file case that a naive next-command distance gets wrong.

    DST splits long moves into chains of short jumps. Three 4 mm jumps carry
    12 mm of thread; an implementation that measured only the first hop would
    call it 4 mm and wrongly drop the trim.
    """
    d = _design([
        _s("STITCH", 0, 0),
        _s("TRIM", 0, 0),
        _s("JUMP", 4, 0), _s("JUMP", 8, 0), _s("JUMP", 12, 0),
        _s("STITCH", 12, 0),
    ])
    assert carried_thread_mm(d.stitches, 1) == pytest.approx(12.0)
    out = apply_trim_profile(d, "aggressive")
    assert [str(s.command) for s in out.stitches].count("TRIM") == 1


def test_a_trim_guarding_a_colour_change_is_never_dropped():
    """After a colour change the machine re-threads; the carry question is moot
    and removing that trim would leave the old thread loose."""
    d = _design([
        _s("STITCH", 0, 0),
        _s("TRIM", 0, 0),
        _s("COLOR_CHANGE", 0, 0),
        _s("JUMP", 2, 0), _s("STITCH", 2, 0),
    ])
    out = apply_trim_profile(d, "aggressive")
    assert [str(s.command) for s in out.stitches].count("TRIM") == 1


# ── trim profiles: equivalence on a real design ───────────────────────────────


def test_on_a_real_design_aggressive_removes_exactly_the_6_to_10_band():
    """The safety argument, asserted on a real design: geometry untouched, the
    kept/removed split follows the carried-thread rule exactly, and the filter
    is conservative relative to the engine's own entry-gap rule."""
    d = _digitize(2)
    out = apply_trim_profile(d, "aggressive")

    # Non-TRIM commands are identical, in order — the design sews the same.
    strip = lambda des: [(str(s.command), s.x, s.y) for s in des.stitches
                         if str(s.command) != "TRIM"]
    assert strip(d) == strip(out)

    # Every surviving trim carries >= 10 mm of thread; every removed one carried
    # < 10 and >= TRIM_MIN_GAP_MM (the engine would not have emitted it otherwise;
    # the carried path is never shorter than the entry gap the engine tested).
    threshold = TRIM_PROFILES["aggressive"]
    kept = removed = 0
    for i, s in enumerate(d.stitches):
        if str(s.command) != "TRIM":
            continue
        carry = carried_thread_mm(d.stitches, i)
        if carry >= threshold:
            kept += 1
        else:
            removed += 1
            assert carry >= TRIM_MIN_GAP_MM - 1e-6, (
                f"engine emitted a trim carrying only {carry:.2f} mm"
            )
    assert kept == sum(1 for s in out.stitches if str(s.command) == "TRIM")
    assert removed == len(d.stitches) - len(out.stitches)
    assert d.stitch_count == out.stitch_count

    # Safety direction, pinned: the carried path is never shorter than the entry
    # gap, so every trim this filter drops would ALSO have been dropped by
    # re-generating at the same threshold — the filter is conservative relative
    # to the engine's own rule, never looser. (On the panel the two rules differ
    # by 74 trims, all of them KEPT by the filter; see trim_profiles.py.)
    import math as _math
    for i, s in enumerate(d.stitches):
        if str(s.command) != "TRIM":
            continue
        nxt = d.stitches[i + 1]
        entry_gap = _math.hypot(nxt.x - s.x, nxt.y - s.y)
        assert carried_thread_mm(d.stitches, i) >= entry_gap - 1e-6


# ── imported-stream invariants (v2 Part 61) ──────────────────────────────────
#
# Part 61 measured the profile on foreign files and machine-format round-trips.
# Three stream shapes appeared that our generator never emits, and each gets a
# pin here so the behaviour cannot regress silently.


def test_a_trailing_trim_with_no_following_stitch_is_never_dropped():
    """Seen in real VP3 round-trips: the stream ends on a trim. Its carry is
    unmeasurable (+inf), so the safe call is to keep it — and it is kept."""
    d = _design([_s("STITCH", 0, 0), _s("STITCH", 5, 0), _s("TRIM", 5, 0)])
    out = apply_trim_profile(d, "aggressive")
    assert [str(s.command) for s in out.stitches].count("TRIM") == 1
    assert carried_thread_mm(d.stitches, 2) == float("inf")


def test_consecutive_double_trims_decide_together():
    """Seen 1,435 times in one PES round-trip: TRIM TRIM before one move.

    Both measure the same carried thread (the walk skips the sibling TRIM), so
    they drop together below the threshold and stay together above it — never
    one without the other, which would be an incoherent cut schedule.
    """
    short = _design([
        _s("STITCH", 0, 0),
        _s("TRIM", 0, 0), _s("TRIM", 0, 0),
        _s("JUMP", 7, 0), _s("STITCH", 7, 0),
    ])
    out = apply_trim_profile(short, "aggressive")
    assert [str(s.command) for s in out.stitches].count("TRIM") == 0

    long = _design([
        _s("STITCH", 0, 0),
        _s("TRIM", 0, 0), _s("TRIM", 0, 0),
        _s("JUMP", 15, 0), _s("STITCH", 15, 0),
    ])
    out = apply_trim_profile(long, "aggressive")
    assert [str(s.command) for s in out.stitches].count("TRIM") == 2


def test_the_invariants_hold_on_a_real_machine_format_round_trip():
    """A DST round-trip splits long moves into jump chains — the stream shape
    the carried-path rule exists for, on a genuinely machine-encoded file."""
    from app.services import embroidery_io

    d = _digitize(2)
    imported = embroidery_io.read_embroidery(embroidery_io.write_embroidery(d, "dst"), "dst")
    out = apply_trim_profile(imported, "aggressive")

    strip = lambda des: [(str(s.command), round(s.x, 3), round(s.y, 3))
                         for s in des.stitches if str(s.command) != "TRIM"]
    assert strip(imported) == strip(out), "diff must be trim-only on imports too"

    threshold = TRIM_PROFILES["aggressive"]
    kept_expected = 0
    for i, s in enumerate(imported.stitches):
        if str(s.command) != "TRIM":
            continue
        if carried_thread_mm(imported.stitches, i) >= threshold:
            kept_expected += 1
    assert kept_expected == sum(1 for s in out.stitches if str(s.command) == "TRIM")


# ── the export endpoints ──────────────────────────────────────────────────────


def test_export_accepts_the_profile_and_rejects_unknown_names():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    d = _design([
        _s("STITCH", 0, 0), _s("STITCH", 5, 0),
        _s("TRIM", 5, 0), _s("JUMP", 12, 0), _s("STITCH", 12, 0),
    ])
    body = d.model_dump(by_alias=True)

    ok = client.post("/api/export?format=dst&trim_profile=conservative", json=body)
    assert ok.status_code == 200

    agg = client.post("/api/export?format=dst&trim_profile=aggressive", json=body)
    assert agg.status_code == 200
    # 7 mm carry: the aggressive file drops the trim, so it is strictly smaller.
    assert len(agg.content) < len(ok.content)

    bad = client.post("/api/export?format=dst&trim_profile=fastest", json=body)
    assert bad.status_code == 422
    assert "fastest" in bad.json()["detail"]
