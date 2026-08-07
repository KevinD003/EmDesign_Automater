"""Shared test instruments (v2 Part 66).

Before this file, four test/script files each carried their own copy of the
doubled-angle row instrument, five carried a `_stream` comparator, and twelve
re-digitized the same fixtures under the same seed — the Part 62 file alone
digitized fixture 01 six times. One canonical copy of each lives here, plus a
digitize cache that returns deep copies so no test can poison another.

These are INSTRUMENTS, deliberately independent of the code they measure:
`stream_of` and `row_angle` read only the public Design model.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
QUALITY_BENCH = BACKEND_ROOT / "tests/fixtures/quality_bench"


def stream_of(design):
    """The stitch stream as comparable tuples (command, x, y) at 0.1um."""
    return [(str(s.command), round(s.x, 4), round(s.y, 4)) for s in design.stitches]


def row_angle(design, x0: float, x1: float, y0: float = -1e9, y1: float = 1e9) -> float:
    """Dominant orientation of row segments with midpoints in the given box.

    Length-weighted doubled-angle mean, folded to [0, 180): 179deg and 1deg
    average to 0, not 90. Segments over 1mm only — the short steps between
    fill rows are noise for this purpose.
    """
    c = s2 = 0.0
    prev = None
    for s in design.stitches:
        if str(s.command) != "STITCH":
            prev = None
            continue
        if prev is not None:
            mx, my = (prev[0] + s.x) / 2, (prev[1] + s.y) / 2
            if x0 <= mx <= x1 and y0 <= my <= y1:
                dx, dy = s.x - prev[0], s.y - prev[1]
                length = math.hypot(dx, dy)
                if length > 1.0:
                    th = math.atan2(dy, dx)
                    c += math.cos(2 * th) * length
                    s2 += math.sin(2 * th) * length
        prev = (s.x, s.y)
    return math.degrees(0.5 * math.atan2(s2, c)) % 180.0


def angle_err(got: float, want: float) -> float:
    """Angular error on the fold: |179 - 1| is 2 degrees, not 178."""
    return abs((got - want + 90) % 180 - 90)


@lru_cache(maxsize=8)
def _digitize_cached(fixture_name: str, colors: int):
    import cv2

    from app.services.digitizer import digitize_image

    cv2.setRNGSeed(1234)
    return digitize_image((QUALITY_BENCH / fixture_name).read_bytes(),
                          "cotton", "100x100", colors)


def digitized_fixture(fixture_name: str = "01_flat_2color_logo.png", colors: int = 2):
    """Seeded digitize of a bench fixture, cached across tests.

    Returns a DEEP COPY on every call: the cache cuts repeated ~10s digitizes
    out of the suite, the copy keeps one test's mutation from reaching the
    next — cheaper than the digitize it replaces by two orders of magnitude.
    """
    return _digitize_cached(fixture_name, colors).model_copy(deep=True)
