"""Plan tiers and premium-feature gating (v2 Part 35).

Three tiers. The matrix below is the single source of truth — the admin
dashboard renders it and the gate dependency enforces it.

Enforcement is OPT-IN via ``STITCHIQ_ENFORCE_PLANS=1``: the shipped LAN
topology (and the whole pre-Part-35 test suite) runs with every feature open,
exactly as before. A public deployment flips the switch. Admins always pass.

There is deliberately no billing here: plans are assigned by an admin. Wiring
a payment processor changes who calls ``set_plan``, not this gate.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException

from app.services import supabase_store, user_store

ENFORCE_ENV = "STITCHIQ_ENFORCE_PLANS"

# feature key -> minimum tier. Tier order: free < pro < studio.
_TIER_ORDER = {"free": 0, "pro": 1, "studio": 2}

FEATURE_MIN_PLAN: dict[str, str] = {
    # The pro deliverable: full production package ZIP + worksheet PDF.
    "package_export": "pro",
    "worksheet_pdf": "pro",
    # Path optimization and format conversion are classic paid tools.
    "optimize": "pro",
    "convert": "pro",
    # The photo/textured pipeline and large-format hoops are the studio tier.
    "photo_pipeline": "studio",
    "large_hoop": "studio",
}

# Free tier's hoop ceiling (mm). 130x180 is the ubiquitous mid-size hoop; a
# request beyond EITHER axis of 180x130 (rotated fits count) needs "large_hoop".
FREE_HOOP_MAX_MM = (130.0, 180.0)

PLAN_DESCRIPTIONS = {
    "free": "Digitize, letter, edit and export — mid-size hoops, all day.",
    "pro": "Adds production package ZIP, worksheet PDF, optimizer and converter.",
    "studio": "Everything, plus the photo pipeline and large-format hoops.",
}


def enforcing() -> bool:
    """True only when gating can actually resolve a caller's plan.

    Plans live in the LOCAL account store. When Supabase is the auth backend,
    a valid Supabase JWT resolves to no local profile, so every caller —
    including paying ones — would read as "free" and be refused. Failing OPEN
    there is the only safe direction: an operator who flips the switch on a
    cloud deployment gets today's behaviour, not a store-wide outage. Wiring
    plans into Supabase's own users table is what turns this back on.
    """
    if os.environ.get(ENFORCE_ENV) != "1":
        return False
    return not supabase_store.is_enabled()


def plan_for_request(authorization: str | None) -> tuple[str, str]:
    """Resolve (plan, role) for a request's Authorization header.

    Anonymous callers are "free"/"user". Only local accounts carry plans
    today; a Supabase deployment stores plans in its own users table and is
    out of scope for the local gate.
    """
    if not authorization:
        return "free", "user"
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return "free", "user"
    profile = user_store.get_store().verify_token(parts[1].strip())
    if not profile:
        return "free", "user"
    return profile.get("plan", "free"), profile.get("role", "user")


def hoop_needs_large(hoop_w: float, hoop_h: float) -> bool:
    a, b = sorted((hoop_w, hoop_h))
    fa, fb = sorted(FREE_HOOP_MAX_MM)
    return a > fa or b > fb


def require_feature(feature: str):
    """Dependency factory: 402 when the caller's plan lacks ``feature``.

    Inert unless STITCHIQ_ENFORCE_PLANS=1. Admins bypass every gate.
    """
    min_plan = FEATURE_MIN_PLAN[feature]

    async def _gate(authorization: str | None = Header(default=None)) -> None:
        if not enforcing():
            return
        plan, role = plan_for_request(authorization)
        if role == "admin":
            return
        if _TIER_ORDER[plan] < _TIER_ORDER[min_plan]:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"'{feature}' needs the {min_plan.upper()} plan "
                    f"(you are on {plan.upper()}). An admin can upgrade "
                    "your account from the dashboard."
                ),
            )

    return _gate


def check_hoop_allowed(authorization: str | None, hoop_w: float, hoop_h: float) -> None:
    """402 for a beyond-free hoop when enforcement is on (admin bypasses)."""
    if not enforcing() or not hoop_needs_large(hoop_w, hoop_h):
        return
    plan, role = plan_for_request(authorization)
    if role == "admin" or _TIER_ORDER[plan] >= _TIER_ORDER["studio"]:
        return
    raise HTTPException(
        status_code=402,
        detail=(
            f"Hoops beyond {FREE_HOOP_MAX_MM[0]:.0f}x{FREE_HOOP_MAX_MM[1]:.0f}mm "
            f"need the STUDIO plan (you are on {plan.upper()})."
        ),
    )
