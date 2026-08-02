"""Stitch-level editing — the "DST editor" (v2 Part 36).

What competitors call a stitch editor is the ability to open a machine file
and change the STREAM itself, below the object level: delete a run of bad
stitches, turn a jump into a stitch (or vice versa), drop a redundant trim,
move/scale/rotate a block, split a colour block in two, or reorder colour
blocks to cut re-threads. Everything here operates on the flat stitch list
and re-derives nothing, so it works on an imported .DST that has no objects
at all — which is exactly the case object-level editing cannot serve.

Two invariants are enforced after EVERY operation, because a stitch editor
whose output the machine refuses is worthless:

  * no stitch may exceed the machine's 12.7mm reach — longer moves are
    subdivided (the same rule the digitizer applies at generation time);
  * the stream ends with exactly one END, and never contains a run of
    consecutive duplicate control commands.

``apply_ops`` is a pure function: it returns a NEW stitch list, so undo in the
UI stays a matter of keeping the previous one.
"""

from __future__ import annotations

import math

from app.models.design import Stitch, StitchCommand

# Machine hard limit (mm). The digitizer generates well under this; imported
# files can and do sit right at it.
MACHINE_MAX_MM = 12.7
# Subdivision target when an edit stretches a stitch past the limit.
SUBDIVIDE_MM = 6.0

CONTROL = {StitchCommand.TRIM, StitchCommand.COLOR_CHANGE, StitchCommand.STOP}


class EditError(ValueError):
    """A rejected edit — the message is shown to the user verbatim."""


def _cmd(s: Stitch) -> StitchCommand:
    return s.command if isinstance(s.command, StitchCommand) else StitchCommand(s.command)


def _clone(s: Stitch, **kw) -> Stitch:
    return Stitch(x=kw.get("x", s.x), y=kw.get("y", s.y), command=kw.get("command", _cmd(s)))


def _resolve_range(stitches: list[Stitch], start: int, end: int) -> tuple[int, int]:
    n = len(stitches)
    if n == 0:
        raise EditError("This design has no stitches to edit.")
    a, b = sorted((int(start), int(end)))
    a = max(0, min(a, n - 1))
    b = max(0, min(b, n - 1))
    return a, b


# ── operations ──────────────────────────────────────────────────────────────


def delete_range(stitches, start, end):
    a, b = _resolve_range(stitches, start, end)
    out = stitches[:a] + stitches[b + 1 :]
    if not any(_cmd(s) == StitchCommand.STITCH for s in out):
        raise EditError("That would delete every stitch in the design.")
    return out


def set_command(stitches, start, end, command: str):
    """Retype a block: STITCH <-> JUMP, or drop/insert TRIM markers."""
    try:
        target = StitchCommand(command)
    except ValueError as exc:
        raise EditError(f"Unknown stitch command '{command}'.") from exc
    if target is StitchCommand.END:
        raise EditError("END is managed automatically; it cannot be assigned.")
    a, b = _resolve_range(stitches, start, end)
    return [
        _clone(s, command=target) if a <= i <= b else s for i, s in enumerate(stitches)
    ]


def insert_stitch(stitches, index: int, x: float, y: float, command: str = "STITCH"):
    try:
        cmd = StitchCommand(command)
    except ValueError as exc:
        raise EditError(f"Unknown stitch command '{command}'.") from exc
    i = max(0, min(int(index), len(stitches)))
    return stitches[:i] + [Stitch(x=float(x), y=float(y), command=cmd)] + stitches[i:]


def move_point(stitches, index: int, x: float, y: float):
    if not 0 <= int(index) < len(stitches):
        raise EditError("That stitch index is outside the design.")
    i = int(index)
    return [_clone(s, x=float(x), y=float(y)) if j == i else s for j, s in enumerate(stitches)]


def transform_range(stitches, start, end, dx=0.0, dy=0.0, scale=1.0, rotate_deg=0.0,
                    mirror_x=False, mirror_y=False):
    """Translate / scale / rotate / mirror a block about its own centre."""
    a, b = _resolve_range(stitches, start, end)
    block = stitches[a : b + 1]
    pts = [(s.x, s.y) for s in block]
    if not pts:
        raise EditError("Empty selection.")
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    if scale <= 0:
        raise EditError("Scale must be greater than zero.")
    th = math.radians(float(rotate_deg))
    cos, sin = math.cos(th), math.sin(th)
    out = list(stitches)
    for i, s in enumerate(block):
        px, py = s.x - cx, s.y - cy
        if mirror_x:
            px = -px
        if mirror_y:
            py = -py
        px, py = px * scale, py * scale
        rx = px * cos - py * sin
        ry = px * sin + py * cos
        out[a + i] = _clone(s, x=cx + rx + dx, y=cy + ry + dy)
    return out


def split_color_block(stitches, index: int):
    """Insert a COLOR_CHANGE at ``index`` — one block becomes two stops."""
    i = max(1, min(int(index), len(stitches) - 1))
    return stitches[:i] + [Stitch(x=stitches[i].x, y=stitches[i].y,
                                  command=StitchCommand.COLOR_CHANGE)] + stitches[i:]


