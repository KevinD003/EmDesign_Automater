"""Is the aggressive trim profile safe on IMPORTED machine streams? (v2 Part 61)

Part 59 shipped the profile and measured it on STITCHIQ-generated designs; its
honest-residuals section said in terms that no imported-file population had been
measured. This closes that gap.

The population is two-tier, because the repo's true foreign files are small:

  FOREIGN      tests/fixtures/sample.dst and sample.pes — files this engine
               never generated.
  ROUND-TRIP   tier-A designs exported to each machine format and re-imported.
               This is the honest way to obtain machine-format stream shapes at
               scale: DST really does split long moves into jump chains at
               write time, PES/JEF/EXP/VP3 each re-encode the stream their own
               way, and the re-imported Design is what a user who opens such a
               file actually holds.

For every stream, both profiles are applied and the script asserts — not
reports — that the diff is trim-only. It then scans for the foreign-stream
hazards the profile's rule has to survive:

  * jump CHAINS after a trim (DST splitting) — where the carried path exceeds
    the first hop, and where a naive first-hop rule would have decided a trim
    differently;
  * trims followed by no movement at all, duplicated trims, trims guarding a
    colour change — shapes our generator never emits but a foreign file may.

    scripts/measure_import_trim_safety.py
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

from app.services import embroidery_io
from app.services.digitizer import digitize_image
from app.services.trim_profiles import TRIM_PROFILES, apply_trim_profile, carried_thread_mm

CORPUS = BACKEND / "tests/fixtures/corpus100"
FIXTURES = BACKEND / "tests/fixtures"
RNG_SEED = 20260728
ROUND_TRIP_FORMATS = ("dst", "pes", "jef", "exp", "vp3")
THRESHOLD = TRIM_PROFILES["aggressive"]


def _cmd(s) -> str:
    c = s.command
    return (c.value if hasattr(c, "value") else str(c)).upper()


def counts(design):
    out = {"TRIM": 0, "JUMP": 0, "STITCH": 0, "COLOR_CHANGE": 0}
    for s in design.stitches:
        c = _cmd(s)
        if c in out:
            out[c] += 1
    return out


def non_trim_stream(design):
    return [(_cmd(s), round(s.x, 3), round(s.y, 3))
            for s in design.stitches if _cmd(s) != "TRIM"]


def hazards(design):
    """Foreign-stream shapes the rule must survive, counted."""
    sts = design.stitches
    h = {
        "trim_then_jump_chain": 0,   # >1 consecutive JUMP after a trim
        "max_chain_len": 0,
        "path_exceeds_first_hop": 0,  # carried path > first hop by >0.5 mm
        "first_hop_rule_differs": 0,  # naive rule would decide the trim differently
        "trim_no_following_stitch": 0,
        "double_trim": 0,
        "trim_before_color_change": 0,
    }
    for i, s in enumerate(sts):
        if _cmd(s) != "TRIM":
            continue
        # chain length after this trim
        chain = 0
        j = i + 1
        while j < len(sts) and _cmd(sts[j]) == "JUMP":
            chain += 1
            j += 1
        if chain > 1:
            h["trim_then_jump_chain"] += 1
            h["max_chain_len"] = max(h["max_chain_len"], chain)
        if j < len(sts) and _cmd(sts[j]) == "TRIM":
            h["double_trim"] += 1
        if i + 1 < len(sts) and _cmd(sts[i + 1]) == "COLOR_CHANGE":
            h["trim_before_color_change"] += 1

        carry = carried_thread_mm(sts, i)
        if math.isinf(carry):
            h["trim_no_following_stitch"] += 1
            continue
        first_hop = (math.hypot(sts[i + 1].x - s.x, sts[i + 1].y - s.y)
                     if i + 1 < len(sts) else 0.0)
        if carry > first_hop + 0.5:
            h["path_exceeds_first_hop"] += 1
        naive_drop = first_hop < THRESHOLD
        path_drop = carry < THRESHOLD
        if naive_drop != path_drop:
            h["first_hop_rule_differs"] += 1
    return h


def check(name: str, design):
    base = counts(design)
    agg = apply_trim_profile(design, "aggressive")
    after = counts(agg)
    assert non_trim_stream(design) == non_trim_stream(agg), f"{name}: diff is not trim-only"
    assert apply_trim_profile(design, "conservative") is design
    hz = hazards(design)
    removed = base["TRIM"] - after["TRIM"]
    print(f"{name:34s} {base['TRIM']:5d} -> {after['TRIM']:5d} ({removed:4d} removed) "
          f"jumps {base['JUMP']:5d} st {base['STITCH']:6d} cc {base['COLOR_CHANGE']:3d}  "
          f"chains {hz['trim_then_jump_chain']:4d} (max {hz['max_chain_len']:3d})  "
          f"path>hop {hz['path_exceeds_first_hop']:4d}  rule-differs {hz['first_hop_rule_differs']:4d}  "
          f"inf {hz['trim_no_following_stitch']:3d}", flush=True)
    return base, after, hz


def main() -> int:
    print(f"{'stream':34s} {'trims':>14s} …\n")
    print("FOREIGN FILES (never generated by this engine)")
    for fname in ("sample.dst", "sample.pes"):
        p = FIXTURES / fname
        design = embroidery_io.read_embroidery(p.read_bytes(), p.suffix)
        check(fname, design)

    print("\nROUND-TRIPS (tier-A designs through each machine format)")
    for name, hoop in (("A01_real_peacock_patch_photo", "360x350"),
                       ("A03_real_neckline_panel", "360x350")):
        cv2.setRNGSeed(RNG_SEED)
        original = digitize_image((CORPUS / f"{name}.png").read_bytes(), "cotton", hoop, 12)
        for fmt in ROUND_TRIP_FORMATS:
            try:
                blob = embroidery_io.write_embroidery(original, fmt)
                imported = embroidery_io.read_embroidery(blob, fmt)
            except (ValueError, OSError) as exc:  # a format that cannot round-trip is data too
                print(f"{name}.{fmt:34s} ROUND-TRIP FAILED: {exc}")
                continue
            check(f"{name.split('_')[0]}.{fmt}", imported)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
