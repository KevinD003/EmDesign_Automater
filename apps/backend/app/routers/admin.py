"""Admin panel API (v2 Part 35) — local-account operator tools.

Guarded by ``require_admin``: a valid local bearer token whose profile carries
``role == "admin"``. The FIRST profile created on a fresh store is the admin
(the person who installs the server is the operator); admins can promote
others. Supabase deployments manage users in Supabase itself, so this router
serves the local topology only.

- GET  /admin/users                     -> full public user list
- POST /admin/users/{user_id}/plan     {plan}  -> updated user
- POST /admin/users/{user_id}/role     {role}  -> updated user
- GET  /admin/stats                     -> platform counters + plan matrix

Non-admin token -> 403; missing/invalid token -> 401. Every response uses the
store's public view — hashes and salts never leave the store.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services import plans as plans_svc
from app.services.user_store import UserStore, get_store

router = APIRouter(prefix="/admin", tags=["admin"])

StoreDep = Annotated[UserStore, Depends(get_store)]


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def require_admin(
    store: StoreDep,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    token = _bearer_token(authorization)
    public = store.verify_token(token) if token else None
    if public is None:
        raise HTTPException(status_code=401, detail="authentication required")
    if public.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin access required")
    return public


AdminDep = Annotated[dict, Depends(require_admin)]


class PlanUpdate(BaseModel):
    plan: str


class RoleUpdate(BaseModel):
    role: str


@router.get("/users")
def list_users(store: StoreDep, _admin: AdminDep) -> list[dict]:
    return store.list_profiles()


@router.post("/users/{user_id}/plan")
def set_plan(user_id: str, req: PlanUpdate, store: StoreDep, _admin: AdminDep) -> dict:
    try:
        return store.set_plan(user_id, req.plan)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown user") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/users/{user_id}/role")
def set_role(user_id: str, req: RoleUpdate, store: StoreDep, _admin: AdminDep) -> dict:
    try:
        return store.set_role(user_id, req.role)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown user") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/stats")
def stats(store: StoreDep, _admin: AdminDep) -> dict:
    users = store.list_profiles()
    by_plan: dict[str, int] = {}
    for u in users:
        by_plan[u.get("plan", "free")] = by_plan.get(u.get("plan", "free"), 0) + 1
    return {
        "users": len(users),
        "admins": sum(1 for u in users if u.get("role") == "admin"),
        "byPlan": by_plan,
        "enforcing": plans_svc.enforcing(),
        "features": plans_svc.FEATURE_MIN_PLAN,
        "planDescriptions": plans_svc.PLAN_DESCRIPTIONS,
    }
