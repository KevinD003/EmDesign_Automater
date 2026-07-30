"""Local (offline/LAN) profile auth — the no-cloud counterpart to routers/auth.py.

Contract: this router serves username+PIN profiles stored on disk via
app.services.user_store; Supabase auth in routers/auth.py stays the cloud path.

- POST /auth/local/profiles  {username, pin?} -> 201 LocalSession
  (wire: accessToken/userId/username/hasPin); duplicate username -> 409,
  invalid username or PIN -> 422.
- POST /auth/local/login     {username, pin?} -> 200 LocalSession;
  any failure -> 401 "invalid username or PIN" (never reveals whether the
  username exists).
- GET  /auth/local/profiles  -> public picker list
  {userId, username, hasPin, createdAt} — never salts or hashes.
- GET  /auth/local/me        Bearer token -> {userId, username}; missing or
  invalid token -> 401.
- POST /auth/local/logout    Bearer token -> 204 always (idempotent).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel

from app.models.design import CamelModel
from app.services.user_store import DuplicateUsernameError, UserStore, get_store

router = APIRouter(prefix="/auth/local", tags=["auth-local"])

# Resolved per-request so tests can repoint STITCHIQ_USER_STORE between requests.
StoreDep = Annotated[UserStore, Depends(get_store)]


class ProfileCredentials(BaseModel):
    username: str
    pin: str | None = None


class LocalSession(CamelModel):
    access_token: str  # -> accessToken on the wire
    user_id: str
    username: str
    has_pin: bool


class LocalProfile(CamelModel):
    user_id: str
    username: str
    has_pin: bool
    created_at: str


class LocalMe(CamelModel):
    user_id: str
    username: str


def _bearer_token(authorization: str | None) -> str | None:
    """Extract the token from `Bearer <token>` (scheme case-insensitive)."""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def _session(public: dict, token: str) -> LocalSession:
    return LocalSession(
        access_token=token,
        user_id=public["userId"],
        username=public["username"],
        has_pin=public["hasPin"],
    )


@router.post("/profiles", response_model=LocalSession, status_code=201)
def create_profile(
    creds: ProfileCredentials, store: StoreDep
) -> LocalSession:
    try:
        public = store.create_profile(creds.username, creds.pin)
    except DuplicateUsernameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _session(public, store.issue_token(public["userId"]))


@router.post("/login", response_model=LocalSession)
def login(
    creds: ProfileCredentials, store: StoreDep
) -> LocalSession:
    result = store.login(creds.username, creds.pin)
    if result is None:
        # Single message for unknown user AND wrong PIN — no enumeration.
        raise HTTPException(status_code=401, detail="invalid username or PIN")
    public, token = result
    return _session(public, token)


@router.get("/profiles", response_model=list[LocalProfile])
def list_profiles(store: StoreDep) -> list[LocalProfile]:
    return [LocalProfile(**p) for p in store.list_profiles()]


@router.get("/me", response_model=LocalMe)
def me(
    store: StoreDep,
    authorization: Annotated[str | None, Header()] = None,
) -> LocalMe:
    token = _bearer_token(authorization)
    public = store.verify_token(token) if token else None
    if public is None:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return LocalMe(user_id=public["userId"], username=public["username"])


@router.post("/logout", status_code=204)
def logout(
    store: StoreDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    token = _bearer_token(authorization)
    if token:
        store.revoke_token(token)  # unknown token is still a successful logout
    return Response(status_code=204)
