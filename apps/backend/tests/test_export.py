"""Tests for GET /api/formats advertising — every advertised format must be writable.

Regression: the list was hardcoded and included "vip", which pyembroidery can READ
but not WRITE, so choosing it produced a guaranteed 415 at export time.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.design import Design, Stitch
from app.routers.export import MACHINE_EXPORT_FORMATS
from app.services import embroidery_io

client = TestClient(app)


def _two_stitch_design() -> Design:
    return Design(
        name="two-stitch",
        width_mm=10.0,
        height_mm=0.0,
        stitch_count=2,
        stitches=[Stitch(x=0, y=0, command="STITCH"), Stitch(x=10, y=0, command="STITCH")],
    )


def test_formats_does_not_advertise_unwritable_or_internal():
    body = client.get("/api/formats").json()
    assert "vip" not in body["export"]  # pyembroidery has no VIP writer
    assert "hus" not in body["export"]  # HUS is import-only in pyembroidery
    for internal in ("json", "svg", "png", "txt"):
        assert internal not in body["export"]


def test_every_advertised_format_round_trips_a_design():
    body = client.get("/api/formats").json()
    assert body["export"], "at least one machine format must be advertised"
    design = _two_stitch_design()
    for fmt in body["export"]:
        data = embroidery_io.write_embroidery(design, fmt)  # must not raise
        assert data, f"{fmt} wrote no bytes"


def test_advertised_list_is_writable_machine_formats_in_order():
    body = client.get("/api/formats").json()
    writable = embroidery_io.supported_write_exts()
    assert body["export"] == [f for f in MACHINE_EXPORT_FORMATS if f in writable]
    assert "dst" in body["export"] and "pes" in body["export"]
