"""Embroidery file read/write — wraps pyembroidery (spec §4.8).

Confirmed against pyembroidery 1.5.1 / Python 3.14:
  - ``pattern.stitches`` -> list of ``[x, y, command_int]``; coords in 1/10 mm.
  - Command ints via ``pe.STITCH`` etc. (mapped below, not hard-coded).
  - ``pattern.get_as_colorblocks()`` -> ``(stitch_list, EmbThread)`` per color stop
    (DST has no stored color, so filler colors are supplied; PES preserves them).
  - ``pattern.bounds()`` -> (minx, miny, maxx, maxy) in 1/10 mm.
"""

from __future__ import annotations

import os
import tempfile

import pyembroidery as pe

from app.models.design import ColorStop, Design, Stitch

_TENTHS = 10.0  # pyembroidery unit (1/10 mm) -> mm

# pyembroidery command int <-> our StitchCommand string value
_CMD_TO_STR: dict[int, str] = {
    pe.STITCH: "STITCH",
    pe.JUMP: "JUMP",
    pe.TRIM: "TRIM",
    pe.STOP: "STOP",
    pe.END: "END",
    pe.COLOR_CHANGE: "COLOR_CHANGE",
}
_STR_TO_CMD: dict[str, int] = {v: k for k, v in _CMD_TO_STR.items()}


def _supported_read_exts() -> set[str]:
    """Extensions pyembroidery can read (defensive: falls back to a known set)."""
    exts: set[str] = set()
    try:
        for fmt in pe.supported_formats():
            ext = fmt.get("extension") if isinstance(fmt, dict) else getattr(fmt, "extension", None)
            reader = fmt.get("reader") if isinstance(fmt, dict) else getattr(fmt, "reader", None)
            if ext and reader is not None:
                exts.add(str(ext).lower())
    except Exception:  # noqa: BLE001 - never let format discovery break the request
        pass
    if not exts:
        exts = {"dst", "pes", "pec", "jef", "exp", "vp3", "vip", "xxx", "sew", "u01", "csv", "json"}
    return exts


def read_embroidery(data: bytes, ext: str) -> Design:
    """Decode raw embroidery bytes of format ``ext`` into a Design."""
    ext = ext.lower().lstrip(".")
    if ext not in _supported_read_exts():
        raise ValueError(f"Unsupported embroidery format: .{ext}")

    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        pattern = pe.read(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if pattern is None:
        raise ValueError(f"Could not parse .{ext} file")

    stitches = [
        Stitch(x=x / _TENTHS, y=y / _TENTHS, command=_CMD_TO_STR.get(cmd, "STITCH"))
        for x, y, cmd in pattern.stitches
    ]

    if pattern.stitches:
        minx, miny, maxx, maxy = pattern.bounds()
    else:
        minx = miny = maxx = maxy = 0

    color_stops: list[ColorStop] = []
    if pattern.stitches:
        for i, (block, thread) in enumerate(pattern.get_as_colorblocks(), start=1):
            color_stops.append(
                ColorStop(
                    stop_number=i,
                    thread_brand=(getattr(thread, "brand", None) or "Unknown"),
                    catalog_number=(getattr(thread, "catalog_number", None) or ""),
                    thread_name=(getattr(thread, "description", None) or f"Color {i}"),
                    hex=(thread.hex_color() if thread is not None else "#808080"),
                    stitch_count=len(block),
                )
            )

    return Design(
        name="Imported design",
        width_mm=round((maxx - minx) / _TENTHS, 2),
        height_mm=round((maxy - miny) / _TENTHS, 2),
        stitch_count=pattern.count_stitches(),
        color_stops=color_stops,
        stitches=stitches,
        status="digitized",
    )


def write_embroidery(design: Design, ext: str) -> bytes:
    """Encode a Design to raw embroidery bytes of format ``ext``."""
    ext = ext.lower().lstrip(".")
    if ext not in _supported_write_exts():
        raise ValueError(f"Unsupported export format: .{ext}")

    pattern = pe.EmbPattern()
    for stop in design.color_stops:
        thread = pe.EmbThread()
        try:
            thread.set_hex_color(stop.hex)
        except Exception:  # noqa: BLE001 - bad hex shouldn't abort the export
            pass
        thread.description = stop.thread_name
        thread.catalog_number = stop.catalog_number
        thread.brand = stop.thread_brand
        pattern.add_thread(thread)

    for s in design.stitches:
        cmd_str = s.command.value if hasattr(s.command, "value") else s.command
        pattern.add_stitch_absolute(_STR_TO_CMD.get(cmd_str, pe.STITCH), s.x * _TENTHS, s.y * _TENTHS)

    last = design.stitches[-1].command if design.stitches else None
    last = last.value if hasattr(last, "value") else last
    if last != "END":
        pattern.end()

    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
    try:
        tmp.close()
        pe.write(pattern, tmp.name)
        with open(tmp.name, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _supported_write_exts() -> set[str]:
    exts: set[str] = set()
    try:
        for fmt in pe.supported_formats():
            ext = fmt.get("extension") if isinstance(fmt, dict) else getattr(fmt, "extension", None)
            writer = fmt.get("writer") if isinstance(fmt, dict) else getattr(fmt, "writer", None)
            if ext and writer is not None:
                exts.add(str(ext).lower())
    except Exception:  # noqa: BLE001
        pass
    if not exts:
        exts = {"dst", "pes", "pec", "jef", "exp", "vp3", "csv", "json", "svg", "png"}
    return exts
