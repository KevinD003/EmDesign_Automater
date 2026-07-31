"""Fuzz tests: oversized and decompression-heavy uploads to POST /api/digitize.

Contract under test (app/routers/digitize.py + app/services/digitizer.py, both
READ-ONLY): a large or expensive-to-decode image must end in a 200 or a clean
4xx inside a bounded wall clock — never a 5xx, never a leaked traceback, never
an unbounded hang. digitizer caps its working resolution at _MAX_WORK_PX=1200
via cv2.resize, so a huge source is downscaled *after* a full decode; the decode
and the pre-resize allocation are the actual risk this file exercises.

Measured on this machine (see per-test comments for the numbers): the whole
file runs in ~60s, dominated by the two noise cases.

Helpers are duplicated locally in the style of test_swarm_qa_fuzz_basic.py;
consolidation across the fuzz files happens in a later pass.
"""

from __future__ import annotations

import os
import struct
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

# Wall-clock ceiling for a single oversized-but-decodable upload. Generous
# (measured worst case here is ~16s) because there is no pytest-timeout plugin:
# this constant is the only thing standing between a hang and a stuck CI job.
TIME_BUDGET_S = 120.0

# Ceiling for the palette-clustering worst case (random noise), where k-means
# has no structure to converge on. Measured 16s; the headroom absorbs a slow
# or contended machine without turning a perf regression into a flake.
NOISE_BUDGET_S = 300.0

# Ceiling for inputs cv2 rejects before any real work (malformed header,
# degenerate resize). Measured ~0.02s.
REJECT_BUDGET_S = 30.0

# Decompression-bomb side length: 4000x4000x3 is ~48MB decoded from a ~57KB
# PNG (~840:1). Above digitizer's 1200px work cap, so it also exercises the
# downscale path.
BOMB_SIDE_PX = 4000

# Extreme-aspect sizes: 6000px on one axis with a 2px minor axis. After the
# 1200px cap the minor axis rounds to 0, which is the interesting edge.
ASPECT_LONG_PX = 6000
ASPECT_SHORT_PX = 2

# Palette-stress size: random noise at 1500px, just over the 1200px work cap.
NOISE_SIDE_PX = 1500

# Body-size stress: seeded noise at 1800px encodes to ~9.7MB of PNG, just under
# the 10MB target and well under BodySizeLimitMiddleware's 25MB limit, so the
# request reaches the router instead of being refused at the edge.
BIG_BODY_SIDE_PX = 1800
BIG_BODY_MIN_BYTES = 5 * 1024 * 1024

# Fixed seeds so every payload in this file is byte-reproducible.
NOISE_SEED = 42
BIG_BODY_SEED = 7

# Absurd dimensions for the crafted BMP header: 2**30 px per side would be
# ~3.5 exabytes decoded. cv2 must refuse it on the header, not try to allocate.
BMP_CLAIMED_SIDE_PX = 2**30

# BMP layout constants (little-endian): 14-byte file header + 40-byte
# BITMAPINFOHEADER, pixel data starting at offset 54, 24bpp, 1 plane.
_BMP_PIXEL_OFFSET = 54
_BMP_INFO_HEADER_SIZE = 40
_BMP_PLANES = 1
_BMP_BITS_PER_PIXEL = 24
_BMP_TRUNCATED_BODY_BYTES = 100

# Opt-out for the two multi-second cases when a fast smoke run is wanted.
SWARM_FAST = os.environ.get("SWARM_FAST") == "1"
slow_case = pytest.mark.skipif(SWARM_FAST, reason="SWARM_FAST=1 skips multi-second fuzz cases")


def encode_png(img: np.ndarray) -> bytes:
    """Encode an array as a real PNG; fail loudly if cv2 cannot."""
    ok, buf = cv2.imencode(".png", img)
    assert ok, f"cv2.imencode failed for shape {img.shape}"
    return buf.tobytes()


def noise_png(side: int, seed: int) -> bytes:
    """Seeded uniform RGB noise — incompressible and worst case for k-means."""
    rng = np.random.default_rng(seed)
    return encode_png(rng.integers(0, 256, (side, side, 3), dtype=np.uint8))


def post_digitize(name: str, data: bytes, mime: str = "image/png", budget: float = TIME_BUDGET_S):
    """POST a multipart upload; enforce a named wall-clock budget on the request."""
    start = time.monotonic()
    response = client.post(DIGITIZE_URL, files={"file": (name, data, mime)})
    elapsed = time.monotonic() - start
    assert elapsed < budget, f"{name} took {elapsed:.1f}s (budget {budget}s) — hang or perf regression"
    return response


def response_summary(response) -> str:
    """Short failure message: status plus body head (never dump a huge body)."""
    return f"status={response.status_code} body={response.text[:200]!r}"


