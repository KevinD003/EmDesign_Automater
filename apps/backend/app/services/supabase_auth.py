"""Supabase Auth (GoTrue) integration — signup / login / token verification.

The frontend never holds the service key; it authenticates through these thin proxy
endpoints and receives a normal Supabase user JWT (access_token). It then sends that
token as ``Authorization: Bearer`` on design calls, and the backend verifies it here
(``verify_token``) to derive the acting user's id.

Signup uses the **admin** API with ``email_confirm=true`` so the app is self-serve
(no email round-trip needed for this local/studio context), then immediately logs in
to return a session. See db/schema.sql for the users/RLS model.
"""

from __future__ import annotations

import httpx

from app.config import settings


def is_enabled() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key and settings.supabase_anon_key)


def _auth() -> str:
    return settings.supabase_url.rstrip("/") + "/auth/v1"


def _anon_headers() -> dict[str, str]:
    return {"apikey": settings.supabase_anon_key, "Content-Type": "application/json"}


def _service_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
    }


async def verify_token(access_token: str) -> dict | None:
    """Return the Supabase user for a bearer access token, or None if invalid/expired."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{_auth()}/user",
            headers={"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {access_token}"},
        )
        return r.json() if r.status_code == 200 else None


async def login(email: str, password: str) -> dict | None:
    """Password grant. Returns the token/session dict (access_token, user, …) or None."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{_auth()}/token?grant_type=password",
            headers=_anon_headers(),
            json={"email": email, "password": password},
        )
        return r.json() if r.status_code == 200 else None


async def refresh(refresh_token: str) -> dict | None:
    """Refresh grant (CTO A15/N5). GoTrue access tokens live ~3600s; without
    this the frontend had no way to renew one, so cloud save silently broke an
    hour into every session. Returns the new token/session dict or None."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{_auth()}/token?grant_type=refresh_token",
            headers=_anon_headers(),
            json={"refresh_token": refresh_token},
        )
        return r.json() if r.status_code == 200 else None


async def signup(email: str, password: str) -> tuple[dict | None, str | None]:
    """Create a confirmed user (admin) then log in. Returns (session, error)."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{_auth()}/admin/users",
            headers=_service_headers(),
            json={"email": email, "password": password, "email_confirm": True},
        )
        if r.status_code not in (200, 201):
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("msg") or body.get("error_description") or body.get("message") or "signup failed"
            # 422 == already registered
            return None, msg
    session = await login(email, password)
    if session is None:
        return None, "account created but login failed"
    return session, None
