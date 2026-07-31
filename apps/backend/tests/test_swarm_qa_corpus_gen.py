"""Guards the synthetic breadth corpus in tests/fixtures/swarm_corpus/.

Three properties are asserted, in order of what they protect:
  1. the generator emits exactly the eight documented PNGs and each one decodes,
  2. generation is deterministic (same bytes on every run, on any machine),
  3. the committed PNGs are byte-identical to a fresh generation — i.e. nobody
     edited a fixture by hand or changed a builder without regenerating.

The generator lives outside any package (it sits in a fixtures directory), so it
is loaded by path via importlib rather than imported.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from types import ModuleType

import cv2
import numpy as np
import pytest

CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "swarm_corpus")
GENERATOR_PATH = os.path.join(CORPUS_DIR, "_generate.py")

# Contract from the corpus spec: every image side must sit inside this band.
MIN_SIDE_PX = 400
MAX_SIDE_PX = 800

EXPECTED_NAMES = (
    "01_gradient_blob.png",
    "02_photo_like.png",
    "03_tiny_text.png",
    "04_huge_fill.png",
    "05_thin_outlines.png",
    "06_many_colors.png",
    "07_low_contrast.png",
    "08_mixed_scene.png",
)


def _load_generator() -> ModuleType:
    """Import _generate.py by path — it is not part of an importable package."""
    spec = importlib.util.spec_from_file_location("swarm_corpus_generate", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    return _load_generator()


def _sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _decode(path: str) -> np.ndarray:
    """Decode through cv2.imdecode (the same path the digitize endpoint uses)."""
    with open(path, "rb") as handle:
        raw = np.frombuffer(handle.read(), np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    assert img is not None, f"cv2.imdecode returned None for {path}"
    return img


def test_generator_emits_all_eight_images(generator, tmp_path):
    written = generator.generate(tmp_path)
    assert len(written) == len(EXPECTED_NAMES)
    names = sorted(os.path.basename(p) for p in written)
    assert names == sorted(EXPECTED_NAMES)
    for name in EXPECTED_NAMES:
        assert os.path.getsize(os.path.join(tmp_path, name)) > 0, name


def test_generated_images_decode_at_documented_sizes(generator, tmp_path):
    generator.generate(tmp_path)
    for name in EXPECTED_NAMES:
        img = _decode(os.path.join(tmp_path, name))
        height, width = img.shape[:2]
        assert (height, width) == generator.EXPECTED_SIZES[name], name
        assert MIN_SIDE_PX <= height <= MAX_SIDE_PX, f"{name} height {height}"
        assert MIN_SIDE_PX <= width <= MAX_SIDE_PX, f"{name} width {width}"
        assert img.shape[2] == 3, name


def test_generation_is_deterministic(generator, tmp_path):
    first, second = tmp_path / "run_a", tmp_path / "run_b"
    generator.generate(first)
    generator.generate(second)
    for name in EXPECTED_NAMES:
        assert _sha256(str(first / name)) == _sha256(str(second / name)), f"{name} is not stable"


def test_committed_corpus_matches_fresh_generation(generator, tmp_path):
    generator.generate(tmp_path)
    committed = sorted(p for p in os.listdir(CORPUS_DIR) if p.endswith(".png"))
    assert committed == sorted(EXPECTED_NAMES), "committed corpus has extra/missing PNGs"
    for name in EXPECTED_NAMES:
        expected = _sha256(str(tmp_path / name))
        actual = _sha256(os.path.join(CORPUS_DIR, name))
        assert actual == expected, (
            f"{name} is stale — rerun "
            f"'.venv/bin/python tests/fixtures/swarm_corpus/_generate.py' from apps/backend"
        )


def test_corpus_covers_its_stress_axes(generator, tmp_path):
    """Cheap content checks so a builder cannot silently degrade to a blank frame."""
    generator.generate(tmp_path)
    palette = {
        name: len(np.unique(_decode(str(tmp_path / name)).reshape(-1, 3), axis=0))
        for name in EXPECTED_NAMES
    }
    # 06 is the palette-overflow case: exactly 16 swatches, above the default max_colors=6.
    assert palette["06_many_colors.png"] == 16
    # 02 is continuous tone: thousands of distinct colors after blur.
    assert palette["02_photo_like.png"] > 1000
    # 04 must be one solid region over >80% of the frame.
    huge = _decode(str(tmp_path / "04_huge_fill.png"))
    dominant = np.bincount(huge.reshape(-1, 3)[:, 0]).max() / float(huge.shape[0] * huge.shape[1])
    assert dominant > 0.80, f"04 fill fraction {dominant:.3f}"
    # 07 must stay low contrast: total spread across all channels under 30 levels.
    low = _decode(str(tmp_path / "07_low_contrast.png"))
    assert int(low.max()) - int(low.min()) < 30
