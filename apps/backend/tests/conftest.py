"""Suite-wide isolation (v2 Part 21).

Tests must never read or write the operator's real local-account database.
Before this file existed, `app/deps.py` resolved users against
`apps/backend/data/local_users.json` — a developer who had ever signed up
locally made 25 unrelated tests fail with 401, and a test could in principle
mutate real credentials. Each test now gets an empty store in a temp dir
unless it sets `STITCHIQ_USER_STORE` itself.
"""

from __future__ import annotations

import pytest

from app.services import user_store


@pytest.fixture(autouse=True)
def _isolate_user_store(tmp_path_factory, monkeypatch, request):
    """Point the local-account store at a per-test temp file."""
    if request.node.get_closest_marker("real_user_store"):
        yield
        return
    store_path = tmp_path_factory.mktemp("userstore") / "local_users.json"
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(store_path))
    user_store.reset_store_cache()
    yield
    user_store.reset_store_cache()
