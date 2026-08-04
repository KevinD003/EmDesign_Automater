"""An empty digitize is a failure, not a success (v2 Part 47, R007).

R007 was specified as "nine corpus designs produce zero stitches — silent
failures, trace the pipeline and fix them". Measured, the premise is wrong in
both halves:

* One of them, `C01_hairline_linework`, is a **blank image**. The generator draws
  in `pal[3]` and `PALETTES[1][3]` is (250, 250, 250) on a (255, 255, 255)
  canvas, so nothing was ever drawn. Zero stitches is the correct answer, and
  the fixture has been counted as a pipeline failure in every audit since.
* The rest are the engine **correctly refusing** features thinner than the
  thread. It logs `sub_thread_feature` at a median region width of 0.23mm
  against a 0.4mm thread, and warns that a larger hoop keeps more detail. That
  advice is true: every one of them sews at a larger hoop.

So there was nothing to fix in the filtering — weakening it would make the
engine sew features narrower than its own thread. What was genuinely broken is
that the API returned **HTTP 200 with an empty Design**, so a correct refusal
arrived looking like a successful digitize.
"""

from __future__ import annotations

import io

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.digitizer import digitize_image

client = TestClient(app)


def _png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _hairlines():
    """1px strokes: unstitchable small, stitchable large. The corpus C-class."""
    img = np.full((520, 520, 3), 255, np.uint8)
    for x in range(20, 500, 9):
        cv2.line(img, (x, 20), (x + 40, 500), (60, 60, 60), 1)
    return img


def _post(art: bytes, hoop: str):
    return client.post(
        "/api/digitize",
        files={"file": ("art.png", io.BytesIO(art), "image/png")},
        data={"fabric_type": "cotton", "hoop_size": hoop, "max_colors": "6"},
    )


def test_an_empty_result_is_a_422_not_a_200():
    """The defect: a correct refusal used to arrive as a successful digitize."""
    cv2.setRNGSeed(20260728)
    r = _post(_png(_hairlines()), "100x100")
    assert r.status_code == 422, (
        f"expected a typed failure, got {r.status_code} with "
        f"{r.json().get('stitchCount', '?')} stitches"
    )


def test_the_failure_says_what_to_do_about_it():
    """A 422 that does not name the hoop is not actionable."""
    cv2.setRNGSeed(20260728)
    detail = _post(_png(_hairlines()), "100x100").json()["detail"]
    assert "100x100" in detail, detail
    assert "hoop" in detail.lower(), detail


def test_the_same_artwork_succeeds_at_a_larger_hoop():
    """The advice in that message has to be true, or it is worse than nothing.

    Measured on the real corpus designs going 130x180 -> 200x300:
    C14 0 -> 36,133 · C28 0 -> 18,250 · C30 0 -> 4,618 · C43 14 -> 4,621.
    """
    cv2.setRNGSeed(20260728)
    r = _post(_png(_hairlines()), "360x350")
    assert r.status_code == 200, r.text
    assert r.json()["stitchCount"] > 0


def test_the_service_still_returns_an_empty_design_rather_than_raising():
    """The guard belongs at the API boundary, not in the engine.

    The corpus runner and the bench call `digitize_image` directly and need to
    record an empty result as data, not catch an exception for it.
    """
    cv2.setRNGSeed(20260728)
    design = digitize_image(_png(_hairlines()), "cotton", "100x100", max_colors=6)
    assert design.stitch_count == 0
    assert design.warnings, "an empty design must at least explain itself"


@pytest.mark.parametrize("share,ok", [(0.0, False), (0.05, True)])
def test_the_corpus_generator_refuses_to_write_a_blank_fixture(share, ok):
    """C01 was blank for the corpus's whole life; the generator now catches it."""
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import build_corpus100 as B

    img = np.full((200, 200, 3), 255, np.uint8)
    if share:
        cv2.rectangle(img, (10, 10), (10 + int(200 * share * 4), 190), (20, 20, 20), -1)
    assert (B._ink_share(img) >= 0.002) is ok
