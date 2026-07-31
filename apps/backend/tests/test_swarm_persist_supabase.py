"""Unit tests for supabase_store.update_design / rename_design — NO network.

httpx.AsyncClient is monkeypatched with a fake that records every (method, url, json)
and replays a scripted list of responses, so these assert the exact PostgREST calls.
"""

from __future__ import annotations

import asyncio
from typing import Self

import httpx
import pytest

from app.models.design import ColorStop, Design, Stitch
from app.services import supabase_store


class FakeResponse:
    """Minimal httpx.Response stand-in: json payload + status-driven raise_for_status."""

    def __init__(self, payload: object = None, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPError(f"boom {self.status_code}")


def install_fake_client(monkeypatch, responses: list[FakeResponse]) -> list[tuple]:
    """Patch supabase_store.httpx.AsyncClient; returns the shared (method, url, json) log."""
    calls: list[tuple] = []
    queue = list(responses)

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc) -> bool:
            return False

        def _next(self, method: str, url: str, json=None) -> FakeResponse:
            calls.append((method, url, json))
            assert queue, f"unscripted {method} {url}"
            return queue.pop(0)

        async def get(self, url, headers=None, **kw):
            return self._next("GET", url, kw.get("json"))

        async def patch(self, url, headers=None, json=None, **kw):
            return self._next("PATCH", url, json)

        async def post(self, url, headers=None, json=None, **kw):
            return self._next("POST", url, json)

        async def delete(self, url, headers=None, **kw):
            return self._next("DELETE", url, kw.get("json"))

    monkeypatch.setattr(supabase_store.httpx, "AsyncClient", FakeClient)
    return calls


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    """Make is_enabled() true and pin the REST base URL for assertions."""
    monkeypatch.setattr(supabase_store.settings, "supabase_url", "http://sb.test")
    monkeypatch.setattr(supabase_store.settings, "supabase_service_key", "svc-key")


def _design() -> Design:
    return Design(
        name="Tulip",
        width_mm=50.0,
        height_mm=40.0,
        fabric_type="cotton",
        stitch_count=2,
        status="draft",
        color_stops=[
            ColorStop(
                stop_number=1,
                thread_brand="Madeira",
                catalog_number="1001",
                thread_name="Red",
                hex="#ff0000",
            )
        ],
        stitches=[Stitch(x=1.0, y=2.0), Stitch(x=3.0, y=4.0)],
    )


def test_update_design_returns_none_when_not_owned(monkeypatch):
    calls = install_fake_client(monkeypatch, [FakeResponse([])])
    result = asyncio.run(supabase_store.update_design("d1", _design(), "u1"))
    assert result is None
    # Ownership GET is the only request — no PATCH/POST may follow a miss.
    assert [c[0] for c in calls] == ["GET"]
    assert "id=eq.d1" in calls[0][1] and "user_id=eq.u1" in calls[0][1]


def test_update_design_happy_path_bumps_version(monkeypatch):
    calls = install_fake_client(
        monkeypatch,
        [FakeResponse([{"id": "d1", "version": 3}]), FakeResponse([]), FakeResponse([])],
    )
    result = asyncio.run(supabase_store.update_design("d1", _design(), "u1"))

    assert [c[0] for c in calls] == ["GET", "PATCH", "POST"]
    assert result is not None
    assert result.id == "d1"
    assert result.version == 4

    patch_url, patch_json = calls[1][1], calls[1][2]
    assert patch_url == "http://sb.test/rest/v1/designs?id=eq.d1"
    assert patch_json == {
        "name": "Tulip",
        "stitch_count": 2,
        "colors": 1,
        "width_mm": 50.0,
        "height_mm": 40.0,
        "fabric_type": "cotton",
        "status": "draft",
        "version": 4,
    }


def test_update_design_snapshot_is_camel_case_and_id_forced(monkeypatch):
    calls = install_fake_client(
        monkeypatch,
        [FakeResponse([{"id": "d1", "version": 3}]), FakeResponse([]), FakeResponse([])],
    )
    asyncio.run(supabase_store.update_design("d1", _design(), "u1"))

    post_url, post_json = calls[2][1], calls[2][2]
    assert post_url == "http://sb.test/rest/v1/design_versions"
    assert post_json["design_id"] == "d1"
    assert post_json["version_number"] == 4
    assert post_json["change_summary"] == "autosave"
    snapshot = post_json["snapshot_json"]
    assert snapshot["id"] == "d1"
    assert snapshot["widthMm"] == 50.0
    assert snapshot["stitchCount"] == 2
    assert len(snapshot["stitches"]) == 2  # full fidelity: stitches ride along
    assert snapshot["colorStops"][0]["stopNumber"] == 1


def test_update_design_missing_version_column_defaults_to_two(monkeypatch):
    calls = install_fake_client(
        monkeypatch,
        [FakeResponse([{"id": "d1", "version": None}]), FakeResponse([]), FakeResponse([])],
    )
    result = asyncio.run(supabase_store.update_design("d1", _design(), "u1"))
    assert result is not None and result.version == 2
    assert calls[1][2]["version"] == 2


def test_update_design_propagates_patch_failure(monkeypatch):
    install_fake_client(
        monkeypatch,
        [FakeResponse([{"id": "d1", "version": 3}]), FakeResponse(None, status_code=500)],
    )
    with pytest.raises(httpx.HTTPError):
        asyncio.run(supabase_store.update_design("d1", _design(), "u1"))


def test_rename_design_true_when_row_returned(monkeypatch):
    calls = install_fake_client(monkeypatch, [FakeResponse([{"id": "d1", "name": "New"}])])
    assert asyncio.run(supabase_store.rename_design("d1", "New", "u1")) is True
    assert calls[0][0] == "PATCH"
    assert calls[0][2] == {"name": "New"}


def test_rename_design_false_when_no_rows_matched(monkeypatch):
    install_fake_client(monkeypatch, [FakeResponse([])])
    assert asyncio.run(supabase_store.rename_design("d1", "New", "u1")) is False


def test_rename_design_url_is_scoped_by_id_and_user(monkeypatch):
    calls = install_fake_client(monkeypatch, [FakeResponse([{"id": "d1"}])])
    asyncio.run(supabase_store.rename_design("d1", "New", "u1"))
    # Ownership lives in the URL filter — dropping user_id would let any user rename any design.
    assert calls[0][1] == "http://sb.test/rest/v1/designs?id=eq.d1&user_id=eq.u1"


def test_rename_design_propagates_http_error(monkeypatch):
    install_fake_client(monkeypatch, [FakeResponse(None, status_code=403)])
    with pytest.raises(httpx.HTTPError):
        asyncio.run(supabase_store.rename_design("d1", "New", "u1"))
