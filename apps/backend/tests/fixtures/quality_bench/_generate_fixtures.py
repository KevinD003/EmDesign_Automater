"""Generate the quality-bench fixture images (Part 0 harness).

Every fixture is drawn programmatically here, so the bench corpus is **original
art with no licensing question** and is byte-reproducible on any machine: delete
the PNGs, re-run this file, get the same inputs back.

    python tests/fixtures/quality_bench/_generate_fixtures.py

The ten fixtures deliberately span the cases the digitizer is expected to handle
well AND the ones STATUS.md §9/§12 documents as weak (non-uniform background,
low-contrast subject, fine detail, script lettering), so the baseline audit has
something real to fail at rather than ten variations of "big flat shape".
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent
SIZE = 640  # square canvas for every fixture

# Fonts present on Debian/Ubuntu images (fonts-liberation, fonts-freefont-ttf).
# NOTE: no CC0 *script/cursive* face ships with the base image, so the "script"
# fixture uses a true serif italic — thin, modulated strokes with fine terminals,
# which stresses the same classifier path. Called out in the audit doc.
FONT_SANS_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_SANS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_SCRIPTISH = [
    "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _centered(draw: ImageDraw.ImageDraw, xy, text: str, font, fill) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (right - left) / 2 - left, xy[1] - (bottom - top) / 2 - top), text, font=font, fill=fill)


def _canvas(bg=(255, 255, 255)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (SIZE, SIZE), bg)
    return img, ImageDraw.Draw(img)


# ── 1. flat two-color geometric logo ─────────────────────────────────────────
def flat_2color_logo() -> Image.Image:
    img, d = _canvas()
    d.ellipse((90, 90, 550, 550), fill=(20, 70, 160))
    d.polygon([(320, 190), (470, 430), (170, 430)], fill=(235, 180, 40))
    return img


# ── 2. three-color logo carrying small text ──────────────────────────────────
def logo_fine_text_3color() -> Image.Image:
    img, d = _canvas()
    d.rounded_rectangle((80, 150, 560, 490), radius=40, fill=(15, 90, 75))
    d.ellipse((250, 205, 390, 345), fill=(240, 195, 60))
    _centered(d, (320, 405), "NORTHFIELD", _font(FONT_SANS_BOLD, 46), (250, 250, 250))
    # Deliberately small type — the case that exposes the speck filter / detail loss.
    _centered(d, (320, 452), "EST. 1974  ·  SUPPLY CO.", _font(FONT_SANS, 20), (250, 250, 250))
    return img


# ── 3. soft-edged gradient subject (photo-like) ──────────────────────────────
def gradient_soft_subject() -> Image.Image:
    """Synthetic photo-like art: a lit sphere with a soft shadow on a plain wall.

    Not a photograph (none can be sourced license-cleanly here), but it carries the
    property that matters — continuous tone with no hard edge to threshold.
    """
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    cx, cy, r = 300.0, 290.0, 200.0
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    # Lambert-ish shading from an upper-left key light.
    lit = np.clip(1.0 - dist / r, 0.0, 1.0)
    normal_z = np.sqrt(np.clip(1.0 - (dist / r) ** 2, 0.0, 1.0))
    shade = np.clip(0.35 + 0.65 * (normal_z * 0.8 + (1 - (xx - cx) / r) * 0.1), 0.0, 1.0)
    inside = (dist <= r).astype(np.float32)

    bg = np.full((SIZE, SIZE, 3), 232.0, np.float32)
    bg -= ((yy / SIZE) * 26.0)[..., None]  # gentle wall falloff
    sphere = np.stack([shade * 225.0, shade * 95.0, shade * 60.0], axis=-1)
    edge = np.clip((r - dist) / 6.0, 0.0, 1.0)[..., None]  # anti-aliased rim
    out = bg * (1 - edge) + sphere * edge
    out *= 1.0 - 0.18 * np.clip(1 - np.abs(dist - r * 1.45) / 90.0, 0, 1)[..., None] * (yy > cy)[..., None]

    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    return img.filter(ImageFilter.GaussianBlur(0.8))


# ── 4. thin-line / outline-style mark ────────────────────────────────────────
def thin_line_outline() -> Image.Image:
    img, d = _canvas()
    ink = (25, 35, 55)
    d.ellipse((110, 110, 530, 530), outline=ink, width=6)
    d.ellipse((155, 155, 485, 485), outline=ink, width=3)
    # A thin open compass rose — strokes near the satin/running-stitch boundary.
    for k in range(8):
        a = k * math.pi / 4
        d.line(
            (320 + 60 * math.cos(a), 320 + 60 * math.sin(a), 320 + 150 * math.cos(a), 320 + 150 * math.sin(a)),
            fill=ink,
            width=4,
        )
    d.ellipse((285, 285, 355, 355), outline=ink, width=5)
    return img


# ── 5. all-caps sans wordmark ────────────────────────────────────────────────
def wordmark_caps() -> Image.Image:
    img, d = _canvas()
    _centered(d, (320, 320), "SUMMIT", _font(FONT_SANS_BOLD, 150), (18, 24, 38))
    return img


# ── 6. lowercase script-style wordmark ───────────────────────────────────────
def wordmark_script() -> Image.Image:
    img, d = _canvas()
    _centered(d, (320, 320), "Bellamy", _font(FONT_SCRIPTISH, 150), (95, 25, 70))
    return img


# ── 7. circular badge / crest ────────────────────────────────────────────────
def circular_badge() -> Image.Image:
    img, d = _canvas()
    navy, gold, cream = (18, 40, 85), (215, 165, 45), (248, 244, 232)
    d.ellipse((60, 60, 580, 580), fill=navy)
    d.ellipse((92, 92, 548, 548), outline=gold, width=8)
    d.ellipse((140, 140, 500, 500), fill=cream)
    # five-point star
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rad = 110 if k % 2 == 0 else 46
        pts.append((320 + rad * math.cos(a), 300 + rad * math.sin(a)))
    d.polygon(pts, fill=navy)
    _centered(d, (320, 432), "HARBOR CLUB", _font(FONT_SANS_BOLD, 34), navy)
    # curved-ish top text approximated with per-glyph rotation
    label, font = "· ESTABLISHED 1908 ·", _font(FONT_SANS_BOLD, 26)
    for i, ch in enumerate(label):
        a = math.radians(-150 + i * (120 / max(len(label) - 1, 1)))
        glyph = Image.new("RGBA", (44, 44), (0, 0, 0, 0))
        _centered(ImageDraw.Draw(glyph), (22, 22), ch, font, gold + (255,))
        glyph = glyph.rotate(-math.degrees(a) - 90, resample=Image.BICUBIC)
        img.paste(glyph, (int(320 + 210 * math.cos(a)) - 22, int(320 + 210 * math.sin(a)) - 22), glyph)
    return img


# ── 8. high-detail mascot with many small regions ────────────────────────────
def mascot_detail() -> Image.Image:
    img, d = _canvas()
    orange, dark, cream, pink = (222, 108, 38), (48, 34, 30), (250, 240, 224), (214, 128, 132)
    d.polygon([(150, 250), (205, 110), (268, 215)], fill=orange)   # ears
    d.polygon([(490, 250), (435, 110), (372, 215)], fill=orange)
    d.polygon([(168, 243), (208, 148), (252, 216)], fill=pink)
    d.polygon([(472, 243), (432, 148), (388, 216)], fill=pink)
    d.ellipse((150, 190, 490, 500), fill=orange)                    # head
    d.ellipse((205, 300, 435, 480), fill=cream)                     # muzzle
    for x in (258, 382):                                            # eyes
        d.ellipse((x - 34, 262, x + 34, 322), fill=cream)
        d.ellipse((x - 19, 274, x + 19, 312), fill=dark)
        d.ellipse((x - 12, 280, x - 1, 292), fill=(255, 255, 255))
    d.polygon([(320, 350), (348, 374), (292, 374)], fill=dark)      # nose
    d.line((320, 374, 320, 398), fill=dark, width=5)
    d.arc((272, 380, 320, 424), 0, 180, fill=dark, width=5)         # mouth
    d.arc((320, 380, 368, 424), 0, 180, fill=dark, width=5)
    for sx, sy in ((196, 356), (188, 380), (196, 404)):             # whiskers
        d.line((sx, sy, sx - 58, sy - 12), fill=dark, width=4)
        d.line((640 - sx, sy, 640 - sx + 58, sy - 12), fill=dark, width=4)
    for i in range(5):                                              # brow freckles
        d.ellipse((236 + i * 34, 232, 246 + i * 34, 242), fill=dark)
    return img


# ── 9. subject on a NON-UNIFORM background (documented failure mode) ─────────
def nonuniform_background() -> Image.Image:
    """The corner-average background heuristic (digitizer._is_background) assumes a
    flat backdrop. Here the backdrop is a two-tone diagonal gradient with texture,
    so each corner reads as a different color."""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    t = (xx + yy) / (2.0 * SIZE)
    bg = np.stack(
        [80 + 150 * t, 140 + 60 * (1 - t), 210 - 120 * t], axis=-1
    )
    rng = np.random.default_rng(7)
    bg += rng.normal(0.0, 7.0, bg.shape)  # film-grain texture
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.polygon([(320, 150), (470, 320), (320, 490), (170, 320)], fill=(235, 60, 70))  # diamond
    d.ellipse((280, 280, 360, 360), fill=(252, 246, 230))
    return img


# ── 10. low-contrast subject (probes the ΔBGR < 40 background cut) ───────────
def low_contrast_subject() -> Image.Image:
    """Subject sits ~30 BGR units from the backdrop — inside digitizer's 40.0
    'this cluster is background' radius, so the subject is at risk of being
    dropped entirely."""
    img, d = _canvas(bg=(205, 205, 198))
    d.ellipse((120, 120, 520, 520), fill=(178, 180, 176))
    d.rounded_rectangle((215, 215, 425, 425), radius=24, fill=(160, 164, 162))
    _centered(d, (320, 320), "LC", _font(FONT_SANS_BOLD, 96), (140, 146, 144))
    return img


FIXTURES = {
    "01_flat_2color_logo": flat_2color_logo,
    "02_logo_fine_text_3color": logo_fine_text_3color,
    "03_gradient_soft_subject": gradient_soft_subject,
    "04_thin_line_outline": thin_line_outline,
    "05_wordmark_caps": wordmark_caps,
    "06_wordmark_script": wordmark_script,
    "07_circular_badge": circular_badge,
    "08_mascot_detail": mascot_detail,
    "09_nonuniform_background": nonuniform_background,
    "10_low_contrast_subject": low_contrast_subject,
}


def main() -> None:
    for name, fn in FIXTURES.items():
        path = OUT / f"{name}.png"
        fn().save(path)
        print(f"wrote {path.relative_to(OUT.parents[3])}")


if __name__ == "__main__":
    main()
