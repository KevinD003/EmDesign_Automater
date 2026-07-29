"""Generate the junction probe — the adversarial case Part 4 §11.3 asked for.

Part 4's boundary partition assigns every boundary pixel to its NEAREST medial-axis
branch. Part 4 §9.3 predicted that a sufficiently asymmetric junction would break
it, and Part 6 §4 showed the consequence on real lettering once the penetration
floor stopped the overdraw from hiding it.

These shapes are built to break it on purpose, varying the two things the Voronoi
partition is sensitive to:

  * **thickness ratio** — a hairline meeting a thick stem. The nearest-branch
    boundary between them sits far from the hairline's own axis, so a long run of
    the STEM's boundary is closer to the hairline branch than to the stem branch
    and gets handed to it.
  * **meeting angle** — the sharper the angle, the further along the stem that
    mis-assigned run reaches, and the harder the hairline's arc doubles back.

An arc that doubles back stalls: its arc-length parameter stops advancing (or
reverses) while the opposite arc keeps going, so `_pace_by_boundary` piles
columns onto the stalled station. Before Part 6 those piled columns overlapped
and papered over the gap; with the floor on they are dropped and the gap shows.

Kept OUT of `tests/fixtures/quality_bench/` — that corpus is the ten-fixture
regression baseline every audit since Part 0 diffs against.

    python tests/fixtures/junction_probe/_generate_probe.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
SIZE = 640
INK = (24, 28, 40)
PAPER = (255, 255, 255)

# Both strokes must stay UNDER the satin width cap, or the classifier sends the
# stem to tatami and the junction never reaches the satin path this probe exists
# to exercise. At 640px on a 100mm hoop, 24px is 3.75mm — inside the 4.5mm cap.
STEM_PX = 24
# (name, thin-stroke width in px, angle from the stem in degrees)
CASES = (
    ("hairline_30deg", 4, 30),      # worst case: 6:1 thickness, very sharp
    ("hairline_60deg", 4, 60),
    ("medium_30deg", 10, 30),       # 2.4:1 thickness, same sharp angle
    ("equal_30deg", 24, 30),        # control: symmetric junction, should be fine
)


def _draw(draw: ImageDraw.ImageDraw, thin_px: int, angle_deg: int) -> None:
    """A vertical thick stem with a thinner branch leaving it at `angle_deg`."""
    cx, top, bottom = SIZE * 0.42, 90.0, SIZE - 90.0
    draw.line([(cx, top), (cx, bottom)], fill=INK, width=STEM_PX)
    # The branch leaves the stem at mid-height, going up and to the right.
    joint = (cx, (top + bottom) * 0.55)
    reach = SIZE * 0.42
    rad = math.radians(angle_deg)
    tip = (joint[0] + reach * math.sin(rad), joint[1] - reach * math.cos(rad))
    draw.line([joint, tip], fill=INK, width=thin_px)


def build() -> list[Path]:
    written = []
    for name, thin_px, angle in CASES:
        img = Image.new("RGB", (SIZE, SIZE), PAPER)
        _draw(ImageDraw.Draw(img), thin_px, angle)
        path = OUT / f"{name}.png"
        img.save(path)
        written.append(path)
    return written


if __name__ == "__main__":
    for f in build():
        print(f"wrote {f}")
