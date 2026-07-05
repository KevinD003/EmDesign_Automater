"""Auth endpoints (spec §8) — thin proxies over Supabase GoTrue.

The browser posts credentials here and gets back a Supabase session (access_token +
user). It stores the token and sends it as ``Authorization: Bearer`` on design calls.
Returns 503 when Supabase isn't configured (offline mode has no accounts).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.deps import current_user
from app.models.design import CamelModel
from app.services import supabase_auth

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("invalid email address")
        return v


class Session(CamelModel):
    access_token: str  # -> accessToken on the wire
    refresh_token: str | None = None
    user_id: str
    email: str | None = None


def _to_session(raw: dict) -> Session:
    user = raw.get("user") or {}
    return Session(
        access_token=raw["access_token"],
        refresh_token=raw.get("refresh_token"),
        user_id=user.get("id", ""),
        email=user.get("email"),
    )


def _require_enabled() -> None:
    if not supabase_auth.is_enabled():
        raise HTTPException(status_code=503, detail="auth unavailable — Supabase not configured")


@router.post("/signup", response_model=Session, status_code=201)
async def signup(creds: Credentials) -> Session:
    _require_enabled()
    if len(creds.password) < 6:
        raise HTTPException(status_code=422, detail="password must be at least 6 characters")
    try:
        session, error = await supabase_auth.signup(creds.email, creds.password)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="auth backend error") from exc
    if error:
        raise HTTPException(status_code=409, detail=error)
    return _to_session(session)


@router.post("/login", response_model=Session)
async def login(creds: Credentials) -> Session:
    _require_enabled()
    try:
        session = await supabase_auth.login(creds.email, creds.password)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="auth backend error") from exc
    if session is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return _to_session(session)


@router.get("/me")
async def me(user_id: str = Depends(current_user)) -> dict[str, str]:
    """Echo the authenticated user id (401 if the token is missing/invalid)."""
    return {"userId": user_id}
