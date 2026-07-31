"""Generate the swarm synthetic mini-corpus — deterministic, copyright-free breadth fixtures.

Eight small PNGs, each isolating one digitizer stress axis (palette quantization,
continuous tone, sub-stitchable detail, max fill, thin outlines, palette overflow,
low contrast, mixed classification). All geometry is drawn programmatically with
cv2 + numpy, so nothing here is derived from copyrighted artwork.

Run from apps/backend:

    .venv/bin/python tests/fixtures/swarm_corpus/_generate.py

Re-running produces byte-identical files (PNG carries no timestamp and every
random draw is seeded), so the committed PNGs can be diffed against a fresh
generation to detect drift — see tests/test_swarm_qa_corpus_gen.py.
"""

from __future__ import annotations

import os

import cv2
import numpy as np

# Single seed for every stochastic builder; changing it rewrites committed bytes.
SEED = 20260729

# Every image must land inside this side-length band (task contract: 400-800px).
MIN_SIDE_PX = 400
MAX_SIDE_PX = 800

WHITE = (255, 255, 255)

# FONT_HERSHEY_SIMPLEX at this scale measures ~11px tall — deliberately below the
# ~2mm minimum stitchable stroke so the digitizer must drop or degrade the glyphs.
TINY_TEXT_SCALE = 0.4
TINY_TEXT = "STITCH IQ 123"

# 04_huge_fill: fraction of each axis the solid region spans. 0.94^2 = 88% > 80%.
HUGE_FILL_AXIS_FRACTION = 0.94

# 07_low_contrast: two grays exactly 12 levels apart sitting on a near-white field.
LOW_CONTRAST_BG = 250
LOW_CONTRAST_LIGHT = 238
LOW_CONTRAST_DARK = LOW_CONTRAST_LIGHT - 12

# Exact (height, width) each builder emits, asserted by the corpus test.
EXPECTED_SIZES: dict[str, tuple[int, int]] = {
    "01_gradient_blob.png": (512, 512),
    "02_photo_like.png": (480, 640),
    "03_tiny_text.png": (400, 400),
    "04_huge_fill.png": (600, 600),
    "05_thin_outlines.png": (700, 700),
    "06_many_colors.png": (512, 512),
    "07_low_contrast.png": (500, 500),
    "08_mixed_scene.png": (600, 800),
}


def build_01_gradient_blob() -> np.ndarray:
    """Smooth radial gradient with one solid blob — stresses palette quantization."""
    size = 512
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    centre = (size - 1) / 2.0
    radius = np.hypot(xx - centre, yy - centre) / (size / 2.0)
    ramp = np.clip(1.0 - radius, 0.0, 1.0)
    img = np.empty((size, size, 3), np.uint8)
    # Distinct per-channel slopes so quantizers see a genuine 3-D color cloud.
    img[:, :, 0] = (60 + 180 * ramp).astype(np.uint8)
    img[:, :, 1] = (40 + 140 * ramp**2).astype(np.uint8)
    img[:, :, 2] = (200 - 120 * ramp).astype(np.uint8)
    cv2.circle(img, (200, 220), 90, (30, 30, 30), thickness=-1)
    return img


def _octave_noise(rng: np.random.Generator, height: int, width: int, octaves: int) -> np.ndarray:
    """Perlin-ish value noise: upsampled random lattices summed at halving amplitude."""
    acc = np.zeros((height, width), np.float32)
    amplitude = 1.0
    for octave in range(octaves):
        cells = 2 ** (octave + 2)
        lattice = rng.random((cells, cells), dtype=np.float32)
        layer = cv2.resize(lattice, (width, height), interpolation=cv2.INTER_CUBIC)
        acc += amplitude * layer
        amplitude *= 0.5
    return cv2.normalize(acc, None, 0.0, 1.0, cv2.NORM_MINMAX)


def build_02_photo_like() -> np.ndarray:
    """Blurred multi-octave noise plus a few solid shapes — photo-like continuous tone."""
    height, width = 480, 640
    rng = np.random.default_rng(SEED)
    channels = [_octave_noise(rng, height, width, octaves=5) for _ in range(3)]
    img = np.stack([(40 + 200 * c).astype(np.uint8) for c in channels], axis=2)
    # Blur kernel is odd and fixed so the output stays reproducible across runs.
    img = cv2.GaussianBlur(img, (9, 9), sigmaX=3.0)
    cv2.circle(img, (150, 150), 70, (20, 40, 180), thickness=-1)
    cv2.rectangle(img, (380, 260), (560, 400), (180, 120, 30), thickness=-1)
    cv2.ellipse(img, (330, 120), (110, 45), 25, 0, 360, (30, 160, 90), thickness=-1)
    return img


def build_03_tiny_text() -> np.ndarray:
    """'STITCH IQ 123' rendered at ~10px — detail below the stitchable floor."""
    size = 400
    img = np.full((size, size, 3), 255, np.uint8)
    (text_w, text_h), _ = cv2.getTextSize(TINY_TEXT, cv2.FONT_HERSHEY_SIMPLEX, TINY_TEXT_SCALE, 1)
    # Three rows at different x offsets so no result depends on a single placement.
    for row, x_offset in enumerate((40, 120, 200)):
        origin = (x_offset, 120 + row * (text_h + 40))
        cv2.putText(
            img, TINY_TEXT, origin, cv2.FONT_HERSHEY_SIMPLEX, TINY_TEXT_SCALE, (20, 20, 20), 1,
            cv2.LINE_AA,
        )
    # One anchor rectangle guarantees at least one comfortably stitchable region.
    cv2.rectangle(img, (40, 300), (40 + text_w, 340), (150, 60, 20), thickness=-1)
    return img


