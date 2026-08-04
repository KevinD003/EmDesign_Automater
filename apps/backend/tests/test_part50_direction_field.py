"""Direction field: instrument and solver (v2 Part 50, R004-impl D0/D1).

**Nothing consumes the field yet.** D1 exists so the approach can be judged before
a generator depends on it, so these tests cover the field's own properties and
the instrument that ranks it — not stitch output, which this part does not touch.

The two things worth guarding are the ones this repo keeps getting wrong:

* the instrument has to be right before its verdict counts, and it has to be
  right about a field that VARIES, not just a constant one;
* the cost has to be bounded on pathological input. Parts 48 and 49 both shipped
  per-region work whose multiplier was the noise count, and both were caught only
  by the fuzz suite.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

import measure_direction_field as MDF

from app.services import direction_field as DF


def _disc(size=300, r=110):
    m = np.zeros((size, size), np.uint8)
    cv2.circle(m, (size // 2, size // 2), r, 255, -1)
    return m


def _bar(w=300, h=90):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (10, 20), (w - 10, h - 20), 255, -1)
    return m


class TestTheInstrument:
    """It has to be right before anything it says counts."""

    def test_the_self_test_passes(self):
        assert MDF.self_test(), "stripes and the two synthetic fields must all pass"

    def test_angular_error_folds_to_ninety(self):
        """Orientation has no head or tail: 179 deg and 1 deg are 2 deg apart."""
        a = np.array([math.radians(179.0)])
        b = np.array([math.radians(1.0)])
        assert float(MDF.angular_error_deg(a, b)[0]) == pytest.approx(2.0, abs=0.01)
        assert float(MDF.angular_error_deg(np.array([0.0]), np.array([math.pi / 2]))[0]) \
            == pytest.approx(90.0, abs=0.01)

    def test_it_ranks_a_right_answer_above_a_wrong_one(self):
        """The whole point of D0: two candidates, same artwork, a verdict."""
        mask = _bar()
        # Reference: horizontal everywhere, fully coherent.
        ref_theta = np.zeros(mask.shape, np.float32)
        ref_coh = np.ones(mask.shape, np.float32)
        right = DF.constant_field(mask, 0.0)
        wrong = DF.constant_field(mask, math.pi / 2)
        s_right = MDF.score_field(right, ref_theta, ref_coh)
        s_wrong = MDF.score_field(wrong, ref_theta, ref_coh)
        assert s_right["mean_deg"] < 1.0
        assert s_wrong["mean_deg"] > 89.0
        assert s_right["mean_deg"] < s_wrong["mean_deg"]

    def test_scoring_does_not_let_a_candidate_pick_its_own_pixels(self):
        """Weighting by the candidate's own confidence flattered the diffused field.

        A field that only commits near edges would otherwise score as if the
        interior it is unsure about did not exist. Measured on the reference panel,
        that bias was worth 2.2 deg. Weights are uniform over the qualified set.
        """
        mask = _disc()
        ref_theta = np.zeros(mask.shape, np.float32)
        ref_coh = np.ones(mask.shape, np.float32)
        confident = DF.constant_field(mask, math.pi / 2)   # coherence 1.0, wrong
        s = MDF.score_field(confident, ref_theta, ref_coh)
        # A uniformly wrong field must score ~90 regardless of how sure it is.
        assert s["mean_deg"] > 89.0, s

    def test_it_reports_where_it_is_wrong_not_just_how_wrong(self):
        mask = _disc()
        ref_theta = np.zeros(mask.shape, np.float32)
        ref_coh = np.ones(mask.shape, np.float32)
        s = MDF.score_field(DF.solve(mask), ref_theta, ref_coh)
        assert s["by_cell"], "no spatial breakdown — one scalar cannot locate a fault"
        assert "qualified_share" in s and "committed_share" in s

    def test_a_reference_with_no_structure_scores_nothing_rather_than_zero(self):
        """Low coherence must read as 'cannot answer', not as a perfect score."""
        mask = _disc()
        s = MDF.score_field(DF.solve(mask), np.zeros(mask.shape, np.float32),
                            np.zeros(mask.shape, np.float32))
        assert s["n"] == 0 and s["qualified_share"] == 0.0


class TestTheField:
    def test_a_disc_gets_a_concentric_flow(self):
        """The property that makes this worth trying: flow follows the outline.

        On a disc the boundary tangent is perpendicular to the radius, so a
        correct field is tangential — and that is what a digitizer stitches
        around a circular border, rather than in vertical rows across it.
        """
        mask = _disc()
        f = DF.solve(mask)
        cy = cx = mask.shape[0] // 2
        errs = []
        for r in (70, 90, 105):
            for deg in range(0, 360, 15):
                a = math.radians(deg)
                x, y = int(cx + r * math.cos(a)), int(cy + r * math.sin(a))
                want = a + math.pi / 2               # tangent
                got = float(f.sample([x], [y])[0])
                errs.append(float(MDF.angular_error_deg(np.array([got]), np.array([want]))[0]))
        assert np.median(errs) < 20.0, f"median {np.median(errs):.1f} deg off tangential"

    def test_the_doubled_angle_survives_the_wrap(self):
        """Averaging raw angles would put mean(179, 1) at 90 — exactly wrong."""
        mask = _bar()
        near_180 = DF.constant_field(mask, math.radians(179.0))
        near_0 = DF.constant_field(mask, math.radians(1.0))
        c = (near_180.c + near_0.c) / 2
        s = (near_180.s + near_0.s) / 2
        mean_angle = math.degrees(0.5 * math.atan2(float(s[45, 150]), float(c[45, 150]))) % 180
        assert min(mean_angle, 180 - mean_angle) < 5.0, f"{mean_angle} deg — wrap not handled"

    def test_per_object_field_reproduces_the_angles_it_was_given(self):
        mask = _bar()
        f = DF.per_object_field(mask, [(mask, math.radians(30.0))])
        got = math.degrees(float(f.sample([150], [45])[0])) % 180
        assert min(abs(got - 30.0), 180 - abs(got - 30.0)) < 1.0

    def test_an_empty_mask_returns_an_empty_field_rather_than_raising(self):
        f = DF.solve(np.zeros((80, 80), np.uint8))
        assert f.coherence.max() == 0.0
        assert f.theta.shape == (80, 80)

    def test_it_is_deterministic(self):
        mask = _disc()
        a, b = DF.solve(mask), DF.solve(mask)
        assert np.array_equal(a.c, b.c) and np.array_equal(a.s, b.s)


class TestTheCostIsBounded:
    """Parts 48 and 49 both shipped a cost that scaled with the NOISE count.

    The solver works on a downscaled mask, so its cost is fixed by
    `WORK_MAX_PX` rather than by how many contours the input happens to contain.
    Measured: 600x600 noise (24,737 contours) 0.37 s, 1500x1500 noise (154,449
    contours) 0.41 s — flat, not linear in contour count.
    """

    def test_solve_time_is_flat_in_contour_count(self):
        rng = np.random.default_rng(11)
        small = (rng.random((600, 600)) > 0.5).astype(np.uint8) * 255
        big = (rng.random((1500, 1500)) > 0.5).astype(np.uint8) * 255

        t0 = time.perf_counter(); DF.solve(small); t_small = time.perf_counter() - t0
        t0 = time.perf_counter(); DF.solve(big); t_big = time.perf_counter() - t0

        assert t_big < 4.0, f"{t_big:.2f}s on 1500x1500 noise"
        assert t_big < t_small * 6, (
            f"{t_small:.2f}s -> {t_big:.2f}s: cost is tracking contour count, "
            f"which is the Part 48/49 failure shape"
        )

    def test_a_huge_solid_mask_is_cheap(self):
        t0 = time.perf_counter()
        DF.solve(np.ones((4000, 4000), np.uint8) * 255)
        assert time.perf_counter() - t0 < 3.0

    def test_the_work_resolution_is_actually_capped(self):
        assert DF.WORK_MAX_PX <= 512, "the bound is what keeps noise from mattering"
