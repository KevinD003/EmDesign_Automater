"""Generate committed sample embroidery fixtures for tests + manual UI use.

Run from apps/backend (venv active):  python tests/make_fixtures.py
Produces tests/fixtures/sample.dst and sample.pes — a 2-color ~40mm design.
No copyrighted artwork: geometry is generated programmatically.
"""

from __future__ import annotations

import os

import pyembroidery as pe

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def build_sample() -> pe.EmbPattern:
    p = pe.EmbPattern()

    red = pe.EmbThread()
    red.set_color(200, 30, 40)
    red.description, red.brand, red.catalog_number = "Red", "Madeira", "1147"
    blue = pe.EmbThread()
    blue.set_color(30, 60, 200)
    blue.description, blue.brand, blue.catalog_number = "Blue", "Madeira", "1733"

    # Color 1 — a 400x400 (1/10mm = 40mm) square, filled with horizontal rows (boustrophedon).
    p.add_thread(red)
    y, left = 0, True
    while y <= 400:
        xs = (0, 400) if left else (400, 0)
        p.add_stitch_absolute(pe.STITCH, xs[0], y)
        p.add_stitch_absolute(pe.STITCH, xs[1], y)
        y, left = y + 40, not left

    # Color 2 — a diagonal cross.
    p.color_change()
    p.add_thread(blue)
    p.add_stitch_absolute(pe.STITCH, 0, 0)
    p.add_stitch_absolute(pe.STITCH, 400, 400)
    p.trim()
    p.add_stitch_absolute(pe.STITCH, 400, 0)
    p.add_stitch_absolute(pe.STITCH, 0, 400)
    p.end()
    return p


def main() -> None:
    os.makedirs(FIXTURES, exist_ok=True)
    p = build_sample()
    pe.write_dst(p, os.path.join(FIXTURES, "sample.dst"))
    pe.write_pes(p, os.path.join(FIXTURES, "sample.pes"))
    print("Wrote", os.path.join(FIXTURES, "sample.dst"), "and sample.pes")


if __name__ == "__main__":
    main()