def remove_trims(stitches, start, end):
    """Drop TRIM markers in a range — the classic 'too many trims' cleanup."""
    a, b = _resolve_range(stitches, start, end)
    return [s for i, s in enumerate(stitches)
            if not (a <= i <= b and _cmd(s) == StitchCommand.TRIM)]


OPS = {
    "delete": lambda st, o: delete_range(st, o["start"], o["end"]),
    "setCommand": lambda st, o: set_command(st, o["start"], o["end"], o["command"]),
    "insert": lambda st, o: insert_stitch(st, o["index"], o["x"], o["y"],
                                          o.get("command", "STITCH")),
    "movePoint": lambda st, o: move_point(st, o["index"], o["x"], o["y"]),
    "transform": lambda st, o: transform_range(
        st, o["start"], o["end"], o.get("dx", 0.0), o.get("dy", 0.0),
        o.get("scale", 1.0), o.get("rotateDeg", 0.0),
        bool(o.get("mirrorX")), bool(o.get("mirrorY"))),
    "splitColor": lambda st, o: split_color_block(st, o["index"]),
    "removeTrims": lambda st, o: remove_trims(st, o["start"], o["end"]),
}


# ── invariants ──────────────────────────────────────────────────────────────


def _subdivide_over_limit(stitches: list[Stitch]) -> list[Stitch]:
    """Break any move longer than the machine's reach into legal steps.

    Scaling a block up is the operation that produces these, and it is silent
    at edit time — the file simply fails (or the machine skips) later.
    """
    out: list[Stitch] = []
    prev: Stitch | None = None
    for s in stitches:
        if prev is not None and _cmd(s) in (StitchCommand.STITCH, StitchCommand.JUMP):
            d = math.hypot(s.x - prev.x, s.y - prev.y)
            if d > MACHINE_MAX_MM:
                steps = math.ceil(d / SUBDIVIDE_MM)
                for k in range(1, steps):
                    t = k / steps
                    out.append(Stitch(x=prev.x + (s.x - prev.x) * t,
                                      y=prev.y + (s.y - prev.y) * t,
                                      command=_cmd(s)))
        out.append(s)
        if _cmd(s) is not StitchCommand.END:
            prev = s
    return out


def _normalise_controls(stitches: list[Stitch]) -> tuple[list[Stitch], int]:
    """Collapse consecutive duplicate controls and enforce a single END.

    Returns ``(stitches, dropped)``. The count is returned rather than inferred
    from the length delta because this function also APPENDS the END — a net
    length of zero hid a real repair from the user (caught by test).
    """
    out: list[Stitch] = []
    dropped = 0
    for s in stitches:
        if _cmd(s) is StitchCommand.END:
            continue
        if out and _cmd(s) in CONTROL and _cmd(out[-1]) == _cmd(s):
            dropped += 1  # a second TRIM/COLOR_CHANGE in a row is a no-op
            continue
        out.append(s)
    while out and _cmd(out[-1]) in CONTROL:
        out.pop()  # a trailing trim/colour change before END does nothing
        dropped += 1
    if out:
        out.append(Stitch(x=out[-1].x, y=out[-1].y, command=StitchCommand.END))
    return out, dropped


def apply_ops(stitches: list[Stitch], ops: list[dict]) -> tuple[list[Stitch], list[str]]:
    """Apply ops in order, then restore the stream invariants.

    Returns ``(stitches, notes)`` — notes describe repairs the editor made on
    the user's behalf, so an automatic fix is never invisible.
    """
    cur = list(stitches)
    for op in ops:
        kind = op.get("op")
        if kind not in OPS:
            raise EditError(f"Unknown edit operation '{kind}'.")
        try:
            cur = OPS[kind](cur, op)
        except EditError:
            raise
        except (KeyError, TypeError) as exc:
            raise EditError(f"Operation '{kind}' is missing a required value: {exc}") from exc

    notes: list[str] = []
    before = len(cur)
    cur = _subdivide_over_limit(cur)
    if len(cur) != before:
        notes.append(
            f"{len(cur) - before} stitch(es) were added to split moves longer than "
            f"the machine's {MACHINE_MAX_MM}mm reach."
        )
    cur, dropped = _normalise_controls(cur)
    if dropped > 0:
        notes.append(f"{dropped} redundant control command(s) were removed.")
    return cur, notes


def stream_stats(stitches: list[Stitch]) -> dict:
    """Counters the editor panel shows beside the selection."""
    cmds = [_cmd(s) for s in stitches]
    longest = 0.0
    over = 0
    prev = None
    for s in stitches:
        if prev is not None and _cmd(s) in (StitchCommand.STITCH, StitchCommand.JUMP):
            d = math.hypot(s.x - prev.x, s.y - prev.y)
            longest = max(longest, d)
            if d > MACHINE_MAX_MM:
                over += 1
        if _cmd(s) is not StitchCommand.END:
            prev = s
    return {
        "total": len(stitches),
        "stitches": cmds.count(StitchCommand.STITCH),
        "jumps": cmds.count(StitchCommand.JUMP),
        "trims": cmds.count(StitchCommand.TRIM),
        "colorChanges": cmds.count(StitchCommand.COLOR_CHANGE),
        "longestMm": round(longest, 2),
        "overLimit": over,
    }
