"""Fuzz tests: malformed-bytes uploads to POST /api/digitize must 4xx cleanly.

Contract under test (app/routers/digitize.py — READ-ONLY):
  empty body -> 400; undecodable image (ValueError) -> 415; other digitize
  failure -> 422; missing multipart field -> FastAPI 422. Never 5xx, never
  a leaked stack trace in the response body.

Shared helpers (client, post_digitize, valid_png) live at module top level
so a later worker can extract them without restructuring.
"""

from __future__ import annotations

import random
import time

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

# raise_server_exceptions=False: a genuine 500 must surface as a status code
# we can assert on, not as an exception that aborts the test.
client = TestClient(app, raise_server_exceptions=False)

DIGITIZE_URL = "/api/digitize"

# Generous hang guard per request; no pytest-timeout plugin is installed.
HANG_BUDGET_S = 30.0

# Size of the random-bytes fuzz payload (~64KB keeps the test fast).
RANDOM_PAYLOAD_BYTES = 64 * 1024

# Fixed seed so the random-bytes case is reproducible across runs.
FUZZ_SEED = 1234

# Truncation points: 40 bytes cuts inside the PNG header/IHDR; keeping 70%
# drops the final chunks (IDAT tail + IEND) of an otherwise valid file.
HEADER_TRUNCATE_BYTES = 40
TAIL_KEEP_FRACTION = 0.7


def valid_png(w: int = 64, h: int = 64) -> bytes:
    """Encode a real PNG via cv2: dark square on white (decodable content)."""
    img = np.full((h, w, 3), 255, np.uint8)
    cv2.rectangle(img, (w // 4, h // 4), (3 * w // 4, 3 * h // 4), (30, 30, 30), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def post_digitize(name: str, data: bytes, mime: str = "image/png", **form):
    """POST a multipart upload; enforce the hang budget on every request."""
    start = time.monotonic()
    response = client.post(DIGITIZE_URL, files={"file": (name, data, mime)}, data=form)
    assert time.monotonic() - start < HANG_BUDGET_S
    return response


def assert_clean_4xx(response, exact: int | None = None) -> None:
    """A rejected upload must be a 4xx with a JSON 'detail' and no traceback."""
    if exact is not None:
        assert response.status_code == exact, response.text
    else:
        assert 400 <= response.status_code < 500, response.text
    assert "detail" in response.json()
    assert "Traceback" not in response.text


def test_empty_file_is_400():
    assert_clean_4xx(post_digitize("empty.png", b""), exact=400)


def test_plain_text_named_png_is_4xx():
    r = post_digitize("foo.png", b"this is definitely not an image, just prose")
    assert_clean_4xx(r)


def test_random_bytes_are_4xx():
    rng = random.Random(FUZZ_SEED)
    payload = rng.randbytes(RANDOM_PAYLOAD_BYTES)
    assert_clean_4xx(post_digitize("noise.png", payload))


def test_truncated_png_header_is_4xx():
    r = post_digitize("truncated.png", valid_png()[:HEADER_TRUNCATE_BYTES])
    assert_clean_4xx(r)


def test_png_missing_tail_never_5xx():
    # cv2 may still decode a PNG missing its tail chunks, so 200 is allowed;
    # anything in the 5xx range is a bug.
    png = valid_png()
    r = post_digitize("chopped.png", png[: int(len(png) * TAIL_KEEP_FRACTION)])
    assert r.status_code < 500, response_summary(r)
    if r.status_code != 200:
        assert_clean_4xx(r)


def test_missing_file_field_is_422():
    start = time.monotonic()
    r = client.post(DIGITIZE_URL, data={"fabric_type": "cotton"})
    assert time.monotonic() - start < HANG_BUDGET_S
    assert_clean_4xx(r, exact=422)


def test_file_field_as_form_string_is_4xx():
    start = time.monotonic()
    r = client.post(DIGITIZE_URL, data={"file": "not-an-upload"})
    assert time.monotonic() - start < HANG_BUDGET_S
    assert_clean_4xx(r)


def response_summary(response) -> str:
    """Short failure message: status plus body head (avoid dumping huge bodies)."""
    return f"status={response.status_code} body={response.text[:200]!r}"
