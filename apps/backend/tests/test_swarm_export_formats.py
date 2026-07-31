"""GET /api/formats 'capabilities' — the per-format table the UI uses to guide users.

The capability rows are plain dicts (no Pydantic model), so FastAPI serializes the
keys verbatim: snake_case, e.g. 'supports_color'.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.design import ColorStop, Design, Stitch
from app.services import embroidery_io

client = TestClient(app)

# Two visually distinct hexes: filler colors invented for a colorless format are
# random, so a color-preserving format must return these exact-ish values back.
_RED = "#ff0000"
_BLUE = "#0000ff"

# _color_stops stamps this phrase into thread names when a format carries no
# thread table — the user-visible tell that colors were dropped.
_NO_COLOR_MARKER = "no color data"


def _two_color_design() -> Design:
    """20 stitches, COLOR_CHANGE, 20 stitches — the minimum a 2-color file needs."""
    stitches: list[Stitch] = [Stitch(x=float(i), y=0.0, command="STITCH") for i in range(20)]
    stitches.append(Stitch(x=19.0, y=0.0, command="COLOR_CHANGE"))
    stitches += [Stitch(x=float(i), y=10.0, command="STITCH") for i in range(20)]
    stitches.append(Stitch(x=19.0, y=10.0, command="END"))
    stops = [
        ColorStop(
            stop_number=n,
            thread_brand="Madeira",
            catalog_number=f"100{n}",
            thread_name=name,
            hex=hexcode,
            stitch_count=20,
        )
        for n, (name, hexcode) in enumerate([("Red", _RED), ("Blue", _BLUE)], start=1)
    ]
    return Design(
        name="two-color",
        width_mm=19.0,
        height_mm=10.0,
        stitch_count=len(stitches),
        color_stops=stops,
        stitches=stitches,
        status="digitized",
    )


def _caps() -> list[dict]:
    return client.get("/api/formats").json()["capabilities"]


def test_formats_response_has_all_three_sections():
    body = client.get("/api/formats").json()
    for key in ("export", "brands", "capabilities"):
        assert key in body, f"/api/formats lost the '{key}' key"
    assert body["capabilities"], "capability table must not be empty"


def test_capability_formats_match_the_export_list_exactly():
    body = client.get("/api/formats").json()
    assert {row["format"] for row in body["capabilities"]} == set(body["export"])


def test_every_capability_row_is_fully_populated():
    for row in _caps():
        assert isinstance(row["format"], str) and row["format"]
        assert isinstance(row["label"], str) and row["label"]
        assert isinstance(row["supports_color"], bool)
        assert row["writable"] is True  # unwritable formats are filtered out
        assert isinstance(row["readable"], bool)
        assert isinstance(row["note"], str)
        for dim in ("max_width_mm", "max_height_mm"):
            assert row[dim] is None or isinstance(row[dim], (int, float))


def test_supports_color_flags_match_real_round_trip_behavior():
    by_fmt = {row["format"]: row for row in _caps()}
    assert by_fmt["dst"]["supports_color"] is False
    assert by_fmt["pes"]["supports_color"] is True

    design = _two_color_design()

    # PES stores an RGB thread table: both hexes survive and stay distinct.
    pes_stops = embroidery_io.read_embroidery(
        embroidery_io.write_embroidery(design, "pes"), "pes"
    ).color_stops
    assert len(pes_stops) == 2
    assert pes_stops[0].hex.lower() != pes_stops[1].hex.lower()
    assert {s.hex.lower() for s in pes_stops} == {_RED, _BLUE}

    # DST has no thread table: pyembroidery invents filler threads, which
    # read_embroidery labels honestly rather than passing off as real colors.
    dst_stops = embroidery_io.read_embroidery(
        embroidery_io.write_embroidery(design, "dst"), "dst"
    ).color_stops
    assert len(dst_stops) == 2
    for stop in dst_stops:
        assert _NO_COLOR_MARKER in stop.thread_name.lower()


def test_existing_export_and_brands_keys_are_unchanged():
    body = client.get("/api/formats").json()
    assert "dst" in body["export"]
    # brands is a list of rows, each keyed 'brand' — shape the frontend relies on.
    assert isinstance(body["brands"], list) and body["brands"]
    assert any(row["brand"].startswith("Brother") for row in body["brands"])
