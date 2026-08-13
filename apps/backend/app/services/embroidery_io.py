"""Embroidery file read/write — wraps pyembroidery (spec §4.8).

Confirmed against pyembroidery 1.5.1 / Python 3.14:
  - ``pattern.stitches`` -> list of ``[x, y, command_int]``; coords in 1/10 mm.
  - Command ints via ``pe.STITCH`` etc. (mapped below, not hard-coded).
  - ``pattern.get_as_colorblocks()`` -> ``(stitch_list, EmbThread)`` per color stop
    (DST has no stored color, so filler colors are supplied; PES preserves them).
  - ``pattern.bounds()`` -> (minx, miny, maxx, maxy) in 1/10 mm.
"""

from __future__ import annotations

import contextlib
import os
import tempfile

import pyembroidery as pe

from app.models.design import ColorStop, Design, Stitch, enum_str

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

# DST 'LA:' header field width — the DST writer space-pads/truncates to this,
# so names are capped here to keep the stored value predictable.
_DST_NAME_MAX = 16

# PES v1 (pyembroidery's default) truncates the stored name to 8 chars; v6
# keeps the full name (surfaced as extras['name'] on re-read) and is readable
# by modern Brother machines and by pyembroidery itself.
_PES_VERSION = 6

# read_embroidery fallback when a file carries no usable name metadata.
_DEFAULT_IMPORT_NAME = "Imported design"

# VP3 coordinate ceiling: 32767 tenths of a mm (signed 16-bit) = 3276.7mm.
# Held a few mm under the wrap point so a design at the cap still round-trips.
_VP3_MAX_MM = 3270.0


class DesignTooLargeError(ValueError):
    """A design's extent exceeds what the target format can encode.

    MUST stay a ValueError subclass: app/routers/convert.py and app/routers/files.py
    catch ValueError from this module and turn it into a 4xx. Breaking the subclass
    relationship turns those endpoints' responses into 500s.
    """

# Per-format capability table for the 9 formats /api/formats advertises.
#
# 'supports_color' is NOT copied from format documentation — every flag below was
# measured against THIS venv's pyembroidery by writing a 2-color design with
# distinct hexes (#123456 / #abcdef), re-reading it, and comparing. True means the
# written hexes came back recognizably (exact, or snapped to the format's fixed
# thread palette); False means pyembroidery invented random filler colors, which
# _color_stops surfaces as "Color N (file has no color data)".
#
# 'max_width_mm'/'max_height_mm' are the largest stitch-bounds extent this venv's
# pyembroidery can round-trip without corruption; None = none found. Measured by
# writing square designs at 100/200/…/1200mm and again at 2k…100k mm, re-reading,
# and comparing bounds. Only VP3 has a ceiling below 100m (see its row); every
# other advertised format is byte-faithful at 100_000mm, so no *file format*
# limit is honest to report for them. These are container limits, NOT hoop limits
# — a 500mm DST is well-formed and still will not fit any hoop; hoop fit is
# checked separately by POST /api/export/validate.
FORMAT_CAPS: dict[str, dict] = {
    # Tajima DST stores stitches only — no thread table exists in the spec.
    # Measured: hexes come back random. Colors must ship on the worksheet.
    "dst": {
        "label": "Tajima DST",
        "supports_color": False,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Universal machine format. Stitches only — thread colors are not stored in the file.",
    },
    # Brother PES v6 (see _PES_VERSION) embeds a full RGB thread table.
    # Measured: #123456/#abcdef survive byte-exact.
    "pes": {
        "label": "Brother PES",
        "supports_color": True,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Preserves exact thread colors and the design name.",
    },
    # PEC is the stitch block inside PES; its thread table is the fixed 64-color
    # Brother palette. Measured: #123456 -> #134a46, i.e. kept but snapped.
    "pec": {
        "label": "Brother PEC",
        "supports_color": True,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Colors are snapped to Brother's fixed thread palette, so exact hexes shift.",
    },
    # Janome JEF also quantizes to a fixed palette. Measured: #123456 -> #071650.
    "jef": {
        "label": "Janome JEF",
        "supports_color": True,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Colors are snapped to Janome's fixed thread palette, so exact hexes shift.",
    },
    # Melco EXP is a bare stitch stream. Measured: hexes come back random.
    "exp": {
        "label": "Melco EXP",
        "supports_color": False,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Stitches only — thread colors are not stored in the file.",
    },
    # Husqvarna Viking / Pfaff VP3 stores RGB. Measured: hexes survive byte-exact.
    # Size: empirical, pyembroidery 1.5.1 round-trip corrupts above 3276.7mm — the
    # height comes back wrapped (3280mm -> 3273.6mm, 4000mm -> 2553.6mm), i.e. the
    # signed-16-bit tenths-of-mm ceiling (32767 tenths = 3276.7mm). Width survives
    # further but shares the same field, so both axes are capped just under it.
    "vp3": {
        "label": "Husqvarna Viking / Pfaff VP3",
        "supports_color": True,
        "max_width_mm": _VP3_MAX_MM,
        "max_height_mm": _VP3_MAX_MM,
        "note": "Preserves exact thread colors.",
    },
    # Singer XXX: contrary to the common "stitch-only" claim, this pyembroidery
    # build round-trips XXX hexes byte-exact, so the flag is True. Thread NAMES
    # are still lost (descriptions come back blank), only the RGB survives.
    "xxx": {
        "label": "Singer XXX",
        "supports_color": True,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Thread colors survive, but thread names/catalog numbers do not.",
    },
    # Barudan U01 is a stitch stream. Measured: hexes come back random.
    "u01": {
        "label": "Barudan U01",
        "supports_color": False,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Stitches only — thread colors are not stored in the file.",
    },
    # CSV is pyembroidery's text dump; it writes the thread table verbatim.
    # Measured: hexes survive byte-exact. Not a machine format.
    "csv": {
        "label": "Stitch CSV (text)",
        "supports_color": True,
        "max_width_mm": None,
        "max_height_mm": None,
        "note": "Plain-text stitch list for inspection or import into other tools — not a machine file.",
    },
}


