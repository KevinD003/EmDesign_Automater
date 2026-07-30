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


async def _ensure_user_row(client: httpx.AsyncClient, user_id: str) -> None:
    """Mirror an authenticated auth.users id into public.users (idempotent)."""
    await client.post(
        f"{_rest()}/users",
        headers=_headers("resolution=merge-duplicates"),
        json={"id": user_id},
    )


async def create_design(design: Design, user_id: str) -> Design:
    """Persist a design for a user: metadata rows + full-fidelity snapshot. Returns it with id/createdAt."""
    async with httpx.AsyncClient(timeout=30) as client:
        await _ensure_user_row(client, user_id)

        r = await client.post(
            f"{_rest()}/designs",
            headers=_headers("return=representation"),
            json={
                "user_id": user_id,
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

        # PostgREST has no cross-table transaction. The full-fidelity design lives ONLY
        # in design_versions.snapshot_json (get_design reads from there), so if any child
        # write — especially the snapshot — fails, we must NOT leave a phantom designs row
        # that lists but 404s on open. Check every write; compensate by deleting the row.
        try:
            if design.objects:
                resp = await client.post(
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
                resp.raise_for_status()

            if design.color_stops:
                resp = await client.post(
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
                resp.raise_for_status()

            snapshot = design.model_dump(by_alias=True)
            snapshot["id"] = did
            resp = await client.post(
                f"{_rest()}/design_versions",
                headers=_headers(),
                json={
                    "design_id": did,
                    "version_number": design.version,
                    "snapshot_json": snapshot,
                    "change_summary": "cloud save",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            # Roll back the orphaned designs row so the client sees a real error, not a
            # phantom 201. Best-effort — ignore delete failures, re-raise the original.
            try:
                await client.delete(f"{_rest()}/designs?id=eq.{did}", headers=_headers())
            except httpx.HTTPError:
                pass
            raise

        return design.model_copy(update={"id": did, "created_at": created.get("created_at")})


_PAGE = 1000  # Supabase/PostgREST caps a plain GET at ~1000 rows; page past it explicitly.


async def _get_all(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Fetch ALL rows for a PostgREST query (``query`` already contains ``?...``),
    paging in blocks of _PAGE so users with >1000 designs aren't silently truncated."""
    rows: list[dict] = []
    offset = 0
    while True:
        r = await client.get(f"{query}&limit={_PAGE}&offset={offset}", headers=_headers())
        r.raise_for_status()
        page = r.json()
        rows.extend(page)
        if len(page) < _PAGE:
            return rows
        offset += _PAGE


async def list_designs(user_id: str) -> list[Design]:
    """Lightweight metadata listing for one user (no stitches/objects), newest first."""
    async with httpx.AsyncClient(timeout=30) as client:
        all_rows = await _get_all(
            client, f"{_rest()}/designs?user_id=eq.{user_id}&select=*&order=created_at.desc"
        )
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
            for row in all_rows
        ]


async def design_stats(user_id: str) -> dict:
    """Aggregate a user's designs for the dashboard: counts + a recent list."""
    async with httpx.AsyncClient(timeout=30) as client:
        rows = await _get_all(
            client,
            f"{_rest()}/designs?user_id=eq.{user_id}"
            "&select=id,name,stitch_count,colors,created_at&order=created_at.desc",
        )
        return {
            "designCount": len(rows),
            "totalStitches": sum(int(row.get("stitch_count") or 0) for row in rows),
            "totalColors": sum(int(row.get("colors") or 0) for row in rows),
            "recent": [
                {
                    "id": row["id"],
                    "name": row.get("name") or "Untitled",
                    "stitchCount": int(row.get("stitch_count") or 0),
                    "savedAt": row.get("created_at") or "",
                }
                for row in rows[:8]
            ],
        }


async def get_design(design_id: str, user_id: str) -> Design | None:
    """Fetch a user's design at full fidelity, or None if absent / not theirs.

    The service key bypasses RLS, so ownership is enforced here in app code: the
    snapshot is only returned when the design row belongs to ``user_id``.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        owned = await client.get(
            f"{_rest()}/designs?id=eq.{design_id}&user_id=eq.{user_id}&select=id",
            headers=_headers(),
        )
        owned.raise_for_status()
        if not owned.json():
            return None
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


async def delete_design(design_id: str, user_id: str) -> None:
    """Delete a user's design (scoped by owner; children cascade via FK)."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(
            f"{_rest()}/designs?id=eq.{design_id}&user_id=eq.{user_id}", headers=_headers()
        )
        r.raise_for_status()
