"""Supabase-backed persistence for designs (spec §8).

Talks to the project's PostgREST + Auth-admin API with the **service key** (which
bypasses RLS — the browser never touches these tables directly, only via FastAPI).
Everything degrades gracefully when Supabase isn't configured: ``is_enabled()`` is
False and the router falls back to in-memory storage, so the app and the offline
pytest suite run without any keys.

Persistence model:
- ``designs`` / ``design_objects`` / ``color_stops`` hold queryable metadata.
- ``design_versions.snapshot_json`` holds the **full** Design (stitches + contours),
  so a fetched design round-trips at full fidelity (re-editable, re-exportable).
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.models.design import Design

# A single system/owner user backs all cloud designs until per-user auth is wired on
# the frontend. designs.user_id is NOT NULL -> FK to public.users -> FK to auth.users,
# so we must have a real auth user; we get-or-create it lazily and cache the uuid.
_DEV_EMAIL = "studio@stitchiq.local"
_dev_user_id: str | None = None


def is_enabled() -> bool:
    """True when a Supabase URL + service key are configured."""
    return bool(settings.supabase_url and settings.supabase_service_key)


def _rest() -> str:
    return settings.supabase_url.rstrip("/") + "/rest/v1"


def _auth() -> str:
    return settings.supabase_url.rstrip("/") + "/auth/v1"


def _headers(prefer: str | None = None) -> dict[str, str]:
    h = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


async def _ensure_owner(client: httpx.AsyncClient) -> str:
    """Get-or-create the system owner user; cache and return its uuid."""
    global _dev_user_id
    if _dev_user_id:
        return _dev_user_id

    # Find an existing auth user with our email.
    uid: str | None = None
    r = await client.get(f"{_auth()}/admin/users?per_page=200", headers=_headers())
    if r.status_code == 200:
        for u in r.json().get("users", []):
            if u.get("email") == _DEV_EMAIL:
                uid = u["id"]
                break

    # Create it if missing.
    if uid is None:
        r = await client.post(
            f"{_auth()}/admin/users",
            headers=_headers(),
            json={"email": _DEV_EMAIL, "email_confirm": True},
        )
        r.raise_for_status()
        uid = r.json()["id"]

    # Mirror into public.users (idempotent — ignore duplicates).
    await client.post(
        f"{_rest()}/users",
        headers=_headers("resolution=merge-duplicates"),
        json={"id": uid},
    )
    _dev_user_id = uid
    return uid


async def create_design(design: Design) -> Design:
    """Persist a design: metadata rows + a full-fidelity snapshot. Returns it with id/createdAt."""
    async with httpx.AsyncClient(timeout=30) as client:
        owner = await _ensure_owner(client)

        r = await client.post(
            f"{_rest()}/designs",
            headers=_headers("return=representation"),
            json={
                "user_id": owner,
                "name": design.name,
                "stitch_count": design.stitch_count,
                "colors": len(design.color_stops),
                "width_mm": design.width_mm,
                "height_mm": design.height_mm,
                "fabric_type": design.fabric_type,
                "version": design.version,
                "status": design.status,
            },
        )
        r.raise_for_status()
        created = r.json()[0]
        did = created["id"]

        if design.objects:
            await client.post(
                f"{_rest()}/design_objects",
                headers=_headers(),
                json=[
                    {
                        "design_id": did,
                        "sequence_order": o.sequence_order,
                        "object_name": o.name,
                        "stitch_type": o.stitch_type,
                        "color_stop": o.color_stop,
                        "density": o.density,
                        "stitch_angle": o.stitch_angle,
                        "underlay_type": o.underlay_type,
                        "pull_compensation": o.pull_compensation,
                        "entry_point": o.entry_point.model_dump() if o.entry_point else None,
                        "exit_point": o.exit_point.model_dump() if o.exit_point else None,
                        "connect_method": o.connect_method,
                        "stitch_count": o.stitch_count,
                    }
                    for o in design.objects
                ],
            )

        if design.color_stops:
            await client.post(
                f"{_rest()}/color_stops",
                headers=_headers(),
                json=[
                    {
                        "design_id": did,
                        "stop_number": c.stop_number,
                        "thread_brand": c.thread_brand,
                        "catalog_number": c.catalog_number,
                        "thread_name": c.thread_name,
                        "hex_color": c.hex,
                        "stitch_count": c.stitch_count,
                    }
                    for c in design.color_stops
                ],
            )

        snapshot = design.model_dump(by_alias=True)
        snapshot["id"] = did
        await client.post(
            f"{_rest()}/design_versions",
            headers=_headers(),
            json={
                "design_id": did,
                "version_number": design.version,
                "snapshot_json": snapshot,
                "change_summary": "cloud save",
            },
        )

        return design.model_copy(update={"id": did, "created_at": created.get("created_at")})


async def list_designs() -> list[Design]:
    """Lightweight metadata listing (no stitches/objects), newest first."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_rest()}/designs?select=*&order=created_at.desc",
            headers=_headers(),
        )
        r.raise_for_status()
        return [
            Design(
                id=row["id"],
                name=row["name"],
                width_mm=float(row.get("width_mm") or 0),
                height_mm=float(row.get("height_mm") or 0),
                fabric_type=row.get("fabric_type"),
                stitch_count=row.get("stitch_count") or 0,
                version=row.get("version") or 1,
                status=row.get("status") or "draft",
                created_at=row.get("created_at"),
            )
            for row in r.json()
        ]


async def get_design(design_id: str) -> Design | None:
    """Fetch the latest full-fidelity snapshot for a design, or None if absent."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_rest()}/design_versions"
            f"?design_id=eq.{design_id}&select=snapshot_json&order=version_number.desc&limit=1",
            headers=_headers(),
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        return Design.model_validate(rows[0]["snapshot_json"])


async def delete_design(design_id: str) -> None:
    """Delete a design (children cascade via FK)."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{_rest()}/designs?id=eq.{design_id}", headers=_headers())
        r.raise_for_status()
