"""v2 Part 33 — sketch-then-verify: outline first, check against the original,
only then fill.

The plan's region boundaries ARE its sketch; verification measures them
against the source's own edges. A plan that merged two regions the artwork
separates (a missing line) is the one failure a colour-budget retry can fix —
and the corpus is calibrated to verify on the FIRST attempt (coverage
0.977-1.000 vs the 0.55 gate), so flat artwork's path and RNG stream are
untouched, which the stream locks prove.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services import digitizer as D
from app.services.digitizer import _sketch_from_labels, _verify_sketch, digitize_image


def _checkerboard() -> bytes:
    """Two similar-but-distinct reds checkerboarded: merging them erases nearly
    every internal edge, which is exactly the failure the verify loop exists
    to catch."""
    img = np.full((360, 360, 3), 255, np.uint8)
    for i in range(6):
        for j in range(6):
            cv2.rectangle(img, (30 + i * 50, 30 + j * 50), (30 + (i + 1) * 50, 30 + (j + 1) * 50),
                          (60, 60, 190) if (i + j) % 2 == 0 else (60, 90, 190), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_sketch_of_a_good_plan_verifies():
    labels = np.full((200, 200), -1, np.int32)
    labels[40:160, 40:100] = 0
    labels[40:160, 100:160] = 1
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (100, 160), (40, 40, 200), -1)
    cv2.rectangle(img, (100, 40), (160, 160), (40, 160, 40), -1)
    fg = ((labels >= 0).astype(np.uint8)) * 255
    cov, prec = _verify_sketch(_sketch_from_labels(labels, fg), img, fg)
    assert cov > 0.9 and prec > 0.7


def test_sketch_missing_a_boundary_scores_measurably_lower():
    """One label where the image has two regions: the internal edge is missing
    from the merged plan's sketch, and coverage must rank the split plan above
    it by at least the share of edge the boundary represents (~19% here)."""
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (100, 160), (40, 40, 200), -1)
    cv2.rectangle(img, (100, 40), (160, 160), (40, 160, 40), -1)
    merged = np.full((200, 200), -1, np.int32)
    merged[40:160, 40:160] = 0
    split = merged.copy()
    split[40:160, 100:160] = 1
    fg = ((merged >= 0).astype(np.uint8)) * 255
    cov_merged, _ = _verify_sketch(_sketch_from_labels(merged, fg), img, fg)
    cov_split, _ = _verify_sketch(_sketch_from_labels(split, fg), img, fg)
    assert cov_split > 0.95
    assert cov_merged < cov_split - 0.15


def test_failed_plan_is_redrawn_and_the_user_is_told():
    """End to end: at max_colors=1 the checkerboard's first plan measures
    coverage 0.493 — below the gate — and the re-plan at a larger budget
    recovers both reds. Exceeding the user's colour ask is never silent."""
    attempts = []
    orig = D._verify_sketch

    def spy(sk, im, fg):
        r = orig(sk, im, fg)
        attempts.append(r)
        return r

    D._verify_sketch = spy
    try:
        d = digitize_image(_checkerboard(), "cotton", "100x100", max_colors=1)
    finally:
        D._verify_sketch = orig
    assert len(attempts) >= 2, "the failed plan was not retried"
    assert attempts[0][0] < D.SKETCH_MIN_COVERAGE
    assert max(a[0] for a in attempts) > 0.9
    assert len({s.hex for s in d.color_stops}) == 2
    assert any("Outline check" in w and "re-drawn" in w for w in d.warnings), d.warnings


def test_good_first_plan_stays_quiet():
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.circle(img, (150, 150), 100, (40, 40, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    d = digitize_image(buf.tobytes(), "cotton", "100x100", max_colors=2)
    assert not any("Outline check" in w for w in d.warnings), d.warnings
