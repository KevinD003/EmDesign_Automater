"""GET /api/designs/{id}/preview — PNG thumbnails for the library grid.

Runs against the real local_store disk backend (STITCHIQ_DESIGNS_DIR -> tmp_path),
so the fetch → render path is exercised end-to-end over HTTP.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")  # preview rendering needs Pillow; skip cleanly without it

from fastapi.testclient import TestClient

from app.main import app
from app.services import supabase_store

client = TestClient(app)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(autouse=True)
def _local_disk(monkeypatch, tmp_path):
    monkeypatch.setattr(supabase_store, "is_enabled", lambda: False)
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(tmp_path))
    return tmp_path


def _design(name: str = "Preview", *, stitches: bool = True) -> dict:
    pts = [(0, 0), (8, 0), (8, 6), (0, 6), (0, 0)] if stitches else []
    return {
        "name": name,
        "widthMm": 40,
        "heightMm": 30,
        "stitchCount": len(pts),
        "version": 1,
        "status": "draft",
        "colorStops": [
            {
                "stopNumber": 1,
                "threadBrand": "Madeira",
                "catalogNumber": "1147",
                "threadName": "Scarlet",
                "hex": "#e11d48",
                "stitchCount": len(pts),
            }
        ],
        "objects": [],
        "stitches": [{"x": x, "y": y, "command": "STITCH"} for x, y in pts],
    }


def _create(payload: dict) -> str:
    created = client.post("/api/designs", json=payload)
    assert created.status_code == 201
    return created.json()["id"]


def test_preview_returns_png_with_no_store():
    did = _create(_design("Logo"))
    r = client.get(f"/api/designs/{did}/preview")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"
    assert r.content.startswith(PNG_MAGIC)


def test_preview_is_a_real_decodable_image():
    from io import BytesIO

    from PIL import Image

    did = _create(_design("Logo"))
    img = Image.open(BytesIO(client.get(f"/api/designs/{did}/preview").content))
    # Larger than the 2x2 blank package.render_preview emits for an empty design.
    assert img.format == "PNG"
    assert img.width > 2 and img.height > 2


def test_preview_unknown_id_is_404():
    r = client.get("/api/designs/does-not-exist/preview")
    assert r.status_code == 404
    assert r.json()["detail"] == "design not found"


def test_preview_of_stitchless_design_is_422():
    did = _create(_design("Empty", stitches=False))
    r = client.get(f"/api/designs/{did}/preview")
    assert r.status_code == 422
    assert r.json()["detail"] == "design has no stitches to preview"


def test_plain_get_still_returns_full_json_after_refactor():
    """Regression: GET /designs/{id} now shares _fetch_design with the preview route."""
    did = _create(_design("Logo"))
    r = client.get(f"/api/designs/{did}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == did
    assert body["name"] == "Logo"
    assert len(body["stitches"]) == 5
    assert body["colorStops"][0]["hex"] == "#e11d48"


def test_plain_get_unknown_id_still_404():
    assert client.get("/api/designs/nope/").status_code in (404, 405)
    assert client.get("/api/designs/nope").status_code == 404
