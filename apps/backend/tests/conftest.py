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

import os

import pytest

from app.services import user_store

# ── STITCHIQ_NO_REBUILD_PASSTHROUGH=1 — the second CI lane ───────────────────
#
# `rebuild_design` short-circuits when nothing about a design has changed and
# returns THE VERY SAME OBJECT. That is correct behaviour, but it also meant a
# test could "exercise" the rebuild path without running a single generator:
# P6 asserted stitch counts, coordinates and commands against `d` and `d`, and
# passed while the regenerated stream drifted 36% on a single object (CTO
# verdict V2). Six probes were hollowed out that way.
#
# Setting this variable makes every rebuild regenerate. CI runs the suite a
# second time with it on, so a test that only passes because of the
# short-circuit fails there and names itself. Tests that assert the
# short-circuit ITSELF are marked `needs_rebuild_passthrough` and skip in that
# lane — they are the two or three places where the pass-through is the subject
# rather than the scaffolding.
NO_PASSTHROUGH = os.getenv("STITCHIQ_NO_REBUILD_PASSTHROUGH") == "1"

if NO_PASSTHROUGH:  # pragma: no cover - exercised by the second CI lane
    from app.services.digitizer import rebuild as _rebuild_mod

    _rebuild_mod.rebuild_is_a_noop = lambda design, objs: False


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "needs_rebuild_passthrough: asserts the pass-through itself; skipped in "
        "the STITCHIQ_NO_REBUILD_PASSTHROUGH lane",
    )


def pytest_collection_modifyitems(config, items):
    if not NO_PASSTHROUGH:
        return
    skip = pytest.mark.skip(reason="pass-through disabled in this lane")
    for item in items:
        if item.get_closest_marker("needs_rebuild_passthrough"):
            item.add_marker(skip)


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
