"""Machine-aware trim profiles, applied at export time (v2 Part 59).

The engine writes a TRIM wherever the thread between two objects would be
TRIM_MIN_GAP_MM (6.0 mm) or longer. That default is deliberately conservative:
the file may be sewn on any machine, and on one without an aggressive
auto-trimmer every skipped trim is loose thread left on the garment. Part 48
measured the tradeoff and refused to raise the constant for exactly that reason.

What Part 48 also measured is the price of that caution when the machine IS
known: at a 10 mm threshold the reference panel needs 485 trims instead of 663 —
27% fewer, roughly 7.5 minutes of machine time — with identical stitching. So
the threshold is a fact about the TARGET MACHINE, not about the design, which
makes it an export-time choice rather than an engine constant.

This module applies that choice to a finished Design. The trim decision never
influences geometry — the engine emits the same stitches and the same jump
either way, only the TRIM command itself is conditional (see pipeline.py, the
TRIM_MIN_GAP_MM site) — so dropping trims after the fact cannot change what is
sewn, and a test asserts that on a real design rather than trusting this
paragraph.

One deliberate difference from re-generating at a higher threshold, measured
before it was written down: the engine's gate uses the ENTRY GAP — the straight
line from the previous object's last stitch to the next object's first point —
while this filter walks the NEEDLE PATH from the trim to the next actual
penetration, through any travel jumps the next object opens with. The path is
where the un-trimmed thread physically lies, and it is never shorter than the
entry gap, so this filter only ever KEEPS trims that re-generation would have
dropped — never the reverse. On the reference panel that difference is real: 178
trims have an entry gap under 10 mm, but 74 of them carry >= 10 mm of actual
thread, so the profile leaves 559 trims where re-generation at 10 mm leaves 485.
The 74 are trims a 10 mm-comfort machine genuinely wants. (Part 48's 485 was
measured with the entry-gap rule; both figures are correct for the quantity each
rule measures.) The same path walk is what makes the filter honest on IMPORTED
files, where DST splits long moves into chains of short jumps.

Profiles rather than a free numeric knob, deliberately: a number invites tuning,
and the two situations that exist — "I don't know the machine" and "I know it
auto-trims" — are what the names say.
"""

from __future__ import annotations

import math

from app.models.design import Design, enum_str

# threshold in mm below which a trim is dropped, or None for "leave the stream
# exactly as generated".
TRIM_PROFILES: dict[str, float | None] = {
    # Unknown machine: the engine's own conservative gate (TRIM_MIN_GAP_MM=6.0)
    # already decided every trim; change nothing.
    "conservative": None,
    # Machine with an aggressive auto-trimmer: carry thread up to 10 mm. The
    # value is Part 48's measured point (485 vs 663 trims on the panel), not a
    # tunable — if a different machine wants a different carry length, that is
    # a new named profile with its own measurement.
    "aggressive": 10.0,
}

DEFAULT_PROFILE = "conservative"

# ~Machine seconds per trim, order-of-magnitude, used only for reporting the
# saving in familiar units — never to justify a threshold (Part 48's figure).
TRIM_SECONDS_EQUIV = 2.5


def _cmd(stitch) -> str:
    return enum_str(stitch.command).upper()


def carried_thread_mm(stitches, trim_index: int) -> float:
    """Length of thread the machine would carry if this trim were skipped.

    Walked along the needle path from the trim to the next STITCH — through any
    chain of JUMPs — because that is where the un-trimmed thread physically
    lies. Returns +inf when no stitch follows (a trailing trim guards nothing,
    but dropping it is not this function's call).
    """
    total = 0.0
    px, py = stitches[trim_index].x, stitches[trim_index].y
    for s in stitches[trim_index + 1:]:
        cmd = _cmd(s)
        if cmd == "COLOR_CHANGE":
            # A colour change re-threads; the carry question ends here.
            return math.inf
        if cmd in ("JUMP", "STITCH"):
            total += math.hypot(s.x - px, s.y - py)
            px, py = s.x, s.y
            if cmd == "STITCH":
                return total
    return math.inf


def apply_trim_profile(design: Design, profile: str) -> Design:
    """Return the design with the profile's trim policy applied.

    ``conservative`` returns the design unchanged — the same object, no copy —
    so the default path is provably a no-op. ``aggressive`` returns a copy with
    every TRIM whose carried thread is under the profile threshold removed;
    stitches, jumps and colour changes are untouched, so the design sews
    identically and only the trim schedule differs.
    """
    if profile not in TRIM_PROFILES:
        raise ValueError(
            f"Unknown trim profile {profile!r}; expected one of "
            f"{sorted(TRIM_PROFILES)}"
        )
    threshold = TRIM_PROFILES[profile]
    if threshold is None:
        return design

    stitches = design.stitches
    kept = [
        s for i, s in enumerate(stitches)
        if _cmd(s) != "TRIM" or carried_thread_mm(stitches, i) >= threshold
    ]
    if len(kept) == len(stitches):
        return design
    # stitch_count counts STITCH commands (pipeline.py), which this never touches.
    return design.model_copy(update={"stitches": kept})
