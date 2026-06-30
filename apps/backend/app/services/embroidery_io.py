"""Embroidery file read/write — wraps pyembroidery (spec §4.8).

Scaffold stub. ``pyembroidery`` is imported lazily inside the functions so the app
boots even before the feature dependencies are installed.
"""

from __future__ import annotations

from app.models.design import Design


def read_embroidery(data: bytes, fmt: str) -> Design:
    """Decode raw embroidery bytes of format ``fmt`` into a Design.

    TODO:
        import pyembroidery
        pattern = pyembroidery.read(...)        # from data + fmt
        # map pattern.stitches -> Design.stitches (1/10mm -> mm)
        # map pattern.threadlist -> Design.color_stops
    """
    raise NotImplementedError("read_embroidery — scaffold stub (spec §4.8)")


def write_embroidery(design: Design, fmt: str) -> bytes:
    """Encode a Design to raw embroidery bytes of format ``fmt``.

    TODO:
        import pyembroidery
        pattern = pyembroidery.EmbPattern()
        # build pattern from design.stitches + color_stops, then write_<fmt> to bytes
    """
    raise NotImplementedError("write_embroidery — scaffold stub (spec §4.8)")
