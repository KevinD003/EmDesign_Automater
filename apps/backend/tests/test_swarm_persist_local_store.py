"""local_store: file-backed design persistence (disk mode + in-memory pytest mode)."""

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


def _design(name: str = "Rose", n_stitches: int = 3, n_colors: int = 2, **kwargs) -> Design:
    return Design(
        name=name,
        stitch_count=n_stitches,
        stitches=[Stitch(x=float(i), y=0.0) for i in range(n_stitches)],
        color_stops=[
            ColorStop(
                stop_number=i + 1,
                thread_brand="Madeira",
                catalog_number=str(1000 + i),
                thread_name="Red",
                hex="#ff0000",
            )
            for i in range(n_colors)
        ],
        **kwargs,
    )


def test_create_get_roundtrip_preserves_stitches(disk):
    created = local_store.create_design(_design(), "alice@example.com")
    assert created.id and created.created_at  # id + timestamp assigned

    got = local_store.get_design(created.id, "alice@example.com")
    assert got is not None
    assert [ (s.x, s.y) for s in got.stitches ] == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    assert got.name == "Rose" and len(got.color_stops) == 2

    # File lives under the sanitized user dir, and is camelCase JSON.
    path = disk / "alice@example.com" / f"{created.id}.json"
    assert path.is_file()
    assert json.loads(path.read_text())["stitchCount"] == 3


def test_create_honors_provided_safe_id(disk):
    created = local_store.create_design(_design(id="my-design-1"), "u")
    assert created.id == "my-design-1"
    assert (disk / "u" / "my-design-1.json").is_file()


def test_list_is_newest_first_and_strips_stitches(disk):
    local_store.create_design(_design("Old", created_at="2026-01-01T00:00:00+00:00"), "u")
    local_store.create_design(_design("New", created_at="2026-02-01T00:00:00+00:00"), "u")

    listing = local_store.list_designs("u")
    assert [d.name for d in listing] == ["New", "Old"]
    for d in listing:
        assert d.stitches == []  # kept light
        assert d.stitch_count == 3 and len(d.color_stops) == 2  # metadata retained


def test_delete_then_get_is_none_and_idempotent(disk):
    created = local_store.create_design(_design(), "u")
    local_store.delete_design(created.id, "u")
    assert local_store.get_design(created.id, "u") is None
    local_store.delete_design(created.id, "u")  # second delete: no error


@pytest.mark.parametrize("bad_id", ["../x", "a/b", "..", "", "a" * 65, "x.json"])
def test_unsafe_ids_are_not_found_and_never_escape(disk, bad_id):
    assert local_store.get_design(bad_id, "u") is None
    local_store.delete_design(bad_id, "u")  # no-op, no exception

    # Creating with an unsafe id must replace it, never write outside tmp_path.
    created = local_store.create_design(_design(id=bad_id or None), "u")
    assert created.id != bad_id
    assert not (disk.parent / "x.json").exists() and not (disk / "x.json").exists()
    files = [p for p in disk.rglob("*") if p.is_file()]
    assert files == [disk / "u" / f"{created.id}.json"]


def test_corrupt_files_are_skipped_by_list(disk):
    good = local_store.create_design(_design("Good"), "u")
    user_dir = disk / "u"
    (user_dir / "broken.json").write_text("{not json", encoding="utf-8")
    (user_dir / "wrongshape.json").write_text('{"name": 42}', encoding="utf-8")

    listing = local_store.list_designs("u")
    assert [d.id for d in listing] == [good.id]


def test_user_isolation(disk):
    created = local_store.create_design(_design("Private"), "alice")
    assert local_store.get_design(created.id, "bob") is None
    assert local_store.list_designs("bob") == []
    # bob's delete of alice's id must not remove alice's design
    local_store.delete_design(created.id, "bob")
    assert local_store.get_design(created.id, "alice") is not None


def test_user_dir_is_sanitized(disk):
    local_store.create_design(_design(), "../evil user")
    # dots survive, but the slash is replaced — the name stays a single component
    assert (disk / ".._evil_user").is_dir()
    assert not (disk.parent / "evil user").exists()
    # a dot-only user must not resolve to a parent directory
    local_store.create_design(_design(), "..")
    assert (disk / "anonymous").is_dir()


def test_design_stats_shape_and_values(disk):
    local_store.create_design(
        _design("A", n_stitches=10, n_colors=2, created_at="2026-01-01T00:00:00+00:00"), "u"
    )
    local_store.create_design(
        _design("B", n_stitches=5, n_colors=3, created_at="2026-02-01T00:00:00+00:00"), "u"
    )

    stats = local_store.design_stats("u")
    assert set(stats) == {"designCount", "totalStitches", "totalColors", "recent"}
    assert stats["designCount"] == 2
    assert stats["totalStitches"] == 15
    assert stats["totalColors"] == 5
    assert [r["name"] for r in stats["recent"]] == ["B", "A"]  # newest first
    first = stats["recent"][0]
    assert set(first) == {"id", "name", "stitchCount", "savedAt"}
    assert first["stitchCount"] == 5 and first["savedAt"].startswith("2026-02-01")


def test_stats_recent_caps_at_eight(disk):
    for i in range(10):
        local_store.create_design(
            _design(f"D{i}", created_at=f"2026-01-{i + 1:02d}T00:00:00+00:00"), "u"
        )
    stats = local_store.design_stats("u")
    assert stats["designCount"] == 10
    assert len(stats["recent"]) == 8
    assert stats["recent"][0]["name"] == "D9"


def test_memory_mode_under_pytest(monkeypatch):
    """Without the env var, pytest runs use the in-memory backend (_MEMORY)."""
    monkeypatch.delenv("STITCHIQ_DESIGNS_DIR", raising=False)
    local_store._MEMORY.clear()  # mutate only — the name/binding is load-bearing

    created = local_store.create_design(_design("MemOnly"), "u")
    assert ("u", created.id) in local_store._MEMORY

    got = local_store.get_design(created.id, "u")
    assert got is not None and len(got.stitches) == 3

    listing = local_store.list_designs("u")
    assert [d.name for d in listing] == ["MemOnly"] and listing[0].stitches == []
    assert local_store.design_stats("u")["designCount"] == 1

    local_store.delete_design(created.id, "u")
    assert local_store.get_design(created.id, "u") is None
    assert local_store._MEMORY == {}
