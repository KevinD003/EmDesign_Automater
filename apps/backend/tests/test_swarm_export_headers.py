"""Content-Disposition hardening for /api/export and /api/export/package.

design.name is arbitrary user input: quotes, slashes, CR/LF, or path traversal in it
must never reach the download header. The router also normalizes the ``format`` query
param ('DST', '.dst') at the edge so casing/leading-dot never matters downstream.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import Design, Stitch

client = TestClient(app)

# Extracts the quoted filename value out of 'attachment; filename="..."'.
_FILENAME_RE = re.compile(r'filename="([^"]*)"')


def _design(name: str) -> Design:
    return Design(
        name=name,
        width_mm=10.0,
        height_mm=0.0,
        stitch_count=2,
        stitches=[Stitch(x=0, y=0, command="STITCH"), Stitch(x=10, y=0, command="STITCH")],
    )


def _export(name: str, fmt: str = "dst", endpoint: str = "/api/export"):
    return client.post(endpoint, params={"format": fmt}, json=_design(name).model_dump(by_alias=True))


def _disposition(resp) -> str:
    return resp.headers["content-disposition"]


def test_messy_name_is_sanitized_to_safe_filename():
    resp = _export('my logo (v2)/..\\evil"name.png')
    assert resp.status_code == 200
    cd = _disposition(resp)
    match = _FILENAME_RE.search(cd)
    assert match, f"no quoted filename in {cd!r}"
    filename = match.group(1)
    assert re.fullmatch(r"[\w\-]+\.dst", filename), filename
    # Beyond the two delimiting quotes there must be no quote, path separator, or CR/LF.
    assert cd.count('"') == 2
    for forbidden in ("/", "\\", "\r", "\n"):
        assert forbidden not in cd


def test_crlf_in_name_cannot_inject_headers():
    resp = _export("a\r\nSet-Cookie: x")
    assert resp.status_code == 200
    cd = _disposition(resp)
    assert "\r" not in cd and "\n" not in cd  # single line, nothing smuggled past it
    assert "Set-Cookie:" not in cd  # the colon is stripped, so no header-shaped text
    assert "set-cookie" not in resp.headers


@pytest.mark.parametrize("fmt", ["DST", ".dst"])
def test_format_param_is_case_and_dot_insensitive(fmt: str):
    resp = _export("two-stitch", fmt=fmt)
    assert resp.status_code == 200
    assert resp.content
    filename = _FILENAME_RE.search(_disposition(resp)).group(1)
    assert filename.endswith(".dst"), filename


def test_package_uses_sanitized_stem_and_zip_content_type():
    resp = _export('bad name!/..\\"x.png', endpoint="/api/export/package")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    filename = _FILENAME_RE.search(_disposition(resp)).group(1)
    assert re.fullmatch(r"[\w\-]+-package\.zip", filename), filename


def test_blank_name_falls_back_to_design_stem():
    # Pydantic requires a name, so a single space is the closest to "empty".
    resp = _export(" ")
    assert resp.status_code == 200
    filename = _FILENAME_RE.search(_disposition(resp)).group(1)
    assert filename == "design.dst"