def assert_200_or_clean_4xx(response) -> None:
    """Shared invariant: no 5xx, parseable JSON, no traceback, 4xx carries detail."""
    assert response.status_code < 500, response_summary(response)
    assert "Traceback" not in response.text
    body = response.json()
    if response.status_code != 200:
        assert 400 <= response.status_code < 500, response_summary(response)
        assert "detail" in body, response_summary(response)


def truncated_bmp_bomb() -> bytes:
    """BMP header claiming 2**30 px per side, with a stub body (no pixel data)."""
    file_header = b"BM" + struct.pack("<IHHI", 10**9, 0, 0, _BMP_PIXEL_OFFSET)
    info_header = struct.pack(
        "<IiiHHIIiiII",
        _BMP_INFO_HEADER_SIZE,
        BMP_CLAIMED_SIDE_PX,
        BMP_CLAIMED_SIDE_PX,
        _BMP_PLANES,
        _BMP_BITS_PER_PIXEL,
        0, 0, 2835, 2835, 0, 0,
    )
    return file_header + info_header + b"\x00" * _BMP_TRUNCATED_BODY_BYTES


@slow_case
def test_solid_white_decompression_bomb_never_5xx():
    # (a) 4000x4000 solid white: ~57KB on the wire, ~48MB decoded.
    # Measured: 200 in ~7.0s, empty design (stitchCount=0, widthMm=0.0).
    payload = encode_png(np.full((BOMB_SIDE_PX, BOMB_SIDE_PX, 3), 255, np.uint8))
    response = post_digitize("bomb_white_4000.png", payload)
    assert_200_or_clean_4xx(response)


@slow_case
def test_large_image_with_content_returns_design():
    # (a') Same 4000x4000 frame but with a dark square, so the downscale path
    # produces real stitches rather than an empty design.
    # Measured: 200 in ~4.8s, stitchCount=1877, widthMm=heightMm=45.9.
    img = np.full((BOMB_SIDE_PX, BOMB_SIDE_PX, 3), 255, np.uint8)
    quarter = BOMB_SIDE_PX // 4
    cv2.rectangle(img, (quarter, quarter), (3 * quarter, 3 * quarter), (30, 30, 30), thickness=-1)
    response = post_digitize("bomb_content_4000.png", encode_png(img))
    assert_200_or_clean_4xx(response)
    if response.status_code == 200:
        body = response.json()
        assert isinstance(body["stitches"], list)
        assert body["stitchCount"] <= len(body["stitches"])


@pytest.mark.parametrize(
    ("width", "height"),
    [(ASPECT_LONG_PX, ASPECT_SHORT_PX), (ASPECT_SHORT_PX, ASPECT_LONG_PX)],
    ids=["6000x2", "2x6000"],
)
def test_extreme_aspect_ratio_never_5xx(width: int, height: int):
    # (b) After the 1200px work cap the 2px axis scales to 0, which cv2.resize
    # rejects. Measured: 422 in ~0.02s, detail "Digitizing failed: OpenCV(...)
    # (-215:Assertion failed) inv_scale_x > 0 in function 'resize'".
    # A clean 4xx is the contract; a 5xx or a hang would be the bug.
    img = np.full((height, width, 3), 255, np.uint8)
    img[: max(1, height // 2), : max(1, width // 2)] = 20
    response = post_digitize(f"aspect_{width}x{height}.png", encode_png(img), budget=REJECT_BUDGET_S)
    assert_200_or_clean_4xx(response)


@slow_case
def test_random_noise_palette_stress_never_5xx():
    # (c) 1500x1500 seeded noise: ~6.8MB on the wire, no structure for k-means.
    # Measured: 200 in ~16.1s (encode ~3s more), empty design.
    response = post_digitize("noise_1500.png", noise_png(NOISE_SIDE_PX, NOISE_SEED),
                             budget=NOISE_BUDGET_S)
    assert_200_or_clean_4xx(response)


@slow_case
def test_ten_megabyte_body_never_5xx():
    # (d) ~9.7MB multipart body — under BodySizeLimitMiddleware's 25MB cap, so
    # a 413 here would itself be a (clean) 4xx. Measured: 200 in ~14.8s.
    payload = noise_png(BIG_BODY_SIDE_PX, BIG_BODY_SEED)
    assert len(payload) > BIG_BODY_MIN_BYTES, f"payload only {len(payload)} bytes"
    response = post_digitize("big_body.png", payload, budget=NOISE_BUDGET_S)
    assert_200_or_clean_4xx(response)


def test_bmp_header_claiming_absurd_dimensions_is_4xx():
    # (e) cv2 refuses on CV_IO_MAX_IMAGE_WIDTH/PIXELS before allocating, and
    # raises cv2.error rather than returning None — so the router's generic
    # handler answers 422, not the 415 that a None decode would give.
    # Measured: 422 in ~0.02s. Either code is acceptable; OOM/500 is not.
    response = post_digitize("bomb.bmp", truncated_bmp_bomb(), "image/bmp",
                             budget=REJECT_BUDGET_S)
    assert_200_or_clean_4xx(response)
    assert response.status_code in (415, 422), response_summary(response)
