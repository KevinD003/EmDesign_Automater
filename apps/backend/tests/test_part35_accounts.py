"""v2 Part 35 — accounts: password reset by email, roles/plans, admin, gating.

Everything here runs against the file-backed local store repointed to a tmp
path, with the mail outbox repointed too — the reset test reads the token out
of the actual .eml the mailer wrote, so the loop is tested end to end exactly
as a user would travel it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import user_store


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(tmp_path / "users.json"))
    monkeypatch.setenv("STITCHIQ_OUTBOX", str(tmp_path / "outbox"))
    monkeypatch.delenv("SMTP_HOST", raising=False)
    user_store.reset_store_cache()
    yield TestClient(app)
    user_store.reset_store_cache()


def _signup(client, username, pin="1234", email=None):
    r = client.post(
        "/api/auth/local/profiles",
        json={"username": username, "pin": pin, "email": email},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_first_profile_is_admin_then_users(client):
    _signup(client, "operator")
    second = _signup(client, "customer")
    me = client.get(
        "/api/auth/local/me",
        headers={"Authorization": f"Bearer {second['accessToken']}"},
    ).json()
    assert me["role"] == "user" and me["plan"] == "free"


def test_reset_flow_end_to_end(client, tmp_path):
    """forgot -> .eml lands in the outbox -> token from the email resets the
    PIN -> old PIN dead, new PIN works, old sessions revoked, link single-use."""
    session = _signup(client, "ada", pin="4321", email="ada@example.com")

    r = client.post(
        "/api/auth/local/forgot-password", json={"email": "ada@example.com"}
    )
    assert r.status_code == 202

    emls = list((tmp_path / "outbox").glob("*.eml"))
    assert len(emls) == 1, "exactly one reset email must be spooled"
    body = emls[0].read_text()
    token = re.search(r"/#/reset\?token=([A-Za-z0-9_-]+)", body).group(1)

    r = client.post(
        "/api/auth/local/reset-password", json={"token": token, "new_pin": "9876"}
    )
    assert r.status_code == 200 and r.json()["username"] == "ada"

    assert (
        client.post(
            "/api/auth/local/login", json={"username": "ada", "pin": "4321"}
        ).status_code
        == 401
    ), "the old PIN must be dead"
    assert (
        client.post(
            "/api/auth/local/login", json={"username": "ada", "pin": "9876"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/auth/local/me",
            headers={"Authorization": f"Bearer {session['accessToken']}"},
        ).status_code
        == 401
    ), "pre-reset sessions must be revoked"
    assert (
        client.post(
            "/api/auth/local/reset-password",
            json={"token": token, "new_pin": "5555"},
        ).status_code
        == 400
    ), "a reset link works exactly once"


def test_forgot_password_never_enumerates(client, tmp_path):
    _signup(client, "bea", email="bea@example.com")
    known = client.post(
        "/api/auth/local/forgot-password", json={"email": "bea@example.com"}
    )
    unknown = client.post(
        "/api/auth/local/forgot-password", json={"email": "nobody@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    # Only the real account got mail — the response never says which.
    assert len(list((tmp_path / "outbox").glob("*.eml"))) == 1


def test_login_accepts_email_as_identifier(client):
    _signup(client, "cyd", pin="2468", email="cyd@example.com")
    r = client.post(
        "/api/auth/local/login", json={"username": "cyd@example.com", "pin": "2468"}
    )
    assert r.status_code == 200 and r.json()["username"] == "cyd"


def test_admin_endpoints_guarded(client):
    operator = _signup(client, "operator")
    customer = _signup(client, "customer")
    admin_h = {"Authorization": f"Bearer {operator['accessToken']}"}
    user_h = {"Authorization": f"Bearer {customer['accessToken']}"}

    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/admin/users", headers=user_h).status_code == 403

    users = client.get("/api/admin/users", headers=admin_h).json()
    assert {u["username"] for u in users} == {"operator", "customer"}

    r = client.post(
        f"/api/admin/users/{customer['userId']}/plan",
        json={"plan": "studio"},
        headers=admin_h,
    )
    assert r.status_code == 200 and r.json()["plan"] == "studio"

    # The only admin cannot demote themselves into a lockout.
    r = client.post(
        f"/api/admin/users/{operator['userId']}/role",
        json={"role": "user"},
        headers=admin_h,
    )
    assert r.status_code == 422


def test_plan_gate_blocks_free_allows_paid_and_is_inert_by_default(
    client, monkeypatch
):
    operator = _signup(client, "operator")  # admin
    free = _signup(client, "freeuser")
    admin_h = {"Authorization": f"Bearer {operator['accessToken']}"}
    free_h = {"Authorization": f"Bearer {free['accessToken']}"}
    design = {
        "name": "d",
        "widthMm": 10,
        "heightMm": 10,
        "stitches": [],
        "colorStops": [],
        "objects": [],
    }

    # Default (no env): the gate is inert — pre-Part-35 behaviour, whole suite.
    assert (
        client.post("/api/optimize/path", json=design, headers=free_h).status_code
        != 402
    )

    monkeypatch.setenv("STITCHIQ_ENFORCE_PLANS", "1")
    r = client.post("/api/optimize/path", json=design, headers=free_h)
    assert r.status_code == 402 and "PRO" in r.json()["detail"]
    assert (
        client.post("/api/export/package", json=design, headers=free_h).status_code
        == 402
    )
    # Anonymous callers are refused at the AUTH gate, not billed as free tier:
    # compute endpoints require current_user since CTO A11, and the dependency
    # runs before the plan gate can classify anyone. (Pre-A11 this asserted
    # 402 — anonymous-as-free — which was itself the S2 hole.)
    assert client.post("/api/optimize/path", json=design).status_code == 401
    # Admins bypass every gate.
    assert (
        client.post("/api/optimize/path", json=design, headers=admin_h).status_code
        != 402
    )
    # An upgraded plan passes.
    client.post(
        f"/api/admin/users/{free['userId']}/plan",
        json={"plan": "pro"},
        headers=admin_h,
    )
    assert (
        client.post("/api/optimize/path", json=design, headers=free_h).status_code
        != 402
    )


def test_enforcement_fails_open_on_a_supabase_deployment(client, monkeypatch):
    """Plans live in the LOCAL store. With Supabase as the auth backend a valid
    cloud token resolves to no local profile, so enforcing would read EVERY
    caller — including paying ones — as free and refuse them. Enforcement must
    fail open there rather than take the whole store offline."""
    from app.services import plans, supabase_store

    monkeypatch.setenv("STITCHIQ_ENFORCE_PLANS", "1")
    assert plans.enforcing() is True

    monkeypatch.setattr(supabase_store, "is_enabled", lambda: True)
    assert plans.enforcing() is False
    design = {
        "name": "d",
        "widthMm": 10,
        "heightMm": 10,
        "stitches": [],
        "colorStops": [],
        "objects": [],
    }
    assert client.post("/api/optimize/path", json=design).status_code != 402


def test_free_hoop_cap_only_when_enforcing(client, monkeypatch, tmp_path):
    img = tmp_path / "t.png"
    import cv2
    import numpy as np

    arr = np.full((60, 60, 3), 255, np.uint8)
    cv2.circle(arr, (30, 30), 20, (200, 40, 40), -1)
    cv2.imwrite(str(img), arr)
    data = img.read_bytes()

    def post(hoop):
        return client.post(
            "/api/digitize",
            files={"file": ("t.png", data, "image/png")},
            data={"hoop_size": hoop},
        )

    assert post("360x350").status_code == 200  # inert by default
    monkeypatch.setenv("STITCHIQ_ENFORCE_PLANS", "1")
    r = post("360x350")
    assert r.status_code == 402 and "STUDIO" in r.json()["detail"]
    assert post("100x100").status_code == 200, "free hoops still digitize"
