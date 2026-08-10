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

# The three photographs are TRACKED, at their tier-A names in `OUT`. They used to
# be read from a hardcoded session scratchpad path, which does not exist on any
# other machine — and the failure was silent and total:
#
#   1. tier A dropped 13 -> 10, because `if src.exists()` skipped them;
#   2. `reals` came back empty, so `tier_b` returned immediately: 40 -> 0 images;
#   3. tier C was then asked for 100 - 10 = 90 instead of 47;
#   4. and because ONE module-level RNG was consumed in draw order across all
#      three tiers, tier C's parametric stream moved as well.
#
# A fresh checkout produced a 10/0/90 corpus while every audit table said
# 13/40/47, with nothing said. Reading the tracked copies makes the corpus
# reproducible from the repository alone; `_require` below makes a missing source
# an error instead of a smaller corpus.
TIER_A_PHOTOS = [
    ("A01_real_peacock_patch_photo", "photographed peacock patch"),
    ("A02_real_neckline_black", "floral neckline on black"),
    ("A03_real_neckline_panel", "full-length neckline panel"),
]
TIER_A_FIXTURE_COUNT = 10        # the quality-bench set, also tracked

# ONE GENERATOR PER TIER, each seeded independently. A single shared generator
# makes every tier's output depend on how many draws the tiers before it made, so
# adding one photograph silently re-rolls all 47 parametric designs. These are
# derived from the original 20260802 so tier B's stream is unchanged from the
# corpus that was measured; tier C's moves once, here, and is stable thereafter.
RNG_B = np.random.default_rng(20260802)
RNG_C = np.random.default_rng(20260803)

PALETTES = [
    [(40, 40, 200), (30, 160, 30), (200, 160, 20), (60, 60, 60)],
    [(180, 60, 40), (40, 120, 200), (240, 220, 60), (250, 250, 250)],
    [(20, 20, 20), (200, 30, 120), (60, 200, 200), (240, 240, 100)],
    [(90, 40, 140), (30, 180, 90), (240, 140, 30), (30, 30, 30)],
]


def _ink_share(img) -> float:
    """Fraction of pixels that differ visibly from the canvas colour."""
    bg = np.array(img[2, 2], np.float32)
    return float((np.linalg.norm(img.astype(np.float32) - bg, axis=2) > 10).mean())


def _write(name: str, img, tier: str, cls: str, meta: list, *, store: bool = True) -> None:
    # A stress corpus must not contain a blank. C01_hairline_linework was one for
    # the whole life of this corpus: `hairline_linework` draws in `pal[3]`, and
    # PALETTES[1][3] is (250, 250, 250) on a (255, 255, 255) canvas, so the design
    # was invisible. It then digitized to zero stitches and was counted as a
    # pipeline failure in every audit since — the engine was right and the
    # fixture was wrong. Refuse to write one rather than trust the palettes.
    share = _ink_share(img)
    if share < 0.002:
        raise SystemExit(
            f"{name}: only {share * 100:.3f}% of the canvas differs from the "
            f"background — this fixture would be blank. Check the palette/canvas "
            f"contrast for class {cls!r}."
        )
    OUT.mkdir(parents=True, exist_ok=True)
    # `store=False` for the tier-A photographs: they are TRACKED and already live
    # at exactly this path, so re-encoding them would rewrite committed files on
    # every build for no gain. They still go through the blank check above and
    # still appear in the manifest — they are corpus members, just not ones this
    # script produces.
    if store:
        cv2.imwrite(str(OUT / f"{name}.png"), img)
    meta.append({"name": name, "tier": tier, "class": cls})


# ── Tier A: the genuine articles ────────────────────────────────────────────


