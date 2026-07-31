"""Design-name metadata round-trip through machine formats (swarm: export team).

Covers embroidery_io writing the design name into DST ('LA:' header) and PES
(v6 Name), and read_embroidery surfacing it on import.
"""

from __future__ import annotations

import pyembroidery as pe
import pytest

from app.models.design import ColorStop, Design, Stitch
from app.services import embroidery_io

# DST 'LA:' field width enforced by _machine_name — mirrored here so the tests
# fail loudly if the constant drifts.
_DST_NAME_MAX = 16


def _design(name: str) -> Design:
    """Two-color square design (same shape as tests/test_embroidery_io.py)."""
    stitches = [
        Stitch(x=x / 10.0, y=y / 10.0, command="STITCH")
        for x, y in [(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)]
    ]
    stitches.append(Stitch(x=0.0, y=0.0, command="COLOR_CHANGE"))
    stitches += [
        Stitch(x=10.0, y=10.0, command="STITCH"),
        Stitch(x=40.0, y=40.0, command="STITCH"),
    ]
    return Design(
        name=name,
        width_mm=50.0,
        height_mm=50.0,
        stitch_count=len(stitches),
        color_stops=[
            ColorStop(
                stop_number=1,
                thread_brand="Madeira",
                catalog_number="1147",
                thread_name="Red",
                hex="#c81e28",
                stitch_count=5,
            ),
            ColorStop(
                stop_number=2,
                thread_brand="Madeira",
                catalog_number="1733",
                thread_name="Blue",
                hex="#1e3cc8",
                stitch_count=2,
            ),
        ],
        stitches=stitches,
        status="digitized",
    )


@pytest.mark.parametrize("fmt", ["pes", "dst"])
def test_name_roundtrips(fmt):
    data = embroidery_io.write_embroidery(_design("SwarmLogo"), fmt)
    again = embroidery_io.read_embroidery(data, fmt)
    assert again.name == "SwarmLogo"


def test_dst_truncates_long_name_at_16():
    long_name = "A" * 15 + "B" + "C" * 14  # 30 chars; first 16 = 15*A + B
    assert len(long_name) == 30
    data = embroidery_io.write_embroidery(_design(long_name), "dst")
    again = embroidery_io.read_embroidery(data, "dst")
    assert again.name == long_name[:_DST_NAME_MAX]


def test_dst_bytes_carry_la_header_with_name():
    data = embroidery_io.write_embroidery(_design("SwarmLogo"), "dst")
    assert data.startswith(b"LA:")
    assert b"SwarmLogo" in data


@pytest.mark.parametrize("fmt", ["dst", "pes"])
def test_non_ascii_name_is_sanitized_not_fatal(fmt):
    data = embroidery_io.write_embroidery(_design("Bücher ★ Löwe"), fmt)
    assert data  # write must not raise and must produce bytes
    if fmt == "dst":
        again = embroidery_io.read_embroidery(data, "dst")
        assert again.name.isascii()
        assert again.name.strip()  # sanitized, not emptied


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  SwarmLogo  ", "SwarmLogo"),  # stripped
        ("Bücher ★ Löwe", "Bcher  Lwe"),  # non-ASCII dropped, not fatal
        ("★★★", "design"),  # sanitizes to empty -> fallback
        ("", "design"),
        (None, "design"),
        ("A" * 30, "A" * _DST_NAME_MAX),  # capped at the DST LA: field width
    ],
)
def test_machine_name_sanitizes(raw, expected):
    assert embroidery_io._machine_name(raw) == expected


@pytest.mark.parametrize("extras", [None, {}, {"name": "  "}, {"name": "Untitled"}])
def test_stored_name_falls_back(extras):
    # 'Untitled' is DST writer filler, not a user-chosen name.
    p = pe.EmbPattern()
    if extras is not None:
        p.extras.update(extras)
    assert embroidery_io._stored_name(p) == "Imported design"


def test_stored_name_prefers_pes_capital_name_key():
    p = pe.EmbPattern()
    p.extras["Name"] = "PesName"
    assert embroidery_io._stored_name(p) == "PesName"


def test_color_stops_empty_for_stitchless_pattern():
    assert embroidery_io._color_stops(pe.EmbPattern()) == []


def test_file_without_metadata_keeps_default_name(tmp_path):
    p = pe.EmbPattern()
    t = pe.EmbThread()
    t.set_color(200, 30, 40)
    p.add_thread(t)
    for x, y in [(0, 0), (100, 0), (100, 100)]:
        p.add_stitch_absolute(pe.STITCH, x, y)
    p.end()
    f = tmp_path / "noname.dst"
    pe.write_dst(p, str(f))
    design = embroidery_io.read_embroidery(f.read_bytes(), "dst")
    assert design.name == "Imported design"
