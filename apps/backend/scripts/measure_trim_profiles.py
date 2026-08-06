"""What the aggressive trim profile actually buys, and what it touches (v2 Part 59).

Two claims ship with the profile and both are checked here on real designs
rather than asserted:

* the default is a no-op — `conservative` returns the stream exactly as
  generated;
* `aggressive` changes ONLY the trim schedule — every STITCH, JUMP and
  COLOR_CHANGE survives at the same coordinates in the same order, so the
  design sews identically and the difference is machine time.

    scripts/measure_trim_profiles.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.digitizer import digitize_image
from app.services.trim_profiles import TRIM_SECONDS_EQUIV, apply_trim_profile

CORPUS = BACKEND / "tests/fixtures/corpus100"
CASES = (("A01_real_peacock_patch_photo", "360x350"),
         ("A02_real_neckline_black", "360x350"),
         ("A03_real_neckline_panel", "360x350"))
RNG_SEED = 20260728


def stats(design):
    trims = jumps = stitches_n = 0
    travel = 0.0
    prev = None
    for s in design.stitches:
        cmd = str(getattr(s, "command", "")).upper()
        if cmd == "TRIM":
            trims += 1
        elif cmd == "JUMP":
            jumps += 1
            if prev is not None:
                travel += math.hypot(s.x - prev[0], s.y - prev[1])
        elif cmd == "STITCH":
            stitches_n += 1
        if cmd in ("STITCH", "JUMP", "COLOR_CHANGE"):
            prev = (s.x, s.y)
    return trims, jumps, stitches_n, travel / 1000.0


def non_trim_stream(design):
    return [(str(s.command).upper(), round(s.x, 4), round(s.y, 4))
            for s in design.stitches if str(s.command).upper() != "TRIM"]


def main() -> int:
    print(f"{'design':30s} {'profile':>13s} {'trims':>6s} {'jumps':>6s} "
          f"{'stitch':>7s} {'travel m':>9s} {'trim min':>9s}")
    for name, hoop in CASES:
        cv2.setRNGSeed(RNG_SEED)
        base = digitize_image((CORPUS / f"{name}.png").read_bytes(), "cotton", hoop, 12)
        agg = apply_trim_profile(base, "aggressive")
        assert apply_trim_profile(base, "conservative") is base, "default is not a no-op"
        assert non_trim_stream(base) == non_trim_stream(agg), (
            f"{name}: aggressive changed something other than trims")
        for label, d in (("conservative", base), ("aggressive", agg)):
            t, j, st_n, tr = stats(d)
            print(f"{name:30s} {label:>13s} {t:6d} {j:6d} {st_n:7d} {tr:9.2f} "
                  f"{t * TRIM_SECONDS_EQUIV / 60:9.1f}", flush=True)
    print("\nStitch counts and travel are identical by construction — the check "
          "above fails\nloudly if they are not. The saving is trim count, i.e. "
          "machine time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