def _require(path: Path, what: str):
    """Read an image that the corpus CANNOT be built without.

    Every tier-A source is tracked, so a missing one means a broken checkout, not
    a smaller corpus — and a smaller corpus is the dangerous outcome, because the
    tier counts are what every result table is read against.
    """
    if not path.exists():
        raise SystemExit(
            f"missing tier-A source: {path}\n"
            f"  ({what})\n"
            f"  Tier A is tracked in the repository. A corpus built without it "
            f"would silently be a different corpus — refusing rather than "
            f"shrinking. Check out the repo fully, or restore this file."
        )
    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"tier-A source could not be decoded: {path} ({what})")
    return img


def tier_a(meta: list) -> list:
    reals = []
    for name, what in TIER_A_PHOTOS:
        img = _require(OUT / f"{name}.png", what)
        _write(name, img, "A-real", "user-supplied embroidery", meta, store=False)
        reals.append(img)

    fixtures = sorted(FIXTURES.glob("*.png"))
    if len(fixtures) != TIER_A_FIXTURE_COUNT:
        raise SystemExit(
            f"expected {TIER_A_FIXTURE_COUNT} quality-bench fixtures, found "
            f"{len(fixtures)} in {FIXTURES} — the tier-A count is what every "
            f"result table is read against, so this is refused rather than "
            f"silently changing the corpus."
        )
    for f in fixtures:
        img = _require(f, "quality-bench fixture")
        _write(f"A_fixture_{f.stem}", img, "A-real", "quality-bench fixture", meta)
    return reals


# ── Tier B: real-derived (real texture, synthetic framing) ──────────────────