def format_capabilities() -> list[dict]:
    """Capability rows for every FORMAT_CAPS entry pyembroidery can actually write.

    A format the library cannot write is dropped rather than advertised, so this
    list can never name a format /api/export would reject with 415.
    """
    writable = supported_write_exts()
    readable = _supported_read_exts()
    return [
        {
            "format": ext,
            "writable": True,
            "readable": ext in readable,
            **caps,
        }
        for ext, caps in FORMAT_CAPS.items()
        if ext in writable
    ]


def _machine_name(name: str | None) -> str:
    """Sanitize a design name for machine-file headers.

    DST/PES header fields are ASCII; non-ASCII bytes corrupt the fixed-width
    DST 'LA:' field, so anything outside printable ASCII is dropped.
    """
    cleaned = (name or "").strip().encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch for ch in cleaned if ch.isprintable()).strip()
    return cleaned[:_DST_NAME_MAX] or "design"


def _stored_name(pattern: pe.EmbPattern) -> str:
    """Design name recovered from a parsed pattern, or the import fallback.

    DST re-reads expose extras['name'] (the 'LA:' field), PES exposes
    extras['Name'] (v1) or extras['name'] (v6).
    """
    extras = getattr(pattern, "extras", None) or {}
    raw = str(extras.get("name") or extras.get("Name") or "").strip()
    # DST writers (pyembroidery included) stamp 'Untitled' into LA: when no name
    # was set — that filler counts as no metadata, not a real name.
    if raw.lower() == "untitled":
        raw = ""
    return raw or _DEFAULT_IMPORT_NAME


def _color_stops(pattern: pe.EmbPattern) -> list[ColorStop]:
    """One ColorStop per color block; empty for a pattern with no stitches."""
    if not pattern.stitches:
        return []
    stops: list[ColorStop] = []
    for i, (block, thread) in enumerate(pattern.get_as_colorblocks(), start=1):
        # Colorless formats (DST/EXP/…) get filler threads that pyembroidery
        # names "Random" — surface an honest name instead of a confusing one.
        desc = getattr(thread, "description", None)
        if not desc or desc.strip().lower() == "random":
            desc = f"Color {i} (file has no color data)"
        stops.append(
            ColorStop(
                stop_number=i,
                thread_brand=(getattr(thread, "brand", None) or "Unknown"),
                catalog_number=(getattr(thread, "catalog_number", None) or ""),
                thread_name=desc,
                hex=(thread.hex_color() if thread is not None else "#808080"),
                # An imported block is a run of needle positions from the file,
                # so its length IS the penetration count. There is no stream
                # span to record: the importer does not emit jumps into a block.
                penetration_count=len(block),
                stream_span=len(block),
            )
        )
    return stops


def _design_extent_mm(design: Design) -> tuple[float, float]:
    """(width, height) in mm from the stitch bounds, or the declared dims if stitchless."""
    if not design.stitches:
        return (design.width_mm or 0.0, design.height_mm or 0.0)
    xs = [s.x for s in design.stitches]
    ys = [s.y for s in design.stitches]
    return (max(xs) - min(xs), max(ys) - min(ys))


