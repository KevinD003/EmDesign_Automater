"""Byte-identical stitch-output lock, and the quality bands that guard re-pinning.

Optimization workers must not change stitch output: each fixture's full stitch
stream is hashed and compared against docs/benchmarks/v2-swarm/stitch-hashes.json.
Regenerate the lock ONLY when an output change is intended:
    STITCH_LOCK_WRITE=1 pytest tests/test_swarm_perf_lock.py -q

THE HASH IS NOT A QUALITY CLAIM (CTO verdict STEP 3d). An exact hash catches
ANY change, which is exactly right for a performance optimization that should
be byte-identical. What it cannot do is tell a good change from a bad one — and
that is not a theoretical limit, it is what happened: a travel resampler with a
2-pixel floor manufactured 70.8% of a fixture's stitches, took it to 44.4%
sub-floor penetrations and 21.3 machine-minutes, and every gate in the suite
stayed green because the hash simply moved with the regression and was re-pinned.

So the weak point is not the hash, it is THE MOMENT OF RE-PINNING: one command,
no questions asked. The lock now records the quality metrics beside each hash,
`STITCH_LOCK_WRITE=1` REFUSES to write a stream that violates the bands, and
the committed metrics are re-checked on every run. You can still re-pin a
legitimate change; you cannot re-pin your way past a quality cliff.
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

# Quality bands for THIS lock's configuration, which is not the bench's — the
# colour counts and hoops differ, so the numbers do too.
#
#   fixture                 stitches  sub-0.5mm  sub-0.3mm  max stitch  machine-min
#   -- measured 2026-08-09, before CTO 1b --
#   04_thin_line_outline       1,861       0.0%       0.0%      4.20mm         2.7
#   05_wordmark_caps           1,844       0.4%       0.2%      4.30mm         2.7
#   06_wordmark_script         1,763       6.2%       0.9%      3.20mm         2.6
#   07_circular_badge         35,091      14.6%       1.1%      6.05mm        47.0
#   -- measured 2026-08-10, after CTO 1b (boustrophedon cell decomposition) --
#   04_thin_line_outline       1,874       0.1%       0.0%      4.23mm         2.7
#   05_wordmark_caps           1,878       1.0%       0.2%      4.30mm         2.8
#   06_wordmark_script         1,793       5.1%       1.0%      4.72mm         2.7
#   07_circular_badge         17,291       3.2%       0.3%      6.05mm        22.8
#
# THE BADGE'S BANDS ARE RE-CUT, NOT CARRIED OVER. They were 20% / 4% / 55.0
# against readings of 14.6% / 1.1% / 47.0 — deliberately loose, because at the
# time the badge WAS the corpus's worst fixture and the band was set to catch a
# return of the 2px pixel floor (29.9%) rather than to bless 14.6%. After 1b it
# reads 3.2% / 0.3% / 22.8, and those same bands would now wave through the
# entire pre-1b regression: 47 machine-minutes passes a 55-minute band. A gate
# that cannot fail is not a gate — the same reasoning that made
# STITCH_LOCK_WRITE refuse a violating re-pin in the first place — so the badge
# is re-cut to 8% / 1.5% / 28.0. That still clears the pixel floor's 29.9% by a
# wide margin and still leaves ~23% headroom on machine time, but it will not
# sit quietly through a drift back toward either 34.4 or 47.
#
# 06's sub-floor comes down 12% -> 8% on the same reasoning (5.1% measured).
# 04 and 05 are unchanged: their behaviour did not move and their bands were
# already close to their readings.
#
# (max sub-0.5mm share, max sub-0.3mm share, max machine-minutes)
QUALITY_BANDS: dict[str, tuple[float, float, float]] = {
    "04_thin_line_outline": (0.05, 0.02, 3.5),
    "05_wordmark_caps": (0.05, 0.02, 3.5),
    "06_wordmark_script": (0.08, 0.03, 3.5),
    "07_circular_badge": (0.08, 0.015, 28.0),
}

# A machine stop per trim; the same figure the bench harness uses, so a routing
# change cannot shift cost sideways from stitches to trims and look like a win.
TRIM_SECONDS = 2.5
SPM = 800.0
MACHINE_MAX_STITCH_MM = 12.7


def _digitize(fixture: str, params: dict):
    cv2.setRNGSeed(RNG_SEED)
    return digitize_image(
        (FIXTURE_DIR / f"{fixture}.png").read_bytes(),
        fabric_type="cotton",
        hoop_size=params["hoop"],
        max_colors=params["colors"],
        text_mode=params["text"],
    )


def _hash_of(design) -> str:
    """sha256 over the canonical stream: one 'command|x|y' line per stitch."""
    lines = []
    for s in design.stitches:
        cmd = s.command.value if hasattr(s.command, "value") else str(s.command)
        lines.append(f"{cmd}|{s.x:.4f}|{s.y:.4f}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _quality(design) -> dict:
    """The metrics a re-pin has to satisfy. Sub-floor shares are computed over
    consecutive STITCH pairs only — travel across a JUMP is not a stitch, and
    counting it would fake a machine-limit violation."""
    import math

    from app.services.digitizer import MIN_STITCH_MM
    from app.services.digitizer.constants import MIN_PENETRATION_MM

    lengths, prev = [], None
    for s in design.stitches:
        cmd = s.command.value if hasattr(s.command, "value") else str(s.command)
        if cmd == "STITCH":
            if prev is not None:
                lengths.append(math.dist(prev, (s.x, s.y)))
            prev = (s.x, s.y)
        else:
            prev = None if cmd == "TRIM" else (s.x, s.y)
    trims = sum(1 for s in design.stitches
                if (s.command.value if hasattr(s.command, "value") else str(s.command)) == "TRIM")
    n = len(lengths) or 1
    return {
        "stitches": len(design.stitches),
        "trims": trims,
        "sub_floor_share": round(sum(1 for x in lengths if x < MIN_STITCH_MM) / n, 4),
        "sub_penetration_share": round(
            sum(1 for x in lengths if x < MIN_PENETRATION_MM) / n, 4),
        "max_stitch_mm": round(max(lengths), 2) if lengths else 0.0,
        "machine_minutes": round(len(design.stitches) / SPM + trims * TRIM_SECONDS / 60.0, 2),
    }


def _check_bands(fixture: str, q: dict) -> list[str]:
    """Every band violation, as human sentences. Empty list means acceptable."""
    max_floor, max_pen, max_min = QUALITY_BANDS[fixture]
    bad = []
    if q["sub_floor_share"] > max_floor:
        bad.append(f"{q['sub_floor_share']:.1%} of stitches under MIN_STITCH_MM "
                   f"(band {max_floor:.0%}) — is resample_inside back to a pixel floor?")
    if q["sub_penetration_share"] > max_pen:
        bad.append(f"{q['sub_penetration_share']:.1%} under MIN_PENETRATION_MM "
                   f"(band {max_pen:.0%}) — the needle is re-entering its own hole")
    if q["machine_minutes"] > max_min:
        bad.append(f"{q['machine_minutes']:.1f} machine-minutes "
                   f"({q['stitches']:,} stitches + {q['trims']} trims), band {max_min}")
    if q["max_stitch_mm"] > MACHINE_MAX_STITCH_MM:
        bad.append(f"a {q['max_stitch_mm']:.1f}mm stitch exceeds the "
                   f"{MACHINE_MAX_STITCH_MM}mm machine limit")
    return bad


@pytest.mark.parametrize("fixture", sorted(LOCK_FIXTURES))
def test_stitch_stream_locked(fixture: str) -> None:
    design = _digitize(fixture, LOCK_FIXTURES[fixture])
    actual = _hash_of(design)
    quality = _quality(design)

    if os.environ.get("STITCH_LOCK_WRITE") == "1":
        # THE RE-PIN GATE. Re-pinning used to be one command with no questions
        # asked, which is how a 1.95x stitch inflation with 44.4% sub-floor
        # penetrations got locked in as the new baseline. A stream that violates
        # the bands cannot be written, so the only way past this is to widen a
        # band deliberately — a visible line in a diff, not a silent overwrite.
        violations = _check_bands(fixture, quality)
        assert not violations, (
            f"REFUSING to re-pin {fixture}: the new stream fails its quality "
            f"bands.\n  - " + "\n  - ".join(violations) +
            f"\nFix the output, or widen the band in QUALITY_BANDS with the "
            f"measurement and the reason."
        )
        stored = json.loads(HASH_FILE.read_text()) if HASH_FILE.exists() else {}
        stored[fixture] = {"hash": actual, **quality}
        HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
        HASH_FILE.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n")
        return

    expected = json.loads(HASH_FILE.read_text())[fixture]
    # Tolerate the pre-STEP-3d shape (a bare hash string) so an old checkout
    # still gates on the hash rather than erroring.
    locked_hash = expected["hash"] if isinstance(expected, dict) else expected
    assert actual == locked_hash, (
        f"{fixture}: stitch stream changed (got {actual}, locked {locked_hash}). "
        "Optimizations must be byte-identical; regenerate only if the change is "
        "intended — and the re-pin will be checked against the quality bands."
    )


@pytest.mark.parametrize("fixture", sorted(LOCK_FIXTURES))
def test_the_locked_stream_is_within_its_quality_bands(fixture: str) -> None:
    """Check the COMMITTED numbers, every run, not only at the moment of
    re-pinning. Otherwise a band tightened after a re-pin would never be applied
    to the stream already in the lock."""
    stored = json.loads(HASH_FILE.read_text())[fixture]
    if not isinstance(stored, dict):
        pytest.skip("lock predates STEP 3d and carries no metrics; re-pin to add them")
    violations = _check_bands(fixture, stored)
    assert not violations, (
        f"{fixture}: the LOCKED stream violates its own quality bands.\n  - "
        + "\n  - ".join(violations)
    )


@pytest.mark.parametrize("fixture", sorted(LOCK_FIXTURES))
def test_the_lock_records_what_it_locked(fixture: str) -> None:
    """A hash alone says a stream changed; it never says whether the change was
    good. The lock carries the measurements beside it so a re-pin is auditable
    in the diff — you can see the machine time move."""
    stored = json.loads(HASH_FILE.read_text())[fixture]
    assert isinstance(stored, dict), "lock entry is a bare hash with no metrics"
    for key in ("hash", "stitches", "trims", "sub_floor_share",
                "sub_penetration_share", "max_stitch_mm", "machine_minutes"):
        assert key in stored, f"{fixture}: lock is missing {key}"


def test_the_bands_would_reject_the_regression_that_started_this():
    """Negative control. The STEP -1 defect on 01_flat_2color_logo measured
    44.4% sub-floor and 21.3 machine-minutes against ~8. Feed those numbers to
    the checker under the tightest fixture's bands and it must object, or the
    bands are decoration."""
    bad = _check_bands("04_thin_line_outline", {
        "stitches": 17078, "trims": 47,
        "sub_floor_share": 0.444, "sub_penetration_share": 0.368,
        "max_stitch_mm": 4.0, "machine_minutes": 21.3,
    })
    assert len(bad) >= 3, f"the bands barely noticed the regression: {bad}"


def test_every_locked_fixture_has_a_band():
    assert set(QUALITY_BANDS) == set(LOCK_FIXTURES), (
        "a fixture is locked without a quality band, so its re-pin is unguarded"
    )
