"""Upload validation hardening for POST /api/files/parse."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routers.files import MAX_EMBROIDERY_FILE_BYTES

client = TestClient(app)

FIXTURES = Path(__file__).parent / "fixtures"

# Multipart content type sent by browsers for an unknown binary upload; the
# endpoint must key off the filename extension, never this header.
BINARY_CONTENT_TYPE = "application/octet-stream"

# One byte past the endpoint ceiling — the smallest body that must be refused.
OVERSIZE_BYTES = MAX_EMBROIDERY_FILE_BYTES + 1


def _post(filename: str, data: bytes):
    return client.post(
        "/api/files/parse",
        files={"file": (filename, data, BINARY_CONTENT_TYPE)},
    )


def _dst_bytes() -> bytes:
    return (FIXTURES / "sample.dst").read_bytes()


def test_valid_dst_parses() -> None:
    resp = _post("sample.dst", _dst_bytes())
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "sample.dst"
    assert body["stitchCount"] > 0


def test_valid_pes_parses() -> None:
    resp = _post("sample.pes", (FIXTURES / "sample.pes").read_bytes())
    assert resp.status_code == 200
    assert resp.json()["name"] == "sample.pes"


def test_traversal_filename_is_stripped_to_a_bare_basename() -> None:
    resp = _post("evil/../../etc/passwd.dst", _dst_bytes())
    assert resp.status_code == 200
    name = resp.json()["name"]
    assert "/" not in name
    assert ".." not in name
    assert name == "passwd.dst"


def test_windows_traversal_filename_is_stripped() -> None:
    resp = _post(r"..\\..\\windows\\system32\\evil.dst", _dst_bytes())
    assert resp.status_code == 200
    name = resp.json()["name"]
    assert "\\" not in name and "/" not in name
    assert name == "evil.dst"


def test_uppercase_extension_is_accepted() -> None:
    resp = _post("SAMPLE.DST", _dst_bytes())
    assert resp.status_code == 200
    assert resp.json()["name"] == "SAMPLE.DST"


def test_missing_extension_is_415() -> None:
    resp = _post("noextension", _dst_bytes())
    assert resp.status_code == 415
    detail = resp.json()["detail"]
    assert "dst" in detail and "pes" in detail


def test_unsupported_extension_is_415() -> None:
    resp = _post("malware.exe", b"MZ\x90\x00" * 64)
    assert resp.status_code == 415
    assert "exe" in resp.json()["detail"]


def test_empty_body_is_400() -> None:
    resp = _post("empty.dst", b"")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Empty file"


def test_oversized_upload_is_413() -> None:
    resp = _post("big.dst", b"\x00" * OVERSIZE_BYTES)
    assert resp.status_code == 413
    assert "10 MB" in resp.json()["detail"]


def test_garbage_pes_is_4xx_not_500() -> None:
    resp = _post("x.pes", b"this is not an embroidery file" * 8)
    assert resp.status_code in (415, 422)
    assert resp.status_code != 500


def test_parser_error_detail_is_truncated() -> None:
    from app.routers.files import MAX_ERROR_DETAIL_CHARS, _clip

    assert len(_clip("x" * 5_000)) == MAX_ERROR_DETAIL_CHARS
    assert _clip("short") == "short"
