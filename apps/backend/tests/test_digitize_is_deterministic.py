"""The same upload must always produce the same design.

CP1, 2026-08-10. `_palette_centers` called `cv2.kmeans(..., KMEANS_PP_CENTERS)`
with no seed, so k-means++ drew from OpenCV's THREAD-LOCAL RNG. `routers/
digitize.py` declares its handler with a plain `def`, so FastAPI dispatches it
to the anyio threadpool, whose workers are reused — RNG state carried from one
customer's request straight into the next.

Measured on four byte-identical uploads of one fixture, one worker:

    run 1   6 stops   8,694 stitches
    run 2   6 stops   8,755 stitches
    run 3   6 stops   8,673 stitches
    run 4   5 stops   8,486 stitches

Four different products from one file, including a different NUMBER OF THREADS
the customer has to buy.

WHY NO TEST CAUGHT THIS, WHICH IS THE MORE IMPORTANT LESSON. Every bench script
and quality test calls `cv2.setRNGSeed(RNG_SEED)` immediately before
`digitize_image`. The harness was supplying the determinism the library owed, so
the whole suite was reproducible while production was not. A test that seeds
before the call CANNOT observe this class of defect.

So these tests deliberately do the opposite:

  * they never seed, so they see what a customer sees;
  * they actively DIRTY the RNG between runs, reproducing worker reuse.

Any future determinism defect — an unseeded sample, a `set` iteration that
leaks into geometry, a dict ordering dependency — fails here rather than
reaching a customer.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.digitizer import digitize_image

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "quality_bench"

# One flat-vector design and one photographic/gradient design: the gradient is
# where the palette k-means has many near-equal optima and so where the defect
# showed most, but flat art drifted on stitch count too.
FIXTURES = ("03_gradient_soft_subject", "01_flat_2color_logo")

PARAMS = {"fabric_type": "cotton", "hoop_size": "130x180",
          "max_colors": 6, "text_mode": False}


def _dirty_rng() -> None:
    """Leave the thread-local RNG where a previous request would have left it.

    This is the whole point of the test. `cv2.kmeans` with `KMEANS_PP_CENTERS`
    consumes from `cv2.theRNG()`, so running one here advances the state exactly
    as another customer's digitize would on a reused threadpool worker.
    """
    junk = np.random.RandomState(0).rand(400, 3).astype(np.float32)
    cv2.kmeans(junk, 5, None, (cv2.TERM_CRITERIA_EPS, 5, 1.0), 3,
               cv2.KMEANS_PP_CENTERS)


def _stream_hash(design) -> str:
    lines = []
    for s in design.stitches:
        cmd = s.command.value if hasattr(s.command, "value") else str(s.command)
        lines.append(f"{cmd}|{s.x:.4f}|{s.y:.4f}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _digitize(name: str):
    return digitize_image((FIXTURE_DIR / f"{name}.png").read_bytes(), **PARAMS)


@pytest.mark.parametrize("fixture", FIXTURES)
def test_repeated_uploads_are_byte_identical(fixture):
    """Four uploads, RNG dirtied between each. NOT seeded — that is the test."""
    hashes, stops, counts = set(), set(), set()
    for _ in range(4):
        _dirty_rng()
        d = _digitize(fixture)
        hashes.add(_stream_hash(d))
        stops.add(len(d.color_stops))
        counts.add(d.stitch_count)

    assert len(stops) == 1, (
        f"{fixture}: the colour COUNT varies between identical uploads {sorted(stops)} — "
        "a customer would be told to buy a different number of threads each time"
    )
    assert len(counts) == 1, f"{fixture}: stitch count varies {sorted(counts)}"
    assert len(hashes) == 1, f"{fixture}: {len(hashes)} distinct stitch streams from one file"


def test_prior_rng_state_cannot_change_the_result():
    """Determinism must not depend on the RNG being clean when we are called.

    Digitize once from a freshly seeded RNG and once from a deliberately
    mangled one. Seeding INSIDE `digitize_image` is what makes these agree; a
    fix applied only at the call site of one k-means would not.
    """
    cv2.setRNGSeed(1)
    clean = _stream_hash(_digitize(FIXTURES[0]))

    cv2.setRNGSeed(999_983)
    for _ in range(3):
        _dirty_rng()
    dirty = _stream_hash(_digitize(FIXTURES[0]))

    assert clean == dirty, (
        "the result depends on RNG state left by earlier work on this thread — "
        "this is exactly the FastAPI threadpool-reuse defect"
    )


def test_the_harness_seed_and_the_library_seed_agree():
    """Guards the no-churn property, and would catch a silent baseline break.

    Committed hashes and visual baselines were captured by harnesses that seed
    with `run_quality_bench.RNG_SEED` before calling. `digitize_image` now seeds
    internally with `DIGITIZE_RNG_SEED`. While the two are equal, every existing
    baseline stays valid; if someone changes one, every pin in the repo silently
    needs re-cutting, so fail loudly here instead.
    """
    import sys
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from run_quality_bench import RNG_SEED

    from app.services.digitizer.constants import DIGITIZE_RNG_SEED

    assert DIGITIZE_RNG_SEED == RNG_SEED, (
        f"DIGITIZE_RNG_SEED ({DIGITIZE_RNG_SEED}) no longer matches the bench "
        f"harness seed ({RNG_SEED}). Every committed stitch hash and visual "
        "baseline was captured under the harness seed; they must be re-pinned "
        "deliberately, not broken by accident."
    )


def test_digitize_seeds_before_any_random_work():
    """Structural: the seed must be at the TOP of digitize_image.

    Seeded late, everything upstream of it — segmentation, the texture gate,
    the mean-shift — still inherits foreign RNG state. Asserted on source order
    rather than behaviour because a late seed would pass the behavioural tests
    above on any fixture whose upstream stages happen not to draw.
    """
    import inspect

    from app.services.digitizer import pipeline

    src = inspect.getsource(pipeline.digitize_image)
    seed_at = src.find("cv2.setRNGSeed(DIGITIZE_RNG_SEED)")
    assert seed_at != -1, "digitize_image no longer seeds the RNG"

    decode_at = src.find("_decode_image_bgr(data)")
    assert decode_at != -1
    assert seed_at < decode_at, (
        "the RNG seed must come before the image is even decoded, so no stage "
        "can consume foreign randomness"
    )
