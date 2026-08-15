"""Is Euclidean BGR the wrong QUANTITY for the substrate rule? Both metrics, sixteen fixtures.

MECHANISM FIRST, NO FIX (CTO ruling 2026-08-23). This script measures; it changes
nothing. The rule it measures is `pipeline.py`'s substrate deletion:

    if declared_mask is None and ||center - substrate||_BGR < SUBSTRATE_DELTA:
        ... this colour cluster is the garment, not thread — delete it

The A02 promotion found that rule missing by 1.86 units on a black garment:
`#080808` against pure black measures 13.856 in BGR (exactly sqrt(3 * 8^2)) and
the gate is 12.0, so 4,638 penetrations — 5.80 machine-minutes at 800 spm —
are sewn in the cloth's own colour on every garment.

THE RULING'S LEAD, WHICH THIS TESTS RATHER THAN ASSUMES: the gate may not be
miscalibrated so much as measuring the wrong quantity. `#080808` and `#000000`
are the same colour to a human. Euclidean RGB says 13.86 — comfortably
"different" — because RGB distance is not perceptually uniform, and near black
it OVER-states difference. In CIE L*a*b*, sRGB(8,8,8) is L* ~= 2.2 against
black's 0, i.e. dE ~= 2.2, right at the ~2.3 just-noticeable difference.

If that is the mechanism, a perceptual metric gives a threshold DERIVED FROM
JND rather than fitted to a fixture, which is the standard this repository has
enforced throughout.

AND IT MAKES A FALSIFIABLE PREDICTION, which is the reason this script surveys
all sixteen and not just A02: if RGB under-states perceptual difference near
black, it should OVER-state it somewhere else — near white, and in saturated
colours — and therefore DELETE clusters a perceptual metric would keep. So the
report is every verdict FLIP, in both directions, not only the one that
motivated it.

    scripts/measure_substrate_metric.py                # table + flips
    scripts/measure_substrate_metric.py --json out.json
    scripts/measure_substrate_metric.py --sweep        # threshold sensitivity

WHERE THE NUMBERS COME FROM. `constants._SUBSTRATE_LOG`, written at the decision
site itself. Not from colour STOPS: a cluster deleted as substrate never becomes
a stop, so a stop-level survey is structurally blind to the "RGB deleted it,
Lab would keep it" direction — exactly half the prediction.

## The limitation, stated before the numbers rather than after

**dE76 only.** CIEDE2000 is the better metric and is NOT computed here. Writing
forty lines of unverified colour-difference formula and then putting a headline
number on top of it is the failure mode this repository keeps paying for; a
verified implementation (checked against Sharma et al.'s published test pairs)
is a prerequisite, not a detail, and it is named as follow-up work.

What that costs, precisely: dE76 and dE2000 agree closely for two NEAR-NEUTRAL
colours, because CIEDE2000's corrections are mostly chroma- and hue-dependent.
So the A02 result — the case that motivated this — is well served. The
SATURATED-COLOUR half of the prediction is exactly where dE76 is weakest, so a
null result there is not evidence of no effect; it is an untested case.
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
from run_quality_bench import RNG_SEED

# The just-noticeable difference for dE76. NOT fitted here and not tuned to any
# fixture: it is the standard perceptual threshold, which is the entire point of
# changing metric. Reported with a sweep so its sensitivity is visible.
JND_DE76 = 2.3

# CIEDE2000's just-noticeable difference is ~1.0, not 2.3: the formula is
# normalised so that unit dE00 IS the JND, which is the whole reason it exists.
# Using 2.3 here would be importing dE76's threshold into a different scale --
# the "constant carried across a space change" error this repository names.
JND_DE2000 = 1.0


def _to_lab(bgr):
    """BGR (0-255 floats, the pipeline's own representation) -> CIE L*a*b*.

    float32 in 0-1, so OpenCV returns TRUE L* in 0-100 rather than its 8-bit
    encoding (L*255/100, a+128, b+128). Getting that wrong would scale every
    dE by 2.55 and make the JND comparison meaningless.
    """
    import cv2
    import numpy as np

    px = np.array([[[bgr[0], bgr[1], bgr[2]]]], dtype=np.float32) / 255.0
    return cv2.cvtColor(px, cv2.COLOR_BGR2Lab)[0, 0].astype(float)


def _de76(a, b) -> float:
    import math

    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


# dE2000, from the backend's own verified implementation (tests/test_colordiff.py:
# four Sharma pairs directly, plus 1,200 random Lab pairs cross-checked against
# skimage at < 1e-6). The ruling of 2026-08-25 required the verification BEFORE
# anything depended on it, so this import is the point at which that becomes true.
def _de2000(a, b) -> float:
    from app.services.digitizer.colordiff import ciede2000

    return ciede2000(a, b)


def measure_one(name: str, path: Path, params: dict) -> dict:
    import cv2

    from app.services.digitizer import digitize_image
    from app.services.digitizer.constants import _SUBSTRATE_LOG, SUBSTRATE_DELTA

    cv2.setRNGSeed(RNG_SEED)
    digitize_image(
        path.read_bytes(),
        fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    rows = []
    for e in _SUBSTRATE_LOG:
        lab_c, lab_s = _to_lab(e["center_bgr"]), _to_lab(e["substrate_bgr"])
        de = _de76(lab_c, lab_s)
        de00 = _de2000(lab_c, lab_s)
        rgb_del = e["rgb_distance"] < SUBSTRATE_DELTA
        lab_del = de < JND_DE76
        de00_del = de00 < JND_DE2000
        rows.append({
            "center_bgr": [round(v, 2) for v in e["center_bgr"]],
            "center_hex": "#{:02x}{:02x}{:02x}".format(
                *(max(0, min(255, round(v))) for v in reversed(e["center_bgr"]))),
            "substrate_bgr": [round(v, 2) for v in e["substrate_bgr"]],
            "px": e["px"],
            "rgb_distance": round(e["rgb_distance"], 3),
            "lab_center": [round(v, 2) for v in lab_c],
            "lab_substrate": [round(v, 2) for v in lab_s],
            "de76": round(de, 3),
            "de2000": round(de00, 3),
            "de2000_gates_in": de00_del,
            "flip2000": ("none" if rgb_del == de00_del
                         else ("de2000_gates_in_more" if de00_del
                               else "de2000_gates_in_less")),
            "rgb_gates_in": rgb_del,
            "lab_gates_in": lab_del,
            # GATED IN, not deleted. Entering the substrate branch is not the end
            # of the decision — flat artwork faces further tests inside it and can
            # survive. The metric question is about the GATE, so that is what is
            # compared; calling it "deleted" would overstate every row.
            "gated_in": e["gated_in"],
            "flip": ("none" if rgb_del == lab_del
                     else ("lab_gates_in_more" if lab_del else "lab_gates_in_less")),
        })
    total_px = sum(r["px"] for r in rows) or 1
    return {
        "fixture": name,
        "conditions": f"{params.get('fabric', 'cotton')} @ {params['hoop']}",
        "max_colors": params["colors"],
        "substrate_delta": SUBSTRATE_DELTA,
        "jnd_de76": JND_DE76,
        "clusters": len(rows),
        "flips": [r for r in rows if r["flip"] != "none"],
        "flips2000": [r for r in rows if r["flip2000"] != "none"],
        "flipped_px_share": round(
            sum(r["px"] for r in rows if r["flip"] != "none") / total_px, 4),
        "rows": rows,
    }


def sweep(all_rows: list[dict]) -> list[dict]:
    """How many clusters flip as the dE threshold moves. Sensitivity, not tuning."""
    out = []
    for t in (0.5, 0.75, 1.0, 1.5, 2.0, 2.3, 2.5, 3.0, 4.0, 5.0):
        more = sum(1 for r in all_rows if (r["de76"] < t) and not r["rgb_gates_in"])
        less = sum(1 for r in all_rows if not (r["de76"] < t) and r["rgb_gates_in"])
        m0 = sum(1 for r in all_rows if (r["de2000"] < t) and not r["rgb_gates_in"])
        l0 = sum(1 for r in all_rows if not (r["de2000"] < t) and r["rgb_gates_in"])
        out.append({"threshold": t, "lab_gates_in_more": more,
                    "lab_gates_in_less": less,
                    "de2000_gates_in_more": m0, "de2000_gates_in_less": l0})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--sweep", action="store_true", help="threshold sensitivity table")
    args = ap.parse_args()

    docs, every = [], []
    for name, path, params in _audit_fixtures():
        if not path.exists():
            raise SystemExit(f"missing fixture {path}")
        d = measure_one(name, path, params)
        docs.append(d)
        every.extend(d["rows"])
        flips = d["flips"]
        mark = f"  {len(flips)} FLIP" if flips else ""
        print(f"  {name:28s} {d['clusters']:3d} clusters  [{d['conditions']}]{mark}")
        for r in flips:
            print(f"      {r['center_hex']}  rgb {r['rgb_distance']:7.3f} "
                  f"({'in ' if r['rgb_gates_in'] else 'out'})   "
                  f"dE76 {r['de76']:7.3f} ({'in ' if r['lab_gates_in'] else 'out'})   "
                  f"{r['px']:8d} px   -> {r['flip']}")

    more = [r for r in every if r["flip"] == "lab_gates_in_more"]
    less = [r for r in every if r["flip"] == "lab_gates_in_less"]
    m0 = [r for r in every if r["flip2000"] == "de2000_gates_in_more"]
    l0 = [r for r in every if r["flip2000"] == "de2000_gates_in_less"]
    print(f"\n{len(every)} clusters across {len(docs)} fixtures")
    print(f"  RGB gate says KEEP, dE76 says substrate : {len(more):3d}  "
          f"({sum(r['px'] for r in more):,} px)")
    print(f"  RGB gate says substrate, dE76 says KEEP : {len(less):3d}  "
          f"({sum(r['px'] for r in less):,} px)")
    print(f"  RGB keeps, dE2000 says substrate        : {len(m0):3d}  "
          f"({sum(r['px'] for r in m0):,} px)")
    print(f"  RGB says substrate, dE2000 says KEEP    : {len(l0):3d}  "
          f"({sum(r['px'] for r in l0):,} px)")
    _near = sorted(every, key=lambda r: r["de2000"])[:6]
    print("\n  six clusters nearest the substrate under dE2000:")
    for r in _near:
        print(f"    {r['center_hex']}  bgr {r['rgb_distance']:8.3f}  "
              f"dE76 {r['de76']:7.3f}  dE2000 {r['de2000']:7.3f}  {r['px']:8d} px")
    doc = {
        "produced_by": "scripts/measure_substrate_metric.py",
        "code": code_provenance(),
        "toolchain": toolchain(),
        "rng_seed": RNG_SEED,
        "jnd_de76": JND_DE76,
        "fixture_set": [d["fixture"] for d in docs],
        "summary": {
            "clusters": len(every),
            "lab_gates_in_more": len(more),
            "lab_gates_in_less": len(less),
            "de2000_gates_in_more": len(m0),
            "de2000_gates_in_less": len(l0),
            "de2000_gates_in_more_px": sum(r["px"] for r in m0),
            "de2000_gates_in_less_px": sum(r["px"] for r in l0),
            "lab_gates_in_more_px": sum(r["px"] for r in more),
            "lab_gates_in_less_px": sum(r["px"] for r in less),
        },
        "sweep": sweep(every),
        "fixtures": docs,
    }
    if args.sweep:
        print(f"\n{'thresh':>6s}  {'dE76 in+':>8s} {'dE76 in-':>8s}  "
              f"{'dE2000 in+':>10s} {'dE2000 in-':>10s}")
        for s in doc["sweep"]:
            print(f"{s['threshold']:6.2f}  {s['lab_gates_in_more']:8d} "
                  f"{s['lab_gates_in_less']:8d}  {s['de2000_gates_in_more']:10d} "
                  f"{s['de2000_gates_in_less']:10d}")
    print(f"\ntree: {describe(doc['code'])}   fixtures: {len(docs)}")
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