def build_04_huge_fill() -> np.ndarray:
    """One solid region covering >80% of the frame — maximum fill area."""
    size = 600
    img = np.full((size, size, 3), 255, np.uint8)
    span = int(size * HUGE_FILL_AXIS_FRACTION)
    margin = (size - span) // 2
    cv2.rectangle(img, (margin, margin), (margin + span, margin + span), (70, 90, 200), -1)
    return img


def build_05_thin_outlines() -> np.ndarray:
    """1-2px unfilled circle, star and spiral — satin/runner edge cases."""
    size = 700
    img = np.full((size, size, 3), 255, np.uint8)
    cv2.circle(img, (170, 170), 120, (30, 30, 30), thickness=1)
    star_angles = np.arange(5) * (4 * np.pi / 5) - np.pi / 2
    star = np.stack(
        [520 + 130 * np.cos(star_angles), 180 + 130 * np.sin(star_angles)], axis=1
    ).astype(np.int32)
    cv2.polylines(img, [star], isClosed=True, color=(180, 40, 40), thickness=2)
    # Archimedean spiral: r grows 9px per radian over 5 turns, sampled every 0.05 rad.
    theta = np.arange(0.0, 5 * 2 * np.pi, 0.05)
    spiral = np.stack(
        [350 + 9 * theta * np.cos(theta), 500 + 9 * theta * np.sin(theta)], axis=1
    ).astype(np.int32)
    cv2.polylines(img, [spiral], isClosed=False, color=(40, 90, 30), thickness=1)
    return img


def build_06_many_colors() -> np.ndarray:
    """16-swatch patchwork grid — deliberately exceeds the default max_colors=6."""
    size = 512
    cells = 4  # 4x4 = 16 distinct swatches
    img = np.empty((size, size, 3), np.uint8)
    step = size // cells
    for index in range(cells * cells):
        row, col = divmod(index, cells)
        # Widely separated BGR triples so quantization cannot merge them by accident.
        color = (
            30 + (index % 4) * 70,
            25 + ((index // 4) % 4) * 70,
            20 + ((index * 5) % 4) * 70,
        )
        top_left = (col * step, row * step)
        bottom_right = ((col + 1) * step, (row + 1) * step)
        cv2.rectangle(img, top_left, bottom_right, color, thickness=-1)
    return img


def build_07_low_contrast() -> np.ndarray:
    """Two grays 12 levels apart on near-white — threshold/segmentation stress."""
    size = 500
    img = np.full((size, size, 3), LOW_CONTRAST_BG, np.uint8)
    light = (LOW_CONTRAST_LIGHT,) * 3
    dark = (LOW_CONTRAST_DARK,) * 3
    cv2.rectangle(img, (60, 60), (240, 440), light, thickness=-1)
    cv2.rectangle(img, (260, 60), (440, 440), dark, thickness=-1)
    cv2.circle(img, (150, 250), 60, dark, thickness=-1)
    cv2.circle(img, (350, 250), 60, light, thickness=-1)
    return img


def build_08_mixed_scene() -> np.ndarray:
    """Thick bar, thin diagonal, small text and a gradient corner — classifier interaction."""
    height, width = 600, 800
    img = np.full((height, width, 3), 255, np.uint8)
    # Gradient corner occupies the top-left quadrant only; rest stays flat white.
    quad_h, quad_w = height // 2, width // 2
    ramp = np.linspace(0.0, 1.0, quad_w, dtype=np.float32)[None, :].repeat(quad_h, axis=0)
    img[:quad_h, :quad_w, 0] = (220 - 150 * ramp).astype(np.uint8)
    img[:quad_h, :quad_w, 1] = (200 - 60 * ramp).astype(np.uint8)
    img[:quad_h, :quad_w, 2] = (120 + 100 * ramp).astype(np.uint8)
    cv2.rectangle(img, (80, 420), (720, 500), (40, 40, 160), thickness=-1)   # thick bar
    cv2.line(img, (540, 60), (760, 380), (30, 120, 40), thickness=2)         # thin diagonal
    cv2.putText(
        img, TINY_TEXT, (90, 560), cv2.FONT_HERSHEY_SIMPLEX, TINY_TEXT_SCALE, (20, 20, 20), 1,
        cv2.LINE_AA,
    )
    return img


BUILDERS = {
    "01_gradient_blob.png": build_01_gradient_blob,
    "02_photo_like.png": build_02_photo_like,
    "03_tiny_text.png": build_03_tiny_text,
    "04_huge_fill.png": build_04_huge_fill,
    "05_thin_outlines.png": build_05_thin_outlines,
    "06_many_colors.png": build_06_many_colors,
    "07_low_contrast.png": build_07_low_contrast,
    "08_mixed_scene.png": build_08_mixed_scene,
}


def generate(out_dir: str | os.PathLike[str] | None = None) -> list[str]:
    """Write all eight corpus PNGs into out_dir (default: this file's directory)."""
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.fspath(out_dir) if out_dir is not None else here
    os.makedirs(target, exist_ok=True)
    written: list[str] = []
    for name, builder in BUILDERS.items():
        img = builder()
        expected = EXPECTED_SIZES[name]
        if img.shape[:2] != expected:
            raise AssertionError(f"{name}: built {img.shape[:2]}, EXPECTED_SIZES says {expected}")
        path = os.path.join(target, name)
        if not cv2.imwrite(path, img):
            raise OSError(f"cv2.imwrite failed for {path}")
        written.append(path)
    return written


def main() -> None:
    for path in generate():
        print("Wrote", path)


if __name__ == "__main__":
    main()
