"""Diff two `run_corpus100.py` result files, by provenance tier.

    scripts/compare_corpus100.py baseline.json candidate.json

WHY THIS EXISTS. Every headline number in the 2026-08-09/10 engagement — the
badge at 22.65 machine-minutes, the corpus down 33.4%, the width survey, the
Zhang-Suen parity fix — was measured on the TEN-fixture quality bench. The
hundred-design corpus and its runner were already in the tree and were not run
once. A change can look clean on ten synthetic fixtures and be wrong on real
photographed artwork, and nothing was checking.

TIERS ARE NOT INTERCHANGEABLE, so this never prints a single blended average.
`build_corpus100.py` records the provenance and it is the whole point:

    A  real          13  the 3 supplied embroidery photographs + the 10 bench fixtures
    B  real-derived  40  crops/rotations/rescales/recolours of those photographs;
                         real thread texture and lighting, synthetic framing
    C  parametric    47  generated artwork; good for crashes, floor violations and
                         pathological routing, NOT for real-world fidelity claims

A regression confined to tier C is a different thing from one that shows up in
tier A, and averaging them hides exactly that. Tier A moving is the one that
should stop a change.

Exit code is 1 if any design newly errors, or if any design in tier A or B
regresses on a hard-quality metric — so this can gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Metrics where a RISE is bad. Kept explicit rather than inferred: several
# fields in the corpus record (stitches, objects) are neither good nor bad on
# their own and must not be graded.
WORSE_IF_UP = {
    "floor_violations": "stitches under the needle-safety floor",
    "over_limit": "stitches over the 12.7mm machine limit",
    "density_flags": "cells flagged as over-dense",
}
# Metrics where a FALL is bad.
WORSE_IF_DOWN = {
    "interior": "interior coverage %",
}
# `interior` is NOT always a percentage. `measure_stitch_quality` returns None
# when a shape is thinner than 2x EROSION_MM and so has no interior at all --
# it is all edge band -- and `run_corpus100.py` stores that as -1.0. Arithmetic
# on the sentinel is meaningless: the first version of this file reported
# `C45_thin_border 100.0 -> -1.0` as a 101-point coverage drop and, worse,
# `-1.0 -> 0.0` as an IMPROVEMENT on two other designs. A shape gaining or
# losing its interior is a STRUCTURAL change and gets its own category.
NA_SENTINEL = -1.0
# Coverage genuinely moves when stitch placement changes, so a tolerance is
# needed. This one is MEASURED, not chosen: across the 96 comparable designs of
# the Zhang-Suen parity comparison — a change that only reorders thinning and
# should therefore be near-neutral — the absolute coverage delta distributes
#
#     p50 0.00   p75 0.10   p90 0.20   p95 0.30   max 1.20
#
# with 97% of designs inside 0.35. Sitting the tolerance just above p95 isolates
# the three designs that genuinely moved (B00_crop +1.2, C23_monogram -0.9,
# B39_recolour +0.4) and treats the rest as placement jitter. An earlier version
# used 0.1 picked a priori and reported 12 "regressions", nine of them on real
# artwork, all of which were 0.1-0.3 points and half of which had a matching
# improvement elsewhere — the same error as setting a quality band from a single
# reading. Re-derive this from a fresh near-neutral comparison if the pipeline's
# placement noise changes.
COVERAGE_TOL = 0.35
# Reported for context, never graded as better/worse — more stitches is not
# inherently bad and fewer is not inherently good.
CONTEXT = ("stitches", "objects", "colors", "trims", "jumps", "seconds")

# ...but a change in OBJECT COUNT is never noise. It means classification or
# segmentation reached a different answer about what the artwork contains, and
# on a near-neutral change that is worth a human look even when every graded
# metric holds. C45_thin_border went 2 objects/4,141 stitches -> 3/5,952 (+44%)
# under the parity fix and was caught only incidentally, through the interior
# sentinel; nothing here was grading it. A large stitch swing on an UNCHANGED
# object count is the same signal from the other side.
STITCH_SWING_FRAC = 0.15


def tier_of(rec: dict, name: str) -> str:
    """The runner records provenance directly; the name is only a fallback."""
    t = rec.get("tier")
    if t:
        return str(t)
    return {"A": "A-real", "B": "B-real-derived", "C": "C-parametric"}.get(name[:1], "other")


def _errored(rec: dict) -> bool:
    """The runner marks failure with ok=False and may attach a traceback."""
    return bool(rec.get("error")) or rec.get("ok") is False


def load(path: Path) -> dict:
    raw = json.loads(path.read_text())
    rows = raw.get("results", raw) if isinstance(raw, dict) else raw
    out = {}
    for r in rows:
        name = r.get("name") or r.get("design") or r.get("fixture")
        if name:
            out[name] = r
    if not out:
        raise SystemExit(f"no per-design records found in {path}")
    return out


def num(rec: dict, key: str):
    v = rec.get(key)
    return v if isinstance(v, (int, float)) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", type=Path)
    ap.add_argument("candidate", type=Path)
    ap.add_argument("--all", action="store_true", help="list every design, not just changes")
    args = ap.parse_args()

    base, cand = load(args.baseline), load(args.candidate)
    names = sorted(set(base) | set(cand))

    # Errors first: a design that newly crashes outranks any metric movement.
    new_errors, fixed_errors = [], []
    for n in names:
        b_err = _errored(base.get(n, {}))
        c_err = _errored(cand.get(n, {}))
        if c_err and not b_err:
            new_errors.append((n, cand[n].get("error", "ok=False")))
        elif b_err and not c_err:
            fixed_errors.append(n)

    regressions, improvements, structural = [], [], []
    per_tier: dict[str, dict] = {}

    for n in names:
        b, c = base.get(n), cand.get(n)
        if not b or not c or _errored(b) or _errored(c):
            continue
        t = tier_of(c, n)
        agg = per_tier.setdefault(t, {"n": 0, **{k: [0, 0] for k in CONTEXT}})
        agg["n"] += 1
        for k in CONTEXT:
            bv, cv = num(b, k), num(c, k)
            if bv is not None and cv is not None:
                agg[k][0] += bv
                agg[k][1] += cv

        bo, co = num(b, "objects"), num(c, "objects")
        if bo is not None and co is not None and bo != co:
            structural.append((t, n, "object count", bo, co))
        bs, cs = num(b, "stitches"), num(c, "stitches")
        if (bs and cs is not None and bo == co
                and abs(cs - bs) / bs > STITCH_SWING_FRAC):
            structural.append((t, n, f"stitches moved {(cs - bs) / bs * 100:+.0f}%", bs, cs))

        for k, label in WORSE_IF_UP.items():
            bv, cv = num(b, k), num(c, k)
            if bv is None or cv is None or bv == cv:
                continue
            (regressions if cv > bv else improvements).append((t, n, label, bv, cv))
        for k, label in WORSE_IF_DOWN.items():
            bv, cv = num(b, k), num(c, k)
            if bv is None or cv is None:
                continue
            b_na, c_na = bv == NA_SENTINEL, cv == NA_SENTINEL
            if b_na or c_na:
                if b_na != c_na:
                    # Not gradable as a number. Losing an interior means every
                    # object went sub-1.2mm; gaining one means the reverse.
                    structural.append((t, n, "HAD an interior, now none" if c_na
                                       else "had NO interior, now has one", bv, cv))
                continue
            if abs(cv - bv) <= COVERAGE_TOL:
                continue
            (regressions if cv < bv else improvements).append((t, n, label, bv, cv))

    print(f"baseline  {args.baseline}")
    print(f"candidate {args.candidate}\n")

    if new_errors:
        print(f"!! {len(new_errors)} design(s) NEWLY ERROR:")
        for n, e in new_errors:
            print(f"   {n}: {str(e).splitlines()[0][:110]}")
        print()
    if fixed_errors:
        print(f"{len(fixed_errors)} design(s) no longer error: {', '.join(fixed_errors)}\n")

    print("totals by tier (context only — none of these is a quality verdict)")
    head = f"  {'tier':16s} {'n':>4s}" + "".join(f" {k:>12s}" for k in CONTEXT)
    print(head)
    print("  " + "-" * (len(head) - 2))
    for t in sorted(per_tier):
        agg = per_tier[t]
        cells = ""
        for k in CONTEXT:
            bv, cv = agg[k]
            d = ((cv - bv) / bv * 100.0) if bv else 0.0
            cells += f" {cv:8.0f}{d:+5.1f}%" if abs(d) >= 0.05 else f" {cv:8.0f}     ="
        print(f"  {t:16s} {agg['n']:4d}{cells}")
    print()

    def show(rows, title):
        if not rows:
            print(f"{title}: none")
            return
        print(f"{title}: {len(rows)}")
        for t, n, label, bv, cv in sorted(rows):
            print(f"  [{t:14s}] {n:34s} {label}: {bv} -> {cv}")

    show(structural, "STRUCTURAL — interior appeared or vanished, look at these by eye")
    print()
    show(regressions, "REGRESSIONS")
    print()
    show(improvements, "improvements")

    hard = [r for r in regressions if r[0].startswith(("A", "B"))]
    hard += [r for r in structural if r[0].startswith(("A", "B"))]
    print()
    if new_errors:
        print(f"FAIL — {len(new_errors)} new error(s)")
        return 1
    if hard:
        print(f"FAIL — {len(hard)} regression(s) or structural change(s) on real or "
              f"real-derived artwork (tier A/B)")
        return 1
    if structural:
        print(f"LOOK — {len(structural)} structural change(s) on tier C. Not blocking, "
              f"but an interior appearing or vanishing is never noise.")
    if regressions:
        print(f"PASS with note — {len(regressions)} regression(s), all on tier C parametric artwork. "
              "Worth reading, not necessarily blocking.")
        return 0
    print("PASS — no regressions on any tier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
