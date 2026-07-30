"""Fuzz tests: adversarial form params / filenames on POST /api/digitize.

The uploaded PNG is always VALID (dark square on white) so only the parameter
under test is adversarial. Contract under test (app/routers/digitize.py —
READ-ONLY): digitizer._parse_hoop falls back to 100x100 on unparseable hoop
strings; FastAPI coerces max_colors (int Form) and 422s non-numerics; the
router derives design.name via file.filename.rsplit('.', 1)[0]; image type is
sniffed from bytes (cv2.imdecode), so a wrong declared MIME still succeeds.
Never 5xx, never a hang, never a leaked traceback.

Helpers (client, valid_png, post_digitize, response_summary) are duplicated
at module top level per team plan — a later worker consolidates them.
"""

from __future__ import annotations

import math
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

# Generous per-request hang guard; no pytest-timeout plugin is installed.
HANG_BUDGET_S = 60.0

# A 200 Design must report physically sane dimensions: positive, finite, and
# smaller than 10 metres (no hoop is that large).
MAX_SANE_DIMENSION_MM = 10_000.0

# Long-string fuzz sizes: oversized fabric name and oversized filename stem.
LONG_FABRIC_LEN = 10_000
LONG_FILENAME_STEM_LEN = 996  # + '.png' = a 1000-char filename


def valid_png(w: int = 64, h: int = 64) -> bytes:
    """Encode a real PNG via cv2: dark square on white (decodable content)."""
    img = np.full((h, w, 3), 255, np.uint8)
    cv2.rectangle(img, (w // 4, h // 4), (3 * w // 4, 3 * h // 4), (30, 30, 30), thickness=-1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


# Encode once; every test uploads these same known-good bytes.
PNG_BYTES = valid_png()


def post_digitize(name: str, data: bytes, mime: str = "image/png", **form):
    """POST a multipart upload; enforce the hang budget on every request."""
    start = time.monotonic()
    response = client.post(DIGITIZE_URL, files={"file": (name, data, mime)}, data=form)
    assert time.monotonic() - start < HANG_BUDGET_S
    return response


def response_summary(response) -> str:
    """Short failure message: status plus body head (avoid dumping huge bodies)."""
    return f"status={response.status_code} body={response.text[:200]!r}"


def assert_never_5xx(response) -> None:
    """Core invariant: any status below 500, JSON body, no leaked traceback."""
    assert response.status_code < 500, response_summary(response)
    assert "Traceback" not in response.text
    body = response.json()  # must be JSON either way
    if response.status_code != 200:
        assert 400 <= response.status_code < 500, response_summary(response)
        assert "detail" in body


def assert_sane_dimensions(body: dict) -> None:
    """A 200 Design must carry finite, positive, sub-10m widthMm/heightMm."""
    for key in ("widthMm", "heightMm"):
        value = body[key]
        assert isinstance(value, (int, float)), f"{key}={value!r}"
        assert math.isfinite(value), f"{key}={value!r}"
        assert 0 < value < MAX_SANE_DIMENSION_MM, f"{key}={value!r}"


def test_baseline_valid_png_has_camel_case_dimensions():
    # Baseline pins the wire casing (widthMm/heightMm) the fuzz cases rely on.
    r = post_digitize("baseline.png", PNG_BYTES)
    assert r.status_code == 200, response_summary(r)
    assert_sane_dimensions(r.json())


# Known bug (found by this fuzz run): _parse_hoop accepts arbitrarily large
# hoop dimensions with no upper clamp, so '1e9x1e9' and '999999x999999' yield
# a 200 Design claiming widthMm=heightMm=478124.52 (~478 metres wide).
HUGE_HOOP_XFAIL = pytest.mark.xfail(
    strict=False,
    reason="BUG: no upper bound on hoop_size; server returns 200 with "
    "widthMm/heightMm=478124.52 (>10m) for absurd hoop dimensions",
)


# (1) hoop_size fuzzing: _parse_hoop falls back to 100x100 on garbage, so
# most of these should 200 with sane dimensions; a clean 4xx is also fine.
@pytest.mark.parametrize(
    "hoop",
    [
        "0x0",
        "-5x10",
        pytest.param("1e9x1e9", marks=HUGE_HOOP_XFAIL),
        "axb",
        "100x",
        "x100",
        "100×100",  # unicode multiply sign, not ASCII 'x'
        pytest.param("999999x999999", marks=HUGE_HOOP_XFAIL),
        "",
    ],
)
def test_hoop_size_garbage_never_5xx(hoop: str):
    r = post_digitize("hoop.png", PNG_BYTES, hoop_size=hoop)
    assert_never_5xx(r)
    if r.status_code == 200:
        assert_sane_dimensions(r.json())


# (2) max_colors edge values: FastAPI coerces the int; the digitizer must not
# blow up or hang on degenerate palette sizes.
@pytest.mark.parametrize("max_colors", [0, -1, 1, 1000])
def test_max_colors_edge_values_never_5xx(max_colors: int):
    r = post_digitize("colors.png", PNG_BYTES, max_colors=str(max_colors))
    assert_never_5xx(r)


def test_max_colors_non_numeric_is_422():
    r = post_digitize("colors.png", PNG_BYTES, max_colors="six")
    assert r.status_code == 422, response_summary(r)
    assert "detail" in r.json()


# (3) fabric_type is a free string: empty, huge, injection-shaped, and
# whitespace-prefixed values must all be handled without a 5xx.
@pytest.mark.parametrize(
    "fabric",
    ["", "x" * LONG_FABRIC_LEN, "denim; DROP TABLE designs;--", " null"],
    ids=["empty", "10k-chars", "sql-injection", "leading-space-null"],
)
def test_fabric_type_garbage_never_5xx(fabric: str):
    r = post_digitize("fabric.png", PNG_BYTES, fabric_type=fabric)
    assert_never_5xx(r)


# (4) adversarial filenames: name is derived server-side via rsplit('.', 1)[0]
# and must come back as a plain string with no path resolution applied.
@pytest.mark.parametrize(
    "filename",
    [
        "logo",  # no extension: rsplit leaves it unchanged
        "a.png.exe",  # double extension: only the last one is stripped
        "../../etc/passwd.png",  # path traversal must stay inert text
        "日本語デザイン.png",  # multibyte non-ASCII filename ("Japanese design")
        "x" * LONG_FILENAME_STEM_LEN + ".png",  # 1000-char filename
    ],
    ids=["no-ext", "double-ext", "path-traversal", "unicode", "1000-chars"],
)
def test_adversarial_filenames_never_5xx(filename: str):
    r = post_digitize(filename, PNG_BYTES)
    assert_never_5xx(r)
    if r.status_code == 200:
        name = r.json()["name"]
        assert isinstance(name, str)
        # Router rule: design.name = filename.rsplit('.', 1)[0], verbatim.
        assert name == filename.rsplit(".", 1)[0], response_summary(r)


# (5) wrong declared content-type: the server sniffs bytes via cv2.imdecode,
# so valid PNG bytes must digitize regardless of the client's claimed MIME.
@pytest.mark.parametrize("mime", ["application/pdf", "image/jpeg"])
def test_wrong_declared_mime_still_200(mime: str):
    r = post_digitize("mislabelled.png", PNG_BYTES, mime=mime)
    assert r.status_code == 200, response_summary(r)
    assert_sane_dimensions(r.json())
