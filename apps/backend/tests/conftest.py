"""Suite-wide isolation (v2 Part 21) and shared paths (v2 Part 66).

Tests must never read or write the operator's real local-account database.
Before this file existed, `app/deps.py` resolved users against
`apps/backend/data/local_users.json` — a developer who had ever signed up
locally made 25 unrelated tests fail with 401, and a test could in principle
mutate real credentials. Each test now gets an empty store in a temp dir
unless it sets `STITCHIQ_USER_STORE` itself.

Part 66: the backend root and scripts dir are put on sys.path HERE, once —
twenty test files carried their own copy of that shim. Old shims are
idempotent and harmless; new test files should not add one.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_BACKEND_ROOT), str(_BACKEND_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

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
