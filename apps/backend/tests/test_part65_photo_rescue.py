"""Photographic rescue: outcome-gated smoothing retry (v2 Part 65).

The real trigger case is a competitor's photographed sew-out (550px angelfish,
kept outside the repo): interior texture 1.86 — under the Part 27 gate of 6.0
— yet 37 of 67 planned regions skipped as sub-thread webs, leaving 22.8% of
the segmentation foreground unsewn. The rescue re-digitizes once with the
mean-shift forced and keeps the result only if it materially recovers artwork
(the fish: 0.228 -> 0.102 uncovered).

What the committed fixtures CAN pin, and these tests do:

1. flat artwork never reaches the retry — its uncovered share sits far below
   the gate, so locked streams are byte-identical by construction;
2. a retry that does not improve is rejected: even with the gate forced open,
   flat art keeps its plain stream because smoothing recovers nothing;
3. the keep path works end-to-end: warning prepended, smoothed stream
   returned — exercised by forcing the gates;
4. the forced-smoothing pass is deterministic under the seed.

The degenerate-input protections (empty designs stay empty, speck-noise
images are not retried) are pinned where those contracts already live:
test_part47_no_empty_success.py and test_part49_drop_log_position.py both
went red against the first version of this rescue and green against the
shipped one — the chunk gate exists because of them.
"""

from __future__ import annotations

import cv2
from helpers import QUALITY_BENCH, stream_of as _stream

from app.services.digitizer import digitize_image, pipeline
from app.services.digitizer.constants import TEXTURE_RETRY_UNCOVERED

FIXTURE = QUALITY_BENCH / "01_flat_2color_logo.png"


def _digitize(**kw):
    cv2.setRNGSeed(1234)
    return digitize_image(FIXTURE.read_bytes(), "cotton", "100x100", 2, **kw)


def test_flat_artwork_sits_far_below_the_retry_gate():
    _digitize()
    assert pipeline._LAST_UNCOVERED_PX < TEXTURE_RETRY_UNCOVERED / 2, (
        "fixture uncovered share crept toward the rescue gate — "
        "re-measure the corpus before trusting the margin"
    )


def test_a_retry_that_does_not_improve_is_rejected(monkeypatch):
    plain = _digitize()
    # Force the trigger: every design now qualifies for a retry. Flat art's
    # smoothed pass recovers nothing, so the improvement gate must reject it
    # and hand back the plain stream untouched.
    monkeypatch.setattr(pipeline, "TEXTURE_RETRY_UNCOVERED", 0.0)
    monkeypatch.setattr(pipeline, "TEXTURE_RETRY_MIN_CHUNK_MM2", -1.0)
    forced = _digitize()
    assert _stream(forced) == _stream(plain)
    assert not any(w.startswith("Photographic texture") for w in forced.warnings)


def test_the_keep_path_prepends_the_warning_and_returns_the_smoothed_stream(monkeypatch):
    smoothed = _digitize(_texture_smooth=True)
    monkeypatch.setattr(pipeline, "TEXTURE_RETRY_UNCOVERED", 0.0)
    monkeypatch.setattr(pipeline, "TEXTURE_RETRY_MIN_CHUNK_MM2", -1.0)
    monkeypatch.setattr(pipeline, "TEXTURE_RETRY_MIN_GAIN", -1.0)  # always "improved"
    kept = _digitize()
    assert kept.warnings and kept.warnings[0].startswith("Photographic texture")
    assert _stream(kept) == _stream(smoothed)


def test_forced_smoothing_is_deterministic():
    assert _stream(_digitize(_texture_smooth=True)) == _stream(_digitize(_texture_smooth=True))
