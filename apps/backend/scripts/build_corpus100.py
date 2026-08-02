"""Build the 100-design stress corpus (v2 Part 36).

HONEST PROVENANCE — read this before trusting any number measured on it.
This environment has no outbound access to image hosts, so 100 *distinct*
real-world embroidery designs could not be downloaded. The corpus is instead
built from everything genuinely available, in three labelled tiers:

  A. REAL (13)     — the 3 user-supplied embroidery images (a photographed
                     peacock patch, a floral neckline on black, a full-length
                     neckline panel) plus the 10 existing quality-bench
                     fixtures.
  B. REAL-DERIVED  — crops, rotations, rescales and recolours of the tier-A
                     photographs. These carry REAL thread texture, real
                     lighting and real artwork structure; only the framing is
                     synthetic. This is the tier that stresses the photo
                     pipeline honestly.
  C. PARAMETRIC    — generated artwork spanning the design classes that are
                     known to be hard (hairline linework, tiny lettering,
                     dense florals, badges with text, gradients, high colour
                     count, long thin borders, isolated specks, big flat
                     areas). Clearly synthetic; useful for finding crashes,
                     floor violations and pathological routing, NOT for
                     claiming real-world fidelity.

Every result table must keep the tier label so nobody reads a tier-C average
as a real-world score.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "corpus100"
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "quality_bench"
SCRATCH = Path(
    "/tmp/claude-0/-home-user-EmDesign-Automater/"
    "f910d63b-9a34-5903-a86c-18657de0753e/scratchpad"
)

RNG = np.random.default_rng(20260802)

PALETTES = [
    [(40, 40, 200), (30, 160, 30), (200, 160, 20), (60, 60, 60)],
    [(180, 60, 40), (40, 120, 200), (240, 220, 60), (250, 250, 250)],
    [(20, 20, 20), (200, 30, 120), (60, 200, 200), (240, 240, 100)],
    [(90, 40, 140), (30, 180, 90), (240, 140, 30), (30, 30, 30)],
]


def _write(name: str, img, tier: str, cls: str, meta: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / f"{name}.png"), img)
    meta.append({"name": name, "tier": tier, "class": cls})


# ── Tier A: the genuine articles ────────────────────────────────────────────


def tier_a(meta: list) -> list:
    reals = []
    for src, name in [
        (SCRATCH / "peacock.png", "A01_real_peacock_patch_photo"),
        (SCRATCH / "neckline.jpg", "A02_real_neckline_black"),
        (SCRATCH / "neckline2.jpg", "A03_real_neckline_panel"),
    ]:
        if src.exists():
            img = cv2.imread(str(src))
            if img is not None:
                _write(name, img, "A-real", "user-supplied embroidery", meta)
                reals.append(img)
    for f in sorted(FIXTURES.glob("*.png")):
        img = cv2.imread(str(f))
        if img is not None:
            _write(f"A_fixture_{f.stem}", img, "A-real", "quality-bench fixture", meta)
    return reals


# ── Tier B: real-derived (real texture, synthetic framing) ──────────────────


def tier_b(reals: list, meta: list, count: int) -> None:
    if not reals:
        return
    ops = ["crop", "rotate", "scale", "recolour", "crop_rot", "lowlight"]
    for i in range(count):
        base = reals[i % len(reals)].copy()
        op = ops[i % len(ops)]
        h, w = base.shape[:2]
        if op in ("crop", "crop_rot"):
            cw = int(w * RNG.uniform(0.35, 0.75))
            ch = int(h * RNG.uniform(0.35, 0.75))
            x = int(RNG.integers(0, max(1, w - cw)))
            y = int(RNG.integers(0, max(1, h - ch)))
            base = base[y : y + ch, x : x + cw]
            if op == "crop_rot":
                ang = float(RNG.uniform(-30, 30))
                m = cv2.getRotationMatrix2D((base.shape[1] / 2, base.shape[0] / 2), ang, 1)
                base = cv2.warpAffine(
                    base, m, (base.shape[1], base.shape[0]), borderMode=cv2.BORDER_REPLICATE
                )
        elif op == "rotate":
            k = int(RNG.integers(1, 4))
            base = np.rot90(base, k).copy()
        elif op == "scale":
            f = float(RNG.uniform(0.3, 0.8))
            base = cv2.resize(base, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        elif op == "recolour":
            hsv = cv2.cvtColor(base, cv2.COLOR_BGR2HSV).astype(np.int16)
            hsv[..., 0] = (hsv[..., 0] + int(RNG.integers(20, 140))) % 180
            base = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
        elif op == "lowlight":
            base = np.clip(base.astype(np.float32) * RNG.uniform(0.35, 0.6), 0, 255).astype(
                np.uint8
            )
        _write(f"B{i:02d}_{op}", base, "B-real-derived", f"real photo, {op}", meta)


# ── Tier C: parametric classes ──────────────────────────────────────────────


def _canvas(w=520, h=520, bg=(255, 255, 255)):
    return np.full((h, w, 3), bg, np.uint8)


def _flower(img, cx, cy, r, petal, centre, n=6):
    for k in range(n):
        a = 2 * math.pi * k / n
        cv2.circle(img, (int(cx + r * 0.7 * math.cos(a)), int(cy + r * 0.7 * math.sin(a))),
                   int(r * 0.45), petal, -1)
    cv2.circle(img, (cx, cy), int(r * 0.35), centre, -1)


def tier_c(meta: list, count: int) -> None:
    made = 0
    i = 0
    while made < count:
        pal = PALETTES[i % len(PALETTES)]
        cls, img = _generate(i, pal)
        _write(f"C{made:02d}_{cls}", img, "C-parametric", cls, meta)
        made += 1
        i += 1


def _generate(i: int, pal):
    kind = i % 13
    dark = (kind % 3 == 2)
    img = _canvas(bg=(12, 12, 12) if dark else (255, 255, 255))
    h, w = img.shape[:2]

    if kind == 0:  # dense floral spray (the neckline class)
        cls = "dense_floral"
        for k in range(14):
            cx = int(RNG.integers(60, w - 60))
            cy = int(RNG.integers(60, h - 60))
            _flower(img, cx, cy, int(RNG.integers(22, 44)), pal[0], pal[2])
        for k in range(20):
            p1 = (int(RNG.integers(0, w)), int(RNG.integers(0, h)))
            p2 = (p1[0] + int(RNG.integers(-70, 70)), p1[1] + int(RNG.integers(-70, 70)))
            cv2.line(img, p1, p2, pal[1], 4)
    elif kind == 1:  # hairline linework
        cls = "hairline_linework"
        for x in range(20, w - 20, 9):
            cv2.line(img, (x, 20), (x + 40, h - 20), pal[3], 1)
    elif kind == 2:  # lattice trellis on dark (the panel class)
        cls = "lattice_trellis"
        for d in range(-h, w, 46):
            cv2.line(img, (d, 0), (d + h, h), pal[2], 6)
            cv2.line(img, (d + h, 0), (d, h), pal[2], 6)
    elif kind == 3:  # badge with text ring
        cls = "badge_with_text"
        cv2.circle(img, (w // 2, h // 2), 200, pal[0], -1)
        cv2.circle(img, (w // 2, h // 2), 160, pal[3], 8)
        cv2.putText(img, "STITCHIQ", (w // 2 - 130, h // 2 + 10),
                    cv2.FONT_HERSHEY_DUPLEX, 1.4, pal[2], 3)
    elif kind == 4:  # tiny lettering (fine-detail stress)
        cls = "tiny_lettering"
        for r, y in enumerate(range(60, h - 40, 42)):
            cv2.putText(img, "quality embroidery 12345", (30, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45 + r * 0.02, pal[r % 3], 1)
    elif kind == 5:  # smooth gradient (band-recovery stress)
        cls = "gradient_field"
        gx = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
        gy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        a = np.array(pal[0], np.float32)
        b = np.array(pal[1], np.float32)
        img = (a * (1 - gx * gy) + b * (gx * gy)).astype(np.uint8)
        cv2.circle(img, (w // 2, h // 2), 120, tuple(int(v) for v in pal[2]), -1)
    elif kind == 6:  # long thin border
        cls = "thin_border"
        cv2.rectangle(img, (14, 14), (w - 14, h - 14), pal[0], 5)
        cv2.rectangle(img, (34, 34), (w - 34, h - 34), pal[1], 3)
        cv2.rectangle(img, (54, 54), (w - 54, h - 54), pal[2], 2)
    elif kind == 7:  # scattered specks (speck-absorption stress)
        cls = "scattered_specks"
        cv2.circle(img, (w // 2, h // 2), 150, pal[0], -1)
        for k in range(220):
            cv2.circle(img, (int(RNG.integers(0, w)), int(RNG.integers(0, h))),
                       int(RNG.integers(1, 4)), pal[(k % 3) + 1], -1)
    elif kind == 8:  # big flat areas (routing/travel stress)
        cls = "big_flat_areas"
        cv2.rectangle(img, (20, 20), (w // 2 - 10, h - 20), pal[0], -1)
        cv2.rectangle(img, (w // 2 + 10, 20), (w - 20, h // 2 - 10), pal[1], -1)
        cv2.rectangle(img, (w // 2 + 10, h // 2 + 10), (w - 20, h - 20), pal[2], -1)
    elif kind == 9:  # ring/donut set (hole handling)
        cls = "rings_holes"
        for k, r in enumerate([210, 150, 90]):
            cv2.circle(img, (w // 2, h // 2), r, pal[k % 4], -1)
        cv2.circle(img, (w // 2, h // 2), 45, (12, 12, 12) if dark else (255, 255, 255), -1)
    elif kind == 10:  # monogram script
        cls = "monogram"
        cv2.putText(img, "AB", (60, h - 120), cv2.FONT_HERSHEY_SCRIPT_COMPLEX, 6.0, pal[0], 14)
        cv2.putText(img, "AB", (60, h - 120), cv2.FONT_HERSHEY_SCRIPT_COMPLEX, 6.0, pal[2], 4)
    elif kind == 11:  # high colour count
        cls = "many_colours"
        for k in range(24):
            c = (int(RNG.integers(0, 255)), int(RNG.integers(0, 255)), int(RNG.integers(0, 255)))
            x = 20 + (k % 6) * 82
            y = 20 + (k // 6) * 122
            cv2.rectangle(img, (x, y), (x + 72, y + 112), c, -1)
    else:  # photo-ish noisy subject (textured gate stress)
        cls = "noisy_subject"
        base = np.clip(
            np.array(pal[0], np.float32) + RNG.normal(0, 26, (h, w, 3)), 0, 255
        ).astype(np.uint8)
        img = base
        cv2.circle(img, (w // 2, h // 2), 150, tuple(int(v) for v in pal[1]), -1)
        img = np.clip(img.astype(np.float32) + RNG.normal(0, 18, (h, w, 3)), 0, 255).astype(
            np.uint8
        )
    return cls, img


def main() -> None:
    meta: list = []
    reals = tier_a(meta)
    n_a = len(meta)
    tier_b(reals, meta, count=40)
    n_b = len(meta) - n_a
    tier_c(meta, count=100 - len(meta))
    (OUT / "corpus.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"tier A (real): {n_a}\ntier B (real-derived): {n_b}")
    print(f"tier C (parametric): {len(meta) - n_a - n_b}\ntotal: {len(meta)}")


if __name__ == "__main__":
    main()
