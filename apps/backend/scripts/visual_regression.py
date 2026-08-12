"""Visual regression for digitized output (v2 Part 44, R003).

The standing complaint was fair: renders have been checked repeatedly, and every
check lived in a scratchpad that was deleted with the session. Parts 39, 40 and 41
each found a defect that no metric had flagged — a split lobe, a flooded lattice,
a lost bead-chain, thread laid on bare cloth — and found it by looking at a
picture. None of that is reproducible today.

This makes it reproducible. Digitize each bench fixture, render the sewn stream,
compare against a committed baseline, and write a diff image when they disagree.

    scripts/visual_regression.py                # check against baselines
    scripts/visual_regression.py --update       # accept current output as baseline
    scripts/visual_regression.py --contact-sheet  # one PNG of everything, to look at

On the threshold: because `render_design` is a pure function, an unchanged
pipeline scores SSIM 1.000000 exactly. So the gate is 0.995, not the 0.85 a
photograph-comparison harness would use. A loose threshold on a deterministic
renderer is the failure mode to avoid — it passes real regressions and teaches
everyone to ignore the harness.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

if str(BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND / "scripts"))

# IMPORTED, not copied. A first draft of this file retyped the fixture table and
# got four of the ten wrong within the hour — a picture is only comparable if it
# was produced at the same configuration as the numbers beside it, and two hand-
# maintained copies of a config drift silently. Same reasoning the metrics script
# records for importing ZIGZAG_RATIO from the pipeline rather than redeclaring it.
from run_quality_bench import FIXTURE_PARAMS, RNG_SEED

from app.services.digitizer import digitize_image
from app.services.stitch_render import render_design

FIXTURE_DIR = BACKEND / "tests" / "fixtures" / "quality_bench"
BASELINE_DIR = BACKEND / "tests" / "visual" / "baselines"
DIFF_DIR = BACKEND / "tests" / "visual" / "diffs"

SSIM_GATE = 0.995
FIXTURES = FIXTURE_PARAMS


def ssim(a, b) -> float:
    """Structural similarity, Wang et al., 11x11 Gaussian window, on greyscale.

    Implemented here rather than pulled from scikit-image on purpose: the backend
    already depends on OpenCV and NumPy, and adding a large dependency for one
    twenty-line function is a cost the next person pays on every install.
    """
    import cv2
    import numpy as np

    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float64)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2

    def blur(x):
        return cv2.GaussianBlur(x, (11, 11), 1.5)

    mu_a, mu_b = blur(ga), blur(gb)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    var_a = blur(ga * ga) - mu_a2
    var_b = blur(gb * gb) - mu_b2
    cov = blur(ga * gb) - mu_ab
    num = (2 * mu_ab + c1) * (2 * cov + c2)
    den = (mu_a2 + mu_b2 + c1) * (var_a + var_b + c2)
    return float(np.mean(num / den))


def render_fixture(name: str):
    """Digitize one bench fixture and render it, at the pinned configuration."""
    import cv2

    params = FIXTURES[name]
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        (FIXTURE_DIR / f"{name}.png").read_bytes(),
        fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    return render_design(design), design


def compare(name: str, actual, write_diff: bool = True) -> dict:
    """Score one render against its baseline. Returns a verdict dict."""
    import cv2
    import numpy as np

    baseline_path = BASELINE_DIR / f"{name}.png"
    if not baseline_path.exists():
        return {"name": name, "ok": False, "reason": "no baseline — run with --update"}

    expected = cv2.imread(str(baseline_path), cv2.IMREAD_COLOR)
    if expected is None:
        return {"name": name, "ok": False, "reason": f"unreadable baseline {baseline_path}"}

    if expected.shape != actual.shape:
        # A size change means the design's extents moved. That is always worth a
        # human look, and SSIM cannot score mismatched shapes anyway.
        return {
            "name": name, "ok": False, "ssim": None,
            "reason": f"size changed {expected.shape[1]}x{expected.shape[0]} "
                      f"-> {actual.shape[1]}x{actual.shape[0]}",
        }

    score = ssim(expected, actual)
    changed = int(np.count_nonzero(np.any(expected != actual, axis=2)))
    share = changed / float(expected.shape[0] * expected.shape[1])
    ok = score >= SSIM_GATE
    verdict = {"name": name, "ok": ok, "ssim": round(score, 6),
               "changed_px": changed, "changed_share": round(share, 6)}
    if not ok and write_diff:
        DIFF_DIR.mkdir(parents=True, exist_ok=True)
        # Side by side, with changed pixels flagged on a dimmed copy of the new
        # render — "what changed" is the question, not "what does it look like".
        flag = actual.copy()
        mask = np.any(expected != actual, axis=2)
        flag[mask] = (0, 0, 255)
        strip = np.hstack([expected, actual, flag])
        # WRITTEN ATOMICALLY, because two test lanes are routinely run at once
        # and both fail the same fixture. `cv2.imwrite` straight to the final
        # path let the second writer interleave with the first, so the strip a
        # human opens to decide "is this change intended?" could be a torn file.
        # It cannot flip an assertion — the verdict above is already computed —
        # but the artefact it corrupts is the one used to JUDGE a re-pin, which
        # is the same class of problem as a flaky test. A temporary file per
        # process plus `os.replace` keeps the path predictable (the failure
        # message prints it) while making the write indivisible.
        final = DIFF_DIR / f"{name}.png"
        tmp = DIFF_DIR / f".{name}.{os.getpid()}.tmp.png"
        cv2.imwrite(str(tmp), strip)
        os.replace(tmp, final)
        verdict["diff"] = str(final)
    return verdict


def contact_sheet(path: Path, cols: int = 4) -> None:
    """Every fixture in one image, scaled to a common cell. For looking at."""
    import cv2
    import numpy as np

    cell = 320
    tiles = []
    for name in sorted(FIXTURES):
        img, _ = render_fixture(name)
        h, w = img.shape[:2]
        s = min(cell / w, cell / h)
        small = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
        tile = np.full((cell, cell, 3), 255, np.uint8)
        y0, x0 = (cell - small.shape[0]) // 2, (cell - small.shape[1]) // 2
        tile[y0:y0 + small.shape[0], x0:x0 + small.shape[1]] = small
        cv2.putText(tile, name[:22], (6, cell - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append(tile)
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    if len(rows) > 1:
        width = max(r.shape[1] for r in rows)
        rows = [np.hstack([r, np.full((cell, width - r.shape[1], 3), 255, np.uint8)])
                if r.shape[1] < width else r for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.vstack(rows))
    print(f"contact sheet -> {path}")


def main() -> int:
    import cv2

    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="accept current output as the baseline")
    ap.add_argument("--contact-sheet", metavar="PATH", nargs="?", const="", default=None)
    ap.add_argument("--only", help="single fixture name")
    args = ap.parse_args()

    if args.contact_sheet is not None:
        contact_sheet(Path(args.contact_sheet) if args.contact_sheet
                      else BACKEND / "tests" / "visual" / "contact-sheet.png")
        return 0

    names = [args.only] if args.only else sorted(FIXTURES)
    failures = []
    for name in names:
        actual, design = render_fixture(name)
        if args.update:
            BASELINE_DIR.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(BASELINE_DIR / f"{name}.png"), actual)
            print(f"  baseline  {name:26s} {actual.shape[1]}x{actual.shape[0]}  "
                  f"{design.stitch_count} stitches")
            continue
        v = compare(name, actual)
        if v["ok"]:
            print(f"  ok        {name:26s} ssim {v['ssim']:.6f}")
        else:
            failures.append(v)
            detail = v.get("reason") or f"ssim {v['ssim']:.6f}, {v['changed_px']} px changed"
            print(f"  CHANGED   {name:26s} {detail}")
            if v.get("diff"):
                print(f"            diff -> {v['diff']}")

    if args.update:
        print(f"\nwrote {len(names)} baselines to {BASELINE_DIR}")
        return 0
    if failures:
        print(f"\n{len(failures)} of {len(names)} fixtures changed. Look at the diffs, then "
              f"either fix the regression or re-run with --update to accept them.")
        return 1
    print(f"\nall {len(names)} fixtures match their baselines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
