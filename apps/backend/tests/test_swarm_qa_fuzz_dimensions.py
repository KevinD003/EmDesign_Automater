"""Fuzz tests: degenerate image dimensions/contents to POST /api/digitize.

Contract under test (app/routers/digitize.py — READ-ONLY): empty -> 400,
ValueError -> 415, other digitize failure -> 422. Invariant for every case
here: status is 200 or 4xx, NEVER >=500. A 200 body must be a sane Design
(camelCase wire format per app/models/design.py: 'stitchCount', 'stitches',
stitch 'command'); a 4xx body must carry 'detail' and no leaked traceback.

Helpers are duplicated from test_swarm_qa_fuzz_basic.py on purpose — a later
worker consolidates them into a shared module.
"""

from __future__ import annotations

import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

# raise_server_exceptions=False: a genuine 500 must surface as a status code
# we can assert on, not as an exception that aborts the test.
client = TestClient(app, raise_server_exceptions=False)

DIGITIZE_URL = "/api/digitize"

# Per-request hang guard; no pytest-timeout plugin exists. A normal 200px
# digitize takes ~2s on this machine, so 60s flags a real hang, not slowness.
HANG_BUDGET_S = 60.0

# Strip length for the 1xN / Nx1 degenerate-aspect cases.
STRIP_LEN_PX = 1000

# Side of the large all-white image (background-only at scale).
LARGE_BLANK_SIDE_PX = 800

# Side of the solid single-color image.
SOLID_SIDE_PX = 128

# Side of the fully transparent RGBA image.
TRANSPARENT_SIDE_PX = 64


def encode_png(img: np.ndarray) -> bytes:
    """Encode any ndarray as PNG via cv2; caller must check encodability first."""
    ok, buf = cv2.imencode(".png", img)
    assert ok, f"cv2 refused to encode shape={img.shape} dtype={img.dtype}"
    return buf.tobytes()


def valid_png(w: int = 64, h: int = 64) -> bytes:
    """Encode a real PNG via cv2: dark square on white (decodable content)."""
    img = np.full((h, w, 3), 255, np.uint8)
    cv2.rectangle(img, (w // 4, h // 4), (3 * w // 4, 3 * h // 4), (30, 30, 30), thickness=-1)
    return encode_png(img)


def post_digitize(name: str, data: bytes, mime: str = "image/png", **form):
    """POST a multipart upload; enforce the hang budget on every request."""
    start = time.monotonic()
    response = client.post(DIGITIZE_URL, files={"file": (name, data, mime)}, data=form)
    assert time.monotonic() - start < HANG_BUDGET_S
    return response


def response_summary(response) -> str:
    """Short failure message: status plus body head (avoid dumping huge bodies)."""
    return f"status={response.status_code} body={response.text[:200]!r}"


def assert_never_5xx(response, allowed: tuple[int, ...] | None = None) -> None:
    """Core invariant: 200 with a sane Design body, or a clean 4xx. Never 5xx."""
    assert response.status_code < 500, response_summary(response)
    if allowed is not None:
        assert response.status_code in allowed, response_summary(response)
    body = response.json()
    if response.status_code == 200:
        assert_sane_design(body)
    else:
        assert 400 <= response.status_code < 500, response_summary(response)
        assert "detail" in body
        assert "Traceback" not in response.text


def assert_sane_design(body: dict) -> None:
    """A 200 body must be a Design in camelCase wire form (see design.py)."""
    assert body["stitchCount"] >= 0
    stitches = body["stitches"]
    if stitches:  # any produced stream must terminate with an END command
        assert stitches[-1]["command"] == "END"


def test_normal_png_is_sane_design_baseline():
    # Learns/locks the wire casing (stitchCount/stitches/command) the other
    # assertions rely on: a normal upload must 200 with a sane Design.
    r = post_digitize("normal.png", valid_png(64, 64))
    assert r.status_code == 200, response_summary(r)
    body = r.json()
    assert_sane_design(body)
    assert body["stitchCount"] > 0
    assert body["stitches"][-1]["command"] == "END"


def test_1x1_black_pixel():
    # Known behavior: digitize_image raises ValueError ('not enough values to
    # unpack...') on a 1x1 input, mapped to 415 by the router. 200/422 also
    # acceptable if the pipeline changes; 5xx never is.
    img = np.zeros((1, 1, 3), np.uint8)
    r = post_digitize("1x1.png", encode_png(img))
    assert_never_5xx(r, allowed=(200, 415, 422))


def test_2x2_checkerboard():
    img = np.zeros((2, 2, 3), np.uint8)
    img[0, 1] = img[1, 0] = 255
    assert_never_5xx(post_digitize("2x2.png", encode_png(img)))


def test_1x1000_single_row_strip():
    img = np.full((1, STRIP_LEN_PX, 3), 255, np.uint8)
    img[0, : STRIP_LEN_PX // 2] = 0  # half black so there is foreground
    assert_never_5xx(post_digitize("row.png", encode_png(img)))


def test_1000x1_single_column_strip():
    img = np.full((STRIP_LEN_PX, 1, 3), 255, np.uint8)
    img[: STRIP_LEN_PX // 2, 0] = 0
    assert_never_5xx(post_digitize("col.png", encode_png(img)))


def test_3x3_all_white_background_only():
    img = np.full((3, 3, 3), 255, np.uint8)
    assert_never_5xx(post_digitize("white3.png", encode_png(img)))


def test_800x800_all_white_nothing_to_stitch():
    side = LARGE_BLANK_SIDE_PX
    img = np.full((side, side, 3), 255, np.uint8)
    assert_never_5xx(post_digitize("white800.png", encode_png(img)))


def test_fully_transparent_rgba():
    side = TRANSPARENT_SIDE_PX
    rgba = np.zeros((side, side, 4), np.uint8)  # alpha channel all zero
    assert_never_5xx(post_digitize("transparent.png", encode_png(rgba)))


def test_solid_single_color_128x128():
    img = np.full((SOLID_SIDE_PX, SOLID_SIDE_PX, 3), (200, 40, 40), np.uint8)
    assert_never_5xx(post_digitize("solid.png", encode_png(img)))


def test_16bit_depth_png():
    # 16-bit grayscale gradient; skip if this cv2 build refuses uint16 PNGs.
    img = np.linspace(0, 65535, 64 * 64, dtype=np.uint16).reshape(64, 64)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        pytest.skip("cv2 cannot encode a 16-bit PNG in this build")
    assert_never_5xx(post_digitize("16bit.png", buf.tobytes()))
