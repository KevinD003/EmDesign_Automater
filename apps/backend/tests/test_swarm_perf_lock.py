"""Byte-identical stitch-output lock for the digitizer performance swarm.

Optimization workers must not change stitch output: each fixture's full stitch
stream is hashed and compared against docs/benchmarks/v2-swarm/stitch-hashes.json.
Regenerate the lock ONLY when an output change is intended:
    STITCH_LOCK_WRITE=1 pytest tests/test_swarm_perf_lock.py -q
"""

import hashlib
import json
import os
from pathlib import Path

import cv2
import pytest

from app.services.digitizer import digitize_image

# The hashes were captured on the WITH-rembg path; the two segmentation paths
# produce different (both healthy) streams by design — documented since Part 12
# — so the lock is only meaningful where its baseline was taken.
pytestmark = pytest.mark.skipif(
    os.environ.get("STITCHIQ_DISABLE_REMBG") == "1",
    reason="stream lock baselines are WITH-rembg; the no-rembg path differs by design",
)

# Anchors: parents[1] = apps/backend, parents[3] = repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = BACKEND_ROOT / "tests" / "fixtures" / "quality_bench"
HASH_FILE = REPO_ROOT / "docs" / "benchmarks" / "v2-swarm" / "stitch-hashes.json"

# Same seed as scripts/run_quality_bench.py: pins k-means init so runs compare.
RNG_SEED = 20260728

# Params copied verbatim from FIXTURE_PARAMS in scripts/run_quality_bench.py —
# the hash is only meaningful if it locks the exact bench configuration.
LOCK_FIXTURES: dict[str, dict] = {
    "04_thin_line_outline": {"colors": 2, "hoop": "100x100", "text": False},
    "05_wordmark_caps": {"colors": 2, "hoop": "130x180", "text": True},
    "06_wordmark_script": {"colors": 2, "hoop": "130x180", "text": True},
    "07_circular_badge": {"colors": 4, "hoop": "130x180", "text": False},
}


def _stitch_hash(fixture: str, params: dict) -> str:
    """sha256 over the canonical stream: one 'command|x|y' line per stitch."""
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        (FIXTURE_DIR / f"{fixture}.png").read_bytes(),
        fabric_type="cotton",
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params["text"],
    )
    lines = []
    for s in design.stitches:
        cmd = s.command.value if hasattr(s.command, "value") else str(s.command)
        lines.append(f"{cmd}|{s.x:.4f}|{s.y:.4f}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


@pytest.mark.parametrize("fixture", sorted(LOCK_FIXTURES))
def test_stitch_stream_locked(fixture: str) -> None:
    actual = _stitch_hash(fixture, LOCK_FIXTURES[fixture])
    if os.environ.get("STITCH_LOCK_WRITE") == "1":
        stored = json.loads(HASH_FILE.read_text()) if HASH_FILE.exists() else {}
        stored[fixture] = actual
        HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
        HASH_FILE.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n")
        return
    expected = json.loads(HASH_FILE.read_text())
    assert actual == expected[fixture], (
        f"{fixture}: stitch stream changed (got {actual}, locked {expected[fixture]}). "
        "Optimizations must be byte-identical; regenerate only if the change is intended."
    )
