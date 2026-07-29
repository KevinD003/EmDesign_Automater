"""Generate the letter probe — sharp apexes with SHORT arms (v2 Part 8).

Part 7 §7 item 5 asked for this. The existing `junction_probe` shapes have long
clean arms meeting at a point, and Part 7 §5 found that they prove the mechanism
but do not reproduce the corpus's cost: with arms that long, the junction is a
negligible fraction of the area, so a real apex defect barely moves the numbers.

These shapes invert that ratio. Short arms, sharp apexes, drawn at the same
stroke width and hoop scale as the bench wordmarks, so the apex region is a large
enough share of each shape that apex coverage is readable directly off the
interior percentage — no full-corpus run and no manual pixel painting needed.

  * ``apex_M``  — two chevrons, the classic 'M' vertex, both up and down.
  * ``apex_V``  — a single sharp vertex, the simplest possible case.
  * ``apex_U``  — a round join, the control: a bowl has no sharp apex, so its
    interior should stay high whatever happens to the sharp cases.
  * ``apex_narrow`` — a very acute vertex (~28°), where the unreachable triangle
    above the axis terminal is largest.

Kept OUT of `tests/fixtures/quality_bench/` — that corpus is the ten-fixture
regression baseline every audit since Part 0 diffs against.

    python tests/fixtures/letter_probe/_generate_probe.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
SIZE = 320
INK = (24, 28, 40)
PAPER = (255, 255, 255)
# 12px at 320px on a 100mm hoop is 3.75mm — the same stroke weight as the bench
# wordmarks, and inside the 4.5mm satin cap so these reach the satin path.
STROKE_PX = 12


def _chevron(draw, apex, half_span, height, up=True):
    """A single V (or ^), i.e. two arms meeting at one sharp apex."""
    dy = -height if up else height
    draw.line(
        [(apex[0] - half_span, apex[1] - dy), apex, (apex[0] + half_span, apex[1] - dy)],
        fill=INK, width=STROKE_PX, joint="curve",
    )


def _draw_m(draw):
    """'M'-like: down-up-down-up, so the image carries two sharp apexes of each sense."""
    _chevron(draw, (110, 90), 50, 110, up=True)
    _chevron(draw, (210, 230), 50, 110, up=False)


def _draw_v(draw):
    _chevron(draw, (160, 240), 75, 150, up=False)


def _draw_u(draw):
    """Control: a bowl. Same footprint, no sharp apex."""
    draw.arc([70, 60, 250, 250], start=0, end=180, fill=INK, width=STROKE_PX)
    draw.line([(70, 155), (70, 90)], fill=INK, width=STROKE_PX)
    draw.line([(250, 155), (250, 90)], fill=INK, width=STROKE_PX)


def _draw_narrow(draw):
    """A very acute vertex: the unreachable apex triangle is largest here."""
    half_span = 40
    height = 155
    print(f"    apex_narrow interior angle = {2 * math.degrees(math.atan2(half_span, height)):.1f} deg")
    _chevron(draw, (160, 250), half_span, height, up=False)


SHAPES = {"apex_M": _draw_m, "apex_V": _draw_v, "apex_U": _draw_u, "apex_narrow": _draw_narrow}


def build() -> list[Path]:
    written = []
    for name, fn in SHAPES.items():
        img = Image.new("RGB", (SIZE, SIZE), PAPER)
        fn(ImageDraw.Draw(img))
        path = OUT / f"{name}.png"
        img.save(path)
        written.append(path)
    return written


if __name__ == "__main__":
    for f in build():
        print(f"wrote {f}")
