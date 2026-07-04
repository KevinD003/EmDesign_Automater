"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.services import supabase_auth, supabase_store

# Sentinel user for offline/CI mode (Supabase not configured) — auth is skipped so the
# in-memory store and the keyless test suite keep working.
LOCAL_USER = "local-dev"


async def current_user(authorization: str | None = Header(default=None)) -> str:
    """Resolve the acting user's id from the Bearer token.

    - Supabase configured  -> a valid token is REQUIRED; returns the verified user id.
    - Supabase not configured (offline/CI) -> returns the LOCAL_USER sentinel, no auth.
    """
    if not supabase_store.is_enabled():
        return LOCAL_USER
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    token = authorization.split(" ", 1)[1].strip()
    user = await supabase_auth.verify_token(token)
    if not user or "id" not in user:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return user["id"]
