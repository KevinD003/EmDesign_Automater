"""Corpus breadth: every synthetic fixture image survives POST /api/digitize.

Drives the committed mini-corpus (tests/fixtures/swarm_corpus/, built by
_generate.py in that dir) through the real endpoint and asserts the Design
contract, the machine stitch limit and pipeline determinism.

Read-only w.r.t. app code and the corpus: if an image ever regresses, xfail the
param — do NOT regenerate the fixtures, they are the regression baseline.

MEASURED per-image wall clock on this box (first request pays ~2s cold import):
    01_gradient_blob  2.79s   200  stitchCount=830   w=32.13 h=32.14 stops=1
    02_photo_like     1.49s   200  stitchCount=1562  w=68.36 h=48.97 stops=3
    03_tiny_text      0.72s   200  stitchCount=303   w=17.84 h=10.06 stops=1
    04_huge_fill      3.94s   200  stitchCount=4790  w=85.58 h=85.58 stops=1
    05_thin_outlines  2.98s   200  stitchCount=0     empty-but-valid design
    06_many_colors    0.83s   200  stitchCount=1877  w=23.26 h=68.44 stops=3
    07_low_contrast   1.33s   200  stitchCount=5519  w=69.15 h=69.51 stops=2
    08_mixed_scene    0.63s   200  stitchCount=1155  w=72.90 h= 9.97 stops=1
Whole file ~17s: all eight requests are made once by a module-scoped fixture and
shared between tests, so the corpus is digitized exactly eight times.
"""

from __future__ import annotations

import glob
import math
import os
import time
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient

from app.main import app

# raise_server_exceptions=False so an unhandled exception surfaces as a real 500
# response instead of propagating into the test — that is what we assert against.
client = TestClient(app, raise_server_exceptions=False)
DIGITIZE_URL = "/api/digitize"

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "swarm_corpus")
# The generator emits exactly 01_..08_; a short glob means the corpus is missing
# or truncated, which must fail loudly rather than silently skip coverage.
EXPECTED_CORPUS_SIZE = 8

# No pytest-timeout plugin is installed, so hangs are caught with time.monotonic.
# Slowest measured image is 3.94s; 180s leaves ~45x headroom for slow CI boxes.
PER_IMAGE_BUDGET_S = 180.0
# Machine stitch limit in mm — same constant asserted in tests/test_digitizer.py.
MAX_STITCH_MM = 12.7
# Endpoint defaults (apps/backend/app/routers/digitize.py): hoop_size='100x100',
# max_colors=6. The digitizer insets by a margin, so mm dimensions stay under.
DEFAULT_HOOP_MM = 100.0
DEFAULT_MAX_COLORS = 6
# Design JSON keys, camelCase via Design's to_camel alias generator
# (apps/backend/app/models/design.py :: CamelModel).
REQUIRED_DESIGN_KEYS = frozenset(
    {
        "name",
        "widthMm",
        "heightMm",
        "stitchCount",
        "colorStops",
        "objects",
        "stitches",
        "status",
        "version",
    }
)


def _corpus_files() -> list[str]:
    """Sorted corpus paths; raises at import time if the corpus is incomplete."""
    paths = sorted(glob.glob(os.path.join(CORPUS_DIR, "*.png")))
    assert len(paths) == EXPECTED_CORPUS_SIZE, (
        f"expected {EXPECTED_CORPUS_SIZE} corpus PNGs in {CORPUS_DIR}, found "
        f"{len(paths)}: {[os.path.basename(p) for p in paths]}. Regenerate with "
        "`.venv/bin/python tests/fixtures/swarm_corpus/_generate.py` from apps/backend."
    )
    return paths


CORPUS_FILES = _corpus_files()
CORPUS_NAMES = [os.path.basename(p) for p in CORPUS_FILES]


class Result(NamedTuple):
    """One recorded /api/digitize round trip."""

    status: int
    elapsed: float
    body: dict[str, Any] | None  # parsed JSON on 200, else None
    text: str


@pytest.fixture(scope="module")
def corpus_results(tmp_path_factory) -> dict[str, Result]:
    """Digitize every corpus image once; shared by all tests in this module.

    Isolates the user store ITSELF (the conftest contract's escape hatch): a
    module-scoped fixture runs BEFORE the function-scoped autouse isolation,
    so without this it resolves auth against the operator's real
    data/local_users.json — and once any real profile exists, every request
    here is an unauthenticated compute call and 401s (CTO A11 made compute
    endpoints authenticated; the pre-A11 corpus never noticed the ordering).
    """
    from app.services import user_store

    mp = pytest.MonkeyPatch()
    mp.setenv("STITCHIQ_USER_STORE",
              str(tmp_path_factory.mktemp("corpus-users") / "local_users.json"))
    user_store.reset_store_cache()
    try:
        results: dict[str, Result] = {}
        for path in CORPUS_FILES:
            name = os.path.basename(path)
            with open(path, "rb") as fh:
                data = fh.read()
            started = time.monotonic()
            response = client.post(DIGITIZE_URL, files={"file": (name, data, "image/png")})
            elapsed = time.monotonic() - started
            body = response.json() if response.status_code == 200 else None
            results[name] = Result(response.status_code, elapsed, body, response.text)
        return results
    finally:
        mp.undo()
        user_store.reset_store_cache()


