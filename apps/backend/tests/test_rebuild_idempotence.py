"""Rebuild is idempotent: rebuild(rebuild(d)) == rebuild(d). Exact, no band.

THE BEST INSTRUMENT TO COME OUT OF THREE TRANCHES, and it cost a sentence.

The digitize -> rebuild step is NOT lossless: on A01 it drops 22 penetrations
across 21 of 36 `RUNNING_SINGLE` objects, because the dark-linework emitter
stores `_resample_open`'s SAMPLES as the object contour and rebuild can only
resample the chords between them. Three tranches went into trying to bound that
with a percentage band and then an absolute delta, and both were wrong: a
percentage is vacuous or knife-edge on a five-penetration object, and the loss
is `k - (floor(L/step) + 2)`, unbounded, with the longest object already losing
two.

What IS exact is what happens NEXT. Rebuild regenerates stitches from the stored
contour without rewriting it, so the second generation has nothing left to lose.
Measured across three generations of A01 before this was written:

    gen 0 (digitize)  215 run penetrations   stored path 202.219 mm  stream 5776
    gen 1 (rebuild)   193                    202.219 mm              5540
    gen 2             193                    202.219 mm              5540
    gen 3             193                    202.219 mm              5540

So the loss is a one-time gap and not a ratchet, and THAT is assertable with no
threshold, no band and no fitted constant. It is the product guarantee a
customer actually needs from an editor: opening a design, saving it, and opening
it again must not keep eroding the work.

WHAT THIS DOES NOT COVER, stated so it is not mistaken for more: the
digitize -> gen-1 gap itself. That is representational -- see the cross-refs on
`generation.hairline_runs` and pipeline's dark-linework emitter -- and no
assertion here would catch it.
"""

from __future__ import annotations

import cv2
import pytest
from coverage_audit import fixtures as _audit_fixtures
from run_quality_bench import RNG_SEED

from app.services.digitizer import digitize_image
from app.services.digitizer.rebuild import rebuild_design

#: Two fixtures, chosen for what they exercise rather than for speed:
#: 04 carries an RS1 run object (the emitter that stores the ARC), A01 carries
#: 36 linework run objects (the emitter that stores SAMPLES). If the two
#: conventions ever diverge in their round-trip behaviour, they diverge here.
IDEMPOTENT_FIXTURES = ("04_thin_line_outline", "A01_real_peacock_patch_photo")


def _resolve(name):
    for n, path, params in _audit_fixtures():
        if n == name:
            return path, params
    raise AssertionError(f"{name} is not in the standing set")


@pytest.mark.parametrize("name", IDEMPOTENT_FIXTURES)
def test_a_second_rebuild_changes_nothing(name):
    path, params = _resolve(name)
    if not path.exists():
        pytest.skip(f"{path} is missing; test_corpus_baseline_fixtures asserts presence")
    cv2.setRNGSeed(RNG_SEED)
    design = digitize_image(
        path.read_bytes(), fabric_type=params.get("fabric", "cotton"),
        hoop_size=params["hoop"], max_colors=params["colors"],
        text_mode=params.get("text", False),
    )
    one = rebuild_design(design.model_copy(deep=True), force=True)
    two = rebuild_design(one.model_copy(deep=True), force=True)

    def _stream(d):
        return [(str(getattr(s.command, "value", s.command)), round(s.x, 6), round(s.y, 6))
                for s in d.stitches]

    assert len(two.objects) == len(one.objects), (
        f"{name}: object count moved on the SECOND rebuild "
        f"({len(one.objects)} -> {len(two.objects)}); the round trip is a ratchet"
    )
    for a, b in zip(one.objects, two.objects, strict=True):
        assert (a.sequence_order, a.penetration_count) == (b.sequence_order, b.penetration_count), (
            f"{name}: object {a.sequence_order} lost penetrations on the second "
            f"rebuild ({a.penetration_count} -> {b.penetration_count}) — every "
            f"edit-and-save cycle would erode the design"
        )
    assert _stream(one) == _stream(two), (
        f"{name}: the stream is not fixed under a second rebuild"
    )
