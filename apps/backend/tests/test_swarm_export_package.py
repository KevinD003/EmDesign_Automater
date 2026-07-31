"""Package ZIP completeness: exact members, magic bytes, every advertised format.

Complements tests/test_package.py, which checks the dst package loosely (by file
extension only). Here the member list is asserted EXACTLY, for every format the
live GET /api/formats advertises, so a renamed/dropped/added member or a format
whose package build crashes fails immediately.

No package.py defect was found while writing these: all nine advertised formats
build a 7-member ZIP with no corrupt or empty entries, so package.py is untouched.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import Design
from app.services import embroidery_io
from app.services.package import build_package, safe_stem

client = TestClient(app)

_FIXTURE = Path(__file__).parent / "fixtures" / "sample.pes"

# Fetched at collection time so parametrization mirrors the live endpoint rather
# than a hardcoded copy of MACHINE_EXPORT_FORMATS.
ADVERTISED_FORMATS: list[str] = client.get("/api/formats").json()["export"]

# Machine writers add tie-ins/tie-offs and split long jumps, so exact stitch
# counts are NOT stable across a write/read cycle. Bounds are the invariant;
# 1.5mm absorbs per-format coordinate quantization (see test_embroidery_io.py).
_BOUNDS_TOLERANCE_MM = 1.5

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_PDF_MAGIC = b"%PDF-"


def _fixture_design() -> Design:
    """sample.pes decoded to a multi-color Design with real stitches."""
    design = embroidery_io.read_embroidery(_FIXTURE.read_bytes(), "pes")
    assert len(design.color_stops) >= 2, "fixture must be multi-color"
    assert design.stitch_count > 0, "fixture must have real stitches"
    return design


def _expected_members(design: Design, fmt: str) -> set[str]:
    """The exact 7 members build_package promises (spec §4.8)."""
    stem = safe_stem(design.name)
    return {
        f"{stem}.{fmt}",
        f"{stem}.stiq.json",
        f"{stem}-worksheet.pdf",
        f"{stem}-colorcard.pdf",
        f"{stem}-preview.png",
        f"{stem}-summary.txt",
        "quality.json",  # fixed name: same wire shape as POST /api/optimize/quality
    }


def _zip_for(design: Design, fmt: str) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(build_package(design, fmt)))


def test_advertised_formats_is_not_empty():
    assert ADVERTISED_FORMATS, "GET /api/formats must advertise at least one format"


@pytest.mark.parametrize("fmt", ADVERTISED_FORMATS)
def test_package_members_are_exactly_the_seven_expected(fmt):
    design = _fixture_design()
    z = _zip_for(design, fmt)
    names = z.namelist()
    assert len(names) == len(set(names)), f"{fmt}: duplicate member names {names}"
    assert set(names) == _expected_members(design, fmt)


@pytest.mark.parametrize("fmt", ADVERTISED_FORMATS)
def test_package_has_no_corrupt_or_empty_members(fmt):
    z = _zip_for(_fixture_design(), fmt)
    assert z.testzip() is None, f"{fmt}: corrupt member {z.testzip()}"
    for name in z.namelist():
        assert len(z.read(name)) > 0, f"{fmt}: {name} is empty"


def test_member_magic_bytes_and_json_parse():
    # dst only: the six non-machine members are format-independent, so paying the
    # render cost once is enough.
    design = _fixture_design()
    stem = safe_stem(design.name)
    z = _zip_for(design, "dst")
    assert z.read(f"{stem}-worksheet.pdf")[:5] == _PDF_MAGIC
    assert z.read(f"{stem}-colorcard.pdf")[:5] == _PDF_MAGIC
    assert z.read(f"{stem}-preview.png")[:8] == _PNG_MAGIC

    master = json.loads(z.read(f"{stem}.stiq.json"))
    quality = json.loads(z.read("quality.json"))
    # The master carries the ORIGINAL name, not the sanitized filename stem.
    assert master["name"] == design.name
    assert master["stitchCount"] == design.stitch_count
    assert "score" in quality


@pytest.mark.parametrize("fmt", ADVERTISED_FORMATS)
def test_zipped_machine_file_rereads_within_bounds(fmt):
    if fmt not in embroidery_io._supported_read_exts():
        pytest.skip(f".{fmt} is write-only in pyembroidery")
    design = _fixture_design()
    z = _zip_for(design, fmt)
    again = embroidery_io.read_embroidery(z.read(f"{safe_stem(design.name)}.{fmt}"), fmt)
    assert again.stitch_count > 0
    assert abs(again.width_mm - design.width_mm) < _BOUNDS_TOLERANCE_MM
    assert abs(again.height_mm - design.height_mm) < _BOUNDS_TOLERANCE_MM


def test_summary_lists_name_count_and_every_color_stop():
    design = _fixture_design()
    z = _zip_for(design, "dst")
    summary = z.read(f"{safe_stem(design.name)}-summary.txt").decode("utf-8")
    assert design.name in summary
    assert f"{design.stitch_count:,}" in summary
    for cs in design.color_stops:
        line = next((ln for ln in summary.splitlines() if ln.strip().startswith(f"{cs.stop_number}.")), None)
        assert line is not None, f"stop {cs.stop_number} missing from summary"
        assert cs.hex in line
        assert cs.thread_name in line


def test_summary_stitch_count_uses_thousands_separator():
    # The fixture has 32 stitches, where "," is a no-op — force a 5-digit count so
    # the separator is actually exercised.
    design = _fixture_design().model_copy(update={"stitch_count": 12_345})
    z = _zip_for(design, "dst")
    summary = z.read(f"{safe_stem(design.name)}-summary.txt").decode("utf-8")
    assert "12,345" in summary


@pytest.mark.parametrize("fmt", ADVERTISED_FORMATS)
def test_package_endpoint_streams_zip_for_every_format(fmt):
    design = _fixture_design()
    resp = client.post(
        "/api/export/package",
        params={"format": fmt},
        json=design.model_dump(by_alias=True),
    )
    assert resp.status_code == 200, f"{fmt}: {resp.text}"
    assert resp.headers["content-type"] == "application/zip"
    expected = f'attachment; filename="{safe_stem(design.name)}-package.zip"'
    assert resp.headers["content-disposition"] == expected
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    assert set(z.namelist()) == _expected_members(design, fmt)


def test_package_endpoint_rejects_unsupported_format():
    resp = client.post(
        "/api/export/package",
        params={"format": "nope"},
        json=_fixture_design().model_dump(by_alias=True),
    )
    assert resp.status_code == 415


def test_package_namelist_is_deterministic():
    # Byte-identical output is NOT required (ZIP entries carry a timestamp); the
    # member set and its order must not drift between builds.
    design = _fixture_design()
    assert _zip_for(design, "dst").namelist() == _zip_for(design, "dst").namelist()
