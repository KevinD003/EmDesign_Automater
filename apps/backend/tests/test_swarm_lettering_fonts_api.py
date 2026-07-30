"""API tests for GET /api/lettering/fonts (font listing for the lettering dialog)."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_fonts_endpoint_returns_nonempty_list():
    resp = client.get("/api/lettering/fonts")
    assert resp.status_code == 200
    fonts = resp.json()
    assert isinstance(fonts, list) and fonts


def test_fonts_entries_have_camelcase_name_and_path():
    fonts = client.get("/api/lettering/fonts").json()
    for f in fonts:
        # CamelModel serializes camelCase; both fields are single words here,
        # so the keys must be exactly 'name' and 'path' (no snake_case leaks).
        assert set(f) == {"name", "path"}
        assert isinstance(f["name"], str) and f["name"]
        assert isinstance(f["path"], str) and f["path"]


def test_at_least_one_font_path_exists_on_disk():
    fonts = client.get("/api/lettering/fonts").json()
    assert any(os.path.isfile(f["path"]) for f in fonts)


def test_post_lettering_still_validates_empty_text():
    # Smoke only — a full digitize is too slow for this file.
    resp = client.post("/api/lettering", json={"text": ""})
    assert resp.status_code == 422
