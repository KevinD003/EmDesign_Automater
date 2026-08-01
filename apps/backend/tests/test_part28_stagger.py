"""v2 Part 28 — staggered penetrations (fill rows and split satin).

Concept adopted from Ink/Stitch's public documentation (the fill "staggers"
parameter and staggered split-satin stitches); implementation entirely our own —
their code is GPL and none of it was read or copied.

Two instances of one defect: penetrations that align across neighbouring passes
punch a line of holes through the fabric. Measured before the fix: a 40x20mm
rectangle fill had 588 of 588 interior penetrations vertically aligned (the
"valley effect"), and an 8mm-wide satin bar put 383 same-side pairs under the
0.30mm floor purely from aligned split points down the column centre.
"""

from __future__ import annotations

import math
from itertools import pairwise

import cv2
import numpy as np

from app.services import digitizer as D
from app.services.digitizer import ZIGZAG_RATIO, _scanline_fill, digitize_image


def _alignment_share(pts, tol_px=1.5):
    rows: dict[int, list[float]] = {}
    for x, y, _j in pts:
        rows.setdefault(round(y), []).append(x)
    ys = sorted(rows)
    aligned = total = 0
    for a, b in pairwise(ys):
        for x in rows[b][1:-1]:
            total += 1
            if any(abs(x - x2) < tol_px for x2 in rows[a]):
                aligned += 1
    return aligned / max(1, total)


def test_fill_rows_do_not_align_penetrations():
    img = np.zeros((260, 460), np.uint8)
    cv2.rectangle(img, (30, 30), (430, 230), 255, -1)
    share = _alignment_share(_scanline_fill(img, 4, 30, 9.5))
    assert share < 0.10, f"{share:.0%} of interior penetrations align — the valley effect is back"


def test_fill_stagger_respects_stitch_caps():
    img = np.zeros((260, 460), np.uint8)
    cv2.rectangle(img, (30, 30), (430, 230), 255, -1)
    pts = _scanline_fill(img, 4, 30, 9.5)
    prev = None
    for x, y, j in pts:
        if prev is not None and not j and prev[1] == y:
            assert abs(x - prev[0]) <= 30 * 1.35, "stagger end-guard made an over-long stitch"
        prev = (x, y)


def _floor_violations(design) -> int:
    bad = 0
    run: list[tuple[float, float]] = []
    runs = []
    for s in design.stitches:
        if s.command == "STITCH":
            run.append((s.x, s.y))
        else:
            if len(run) >= 3:
                runs.append(run)
            run = []
    if len(run) >= 3:
        runs.append(run)
    for run in runs:
        for (a, b), (_b2, c) in zip(pairwise(run), pairwise(run[1:])):
            gap = math.dist(a, c)
            if gap < ZIGZAG_RATIO * min(math.dist(a, b), math.dist(b, c)) and gap < D.MIN_PENETRATION_MM:
                bad += 1
    return bad


def test_wide_satin_no_longer_perforates_the_column_centre():
    """Before staggered splits, this exact probe produced 383 floor violations:
    every crossing of an 8mm column split at the same midpoints, ~0.15mm apart
    crossing-to-crossing. The satin cap was capped at 4.5mm BECAUSE of this."""
    old = D.SATIN_MAX_W_MM
    try:
        D.SATIN_MAX_W_MM = 8.0
        img = np.full((400, 400, 3), 255, np.uint8)
        cv2.rectangle(img, (40, 190), (360, 216), (40, 40, 200), -1)
        ok, buf = cv2.imencode(".png", img)
        assert ok
        d = digitize_image(buf.tobytes(), "cotton", "130x180", max_colors=2)
        assert any(o.stitch_type == "SATIN" for o in d.objects)
        assert _floor_violations(d) == 0
        # And the ring, where the same alignment hid inside the curve.
        img2 = np.full((400, 400, 3), 255, np.uint8)
        cv2.circle(img2, (200, 200), 120, (40, 40, 200), 26)
        ok, buf2 = cv2.imencode(".png", img2)
        assert ok
        d2 = digitize_image(buf2.tobytes(), "cotton", "130x180", max_colors=2)
        assert _floor_violations(d2) == 0
    finally:
        D.SATIN_MAX_W_MM = old
