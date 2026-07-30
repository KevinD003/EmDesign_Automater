"""Session-token tests for app.services.user_store (issue/verify/login/revoke)."""

import pytest

from app.services.user_store import (
    MAX_SESSIONS_PER_USER,
    UserStore,
    reset_store_cache,
    resolve_bearer,
)


@pytest.fixture
def store(tmp_path):
    return UserStore(tmp_path / "users.json")


def test_login_without_pin_yields_verifiable_token(store):
    created = store.create_profile("Alice", None)
    result = store.login("alice", None)
    assert result is not None
    profile, token = result
    assert profile["userId"] == created["userId"]
    verified = store.verify_token(token)
    assert verified is not None
    assert verified["userId"] == created["userId"]


def test_login_without_pin_ignores_provided_pin(store):
    store.create_profile("Alice", None)
    assert store.login("Alice", "whatever") is not None


def test_login_with_correct_pin_succeeds(store):
    created = store.create_profile("Bob", "1234")
    result = store.login("BOB", "1234")
    assert result is not None
    profile, token = result
    assert profile["userId"] == created["userId"]
    assert store.verify_token(token)["userId"] == created["userId"]


def test_login_wrong_or_missing_pin_returns_none(store):
    store.create_profile("Bob", "1234")
    assert store.login("Bob", "9999") is None
    assert store.login("Bob", None) is None


def test_login_unknown_username_returns_none(store):
    assert store.login("Nobody", "1234") is None


def test_issue_token_unknown_user_raises(store):
    with pytest.raises(KeyError):
        store.issue_token("local-doesnotexist")


def test_tokens_survive_reopening_store(tmp_path):
    path = tmp_path / "users.json"
    first = UserStore(path)
    created = first.create_profile("Carol", None)
    _, token = first.login("Carol", None)

    reopened = UserStore(path)
    verified = reopened.verify_token(token)
    assert verified is not None
    assert verified["userId"] == created["userId"]


def test_revoke_token_invalidates(store):
    store.create_profile("Dave", None)
    _, token = store.login("Dave", None)
    assert store.revoke_token(token) is True
    assert store.verify_token(token) is None
    assert store.revoke_token(token) is False


def test_verify_token_garbage_returns_none(store):
    assert store.verify_token("not-a-token") is None


def test_session_cap_evicts_oldest(store):
    created = store.create_profile("Eve", None)
    tokens = [
        store.issue_token(created["userId"])
        for _ in range(MAX_SESSIONS_PER_USER + 5)
    ]
    live = [t for t in tokens if store.verify_token(t) is not None]
    assert len(live) <= MAX_SESSIONS_PER_USER
    # The newest token must always survive eviction.
    assert store.verify_token(tokens[-1]) is not None


def test_cap_is_per_user(store):
    a = store.create_profile("UserA", None)
    b = store.create_profile("UserB", None)
    token_b = store.issue_token(b["userId"])
    for _ in range(MAX_SESSIONS_PER_USER + 5):
        store.issue_token(a["userId"])
    # User A's churn must not evict user B's token.
    assert store.verify_token(token_b)["userId"] == b["userId"]


@pytest.fixture
def env_store(tmp_path, monkeypatch):
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(tmp_path / "env_users.json"))
    reset_store_cache()
    yield UserStore(tmp_path / "env_users.json")
    reset_store_cache()


def test_resolve_bearer_valid_token(env_store):
    created = env_store.create_profile("Frank", None)
    token = env_store.issue_token(created["userId"])
    assert resolve_bearer(f"Bearer {token}") == created["userId"]
    # Scheme match is case-insensitive.
    assert resolve_bearer(f"bearer {token}") == created["userId"]


def test_resolve_bearer_rejects_bad_headers(env_store):
    created = env_store.create_profile("Grace", None)
    token = env_store.issue_token(created["userId"])
    assert resolve_bearer(None) is None
    assert resolve_bearer("") is None
    assert resolve_bearer("garbage") is None
    assert resolve_bearer("Basic x") is None
    assert resolve_bearer(f"Basic {token}") is None
    assert resolve_bearer("Bearer not-a-real-token") is None
