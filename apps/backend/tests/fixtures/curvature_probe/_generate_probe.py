"""Generate the curvature probe — a targeted instrument, NOT a bench fixture.

Part 4 §8 flagged an unmeasured risk: boundary-paced satin sets its pitch by the
FASTER of a stroke's two boundaries, so on the inside of a curve the slower
boundary gets its penetrations packed closer than the nominal pitch. Part 4 §11
item 2 asked at what curvature that becomes fabric damage.

No bench fixture answers that, because none bends tightly enough to isolate it.

**Why rings and not hairpins.** The first version of this probe used U-turns of
decreasing radius. It did not work: every open stroke has two terminals, and the
cap columns there land in nearly the same holes, so the minimum was pinned near
zero at *every* radius and the curvature signal was buried. A RING has no
terminals — every penetration is a bend penetration — so the measurement isolates
curvature with nothing else contributing.

The prediction this probe tests is exact. For centreline radius ``R`` and stroke
width ``w``, pacing by the outer boundary makes the inner-side spacing

    pitch x (R - w/2) / (R + w/2)

so each ring below has a closed-form expected value to check the metric against.

    python tests/fixtures/curvature_probe/_generate_probe.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
SIZE = 640
STROKE_PX = 16          # constant stroke width on every ring
INK = (24, 28, 40)
PAPER = (255, 255, 255)
# Centreline radii, in stroke widths. 0.75 is close to the tightest a stroke of
# this width can turn while still enclosing a hole.
RADII_IN_WIDTHS = (8.0, 4.0, 2.0, 1.25, 0.75)


def build() -> list[Path]:
    written = []
    for factor in RADII_IN_WIDTHS:
        radius = STROKE_PX * factor
        img = Image.new("RGB", (SIZE, SIZE), PAPER)
        draw = ImageDraw.Draw(img)
        c = SIZE / 2.0
        draw.ellipse(
            [c - radius, c - radius, c + radius, c + radius],
            outline=INK,
            width=STROKE_PX,
        )
        path = OUT / f"ring_r{str(factor).replace('.', 'p')}w.png"
        img.save(path)
        written.append(path)
    return written


if __name__ == "__main__":
    for f in build():
        print(f"wrote {f}")