def _check_size(design: Design, ext: str) -> None:
    """Reject a design the .``ext`` container cannot encode without corruption.

    Raises DesignTooLargeError so callers get a 4xx instead of a silently wrapped
    file. ``ext`` must already be normalized (lowercase, no leading dot).
    """
    caps = FORMAT_CAPS.get(ext) or {}
    max_w = caps.get("max_width_mm")
    max_h = caps.get("max_height_mm")
    if max_w is None and max_h is None:
        return
    w, h = _design_extent_mm(design)
    if (max_w is not None and w > max_w) or (max_h is not None and h > max_h):
        raise DesignTooLargeError(
            f"Design {w:.0f}x{h:.0f}mm exceeds the .{ext} limit of "
            f"{(max_w or 0):.0f}x{(max_h or 0):.0f}mm"
        )


def _supported_read_exts() -> set[str]:
    """Extensions pyembroidery can read (defensive: falls back to a known set)."""
    exts: set[str] = set()
    # Format discovery must never break the request — any failure falls through
    # to the known-good set below.
    with contextlib.suppress(Exception):
        for fmt in pe.supported_formats():
            ext = fmt.get("extension") if isinstance(fmt, dict) else getattr(fmt, "extension", None)
            reader = fmt.get("reader") if isinstance(fmt, dict) else getattr(fmt, "reader", None)
            if ext and reader is not None:
                exts.add(str(ext).lower())
    if not exts:
        exts = {"dst", "pes", "pec", "jef", "exp", "vp3", "vip", "xxx", "sew", "u01", "csv", "json"}
    return exts


def read_embroidery(data: bytes, ext: str) -> Design:
    """Decode raw embroidery bytes of format ``ext`` into a Design."""
    ext = ext.lower().lstrip(".")
    if ext not in _supported_read_exts():
        raise ValueError(f"Unsupported embroidery format: .{ext}")

    # delete=False + manual unlink: pyembroidery needs a real path after the handle
    # closes, so the auto-deleting context-manager form cannot be used here.
    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)  # noqa: SIM115
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

    return Design(
        name=_stored_name(pattern),
        width_mm=round((maxx - minx) / _TENTHS, 2),
        height_mm=round((maxy - miny) / _TENTHS, 2),
        stitch_count=pattern.count_stitches(),
        color_stops=_color_stops(pattern),
        stitches=stitches,
        status="digitized",
    )


def write_embroidery(design: Design, ext: str) -> bytes:
    """Encode a Design to raw embroidery bytes of format ``ext``."""
    ext = ext.lower().lstrip(".")
    if ext not in supported_write_exts():
        raise ValueError(f"Unsupported export format: .{ext}")
    _check_size(design, ext)

    pattern = pe.EmbPattern()
    for stop in design.color_stops:
        thread = pe.EmbThread()
        # A bad hex string must not abort the export — the thread keeps its default.
        with contextlib.suppress(Exception):
            thread.set_hex_color(stop.hex)
        thread.description = stop.thread_name
        thread.catalog_number = stop.catalog_number
        thread.brand = stop.thread_brand
        pattern.add_thread(thread)

    for s in design.stitches:
        cmd_str = enum_str(s.command)
        pattern.add_stitch_absolute(_STR_TO_CMD.get(cmd_str, pe.STITCH), s.x * _TENTHS, s.y * _TENTHS)

    last = design.stitches[-1].command if design.stitches else None
    last = enum_str(last)
    if last != "END":
        pattern.end()

    # Carry the design name into the machine file (DST 'LA:' field / PES Name).
    pattern.metadata("name", _machine_name(design.name))

    # Same path-after-close constraint as read_embroidery above.
    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)  # noqa: SIM115
    try:
        tmp.close()
        settings = {"pes version": _PES_VERSION} if ext == "pes" else None
        pe.write(pattern, tmp.name, settings)
        with open(tmp.name, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def supported_write_exts() -> set[str]:
    """Extensions pyembroidery can WRITE (public: /api/formats derives its list here).

    Defensive: falls back to a known-good set if format discovery ever breaks.
    """
    exts: set[str] = set()
    with contextlib.suppress(Exception):
        for fmt in pe.supported_formats():
            ext = fmt.get("extension") if isinstance(fmt, dict) else getattr(fmt, "extension", None)
            writer = fmt.get("writer") if isinstance(fmt, dict) else getattr(fmt, "writer", None)
            if ext and writer is not None:
                exts.add(str(ext).lower())
    if not exts:
        exts = {"dst", "pes", "pec", "jef", "exp", "vp3", "csv", "json", "svg", "png"}
    return exts
