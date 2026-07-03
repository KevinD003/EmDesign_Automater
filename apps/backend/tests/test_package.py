"""Tests for the production export package + formats map (spec §4.8) — Phase 5."""

from __future__ import annotations

import io
import os
import zipfile

from fastapi.testclient import TestClient

from app.main import app
from app.services import embroidery_io
from app.services.package import build_package, render_color_card, render_preview

client = TestClient(app)
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _design():
    with open(os.path.join(FIXTURES, "sample.pes"), "rb") as fh:
        return embroidery_io.read_embroidery(fh.read(), "pes")


def test_package_contains_all_artifacts():
    z = zipfile.ZipFile(io.BytesIO(build_package(_design(), "dst")))
    names = z.namelist()
    exts = sorted(n.rsplit(".", 1)[-1] for n in names)
    assert "dst" in exts          # machine file
    assert "json" in exts         # master .stiq.json
    assert exts.count("pdf") == 2 # worksheet + color card
    assert "png" in exts          # preview
    assert "txt" in exts          # summary
    # every entry is non-empty
    for n in names:
        assert len(z.read(n)) > 0
    # the machine file re-reads as a valid design
    dst = next(n for n in names if n.endswith(".dst"))
    assert embroidery_io.read_embroidery(z.read(dst), "dst").stitch_count > 0


def test_preview_is_png_and_colorcard_is_pdf():
    assert render_preview(_design())[:8] == b"\x89PNG\r\n\x1a\n"
    assert render_color_card(_design())[:5] == b"%PDF-"


def test_export_package_endpoint_streams_zip():
    r = client.post("/api/export/package", params={"format": "pes"}, json=_design().model_dump(by_alias=True))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert any(n.endswith(".pes") for n in z.namelist())


def test_formats_endpoint_lists_brands():
    r = client.get("/api/formats")
    assert r.status_code == 200
    body = r.json()
    assert "dst" in body["export"]
    assert any(b["brand"].startswith("Brother") for b in body["brands"])
