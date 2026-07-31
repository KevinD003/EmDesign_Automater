"""Shared FastAPI dependencies."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException

from app.services import supabase_auth, supabase_store, user_store

# Sentinel user for offline mode when local auth is NOT in use. Keeps the keyless
# test suite and a single-operator dev box working without forcing a login.
LOCAL_USER = "local-dev"

# Opt-OUT switch for local-account enforcement (v2 Part 21). Enforcement is ON by
# default in offline mode: before this, `current_user` returned LOCAL_USER for
# every caller whenever Supabase was unconfigured — which is the launch topology
# — so all users shared one namespace and an UNAUTHENTICATED caller could list,
# overwrite and DELETE anyone's designs (reproduced end-to-end by the Part 21
# review layer). Set STITCHIQ_OPEN_ACCESS=1 only for a single-user machine.
OPEN_ACCESS_ENV = "STITCHIQ_OPEN_ACCESS"


def _bearer(authorization: str | None) -> str | None:
    """The token from an `Authorization: Bearer <token>` header, or None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip() or None


def _local_user(authorization: str | None) -> str:
    """Resolve a local-account token to its user id, or 401.

    Falls back to LOCAL_USER only when no local profiles exist at all (a fresh
    install has nobody to authenticate as, and refusing every request would
    make the app unusable before the first signup) or when the operator has
    explicitly opted out.
    """
    if os.environ.get(OPEN_ACCESS_ENV) == "1":
        return LOCAL_USER
    store = user_store.get_store()
    if not store.list_profiles():
        return LOCAL_USER
    token = _bearer(authorization)
    user_id = user_store.resolve_bearer(f"Bearer {token}") if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="authentication required")
    return user_id


async def current_user(authorization: str | None = Header(default=None)) -> str:
    """Resolve the acting user's id from the Bearer token.

    - Supabase configured -> a valid Supabase token is REQUIRED.
    - Otherwise -> a local-account token is required once any profile exists.
    """
    if not supabase_store.is_enabled():
        return _local_user(authorization)
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="authentication required")
    user = await supabase_auth.verify_token(token)
    if not user or "id" not in user:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return user["id"]