def tier_b(reals: list, meta: list, count: int) -> None:
    # `return` on an empty `reals` is what turned a missing scratchpad into a
    # 40-image tier vanishing without a word. It cannot happen now — `tier_a`
    # raises first — so if it somehow does, say so instead of shrinking.
    if not reals:
        raise SystemExit(
            "tier B has no tier-A photographs to derive from. Tier B is 40 of "
            "the corpus's 100 designs; continuing would build a different "
            "corpus under the same name."
        )
    ops = ["crop", "rotate", "scale", "recolour", "crop_rot", "lowlight"]
    for i in range(count):
        base = reals[i % len(reals)].copy()
        op = ops[i % len(ops)]
        h, w = base.shape[:2]
        if op in ("crop", "crop_rot"):
            cw = int(w * RNG_B.uniform(0.35, 0.75))
            ch = int(h * RNG_B.uniform(0.35, 0.75))
            x = int(RNG_B.integers(0, max(1, w - cw)))
            y = int(RNG_B.integers(0, max(1, h - ch)))
            base = base[y : y + ch, x : x + cw]
            if op == "crop_rot":
                ang = float(RNG_B.uniform(-30, 30))
                m = cv2.getRotationMatrix2D((base.shape[1] / 2, base.shape[0] / 2), ang, 1)
                base = cv2.warpAffine(
                    base, m, (base.shape[1], base.shape[0]), borderMode=cv2.BORDER_REPLICATE
                )
        elif op == "rotate":
            k = int(RNG_B.integers(1, 4))
            base = np.rot90(base, k).copy()
        elif op == "scale":
            f = float(RNG_B.uniform(0.3, 0.8))
            base = cv2.resize(base, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        elif op == "recolour":
            hsv = cv2.cvtColor(base, cv2.COLOR_BGR2HSV).astype(np.int16)
            hsv[..., 0] = (hsv[..., 0] + int(RNG_B.integers(20, 140))) % 180
            base = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
        elif op == "lowlight":
            base = np.clip(base.astype(np.float32) * RNG_B.uniform(0.35, 0.6), 0, 255).astype(
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


def _contrasting(pal, bg):
    """The palette, reordered so the lowest-contrast entry against `bg` is last.

    Several classes draw their only ink in `pal[3]`, which silently produced a
    blank design whenever that entry matched the canvas.
    """
    bg_v = np.array(bg, np.float32)
    return sorted(pal, key=lambda c: -float(np.linalg.norm(np.array(c, np.float32) - bg_v)))


def _generate(i: int, pal):
    kind = i % 13
    dark = (kind % 3 == 2)
    bg = (12, 12, 12) if dark else (255, 255, 255)
    img = _canvas(bg=bg)
    pal = _contrasting(pal, bg)
    h, w = img.shape[:2]

    if kind == 0:  # dense floral spray (the neckline class)
        cls = "dense_floral"
        for k in range(14):
            cx = int(RNG_C.integers(60, w - 60))
            cy = int(RNG_C.integers(60, h - 60))
            _flower(img, cx, cy, int(RNG_C.integers(22, 44)), pal[0], pal[2])
        for k in range(20):
            p1 = (int(RNG_C.integers(0, w)), int(RNG_C.integers(0, h)))
            p2 = (p1[0] + int(RNG_C.integers(-70, 70)), p1[1] + int(RNG_C.integers(-70, 70)))
            cv2.line(img, p1, p2, pal[1], 4)
    elif kind == 1:  # hairline linework
        cls = "hairline_linework"
        # `pal[0]`, not `pal[3]`. `_contrasting` sorts the palette by DESCENDING
        # distance from the canvas, so `pal[3]` is by construction the LEAST
        # contrasting entry — and this class's only ink was taken from it. The
        # helper written to stop blank fixtures was guaranteeing one here: on
        # PALETTES[1] against white, `pal[3]` resolves to (250, 250, 250) and the
        # design is invisible, so `_write`'s blank guard aborted the whole build
        # at C01 and tier C could not be generated at all. A single-ink class
        # must take the most contrasting entry, which is what `_contrasting`
        # exists to identify.
        for x in range(20, w - 20, 9):
            cv2.line(img, (x, 20), (x + 40, h - 20), pal[0], 1)
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
            cv2.circle(img, (int(RNG_C.integers(0, w)), int(RNG_C.integers(0, h))),
                       int(RNG_C.integers(1, 4)), pal[(k % 3) + 1], -1)
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
            c = (int(RNG_C.integers(0, 255)), int(RNG_C.integers(0, 255)), int(RNG_C.integers(0, 255)))
            x = 20 + (k % 6) * 82
            y = 20 + (k // 6) * 122
            cv2.rectangle(img, (x, y), (x + 72, y + 112), c, -1)
    else:  # photo-ish noisy subject (textured gate stress)
        cls = "noisy_subject"
        base = np.clip(
            np.array(pal[0], np.float32) + RNG_C.normal(0, 26, (h, w, 3)), 0, 255
        ).astype(np.uint8)
        img = base
        cv2.circle(img, (w // 2, h // 2), 150, tuple(int(v) for v in pal[1]), -1)
        img = np.clip(img.astype(np.float32) + RNG_C.normal(0, 18, (h, w, 3)), 0, 255).astype(
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
    n_c = len(meta) - n_a - n_b

    # The tier split is the corpus's contract — every result table is read
    # against it, and a corpus with the right total but the wrong split is the
    # failure this script just had. Assert it rather than print it and hope.
    expected = {"A-real": 13, "B-real-derived": 40, "C-parametric": 47}
    got = {"A-real": n_a, "B-real-derived": n_b, "C-parametric": n_c}
    if got != expected:
        raise SystemExit(f"tier split is {got}, expected {expected}")

    # Every manifest entry must have an image on disk. Tier A's are tracked
    # rather than written here, so a missing one is precisely the case that used
    # to pass silently.
    missing = [m["name"] for m in meta if not (OUT / f"{m['name']}.png").exists()]
    if missing:
        raise SystemExit(f"manifest lists images that are not on disk: {missing}")

    (OUT / "corpus.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"tier A (real): {n_a}\ntier B (real-derived): {n_b}")
    print(f"tier C (parametric): {n_c}\ntotal: {len(meta)}")


if __name__ == "__main__":
    main()