def assert_design_shape(name: str, body: dict[str, Any]) -> None:
    """Container types and cross-field consistency of the Design payload."""
    missing = REQUIRED_DESIGN_KEYS - set(body)
    assert not missing, f"{name}: Design payload missing {sorted(missing)}"
    assert isinstance(body["stitches"], list), f"{name}: stitches is not a list"
    assert isinstance(body["colorStops"], list), f"{name}: colorStops is not a list"
    assert isinstance(body["objects"], list), f"{name}: objects is not a list"
    count = body["stitchCount"]
    assert isinstance(count, int) and count >= 0, f"{name}: bad stitchCount {count!r}"
    # stitchCount is derived from the stream, so it can never exceed it.
    assert count <= len(body["stitches"]), f"{name}: stitchCount > len(stitches)"
    assert len(body["colorStops"]) <= DEFAULT_MAX_COLORS, (
        f"{name}: {len(body['colorStops'])} color stops exceeds max_colors default"
    )


def assert_design_geometry(name: str, body: dict[str, Any]) -> None:
    """Either a stitched design that fits the default hoop, or empty-but-valid."""
    width, height = body["widthMm"], body["heightMm"]
    assert math.isfinite(width) and math.isfinite(height), f"{name}: non-finite mm"
    if body["stitchCount"] > 0:
        for axis, value in (("width", width), ("height", height)):
            assert 0 < value <= DEFAULT_HOOP_MM, f"{name}: {axis}Mm={value} off-hoop"
        assert body["stitches"][-1]["command"] == "END", (
            f"{name}: stream ends with {body['stitches'][-1]['command']!r}, not END"
        )
    else:
        # Empty-but-valid: the digitizer found nothing stitchable (05_thin_outlines
        # is 1-2px strokes, which fall below the minimum region area).
        assert body["stitches"] == [], f"{name}: stitchCount 0 but stream non-empty"
        assert body["colorStops"] == [], f"{name}: stitchCount 0 but stops present"
        assert body["objects"] == [], f"{name}: stitchCount 0 but objects present"
        assert width == 0.0 and height == 0.0, f"{name}: stitchCount 0 but {width}x{height}"


def max_stitch_step_mm(stitches: list[dict[str, Any]]) -> float:
    """Longest STITCH-to-STITCH hop, mirroring the walk in tests/test_digitizer.py."""
    worst = 0.0
    previous: dict[str, Any] | None = None
    for stitch in stitches:
        both_stitch = previous is not None and previous["command"] == "STITCH"
        if stitch["command"] == "STITCH" and both_stitch:
            step = math.hypot(stitch["x"] - previous["x"], stitch["y"] - previous["y"])
            worst = max(worst, step)
        previous = stitch
    return worst


def test_corpus_glob_finds_exactly_eight_images():
    """Guards the parametrization itself: a vanished corpus must fail, not skip."""
    assert len(CORPUS_FILES) == EXPECTED_CORPUS_SIZE
    assert CORPUS_NAMES[0] == "01_gradient_blob.png"
    assert CORPUS_NAMES[-1] == "08_mixed_scene.png"
    assert all(os.path.getsize(p) > 0 for p in CORPUS_FILES)


@pytest.mark.parametrize("name", CORPUS_NAMES)
def test_corpus_image_digitizes_to_a_valid_design(name: str, corpus_results):
    """Every corpus image returns 200-with-a-sane-Design or a clean 4xx, in budget."""
    result = corpus_results[name]
    assert result.status < 500, f"{name}: 5xx {result.status} — {result.text[:400]}"
    assert "Traceback" not in result.text, f"{name}: traceback leaked in body"
    assert result.elapsed < PER_IMAGE_BUDGET_S, (
        f"{name}: took {result.elapsed:.1f}s, budget {PER_IMAGE_BUDGET_S}s"
    )
    if result.status != 200:
        pytest.fail(f"{name}: unexpected {result.status} — {result.text[:400]}")
    assert result.body is not None
    assert_design_shape(name, result.body)
    assert_design_geometry(name, result.body)


def test_corpus_stitch_steps_stay_within_machine_limit(corpus_results):
    """No consecutive STITCH pair may exceed the 12.7mm machine maximum."""
    worst_per_image: dict[str, float] = {}
    for name, result in corpus_results.items():
        if result.status != 200 or not result.body:
            continue
        worst_per_image[name] = max_stitch_step_mm(result.body["stitches"])
    assert worst_per_image, "no 200 responses to check — corpus regressed entirely"
    offenders = {n: v for n, v in worst_per_image.items() if v > MAX_STITCH_MM}
    assert not offenders, f"stitch steps over {MAX_STITCH_MM}mm: {offenders}"
    # Measured worst case across the corpus is 8.82mm (07_low_contrast); a jump to
    # near the limit is a real signal even though it is not yet a failure.
    assert max(worst_per_image.values()) > 0.0, "every design was empty"


def test_digitizing_is_deterministic_across_repeat_posts():
    """Identical bytes must yield an identical design — the pipeline has no RNG.

    Verified over three consecutive posts of 01_gradient_blob.png: stitchCount,
    stream length and both mm dimensions were byte-identical every time
    (830 / 833 / 32.13 x 32.14), so this asserts exact equality, not a tolerance.
    """
    path = os.path.join(CORPUS_DIR, "01_gradient_blob.png")
    with open(path, "rb") as fh:
        data = fh.read()
    signatures = []
    for _ in range(2):
        started = time.monotonic()
        response = client.post(
            DIGITIZE_URL, files={"file": ("01_gradient_blob.png", data, "image/png")}
        )
        elapsed = time.monotonic() - started
        assert elapsed < PER_IMAGE_BUDGET_S, f"determinism run took {elapsed:.1f}s"
        assert response.status_code == 200, response.text
        body = response.json()
        signatures.append(
            (body["stitchCount"], len(body["stitches"]), body["widthMm"], body["heightMm"])
        )
    assert signatures[0] == signatures[1], f"non-deterministic digitize: {signatures}"
    assert signatures[0][0] > 0, "determinism fixture must actually produce stitches"
