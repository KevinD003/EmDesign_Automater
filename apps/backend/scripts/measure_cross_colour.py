"""Is cross-colour ordering the next real cost win? (v2 Part 58)

Part 48 cut within-colour travel roughly in half by sewing a stop's regions in
proximity order, and deliberately declined to reorder across colours. Part 57
closed R005, leaving machine cost as the remaining line of work. This measures
the ceiling on cross-colour ordering BEFORE anyone implements it.

The measurement turns on one distinction that decides the whole question:

  INTRA-STOP travel   jumps between regions of the same colour. Part 48 already
                      optimises these; reordering colours cannot touch them.
  INTER-STOP travel   the jump from the last stitch of one colour to the first
                      of the next. There are exactly (stops - 1) of these, and
                      they are ALL that reordering contiguous colour stops can
                      move.

So the ceiling on "reorder the colour sequence" is bounded by inter-stop travel,
and this script measures that share directly rather than assuming it. It also
computes the best reachable inter-stop travel by solving the tiny open TSP over
the stops' entry and exit points, which is the true optimum for that policy, not
a heuristic's guess at it.

    scripts/measure_cross_colour.py

What it deliberately does NOT model: interleaving objects across colours. That
buys more travel but pays a COLOUR CHANGE per switch, and a colour change is a
re-thread — tens of seconds against a trim's ~2.5 s. Any policy that adds colour
changes to save jumps is trading a large cost for a small one, and the stop count
in the table is there to make that trade visible.
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import cv2

BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND), str(BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.digitizer import digitize_image

CORPUS = BACKEND / "tests/fixtures/corpus100"
CASES = (("A01_real_peacock_patch_photo", "360x350"),
         ("A02_real_neckline_black", "360x350"),
         ("A03_real_neckline_panel", "360x350"))
RNG_SEED = 20260728
# A trim costs roughly this much machine time; a colour change means re-threading
# or an index on a multi-needle head. Both are order-of-magnitude figures used
# only to state the trade, never to justify a threshold.
TRIM_SECONDS = 2.5
COLOUR_CHANGE_SECONDS = 20.0


def walk(design):
    """Split the stream into colour stops and measure every jump.

    A jump's length is the distance from the previous stitch to where the needle
    lands. Jumps that follow a COLOR_CHANGE are inter-stop; the rest are within
    one colour and belong to Part 48's territory.
    """
    stops = []                 # (entry_xy, exit_xy) per stop
    intra_mm = 0.0
    inter_mm = 0.0
    inter_jumps = []
    prev = None
    entry = None
    last = None
    just_changed = True
    for s in design.stitches:
        cmd = str(getattr(s, "command", "")).upper()
        xy = (s.x, s.y)
        if cmd == "COLOR_CHANGE":
            if entry is not None:
                stops.append((entry, last))
            entry = None
            just_changed = True
            prev = xy
            continue
        if cmd == "JUMP" and prev is not None:
            d = math.dist(prev, xy)
            if just_changed:
                inter_mm += d
                inter_jumps.append(d)
            else:
                intra_mm += d
        if cmd == "STITCH":
            if entry is None:
                entry = xy
            last = xy
            just_changed = False
        prev = xy
    if entry is not None:
        stops.append((entry, last))
    return stops, intra_mm, inter_mm, inter_jumps


def best_stop_order(stops):
    """Optimal inter-stop travel over a permutation of colour stops.

    Exact for small stop counts by brute force over permutations; a greedy
    nearest-exit chain beyond that, restarted from every stop. Reported as a
    CEILING on the saving, so an approximation here can only understate the win,
    never overstate it — which is the safe direction for a go/no-go.
    """
    n = len(stops)
    if n < 2:
        return 0.0, True

    def cost(order):
        return sum(math.dist(stops[order[i]][1], stops[order[i + 1]][0])
                   for i in range(len(order) - 1))

    if n <= 8:
        return min(cost(p) for p in itertools.permutations(range(n))), True
    best = float("inf")
    for start in range(n):
        order, seen = [start], {start}
        while len(order) < n:
            here = stops[order[-1]][1]
            nxt = min((i for i in range(n) if i not in seen),
                      key=lambda i: math.dist(here, stops[i][0]))
            order.append(nxt)
            seen.add(nxt)
        best = min(best, cost(order))
    return best, False


def main() -> int:
    rows = {}
    print(f"{'design':30s} {'stops':>6s} {'trims':>6s} {'travel m':>9s} "
          f"{'intra m':>8s} {'inter m':>8s} {'inter%':>7s} {'best m':>7s} {'save m':>7s}")
    for name, hoop in CASES:
        cv2.setRNGSeed(RNG_SEED)
        design = digitize_image((CORPUS / f"{name}.png").read_bytes(), "cotton", hoop, 12)
        stops, intra, inter, jumps = walk(design)
        trims = sum(1 for s in design.stitches
                    if str(getattr(s, "command", "")).upper() == "TRIM")
        best, exact = best_stop_order(stops)
        total = intra + inter
        rows[name] = {
            "stops": len(stops), "trims": trims,
            "travel_m": round(total / 1000, 2),
            "intra_m": round(intra / 1000, 2), "inter_m": round(inter / 1000, 2),
            "inter_pct": round(100 * inter / max(total, 1e-9), 1),
            "best_inter_m": round(best / 1000, 2),
            "saving_m": round((inter - best) / 1000, 2),
            "exact": exact,
            "longest_inter_mm": round(max(jumps), 1) if jumps else 0.0,
        }
        r = rows[name]
        print(f"{name:30s} {r['stops']:6d} {r['trims']:6d} {r['travel_m']:9.2f} "
              f"{r['intra_m']:8.2f} {r['inter_m']:8.2f} {r['inter_pct']:6.1f}% "
              f"{r['best_inter_m']:7.2f} {r['saving_m']:7.2f}", flush=True)

    print()
    tot_save = sum(r["saving_m"] for r in rows.values())
    tot_travel = sum(r["travel_m"] for r in rows.values())
    print(f"Across the three designs: {tot_save:.2f} m of {tot_travel:.2f} m "
          f"({100 * tot_save / max(tot_travel, 1e-9):.1f}%) is reachable by")
    print("reordering contiguous colour stops. Trims are unchanged by definition:")
    print("every object still needs one transition, whatever order the stops run in.")
    print("\n" + json.dumps(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
