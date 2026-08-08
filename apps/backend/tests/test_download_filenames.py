"""CTO A15/N4: non-Latin design names must download, not 500.

Starlette encodes headers as Latin-1; the three download endpoints put the
design name into Content-Disposition, so a name like ロゴ (set automatically
from the uploaded filename) raised UnicodeEncodeError before the response
streamed — a user in Japan could not export at all. All three now emit an
RFC 5987 header: ASCII fallback in `filename`, the real UTF-8 name
percent-encoded in `filename*`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.package import content_disposition

client = TestClient(app)


def _design(name: str) -> dict:
    return {
        "name": name, "widthMm": 10, "heightMm": 10, "stitchCount": 3, "version": 1,
        "status": "digitized", "hoopSize": "100x100",
        "colorStops": [{"stopNumber": 1, "threadBrand": "M", "catalogNumber": "1",
                        "threadName": "a", "hex": "#112233", "stitchCount": 3}],
        "objects": [],
        "stitches": [{"x": 0, "y": 0, "command": "STITCH"},
                     {"x": 5, "y": 0, "command": "STITCH"},
                     {"x": 5, "y": 5, "command": "STITCH"},
                     {"x": 5, "y": 5, "command": "END"}],
    }


@pytest.mark.parametrize("name", ["ロゴ", "logo😀", "über-Ärmel", "plain"])
@pytest.mark.parametrize("path", ["/api/export?format=dst", "/api/export/package?format=dst",
                                  "/api/worksheet/pdf"])
def test_downloads_survive_any_name(path, name):
    r = client.post(path, json=_design(name))
    assert r.status_code == 200, f"{path} with {name!r}: {r.status_code} {r.text[:200]}"
    cd = r.headers["content-disposition"]
    assert cd.isascii(), f"header not Latin-1 safe: {cd}"
    assert "filename*=UTF-8''" in cd


def test_helper_preserves_the_real_name_and_ascii_fallback():
    h = content_disposition("ロゴ.dst")
    assert h == "attachment; filename=\"design.dst\"; filename*=UTF-8''%E3%83%AD%E3%82%B4.dst"
    h2 = content_disposition("plain.dst")
    assert 'filename="plain.dst"' in h2
