"""Tests for POST /api/convert (spec §4.8) — Phase 5."""

from __future__ import annotations

import base64
import os

from fastapi.testclient import TestClient

from app.main import app
from app.services import embroidery_io

client = TestClient(app)
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _b64(name: str) -> str:
    with open(os.path.join(FIXTURES, name), "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def test_convert_dst_to_pes_roundtrips():
    r = client.post(
        "/api/convert",
        json={"inputFileBase64": _b64("sample.dst"), "fromFormat": "dst", "toFormat": "pes"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stitchCount"] > 0
    assert body["colors"] == 2
    # DST source carries no colors → warning present
    assert any("color" in w.lower() for w in body["warnings"])
    # output decodes as a real PES
    out = base64.b64decode(body["outputFileBase64"])
    again = embroidery_io.read_embroidery(out, "pes")
    assert again.stitch_count > 0
    assert len(again.color_stops) == 2


def test_convert_pes_to_dst_warns_about_color_loss():
    r = client.post(
        "/api/convert",
        json={"inputFileBase64": _b64("sample.pes"), "fromFormat": "pes", "toFormat": "dst"},
    )
    assert r.status_code == 200
    assert any("no thread colors" in w for w in r.json()["warnings"])


def test_convert_rejects_bad_base64():
    r = client.post(
        "/api/convert",
        json={"inputFileBase64": "not-base64!!!", "fromFormat": "dst", "toFormat": "pes"},
    )
    assert r.status_code == 400


def test_convert_rejects_unknown_format():
    r = client.post(
        "/api/convert",
        json={"inputFileBase64": _b64("sample.dst"), "fromFormat": "zzz", "toFormat": "pes"},
    )
    assert r.status_code == 415
