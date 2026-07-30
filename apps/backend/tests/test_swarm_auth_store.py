"""Tests for the local user profile store (app/services/user_store.py)."""

import pytest

from app.services.user_store import DuplicateUsernameError, UserStore


def test_create_and_list_round_trip_persists(tmp_path):
    path = tmp_path / "u.json"
    store = UserStore(path)
    created = store.create_profile("Alice", "1234")
    assert created["username"] == "Alice"
    assert created["hasPin"] is True
    assert created["userId"].startswith("local-")
    # Secrets must never appear in the public dict.
    assert "pin_hash" not in created and "pin_salt" not in created

    # A second instance on the same path must see the persisted profile.
    reloaded = UserStore(path)
    profiles = reloaded.list_profiles()
    assert [p["userId"] for p in profiles] == [created["userId"]]
    assert profiles[0]["createdAt"] == created["createdAt"]


def test_duplicate_username_case_insensitive(tmp_path):
    store = UserStore(tmp_path / "u.json")
    store.create_profile("Alice", None)
    with pytest.raises(DuplicateUsernameError):
        store.create_profile("alice", None)
    with pytest.raises(DuplicateUsernameError):
        store.create_profile("  ALICE  ", None)


@pytest.mark.parametrize("bad_name", ["", "   ", "a" * 33, "bad!name", "x@y"])
def test_invalid_username_raises_value_error(tmp_path, bad_name):
    store = UserStore(tmp_path / "u.json")
    with pytest.raises(ValueError):
        store.create_profile(bad_name, None)


@pytest.mark.parametrize("bad_pin", ["123", "", "x" * 65])
def test_bad_pin_length_raises_value_error(tmp_path, bad_pin):
    store = UserStore(tmp_path / "u.json")
    with pytest.raises(ValueError):
        store.create_profile("bob", bad_pin)


def test_verify_pin_true_and_false(tmp_path):
    store = UserStore(tmp_path / "u.json")
    profile = store.create_profile("carol", "secret99")
    assert store.verify_pin(profile["userId"], "secret99") is True
    assert store.verify_pin(profile["userId"], "wrongpin") is False
    assert store.verify_pin("local-nonexistent", "secret99") is False


def test_profile_without_pin(tmp_path):
    store = UserStore(tmp_path / "u.json")
    profile = store.create_profile("dave", None)
    assert profile["hasPin"] is False
    assert store.verify_pin(profile["userId"], "anything") is False


def test_get_by_username_case_insensitive(tmp_path):
    store = UserStore(tmp_path / "u.json")
    created = store.create_profile("Erin Smith", None)
    record = store.get_by_username("erin smith")
    assert record is not None
    assert record["user_id"] == created["userId"]
    assert store.get_by_username("nobody") is None


def test_corrupt_file_recovers_to_empty(tmp_path):
    path = tmp_path / "u.json"
    path.write_text("not json", encoding="utf-8")
    store = UserStore(path)
    assert store.list_profiles() == []
    # The store must remain usable after recovery.
    store.create_profile("frank", None)
    assert len(UserStore(path).list_profiles()) == 1
