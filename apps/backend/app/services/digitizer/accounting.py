"""Stream accounting — the census that lets the stream say where it came from.

Diagnostic, not pipeline logic: nothing here changes a stitch. It exists so that
"every entry has exactly one source" is a measured identity instead of a claim
(INSTRUMENT-2), and it lives in its own module because BOTH emitters need it —
`pipeline.digitize_image` uses it today, and `rebuild.rebuild_design` calls the
same `_lock_stream` with no census at all, which is the named gap this
extraction exists to close. One implementation serving both paths cannot drift
into two that disagree; two copies is how the worksheet printed rows in one
space under a header in another.

Sits directly above `constants` in the layering: it reads streams and colour
stops, imports nothing from the generation stack, and everything above it may
import it.
"""

from __future__ import annotations

# The commands a digitized stream is allowed to contain. Named, and closed:
# an earlier draft counted with `out.get(key, 0) + 1`, which admits ANY command
# and therefore always sums to `len(stitches)`. That made the census incapable
# of noticing a new command type — the identity built on it closed by
# construction and could not say no.
_STREAM_COMMANDS = ("STITCH", "JUMP", "TRIM", "COLOR_CHANGE", "END")


def _stream_census(stitches) -> dict:
    """Count each command in a stream. One place, so the two sides agree.

    Anything outside `_STREAM_COMMANDS` lands in `other` and is named in
    `other_commands`. It is counted rather than rejected — raising here would
    turn a new command type into a production outage instead of a red test —
    but `other` is a category the accounting identity must include and the
    tests assert is empty, so it cannot pass unnoticed.
    """
    out = {k: 0 for k in _STREAM_COMMANDS}
    out["other"] = 0
    seen_other: set[str] = set()
    for s in stitches:
        key = str(getattr(s.command, "value", s.command))
        if key in out and key != "other":
            out[key] += 1
        else:
            out["other"] += 1
            seen_other.add(key)
    out["other_commands"] = sorted(seen_other)
    return out


def attribute_stops_from_stream(stitches, color_stops) -> tuple[int, bool]:
    """Recount each colour stop from the FINAL stream. Returns (segments, matched).

    Stop counts used to be `len(stitches) - stop_start`, measured before
    locking, so every tie-off `_lock_stream` added belonged to no stop. On
    fixture 08 that left the operator's worksheet with rows summing to 7,862
    under a header of 8,024 — the 162 lock penetrations, printed nowhere. A
    tie-off is sewn in whichever thread is mounted, so it belongs to that stop.

    Recoverable for stops and not for objects: the final stream is partitioned
    by its COLOR_CHANGE entries, one fewer than there are stops, whereas object
    boundaries do not survive locking (their start indices are not kept, and
    deliberately so).

    NOTHING IS WRITTEN when the partition does not match the stop count. That
    happens when a COLOR_CHANGE is emitted for a stop that produced nothing —
    the dark-linework pass can do it when its chains are dropped as
    garment-coloured — and zipping the shorter list would misattribute every
    stop after it. The caller records the mismatch instead; see the accounting
    test that names this case separately from a wrong sum.
    """
    seg_pen: list[int] = []
    seg_span: list[int] = []
    pen = span = 0
    for s in stitches:
        span += 1
        if s.command == "STITCH":
            pen += 1
        elif s.command == "COLOR_CHANGE":
            seg_pen.append(pen)
            seg_span.append(span)
            pen = span = 0
    seg_pen.append(pen)
    seg_span.append(span)
    matched = len(seg_pen) == len(color_stops)
    if matched:
        for cs, p_, sp_ in zip(color_stops, seg_pen, seg_span):
            cs.penetration_count = p_
            cs.stream_span = sp_
    return len(seg_pen), matched
