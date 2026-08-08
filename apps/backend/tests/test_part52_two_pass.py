"""The two-pass split and the artifact it exists to produce (v2 Part 52).

Part 51 measured that the direction field's quality is mostly decided by its SEED
MASK, and that the only seed a one-pass `digitize_image` could reach — the
segmentation foreground silhouette — was the worst of the three candidates. This
part splits the pipeline so the best seed, the union of every object's own
outline, exists before any generator runs.

What has to stay true, and is easy to break silently:

* the split must not change a single stitch — pass B still sews exactly what the
  one loop sewed, in the same order, with the same logs;
* the field must be solved from the union seed, once per design, AFTER every
  region is known and BEFORE any of them is sewn;
* seed accumulation must stay bounded on pathological input. The contour loop
  runs once per region BEFORE the speck filter, so a full-frame operation there
  is multiplied by the NOISE count — the shape behind both the Part 48 and Part
  49 regressions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import direction_field as DF
from app.services.digitizer import digitize_image, staging
from app.services.digitizer import pipeline as PL


def _fixture(name: str = "01_flat_2color_logo") -> bytes:
    return (BACKEND_ROOT / "tests/fixtures/quality_bench" / f"{name}.png").read_bytes()


@pytest.fixture(scope="module")
def digitized():
    cv2.setRNGSeed(1234)
    design = digitize_image(_fixture(), "cotton", "100x100", 2)
    return design, staging.last_field_artifact()


# ── the artifact ──────────────────────────────────────────────────────────────


def test_the_pipeline_exposes_a_field_solved_from_the_union_seed(digitized):
    design, art = digitized
    assert art is not None and art.field is not None
    assert art.seed_px > 0
    assert art.region_count == len([o for o in design.objects if o.contour]), (
        "the seed should be built from exactly the regions that became objects"
    )
    # The seed covers ground but is not the whole frame — a seed that filled its
    # frame would be a silhouette by another name.
    assert 0 < art.seed_px < art.seed_mask.size


def test_the_seed_is_the_object_outlines_not_the_foreground_silhouette(monkeypatch):
    """The distinction Part 51 measured at 2.35 deg on the panel.

    The foreground mask is one blob whose boundary is the subject's outline; the
    seed is every region's own boundary. Asserted against the real foreground the
    run produced, not against a shape property — a solid logo legitimately fills
    its own convex hull, so 'sparser than its hull' proves nothing in general.

    A fixture with interior structure is used on purpose: on artwork that IS a
    single blob the two seeds coincide and the test could not fail.
    """
    grabbed: dict = {}
    real = PL._sketch_from_labels

    def spy(labels, fg_mask):
        grabbed.setdefault("fg", fg_mask.copy())
        return real(labels, fg_mask)

    monkeypatch.setattr(PL, "_sketch_from_labels", spy)
    cv2.setRNGSeed(1234)
    digitize_image(_fixture("02_logo_fine_text_3color"), "cotton", "180x130", 3)
    art = staging.last_field_artifact()
    fg = grabbed["fg"]

    assert art is not None and art.seed_px > 0
    assert fg.shape == art.seed_mask.shape, "seed and foreground must share a frame"
    fg_px = int(cv2.countNonZero(fg))
    assert art.seed_px < fg_px, (
        f"the seed ({art.seed_px} px) is not smaller than the foreground "
        f"({fg_px} px) — it may have reverted to the silhouette"
    )
    # The gaps the foreground swallows are exactly the interior boundaries the
    # field is seeded from, so they have to be a real share of the mask.
    assert art.seed_px < 0.99 * fg_px


def test_the_field_is_solved_once_per_design(monkeypatch):
    """Once for the whole design — not per cluster, not per region.

    Part 51 measured per-cluster seeding as WORSE than the union, and per-region
    solving would put a full solve inside the contour loop, which is the cost
    shape this repo has shipped twice by accident.
    """
    calls = {"n": 0}
    real = DF.solve

    def counting_solve(mask, **kw):
        calls["n"] += 1
        return real(mask, **kw)

    monkeypatch.setattr(PL.direction_field, "solve", counting_solve)
    cv2.setRNGSeed(1234)
    digitize_image(_fixture(), "cotton", "100x100", 2)
    assert calls["n"] == 1, f"field solved {calls['n']} times, expected once"


# ── the sequencing ────────────────────────────────────────────────────────────


def test_every_region_is_collected_before_any_is_sewn(monkeypatch):
    """The whole point of the split, asserted on the real call order.

    If a generator ever ran before collection finished, the union seed handed to
    it would be partial — which is exactly the failure the one-pass pipeline had,
    just harder to see.
    """
    events: list[str] = []
    real_solve = DF.solve
    real_fill = PL._fill_by_component

    def solve_spy(mask, **kw):
        events.append("solve")
        return real_solve(mask, **kw)

    def fill_spy(*a, **kw):
        events.append("fill")
        return real_fill(*a, **kw)

    monkeypatch.setattr(PL.direction_field, "solve", solve_spy)
    monkeypatch.setattr(PL, "_fill_by_component", fill_spy)
    cv2.setRNGSeed(1234)
    digitize_image(_fixture(), "cotton", "100x100", 2)

    assert "solve" in events, "no field was solved"
    assert "fill" in events, "nothing was sewn — the test proves nothing"
    assert events.index("solve") < events.index("fill"), (
        "a fill ran before the field was solved; collection and generation are "
        "not actually separated"
    )


def test_a_blank_image_yields_no_field_rather_than_a_solve_on_nothing():
    blank = cv2.imencode(".png", np.full((80, 80, 3), 255, np.uint8))[1].tobytes()
    cv2.setRNGSeed(1234)
    digitize_image(blank, "cotton", "100x100", 2)
    art = staging.last_field_artifact()
    assert art is not None
    assert art.seed_px == 0
    assert art.field is None


# ── seed accumulation ─────────────────────────────────────────────────────────


def test_add_to_seed_matches_a_full_frame_draw_exactly():
    """The bounding-box optimisation must be exact, not merely close.

    It exists so seed accumulation is proportional to region area rather than to
    frame area times region count. If it ever diverges from the obvious
    implementation, the seed silently stops being the union it claims to be.
    """
    rng = np.random.default_rng(3)
    frame = (200, 260)
    fast = np.zeros(frame, np.uint8)
    slow = np.zeros(frame, np.uint8)
    for _ in range(25):
        cx, cy = int(rng.integers(20, 240)), int(rng.integers(20, 180))
        rx, ry = int(rng.integers(6, 30)), int(rng.integers(6, 30))
        shape = np.zeros(frame, np.uint8)
        cv2.ellipse(shape, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
        cs, _ = cv2.findContours(shape, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cs:
            continue
        hole = np.zeros(frame, np.uint8)
        cv2.circle(hole, (cx, cy), max(2, min(rx, ry) // 3), 255, -1)
        hs, _ = cv2.findContours(hole, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        staging.add_to_seed(fast, cs[0], list(hs))
        one = np.zeros(frame, np.uint8)
        cv2.drawContours(one, [cs[0]], -1, 255, thickness=cv2.FILLED)
        cv2.drawContours(one, list(hs), -1, 0, thickness=cv2.FILLED)
        slow |= one

    assert int(cv2.countNonZero(cv2.bitwise_xor(fast, slow))) == 0


def test_seed_accumulation_does_not_scale_with_frame_size():
    """A region costs its own area, not the frame's.

    Same 30 small shapes composited into a small frame and into a frame 25x
    larger. A full-frame draw per region would make the big frame ~25x dearer;
    bounding-box work makes it roughly free.
    """
    import time

    def build(frame):
        seed = np.zeros(frame, np.uint8)
        shapes = []
        for k in range(30):
            one = np.zeros(frame, np.uint8)
            cv2.circle(one, (30 + 7 * k, 30 + 5 * k), 12, 255, -1)
            cs, _ = cv2.findContours(one, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            shapes.append(cs[0])
        t0 = time.perf_counter()
        for c in shapes:
            staging.add_to_seed(seed, c, [])
        return time.perf_counter() - t0

    small = build((400, 400))
    big = build((2000, 2000))
    assert big < 6.0 * max(small, 1e-4), (
        f"25x the frame area cost {big / max(small, 1e-9):.1f}x the time — "
        "seed accumulation is tracking frame size, not region size"
    )


@pytest.mark.skipif(os.environ.get("CI") == "true",
                    reason="timing-ratio budget calibrated on dev hardware; shared CI runners are too noisy for it")
def test_solving_the_seed_is_flat_in_region_count():
    """Pathological inputs must not multiply the solve.

    The solver works at a fixed resolution, so a mask broken into vastly more
    pieces costs about the same. This is the guarantee that lets the field sit in
    the pipeline at all.
    """
    import time

    rng = np.random.default_rng(1)
    few = np.zeros((900, 900), np.uint8)
    cv2.rectangle(few, (50, 50), (850, 850), 255, -1)
    many = (rng.random((900, 900)) > 0.5).astype(np.uint8) * 255
    n_few = len(cv2.findContours(few, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0])
    n_many = len(cv2.findContours(many, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0])
    assert n_many > 1000 * n_few

    DF.solve(few)
    t0 = time.perf_counter(); DF.solve(few); t_few = time.perf_counter() - t0
    t0 = time.perf_counter(); DF.solve(many); t_many = time.perf_counter() - t0
    assert t_many < 25.0 * max(t_few, 1e-3), (
        f"{n_many} contours cost {t_many:.3f}s vs {t_few:.3f}s for {n_few}"
    )
    assert t_many < 2.0
