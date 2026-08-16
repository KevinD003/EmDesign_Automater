"""What does `_INK_DELTA = 60.0` MEAN perceptually? The ratio survey, on the sixteen.

The substrate gate moved from Euclidean BGR to CIEDE2000 on 2026-08-25 because
BGR is not perceptually uniform. The enumeration of 2026-08-26 then found that
`SUBSTRATE_DELTA` was one of THREE BGR-distance-to-substrate numbers in the
codebase, and the only one that moved. This measures the second.

`segmentation._reclaim_missed_ink` keeps a pixel when
`||pixel - substrate||_BGR >= 60.0` — "unmistakably ink rather than a shadow or
a compression artefact". MEASURED, and the extrapolation that motivated it was wrong about the axis. The
prediction, from the substrate gate's small-distance ratios, was that saturated
or coloured garments would be the strict end at roughly threefold. The magnitude
is right — 2.77x across the sixteen — but the axis is LUMINANCE and the
direction is the other way:

    substrate luma 255  ->  60.0 BGR is dE2000  7.4 - 11.0   (permissive)
    substrate luma 195  ->                     12.3
    substrate luma 162  ->                     20.1
    substrate luma   0  ->                     19.5 - 20.4   (restrictive)

Monotone in luminance. THE DARKER THE GARMENT, THE MORE PERCEPTUAL DIFFERENCE
THIS RULE DEMANDS BEFORE IT WILL RESCUE ARTWORK THE SEGMENTER DROPPED. Those
ratios are not the substrate gate's: that gate compares SMALL distances near
black, where L* is steep; this one compares a large one, where 60 BGR from black
lands well up the L* curve and 60 BGR from white barely moves it.

It is the opposite error from the substrate gate — that one sewed invisible
thread, this one would DISCARD VISIBLE ARTWORK.

WHAT THIS MEASURES AND WHAT IT CANNOT. It samples the real pixels sitting near
the decision boundary and reports the dE2000 they correspond to, per fixture.
That converts "nobody has looked" into a number.

It CANNOT say whether the spread produces a WRONG VERDICT, and the reason is
narrower than "the corpus has no mid-tones" — 09 at luma 162 and C18 at 195 do
sit between, which is how the trend above could be measured at all. What the
corpus lacks is ARTWORK CLOSE TO ITS OWN GARMENT'S TONE on a dark substrate:
A02 and C24 are dark, but their artwork is high-contrast florals, so nothing
they contain is near enough to the cloth for a dE-20 threshold to discard it.
The verdict test needs tone-on-tone artwork on a dark or mid-tone garment —
intake ask 2c. Stated as a blocked half rather than inferred.

NOTHING IS CHANGED HERE.

    scripts/measure_ink_delta_space.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for _p in (BACKEND, BACKEND / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _provenance import code_provenance, describe, toolchain
from coverage_audit import fixtures as _audit_fixtures

#: Half-width of the band sampled around the threshold. Wide enough to catch
#: real pixels on every fixture, narrow enough that the dE reported is the dE
#: AT the decision rather than an average over the whole image.
BAND = 5.0


def measure_one(name: str, path: Path) -> dict:
    import numpy as np

    from app.services.digitizer.colordiff import bgr_ciede2000
    from app.services.digitizer.geometry import _decode_raster
    from app.services.segmentation import _INK_DELTA

    img, _alpha = _decode_raster(path.read_bytes())
    f = img.astype(np.float32)
    substrate = np.array([img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]],
                         dtype=np.float32).mean(axis=0)
    dist = np.linalg.norm(f - substrate, axis=2)
    sel = (dist >= _INK_DELTA - BAND) & (dist <= _INK_DELTA + BAND)
    px = f[sel]
    row = {
        "fixture": name,
        "substrate_bgr": [round(float(v), 1) for v in substrate],
        "substrate_luma": round(float(0.114 * substrate[0] + 0.587 * substrate[1]
                                      + 0.299 * substrate[2]), 1),
        "ink_delta": _INK_DELTA,
        "pixels_at_boundary": int(px.shape[0]),
    }
    if px.shape[0] == 0:
        row["note"] = "no pixels within the band; threshold never exercised here"
        return row
    # Cap the sample: dE2000 is a per-pixel Python call and a 1200x1200 image can
    # put a million pixels in the band. Deterministic stride, not random.
    stride = max(1, px.shape[0] // 4000)
    sample = px[::stride]
    des = [bgr_ciede2000(tuple(float(c) for c in p), tuple(float(c) for c in substrate))
           for p in sample]
    des.sort()
    n = len(des)
    row.update({
        "sampled": n,
        "de2000_min": round(des[0], 3),
        "de2000_p50": round(des[n // 2], 3),
        "de2000_max": round(des[-1], 3),
        "ratio_bgr_per_de_p50": round(_INK_DELTA / max(des[n // 2], 1e-6), 2),
    })
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args()

    rows = []
    print(f"  {'fixture':28s} {'sub luma':>8s} {'px@bnd':>8s} {'dE min':>7s} "
          f"{'dE p50':>7s} {'dE max':>7s} {'BGR/dE':>7s}")
    for name, path, _params in _audit_fixtures():
        r = measure_one(name, path)
        rows.append(r)
        if not r.get("sampled"):
            print(f"  {name:28s} {r['substrate_luma']:8.1f} {0:8d}       —       —"
                  f"       —       —")
            continue
        print(f"  {name:28s} {r['substrate_luma']:8.1f} {r['pixels_at_boundary']:8d} "
              f"{r['de2000_min']:7.3f} {r['de2000_p50']:7.3f} {r['de2000_max']:7.3f} "
              f"{r['ratio_bgr_per_de_p50']:7.2f}")
    got = [r for r in rows if r.get("sampled")]
    if got:
        lo = min(r["de2000_p50"] for r in got)
        hi = max(r["de2000_p50"] for r in got)
        print(f"\n  _INK_DELTA = 60.0 BGR spans dE2000 {lo:.3f} to {hi:.3f} "
              f"across the sixteen — a {hi / max(lo, 1e-6):.2f}x spread in what "
              f"'unmistakably ink' means.")
        print("  BLOCKED HALF: every substrate here is black or white. Whether the "
              "spread\n  produces a WRONG VERDICT needs a mid-tone or coloured "
              "garment (intake ask 2c).")
    doc = {"produced_by": "scripts/measure_ink_delta_space.py",
           "code": code_provenance(), "toolchain": toolchain(), "rows": rows}
    print(f"\ntree: {describe(doc['code'])}")
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
