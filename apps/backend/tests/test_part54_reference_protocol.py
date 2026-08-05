"""The reference protocol's own tooling (v2 Part 54, R004).

Part 53 found that the sew-out photograph cannot judge stitch direction on thin
structures. Part 54 builds the protocol for a reference that can — a capture
spec derived from the panel's own downsample law, plus crop registration so a
macro close-up can be placed in the design's coordinate frame.

Two things here have already been wrong once and are pinned so they stay fixed:

* `crossover_width` must express "the width ABOVE WHICH the reference is
  trustworthy". Scanning upward for the first bucket that reads thread collapses
  to the bottom of the range on one noisy bucket, and did — it reported
  "0.4 mm, 100% usable" at a scale Part 53 had already measured as unusable.
* crop registration must recover a transform we applied ourselves. A plausible
  mapping that nobody checked is exactly what Part 52 had to correct.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(BACKEND_ROOT), str(BACKEND_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import reference_protocol as RP

WIDTHS = tuple(round(0.4 + 0.2 * i, 2) for i in range(29))


def _rows(spec: dict[float, bool], n: int = 400):
    """Rows whose reference either agrees with the thread or with the axis.

    `spec` maps a bucket's lower edge to True (reads thread) or False (reads the
    column axis). Sewn direction is 0 throughout, so a thread-reading bucket puts
    the reference near 0 and an axis-reading bucket puts it near 90.
    """
    rows = []
    for lo, thread in spec.items():
        ref = 0.0 if thread else math.pi / 2
        for _ in range(n):
            rows.append({"width_mm": lo + 0.1, "sewn": 0.0, "ref": ref})
    return rows


def test_crossover_is_where_the_reading_becomes_consistently_thread():
    rows = _rows({0.6: False, 1.0: False, 1.4: True, 1.8: True, 2.2: True})
    assert RP.crossover_width(rows, WIDTHS) == 1.4


def test_one_noisy_narrow_bucket_does_not_collapse_the_crossover():
    """The regression that produced '0.4 mm, 100% usable'.

    A single thread-reading bucket at the bottom, with edges above it, must not
    be mistaken for the crossover — everything above it is still untrustworthy.
    """
    rows = _rows({0.6: True, 1.0: False, 1.4: False, 1.8: True, 2.2: True})
    got = RP.crossover_width(rows, WIDTHS)
    assert got == 1.8, f"expected 1.8 (above the last edges bucket), got {got}"


def test_no_crossover_when_nothing_reads_thread():
    rows = _rows({0.6: False, 1.0: False, 1.4: False})
    assert RP.crossover_width(rows, WIDTHS) is None


def test_sparse_buckets_are_ignored_rather_than_trusted():
    """A handful of segments cannot establish that a width is trustworthy."""
    rows = _rows({1.0: False, 1.4: True, 1.8: True})
    rows += _rows({0.6: True}, n=5)     # too few to count
    assert RP.crossover_width(rows, WIDTHS) == 1.4


def test_crop_registration_recovers_a_known_transform():
    """A macro crop must land back where it came from, to about a pixel."""
    full = cv2.imread(str(BACKEND_ROOT / "tests/fixtures/reference_sewout.jpg"))
    assert full is not None, "the committed sew-out reference is missing"
    x, y, w, h = 200, 700, 300, 300
    for factor in (2.0, 3.0):
        crop = cv2.resize(full[y:y + h, x:x + w], None, fx=factor, fy=factor,
                          interpolation=cv2.INTER_CUBIC)
        M, inliers, scale = RP.register_crop(crop, full)
        assert M is not None, f"{factor}x crop failed to register"
        assert inliers >= 10, f"only {inliers} inliers at {factor}x"
        origin = M @ np.array([0.0, 0.0, 1.0])
        assert math.hypot(origin[0] - x, origin[1] - y) < 12.0
        assert abs(scale - 1.0 / factor) * factor < 0.05


def test_registration_reports_failure_rather_than_a_wrong_answer():
    """An unrelated image must not produce a confident placement."""
    full = cv2.imread(str(BACKEND_ROOT / "tests/fixtures/reference_sewout.jpg"))
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (200, 200, 3), dtype=np.uint8)
    M, inliers, _scale = RP.register_crop(noise, full)
    assert M is None or inliers < 15, (
        f"random noise registered against the panel with {inliers} inliers"
    )
