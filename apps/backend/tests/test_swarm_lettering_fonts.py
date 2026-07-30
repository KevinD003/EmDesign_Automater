"""Swarm tests: font scanning for the lettering engine (list_fonts)."""

from __future__ import annotations

import os
import shutil

from app.services.lettering import list_fonts

_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def test_list_fonts_non_empty_and_includes_dejavu():
    fonts = list_fonts()
    assert fonts, "expected at least one system font on this Linux env"
    assert any("DejaVu" in f["path"] for f in fonts)


def test_every_entry_has_name_and_existing_path():
    fonts = list_fonts()
    for entry in fonts:
        assert entry["name"], f"empty display name for {entry['path']}"
        assert os.path.isfile(entry["path"])


def test_env_fonts_dir_is_scanned(monkeypatch, tmp_path):
    copy = tmp_path / "SwarmTestCopy.ttf"
    shutil.copyfile(_DEJAVU_BOLD, copy)
    monkeypatch.setenv("STITCHIQ_FONTS_DIR", str(tmp_path))
    reals = {os.path.realpath(f["path"]) for f in list_fonts()}
    assert os.path.realpath(str(copy)) in reals


def test_garbage_font_is_skipped_silently(monkeypatch, tmp_path):
    garbage = tmp_path / "garbage.ttf"
    garbage.write_bytes(b"not a font")
    monkeypatch.setenv("STITCHIQ_FONTS_DIR", str(tmp_path))
    fonts = list_fonts()  # must not raise
    assert all(os.path.realpath(str(garbage)) != os.path.realpath(f["path"]) for f in fonts)


def test_sorted_by_name_and_paths_unique():
    fonts = list_fonts()
    names = [f["name"] for f in fonts]
    assert names == sorted(names)
    paths = [f["path"] for f in fonts]
    assert len(paths) == len(set(paths))
