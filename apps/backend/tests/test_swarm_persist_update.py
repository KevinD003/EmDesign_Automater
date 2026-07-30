"""local_store update_design/rename_design: overwrite + rename semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.design import ColorStop, Design, Stitch
from app.services import local_store


@pytest.fixture()
def disk(tmp_path, monkeypatch) -> Path:
    """Force disk mode rooted at an isolated tmp dir."""
    monkeypatch.setenv("STITCHIQ_DESIGNS_DIR", str(tmp_path))
    return tmp_path


def _design(name: str = "Rose", n_stitches: int = 3, **kwargs) -> Design:
    return Design(
        name=name,
        stitch_count=n_stitches,
        stitches=[Stitch(x=float(i), y=0.0) for i in range(n_stitches)],
        color_stops=[
            ColorStop(
                stop_number=1,
                thread_brand="Madeira",
                catalog_number="1000",
                thread_name="Red",
                hex="#ff0000",
            )
        ],
        **kwargs,
    )


def test_update_overwrites_content_but_preserves_created_at(disk):
    created = local_store.create_design(
        _design("Old", created_at="2026-01-01T00:00:00+00:00"), "u"
    )

    updated = local_store.update_design(created.id, _design("New", n_stitches=5), "u")
    assert updated is not None
    assert updated.id == created.id
    assert updated.created_at == "2026-01-01T00:00:00+00:00"  # original stamp kept

    got = local_store.get_design(created.id, "u")
    assert got is not None
    assert got.name == "New" and len(got.stitches) == 5
    assert got.created_at == "2026-01-01T00:00:00+00:00"

    # On-disk JSON reflects the overwrite (camelCase, same file).
    raw = json.loads((disk / "u" / f"{created.id}.json").read_text())
    assert raw["name"] == "New" and raw["createdAt"] == "2026-01-01T00:00:00+00:00"


def test_update_missing_id_is_none_and_creates_no_file(disk):
    assert local_store.update_design("deadbeef", _design(), "u") is None
    assert list(disk.rglob("*.json")) == []


def test_update_does_not_reshuffle_newest_first_ordering(disk):
    local_store.create_design(_design("Old", created_at="2026-01-01T00:00:00+00:00"), "u")
    new = local_store.create_design(
        _design("New", created_at="2026-02-01T00:00:00+00:00"), "u"
    )
    # Updating the OLDER design must not move it to the top of the listing.
    old = local_store.list_designs("u")[1]
    local_store.update_design(old.id, _design("Old v2"), "u")
    assert [d.id for d in local_store.list_designs("u")] == [new.id, old.id]


def test_rename_changes_only_the_name(disk):
    created = local_store.create_design(_design("Rose", n_stitches=4), "u")

    renamed = local_store.rename_design(created.id, "  Tulip  ", "u")
    assert renamed is not None
    assert renamed.name == "Tulip"  # surrounding whitespace stripped

    got = local_store.get_design(created.id, "u")
    assert got is not None
    assert got.name == "Tulip"
    assert len(got.stitches) == 4  # stitch data intact
    assert got.stitch_count == 4 and len(got.color_stops) == 1
    assert got.created_at == created.created_at


def test_rename_caps_name_at_200_chars(disk):
    created = local_store.create_design(_design(), "u")
    renamed = local_store.rename_design(created.id, "x" * 500, "u")
    assert renamed is not None and len(renamed.name) == 200


def test_rename_missing_is_none(disk):
    assert local_store.rename_design("deadbeef", "New Name", "u") is None


@pytest.mark.parametrize("bad_name", ["", "   ", "\t\n"])
def test_rename_blank_name_raises_value_error(disk, bad_name):
    created = local_store.create_design(_design(), "u")
    with pytest.raises(ValueError, match="name must not be empty"):
        local_store.rename_design(created.id, bad_name, "u")
    # Stored design untouched by the failed rename.
    assert local_store.get_design(created.id, "u").name == "Rose"


def test_other_users_design_is_invisible_to_update_and_rename(disk):
    created = local_store.create_design(_design("Private"), "alice")
    assert local_store.update_design(created.id, _design("Hijack"), "bob") is None
    assert local_store.rename_design(created.id, "Hijack", "bob") is None
    assert local_store.get_design(created.id, "alice").name == "Private"


def test_unsafe_design_id_is_none_and_never_escapes(disk):
    assert local_store.update_design("../x", _design(), "u") is None
    assert local_store.rename_design("../x", "Name", "u") is None
    # Nothing written anywhere — inside the root or beside it.
    assert list(disk.rglob("*")) == []
    assert not (disk.parent / "x.json").exists()


def test_memory_mode_update_and_rename_roundtrip(monkeypatch):
    """Without the env var, pytest runs use the in-memory backend (_MEMORY)."""
    monkeypatch.delenv("STITCHIQ_DESIGNS_DIR", raising=False)
    local_store._MEMORY.clear()  # mutate only — the name/binding is load-bearing

    created = local_store.create_design(
        _design("Mem", created_at="2026-03-01T00:00:00+00:00"), "u"
    )

    updated = local_store.update_design(created.id, _design("Mem v2", n_stitches=2), "u")
    assert updated is not None and updated.created_at == "2026-03-01T00:00:00+00:00"
    assert local_store._MEMORY[("u", created.id)].name == "Mem v2"

    renamed = local_store.rename_design(created.id, "Mem final", "u")
    assert renamed is not None and renamed.name == "Mem final"
    got = local_store.get_design(created.id, "u")
    assert got.name == "Mem final" and len(got.stitches) == 2

    assert local_store.update_design("missing", _design(), "u") is None
    assert local_store.rename_design("missing", "x", "u") is None
